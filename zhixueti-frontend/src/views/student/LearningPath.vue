<script setup lang="ts">
defineOptions({ name: 'LearningPath' })

import { onMounted, onActivated, onUnmounted, onBeforeUnmount, ref, reactive, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CircleCheck, ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import { pathApi, type PathSummary } from '@/api/path'
import { useStudySession } from '@/composables/useStudySession'
import { useProfileStore } from '@/stores/profile'
import { useUserStore } from '@/stores/user'
import { useLearningPathStore } from '@/stores/learningPath'
import { formatPathProfileFields, formatPathUserText, formatWeakFocusList, resolveStudentLearningGoal, sanitizeStudentText } from '@/utils/profileDisplay'
import type { PathData, PathNode } from '@/types'
import { NODE_STATUS_MAP } from '@/types'
import PathTimeline from '@/components/PathTimeline.vue'
import PathGraph from '@/components/PathGraph.vue'
import { formatBeijingShort } from '@/utils/datetime'
import { savePathResourceGenIntent } from '@/utils/pathResourceGenIntent'

const router = useRouter()
const route = useRoute()
// 真实学习时长追踪：开启/结束学习会话，喂给学习数据看板
const studySession = useStudySession()
let nodeStudyStartedAt = 0
// 演示对比模式仅供答辩演示：URL 带 ?demo=1 时才显示入口
const demoEnabled = computed(() => String(route.query.demo || '') === '1')
const profileStore = useProfileStore()
const userStore = useUserStore()
const pathStore = useLearningPathStore()
const paths = ref<PathSummary[]>([])
const currentPath = ref<PathData | null>(null)
const loading = ref(false)
const planning = ref(false)
const viewMode = ref<'timeline' | 'graph'>('timeline')
const selectedNode = ref<PathNode | null>(null)
const progressVisible = ref(false)
const progressStep = ref(0)
const progressPercent = ref(0)
const demoRunning = ref(false)
const advancedOpen = ref(false)
const nodePanelRef = ref<HTMLElement | null>(null)
const graphHeight = ref<number | null>(null)
let nodePanelObserver: ResizeObserver | null = null

const DOMAIN_OPTIONS = [
  { value: 'machine_learning', label: '机器学习' },
  { value: 'computer_science', label: '计算机科学' },
  { value: 'software_engineering', label: '软件工程' },
  { value: 'data_structure', label: '数据结构' },
  { value: 'algorithm', label: '算法' },
  { value: 'mathematics', label: '数学' },
  { value: 'linear_algebra', label: '线性代数' },
]

function syncGraphHeight() {
  const el = nodePanelRef.value
  if (!el) return
  const h = Math.round(el.getBoundingClientRect().height)
  if (h > 0) graphHeight.value = h
}

function bindNodePanelObserver() {
  if (!nodePanelRef.value || typeof ResizeObserver === 'undefined') return
  nodePanelObserver?.disconnect()
  nodePanelObserver = new ResizeObserver(() => syncGraphHeight())
  nodePanelObserver.observe(nodePanelRef.value)
  syncGraphHeight()
}

const planForm = reactive({
  goal: pathStore.planForm.goal || '掌握机器学习基础',
  domain: pathStore.planForm.domain || 'machine_learning',
  title: pathStore.planForm.title || '',
  ignore_profile: pathStore.planForm.ignore_profile || false,
  supplement: pathStore.planForm.supplement || '',
})

if (pathStore.viewMode) viewMode.value = pathStore.viewMode

const PLAN_STEPS = [
  '读取用户 6 维学习画像',
  '学情数据分析，识别薄弱知识点',
  '分入门 / 进阶 / 提升三阶段拆分学习节点',
  '节点自动匹配多模态个性化学习资源',
  '多智能体内容校验，防幻觉生成最终路径',
]

const profileReady = computed(() =>
  profileStore.profile?.is_profile_built && (profileStore.profile?.completeness ?? 0) >= 0.8,
)

const profileFields = computed(() =>
  formatPathProfileFields(
    profileStore.profile,
    userStore.userInfo?.major,
    userStore.userInfo?.grade,
  ),
)

const completedNodes = computed(() => currentPath.value?.nodes.filter((n) => n.status === 3).length ?? 0)

const masteryHint = computed(() => {
  const score = selectedNode.value?.mastery_score
  if (score == null) return '暂无该节点习题数据，完成练习后将展示正确率与错因。'
  if (score < 0.6) return '该节点掌握度不足 60%，建议重新学习配套讲义巩固。'
  if (score < 0.8) return '掌握尚可，建议刷完错题后再推进。'
  return '掌握良好，可继续下一节点。'
})

const TYPE_LABEL: Record<string, string> = {
  document: '讲义',
  mindmap: '图谱',
  question: '习题',
  video: '动画',
  reading: '拓展',
  code: '实战',
}

async function loadPaths(force = false) {
  if (!force && pathStore.cached && pathStore.currentPath) {
    paths.value = pathStore.paths
    currentPath.value = pathStore.currentPath
    viewMode.value = pathStore.viewMode
    Object.assign(planForm, pathStore.planForm)
    selectedNode.value =
      pathStore.currentPath.nodes.find((n) => n.id === pathStore.selectedNodeId)
      || pathStore.currentPath.nodes[0]
      || null
    return
  }

  loading.value = true
  try {
    const summaries = await pathApi.list()
    paths.value = summaries
    if (!summaries.length) {
      currentPath.value = null
      selectedNode.value = null
      pathStore.clearCache()
      return
    }
    const targetId = currentPath.value?.id || pathStore.currentPath?.id || summaries[0].id
    const detail = await pathApi.get(targetId)
    currentPath.value = detail
    if (!selectedNode.value || !detail.nodes.some((n) => n.id === selectedNode.value!.id)) {
      selectedNode.value = detail.nodes[0] || null
    } else {
      selectedNode.value = detail.nodes.find((n) => n.id === selectedNode.value!.id) || detail.nodes[0] || null
    }
    persistPathCache()
  } finally {
    loading.value = false
  }
}

function persistPathCache() {
  pathStore.saveSnapshot({
    paths: paths.value,
    currentPath: currentPath.value,
    selectedNodeId: selectedNode.value?.id ?? null,
    viewMode: viewMode.value,
    planForm: { ...planForm },
  })
}

function toSummary(path: PathData): PathSummary {
  return {
    id: path.id,
    path_no: path.path_no,
    title: path.title,
    goal: path.goal,
    path_version: path.path_version,
    total_nodes: path.total_nodes,
    estimated_hours: path.estimated_hours,
    status: path.status,
    progress_rate: path.progress_rate,
    path_mode: path.path_mode,
    weak_focus: path.weak_focus,
    adaptive_node_count: path.adaptive_node_count,
    created_at: path.created_at,
    nodes: [],
  }
}

async function runProgressOverlay<T>(runner: () => Promise<T>): Promise<T> {
  progressVisible.value = true
  progressStep.value = 0
  progressPercent.value = 0
  const timer = window.setInterval(() => {
    if (progressStep.value < PLAN_STEPS.length - 1) {
      progressStep.value += 1
      progressPercent.value = Math.round(((progressStep.value + 1) / PLAN_STEPS.length) * 90)
    }
  }, 700)
  try {
    const result = await runner()
    progressStep.value = PLAN_STEPS.length - 1
    progressPercent.value = 100
    await new Promise((r) => setTimeout(r, 400))
    return result
  } finally {
    clearInterval(timer)
    progressVisible.value = false
  }
}

async function handlePlan(opts?: { adaptive?: boolean }) {
  if (!planForm.ignore_profile && !profileReady.value) {
    ElMessage.warning('请先完成 6 维画像构建（完整度≥80%），或勾选「忽略画像」生成通用路径')
    return
  }
  if (!planForm.goal.trim() || !sanitizeStudentText(planForm.goal)) {
    planForm.goal = resolveStudentLearningGoal(profileStore.profile)
  } else {
    planForm.goal = sanitizeStudentText(planForm.goal) || resolveStudentLearningGoal(profileStore.profile)
  }

  planning.value = true
  try {
    const path = await runProgressOverlay(() =>
      pathApi.plan({
        goal: planForm.goal,
        domain: planForm.domain,
        title: sanitizeStudentText(planForm.title) || undefined,
        ignore_profile: planForm.ignore_profile,
        supplement: planForm.supplement.trim() || undefined,
        adaptive: opts?.adaptive,
      }),
    )
    currentPath.value = path
    selectedNode.value = path.nodes[0] || null
    paths.value = [toSummary(path), ...paths.value.filter((p) => p.id !== path.id)]
    persistPathCache()
    ElMessage.success(opts?.adaptive ? '已按学情调整路径' : '三阶段路径已生成')
  } catch (e: unknown) {
    ElMessage.error((e as Error)?.message || '路径规划失败')
  } finally {
    planning.value = false
  }
}

async function handleReplan() {
  if (!currentPath.value) {
    ElMessage.warning('请先生成一条路径')
    return
  }
  planning.value = true
  try {
    const path = await runProgressOverlay(() =>
      pathApi.replan(currentPath.value!.id, {
        trigger_type: 'manual',
        reason: planForm.supplement.trim() || '根据学习完成度与薄弱点动态调整',
      }),
    )
    currentPath.value = path
    selectedNode.value = path.nodes.find((n) => n.is_adaptive) || path.nodes[0] || null
    paths.value = [toSummary(path), ...paths.value.filter((p) => p.id !== path.id)]
    persistPathCache()
    ElMessage.success('已根据当前学情调整路径')
  } catch (e: unknown) {
    ElMessage.error((e as Error)?.message || '重规划失败')
  } finally {
    planning.value = false
  }
}

async function onIgnoreProfileChange(val: boolean | string | number) {
  planForm.ignore_profile = Boolean(val)
  // 勾选后可重新生成对比；不强制立刻调用，给用户确认目标
  ElMessage.info(planForm.ignore_profile ? '已切换为通用标准路径模式，点击「全新生成路径」生效' : '已切回画像定制模式')
}

async function runDemoCompare() {
  if (demoRunning.value || planning.value) return
  demoRunning.value = true
  try {
    ElMessage.info('演示对比：先生成通用标准路径…')
    planForm.ignore_profile = true
    await handlePlan()
    await new Promise((r) => setTimeout(r, 1200))
    ElMessage.info('演示对比：再生成画像定制路径…')
    planForm.ignore_profile = false
    await handlePlan()
    ElMessage.success('演示对比完成：可在路径下拉中切换两套结果')
  } finally {
    demoRunning.value = false
  }
}

function onNodeClick(node: PathNode) {
  selectedNode.value = node
}

function goResource(resourceId: number, node: PathNode) {
  router.push({
    path: `/student/resources/${resourceId}`,
    query: { node_id: String(node.id), path_id: String(currentPath.value?.id) },
  })
}

function generateNodeResources(node: PathNode) {
  const pathId = currentPath.value?.id
  savePathResourceGenIntent({
    topic: node.node_name,
    goal: node.description?.slice(0, 120) || undefined,
    node_id: node.id,
    path_id: pathId,
  })
  // 清路径缓存，生成回来后强制拉新详情（含绑定结果）
  pathStore.clearCache()
  router.push({
    path: '/student/resources',
    query: {
      topic: node.node_name,
      ...(node.description ? { goal: node.description.slice(0, 120) } : {}),
      node_id: String(node.id),
      ...(pathId ? { path_id: String(pathId) } : {}),
      auto_generate: '1',
    },
  })
}

function viewNodeResources(node: PathNode) {
  selectedNode.value = node
}

async function startNode(node: PathNode) {
  if (node.status === 0) return ElMessage.warning('该节点尚未解锁，请先完成前置节点')
  try {
    const updated = await pathApi.updateNodeProgress(node.id, { status: 2 })
    currentPath.value = updated
    selectedNode.value = updated.nodes.find((n) => n.id === node.id) || node
    persistPathCache()
    if (currentPath.value) {
      nodeStudyStartedAt = Date.now()
      void studySession.end().then(() =>
        studySession.start({ path_id: currentPath.value?.id, node_id: node.id }),
      )
      void studySession.track({ event_type: 'page_view', target_id: node.id, event_target: 'path_node' })
    }
    if (node.resource_items.length) {
      goResource(node.resource_items[0].resource_id, node)
    } else {
      generateNodeResources(node)
    }
  } catch {
    ElMessage.error('无法开始学习该节点')
  }
}

async function completeNode(node: PathNode) {
  try {
    // 本次节点学习真实用时（上限 4 小时，防止挂机刷时长）
    const elapsedSec = nodeStudyStartedAt > 0
      ? Math.max(30, Math.min((Date.now() - nodeStudyStartedAt) / 1000, 4 * 3600))
      : 0
    currentPath.value = await pathApi.updateNodeProgress(node.id, {
      status: 3,
      mastery_score: 0.85,
      study_duration_sec: Math.round(elapsedSec) || undefined,
    })
    nodeStudyStartedAt = 0
    void studySession.track({ event_type: 'page_view', target_id: node.id, event_target: 'path_node_complete', event_data: { action: 'complete' } })
    void studySession.end()
    selectedNode.value = currentPath.value.nodes.find((n) => n.id === node.id) || null
    persistPathCache()
    ElMessage.success('节点已完成，路径进度已更新')
  } catch {
    ElMessage.error('节点完成状态更新失败')
  }
}

function switchPath(pathId: number) {
  pathApi.get(pathId).then((p) => {
    currentPath.value = p
    selectedNode.value = p.nodes[0] || null
    persistPathCache()
  })
}

function pathModeTag(p: PathData | PathSummary) {
  return p.path_mode === 'standard' ? '通用标准' : '画像定制'
}

function formatPathTime(iso: string | undefined) {
  return formatBeijingShort(iso, '')
}

/** 下拉收起时展示的短文案，避免标题重复堆叠 */
function pathSelectLabel(p: PathData | PathSummary) {
  const time = formatPathTime(p.created_at) || '未知时间'
  return `${time} · ${pathModeTag(p)}`
}

function displayPathTitle(p: PathData | PathSummary) {
  return formatPathUserText(p.title, '个性化学习路径')
}

function displayPathGoal(p: PathData) {
  return formatPathUserText(p.goal, '基于你的画像生成的学习目标')
}

onMounted(async () => {
  if (!userStore.userInfo) await userStore.fetchUser()
  if (!profileStore.profile) await profileStore.fetchProfile()
  if (!planForm.goal || planForm.goal === '掌握机器学习基础') {
    planForm.goal = resolveStudentLearningGoal(profileStore.profile)
  }
  await loadPaths()
  await nextTick()
  bindNodePanelObserver()
  window.addEventListener('resize', syncGraphHeight)
})

onActivated(async () => {
  // 从资源中心返回时需拉最新节点绑定；缓存被清或无本地数据则全量加载
  if (!pathStore.cached || !currentPath.value) {
    await loadPaths(true)
  } else if (currentPath.value?.id) {
    try {
      const detail = await pathApi.get(currentPath.value.id)
      const keepId = selectedNode.value?.id
      currentPath.value = detail
      selectedNode.value =
        detail.nodes.find((n) => n.id === keepId) || detail.nodes[0] || null
      persistPathCache()
    } catch {
      await loadPaths(true)
    }
  }
  await nextTick()
  bindNodePanelObserver()
  syncGraphHeight()
})

onBeforeUnmount(() => {
  persistPathCache()
  void studySession.end()
})

onUnmounted(() => {
  nodePanelObserver?.disconnect()
  window.removeEventListener('resize', syncGraphHeight)
})

watch(selectedNode, async () => {
  await nextTick()
  syncGraphHeight()
})

watch(currentPath, async () => {
  await nextTick()
  bindNodePanelObserver()
})

watch(viewMode, async () => {
  await nextTick()
  syncGraphHeight()
})
</script>

<template>
  <div class="space path-page">
    <div class="atmosphere" aria-hidden="true" />

    <header class="hero">
      <div class="hero-row">
        <p class="kicker">智课共生 · 路径规划</p>
        <button
          v-if="demoEnabled"
          type="button"
          class="ghost-link"
          :disabled="demoRunning || planning"
          @click="runDemoCompare"
        >
          {{ demoRunning ? '演示中…' : '演示对比模式 →' }}
        </button>
      </div>
      <div class="hero-main">
        <div class="hero-copy">
          <h1>学习路径</h1>
          <p class="subline">画像联动三阶段路径，学情变化时可调整，节点资源一键推送。</p>
        </div>
        <dl class="pulse">
          <div>
            <dt>画像完整度</dt>
            <dd :class="{ warn: !profileReady }">{{ ((profileStore.profile?.completeness || 0) * 100).toFixed(0) }}%</dd>
          </div>
          <div>
            <dt>路径</dt>
            <dd>{{ paths.length }}</dd>
          </div>
          <div>
            <dt>当前节点</dt>
            <dd>{{ currentPath ? `${completedNodes}/${currentPath.total_nodes || 0}` : '—' }}</dd>
          </div>
          <div class="accent">
            <dt>预计学时</dt>
            <dd>{{ currentPath?.estimated_hours ?? '—' }}</dd>
          </div>
        </dl>
      </div>
    </header>

    <main class="stage">
    <section class="block plan-panel">
      <div class="stage-head">
        <h2>规划工位</h2>
        <p>读取画像 → 识别薄弱点 → 入门 / 进阶 / 提升拆分 → 匹配资源</p>
      </div>

      <div class="profile-sync-bar" :class="{ ignored: planForm.ignore_profile }">
        <el-icon class="sync-check"><CircleCheck /></el-icon>
        <p class="sync-text">
          {{ planForm.ignore_profile ? '已忽略画像（通用标准路径）｜' : '已同步动态学习画像｜' }}
          专业：{{ profileFields.major }}｜薄弱模块：{{ profileFields.weakPoint }}｜学习偏好：{{ profileFields.learnStyle }}｜学习阶段：{{ profileFields.grade }}
          <a class="link" @click.prevent="router.push('/student/profile-dialogue')">去修改画像</a>
        </p>
        <el-tooltip content="关闭画像后系统将生成无个性化的通用标准化学习路径" placement="top">
          <el-checkbox
            :model-value="planForm.ignore_profile"
            class="ignore-check"
            @change="onIgnoreProfileChange"
          >
            本次生成忽略画像
          </el-checkbox>
        </el-tooltip>
      </div>

      <el-form label-position="top" class="plan-form">
        <div class="form-row-main">
          <el-form-item label="学习目标" class="item-goal">
            <el-input v-model="planForm.goal" placeholder="与画像学习目标一致，可按需修改" clearable />
          </el-form-item>
          <el-form-item label="学习领域" class="item-domain">
            <el-select
              v-model="planForm.domain"
              filterable
              allow-create
              default-first-option
              placeholder="选择或输入领域"
              style="width: 100%"
            >
              <el-option
                v-for="d in DOMAIN_OPTIONS"
                :key="d.value"
                :label="d.label"
                :value="d.value"
              />
            </el-select>
          </el-form-item>
        </div>

        <div class="advanced-wrap">
          <button type="button" class="advanced-btn" @click="advancedOpen = !advancedOpen">
            <el-icon>
              <ArrowUp v-if="advancedOpen" />
              <ArrowDown v-else />
            </el-icon>
            {{ advancedOpen ? '收起路径定制参数' : '展开路径定制参数' }}
          </button>
          <div v-show="advancedOpen" class="advanced-body">
            <el-form-item label="路径标题（选填）">
              <el-input v-model="planForm.title" placeholder="如：机器学习入门专属路径" clearable maxlength="40" show-word-limit />
            </el-form-item>
            <el-form-item label="路径定制补充需求（选填）">
              <el-input
                v-model="planForm.supplement"
                type="textarea"
                :rows="2"
                placeholder="期末冲刺、偏竞赛实战、精简入门、跳过简单基础节点"
              />
            </el-form-item>
          </div>
        </div>

        <div class="plan-actions">
          <p class="plan-tip">结合 6 维画像与补充需求，生成入门 → 进阶 → 提升三阶段路径</p>
          <div class="plan-btns">
            <el-tooltip
              :disabled="!planning"
              content="路径正在生成中，请稍候"
              placement="top"
            >
              <button type="button" class="btn primary lg" :disabled="planning" @click="handlePlan()">
                {{ planning ? '生成中…' : '全新生成路径' }}
              </button>
            </el-tooltip>
            <el-tooltip
              :content="!currentPath ? '请先生成一条路径，再根据学情调整' : (planning ? '路径正在生成中，请稍候' : '基于当前学情重新编排节点')"
              placement="top"
            >
              <button
                type="button"
                class="btn ghost lg"
                :disabled="planning || !currentPath"
                @click="handleReplan"
              >
                根据学情调整路径
              </button>
            </el-tooltip>
          </div>
          <div v-if="!currentPath && !planning" class="path-empty-cta">
            <p>还没有学习路径。填好上方目标后，点「全新生成路径」即可开始。</p>
            <el-button type="primary" link @click="router.push('/student/profile-dialogue')">先完善画像</el-button>
          </div>
        </div>
      </el-form>
    </section>

    <el-skeleton v-if="loading" :rows="6" animated />

    <div v-else-if="currentPath">
      <!-- 区域3：路径总览 -->
      <div class="path-header card">
        <div class="header-row">
          <div class="header-main">
            <div class="title-row">
              <h3>{{ displayPathTitle(currentPath) }}</h3>
              <el-tag size="small" effect="light" :type="currentPath.path_mode === 'standard' ? 'info' : 'success'">
                {{ pathModeTag(currentPath) }}
              </el-tag>
            </div>
            <p class="goal-line">{{ displayPathGoal(currentPath) }}</p>
          </div>
          <div v-if="paths.length > 1" class="path-switcher">
            <el-select
              class="history-select"
              :model-value="currentPath.id"
              placeholder="切换历史路径"
              popper-class="path-history-popper"
              @change="switchPath"
            >
              <template #prefix>
                <span class="history-prefix">历史</span>
              </template>
              <el-option
                v-for="(p, idx) in paths"
                :key="p.id"
                :label="pathSelectLabel(p)"
                :value="p.id"
              >
                <div class="history-item" :class="{ latest: idx === 0 }">
                  <div class="history-item-top">
                    <span class="history-title">{{ displayPathTitle(p) }}</span>
                    <span v-if="idx === 0" class="history-latest">最近</span>
                  </div>
                  <div class="history-meta">
                    <span>{{ formatPathTime(p.created_at) || '—' }}</span>
                    <span class="dot">·</span>
                    <span>{{ pathModeTag(p) }}</span>
                    <span class="dot">·</span>
                    <span>{{ p.nodes?.length || p.total_nodes || 0 }} 节点</span>
                  </div>
                </div>
              </el-option>
            </el-select>
          </div>
        </div>

        <div class="progress-block">
          <div class="progress-label-row">
            <span class="progress-label">节点进度</span>
            <span class="progress-pct">{{ Math.round((currentPath.progress_rate || 0) * 100) }}%</span>
          </div>
          <div class="segment-progress">
            <div
              v-for="n in currentPath.nodes"
              :key="n.id"
              class="seg"
              :class="{
                done: n.status === 3,
                weak: n.is_weak && n.status !== 3,
                pending: n.status < 3 && !n.is_weak,
              }"
              :title="n.node_name"
            />
          </div>
          <div class="seg-legend">
            <span><i class="dot done" />已完成</span>
            <span><i class="dot weak" />薄弱聚焦</span>
            <span><i class="dot pending" />待学习</span>
          </div>
        </div>

        <div class="stat-chips">
          <div class="stat-chip">
            <span class="stat-num">{{ completedNodes }}/{{ currentPath.total_nodes }}</span>
            <span class="stat-label">节点完成</span>
          </div>
          <div class="stat-chip">
            <span class="stat-num">{{ currentPath.estimated_hours }}</span>
            <span class="stat-label">预计学时</span>
          </div>
          <div class="stat-chip">
            <span class="stat-num">+{{ currentPath.adaptive_node_count || 0 }}</span>
            <span class="stat-label">巩固节点</span>
          </div>
          <div class="stat-chip wide">
            <span class="stat-label">薄弱聚焦</span>
            <span class="stat-text">{{ formatWeakFocusList(currentPath.weak_focus) || '暂无' }}</span>
          </div>
          <div class="stat-chip">
            <span class="stat-num">v{{ currentPath.path_version }}</span>
            <span class="stat-label">路径版本</span>
          </div>
        </div>

        <div v-if="currentPath.phases?.length" class="phase-summary">
          <div
            v-for="(ph, idx) in currentPath.phases"
            :key="ph.phase"
            class="phase-pill"
            :class="`phase-${ph.phase || idx}`"
          >
            <div class="phase-head">
              <span class="phase-idx">0{{ idx + 1 }}</span>
              <span class="phase-name">{{ ph.phase_name }}</span>
              <span class="phase-count">{{ ph.completed_count }}/{{ ph.total_count }}</span>
            </div>
            <p class="phase-desc">
              <template v-if="ph.phase === 'intro'">适配薄弱基础，扩充巩固节点</template>
              <template v-else-if="ph.phase === 'intermediate'">深入核心方法，强化实践能力</template>
              <template v-else>综合应用拓展，达成学习目标</template>
            </p>
            <el-progress
              :percentage="ph.total_count ? Math.round((ph.completed_count / ph.total_count) * 100) : 0"
              :stroke-width="8"
              :show-text="false"
              :color="idx === 0 ? '#3b82f6' : idx === 1 ? '#2563eb' : '#1d4ed8'"
            />
          </div>
        </div>
      </div>

      <div class="path-workspace">
        <div
          class="card graph-panel"
          :style="graphHeight ? { height: `${graphHeight}px` } : undefined"
        >
          <div class="panel-toolbar">
            <h4>路径可视化</h4>
            <el-radio-group v-model="viewMode" size="small">
              <el-radio-button value="timeline">列表视图</el-radio-button>
              <el-radio-button value="graph">拓扑关系图视图</el-radio-button>
            </el-radio-group>
          </div>
          <div class="panel-scroll">
            <PathTimeline
              v-if="viewMode === 'timeline'"
              :phases="currentPath.phases"
              :nodes="currentPath.nodes"
              :selected-id="selectedNode?.id"
              @node-click="onNodeClick"
              @resource-click="goResource"
              @generate-resources="generateNodeResources"
              @view-resources="viewNodeResources"
            />
            <PathGraph
              v-else
              :nodes="currentPath.nodes"
              :edges="currentPath.edges"
              :selected-id="selectedNode?.id"
              @node-click="onNodeClick"
            />
          </div>
        </div>

        <div ref="nodePanelRef" class="card node-panel">
          <h4>节点详情</h4>
          <template v-if="selectedNode">
              <section class="detail-block">
                <h5>基础学情信息</h5>
                <el-descriptions :column="1" border size="small">
                  <el-descriptions-item label="名称">{{ selectedNode.node_name }}</el-descriptions-item>
                  <el-descriptions-item label="阶段">{{ selectedNode.phase_name || '—' }}</el-descriptions-item>
                  <el-descriptions-item label="时长">{{ selectedNode.estimated_min }} 分钟</el-descriptions-item>
                  <el-descriptions-item label="难度">
                    <el-rate :model-value="selectedNode.difficulty" disabled :max="5" />
                  </el-descriptions-item>
                  <el-descriptions-item label="分类">
                    <el-tag v-if="selectedNode.is_weak" size="small" type="warning">适配薄弱点</el-tag>
                    <el-tag v-else-if="selectedNode.is_adaptive" size="small" type="success">自适应巩固</el-tag>
                    <el-tag v-else size="small">常规学习</el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="前置依赖">
                    {{ (selectedNode.prereq_names || []).join('、') || '无' }}
                  </el-descriptions-item>
                  <el-descriptions-item label="目标">{{ selectedNode.description || '完成本节点知识与练习' }}</el-descriptions-item>
                  <el-descriptions-item label="状态">
                    <el-tag size="small" :type="(NODE_STATUS_MAP[selectedNode.status]?.type as any)">
                      {{ NODE_STATUS_MAP[selectedNode.status]?.label }}
                    </el-tag>
                  </el-descriptions-item>
                </el-descriptions>
              </section>

              <section class="detail-block">
                <h5>个性化推送资源</h5>
                <p v-if="selectedNode.resource_items.length" class="res-progress-hint">
                  已学 {{ selectedNode.learned_resource_count ?? selectedNode.resource_items.filter((r) => r.is_learned).length }}
                  /
                  {{ selectedNode.total_resource_count ?? selectedNode.resource_items.length }}
                  个资源
                  <template v-if="(selectedNode.learned_resource_count ?? 0) > 0 && (selectedNode.learned_resource_count ?? 0) === (selectedNode.total_resource_count ?? selectedNode.resource_items.length)">
                    · 全部完成
                  </template>
                </p>
                <div v-if="selectedNode.resource_items.length" class="push-cards">
                  <div
                    v-for="r in selectedNode.resource_items"
                    :key="r.resource_id"
                    class="push-card"
                    :class="{ learned: r.is_learned }"
                    @click="goResource(r.resource_id, selectedNode!)"
                  >
                    <div class="push-card-top">
                      <el-tag size="small" type="primary" effect="plain">个性化推送·基于你的学习画像生成</el-tag>
                      <el-tag v-if="r.is_learned" size="small" type="success">已学完</el-tag>
                      <el-tag v-else size="small" type="info" effect="plain">未学习</el-tag>
                    </div>
                    <strong>{{ r.title }}</strong>
                    <span>{{ TYPE_LABEL[r.type_code] || r.type_name }}</span>
                  </div>
                </div>
                <el-empty v-else description="尚未匹配资源" :image-size="56">
                  <el-button type="primary" size="small" @click="generateNodeResources(selectedNode!)">
                    去资源中心生成
                  </el-button>
                </el-empty>
              </section>

              <section class="detail-block">
                <h5>学习效果评估</h5>
                <p class="eval-text">
                  掌握度
                  {{ selectedNode.mastery_score != null ? `${Math.round(selectedNode.mastery_score * 100)}%` : '暂无' }}
                </p>
                <p class="eval-hint">{{ masteryHint }}</p>
                <el-button type="primary" plain @click="router.push('/student/dashboard')">查看完整学习数据</el-button>
              </section>

              <section class="detail-block actions-block">
                <h5>快捷操作</h5>
                <div class="action-stack">
                  <button
                    type="button"
                    class="action-tile tile-learn"
                    :disabled="selectedNode.status === 0"
                    @click="startNode(selectedNode)"
                  >
                    <span class="action-title">{{ selectedNode.resource_items.length ? '开始学习' : '生成配套资源' }}</span>
                    <span class="action-desc">{{ selectedNode.resource_items.length ? '打开本节点学习内容' : '跳转资源中心并自动生成 6 类资源' }}</span>
                  </button>
                  <button type="button" class="action-tile tile-push" @click="generateNodeResources(selectedNode)">
                    <span class="action-title">一键生成配套资源</span>
                    <span class="action-desc">按节点主题自动生成并绑定到本节点</span>
                  </button>
                  <button
                    v-if="selectedNode.status >= 2"
                    type="button"
                    class="action-tile tile-done"
                    @click="completeNode(selectedNode)"
                  >
                    <span class="action-title">标记本节点完成</span>
                    <span class="action-desc">确认已掌握后解锁后续节点</span>
                  </button>
                  <button
                    type="button"
                    class="action-tile tile-adapt"
                    :disabled="planning"
                    @click="handleReplan"
                  >
                    <span class="action-title">根据学情调整路径</span>
                    <span class="action-desc">按薄弱点与完成度动态改路线</span>
                  </button>
                </div>
              </section>
            </template>
          <el-empty v-else description="点击左侧节点查看详情" :image-size="80" />
        </div>
      </div>
    </div>

    <div v-else class="void-path">
      <strong>还没有个性化路径</strong>
      <span>填写上方目标后，基于画像生成第一条三阶段路径。</span>
      <button type="button" class="btn primary lg" :disabled="planning" @click="handlePlan()">
        {{ planning ? '生成中…' : '全新生成路径' }}
      </button>
    </div>

    <p class="safety-note">
      本学习路径及配套资源由多智能体协同校验生成，已完成事实错误、违规内容过滤。
    </p>

    <el-dialog v-model="progressVisible" title="多智能体路径生成中" width="480px" :close-on-click-modal="false" :show-close="false">
      <el-progress :percentage="progressPercent" :stroke-width="12" striped />
      <ul class="step-list">
        <li v-for="(s, i) in PLAN_STEPS" :key="s" :class="{ active: i <= progressStep, current: i === progressStep }">
          {{ i <= progressStep ? '✓' : '…' }} {{ s }}
        </li>
      </ul>
      <el-skeleton :rows="3" animated style="margin-top: 12px" />
    </el-dialog>
    </main>
  </div>
