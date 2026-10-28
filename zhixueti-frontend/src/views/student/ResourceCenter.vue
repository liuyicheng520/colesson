<script setup lang="ts">
defineOptions({ name: 'ResourceCenter' })

const aiMockMode = ref(false)

import { onMounted, onUnmounted, onActivated, onBeforeUnmount, ref, reactive, computed, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document, Share, Reading, VideoCamera, Monitor, QuestionFilled, RefreshRight, ArrowDown, ArrowUp, CircleCheck } from '@element-plus/icons-vue'
import { resourceApi } from '@/api/resource'
import { systemApi } from '@/api/system'
import { agentApi } from '@/api/agent'
import { pathApi } from '@/api/path'
import { useResourceCenterStore } from '@/stores/resourceCenter'
import { useProfileStore } from '@/stores/profile'
import { codeTypeLabel, TYPE_LABELS, formatResourceSummary } from '@/utils/resourceLabels'
import { buildProfileTags } from '@/utils/profileTags'
import {
  consumePathResourceGenIntent,
  peekPathResourceGenIntent,
} from '@/utils/pathResourceGenIntent'
import type { ResourceItem, ResourceTypeCode, TaskData } from '@/types'
import AgentProgressPanel from '@/components/AgentProgressPanel.vue'

const route = useRoute()
const router = useRouter()
const listStore = useResourceCenterStore()
const profileStore = useProfileStore()
const loading = ref(false)
const generating = ref(false)
const resources = ref<ResourceItem[]>([])
const total = ref(0)
const taskData = ref<TaskData | null>(null)
const showRetry = ref(false)
const advancedOpen = ref(false)
let stopStream: (() => void) | null = null

const filters = reactive({ type_code: '', topic: '', page: 1, page_size: 20 })

const genForm = reactive({
  topic: '',
  goal: '',
  resource_types: ['document', 'question', 'mindmap', 'reading', 'code', 'video'] as ResourceTypeCode[],
  difficulty: 3,
  node_id: undefined as number | undefined,
  ignore_profile: false,
  supplement: '',
  use_scene: '' as string,
  content_focus: [] as string[],
  content_length: '' as string,
  special_requirements: '',
})

const SCENE_OPTIONS = ['课前预习', '课堂巩固', '期末复习', '课程实验', '竞赛备考']
const FOCUS_OPTIONS = ['理论概念', '实战演练', '项目案例', '应试习题', '前沿新技术']
const LENGTH_OPTIONS = ['精简版', '标准课堂版', '深度拓展版']
const SUPPLEMENT_TEMPLATES = [
  { label: '期末冲刺考点', value: '期末冲刺侧重高频考点与易错题，讲解尽量精炼，搭配对照练习' },
  { label: 'Python 实战案例', value: '多增加 Python 实战案例与可运行代码，少做复杂数学推导' },
  { label: '课前预习精简', value: '精简内容用于课前预习，先建立直觉再给关键术语' },
  { label: '通俗易懂讲解', value: '讲解通俗易懂，避开复杂数学推导，多用类比和生活例子' },
]

const typeIcons: Record<string, unknown> = {
  document: Document,
  question: QuestionFilled,
  mindmap: Share,
  reading: Reading,
  video: VideoCamera,
  code: Monitor,
}

const typeLabels = computed(() => ({
  ...TYPE_LABELS,
  code: codeTypeLabel(genForm.topic, genForm.goal),
}))

/** 固定 2×3 顺序，避免对象键序不稳定 */
const TYPE_ORDER: ResourceTypeCode[] = ['document', 'question', 'mindmap', 'reading', 'code', 'video']

