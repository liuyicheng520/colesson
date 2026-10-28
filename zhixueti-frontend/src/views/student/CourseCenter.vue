<script setup lang="ts">
defineOptions({ name: 'CourseCenter' })

import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Collection,
  Document,
  Guide,
  Monitor,
  QuestionFilled,
  Reading,
  Share,
  VideoCamera,
} from '@element-plus/icons-vue'
import { resourceApi } from '@/api/resource'
import { classroomApi, type ClassRoom } from '@/api/classroom'
import { formatResourceSummary } from '@/utils/resourceLabels'
import type { ResourceItem } from '@/types'
import EmptyState from '@/components/EmptyState.vue'
import {
  fetchPublishedLessons,
  openGongshengWorkbench,
  readGongshengProgress,
  type GongshengLesson,
} from '@/utils/gongshengProgress'

type LearnStatus = 'not_started' | 'learning' | 'completed'
type CourseKind = 'gongsheng' | 'resource'

interface CourseCard {
  key: string
  kind: CourseKind
  id: string
  title: string
  summary: string
  subject: string
  teacher: string
  timeLabel: string
  timeMs: number
  resourceCount: number
  status: LearnStatus
  percent: number
  typeCode?: string
  scope?: 'mine' | 'public'
}

const UNKNOWN_SUBJECT = '未分类'
const UNKNOWN_TEACHER = '未知教师'

const router = useRouter()
const loading = ref(false)
const progressMap = ref(readGongshengProgress())
const cards = ref<CourseCard[]>([])

const myClasses = ref<ClassRoom[]>([])
const joinVisible = ref(false)
const joining = ref(false)
const requestingCode = ref(false)
const inviteCode = ref('')
const joinContext = ref('')
watch(joinVisible, (v) => {
  if (!v) {
    inviteCode.value = ''
    joinEmail.value = ''
    emailCode.value = ''
    demoHint.value = ''
    joinContext.value = ''
    joinShaking.value = false
  }
})
const joinEmail = ref('')
const emailCode = ref('')
const demoHint = ref('')

/** 突出课程名：2026软件01班 → 课程「2026软件」/ 班级「01班」 */
function splitCourseClass(c: ClassRoom) {
  const name = (c.name || '').trim()
  const m = name.match(/^(.*?)(\d+\s*班)$/)
  if (m && m[1]) {
    return { course: m[1].trim(), classLabel: m[2].replace(/\s+/g, '') }
  }
  if (c.subject?.trim()) {
    return { course: c.subject.trim(), classLabel: name || '未命名班级' }
  }
  return { course: name || '未命名课程', classLabel: '班级' }
}

const typeIcons: Record<string, unknown> = {
  document: Document,
  question: QuestionFilled,
  mindmap: Share,
  reading: Reading,
  video: VideoCamera,
  code: Monitor,
}

function parseTimeMs(value?: string | null): number {
  if (!value) return 0
  const ms = Date.parse(value)
  return Number.isFinite(ms) ? ms : 0
}

function formatTime(value?: string | null): string {
  if (!value) return '暂无时间'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value).slice(0, 16)
  return d.toLocaleDateString('zh-CN')
}

function statusOfPercent(percent: number): LearnStatus {
  if (percent >= 100) return 'completed'
  if (percent > 0) return 'learning'
  return 'not_started'
}

function statusLabel(status: LearnStatus): string {
  if (status === 'completed') return '已完成'
  if (status === 'learning') return '学习中'
  return '未学习'
}

function statusTagType(status: LearnStatus): '' | 'success' | 'warning' | 'info' {
  if (status === 'completed') return 'success'
  if (status === 'learning') return 'warning'
  return 'info'
}

