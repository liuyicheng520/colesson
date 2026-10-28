<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { tutorApi } from '@/api/tutor'
import OpenMaicBackground from '@/components/tutor/OpenMaicBackground.vue'
import type { TutorLectureData } from '@/types'

const LECTURE_GEN_KEY = 'edunexus_lecture_gen'
const STALE_JOB_MS = 5 * 60 * 1000

type GenStatus = 'generating' | 'done' | 'error'

interface GenState {
  sessionNo: string
  topic: string
  sourceText?: string
  status: GenStatus
  lectureId?: string
  error?: string
  jobStartedAt?: string
  updatedAt: string
}

const route = useRoute()
const router = useRouter()

const sessionNo = computed(() => String(route.query.session_no || ''))
const topic = computed(() => String(route.query.topic || '知识点讲解'))

const status = ref<GenStatus>('generating')
const errorMsg = ref('')
const lecture = ref<TutorLectureData | null>(null)
const activeStep = ref(0)
const progressText = ref('')
const generatingLock = ref(false)

const steps = [
  { key: 'parse', label: '解析知识点', icon: '🔍' },
  { key: 'outline', label: '生成 PPT 大纲', icon: '📋' },
  { key: 'slides', label: '生成逐页内容', icon: '📑' },
  { key: 'narration', label: '合成讲解语音', icon: '🔊' },
  { key: 'done', label: '生成完成', icon: '✅' },
]

function storageKey() {
  return `${LECTURE_GEN_KEY}_${sessionNo.value}`
}

function saveState(partial: Partial<GenState>) {
  const prev = loadState()
  const next: GenState = {
    sessionNo: sessionNo.value,
    topic: topic.value,
    status: status.value,
    updatedAt: new Date().toISOString(),
    ...prev,
    ...partial,
  }
  sessionStorage.setItem(storageKey(), JSON.stringify(next))
}