const profileSyncLine = computed(() => {
  const p = profileStore.profile
  if (!p) return '正在同步学习画像…'
  const dims = p.dimensions?.length
    ? p.dimensions
    : (p.dimension_progress || [])
        .filter((d) => d.dimension_value || d.status === 'completed' || (d.display_score ?? 0) > 0)
        .map((d) => ({
          dimension_code: d.dimension_code,
          dimension_name: d.dimension_name,
          dimension_value: d.dimension_value || {},
          confidence: d.fusion_confidence ?? d.confidence ?? 0,
          source_type: 'fusion',
          updated_at: d.updated_at || '',
          display_score: d.display_score,
        }))
  if (!dims.length) {
    return '画像未完善：请先前往「画像构建」；未勾选忽略时将使用默认策略生成'
  }
  try {
    const tags = buildProfileTags(dims as Parameters<typeof buildProfileTags>[0])
    const raw = Number(p.completeness ?? 0)
    const pct = Math.round(raw <= 1 ? raw * 100 : raw)
    return `已同步画像 ${pct}%｜${tags.line}`
  } catch {
    return `已同步画像｜已采集 ${dims.length} 个维度，生成时将自动融合学情`
  }
})

const statusMap: Record<number, string> = { 0: '生成中', 1: '待审核', 2: '已发布', 3: '已拒绝' }

const publishedCount = computed(() => resources.value.filter((r) => r.status === 2).length)
const typeCount = computed(() => new Set(resources.value.map((r) => r.type_code)).size)
const selectedTypeCount = computed(() => genForm.resource_types.length)

function applyRouteQuery() {
  const topic = route.query.topic as string | undefined
  const goal = route.query.goal as string | undefined
  const nodeId = route.query.node_id as string | undefined
  if (topic) genForm.topic = topic
  if (goal) genForm.goal = goal
  if (nodeId) genForm.node_id = Number(nodeId) || undefined
}

/** 学习路径跳转意图优先于缓存表单，确保 node_id 一定带上 */
function applyPathGenIntent() {
  const intent = peekPathResourceGenIntent()
  if (!intent) return null
  genForm.topic = intent.topic
  if (intent.goal) genForm.goal = intent.goal
  genForm.node_id = intent.node_id
  return intent
}

/** 防止 keep-alive 下 mount+activated 或重复导航重复触发 */
let autoGenKey = ''

async function maybeAutoGenerateFromPath() {
  const intent = applyPathGenIntent()
  const wantAuto = String(route.query.auto_generate || '') === '1' || !!intent
  if (!wantAuto) return
  applyRouteQuery()
  applyPathGenIntent()
  if (!genForm.topic?.trim()) {
    ElMessage.warning('缺少学习主题，无法自动生成')
    return
  }
  if (!genForm.node_id && intent?.node_id) {
    genForm.node_id = intent.node_id
  }
  if (generating.value) return
  const key = `${genForm.node_id || ''}|${genForm.topic}`
  if (autoGenKey === key) return
  autoGenKey = key

  consumePathResourceGenIntent()
  const nextQuery = { ...route.query }
  delete nextQuery.auto_generate
  await router.replace({ path: route.path, query: nextQuery })
  await nextTick()
  ElMessage.info(`正在为「${genForm.topic}」一键生成配套资源…`)
  await handleGenerate(false)
}

/** 生成完成后兜底绑定到路径节点（后端 push 失败或 node_id 曾丢失时） */
async function bindGeneratedToNode(task: TaskData) {
  const nodeId = genForm.node_id
  if (!nodeId) return
  const out = (task.output_result || {}) as Record<string, unknown>
  const ids = Array.isArray(out.resource_ids)
    ? (out.resource_ids as number[]).filter((x) => Number.isFinite(Number(x)))
    : []
  if (!ids.length) return
  try {
    await pathApi.pushResources(nodeId, ids.map(Number))
  } catch {
    /* 绑定失败不阻断列表刷新；打开路径时后端会按主题自动补绑 */
  }
}

function applySupplementTemplate(value: string) {
  if (value) genForm.supplement = value
}

async function loadList(force = false) {
  if (!force && listStore.cached && listStore.resources.length) {
    resources.value = listStore.resources
    total.value = listStore.total
    Object.assign(filters, listStore.filters)
    return
  }
  loading.value = true
  try {
    const data = await resourceApi.list({
      type_code: filters.type_code || undefined,
      topic: filters.topic || undefined,
      page: filters.page,
      page_size: filters.page_size,
    })
    resources.value = data.items
    total.value = data.total
    // 写入会话缓存，切换页面回来可秒开
    saveState()
  } finally {
    loading.value = false
  }
}

