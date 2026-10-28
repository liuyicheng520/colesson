<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import MermaidViewer from '@/components/MermaidViewer.vue'
import MarkdownViewer from '@/components/MarkdownViewer.vue'
import OpenMaicBackground from '@/components/tutor/OpenMaicBackground.vue'
import TutorLectureRoundtable, { type LectureChatMessage } from '@/components/tutor/TutorLectureRoundtable.vue'
import LectureCompletePage from '@/components/tutor/LectureCompletePage.vue'
import LectureSlidePreview from '@/components/tutor/LectureSlidePreview.vue'
import LectureNotesPanel from '@/components/tutor/LectureNotesPanel.vue'
import { tutorApi } from '@/api/tutor'
import { resourceApi } from '@/api/resource'
import { pathApi } from '@/api/path'
import { exportLecturePptxClient } from '@/utils/exportLecturePptx'
import { useLectureSpeech } from '@/composables/useLectureSpeech'
import { stripCitationBlock } from '@/utils/citation'
import { summarizeLectureSlides } from '@/utils/lectureSummary'
import type { TutorLectureData, TutorLectureSlide, TutorLectureSummary } from '@/types'

const route = useRoute()
const router = useRouter()

const sessionNo = computed(() => String(route.query.session_no || ''))
const lectureId = computed(() => String(route.params.lectureId || ''))
const resourceId = computed(() => {
  const id = Number(route.query.resource_id)
  return Number.isFinite(id) && id > 0 ? id : null
})
const nodeId = computed(() => {
  const id = Number(route.query.node_id)
  return Number.isFinite(id) && id > 0 ? id : null
})
const pathId = computed(() => {
  const id = Number(route.query.path_id)
  return Number.isFinite(id) && id > 0 ? id : null
})
const fromResource = computed(() => route.query.from === 'resource')
const fromHost = computed(() => route.query.from === 'host')
const hostProjectId = computed(() => String(route.query.projectId || ''))
const isPublicScope = computed(
  () => route.query.scope === 'public' || route.query.from === 'square' || fromHost.value,
)

const loading = ref(true)
const loadError = ref('')
const lecture = ref<TutorLectureData | null>(null)
const slideIndex = ref(0)
const autoPlay = ref(false)
const muted = ref(false)
const speed = ref(1)
const speedOptions = [1, 1.25, 1.5, 1.75, 2]
const slideAnim = ref(false)
const showQuiz = ref(false)
const quizAnswers = ref<string[]>([])
const quizResult = ref<{ correct: boolean; analysis: string } | null>(null)
const summaryLoaded = ref(false)
const summary = ref<TutorLectureSummary | null>(null)
let progressMarked = false
const previewOpen = ref(false)
const isPresenting = ref(false)
const notesPanelOpen = ref(false)
const quizResults = ref<{ correct: boolean }[]>([])
const stageRef = ref<HTMLElement | null>(null)
const slideTranscripts = ref<Record<number, string>>({})

const askHistory = ref<Array<{ role: 'user' | 'assistant'; content: string }>>([])
const askLoading = ref(false)
const qaPausedAuto = ref(false)

const chatLog = ref<LectureChatMessage[]>([])
let chatSeq = 0
let liveTeacherId: string | null = null
let slideSentences: string[] = []

function appendChatMessage(role: 'teacher' | 'user', content: string, live = false) {
  const id = `chat-${++chatSeq}`
  chatLog.value.push({ id, role, content, live: live || undefined })
  return id
}

function finalizeLiveTeacher(finalContent?: string) {
  if (!liveTeacherId) return
  const idx = chatLog.value.findIndex((m) => m.id === liveTeacherId)
  if (idx === -1) {
    liveTeacherId = null
    slideSentences = []
    return
  }
  const item = chatLog.value[idx]
  const content = stripCitationBlock((finalContent ?? item.content).trim())
  if (!content) {
    chatLog.value.splice(idx, 1)
  } else {
    item.content = content
    item.live = false
    if (slideIndex.value < slides.value.length) {
      slideTranscripts.value[slideIndex.value] = content
    }
  }
  liveTeacherId = null
  slideSentences = []
}

