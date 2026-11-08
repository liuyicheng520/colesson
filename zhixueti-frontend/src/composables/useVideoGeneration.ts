/**
 * 沉浸式视频讲解生成流程（参考 OpenMAIC generation-preview 交互模式）
 * - 悬浮弹窗 + 分步动画
 * - 大纲流式预览 + 2.5s 自动继续审阅门控
 * - 确认后走沉浸式 lecture SSE，完成后跳转讲解页
 */
import { ref, computed } from 'vue'
import { tutorApi } from '@/api/tutor'
import type { TutorLectureData, TutorOutlineItem } from '@/types'

export type VideoGenPhase =
  | 'idle'
  | 'preparing'
  | 'outline'
  | 'review'
  | 'generating'
  | 'done'
  | 'error'

export const OUTLINE_REVIEW_AUTO_CONTINUE_MS = 2500

const STEPS = [
  { id: 'parse', label: '解析需求' },
  { id: 'outline', label: '生成大纲' },
  { id: 'content', label: '生成讲解' },
  { id: 'narration', label: '合成语音' },
  { id: 'done', label: '完成' },
] as const

export interface VideoGenDeps {
  getSessionNo: () => string
  ensureSession: (topic: string) => Promise<void>
  getStreamOptions: () => { web_search_enabled: boolean; deep_mode: boolean }
  onUserMessage?: (content: string) => void
  onAssistantNote?: (
    content: string,
    lecture?: { lecture_id: string; topic: string; slide_count: number; resource_id?: number },
  ) => void
  onComplete?: (lectureId: string) => void
}

function outlineToSourceText(outline: TutorOutlineItem[], topic: string): string {
  const lines = outline.map((o, i) => {
    const goals = (o.objectives || []).filter(Boolean).join('、') || '掌握核心概念'
    return `${i + 1}. ${o.title}\n   学习目标：${goals}\n   建议时长：${o.duration_min ?? 5} 分钟`
  })
  return `讲解主题：${topic}\n\n已确认课程大纲：\n${lines.join('\n\n')}`
}

function lecturePhaseToStep(phase?: string): number {
  const map: Record<string, number> = { parse: 0, outline: 1, slides: 2, narration: 3, done: 4 }
  return map[phase || ''] ?? 2
}