function saveState() {
  const mainEl = document.querySelector('.student-layout .main') as HTMLElement | null
  listStore.saveListState(filters, resources.value, total.value, mainEl?.scrollTop || 0)
  listStore.saveGenForm(genForm)
}

function onTaskUpdate(task: TaskData) {
  taskData.value = task
  if (task.status === 2) {
    generating.value = false
    showRetry.value = false
    ElMessage.success('多智能体协同生成完成')
    void bindGeneratedToNode(task)
    listStore.clearCache()
    loadList(true)
    stopStream?.()
    stopStream = null
  } else if (task.status === 3) {
    generating.value = false
    const errMsg = task.error_message || '生成失败'
    listStore.setTaskError(errMsg)
    showRetry.value = /审核|安全|unsafe|CONTENT/i.test(errMsg) || !!(task.output_result as Record<string, unknown>)?.errors
    ElMessage.error(errMsg)
    stopStream?.()
    stopStream = null
  } else if (task.status === 4) {
    generating.value = false
    showRetry.value = true
    ElMessage.warning('部分资源生成成功，可重新生成失败项')
    void bindGeneratedToNode(task)
    listStore.clearCache()
    loadList(true)
    stopStream?.()
    stopStream = null
  }
}

function focusGenTopic() {
  const el = document.querySelector('.gen-block .item-topic input') as HTMLInputElement | null
  el?.focus()
  document.querySelector('.gen-block')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function handleGenerate(isRetry = false) {
  if (!genForm.topic) return ElMessage.warning('请输入主题')
  if (!genForm.resource_types.length) return ElMessage.warning('请至少选择一种资源类型')
  generating.value = true
  showRetry.value = false
  taskData.value = null
  stopStream?.()
  listStore.saveGenForm(genForm)

  try {
    const { task_no } = await resourceApi.generate({
      topic: genForm.topic,
      goal: genForm.goal || undefined,
      resource_types: genForm.resource_types,
      difficulty: genForm.difficulty,
      node_id: genForm.node_id,
      ignore_profile: genForm.ignore_profile,
      supplement: genForm.supplement.trim() || undefined,
      use_scene: genForm.use_scene || undefined,
      content_focus: genForm.content_focus.length ? [...genForm.content_focus] : undefined,
      content_length: genForm.content_length || undefined,
      special_requirements: genForm.special_requirements.trim() || undefined,
    })
    stopStream = agentApi.streamTask(
      task_no,
      onTaskUpdate,
      () => {
        // SSE 结束后继续轮询，避免长任务（讲义 1–3 分钟）流断开后进度假死
        let tries = 0
        const poll = () => {
          agentApi
            .getTask(task_no)
            .then((task) => {
              onTaskUpdate(task)
              if ([2, 3, 4, 5].includes(task.status)) return
              if (++tries >= 180) {
                generating.value = false
                ElMessage.warning('生成时间较长，请稍后在资源列表刷新查看')
                return
              }
              setTimeout(poll, 2000)
            })
            .catch(() => {
              generating.value = false
            })
        }
        poll()
      },
    )
    if (isRetry) ElMessage.info('正在重新生成，智能体将自动调整内容后再次提交审核…')
  } catch (e) {
    generating.value = false
    const msg = (e as Error).message || '启动生成失败'
    if (/审核|安全/i.test(msg)) {
      showRetry.value = true
      listStore.setTaskError(msg)
    }
  }
}

/** 快捷入口：仅生成视频讲解（与智能答疑「视频生成」对齐，入库到资源中心） */
async function handleGenerateVideoOnly() {
  if (!genForm.topic) return ElMessage.warning('请先填写学习主题')
  genForm.resource_types = ['video']
  ElMessage.info('将仅生成「AI视频讲解」资源')
  await handleGenerate(false)
}

function openDetail(id: number) {
  saveState()
  router.push({ name: 'ResourceDetail', params: { id: String(id) } })
}

onMounted(async () => {
  // 先恢复上次表单，再用路由/意图覆盖（学习路径跳转优先，必须带上 node_id）
  if (listStore.lastGenForm) {
    const savedTypes = listStore.lastGenForm.resource_types || []
    Object.assign(genForm, {
      ...listStore.lastGenForm,
      content_focus: [...(listStore.lastGenForm.content_focus || [])],
      resource_types: (savedTypes.length ? savedTypes : [...TYPE_ORDER]) as ResourceTypeCode[],
    })
  }
  applyRouteQuery()
  applyPathGenIntent()
  loadList()
  try {
    const info = await systemApi.publicInfo()
    aiMockMode.value = !!(info.features as Record<string, unknown>)?.ai_mock_mode
  } catch {
    /* ignore */
  }
  try {
    await profileStore.fetchProfile()
  } catch {
    /* 画像拉取失败时提示栏会显示未完善文案 */
  }
  await maybeAutoGenerateFromPath()
})

onActivated(async () => {
  // keep-alive 再次进入：仍要处理路径页「一键生成」带参跳转
  applyRouteQuery()
  applyPathGenIntent()
  await maybeAutoGenerateFromPath()

  if (listStore.cached && listStore.resources.length) {
    resources.value = listStore.resources
    total.value = listStore.total
    Object.assign(filters, listStore.filters)
    requestAnimationFrame(() => {
      const mainEl = document.querySelector('.student-layout .main') as HTMLElement | null
      if (mainEl && listStore.scrollTop) mainEl.scrollTop = listStore.scrollTop
    })
    return
  }
  loadList()
})

onBeforeUnmount(() => {
  saveState()
})

onUnmounted(() => stopStream?.())
</script>

<template>
  <div class="space">
    <div class="atmosphere" aria-hidden="true" />
    <el-alert
      v-if="aiMockMode"
      type="warning"
      :closable="true"
      show-icon
      title="当前未配置 AI 服务密钥：生成的资源为内置演示内容，并非真实 AI 输出"
      style="margin-bottom: 12px"
    />

    <header class="hero">
      <div class="hero-row">
        <p class="kicker">智课共生 · 个人工坊</p>
        <div class="hero-links">
          <button type="button" class="ghost-link" @click="router.push({ name: 'ResourceKnowledgeGraph' })">
            知识图谱 →
          </button>
          <button type="button" class="ghost-link" @click="router.push({ name: 'ResourceSquare' })">
            资源广场 →
          </button>
        </div>
      </div>
      <div class="hero-main">
        <div class="hero-copy">
          <h1>资源中心</h1>
          <p class="subline">多智能体协同生成讲义、习题、思维导图与视频讲解，按你的学情定制。</p>
        </div>
        <dl class="pulse">
          <div>
            <dt>全部</dt>
            <dd>{{ total }}</dd>
          </div>
          <div>
            <dt>已发布</dt>
            <dd>{{ publishedCount }}</dd>
          </div>
          <div>
            <dt>类型</dt>
            <dd>{{ typeCount }}</dd>
          </div>
          <div class="accent">
            <dt>本次选中</dt>
            <dd>{{ selectedTypeCount }}</dd>
          </div>
        </dl>
      </div>
    </header>

    <main class="stage">
      <section class="block gen-block">
        <div class="stage-head">
          <h2>生成工位</h2>
          <p>总协调 → 学情分析 → 分工智能体并行 → 校验入库</p>
        </div>

        <div class="profile-sync" :class="{ ignored: genForm.ignore_profile }">
          <el-icon class="sync-ico"><CircleCheck /></el-icon>
          <p>
            {{ genForm.ignore_profile ? '已忽略画像（本次生成不参考画像）｜' : '' }}{{ profileSyncLine }}
          </p>
          <el-checkbox v-model="genForm.ignore_profile" class="ignore-check">
            本次生成忽略画像
          </el-checkbox>
        </div>

        <div v-if="genForm.node_id" class="node-chip">
          已从学习路径跳转，资源将绑定到对应节点
        </div>

        <el-form class="gen-form" label-position="top">
          <div class="wizard-steps" aria-hidden="true">
            <span class="wiz-step is-on">1 主题</span>
            <span class="wiz-sep">→</span>
            <span class="wiz-step is-on">2 类型</span>
            <span class="wiz-sep">→</span>
            <span class="wiz-step" :class="{ 'is-on': advancedOpen }">3 高级</span>
          </div>

          <div class="form-row-main">
            <el-form-item label="学习主题" class="item-topic item-topic-full">
              <el-input v-model="genForm.topic" placeholder="如：线性回归 / 英语语法 / 微积分" clearable />
            </el-form-item>
          </div>

          <div class="types-section">
            <div class="types-head">
              <h3>多模态资源类型</h3>
              <button
                type="button"
                class="btn ghost"
                :disabled="generating"
                @click="handleGenerateVideoOnly"
              >
                仅生成视频讲解
              </button>
            </div>
            <p class="types-hint">
              默认勾选常用类型；高级参数（目标、难度、补充需求）可按需展开。
            </p>
            <el-checkbox-group v-model="genForm.resource_types" class="types-group">
              <div class="types-grid">
                <el-checkbox
                  v-for="code in TYPE_ORDER"
                  :key="code"
                  :value="code"
                  :label="code"
                  class="type-check"
                  :class="{ 'is-video': code === 'video' }"
                >
                  <span class="type-label">
                    <el-icon class="type-icon"><component :is="typeIcons[code] || Document" /></el-icon>
                    {{ typeLabels[code] || TYPE_LABELS[code] || code }}
                    <em v-if="code === 'video'">视频</em>
                  </span>
                </el-checkbox>
              </div>
            </el-checkbox-group>
          </div>

          <div class="advanced-wrap">
            <button type="button" class="advanced-btn" @click="advancedOpen = !advancedOpen">
              <el-icon>
                <ArrowUp v-if="advancedOpen" />
                <ArrowDown v-else />
              </el-icon>
              {{ advancedOpen ? '收起高级参数' : '展开高级参数（目标 / 难度 / 补充）' }}
            </button>

            <div v-show="advancedOpen" class="advanced-body">
              <el-form-item label="学习目标">
                <el-input v-model="genForm.goal" placeholder="可选，如：掌握核心公式与应用" clearable />
              </el-form-item>
              <div class="form-row-difficulty">
                <span class="diff-label">难度等级</span>
                <el-rate v-model="genForm.difficulty" :max="5" class="diff-rate" />
                <span class="diff-hint">{{ genForm.difficulty }} / 5</span>
              </div>
              <el-form-item>
                <template #label>
                  <span>本次生成补充需求</span>
                  <el-tooltip content="系统将结合学习画像与当前描述生成专属资源" placement="top">
                    <el-icon class="label-tip"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </template>
                <div class="supplement-row">
                  <el-input
                    v-model="genForm.supplement"
                    placeholder="例：期末冲刺侧重考点、多增加 Python 实战案例"
                    clearable
                  />
                  <el-select
                    placeholder="推荐模板"
                    clearable
                    class="tpl-select"
                    @change="applySupplementTemplate"
                  >
                    <el-option
                      v-for="t in SUPPLEMENT_TEMPLATES"
                      :key="t.label"
                      :label="t.label"
                      :value="t.value"
                    />
                  </el-select>
                </div>
              </el-form-item>

              <el-row :gutter="16">
                <el-col :xs="24" :sm="8">
                  <el-form-item label="使用场景">
                    <el-select v-model="genForm.use_scene" placeholder="请选择" clearable style="width: 100%">
                      <el-option v-for="s in SCENE_OPTIONS" :key="s" :label="s" :value="s" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <el-form-item label="内容篇幅">
                    <el-select v-model="genForm.content_length" placeholder="请选择" clearable style="width: 100%">
                      <el-option v-for="s in LENGTH_OPTIONS" :key="s" :label="s" :value="s" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <el-form-item label="内容侧重">
                    <el-checkbox-group v-model="genForm.content_focus" class="focus-group">
                      <el-checkbox v-for="f in FOCUS_OPTIONS" :key="f" :value="f" :label="f">
                        {{ f }}
                      </el-checkbox>
                    </el-checkbox-group>
                  </el-form-item>
                </el-col>
              </el-row>

              <el-form-item label="特殊要求">
                <el-input
                  v-model="genForm.special_requirements"
                  type="textarea"
                  :rows="3"
                  placeholder="可填写行业案例、需要规避的难点、输出格式、讲解风格等"
                />
              </el-form-item>
            </div>
          </div>

          <div class="gen-actions">
            <p class="gen-tip">结合学习画像与自定义参数，多智能体并行生成</p>
            <div class="gen-btns">
              <button type="button" class="btn primary lg" :disabled="generating" @click="handleGenerate(false)">
                {{ generating ? '生成中…' : '启动多智能体生成' }}
              </button>
              <button
                type="button"
                class="btn ghost lg"
                :disabled="generating || !genForm.topic"
                @click="handleGenerateVideoOnly"
              >
                仅生成 AI 视频
              </button>
              <button
                v-if="showRetry"
                type="button"
                class="btn warn lg"
                :disabled="generating"
                @click="handleGenerate(true)"
              >
                <el-icon><RefreshRight /></el-icon>
                重新生成
              </button>
            </div>
          </div>

          <el-alert
            v-if="showRetry && listStore.lastTaskError"
            type="warning"
            :closable="false"
            show-icon
            :title="`上次失败原因：${listStore.lastTaskError}`"
            class="retry-alert"
          />
        </el-form>

        <el-dialog
          :model-value="generating"
          title="多智能体资源生成进度"
          width="720px"
          :close-on-click-modal="false"
          :close-on-press-escape="false"
          :show-close="false"
          align-center
          class="progress-dialog"
          destroy-on-close
        >
          <p class="progress-flow-hint">
            读取画像 → 学情分析 → 多智能体并行生成 → 校验入库。课程讲义通常最久（约 1–2 分钟），请勿关闭弹窗。
          </p>
          <AgentProgressPanel
            v-if="taskData"
            :stages="taskData.stages"
            :progress="taskData.progress"
            :agent-runs="taskData.agent_runs"
            :partial-previews="taskData.partial_previews"
            :learning-diagnosis="taskData.learning_diagnosis"
          />
          <div v-else class="starting">
            <el-skeleton :rows="4" animated />
            <p>总协调智能体正在初始化任务…</p>
          </div>
        </el-dialog>
      </section>

      <section class="block list-block">
        <div class="stage-head list-head">
          <div>
            <h2>我的资源</h2>
            <p>点击条目进入详情，可预览、学习或继续生成配套内容。</p>
          </div>
          <div class="filter-bar">
            <el-select
              v-model="filters.type_code"
              placeholder="资源类型"
              clearable
              style="width: 132px"
              @change="() => { filters.page = 1; listStore.clearCache(); loadList(true) }"
            >
              <el-option v-for="(label, code) in typeLabels" :key="code" :label="label" :value="code" />
            </el-select>
            <el-input
              v-model="filters.topic"
              placeholder="搜索主题"
              clearable
              style="width: 180px"
              @keyup.enter="() => { filters.page = 1; listStore.clearCache(); loadList(true) }"
            />
            <button
              type="button"
              class="btn ghost"
              @click="() => { filters.page = 1; listStore.clearCache(); loadList(true) }"
            >
              搜索
            </button>
            <el-select
              v-model="filters.page_size"
              style="width: 118px"
              @change="() => { filters.page = 1; listStore.clearCache(); loadList(true) }"
            >
              <el-option :value="20" label="每页 20" />
              <el-option :value="40" label="每页 40" />
              <el-option :value="60" label="每页 60" />
            </el-select>
          </div>
        </div>

        <div v-loading="loading" class="resource-list">
          <button
            v-for="(r, idx) in resources"
            :key="r.id"
            type="button"
            class="res-row"
            @click="openDetail(r.id)"
          >
            <span class="idx">{{ String(idx + 1 + (filters.page - 1) * filters.page_size).padStart(2, '0') }}</span>
            <span class="ico">
              <el-icon :size="20"><component :is="typeIcons[r.type_code] || Document" /></el-icon>
            </span>
            <span class="body">
              <strong>{{ r.title }}</strong>
              <em>{{ formatResourceSummary(r.summary, r.topic).slice(0, 72) || r.topic }}</em>
            </span>
            <span class="meta">
              <i>{{ r.type_code === 'code' ? codeTypeLabel(r.topic) : r.type_name }}</i>
              <b :class="{ ok: r.status === 2 }">{{ statusMap[r.status] }}</b>
            </span>
          </button>
          <div v-if="!loading && !resources.length" class="void">
            <strong>还没有资源</strong>
            <span>填写主题、勾选类型后，点上方生成按钮即可创建第一条。</span>
            <button type="button" class="btn primary" @click="focusGenTopic">
              生成第一条
            </button>
          </div>
        </div>

        <el-pagination
          v-if="total > 0"
          v-model:current-page="filters.page"
          v-model:page-size="filters.page_size"
          :page-sizes="[20, 40, 60]"
          :total="total"
          layout="total, sizes, prev, pager, next"
          class="pager"
          @current-change="() => { listStore.clearCache(); loadList(true) }"
          @size-change="() => { filters.page = 1; listStore.clearCache(); loadList(true) }"
        />
      </section>
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
  margin-bottom: 28px;
  animation: rise 0.55s ease both;
}