function fromGongsheng(lesson: GongshengLesson): CourseCard {
  const percent = Math.round(progressMap.value[lesson.id]?.percent || 0)
  const timeRaw = lesson.publishedAt || lesson.updatedAt || ''
  return {
    key: `gongsheng:${lesson.id}`,
    kind: 'gongsheng',
    id: lesson.id,
    title: lesson.title,
    summary: lesson.summary || '教师发布的智课，点击进入沉浸学习工作台。',
    subject: lesson.subject?.trim() || UNKNOWN_SUBJECT,
    teacher: lesson.teacher?.trim() || UNKNOWN_TEACHER,
    timeLabel: formatTime(timeRaw),
    timeMs: parseTimeMs(timeRaw),
    resourceCount: lesson.resourceCount || 0,
    status: statusOfPercent(percent),
    percent,
  }
}

function fromResource(item: ResourceItem, scope: 'mine' | 'public'): CourseCard {
  const subject = item.topic?.trim() || UNKNOWN_SUBJECT
  const teacher = item.author_name?.trim() || UNKNOWN_TEACHER
  const timeRaw = item.published_at || item.created_at
  // 资源暂无细粒度进度数据：只标记学习状态，不伪造百分比
  const status: LearnStatus = scope === 'mine' ? 'learning' : 'not_started'
  const percent = 0
  return {
    key: `resource:${scope}:${item.id}`,
    kind: 'resource',
    id: String(item.id),
    title: item.title,
    summary: formatResourceSummary(item.summary, item.topic).slice(0, 96) || item.topic || '课程资源',
    subject,
    teacher,
    timeLabel: formatTime(timeRaw),
    timeMs: parseTimeMs(timeRaw),
    resourceCount: 1,
    status,
    percent,
    typeCode: item.type_code,
    scope,
  }
}

async function loadClasses() {
  try {
    const data = await classroomApi.listMyClasses()
    myClasses.value = data.items || []
  } catch {
    myClasses.value = []
  }
}

async function requestEmailCode() {
  const code = inviteCode.value.trim()
  const email = joinEmail.value.trim()
  if (!code || !email) {
    ElMessage.warning('请填写邀请码和邮箱')
    return
  }
  requestingCode.value = true
  demoHint.value = ''
  try {
    const data = await classroomApi.requestJoinCode(code, email)
    demoHint.value = data.hint || '验证码已发送，请注意查收'
    if (data.demoCode) {
      demoHint.value = `演示验证码：${data.demoCode}`
      emailCode.value = data.demoCode
    } else {
      demoHint.value = data.hint || '验证码已发送'
    }
    ElMessage.success('验证码已生成')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '获取验证码失败')
  } finally {
    requestingCode.value = false
  }
}

function openJoinDialog() {
  joinVisible.value = true
  demoHint.value = ''
}

// 校验失败抖动：450ms 后自动移除类，避免连续触发叠加
const joinShaking = ref(false)
let joinShakeTimer: ReturnType<typeof setTimeout> | null = null
function triggerJoinShake() {
  if (joinShakeTimer) clearTimeout(joinShakeTimer)
  joinShaking.value = false
  requestAnimationFrame(() => {
    joinShaking.value = true
    joinShakeTimer = setTimeout(() => {
      joinShaking.value = false
    }, 450)
  })
}

async function joinClass() {
  const code = inviteCode.value.trim()
  const email = joinEmail.value.trim()
  const otp = emailCode.value.trim()
  if (!code || !email || !otp) {
    ElMessage.warning('请填写邀请码、邮箱与验证码')
    triggerJoinShake()
    return
  }
  joining.value = true
  try {
    const data = await classroomApi.join(code, email, otp)
    ElMessage.success('已加入班级')
    inviteCode.value = ''
    joinEmail.value = ''
    emailCode.value = ''
    demoHint.value = ''
    joinVisible.value = false
    await loadClasses()
    if (data.class?.id) {
      router.push({ name: 'StudentClassRoom', params: { classId: data.class.id } })
    }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加入失败')
    triggerJoinShake()
  } finally {
    joining.value = false
  }
}

function openClass(c: ClassRoom) {
  router.push({ name: 'StudentClassRoom', params: { classId: c.id } })
}