export function useVideoGeneration(deps: VideoGenDeps) {
  const visible = ref(false)
  const phase = ref<VideoGenPhase>('idle')
  const topic = ref('')
  const stepIndex = ref(0)
  const progressText = ref('')
  const error = ref<string | null>(null)
  const outline = ref<TutorOutlineItem[]>([])
  const streamingOutline = ref<TutorOutlineItem[]>([])
  const isOutlineStreaming = ref(false)
  const reviewOutlineEnabled = ref(false)
  const reviewIntent = ref(false)
  const autoContinueHint = ref('')
  const lecture = ref<TutorLectureData | null>(null)
  const confirming = ref(false)

  const abortController = ref<AbortController | null>(null)
  const reviewTimer = ref<ReturnType<typeof setTimeout> | null>(null)
  const reviewResolve = ref<((o: TutorOutlineItem[]) => void) | null>(null)

  const steps = STEPS
  const activeStep = computed(() => steps[Math.min(stepIndex.value, steps.length - 1)])

  function clearReviewTimer() {
    if (reviewTimer.value) {
      clearTimeout(reviewTimer.value)
      reviewTimer.value = null
    }
  }

  function abortFlow() {
    clearReviewTimer()
    abortController.value?.abort()
    abortController.value = null
    reviewResolve.value = null
  }

  function resetState() {
    phase.value = 'idle'
    stepIndex.value = 0
    progressText.value = ''
    error.value = null
    outline.value = []
    streamingOutline.value = []
    isOutlineStreaming.value = false
    reviewIntent.value = false
    autoContinueHint.value = ''
    lecture.value = null
    confirming.value = false
  }

  function waitForOutlineReview(
    outlines: TutorOutlineItem[],
    shouldReview: boolean,
    signal: AbortSignal,
  ): Promise<TutorOutlineItem[]> {
    return new Promise((resolve, reject) => {
      if (signal.aborted) {
        reject(new DOMException('Aborted', 'AbortError'))
        return
      }
      reviewResolve.value = resolve
      const onAbort = () => {
        clearReviewTimer()
        reviewResolve.value = null
        reject(new DOMException('Aborted', 'AbortError'))
      }
      signal.addEventListener('abort', onAbort, { once: true })

      if (!shouldReview) {
        autoContinueHint.value = `${OUTLINE_REVIEW_AUTO_CONTINUE_MS / 1000} 秒后自动继续生成讲解…`
        reviewTimer.value = setTimeout(() => {
          reviewTimer.value = null
          reviewResolve.value = null
          signal.removeEventListener('abort', onAbort)
          autoContinueHint.value = ''
          resolve(outlines)
        }, OUTLINE_REVIEW_AUTO_CONTINUE_MS)
      }
    })
  }

  async function fetchOutline(content: string, signal: AbortSignal): Promise<TutorOutlineItem[]> {
    const sessionNo = deps.getSessionNo()
    if (!sessionNo) throw new Error('会话未就绪')

    isOutlineStreaming.value = true
    streamingOutline.value = []
    stepIndex.value = 1
    phase.value = 'outline'
    progressText.value = '正在生成课程大纲…'

    let result: TutorOutlineItem[] = []

    await tutorApi.streamMessage(
      sessionNo,
      content,
      {
        onProgress: (p) => {
          progressText.value = p.message || progressText.value
          if (p.phase === 'outline') stepIndex.value = 1
        },
        onOutline: (data) => {
          result = data.outline
          streamingOutline.value = data.outline.map((o) => ({
            ...o,
            objectives: [...(o.objectives || [])],
          }))
          outline.value = streamingOutline.value
        },
        onDone: () => {
          isOutlineStreaming.value = false
        },
      },
      {
        force_lecture: true,
        signal,
        ...deps.getStreamOptions(),
      },
    )

    isOutlineStreaming.value = false
    if (!result.length && outline.value.length) result = outline.value
    if (!result.length) throw new Error('大纲生成失败，请重试')
    outline.value = result
    streamingOutline.value = result
    return result
  }

  async function fetchLecture(confirmed: TutorOutlineItem[], signal: AbortSignal) {
    const sessionNo = deps.getSessionNo()
    const sourceText = outlineToSourceText(confirmed, topic.value)
    phase.value = 'generating'
    stepIndex.value = 2
    progressText.value = '正在生成沉浸式讲解…'

    await tutorApi.streamLectureGenerate(
      sessionNo,
      topic.value,
      sourceText,
      {
        onProgress: (p) => {
          progressText.value = p.message || progressText.value
          if (p.phase) stepIndex.value = lecturePhaseToStep(p.phase)
        },
        onDone: (data) => {
          if (!data.lecture?.lecture_id) throw new Error('生成结果无效')
          lecture.value = data.lecture
          stepIndex.value = 4
          phase.value = 'done'
          progressText.value = '讲解已生成完成'
          if (data.resource_id) {
            lecture.value = { ...data.lecture, resource_id: data.resource_id }
          }
        },
        onError: (msg) => {
          throw new Error(msg)
        },
      },
      signal,
    )
  }

  async function runFlow(content: string) {
    resetState()
    topic.value = content
    visible.value = true
    phase.value = 'preparing'
    stepIndex.value = 0
    progressText.value = '正在准备生成环境…'

    abortController.value?.abort()
    const controller = new AbortController()
    abortController.value = controller
    const { signal } = controller

    try {
      await deps.ensureSession(content.slice(0, 100))
      deps.onUserMessage?.(content)

      const outlines = await fetchOutline(content, signal)

      const shouldReview = reviewOutlineEnabled.value || reviewIntent.value
      if (shouldReview) {
        phase.value = 'review'
        progressText.value = isOutlineStreaming.value
          ? '大纲生成中，可先预览已生成节点…'
          : '请审阅并确认课程大纲'
      } else {
        autoContinueHint.value = `${OUTLINE_REVIEW_AUTO_CONTINUE_MS / 1000} 秒后自动继续…`
      }

      const confirmed = await waitForOutlineReview(outlines, shouldReview, signal)
      clearReviewTimer()
      autoContinueHint.value = ''
      outline.value = confirmed

      await fetchLecture(confirmed, signal)

      deps.onAssistantNote?.(
        `✅ 已为您生成「${topic.value.slice(0, 40)}」的沉浸式视频讲解（${lecture.value?.slides?.length || 0} 页），已保存至个人资源中心并公开至资源广场。`,
        lecture.value?.lecture_id
          ? {
              lecture_id: lecture.value.lecture_id,
              topic: topic.value,
              slide_count: lecture.value.slides?.length || 0,
              resource_id: lecture.value.resource_id,
            }
          : undefined,
      )
      if (lecture.value?.lecture_id) {
        deps.onComplete?.(lecture.value.lecture_id)
      }
    } catch (e) {
      if ((e as Error).name === 'AbortError') {
        visible.value = false
        return
      }
      phase.value = 'error'
      error.value = (e as Error).message || '视频讲解生成失败'
      progressText.value = ''
    } finally {
      if (abortController.value === controller) {
        abortController.value = null
      }
    }
  }

  function open(content: string) {
    if (!content.trim()) return
    void runFlow(content.trim())
  }

  function close() {
    abortFlow()
    visible.value = false
    resetState()
  }

  function expandReview() {
    if (phase.value !== 'outline' && phase.value !== 'review') return
    clearReviewTimer()
    autoContinueHint.value = ''
    reviewIntent.value = true
    phase.value = 'review'
    progressText.value = isOutlineStreaming.value
      ? '大纲生成中，可先编辑已生成节点…'
      : '请审阅并确认课程大纲'
  }

  function collapseReview() {
    if (phase.value !== 'review') return
    reviewIntent.value = false
    if (isOutlineStreaming.value) {
      phase.value = 'outline'
      progressText.value = '正在生成课程大纲…'
      return
    }
    phase.value = 'outline'
    autoContinueHint.value = `${OUTLINE_REVIEW_AUTO_CONTINUE_MS / 1000} 秒后自动继续…`
    clearReviewTimer()
    const current = outline.value.length ? outline.value : streamingOutline.value
    if (!current.length) return

    reviewTimer.value = setTimeout(() => {
      reviewTimer.value = null
      const resolve = reviewResolve.value
      reviewResolve.value = null
      autoContinueHint.value = ''
      if (resolve) {
        resolve(current)
        return
      }
      void (async () => {
        try {
          await fetchLecture(current, abortController.value?.signal || new AbortController().signal)
        } catch (e) {
          if ((e as Error).name !== 'AbortError') {
            phase.value = 'error'
            error.value = (e as Error).message
          }
        }
      })()
    }, OUTLINE_REVIEW_AUTO_CONTINUE_MS)
  }

  function confirmReview(confirmed: TutorOutlineItem[]) {
    confirming.value = true
    clearReviewTimer()
    autoContinueHint.value = ''
    reviewIntent.value = false
    outline.value = confirmed

    if (reviewResolve.value) {
      const resolve = reviewResolve.value
      reviewResolve.value = null
      resolve(confirmed)
      confirming.value = false
      return
    }

    confirming.value = false
    void (async () => {
      try {
        await fetchLecture(confirmed, abortController.value?.signal || new AbortController().signal)
      } catch (e) {
        if ((e as Error).name !== 'AbortError') {
          phase.value = 'error'
          error.value = (e as Error).message
        }
      }
    })()
  }

  function retry() {
    if (!topic.value) return
    void runFlow(topic.value)
  }

  return {
    visible,
    phase,
    topic,
    stepIndex,
    steps,
    activeStep,
    progressText,
    error,
    outline,
    streamingOutline,
    isOutlineStreaming,
    reviewOutlineEnabled,
    autoContinueHint,
    lecture,
    confirming,
    open,
    close,
    expandReview,
    collapseReview,
    confirmReview,
    retry,
  }
}