.hero-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.hero-links {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
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
  &:hover { text-decoration: underline; }
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
    font-size: 26px;
    font-weight: 800;
    line-height: 1;
  }
}

.stage {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.block {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 22px 24px 26px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
  animation: rise 0.45s ease both;
}

.list-block { animation-delay: 0.06s; }

.stage-head {
  margin-bottom: 18px;
  padding-bottom: 14px;
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

.list-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.profile-sync {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  margin-bottom: 14px;
  border: 1px solid rgba(37, 99, 235, 0.22);
  background: rgba(37, 99, 235, 0.06);

  .sync-ico {
    flex-shrink: 0;
    font-size: 18px;
    color: var(--brand);
  }
  p {
    margin: 0;
    flex: 1;
    min-width: 0;
    font-size: 12px;
    color: var(--brand-deep);
    line-height: 1.5;
    word-break: break-all;
  }
  .ignore-check {
    flex-shrink: 0;
    :deep(.el-checkbox__label) { font-size: 12px; color: var(--muted); }
  }
  &.ignored {
    border-color: rgba(180, 83, 9, 0.28);
    background: rgba(180, 83, 9, 0.06);
    .sync-ico { color: var(--warn); }
    p { color: #92400e; }
  }
}

.node-chip {
  margin-bottom: 14px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--brand-deep);
  border-left: 3px solid var(--brand);
  background: rgba(37, 99, 235, 0.05);
}

.wizard-steps {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
}
.wiz-step.is-on { color: var(--brand-deep); }
.wiz-sep { opacity: 0.45; }
.item-topic-full { width: 100%; }

.gen-form {
  :deep(.el-form-item) { margin-bottom: 14px; }
  :deep(.el-form-item__label) {
    font-weight: 700;
    font-size: 12px;
    color: var(--ink);
  }
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
}

.form-row-main {
  display: flex;
  align-items: flex-end;
  gap: 14px;
  .item-topic,
  .item-goal {
    flex: 1;
    min-width: 0;
    margin-bottom: 14px;
  }
}

.form-row-difficulty {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 2px 0 18px;
  .diff-label {
    font-size: 12px;
    font-weight: 700;
    color: var(--ink);
  }
  .diff-hint {
    font-size: 12px;
    color: var(--muted);
  }
}

.types-section { margin-bottom: 8px; }

.types-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
  h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 800;
  }
}