// 骨架屏最小展示时长：避免快速加载时 <100ms 的闪现（比无骨架更刺眼）
const SKELETON_MIN_MS = 320

async function loadAll() {
  loading.value = true
  const skeletonStart = performance.now()
  progressMap.value = readGongshengProgress()
  const next: CourseCard[] = []

  try {
    const [lessons, mineRes, publicRes] = await Promise.all([
      fetchPublishedLessons().catch((err) => {
        console.warn(err)
        return [] as GongshengLesson[]
      }),
      resourceApi.list({ page: 1, page_size: 100 }).catch(() => ({ items: [] as ResourceItem[], total: 0 })),
      resourceApi.listPublic({ page: 1, page_size: 100 }).catch(() => ({ items: [] as ResourceItem[], total: 0 })),
      loadClasses(),
    ])

    for (const lesson of lessons) {
      next.push(fromGongsheng(lesson))
    }

    const mineIds = new Set((mineRes.items || []).map((x) => x.id))
    for (const item of mineRes.items || []) {
      next.push(fromResource(item, 'mine'))
    }
    for (const item of publicRes.items || []) {
      if (mineIds.has(item.id)) continue
      next.push(fromResource(item, 'public'))
    }

    cards.value = next
  } catch (err) {
    cards.value = []
    ElMessage.error('课程中心加载失败，请稍后重试')
    console.error(err)
  } finally {
    const elapsed = performance.now() - skeletonStart
    if (elapsed < SKELETON_MIN_MS) {
      await new Promise((resolve) => setTimeout(resolve, SKELETON_MIN_MS - elapsed))
    }
    loading.value = false
  }
}

function applyFilters(list: CourseCard[]): CourseCard[] {
  return [...list].sort((a, b) => b.timeMs - a.timeMs)
}

const allList = computed(() => applyFilters(cards.value))

function openCard(card: CourseCard) {
  if (card.kind === 'gongsheng') {
    openGongshengWorkbench(card.id)
    return
  }
  router.push({
    name: 'ResourceDetail',
    params: { id: card.id },
    query: card.scope === 'public' ? { scope: 'public' } : undefined,
  })
}

function goResourceCenter() {
  router.push({ name: 'ResourceCenter' })
}

function goLearningPath() {
  router.push({ name: 'LearningPath' })
}

let hydrated = false

onMounted(() => {
  const invite = String(router.currentRoute.value.query.invite || '').trim()
  if (invite) {
    inviteCode.value = invite.toUpperCase()
    joinVisible.value = true
    const qClassId = String(router.currentRoute.value.query.classId || '').trim()
    const qProjectId = String(router.currentRoute.value.query.projectId || '').trim()
    joinContext.value = [qClassId ? '班级 ' + qClassId : '', qProjectId ? '智课 ' + qProjectId : ''].filter(Boolean).join(' · ')
  }
  void loadAll()
  hydrated = true
})

onActivated(() => {
  // keep-alive 返回时刷新（首次 onMounted 已加载，activated 跳过避免双发）
  if (hydrated) void loadAll()
})
</script>