function beginLiveTeacherSpeech() {
  finalizeLiveTeacher()
  liveTeacherId = null
  slideSentences = []
}

function updateLiveTeacherText(text: string) {
  const cleaned = text.trim()
  if (!cleaned) return
  if (!liveTeacherId) {
    liveTeacherId = appendChatMessage('teacher', cleaned, true)
    slideSentences = [cleaned]
    return
  }
  const item = chatLog.value.find((m) => m.id === liveTeacherId)
  if (!item) return
  if (!slideSentences.includes(cleaned)) slideSentences.push(cleaned)
  item.content = slideSentences.join('')
}

function getSlideNarrationText() {
  if (!current.value) return ''
  if (isQuizSlide.value) {
    return current.value.narration || current.value.question || '请完成随堂测验'
  }
  return current.value.narration || current.value.title || ''
}

const speech = useLectureSpeech()
const {
  speaking,
  bubbleText,
  bubbleRole,
  activeBulletIndex,
  speakSlide,
  speakReply,
  stop: stopSpeech,
} = speech

const slides = computed(() => lecture.value?.slides || [])
const completionIndex = computed(() => slides.value.length)
const totalPages = computed(() => slides.value.length + 1)
const isOnCompletePage = computed(() => slideIndex.value === completionIndex.value)
const current = computed(() => (isOnCompletePage.value ? null : slides.value[slideIndex.value]))
const total = computed(() => slides.value.length)
const isQuizSlide = computed(() => current.value?.type === 'quiz')
const spotlightActive = computed(() => speaking.value && !isQuizSlide.value && !isOnCompletePage.value)

const completeStats = computed(() =>
  summarizeLectureSlides(slides.value, quizResults.value),
)

function lectureFromResourceDetail(detail: Record<string, unknown>, topic: string): TutorLectureData | null {
  const ad = (detail.animation_data as Record<string, unknown> | undefined) || {}
  const raw = (ad.lecture || detail.lecture) as TutorLectureData | undefined
  if (raw && Array.isArray(raw.slides) && raw.slides.length) {
    return {
      ...raw,
      lecture_id: raw.lecture_id || lectureId.value || `resource-${resourceId.value}`,
      topic: raw.topic || topic,
      resource_id: resourceId.value || raw.resource_id,
    }
  }
  const animSlides = (ad.slides || detail.slides || detail.storyboard) as Array<Record<string, unknown>> | undefined
  if (!Array.isArray(animSlides) || !animSlides.length) return null
  const slides: TutorLectureSlide[] = animSlides.map((s, i) => {
    const visual = String(s.visual || '').trim()
    const bullets = visual
      .split('\n')
      .map((ln) => ln.replace(/^[•★\s]+/, '').trim())
      .filter(Boolean)
    const title = String(s.title || `第${i + 1}页`)
    const narration = String(s.narration || '')
    if (title === '随堂测验' || s.emoji === '❓') {
      return {
        id: i + 1,
        type: 'quiz',
        title,
        question: narration || title,
        options: bullets.length ? bullets : ['A', 'B', 'C', 'D'],
        answer: 'A',
        narration,
        analysis: '',
      }
    }
    return {
      id: i + 1,
      type: 'content',
      title,
      bullets: bullets.length ? bullets : narration ? [narration.slice(0, 80)] : ['请听讲解'],
      narration,
    }
  })
  return {
    lecture_id: lectureId.value || `resource-${resourceId.value}`,
    topic: topic || 'AI视频讲解',
    slides,
    content_slide_count: slides.filter((x) => x.type === 'content').length,
    quiz_count: slides.filter((x) => x.type === 'quiz').length,
    recommendations: [],
    resource_id: resourceId.value || undefined,
  }
}

async function loadLectureFromResource(): Promise<boolean> {
  if (!resourceId.value) return false
  try {
    const res = isPublicScope.value
      ? await resourceApi.getPublic(resourceId.value)
      : await resourceApi.get(resourceId.value)
    const detail = (res.detail || {}) as Record<string, unknown>
    const data = lectureFromResourceDetail(detail, res.title || res.topic || 'AI视频讲解')
    if (!data?.slides?.length) return false
    lecture.value = data
    return true
  } catch {
    return false
  }
}