</template>

<style scoped lang="scss">
.space {
  --ink: #122033;
  --muted: #5a6b80;
  --line: rgba(18, 32, 51, 0.1);
  --paper: #f8fbfd;
  --brand: #2563eb;
  --brand-deep: #1d4ed8;
  --warn: #b45309;
  --ok: #047857;
  --display: 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  position: relative;
  isolation: isolate;
  min-height: 100%;
  color: var(--ink);
  font-family: 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  margin: -20px -24px;
  padding: 28px 28px 48px;
  background:
    radial-gradient(ellipse 70% 45% at 6% -8%, rgba(37, 99, 235, 0.12), transparent 55%),
    radial-gradient(ellipse 50% 40% at 98% 4%, rgba(59, 130, 246, 0.08), transparent 50%),
    linear-gradient(165deg, #f4f7fc 0%, #eaf0fb 48%, #e2eaf8 100%);
}

.atmosphere {
  display: none;
}

.hero,
.stage {
  position: relative;
  z-index: 1;
  max-width: 1120px;
  margin: 0 auto;
}

.hero {
  margin-bottom: 24px;
  animation: rise 0.55s ease both;
}

.hero-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.kicker {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--brand);
}

.ghost-link {
  border: 0;
  background: transparent;
  color: var(--brand-deep);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  padding: 0;
  &:disabled { opacity: 0.5; cursor: not-allowed; }
  &:not(:disabled):hover { text-decoration: underline; }
}