<template>
  <div class="page-container course-center">
    <div v-if="loading" class="course-skeleton" role="status" aria-live="polite" aria-label="课程中心加载中">
      <span class="visually-hidden">加载课程中心…</span>
      <div class="skeleton-head skeleton-pulse" />
      <div class="skeleton-grid">
        <div v-for="n in 4" :key="n" class="skeleton-card skeleton-pulse">
          <div class="skeleton-line w60" />
          <div class="skeleton-line w90" />
          <div class="skeleton-line w40" />
        </div>
      </div>
    </div>
    <template v-else>
    <div class="page-head">
      <div class="head-copy">
        <h2>课程中心</h2>
        <p class="subtitle">加入多个班级，点进班级学习智课、交作业、看资料与聊天</p>
      </div>
      <div class="head-actions">
        <el-button class="join-btn" type="primary" plain @click="openJoinDialog">加入</el-button>
        <el-button :icon="Collection" @click="goResourceCenter">资源中心</el-button>
        <el-button type="primary" :icon="Guide" @click="goLearningPath">学习路径</el-button>
      </div>
    </div>

    <el-dialog
      v-model="joinVisible"
      title="加入班级"
      width="440px"
      append-to-body
      align-center
      class="join-dialog"
    >
      <p class="dialog-tip">向任课老师索取邀请码，完成邮箱验证后即可进入班级。</p>
      <p v-if="joinContext" class="dialog-tip" style="color: var(--el-color-primary)">来自老师分享：{{ joinContext }}</p>
      <div class="join-panel" :class="{ 'form-shake': joinShaking }">
      <!-- close 时重置由下方 watch joinVisible 处理 -->
        <el-input v-model="inviteCode" maxlength="12" placeholder="班级邀请码（6 位）" clearable />
        <el-input v-model="joinEmail" type="email" placeholder="接收验证码的邮箱" clearable />
        <div class="join-row">
          <el-input v-model="emailCode" maxlength="8" placeholder="邮箱验证码" clearable />
          <el-button :loading="requestingCode" @click="requestEmailCode">获取验证码</el-button>
        </div>
        <p v-if="demoHint" class="demo-hint">{{ demoHint }}</p>
      </div>
      <template #footer>
        <el-button @click="joinVisible = false">取消</el-button>
        <el-button type="primary" :loading="joining" @click="joinClass">验证并加入</el-button>
      </template>
    </el-dialog>

    <section class="zone">
      <div class="zone-head">
        <h3>我的班级</h3>
        <span>{{ myClasses.length }} 个</span>
      </div>
      <div v-if="myClasses.length" class="resource-grid">
        <div
          v-for="c in myClasses"
          :key="c.id"
          class="resource-card class-card"
          @click="openClass(c)"
        >
          <div class="card-icon brand">
            <el-icon :size="28"><Reading /></el-icon>
          </div>
          <h4>{{ splitCourseClass(c).course }}</h4>
          <p class="class-sub">{{ splitCourseClass(c).classLabel }} · {{ c.subject || '课程' }}</p>
          <p>{{ c.description || '进入班级：学习、作业、资料、成员与聊天' }}</p>
          <div class="card-meta">
            <el-tag size="small" type="info">教师 {{ c.teacherUsername || '-' }}</el-tag>
            <span class="meta-time">{{ (c.memberUsernames || []).length }} 名同学</span>
          </div>
          <div class="card-foot">
            <span>班级空间</span>
            <strong>进入班级</strong>
          </div>
        </div>
      </div>
      <EmptyState v-else description="还没有班级。点击右上角「加入」，用邀请码进入。" />
    </section>

    <section class="zone">
      <div class="zone-head">
        <h3>全部课程</h3>
        <span>{{ allList.length }} 门</span>
      </div>
      <div v-if="allList.length" class="resource-grid">
        <div
          v-for="card in allList"
          :key="card.key"
          class="resource-card"
          @click="openCard(card)"
        >
          <div class="card-icon" :class="{ brand: card.kind === 'gongsheng' }">
            <el-icon :size="28">
              <component :is="card.kind === 'gongsheng' ? Reading : (typeIcons[card.typeCode || ''] || Document)" />
            </el-icon>
          </div>
          <h4>{{ card.title }}</h4>
          <p>{{ card.summary }}</p>
          <div class="card-meta">
            <el-tag size="small">{{ card.subject }}</el-tag>
            <el-tag size="small" type="info">{{ card.teacher }}</el-tag>
            <el-tag size="small" :type="statusTagType(card.status)">{{ statusLabel(card.status) }}</el-tag>
            <span class="meta-time">{{ card.timeLabel }}</span>
          </div>
          <div class="card-foot">
            <span>{{ card.kind === 'gongsheng' ? `课时/资源 ${card.resourceCount || '—'}` : '课程资源' }}</span>
            <strong>进入学习</strong>
          </div>
          <div v-if="card.kind === 'gongsheng'" class="mini-progress">
            <span :style="{ width: `${card.percent}%` }" />
          </div>
        </div>
      </div>
      <EmptyState v-else description="暂无课程，请等待教师发布或前往资源中心生成" />
    </section>
    </template>
  </div>