async function loadLectureFromHost(): Promise<boolean> {
  if (!fromHost.value && !String(lectureId.value || '').startsWith('host-')) return false
  const id = String(lectureId.value || '').trim()
  if (!id) return false
  try {
    const q = hostProjectId.value
      ? `?projectId=${encodeURIComponent(hostProjectId.value)}`
      : ''
    const urls = [
      `/api/v1/lesson/host-lecture/${encodeURIComponent(id)}${q}`,
      `/public/host-lecture/${encodeURIComponent(id)}${q}`,
    ]
    for (const url of urls) {
      try {
        const resp = await fetch(url, { credentials: 'same-origin' })
        const payload = await resp.json().catch(() => null) as {
          code?: number
          data?: TutorLectureData
        } | null
        if (!resp.ok || !payload || payload.code !== 0 || !payload.data?.slides?.length) {
          continue
        }
        lecture.value = {
          ...payload.data,
          lecture_id: payload.data.lecture_id || id,
          topic: payload.data.topic || '课程讲解',
        }
        return true
      } catch {
        /* try next */
      }
    }
    return false
  } catch {
    return false
  }
}

async function loadLecture() {
  loadError.value = ''
  const cacheKey = `edunexus_lecture_preview_${sessionNo.value || 'res'}_${lectureId.value}`
  if (!lectureId.value && !resourceId.value) {
    loadError.value = '缺少会话或讲解参数'
    loading.value = false
    return
  }
  loading.value = true
  try {
    if (await loadLectureFromHost()) {
      sessionStorage.setItem(cacheKey, JSON.stringify(lecture.value))
      return
    }
    if (sessionNo.value && lectureId.value && !String(lectureId.value).startsWith('resource-') && !String(lectureId.value).startsWith('host-')) {
      try {
        lecture.value = await tutorApi.getLecture(sessionNo.value, lectureId.value)
        if (lecture.value?.slides?.length) {
          sessionStorage.setItem(cacheKey, JSON.stringify(lecture.value))
          return
        }
      } catch {
        /* 会话讲义不可用时回退资源详情 */
      }
    }
    if (await loadLectureFromResource()) {
      sessionStorage.setItem(cacheKey, JSON.stringify(lecture.value))
      return
    }
    try {
      const cached = sessionStorage.getItem(cacheKey)
      if (cached) {
        lecture.value = JSON.parse(cached) as TutorLectureData
        if (lecture.value?.slides?.length) return
      }
    } catch { /* ignore */ }
    loadError.value = '讲解内容为空，请返回资源中心重新生成「AI视频讲解」'
  } catch (e) {
    loadError.value = (e as Error).message || '加载讲解失败，请返回重新生成'
  } finally {
    loading.value = false
  }
}

function onSlideSpeechComplete() {
  finalizeLiveTeacher(getSlideNarrationText())
  if (!autoPlay.value || qaPausedAuto.value || isQuizSlide.value || isOnCompletePage.value) return
  const narr = getSlideNarrationText().trim()
  if (!narr || narr.length < 4) return
  if (slideIndex.value < total.value - 1) {
    goTo(slideIndex.value + 1, { keepAuto: true })
  } else {
    goTo(completionIndex.value, { keepAuto: true })
  }
}

function resetToFirstSlide() {
  stopSpeech()
  slideIndex.value = 0
  slideAnim.value = false
  quizResult.value = null
  quizAnswers.value = []
  showQuiz.value = slides.value[0]?.type === 'quiz'
  chatLog.value = []
  slideTranscripts.value = {}
  chatSeq = 0
  liveTeacherId = null
  slideSentences = []
}

function playCurrentSlide() {
  if (isOnCompletePage.value) return
  if (!current.value) return

  const narr = getSlideNarrationText()
  beginLiveTeacherSpeech()

  if (isQuizSlide.value) {
    bubbleRole.value = 'teacher'
    bubbleText.value = narr
    updateLiveTeacherText(narr)
    if (!muted.value) speakSlide(narr, 0, speed.value)
    else finalizeLiveTeacher(narr)
    return
  }

  const bulletCount = current.value.bullets?.length || 0
  if (muted.value) {
    updateLiveTeacherText(narr)
    finalizeLiveTeacher(narr)
    return
  }
  speakSlide(narr, bulletCount, speed.value, onSlideSpeechComplete)
}