.hero-main {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
}

.hero-copy h1 {
  margin: 0;
  font-family: var(--display);
  font-size: clamp(36px, 5vw, 48px);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.08;
}

.subline {
  margin: 10px 0 0;
  max-width: 520px;
  font-size: 14px;
  line-height: 1.55;
  color: var(--muted);
}

.pulse {
  display: grid;
  grid-template-columns: repeat(4, minmax(64px, 1fr));
  gap: 10px 18px;
  margin: 0;
  padding: 14px 18px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);

  div {
    text-align: right;
    &.accent dd { color: var(--brand-deep); }
  }
  dt {
    margin: 0;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: var(--muted);
  }
  dd {
    margin: 4px 0 0;
    font-family: var(--display);
    font-size: 24px;
    font-weight: 800;
    line-height: 1;
    &.warn { color: var(--warn); }
  }
}

.stage {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.block {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 22px 24px 26px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
  animation: rise 0.45s ease both;
}

.stage-head {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
  h2 {
    margin: 0;
    font-family: var(--display);
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -0.02em;
  }
  p {
    margin: 6px 0 0;
    font-size: 13px;
    color: var(--muted);
  }
}

.plan-panel {
  :deep(.el-input__wrapper),
  :deep(.el-textarea__inner),
  :deep(.el-select__wrapper) {
    border-radius: 0;
    box-shadow: 0 0 0 1px var(--line) inset !important;
  }
  :deep(.el-input__wrapper:hover),
  :deep(.el-textarea__inner:hover),
  :deep(.el-select__wrapper:hover),
  :deep(.el-input__wrapper.is-focus),
  :deep(.el-select__wrapper.is-focused) {
    box-shadow: 0 0 0 1px var(--brand) inset !important;
  }
  :deep(.el-form-item) { margin-bottom: 14px; }
  :deep(.el-form-item__label) {
    font-weight: 700;
    font-size: 12px;
    color: var(--ink);
  }
}

.profile-sync-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  padding: 10px 14px;
  margin-bottom: 16px;
  background: rgba(37, 99, 235, 0.06);
  border: 1px solid rgba(37, 99, 235, 0.22);
  flex-wrap: wrap;

  .sync-check {
    flex-shrink: 0;
    font-size: 18px;
    color: var(--brand);
  }

  .sync-text {
    margin: 0;
    flex: 1;
    min-width: 200px;
    font-size: 12px;
    color: var(--brand-deep);
    line-height: 1.5;
    word-break: break-all;
  }

  .link {
    margin-left: 8px;
    color: var(--brand);
    font-weight: 700;
    cursor: pointer;
    &:hover { text-decoration: underline; }
  }

  .ignore-check {
    flex-shrink: 0;
    :deep(.el-checkbox__label) { font-size: 12px; color: var(--muted); }
  }

  &.ignored {
    background: rgba(180, 83, 9, 0.06);
    border-color: rgba(180, 83, 9, 0.28);
    .sync-check { color: var(--warn); }
    .sync-text { color: #92400e; }
  }
}

.plan-form { width: 100%; }

.form-row-main {
  display: flex;
  align-items: flex-end;
  gap: 14px;

  .item-goal {
    flex: 1.5;
    min-width: 0;
    margin-bottom: 0;
  }
  .item-domain {
    flex: 1;
    min-width: 0;
    max-width: 40%;
    margin-bottom: 0;
  }
}

@media (max-width: 768px) {
  .form-row-main {
    flex-direction: column;
    align-items: stretch;
    gap: 0;
    .item-goal,
    .item-domain {
      max-width: none;
      margin-bottom: 14px;
    }
  }
  .pulse { grid-template-columns: repeat(2, 1fr); width: 100%; }
  .pulse div { text-align: left; }
}

.advanced-wrap {
  margin: 16px 0 8px;
  text-align: center;
}

.advanced-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid rgba(37, 99, 235, 0.35);
  background: rgba(37, 99, 235, 0.06);
  color: var(--brand-deep);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.2s;
  &:hover { background: rgba(37, 99, 235, 0.12); }
}

