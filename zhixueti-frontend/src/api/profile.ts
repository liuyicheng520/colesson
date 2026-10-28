import { request, getToken, API_TIMEOUT } from './request'
import { stripLlmStreamMarkers } from '@/utils/llmStreamMarkers'
import type {
  AssessmentQuestionItem,
  BehaviorGenerateData,
  DialogueMessageData,
  DialogueStartData,
  ProfileData,
  ProfileModesMeta,
  QuestionnaireItem,
} from '@/types'

export type ProfileStreamHandlers = {
  onChunk?: (text: string) => void
  onReplace?: (text: string) => void
  onDone?: (data: DialogueMessageData) => void
}

export const profileApi = {
  get() {
    return request<ProfileData>({ method: 'GET', url: '/profiles' })
  },

  updateDimension(data: {
    dimension_code: string
    dimension_value: Record<string, unknown>
    confidence?: number
    source_type?: string
  }) {
    return request<ProfileData>({ method: 'PUT', url: '/profiles/dimensions', data })
  },

  startDialogue() {
    return request<DialogueStartData>({
      method: 'POST',
      url: '/profiles/dialogue/start',
      timeout: API_TIMEOUT.long,
    })
  },

  sendMessage(sessionNo: string, content: string) {
    return request<DialogueMessageData>({
      method: 'POST',
      url: `/profiles/dialogue/${sessionNo}/message`,
      data: { content },
      timeout: API_TIMEOUT.long,
    })
  },

  async streamMessage(
    sessionNo: string,
    content: string,
    handlers: ProfileStreamHandlers,
    options?: { signal?: AbortSignal },
  ): Promise<void> {
    const base = import.meta.env.VITE_API_BASE || '/api/v1'
    const controller = new AbortController()
    const onExternalAbort = () => controller.abort()
    if (options?.signal) {
      if (options.signal.aborted) controller.abort()
      else options.signal.addEventListener('abort', onExternalAbort, { once: true })
    }
    const timer = window.setTimeout(() => controller.abort(), API_TIMEOUT.long)

    let resp: Response
    try {
      resp = await fetch(`${base}/profiles/dialogue/${sessionNo}/message/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify({ content }),
        signal: controller.signal,
      })
    } catch (e) {
      window.clearTimeout(timer)
      if (options?.signal) options.signal.removeEventListener('abort', onExternalAbort)
      if ((e as Error).name === 'AbortError') {
        throw new DOMException('已中断', 'AbortError')
      }
      throw e
    }

    if (!resp.ok || !resp.body) {
      window.clearTimeout(timer)
      throw new Error('流式请求失败')
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    const dispatch = (payload: string) => {
      if (payload === '[DONE]') return
      try {
        const json = JSON.parse(payload) as Record<string, unknown>
        const type = json.type as string
        if (type === 'chunk' && json.content != null) {
          handlers.onChunk?.(stripLlmStreamMarkers(String(json.content)))
        } else if (type === 'replace' && json.content != null) {
          handlers.onReplace?.(stripLlmStreamMarkers(String(json.content)))
        } else if (type === 'done') handlers.onDone?.(json as unknown as DialogueMessageData)
      } catch {
        /* skip */
      }
    }

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        buffer = buffer.replace(/\r\n/g, '\n')
        let sep = buffer.indexOf('\n\n')
        while (sep >= 0) {
          const block = buffer.slice(0, sep)
          buffer = buffer.slice(sep + 2)
          for (const line of block.split('\n')) {
            if (line.startsWith('data: ')) dispatch(line.slice(6).trim())
          }
          sep = buffer.indexOf('\n\n')
        }
      }
      buffer += decoder.decode()
      if (buffer.trim()) {
        for (const line of buffer.replace(/\r\n/g, '\n').split('\n')) {
          if (line.startsWith('data: ')) dispatch(line.slice(6).trim())
        }
      }
    } finally {
      window.clearTimeout(timer)
      if (options?.signal) options.signal.removeEventListener('abort', onExternalAbort)
    }
  },

  switchDimension(sessionNo: string, dimensionCode: string) {
    return request<DialogueStartData>({
      method: 'POST',
      url: `/profiles/dialogue/${sessionNo}/switch-dimension`,
      data: { dimension_code: dimensionCode },
    })
  },

  getQuestionnaire() {
    return request<QuestionnaireItem[]>({ method: 'GET', url: '/profiles/questionnaire' })
  },

  submitQuestionnaire(data: { answers: { dimension_code: string; option_id: string }[] }) {
    return request<ProfileData>({ method: 'POST', url: '/profiles/questionnaire/submit', data })
  },

  getAssessmentBank() {
    return request<AssessmentQuestionItem[]>({ method: 'GET', url: '/profiles/assessment/bank' })
  },

  submitAssessment(data: {
    answers: { question_id: string; selected_index: number }[]
    theta?: number
    standard_error?: number
  }) {
    return request<ProfileData>({ method: 'POST', url: '/profiles/assessment/submit', data })
  },

  getBehaviorAvailability() {
    return request<{ has_data: boolean; resources_learned: number }>({
      method: 'GET',
      url: '/profiles/behavior/availability',
    })
  },

  generateBehaviorProfile() {
    return request<BehaviorGenerateData>({ method: 'POST', url: '/profiles/behavior/generate' })
  },

  refreshBehaviorProfile() {
    return request<{ refreshed: boolean; reason?: string; updated_dimensions?: string[] }>({
      method: 'POST',
      url: '/profiles/behavior/refresh',
    })
  },

  getModesMeta() {
    return request<ProfileModesMeta>({ method: 'GET', url: '/profiles/modes/meta' })
  },
}