function goTo(index: number, opts?: { keepAuto?: boolean }) {
  if (index < 0 || index > completionIndex.value) return
  finalizeLiveTeacher(getSlideNarrationText())
  stopSpeech()
  if (!opts?.keepAuto) autoPlay.value = false
  slideAnim.value = true
  window.setTimeout(() => { slideAnim.value = false }, 400)
  slideIndex.value = index
  quizResult.value = null
  quizAnswers.value = []
  showQuiz.value = !isOnCompletePage.value && slides.value[index]?.type === 'quiz'

  if (isOnCompletePage.value) {
    void finishLecture()
    return
  }
  playCurrentSlide()
}

function selectSlide(index: number) {
  goTo(index)
}

function togglePreview() {
  previewOpen.value = !previewOpen.value
}

function togglePresentation() {
  const el = stageRef.value
  if (!el) return
  if (!document.fullscreenElement) {
    void el.requestFullscreen?.().catch(() => {
      isPresenting.value = true
      previewOpen.value = false
      notesPanelOpen.value = false
    })
  } else {
    void document.exitFullscreen?.()
  }
}

function toggleNotesPanel() {
  notesPanelOpen.value = !notesPanelOpen.value
}

function onFullscreenChange() {
  const active = document.fullscreenElement === stageRef.value
  isPresenting.value = active
  if (active) {
    previewOpen.value = false
    notesPanelOpen.value = false
  }
}

function prev() {
  goTo(slideIndex.value - 1)
}

function next() {
  if (isOnCompletePage.value) return
  if (slideIndex.value >= total.value - 1) goTo(completionIndex.value)
  else goTo(slideIndex.value + 1)
}

function togglePlay() {
  if (speaking.value) {
    stopSpeech()
    return
  }
  if (!isQuizSlide.value && !isOnCompletePage.value) {
    playCurrentSlide()
  }
}

function toggleMute() {
  muted.value = !muted.value
  if (muted.value && speaking.value) {
    stopSpeech()
  }
}

function onSpeedChange(v: number) {
  speed.value = v
  if (speaking.value) playCurrentSlide()
}

async function exportPptx() {
  if (!lecture.value) return
  const loading = ElMessage.info({ message: '正在生成 PPT，请稍候…', duration: 0 })
  try {
    await exportLecturePptxClient(lecture.value.topic, lecture.value.slides)
    ElMessage.success('PPTX 已开始下载')
  } catch {
    ElMessage.error('导出失败，请重试')
  } finally {
    loading.close()
  }
}

function toggleQuizOption(opt: string) {
  const letter = opt.trim().charAt(0).toUpperCase()
  if (current.value?.multi) {
    if (quizAnswers.value.includes(letter)) {
      quizAnswers.value = quizAnswers.value.filter((a) => a !== letter)
    } else {
      quizAnswers.value = [...quizAnswers.value, letter]
    }
  } else {
    quizAnswers.value = [letter]
  }
}

function gradeQuizLocally(slide: TutorLectureSlide, answers: string[]) {
  const expectedRaw = String(slide.answer || 'A').toUpperCase()
  const expectedLetters = expectedRaw.replace(/[^A-D]/g, '').split('')
  const givenLetters = answers.map((a) => a.trim().charAt(0).toUpperCase()).filter((c) => /[A-D]/.test(c))
  const correct = slide.multi
    ? [...givenLetters].sort().join('') === [...expectedLetters].sort().join('')
    : givenLetters[0] === (expectedLetters[0] || 'A')
  const answer = expectedLetters.join('') || 'A'
  const analysis = String(
    slide.analysis
      || (correct ? '回答正确，我们继续往下讲。' : `正确答案是 ${answer}。结合刚才的讲解再想一遍。`),
  )
  return { correct, analysis, answer }
}

function useLocalQuizGrading() {
  const id = String(lectureId.value || '')
  return fromHost.value
    || !sessionNo.value
    || id.startsWith('host-')
    || id.startsWith('resource-')
}