.advanced-body {
  margin-top: 14px;
  padding: 16px;
  text-align: left;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.45);
}

.plan-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid var(--line);
}

.plan-tip {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
  text-align: center;
}

.plan-btns {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.path-empty-cta {
  text-align: center;
  font-size: 13px;
  color: var(--muted);
  p { margin: 0 0 4px; }
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid transparent;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.15s, background 0.2s;
  &:disabled { opacity: 0.5; cursor: not-allowed; }
  &:not(:disabled):hover { transform: translateY(-1px); }
  &.primary {
    background: var(--brand);
    color: #fff;
    &:hover { background: var(--brand-deep); }
  }
  &.ghost {
    background: transparent;
    border-color: rgba(37, 99, 235, 0.35);
    color: var(--brand-deep);
    &:hover { background: rgba(37, 99, 235, 0.08); }
  }
  &.lg { padding: 12px 20px; font-size: 14px; min-width: 160px; }
}

.void-path {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 220px;
  padding: 32px 20px;
  background: var(--paper);
  border: 1px solid var(--line);
  text-align: center;
  strong {
    font-size: 16px;
    font-weight: 800;
    color: var(--ink);
  }
  span {
    font-size: 13px;
    color: var(--muted);
    margin-bottom: 8px;
  }
}

@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: none; }
}

