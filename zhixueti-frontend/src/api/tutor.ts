import { getToken } from './request'
import { request } from './request'
import service from './request'
import type {
  TutorDocumentItem,
  TutorLectureData,
  TutorLectureSummary,
  TutorMessageMeta,
  TutorOutlineItem,
  TutorSessionData,
} from '@/types'

export interface TutorSessionCreateParams {
  topic: string
  tutor_mode?: string
  path_id?: number
  node_id?: number
  resource_id?: number
  question_id?: number
  profile_adapt_enabled?: boolean
  answer_detail?: 'brief' | 'normal' | 'detailed'
  show_steps?: boolean
  deep_mode?: boolean
  web_search_enabled?: boolean
  document_ids?: string[]
}

export interface StreamHandlers {
  onMeta?: (meta: TutorMessageMeta) => void
  onChunk?: (text: string) => void
  onThinkChunk?: (text: string) => void
  onProgress?: (data: { phase?: string; message?: string }) => void
  onOutline?: (data: { outline: TutorOutlineItem[]; topic?: string }) => void
  onSlides?: (data: { index: number; slides: unknown[] }) => void
  onModuleStart?: (data: { index: number; title: string; phase: string }) => void
  onModuleChunk?: (data: { index: number; module: string; content: string }) => void
  onModuleDone?: (data: { index: number; title: string }) => void
  onLectureDone?: (data: { sections: number }) => void
  onDone?: (data: { round_no: number; meta: TutorMessageMeta; content?: string }) => void
}

export interface StreamOptions {
  request_full_answer?: boolean
  retry_assistant?: boolean
  web_search_enabled?: boolean
  deep_mode?: boolean
  force_lecture?: boolean
  confirmed_outline?: TutorOutlineItem[]
  signal?: AbortSignal
}

export interface TutorSessionSettingsParams {
  document_ids?: string[]
  deep_mode?: boolean
  web_search_enabled?: boolean
  answer_detail?: 'brief' | 'normal' | 'detailed'
  show_steps?: boolean
  profile_adapt_enabled?: boolean
  tutor_mode?: string
}