async function applyQuizResult(res: { correct: boolean; analysis: string; answer?: string }) {
  quizResult.value = res
  quizResults.value.push({ correct: res.correct })
  showQuiz.value = false
  autoPlay.value = true
  const feedback = res.correct ? '回答正确。' : '回答错误。'
  const reply = stripCitationBlock(`${feedback}${res.analysis || ''}`)
  finalizeLiveTeacher()
  liveTeacherId = appendChatMessage('teacher', reply, true)
  await speakReply(reply, speed.value)
  finalizeLiveTeacher(reply)
  if (slideIndex.value < total.value - 1) {
    goTo(slideIndex.value + 1, { keepAuto: true })
  } else {
    goTo(completionIndex.value, { keepAuto: true })
  }
}

async function submitQuiz() {
  if (!quizAnswers.value.length) return
  const slide = current.value
  try {
    let res: { correct: boolean; analysis: string; answer: string }
    if (useLocalQuizGrading() && slide) {
      res = gradeQuizLocally(slide, quizAnswers.value)
    } else {
      res = await tutorApi.submitLectureQuiz(
        sessionNo.value,
        lectureId.value,
        slideIndex.value,
        quizAnswers.value,
      )
    }
    await applyQuizResult(res)
  } catch {
    // 宿主讲解/无会话时后端可能 404：有答案字段则本地判题，避免卡死
    if (slide && (slide.answer || slide.analysis)) {
      try {
        await applyQuizResult(gradeQuizLocally(slide, quizAnswers.value))
        return
      } catch {
        /* fall through */
      }
    }
    ElMessage.error('提交失败')
  }
}

async function markResourceLearned() {
  if (progressMarked || isPublicScope.value) return
  if (!nodeId.value || !resourceId.value) return
  progressMarked = true
  try {
    await pathApi.updateNodeProgress(nodeId.value, {
      status: 2,
      study_duration_sec: Math.max(60, slides.value.length * 30),
      resource_id: resourceId.value,
      mark_resource_done: true,
    })
  } catch {
    progressMarked = false
  }
}

async function finishLecture() {
  if (!summaryLoaded.value) {
    summaryLoaded.value = true
    finalizeLiveTeacher(getSlideNarrationText())
    stopSpeech()
    try {
      summary.value = await tutorApi.getLectureSummary(sessionNo.value, lectureId.value)
      if (summary.value && quizResults.value.length === 0 && summary.value.total_quizzes > 0) {
        quizResults.value = Array.from({ length: summary.value.total_quizzes }, (_, i) => ({
          correct: i < (summary.value?.correct_count ?? 0),
        }))
      }
    } catch { /* ignore */ }
  }
  // 到达完成页即标记路径节点上的视频资源为已学完
  await markResourceLearned()
}

async function goBack() {
  if (isOnCompletePage.value) {
    await markResourceLearned()
  }
  if (pathId.value && !isPublicScope.value) {
    router.push('/student/path')
    return
  }
  if (fromResource.value) {
    if (isPublicScope.value) {
      router.push({ name: 'ResourceSquare' })
      return
    }
    router.push({ name: 'ResourceCenter' })
    return
  }
  if (sessionNo.value) {
    router.push({ path: '/student/tutor', query: { session_no: sessionNo.value } })
    return
  }
  router.push({ name: 'ResourceCenter' })
}