</template>

<style scoped lang="scss">
.course-center {
  .boot-loading {
    margin-bottom: 12px;
    font-size: 13px;
    font-weight: 600;
    color: $text-secondary;
  }

  .page-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 18px;
    flex-wrap: wrap;
  }

  h2 {
    margin: 0;
    font-size: 22px;
    font-weight: 700;
    color: $text-primary;
  }

  .subtitle {
    margin: 8px 0 0;
    color: $text-secondary;
    line-height: 1.6;
  }

  .head-actions {
    display: flex;
    gap: 10px;
  }
}

.join-btn {
  min-width: 72px;
  font-weight: 700;
}

.join-panel {
  display: grid;
  gap: 10px;
}

.join-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.dialog-tip {
  margin: 0 0 12px;
  color: $text-secondary;
  font-size: 13px;
  line-height: 1.6;
}

.demo-hint {
  margin: 0;
  color: #b45309;
  font-size: 13px;
}

/* 首屏骨架：与最终卡片同宽高，数据到达后由 v-else 交叉替换 */
.course-skeleton {
  padding: 20px 24px;
  max-width: 1440px;
  margin: 0 auto;
}
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
.skeleton-head {
  height: 28px;
  width: 180px;
  border-radius: 8px;
  background: var(--el-fill-color-light, #eef2f7);
  margin-bottom: 20px;
}
.skeleton-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}
.skeleton-card {
  border-radius: 16px;
  border: 1px solid var(--el-border-color-lighter, #e8eef5);
  background: #fff;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 132px;
}
.skeleton-line {
  height: 12px;
  border-radius: 6px;
  background: var(--el-fill-color-light, #eef2f7);
}
.skeleton-line.w60 { width: 60%; }
.skeleton-line.w90 { width: 90%; }
.skeleton-line.w40 { width: 40%; }

.class-card {
  border-color: rgba(37, 99, 235, 0.28);

  h4 {
    font-size: 18px;
    font-weight: 800;
  }

  .class-sub {
    min-height: 0;
    margin: -2px 0 6px;
    color: $primary;
    font-size: 13px;
    font-weight: 700;
  }
}

.zone {
  margin-bottom: 28px;
}

.zone-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;

  h3 {
    margin: 0;
    font-size: 17px;
    font-weight: 700;
    color: $text-primary;
  }

  span {
    color: $text-secondary;
    font-size: 13px;
  }
}

.resource-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
  min-height: 80px;
}

.resource-card {
  background: $bg-card;
  border: 1px solid $border-color;
  border-radius: $radius-lg;
  padding: 16px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
  box-shadow: $shadow-card;

  &:hover {
    border-color: rgba(37, 99, 235, 0.35);
    box-shadow: 0 8px 24px rgba(37, 99, 235, 0.08);
    transform: translateY(-2px);
  }

  h4 {
    margin: 12px 0 8px;
    font-size: 16px;
    color: $text-primary;
    line-height: 1.4;
  }

  p {
    margin: 0;
    min-height: 44px;
    color: $text-secondary;
    font-size: 13px;
    line-height: 1.6;
  }
}

.card-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: #eff6ff;
  color: $primary;

  &.brand {
    background: linear-gradient(135deg, #dbeafe, #eff6ff);
  }
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-top: 12px;

  .meta-time {
    color: $text-secondary;
    font-size: 12px;
  }
}

.card-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid $border-color;
  color: $text-secondary;
  font-size: 12px;

  strong {
    color: $primary;
    font-weight: 600;
  }
}

.mini-progress {
  margin-top: 10px;
  height: 6px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;

  > span {
    display: block;
    height: 100%;
    background: #2563eb;
  }
}
</style>