export const tutorApi = {
  createSession(data: TutorSessionCreateParams) {
    return request<TutorSessionData>({ method: 'POST', url: '/tutor/sessions', data })
  },

  getSession(sessionNo: string) {
    return request<TutorSessionData>({ method: 'GET', url: `/tutor/sessions/${sessionNo}` })
  },

  listSessions() {
    return request<TutorSessionData[]>({ method: 'GET', url: '/tutor/sessions' })
  },

  deleteSession(sessionNo: string) {
    return request<void>({ method: 'DELETE', url: `/tutor/sessions/${sessionNo}` })
  },

  bindDocuments(sessionNo: string, documentIds: string[]) {
    return request<TutorSessionData>({
      method: 'PUT',
      url: `/tutor/sessions/${sessionNo}/documents`,
      data: { document_ids: documentIds },
    })
  },

  updateSettings(sessionNo: string, settings: TutorSessionSettingsParams) {
    return request<TutorSessionData>({
      method: 'PUT',
      url: `/tutor/sessions/${sessionNo}/settings`,
      data: settings,
    })
  },

  async uploadDocument(
    sessionNo: string,
    file: File,
    onProgress?: (pct: number) => void,
  ) {
    const form = new FormData()
    form.append('file', file)
    const res = await service.request({
      method: 'POST',
      url: `/tutor/sessions/${sessionNo}/documents/upload`,
      data: form,
      onUploadProgress: (e) => {
        if (e.total && onProgress) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    })
    const body = res.data
    if (body.code !== 0) throw new Error(body.message || '上传失败')
    return body.data as TutorDocumentItem & { truncated?: boolean; preview?: string }
  },

  listSessionDocuments(sessionNo: string) {
    return request<TutorDocumentItem[]>({
      method: 'GET',
      url: `/tutor/sessions/${sessionNo}/documents`,
    })
  },

  deleteDocument(sessionNo: string, docId: string) {
    return request<TutorSessionData>({
      method: 'DELETE',
      url: `/tutor/sessions/${sessionNo}/documents/${docId}`,
    })
  },

  generateLecture(sessionNo: string, topic: string, sourceText?: string) {
    return request<TutorLectureData>({
      method: 'POST',
      url: `/tutor/sessions/${sessionNo}/lecture/generate`,
      data: { topic, source_text: sourceText },
    })
  },

  async streamLectureGenerate(
    sessionNo: string,
    topic: string,
    sourceText: string | undefined,
    handlers: {
      onProgress?: (data: { phase?: string; message?: string }) => void
      onDone?: (data: { lecture: TutorLectureData; resource_id?: number }) => void
      onError?: (message: string) => void
    },
    externalSignal?: AbortSignal,
  ): Promise<void> {
    const base = import.meta.env.VITE_API_BASE || '/api/v1'
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), 130_000)

    const onExternalAbort = () => controller.abort()
    if (externalSignal) {
      if (externalSignal.aborted) controller.abort()
      else externalSignal.addEventListener('abort', onExternalAbort, { once: true })
    }

    let resp: Response
    try {
      resp = await fetch(`${base}/tutor/sessions/${sessionNo}/lecture/generate/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify({ topic, source_text: sourceText }),
        signal: controller.signal,
      })
    } catch (e) {
      window.clearTimeout(timer)
      if ((e as Error).name === 'AbortError') {
        throw new Error('讲解生成超时，请重试')
      }
      throw e
    }

    if (!resp.ok || !resp.body) {
      window.clearTimeout(timer)
      const errText = await resp.text().catch(() => '')
      throw new Error(errText || '讲解生成请求失败')
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6).trim()
          if (payload === '[DONE]') return
          let json: Record<string, unknown>
          try {
            json = JSON.parse(payload) as Record<string, unknown>
          } catch {
            continue
          }
          const type = json.type as string
          if (type === 'progress') handlers.onProgress?.(json as { phase?: string; message?: string })
          else if (type === 'error') {
            const msg = String(json.message || '讲解生成失败')
            handlers.onError?.(msg)
            throw new Error(msg)
          } else if (type === 'done') {
            handlers.onDone?.({
              lecture: (json.lecture || json) as TutorLectureData,
              resource_id: typeof json.resource_id === 'number' ? json.resource_id : undefined,
            })
            return
          }
        }
      }
      buffer += decoder.decode()
      if (buffer.trim()) {
        for (const line of buffer.split('\n')) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6).trim()
          if (payload === '[DONE]') return
          try {
            const json = JSON.parse(payload) as Record<string, unknown>
            if (json.type === 'done') {
              handlers.onDone?.({
                lecture: (json.lecture || json) as TutorLectureData,
                resource_id: typeof json.resource_id === 'number' ? json.resource_id : undefined,
              })
            }
          } catch { /* skip */ }
        }
      }
    } finally {
      window.clearTimeout(timer)
      if (externalSignal) externalSignal.removeEventListener('abort', onExternalAbort)
    }
  },

  getLecture(sessionNo: string, lectureId: string) {
    return request<TutorLectureData>({
      method: 'GET',
      url: `/tutor/sessions/${sessionNo}/lecture/${lectureId}`,
    })
  },

  async exportLecturePptx(sessionNo: string, lectureId: string, filename: string) {
    const base = import.meta.env.VITE_API_BASE || '/api/v1'
    const resp = await fetch(`${base}/tutor/sessions/${sessionNo}/lecture/${lectureId}/export`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    if (!resp.ok) {
      const text = await resp.text().catch(() => '')
      throw new Error(text || '导出失败')
    }
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename.endsWith('.pptx') ? filename : `${filename}.pptx`
    a.style.display = 'none'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  },

  lectureSideAsk(
    sessionNo: string,
    lectureId: string,
    question: string,
    slideIndex: number,
    history: Array<{ role: string; content: string }>,
  ) {
    return request<{ answer: string }>({
      method: 'POST',
      url: `/tutor/sessions/${sessionNo}/lecture/${lectureId}/ask`,
      data: { question, slide_index: slideIndex, history },
    })
  },

  submitLectureQuiz(sessionNo: string, lectureId: string, slideIndex: number, answers: string[]) {
    return request<{ correct: boolean; analysis: string; answer: string }>({
      method: 'POST',
      url: `/tutor/sessions/${sessionNo}/lecture/${lectureId}/quiz`,
      data: { slide_index: slideIndex, answers },
    })
  },

  getLectureSummary(sessionNo: string, lectureId: string) {
    return request<TutorLectureSummary>({
      method: 'GET',
      url: `/tutor/sessions/${sessionNo}/lecture/${lectureId}/summary`,
    })
  },

  multimodal(sessionNo: string, action: 'image' | 'video' | 'tts', prompt: string, sourceText?: string) {
    return request<{ action: string; payload: Record<string, unknown> }>({
      method: 'POST',
      url: `/tutor/sessions/${sessionNo}/multimodal`,
      data: { action, prompt, source_text: sourceText },
    })
  },

  async streamMessage(
    sessionNo: string,
    content: string,
    handlers: StreamHandlers,
    options?: StreamOptions,
  ): Promise<void> {
    const base = import.meta.env.VITE_API_BASE || '/api/v1'
    const deep = options?.deep_mode ?? false
    const web = options?.web_search_enabled ?? false
    const timeoutMs = deep ? 55_000 : web ? 45_000 : 30_000
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), timeoutMs)

    const onExternalAbort = () => controller.abort()
    if (options?.signal) {
      if (options.signal.aborted) controller.abort()
      else options.signal.addEventListener('abort', onExternalAbort, { once: true })
    }

    let resp: Response
    try {
      resp = await fetch(`${base}/tutor/sessions/${sessionNo}/message/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify({
          content,
          request_full_answer: options?.request_full_answer ?? false,
          retry_assistant: options?.retry_assistant ?? false,
          web_search_enabled: options?.web_search_enabled,
          deep_mode: options?.deep_mode,
          force_lecture: options?.force_lecture ?? false,
          confirmed_outline: options?.confirmed_outline,
        }),
        signal: controller.signal,
      })
    } catch (e) {
      window.clearTimeout(timer)
      if (options?.signal) options.signal.removeEventListener('abort', onExternalAbort)
      if ((e as Error).name === 'AbortError') {
        if (options?.signal?.aborted) throw new DOMException('用户已停止生成', 'AbortError')
        throw new Error('响应超时，请重试')
      }
      const msg = (e as Error).message || ''
      if (msg === 'Failed to fetch' || msg === 'Network Error') {
        throw new Error('无法连接服务器，请确认后端服务已启动')
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

    const dispatchEvent = (payload: string) => {
      if (payload === '[DONE]') return 'done' as const
      try {
        const json = JSON.parse(payload) as Record<string, unknown>
        const type = json.type as string
        if (type === 'chunk' && json.content != null && json.content !== '') {
          handlers.onChunk?.(String(json.content))
        } else if (type === 'think_chunk' && json.content != null && json.content !== '') {
          handlers.onThinkChunk?.(String(json.content))
        } else if (type === 'meta') handlers.onMeta?.(json as unknown as TutorMessageMeta)
        else if (type === 'progress') handlers.onProgress?.(json as { phase?: string; message?: string })
        else if (type === 'outline') handlers.onOutline?.(json as { outline: TutorOutlineItem[]; topic?: string })
        else if (type === 'slides') handlers.onSlides?.(json as { index: number; slides: unknown[] })
        else if (type === 'module_start') handlers.onModuleStart?.(json as { index: number; title: string; phase: string })
        else if (type === 'module_chunk') handlers.onModuleChunk?.(json as { index: number; module: string; content: string })
        else if (type === 'module_done') handlers.onModuleDone?.(json as { index: number; title: string })
        else if (type === 'lecture_done') handlers.onLectureDone?.(json as { sections: number })
        else if (type === 'done') {
          handlers.onDone?.({
            round_no: (json.round_no as number) || 0,
            meta: json.meta as TutorMessageMeta,
            content: json.content ? String(json.content) : undefined,
          })
        }
      } catch { /* skip malformed event */ }
      return 'continue' as const
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
            if (!line.startsWith('data: ')) continue
            const result = dispatchEvent(line.slice(6).trim())
            if (result === 'done') return
          }
          sep = buffer.indexOf('\n\n')
        }
      }
      buffer += decoder.decode()
      if (buffer.trim()) {
        for (const line of buffer.replace(/\r\n/g, '\n').split('\n')) {
          if (!line.startsWith('data: ')) continue
          const result = dispatchEvent(line.slice(6).trim())
          if (result === 'done') return
        }
      }
    } finally {
      window.clearTimeout(timer)
      if (options?.signal) options.signal.removeEventListener('abort', onExternalAbort)
    }
  },
}

export function getSessionTitle(session: TutorSessionData): string {
  const firstUser = session.messages.find((m) => m.role === 'user')
  const raw = firstUser?.content || session.topic || '新对话'
  return raw.length > 15 ? `${raw.slice(0, 15)}…` : raw
}

export function displayMessageRound(roundNo: number): number {
  return roundNo > 0 ? roundNo : 1
}