async function askHostLecture(question: string): Promise<string> {
  const id = String(lectureId.value || '').trim()
  if (!id) throw new Error('missing lecture id')
  const body = {
    question,
    slide_index: slideIndex.value,
    projectId: hostProjectId.value || undefined,
    history: askHistory.value.slice(0, -1),
  }
  const urls = [
    `/api/v1/lesson/host-lecture/${encodeURIComponent(id)}/ask`,
    `/public/host-lecture/${encodeURIComponent(id)}/ask`,
  ]
  for (const url of urls) {
    try {
      const resp = await fetch(url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const payload = await resp.json().catch(() => null) as {
        code?: number
        data?: { answer?: string }
        message?: string
      } | null
      const answer = String(payload?.data?.answer || '').trim()
      if (resp.ok && payload?.code === 0 && answer) {
        return answer
      }
    } catch {
      /* try next */
    }
  }
  // 本地兜底：结合当前页讲稿简要回应，避免再次「暂时无法回答」
  const narr = getSlideNarrationText().trim()
  const title = String(current.value?.title || '').trim()
  if (narr || title) {
    return `关于「${title || '这一页'}」：${narr || '请先听完本页讲解。'} 你问的是「${question}」。建议对照上面要点再想一想；若仍不清楚，可以把具体哪一句话或哪个概念告诉我。`
  }
  throw new Error('host ask failed')
}

async function handleAsk(question: string) {
  const q = question.trim()
  if (!q || askLoading.value) return

  qaPausedAuto.value = true
  finalizeLiveTeacher(getSlideNarrationText())
  stopSpeech()
  appendChatMessage('user', q)
  askHistory.value.push({ role: 'user', content: q })
  askLoading.value = true

  try {
    let answerRaw: string
    if (useLocalQuizGrading()) {
      answerRaw = await askHostLecture(q)
    } else {
      const res = await tutorApi.lectureSideAsk(
        sessionNo.value,
        lectureId.value,
        q,
        slideIndex.value,
        askHistory.value.slice(0, -1),
      )
      answerRaw = res.answer
    }
    const answer = stripCitationBlock(answerRaw)
    askHistory.value.push({ role: 'assistant', content: answer })
    liveTeacherId = appendChatMessage('teacher', answer, true)
    await speakReply(answer, speed.value)
    finalizeLiveTeacher(answer)
  } catch {
    const fallback = '抱歉，暂时无法回答。'
    askHistory.value.push({ role: 'assistant', content: fallback })
    liveTeacherId = appendChatMessage('teacher', fallback, true)
    await speakReply(fallback, speed.value)
    finalizeLiveTeacher(fallback)
  } finally {
    askLoading.value = false
    qaPausedAuto.value = false
    if (autoPlay.value && !isQuizSlide.value) playCurrentSlide()
  }
}

watch(bubbleText, (text) => {
  if (bubbleRole.value !== 'teacher') return
  if (text.trim() && (speaking.value || liveTeacherId)) updateLiveTeacherText(text)
})

watch(speaking, (now, prev) => {
  if (prev && !now && liveTeacherId && !askLoading.value) {
    const item = chatLog.value.find((m) => m.id === liveTeacherId)
    if (item?.live) finalizeLiveTeacher(item.content || bubbleText.value)
  }
})

const backLabel = computed(() => {
  if (pathId.value && !isPublicScope.value) return '返回学习路径'
  if (fromResource.value) return isPublicScope.value ? '返回资源广场' : '返回资源中心'
  return '返回对话'
})

onMounted(async () => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
  previewOpen.value = false
  autoPlay.value = false
  await loadLecture()
  if (slides.value.length) {
    resetToFirstSlide()
    playCurrentSlide()
  }
})

onUnmounted(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  stopSpeech()
})
</script>