function loadState(): Partial<GenState> {
  try {
    const raw = sessionStorage.getItem(storageKey())
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function stepIndex(phase: string) {
  const map: Record<string, number> = { parse: 0, outline: 1, slides: 2, narration: 3, done: 4 }
  return map[phase] ?? activeStep.value
}

function isJobStale(state: Partial<GenState>) {
  if (!state.jobStartedAt) return false
  return Date.now() - new Date(state.jobStartedAt).getTime() > STALE_JOB_MS
}

async function runGenerate(force = false) {
  if (!sessionNo.value) {
    errorMsg.value = '缺少会话信息，请返回对话页重试'
    status.value = 'error'
    return
  }
  if (generatingLock.value && !force) return

  const cached = loadState()
  const sourceText =
    cached.sourceText || sessionStorage.getItem(`${storageKey()}_source`) || undefined

  generatingLock.value = true
  status.value = 'generating'
  errorMsg.value = ''
  progressText.value = '正在启动生成任务…'
  saveState({
    status: 'generating',
    topic: topic.value,
    sourceText,
    jobStartedAt: new Date().toISOString(),
    error: undefined,
  })

  try {
    await tutorApi.streamLectureGenerate(
      sessionNo.value,
      topic.value,
      sourceText,
      {
        onProgress: (p) => {
          progressText.value = p.message || progressText.value
          if (p.phase) activeStep.value = stepIndex(p.phase)
        },
        onDone: (data) => {
          if (!data.lecture?.lecture_id) throw new Error('生成结果无效')
          lecture.value = data.lecture
          status.value = 'done'
          activeStep.value = 4
          progressText.value = '讲解已生成完成'
          saveState({
            status: 'done',
            lectureId: data.lecture.lecture_id,
            error: undefined,
          })
          router.replace({
            query: {
              ...route.query,
              lecture_id: data.lecture.lecture_id,
            },
          })
        },
        onError: (msg) => {
          throw new Error(msg)
        },
      },
    )
    if (status.value === 'generating') {
      throw new Error('生成流意外结束，请重试')
    }
  } catch (e) {
    status.value = 'error'
    errorMsg.value = (e as Error).message || '讲解生成失败'
    saveState({ status: 'error', error: errorMsg.value })
    ElMessage.error(errorMsg.value)
  } finally {
    generatingLock.value = false
  }
}

function enterLecture() {
  const id = lecture.value?.lecture_id || (route.query.lecture_id as string)
  if (!id) return
  router.push({
    path: `/student/tutor/lecture/${id}`,
    query: { session_no: sessionNo.value },
  })
}

function retryGenerate() {
  runGenerate(true)
}

function backToChat() {
  router.push({ path: '/student/tutor', query: { session_no: sessionNo.value } })
}

onBeforeRouteLeave(async (to) => {
  if (status.value !== 'generating') return true
  if (to.path === '/student/tutor/lecture/generate') return true
  try {
    await ElMessageBox.confirm(
      '讲解仍在生成中，离开页面不会中断后台任务，但可能无法看到实时进度。确定离开？',
      '生成进行中',
      { confirmButtonText: '离开', cancelButtonText: '继续等待', type: 'warning' },
    )
    return true
  } catch {
    return false
  }
})

onMounted(async () => {
  if (!sessionNo.value) {
    status.value = 'error'
    errorMsg.value = '缺少会话参数'
    return
  }

  const cached = loadState()
  const queryLectureId = route.query.lecture_id as string | undefined

  if ((cached.status === 'done' && cached.lectureId) || queryLectureId) {
    const lid = cached.lectureId || queryLectureId
    status.value = 'done'
    activeStep.value = 4
    try {
      lecture.value = await tutorApi.getLecture(sessionNo.value, lid!)
      saveState({ status: 'done', lectureId: lid })
      return
    } catch {
      if (cached.status === 'done') {
        status.value = 'error'
        errorMsg.value = '讲解数据已过期，请重新生成'
        return
      }
    }
  }

  if (cached.status === 'error' && cached.error && !isJobStale(cached)) {
    errorMsg.value = cached.error
    status.value = 'error'
    return
  }

  if (cached.status === 'generating' && !isJobStale(cached)) {
    progressText.value = '检测到进行中的生成任务，正在恢复…'
  }

  await runGenerate()
})

onBeforeUnmount(() => {
  generatingLock.value = false
})
</script>

<template>
  <OpenMaicBackground class="gen-page">
    <div class="gen-card">
      <header class="gen-header">
        <h1>视频讲解生成</h1>
        <p class="topic">{{ topic }}</p>
      </header>

      <div v-if="status === 'generating'" class="loader-wrap">
        <div class="pulse-ring" />
        <div class="loader-icon">🎬</div>
      </div>

      <div class="steps">
        <div
          v-for="(step, i) in steps"
          :key="step.key"
          class="step-item"
          :class="{ active: i === activeStep, done: i < activeStep || status === 'done' }"
        >
          <span class="step-icon">{{ step.icon }}</span>
          <span class="step-label">{{ step.label }}</span>
          <span v-if="i < steps.length - 1" class="step-line" />
        </div>
      </div>

      <p v-if="status === 'generating'" class="hint">
        {{ progressText || '正在为您生成沉浸式讲解，请稍候…' }}
      </p>

      <div v-if="status === 'done'" class="done-panel">
        <p class="done-title">讲解已就绪</p>
        <p class="done-sub">共 {{ lecture?.slides?.length || 0 }} 页内容，点击开始进入讲解</p>
        <div class="actions">
          <el-button type="primary" size="large" @click="enterLecture">进入讲解</el-button>
          <el-button size="large" @click="backToChat">返回对话</el-button>
        </div>
      </div>

      <div v-if="status === 'error'" class="error-panel">
        <p class="error-title">生成失败</p>
        <p class="error-msg">{{ errorMsg || '未知错误' }}</p>
        <div class="actions">
          <el-button type="primary" @click="retryGenerate">重新生成</el-button>
          <el-button @click="backToChat">返回对话</el-button>
        </div>
      </div>

      <footer v-if="status === 'generating'" class="gen-footer">
        生成过程与当前会话绑定；刷新页面将继续或恢复进度
      </footer>
    </div>
  </OpenMaicBackground>
</template>

<style scoped lang="scss">
.gen-page {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  width: 100%;
}

.gen-card {
  width: 100%;
  max-width: 680px;
  padding: 40px 36px 32px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(148, 163, 184, 0.2);
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.08);
  text-align: center;
}

.gen-header {
  margin-bottom: 28px;
  h1 { margin: 0 0 8px; font-size: 22px; color: #0f172a; }
  .topic { margin: 0; font-size: 14px; color: #64748b; }
}

.loader-wrap {
  position: relative;
  width: 88px;
  height: 88px;
  margin: 0 auto 24px;
  .loader-icon { font-size: 36px; line-height: 88px; position: relative; z-index: 1; }
  .pulse-ring {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 3px solid #3b82f6;
    animation: pulse 1.6s ease-out infinite;
  }
}

@keyframes pulse {
  0% { transform: scale(0.85); opacity: 1; }
  100% { transform: scale(1.25); opacity: 0; }
}

.steps {
  display: flex;
  justify-content: space-between;
  gap: 4px;
  margin-bottom: 24px;
}

.step-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  opacity: 0.35;
  position: relative;
  transition: opacity 0.3s;

  &.active, &.done { opacity: 1; }

  .step-icon {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: #e2e8f0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    transition: all 0.3s;
  }

  &.active .step-icon {
    background: #2563eb;
    box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.25);
    animation: stepPulse 1.4s infinite;
  }

  &.done .step-icon { background: #22c55e; }

  .step-label { font-size: 10px; color: #64748b; font-weight: 500; line-height: 1.2; }
  &.active .step-label { color: #2563eb; font-weight: 600; }

  .step-line {
    position: absolute;
    top: 20px;
    left: calc(50% + 24px);
    width: calc(100% - 48px);
    height: 2px;
    background: #e2e8f0;
    z-index: -1;
  }
  &.done .step-line { background: #86efac; }
}

@keyframes stepPulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.06); }
}

.hint { font-size: 13px; color: #64748b; margin: 0 0 8px; min-height: 20px; }

.done-panel, .error-panel {
  padding: 16px 0 8px;
  .done-title, .error-title { font-size: 18px; font-weight: 600; margin: 0 0 8px; }
  .done-sub { font-size: 14px; color: #64748b; margin: 0 0 20px; }
  .error-msg { font-size: 14px; color: #dc2626; margin: 0 0 20px; }
}

.actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

.gen-footer {
  margin-top: 20px;
  font-size: 12px;
  color: #94a3b8;
}
</style>