.path-header {
  padding: 22px 24px;
  margin-bottom: 0;
  background: var(--paper);
  border: 1px solid var(--line);

  .header-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 18px;
  }
  .header-main { min-width: 0; flex: 1; }
  .title-row {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    h3 {
      margin: 0;
      font-size: 18px;
      font-weight: 700;
      color: #303133;
      line-height: 1.35;
    }
  }
  .goal-line {
    margin: 8px 0 0;
    font-size: 13px;
    color: #909399;
    line-height: 1.5;
  }
  .path-switcher { flex-shrink: 0; }
  .history-select { width: 220px; }
  .history-prefix {
    color: #909399;
    font-size: 12px;
    padding-right: 2px;
  }
}

.progress-block {
  margin-bottom: 16px;
  padding: 14px 16px;
  background: rgba(37, 99, 235, 0.05);
  border: 1px solid rgba(37, 99, 235, 0.18);
}

.progress-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  .progress-label {
    font-size: 13px;
    font-weight: 600;
    color: #303133;
  }
  .progress-pct {
    font-size: 16px;
    font-weight: 800;
    color: var(--brand);
  }
}

.segment-progress {
  display: flex;
  gap: 4px;
  height: 12px;

  .seg {
    flex: 1;
    border-radius: 4px;
    background: #DCDFE6;
    transition: transform 0.15s ease;
    cursor: default;
    &:hover { transform: scaleY(1.15); }
    &.done { background: #2563eb; }
    &.weak { background: #f59e0b; }
    &.pending { background: #cbd5e1; }
  }
}

.seg-legend {
  display: flex;
  gap: 14px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--muted);
  span { display: inline-flex; align-items: center; gap: 5px; }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
    &.done { background: #2563eb; }
    &.weak { background: #f59e0b; }
    &.pending { background: #cbd5e1; }
  }
}

.stat-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}

.stat-chip {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 88px;
  padding: 10px 14px;
  background: #F8FAFC;
  border: 1px solid #EBEEF5;
  border-radius: 8px;

  &.wide {
    flex: 1 1 180px;
    min-width: 160px;
  }

  .stat-num {
    font-size: 16px;
    font-weight: 700;
    color: #303133;
    line-height: 1.2;
  }
  .stat-label {
    font-size: 11px;
    color: #909399;
  }
  .stat-text {
    font-size: 12px;
    color: #606266;
    line-height: 1.4;
    word-break: break-all;
  }
}

.phase-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;

  .phase-pill {
    padding: 14px;
    background: #fff;
    border: 1px solid #EBEEF5;
    border-radius: 10px;
    transition: box-shadow 0.2s, border-color 0.2s;

    &:hover {
      border-color: #A0CFFF;
      box-shadow: 0 4px 12px rgba(64, 158, 255, 0.1);
    }

    &.phase-intro { border-top: 3px solid #60a5fa; }
    &.phase-intermediate { border-top: 3px solid #2563eb; }
    &.phase-advanced,
    &.phase-improve,
    &.phase-elevation { border-top: 3px solid #1e3a8a; }
  }

  .phase-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }
  .phase-idx {
    font-size: 11px;
    font-weight: 700;
    color: #909399;
    letter-spacing: 0.02em;
  }
  .phase-name {
    flex: 1;
    font-size: 14px;
    font-weight: 700;
    color: #303133;
  }
  .phase-count {
    font-size: 12px;
    color: #409EFF;
    font-weight: 600;
  }
  .phase-desc {
    margin: 0 0 10px;
    font-size: 12px;
    color: #909399;
    line-height: 1.45;
  }
}

.path-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(280px, 1fr);
  gap: 16px;
  align-items: start;
  margin-bottom: 0;
}

.graph-panel,
.node-panel,
.path-header.card {
  border-radius: 0 !important;
  box-shadow: none !important;
  background: var(--paper) !important;
  border: 1px solid var(--line) !important;
}

.graph-panel {
  display: flex;
  flex-direction: column;
  min-height: 360px;
  padding: 16px 18px;
  margin-bottom: 0;
  overflow: hidden;
}

.node-panel {
  padding: 16px 18px;
  margin-bottom: 0;
  height: auto;
  overflow: visible;

  h4 {
    margin: 0 0 12px;
  }
  h5 {
    margin: 0 0 10px;
    font-size: 14px;
    color: #303133;
  }
}

.panel-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  margin-bottom: 12px;
  h4 { margin: 0; }
}

.panel-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 4px;
  scrollbar-gutter: stable;

  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-thumb {
    background: #c0c4cc;
    border-radius: 999px;
  }
}

.detail-block {
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid #ebeef5;
  &:last-child { border-bottom: 0; margin-bottom: 0; }
}

.push-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.res-progress-hint {
  margin: 0 0 10px;
  font-size: 12px;
  color: $text-secondary;
}

.push-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  cursor: pointer;
  transition: box-shadow 0.2s, border-color 0.2s, background 0.2s;

  &:hover { box-shadow: 0 6px 16px rgba(64, 158, 255, 0.12); }
  &.learned {
    border-color: #b3e19d;
    background: linear-gradient(180deg, #f0f9eb, #fff);
  }
  .push-card-top {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
  }
  strong { font-size: 13px; }
  span { font-size: 12px; color: $text-secondary; }
}

.eval-text { margin: 0 0 6px; font-size: 14px; }
.eval-hint { margin: 0 0 10px; font-size: 12px; color: $text-secondary; line-height: 1.5; }

.actions-block {
  border-bottom: 0 !important;
  padding-bottom: 0 !important;
}

.action-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.action-tile {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  width: 100%;
  min-height: 64px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid transparent;
  text-align: left;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease;

  &:hover:not(:disabled) {
    transform: translateY(-1px);
    filter: brightness(1.03);
  }

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .action-title {
    font-size: 14px;
    font-weight: 650;
    line-height: 1.3;
  }

  .action-desc {
    font-size: 12px;
    line-height: 1.4;
    opacity: 0.88;
  }

  &.tile-learn {
    background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 50%, #e0f2fe 100%);
    border-color: #bfdbfe;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.08);
    .action-title { color: #1d4ed8; }
    .action-desc { color: #3b82f6; }
  }

  &.tile-push {
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 55%, #eef2ff 100%);
    border-color: #e2e8f0;
    box-shadow: 0 4px 12px rgba(100, 116, 139, 0.06);
    .action-title { color: #334155; }
    .action-desc { color: #64748b; }
  }

  &.tile-done {
    background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 50%, #ecfdf5 100%);
    border-color: #bbf7d0;
    box-shadow: 0 4px 12px rgba(34, 197, 94, 0.08);
    .action-title { color: #15803d; }
    .action-desc { color: #22c55e; }
  }

  &.tile-adapt {
    background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 45%, #ffedd5 100%);
    border-color: #fde68a;
    box-shadow: 0 4px 12px rgba(245, 158, 11, 0.08);
    .action-title { color: #b45309; }
    .action-desc { color: #d97706; }
  }
}

.safety-note {
  margin: 8px 0 0;
  text-align: center;
  font-size: 12px;
  color: var(--muted);
}

.step-list {
  list-style: none;
  padding: 0;
  margin: 16px 0 0;
  li {
    font-size: 13px;
    color: #c0c4cc;
    margin-bottom: 8px;
    &.active { color: #303133; }
    &.current { color: #409eff; font-weight: 600; }
  }
}

@media (max-width: 992px) {
  .path-workspace {
    grid-template-columns: 1fr;
  }

  .graph-panel {
    height: min(52vh, 480px) !important;
    min-height: 360px;
  }
}

@media (max-width: 768px) {
  .phase-summary { grid-template-columns: 1fr; }
}
</style>

<style lang="scss">
.path-history-popper {
  min-width: 320px !important;

  .el-select-dropdown__item {
    height: auto !important;
    line-height: 1.4 !important;
    padding: 10px 14px !important;
  }

  .history-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .history-item-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .history-title {
    flex: 1;
    min-width: 0;
    font-size: 13px;
    font-weight: 600;
    color: #303133;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .history-latest {
    flex-shrink: 0;
    font-size: 11px;
    color: #909399;
    background: #f4f4f5;
    border-radius: 4px;
    padding: 1px 6px;
  }

  .history-meta {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px;
    font-size: 12px;
    color: #909399;

    .dot { opacity: 0.5; }
  }

  .el-select-dropdown__item.is-selected {
    .history-title { color: #409eff; }
    .history-latest {
      color: #409eff;
      background: #ecf5ff;
    }
  }
}
</style>