<template>
  <OpenMaicBackground class="lecture-page" :class="{ presenting: isPresenting }">
    <header v-show="!isPresenting" class="lecture-header">
      <el-button :icon="ArrowLeft" link @click="goBack">{{ backLabel }}</el-button>
      <div class="header-brand">
        <img src="/brand-icon.jpg" alt="" class="brand-mark" />
        <span class="brand-logo">智课共生</span>
        <span class="brand-divider">·</span>
        <h1>{{ lecture?.topic || '沉浸式讲解' }}</h1>
      </div>
      <span class="page-indicator">{{ slideIndex + 1 }} / {{ totalPages }}</span>
      <el-button type="primary" plain :icon="Download" size="small" @click="exportPptx">导出 PPTX</el-button>
    </header>

    <div v-if="loading" class="loading-wrap">
      <el-skeleton :rows="8" animated />
    </div>

    <div v-else-if="loadError" class="error-page">
      <h2>无法加载讲解</h2>
      <p>{{ loadError }}</p>
      <div class="actions">
        <el-button type="primary" @click="goBack">{{ backLabel }}</el-button>
        <el-button @click="loadLecture">重试加载</el-button>
      </div>
    </div>

    <template v-else-if="lecture">
      <div
        ref="stageRef"
        class="lecture-workspace"
        :class="{ presenting: isPresenting, 'notes-open': notesPanelOpen, 'sidebar-open': previewOpen }"
      >
        <LectureSlidePreview
          embedded
          :open="previewOpen"
          :slides="slides"
          :current-index="slideIndex"
          :topic="lecture.topic"
          :completion-index="completionIndex"
          @close="previewOpen = false"
          @select="selectSlide"
        />

        <div class="lecture-main-column">
          <main class="slide-viewport">
            <div class="slide-progress">
              <div class="slide-progress-fill" :style="{ width: `${((slideIndex + 1) / totalPages) * 100}%` }" />
            </div>
            <div
              class="slide-frame"
              :class="{ anim: slideAnim, 'spotlight-mode': spotlightActive, 'complete-frame': isOnCompletePage }"
            >
          <LectureCompletePage
            v-if="isOnCompletePage"
            :title="lecture.topic"
            :stats="completeStats"
          />
          <template v-else-if="current?.type === 'content'">
            <h2 :class="{ dimmed: spotlightActive }">{{ current.title }}</h2>
            <ul>
              <li
                v-for="(b, i) in current.bullets"
                :key="i"
                :class="{
                  'bullet-spotlight': spotlightActive && i === activeBulletIndex,
                  dimmed: spotlightActive && i !== activeBulletIndex,
                }"
              >
                {{ b }}
              </li>
            </ul>
            <p
              v-if="current.highlight"
              class="highlight-box"
              :class="{ dimmed: spotlightActive && activeBulletIndex >= 0 }"
            >
              {{ current.highlight }}
            </p>
            <MermaidViewer v-if="current.mermaid" :class="{ dimmed: spotlightActive }" :code="current.mermaid" />
          </template>
          <template v-else-if="current?.type === 'quiz' && showQuiz">
            <h2>随堂测验</h2>
            <p class="quiz-q">{{ current.question }}</p>
            <div class="quiz-opts">
              <button
                v-for="opt in current.options"
                :key="opt"
                type="button"
                class="quiz-opt"
                :class="{ selected: quizAnswers.includes(opt.charAt(0).toUpperCase()) }"
                @click="toggleQuizOption(opt)"
              >
                {{ opt }}
              </button>
            </div>
            <el-button type="primary" :disabled="!quizAnswers.length" @click="submitQuiz">提交答案</el-button>
          </template>
          <div v-if="quizResult && current?.type === 'quiz'" class="quiz-feedback" :class="{ ok: quizResult.correct }">
            <p>{{ quizResult.correct ? '✓ 回答正确' : '✗ 回答错误' }}</p>
            <MarkdownViewer :content="quizResult.analysis" />
          </div>
            </div>
          </main>

          <TutorLectureRoundtable
            embedded
            :messages="chatLog"
            :speaking="speaking"
            :auto-play="autoPlay"
            :muted="muted"
            :can-prev="slideIndex > 0"
            :can-next="!isOnCompletePage"
            :current-page="slideIndex + 1"
            :total-pages="totalPages"
            :preview-open="previewOpen"
            :is-presenting="isPresenting"
            :notes-panel-open="notesPanelOpen"
            :speed="speed"
            :speed-options="speedOptions"
            :ask-loading="askLoading"
            @toggle-play="togglePlay"
            @prev="prev"
            @next="next"
            @toggle-mute="toggleMute"
            @speed-change="onSpeedChange"
            @send-message="handleAsk"
            @voice-result="handleAsk"
            @toggle-preview="togglePreview"
            @toggle-presentation="togglePresentation"
            @toggle-chat-history="toggleNotesPanel"
          />
        </div>

        <LectureNotesPanel
          :open="notesPanelOpen"
          :slides="slides"
          :current-index="slideIndex"
          :slide-transcripts="slideTranscripts"
          :chat-messages="chatLog"
          @close="notesPanelOpen = false"
        />
      </div>
    </template>
  </OpenMaicBackground>
</template>

<style scoped lang="scss">
.lecture-page {
  color: #0f172a;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.lecture-workspace {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
  background: transparent;

  &:fullscreen {
    background: #f8fafc;
  }

  &.presenting .slide-viewport {
    padding: 16px 24px 0;
  }
}