.types-hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.5;
}

.types-group { display: block; width: 100%; }

.types-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.type-check {
  margin: 0 !important;
  width: 100%;
  height: 44px;
  padding: 0 12px !important;
  display: inline-flex !important;
  align-items: center;
  border: 1px solid var(--line) !important;
  border-radius: 0 !important;
  background: rgba(255, 255, 255, 0.55);
  transition: border-color 0.2s, background 0.2s, transform 0.2s;

  &:hover {
    border-color: rgba(37, 99, 235, 0.45) !important;
    transform: translateY(-1px);
  }

  &.is-checked,
  :deep(.is-checked) {
    /* checked state via parent */
  }

  &.is-video {
    border-color: rgba(37, 99, 235, 0.35) !important;
    background: rgba(37, 99, 235, 0.05);
  }

  :deep(.el-checkbox__input) { display: none; }
  :deep(.el-checkbox__label) {
    padding-left: 0;
    width: 100%;
    font-size: 13px;
    color: var(--ink);
  }

  .type-label {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    width: 100%;
  }
  .type-icon { font-size: 16px; color: var(--brand); }
  em {
    margin-left: auto;
    font-style: normal;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.06em;
    color: var(--brand-deep);
  }
}

:deep(.type-check.is-checked) {
  border-color: var(--brand) !important;
  background: rgba(37, 99, 235, 0.1);
  box-shadow: inset 0 -2px 0 var(--brand);
}

.label-tip {
  margin-left: 4px;
  vertical-align: middle;
  color: var(--muted);
  cursor: help;
}

.supplement-row {
  display: flex;
  gap: 10px;
  width: 100%;
  align-items: center;
  .tpl-select { width: 150px; flex-shrink: 0; }
}

.focus-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
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

.gen-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid var(--line);
}

.gen-tip {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}

.gen-btns {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
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
  transition: transform 0.15s, background 0.2s, border-color 0.2s;
  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
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
  &.warn {
    background: rgba(180, 83, 9, 0.1);
    border-color: rgba(180, 83, 9, 0.35);
    color: var(--warn);
  }
  &.lg { padding: 12px 20px; font-size: 14px; }
}

.retry-alert { margin-top: 12px; }

.progress-flow-hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--muted);
  text-align: center;
}

.starting {
  padding: 16px;
  text-align: center;
  p { margin-top: 12px; color: var(--muted); font-size: 13px; }
}

.filter-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.resource-list {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 160px;
}

.res-row {
  display: grid;
  grid-template-columns: 40px 40px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  width: 100%;
  text-align: left;
  padding: 14px 8px;
  border: 0;
  border-bottom: 1px solid var(--line);
  background: transparent;
  color: inherit;
  cursor: pointer;
  transition: background 0.2s, padding-left 0.2s;

  &:hover {
    background: rgba(37, 99, 235, 0.05);
    padding-left: 12px;
  }

  .idx {
    font-family: var(--display);
    font-size: 16px;
    font-weight: 800;
    color: rgba(37, 99, 235, 0.45);
    letter-spacing: -0.02em;
  }
  .ico {
    width: 36px;
    height: 36px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: var(--brand);
    background: rgba(37, 99, 235, 0.08);
  }
  .body {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
    strong {
      font-size: 15px;
      font-weight: 800;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    em {
      font-style: normal;
      font-size: 12px;
      color: var(--muted);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }
  .meta {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 4px;
    i {
      font-style: normal;
      font-size: 11px;
      font-weight: 700;
      color: var(--muted);
    }
    b {
      font-size: 12px;
      font-weight: 800;
      color: var(--muted);
      &.ok { color: var(--ok); }
    }
  }
}

.void {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 180px;
  color: var(--muted);
  strong {
    font-size: 15px;
    font-weight: 800;
    color: var(--ink);
  }
  span { font-size: 13px; }
}

.pager {
  margin-top: 18px;
  justify-content: flex-end;
}

@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: none; }
}

@media (max-width: 768px) {
  .space { margin: -12px -12px; padding: 18px 16px 36px; }
  .form-row-main { flex-direction: column; gap: 0; }
  .types-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .pulse { grid-template-columns: repeat(2, 1fr); width: 100%; }
  .pulse div { text-align: left; }
  .res-row {
    grid-template-columns: 32px 32px minmax(0, 1fr);
    .meta {
      grid-column: 3;
      flex-direction: row;
      justify-content: flex-start;
      gap: 10px;
    }
  }
}
</style>