.lecture-main-column {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.lecture-body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

.lecture-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(148, 163, 184, 0.25);

  .header-brand {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }

  .brand-mark {
    width: 28px;
    height: 28px;
    border-radius: 7px;
    object-fit: cover;
    flex-shrink: 0;
  }

  .brand-logo {
    flex-shrink: 0;
    font-size: 16px;
    font-weight: 800;
    color: #2563eb;
  }

  .brand-divider {
    color: #cbd5e1;
    flex-shrink: 0;
  }

  h1 {
    font-size: 16px;
    margin: 0;
    font-weight: 600;
    color: #475569;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .page-indicator { font-size: 13px; color: #64748b; flex-shrink: 0; }
}

.loading-wrap { padding: 48px; max-width: 70%; margin: 0 auto; width: 100%; }

.slide-viewport {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px 24px 8px;
  gap: 16px;
  overflow: hidden;
}

.slide-progress {
  width: min(960px, 100%);
  flex-shrink: 0;
  height: 4px;
  background: rgba(15, 23, 42, 0.08);
  border-radius: 999px;
  overflow: hidden;
}

.slide-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  border-radius: 999px;
  transition: width 0.35s ease;
}

.slide-frame {
  width: min(960px, 100%);
  max-height: 100%;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(16px);
  color: #1e293b;
  border-radius: 20px;
  padding: 40px 48px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  box-shadow:
    0 24px 48px rgba(15, 23, 42, 0.08),
    0 0 0 1px rgba(255, 255, 255, 0.6);
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.4s ease, box-shadow 0.4s ease;

  &.anim {
    transform: translateY(-4px) scale(1.01);
    opacity: 0.98;
    box-shadow:
      0 32px 64px rgba(37, 99, 235, 0.12),
      0 0 0 1px rgba(255, 255, 255, 0.8);
  }

  &.spotlight-mode {
    box-shadow:
      0 24px 48px rgba(15, 23, 42, 0.12),
      inset 0 0 80px rgba(15, 23, 42, 0.04);
  }

  &.complete-frame {
    padding: 0;
    overflow: hidden;
    background: transparent;
    border: none;
    box-shadow: none;
  }

  h2 { font-size: 28px; margin: 0 0 24px; color: #0f172a; transition: opacity 0.35s ease; }
  ul { padding-left: 20px; }
  li {
    margin: 12px 0;
    font-size: 18px;
    line-height: 1.6;
    border-radius: 10px;
    padding: 6px 10px;
    transition: opacity 0.35s ease, transform 0.35s ease, box-shadow 0.35s ease, background 0.35s ease;
  }

  .dimmed {
    opacity: 0.32;
    filter: saturate(0.6);
  }

  li.bullet-spotlight {
    opacity: 1;
    filter: none;
    background: linear-gradient(90deg, #fef9c3 0%, #fff 100%);
    box-shadow:
      0 0 0 3px rgba(37, 99, 235, 0.22),
      0 8px 28px rgba(37, 99, 235, 0.14);
    transform: scale(1.02);
    font-weight: 600;
    color: #0f172a;
  }
}

.highlight-box {
  margin-top: 24px;
  padding: 16px 20px;
  background: #eff6ff;
  border-left: 4px solid #2563eb;
  border-radius: 8px;
  font-size: 17px;
  font-weight: 500;
  transition: opacity 0.35s ease;
}

.quiz-q { font-size: 20px; margin-bottom: 20px; }
.quiz-opts { display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; }
.quiz-opt {
  text-align: left;
  padding: 12px 16px;
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
  cursor: pointer;
  font-size: 16px;
  &.selected { border-color: #2563eb; background: #eff6ff; }
}
.quiz-feedback {
  margin-top: 16px;
  padding: 16px;
  border-radius: 8px;
  background: #fef2f2;
  &.ok { background: #f0fdf4; }
}

.error-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  text-align: center;
  color: #0f172a;
  h2 { margin: 0 0 12px; }
  p { color: #64748b; margin: 0 0 24px; }
  .actions { display: flex; gap: 12px; }
}

@media (max-width: 768px) {
  .slide-frame { width: 92%; padding: 24px; }
}
</style>
