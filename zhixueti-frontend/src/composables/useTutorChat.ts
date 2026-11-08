import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { tutorApi, type TutorSessionCreateParams } from '@/api/tutor'
import { createThinkStreamSplitter, appendStreamContent, sanitizeAnswerContent, splitStoredMessage, stripThinkTags } from '@/utils/thinkStreamParser'
import type {
  ChatMessage,
  TutorDocumentItem,
  TutorMessageMeta,
  TutorOutlineItem,
  TutorRelatedResource,
  TutorSessionData,
  TutorSlide,
} from '@/types'

const lectureEntriesKey = (sessionNo: string) => `edunexus_lecture_entries_${sessionNo}`

interface StoredLectureEntry {
  lecture_id: string
  topic: string
  slide_count: number
  created_at: string
}

function saveLectureEntry(sessionNo: string, entry: StoredLectureEntry) {
  if (!sessionNo) return
  try {
    const prev: StoredLectureEntry[] = JSON.parse(sessionStorage.getItem(lectureEntriesKey(sessionNo)) || '[]')
    if (prev.some((e) => e.lecture_id === entry.lecture_id)) return
    prev.push(entry)
    sessionStorage.setItem(lectureEntriesKey(sessionNo), JSON.stringify(prev))
  } catch { /* ignore */ }
}

function restoreLectureMessages(msgs: TutorChatMessage[], sessionNo: string): TutorChatMessage[] {
  if (!sessionNo) return msgs
  let entries: StoredLectureEntry[] = []
  try {
    entries = JSON.parse(sessionStorage.getItem(lectureEntriesKey(sessionNo)) || '[]')
  } catch { return msgs }
  if (!entries.length) return msgs

  const existing = new Set(
    msgs.filter((m) => m.meta?.lecture_id).map((m) => m.meta!.lecture_id as string),
  )
  const restored = [...msgs]
  for (const e of entries) {
    if (existing.has(e.lecture_id)) continue
    restored.push({
      id: `msg-lecture-${e.lecture_id}`,
      role: 'assistant',
      content: `✅ 沉浸式视频讲解「${e.topic.slice(0, 40)}」已生成（${e.slide_count} 页），可随时进入学习。`,
      meta: {
        knowledge_points: [],
        related_resources: [],
        message_type: 'video_lecture',
        strategy_used: 'video_lecture',
        hint_level: 0,
        is_exercise: false,
        lecture_id: e.lecture_id,
        lecture_topic: e.topic,
        lecture_slide_count: e.slide_count,
      },
    })
  }
  return restored
}

export type GenPhase = 'idle' | 'outline' | 'confirm' | 'modules' | 'done'
export type ActiveTool = 'image' | 'video' | 'tts'

export type TutorChatMessage = ChatMessage & {
  meta?: TutorMessageMeta
  round_no?: number
  failed?: boolean
  slides?: TutorSlide[]
  multimodal?: Record<string, unknown>
  progressMessage?: string
  thinkingContent?: string
  thinkingDurationSec?: number
}

let msgCounter = 0

function mapMessages(data: TutorSessionData): TutorChatMessage[] {
  return data.messages.map((m) => {
    const split = m.role === 'assistant'
      ? splitStoredMessage(m.content)
      : { thinkingContent: '', content: m.content }
    return {
      id: `msg-${++msgCounter}`,
      role: m.role as ChatMessage['role'],
      content: split.content,
      thinkingContent: split.thinkingContent || undefined,
      round_no: m.round_no,
      meta: m.role === 'assistant'
        ? (m.meta || (m.strategy_used
          ? {
              strategy_used: m.strategy_used,
              knowledge_points: [],
              related_resources: [],
              hint_level: 0,
              is_exercise: false,
              message_type: m.message_type,
            }
          : undefined))
        : undefined,
      slides: m.meta?.slides?.length ? (m.meta.slides as TutorSlide[]) : undefined,
      multimodal: m.meta?.multimodal || undefined,
    }
  })
}

function restoreSlidesFromMessages(msgs: TutorChatMessage[]): TutorSlide[] {
  for (let i = msgs.length - 1; i >= 0; i--) {
    const m = msgs[i]
    if (m.role === 'assistant' && m.slides?.length) return m.slides
    if (m.meta?.slides?.length) return m.meta.slides as TutorSlide[]
  }
  return []
}

function applySessionState(data: TutorSessionData, state: ReturnType<typeof createState>) {
  state.sessionNo.value = data.session_no
  state.profileSummary.value = data.profile_summary
  state.tutorMode.value = data.tutor_mode
  state.totalRounds.value = data.total_rounds
  state.profileAdaptEnabled.value = data.profile_adapt_enabled ?? true
  state.answerDetail.value = (data.answer_detail as 'brief' | 'normal' | 'detailed') || 'normal'
  state.showSteps.value = data.show_steps ?? true
  state.deepMode.value = data.deep_mode ?? false
  state.webSearchEnabled.value = data.web_search_enabled ?? false
  state.documentIds.value = data.document_ids ?? []
  state.messages.value = mapMessages(data)
}

function createState() {
  return {
    sessionNo: ref(''),
    messages: ref<TutorChatMessage[]>([]),
    sessions: ref<TutorSessionData[]>([]),
    sessionsLoading: ref(false),
    streaming: ref(false),
    error: ref<string | null>(null),
    lastMeta: ref<TutorMessageMeta | null>(null),
    profileSummary: ref(''),
    tutorMode: ref('socratic'),
    totalRounds: ref(0),
    profileAdaptEnabled: ref(true),
    answerDetail: ref<'brief' | 'normal' | 'detailed'>('normal'),
    showSteps: ref(true),
    deepMode: ref(false),
    webSearchEnabled: ref(false),
    documentIds: ref<string[]>([]),
    documents: ref<TutorDocumentItem[]>([]),
    uploadProgress: ref(0),
    uploading: ref(false),
    uploadError: ref<string | null>(null),
    failedUploadFile: ref<File | null>(null),
    pendingOutline: ref<TutorOutlineItem[] | null>(null),
    outlineTopic: ref(''),
    genProgress: ref(''),
    activeSlides: ref<TutorSlide[]>([]),
    slideIndex: ref(0),
    showSlideDeck: ref(false),
    genPhase: ref<GenPhase>('idle'),
    activeTool: ref<ActiveTool | null>(null),
    toolLoading: ref(false),
    streamAbortController: ref<AbortController | null>(null),
    videoGenerationHandler: ref<((topic: string) => void) | null>(null),
    lastVideoLectureId: ref<string | null>(null),
  }
}

export function useTutorChat() {
  const route = useRoute()
  const state = createState()

  const displayRound = computed(() => Math.max(1, state.totalRounds.value))

  function sessionSettings(): Pick<
    TutorSessionCreateParams,
    'profile_adapt_enabled' | 'answer_detail' | 'show_steps' | 'deep_mode' | 'web_search_enabled' | 'document_ids'
  > {
    return {
      profile_adapt_enabled: state.profileAdaptEnabled.value,
      answer_detail: state.answerDetail.value,
      show_steps: state.showSteps.value,
      deep_mode: state.deepMode.value,
      web_search_enabled: state.webSearchEnabled.value,
      document_ids: state.documentIds.value,
    }
  }

  async function loadSessions() {
    state.sessionsLoading.value = true
    try {
      state.sessions.value = await tutorApi.listSessions()
    } catch {
      state.sessions.value = []
    } finally {
      state.sessionsLoading.value = false
    }
  }

  async function loadDocuments() {
    if (!state.sessionNo.value) {
      state.documents.value = []
      return
    }
    state.documents.value = await tutorApi.listSessionDocuments(state.sessionNo.value)
  }

  async function initSession(topic: string, mode?: string) {
    const data = await tutorApi.createSession({
      topic,
      tutor_mode: mode || state.tutorMode.value,
      resource_id: route.query.resource_id ? Number(route.query.resource_id) : undefined,
      node_id: route.query.node_id ? Number(route.query.node_id) : undefined,
      path_id: route.query.path_id ? Number(route.query.path_id) : undefined,
      ...sessionSettings(),
    })
    applySessionState(data, state)
    await loadDocuments()
    await loadSessions()
    return data
  }

  async function bindDocuments() {
    if (!state.sessionNo.value) return
    await tutorApi.bindDocuments(state.sessionNo.value, state.documentIds.value)
  }

  async function syncSettings() {
    if (!state.sessionNo.value) return
    await tutorApi.updateSettings(state.sessionNo.value, {
      tutor_mode: state.tutorMode.value,
      deep_mode: state.deepMode.value,
      web_search_enabled: state.webSearchEnabled.value,
      answer_detail: state.answerDetail.value,
      show_steps: state.showSteps.value,
      profile_adapt_enabled: state.profileAdaptEnabled.value,
      document_ids: state.documentIds.value,
    })
  }

  async function uploadDocument(file: File) {
    state.uploadError.value = null
    state.failedUploadFile.value = null
    if (!state.sessionNo.value) {
      await initSession('文档问答', state.tutorMode.value)
    }
    state.uploading.value = true
    state.uploadProgress.value = 0
    try {
      const doc = await tutorApi.uploadDocument(state.sessionNo.value, file, (pct) => {
        state.uploadProgress.value = pct
      })
      if (!state.documentIds.value.includes(doc.doc_id)) {
        state.documentIds.value.push(doc.doc_id)
      }
      await loadDocuments()
      return doc
    } catch (e) {
      state.uploadError.value = (e as Error).message || '上传失败'
      state.failedUploadFile.value = file
      throw e
    } finally {
      state.uploading.value = false
      setTimeout(() => { state.uploadProgress.value = 0 }, 800)
    }
  }

  async function retryUpload() {
    if (state.failedUploadFile.value) {
      await uploadDocument(state.failedUploadFile.value)
    }
  }

  async function removeDocument(docId: string) {
    if (!state.sessionNo.value) return
    await tutorApi.deleteDocument(state.sessionNo.value, docId)
    state.documentIds.value = state.documentIds.value.filter((id) => id !== docId)
    state.documents.value = state.documents.value.filter((d) => d.doc_id !== docId)
  }

  function toggleDocument(docId: string) {
    const ids = state.documentIds.value
    if (ids.includes(docId)) {
      state.documentIds.value = ids.filter((id) => id !== docId)
    } else {
      state.documentIds.value = [...ids, docId]
    }
    if (state.sessionNo.value) bindDocuments()
  }

  function clearActiveTools() {
    state.activeTool.value = null
    state.toolLoading.value = false
  }

  function patchMessage(id: string, patch: Partial<TutorChatMessage>) {
    const idx = state.messages.value.findIndex((m) => m.id === id)
    if (idx < 0) return
    state.messages.value[idx] = { ...state.messages.value[idx], ...patch }
  }

  function getMessage(id: string): TutorChatMessage | undefined {
    return state.messages.value.find((m) => m.id === id)
  }

  function stopStream() {
    state.streamAbortController.value?.abort()
    const last = [...state.messages.value].reverse().find((m) => m.role === 'assistant' && m.streaming)
    if (last) {
      patchMessage(last.id, {
        streaming: false,
        progressMessage: undefined,
        content: last.content || '（已停止生成）',
      })
    }
    state.streaming.value = false
    state.toolLoading.value = false
    state.genProgress.value = ''
    state.genPhase.value = 'idle'
    clearActiveTools()
  }

  async function runStream(
    content: string,
    assistant: TutorChatMessage,
    userMsg: TutorChatMessage | null,
    options?: Parameters<typeof tutorApi.streamMessage>[3],
  ) {
    const assistantId = assistant.id
    const abortController = new AbortController()
    state.streamAbortController.value = abortController
    const thinkSplitter = createThinkStreamSplitter()
    patchMessage(assistantId, { thinkingContent: '', thinkingDurationSec: undefined })
    let hasRemoteThinking = false

    function syncAnswerContent() {
      const current = getMessage(assistantId)
      if (!current) return
      patchMessage(assistantId, {
        content: sanitizeAnswerContent(current.content || '', current.thinkingContent || ''),
      })
    }

    function applyThinkChunk(text: string) {
      if (!text) return
      hasRemoteThinking = true
      const current = getMessage(assistantId)
      if (!current) return
      patchMessage(assistantId, {
        thinkingContent: (current.thinkingContent || '') + text.replace(/\x01T\x01/g, ''),
      })
    }

    function applyContentChunk(text: string) {
      if (!text) return
      const cleaned = text.replace(/\x01C\x01/g, '').replace(/\x01T\x01/g, '')
      const current = getMessage(assistantId)
      if (!current) return

      if (hasRemoteThinking) {
        const main = stripThinkTags(cleaned)
        if (!main) return
        patchMessage(assistantId, {
          progressMessage: undefined,
          content: appendStreamContent(current.content || '', main),
        })
        syncAnswerContent()
        return
      }

      const { thinking, content: main, thinkEnded } = thinkSplitter.feed(cleaned)
      const patch: Partial<TutorChatMessage> = {}
      if (thinking) {
        patch.thinkingContent = (current.thinkingContent || '') + thinking
      }
      if (main) {
        patch.progressMessage = undefined
        patch.content = appendStreamContent(current.content || '', main)
      }
      if (thinkEnded) {
        patch.thinkingDurationSec = thinkSplitter.getThinkDurationSec() ?? undefined
      }
      if (Object.keys(patch).length) {
        patchMessage(assistantId, patch)
        if (patch.content !== undefined || thinkEnded) syncAnswerContent()
      }
    }

    function flushRemainingStream() {
      const current = getMessage(assistantId)
      if (!current) return
      if (hasRemoteThinking) {
        syncAnswerContent()
        return
      }
      const tail = thinkSplitter.flush()
      const patch: Partial<TutorChatMessage> = {}
      if (tail.thinking) {
        patch.thinkingContent = (current.thinkingContent || '') + tail.thinking
      }
      if (tail.content) {
        patch.content = appendStreamContent(current.content || '', tail.content)
      }
      if (Object.keys(patch).length) {
        patchMessage(assistantId, patch)
        syncAnswerContent()
      }
    }

    try {
      await tutorApi.streamMessage(
        state.sessionNo.value,
        content,
        {
          onMeta: (meta) => {
            state.lastMeta.value = meta
            patchMessage(assistantId, { meta })
          },
          onProgress: (p) => {
            state.genProgress.value = p.message || ''
            patchMessage(assistantId, { progressMessage: p.message })
            if (p.phase === 'outline') state.genPhase.value = 'outline'
          },
          onThinkChunk: applyThinkChunk,
          onOutline: (data) => {
            state.pendingOutline.value = data.outline
            state.outlineTopic.value = data.topic || content
            state.genPhase.value = 'confirm'
            patchMessage(assistantId, {
              content: '已生成课程大纲，请在下方预览、编辑节点后点击「确认生成」。',
              meta: {
                ...(getMessage(assistantId)?.meta || {
                  knowledge_points: [],
                  related_resources: [],
                  hint_level: 0,
                  is_exercise: false,
                }),
                message_type: 'outline',
                strategy_used: 'lecture_outline',
              } as TutorMessageMeta,
            })
          },
          onSlides: (data) => {
            const slides = (data.slides || []) as TutorSlide[]
            state.activeSlides.value = [...state.activeSlides.value, ...slides]
            patchMessage(assistantId, { slides: state.activeSlides.value })
          },
          onModuleStart: (data) => {
            state.genPhase.value = 'modules'
            const progressMessage = `正在生成：${data.title}（${data.phase}）…`
            state.genProgress.value = progressMessage
            patchMessage(assistantId, { progressMessage })
          },
          onChunk: applyContentChunk,
          onDone: (data) => {
            state.lastMeta.value = data.meta
            const current = getMessage(assistantId)
            const patch: Partial<TutorChatMessage> = {
              meta: data.meta,
              round_no: data.round_no,
              progressMessage: undefined,
            }
            if (data.content) {
              patch.content = data.content
            } else {
              flushRemainingStream()
            }
            if (data.meta.slides?.length) {
              patch.slides = data.meta.slides
              state.activeSlides.value = data.meta.slides
            }
            if (!patch.content && current) {
              patch.content = current.content
            }
            if (!patch.thinkingDurationSec && current?.thinkingContent) {
              patch.thinkingDurationSec = thinkSplitter.getThinkDurationSec() ?? undefined
            }
            patchMessage(assistantId, patch)
            if (data.content) {
              syncAnswerContent()
            }
            state.totalRounds.value = data.round_no
            if (userMsg) patchMessage(userMsg.id, { round_no: data.round_no })
            const isOutlineOnly = data.meta?.message_type === 'outline'
            if (!isOutlineOnly) {
              state.pendingOutline.value = null
            }
            state.genProgress.value = ''
            state.genPhase.value = (patch.slides?.length || data.meta.slides?.length)
              ? 'done'
              : isOutlineOnly
                ? 'confirm'
                : 'idle'
            if (patch.slides?.length || data.meta.slides?.length) state.showSlideDeck.value = true
          },
        },
        {
          web_search_enabled: state.webSearchEnabled.value,
          deep_mode: state.deepMode.value,
          signal: abortController.signal,
          ...options,
        },
      )
    } finally {
      if (state.streamAbortController.value === abortController) {
        state.streamAbortController.value = null
      }
    }
  }

  async function runToolAction(content: string, tool: ActiveTool) {
    if (!state.sessionNo.value) {
      await initSession(content.slice(0, 100), state.tutorMode.value)
    }

    const userMsg: TutorChatMessage = {
      id: `msg-${++msgCounter}`,
      role: 'user',
      content,
      round_no: state.totalRounds.value + 1,
    }
    state.messages.value.push(userMsg)

    // 视频生成：打开沉浸式弹窗，不在聊天区内联流式输出（参考 OpenMAIC generation-preview）
    if (tool === 'video' && state.videoGenerationHandler.value) {
      state.videoGenerationHandler.value(content)
      clearActiveTools()
      return
    }

    const assistant: TutorChatMessage = {
      id: `msg-${++msgCounter}`,
      role: 'assistant',
      content: '',
      streaming: true,
      round_no: state.totalRounds.value + 1,
    }
    state.messages.value.push(assistant)
    state.streaming.value = true
    state.toolLoading.value = true

    try {
      if (tool === 'video') {
        state.genPhase.value = 'outline'
        await runStream(content, assistant, userMsg, { force_lecture: true })
        return
      }

      const lastAssistant = [...state.messages.value]
        .reverse()
        .find((m) => m.role === 'assistant' && m.content && m.id !== assistant.id)
      const sourceText = lastAssistant?.content

      const payload = await tutorApi.multimodal(
        state.sessionNo.value,
        tool,
        tool === 'tts' ? (sourceText || content) : content,
        tool === 'tts' ? sourceText : undefined,
      )
      const data = payload.payload
      if (tool === 'image') {
        const title = String(data.title || '思维导图')
        patchMessage(assistant.id, {
          content: `## ${title}`,
          multimodal: data,
        })
      } else {
        patchMessage(assistant.id, {
          content: '🔊 语音合成就绪，可在消息中播放。',
          multimodal: data,
        })
      }
      patchMessage(assistant.id, {
        meta: {
          knowledge_points: [],
          related_resources: [],
          message_type: tool,
          strategy_used: `multimodal_${tool}`,
          hint_level: 0,
          is_exercise: false,
          multimodal: data,
          disclaimer: data.disclaimer ? String(data.disclaimer) : undefined,
        },
      })
      state.totalRounds.value += 1
      patchMessage(userMsg.id, { round_no: state.totalRounds.value })
      patchMessage(assistant.id, { round_no: state.totalRounds.value })
    } catch (e) {
      const err = e as Error
      if (err.name === 'AbortError') {
        const cur = getMessage(assistant.id)
        patchMessage(assistant.id, { content: cur?.content || '（已停止生成）' })
      } else {
        state.error.value = err.message
        const cur = getMessage(assistant.id)
        patchMessage(assistant.id, {
          failed: true,
          content: cur?.content || '抱歉，生成失败。',
        })
      }
    } finally {
      patchMessage(assistant.id, { streaming: false, progressMessage: undefined })
      state.streaming.value = false
      state.toolLoading.value = false
      clearActiveTools()
      await loadSessions()
    }
  }

  async function send(content: string, requestFullAnswer = false) {
    if (!content.trim() || state.streaming.value) return

    // 用户直接说「生成xx思维导图」时，自动走思维导图工具，避免只返回文字大纲
    let tool = state.activeTool.value
    if (!tool && /思维导图|知识图谱|mind\s*map|知识树|结构图/i.test(content)) {
      tool = 'image'
    }
    if (tool) {
      await runToolAction(content, tool)
      return
    }

    if (!state.sessionNo.value) {
      await initSession(content.slice(0, 100), state.tutorMode.value)
    } else {
      await syncSettings()
    }
    state.error.value = null
    state.activeSlides.value = []
    state.showSlideDeck.value = false
    state.genPhase.value = 'idle'

    const userMsg: TutorChatMessage = {
      id: `msg-${++msgCounter}`,
      role: 'user',
      content,
      round_no: state.totalRounds.value + 1,
    }
    state.messages.value.push(userMsg)

    const assistant: TutorChatMessage = {
      id: `msg-${++msgCounter}`,
      role: 'assistant',
      content: '',
      streaming: true,
      round_no: state.totalRounds.value + 1,
    }
    state.messages.value.push(assistant)
    state.streaming.value = true

    try {
      await runStream(content, assistant, userMsg, {
        request_full_answer: requestFullAnswer,
        force_lecture: false,
      })
    } catch (e) {
      const err = e as Error
      if (err.name === 'AbortError') {
        const cur = getMessage(assistant.id)
        patchMessage(assistant.id, { content: cur?.content || '（已停止生成）' })
      } else {
        state.error.value = err.message
        const cur = getMessage(assistant.id)
        patchMessage(assistant.id, {
          failed: true,
          content: cur?.content || `抱歉，回答生成失败：${err.message}`,
        })
      }
    } finally {
      patchMessage(assistant.id, { streaming: false, progressMessage: undefined })
      state.streaming.value = false
      state.genProgress.value = ''
      clearActiveTools()
      await loadSessions()
    }
  }

  async function confirmOutline(outline: TutorOutlineItem[]) {
    if (!state.sessionNo.value || state.streaming.value) return
    const topic = state.outlineTopic.value || '确认生成讲解'
    state.pendingOutline.value = null

    const assistant: TutorChatMessage = {
      id: `msg-${++msgCounter}`,
      role: 'assistant',
      content: '',
      streaming: true,
      progressMessage: '正在分模块生成讲解内容…',
    }
    state.messages.value.push(assistant)
    state.streaming.value = true
    state.activeSlides.value = []
    state.genPhase.value = 'modules'

    try {
      await runStream(topic, assistant, null, { confirmed_outline: outline })
    } catch (e) {
      state.error.value = (e as Error).message
      patchMessage(assistant.id, { failed: true })
    } finally {
      patchMessage(assistant.id, { streaming: false })
      state.streaming.value = false
      clearActiveTools()
    }
  }

  async function generateMultimodal(action: 'image' | 'video' | 'tts', prompt: string, sourceText?: string) {
    if (!state.sessionNo.value) {
      await initSession(prompt.slice(0, 80), state.tutorMode.value)
    }
    const payload = await tutorApi.multimodal(state.sessionNo.value, action, prompt, sourceText)
    const msg: TutorChatMessage = {
      id: `msg-${++msgCounter}`,
      role: 'assistant',
      content: action === 'tts' ? `🔊 语音合成就绪` : `🎨 ${action === 'image' ? '图像' : '视频'}生成完成`,
      multimodal: payload.payload,
      meta: {
        knowledge_points: [],
        related_resources: [],
        message_type: action,
        strategy_used: `multimodal_${action}`,
        hint_level: 0,
        is_exercise: false,
        multimodal: payload.payload,
        disclaimer: payload.payload.disclaimer ? String(payload.payload.disclaimer) : undefined,
      },
    }
    state.messages.value.push(msg)
    return payload.payload
  }

  async function retryLast() {
    const msgs = state.messages.value
    const lastAssistant = [...msgs].reverse().find((m) => m.role === 'assistant' && m.failed)
    if (!lastAssistant || state.streaming.value) return
    const idx = msgs.indexOf(lastAssistant)
    const lastUser = msgs.slice(0, idx).reverse().find((m) => m.role === 'user')
    if (!lastUser) return

    state.messages.value = msgs.filter((m) => m.id !== lastAssistant.id)
    state.error.value = null

    const assistant: TutorChatMessage = {
      id: `msg-${++msgCounter}`,
      role: 'assistant',
      content: '',
      streaming: true,
      round_no: lastUser.round_no,
    }
    state.messages.value.push(assistant)
    state.streaming.value = true

    try {
      await runStream(lastUser.content, assistant, lastUser, { retry_assistant: true })
    } catch (e) {
      state.error.value = (e as Error).message
      const cur = getMessage(assistant.id)
      patchMessage(assistant.id, {
        failed: true,
        content: cur?.content || `抱歉，回答生成失败：${(e as Error).message}`,
      })
    } finally {
      patchMessage(assistant.id, { streaming: false })
      state.streaming.value = false
      clearActiveTools()
      await loadSessions()
    }
  }

  async function loadSession(no: string) {
    if (state.streaming.value) return
    const data = await tutorApi.getSession(no)
    applySessionState(data, state)
    state.messages.value = restoreLectureMessages(state.messages.value, no)
    await loadDocuments()
    const slides = restoreSlidesFromMessages(state.messages.value)
    if (slides.length) {
      state.activeSlides.value = slides
      state.showSlideDeck.value = true
      state.genPhase.value = 'done'
    } else {
      state.showSlideDeck.value = false
      state.genPhase.value = 'idle'
    }
    state.error.value = null
    state.lastMeta.value = null
    state.pendingOutline.value = null
  }

  async function deleteSession(no: string) {
    await tutorApi.deleteSession(no)
    state.sessions.value = state.sessions.value.filter((s) => s.session_no !== no)
    if (state.sessionNo.value === no) newSession()
  }

  function newSession() {
    stopStream()
    state.sessionNo.value = ''
    state.messages.value = []
    state.lastMeta.value = null
    state.error.value = null
    state.totalRounds.value = 0
    state.profileSummary.value = ''
    state.pendingOutline.value = null
    state.activeSlides.value = []
    state.showSlideDeck.value = false
    state.genProgress.value = ''
    state.genPhase.value = 'idle'
    state.documentIds.value = []
    state.documents.value = []
    state.uploadError.value = null
    state.failedUploadFile.value = null
    clearActiveTools()
  }

  async function startLecture(topic: string, sourceText?: string) {
    if (!state.sessionNo.value) {
      await initSession(topic.slice(0, 100), state.tutorMode.value)
    }
    return tutorApi.generateLecture(state.sessionNo.value, topic, sourceText)
  }

  function registerVideoGeneration(handler: ((topic: string) => void) | null) {
    state.videoGenerationHandler.value = handler
  }

  function appendAssistantNote(
    content: string,
    lecture?: { lecture_id: string; topic: string; slide_count: number; resource_id?: number },
  ) {
    const relatedResources: TutorRelatedResource[] = lecture?.resource_id
      ? [
          {
            resource_id: lecture.resource_id,
            title: `${lecture.topic} - AI视频讲解`,
            type_code: 'video',
            type_name: '教学视频',
            topic: lecture.topic,
          },
        ]
      : []

    const meta: TutorMessageMeta | undefined = lecture
      ? {
          knowledge_points: [],
          related_resources: relatedResources,
          message_type: 'video_lecture',
          strategy_used: 'video_lecture',
          hint_level: 0,
          is_exercise: false,
          lecture_id: lecture.lecture_id,
          lecture_topic: lecture.topic,
          lecture_slide_count: lecture.slide_count,
        }
      : undefined

    state.messages.value.push({
      id: `msg-${++msgCounter}`,
      role: 'assistant',
      content,
      round_no: state.totalRounds.value,
      meta,
    })

    if (lecture && state.sessionNo.value) {
      saveLectureEntry(state.sessionNo.value, {
        lecture_id: lecture.lecture_id,
        topic: lecture.topic,
        slide_count: lecture.slide_count,
        created_at: new Date().toISOString(),
      })
      state.lastVideoLectureId.value = lecture.lecture_id
    }
  }

  onMounted(async () => {
    await loadSessions()
    const q = route.query.session_no as string | undefined
    if (q) await loadSession(q)
  })

  return {
    ...state,
    displayRound,
    initSession,
    send,
    stopStream,
    clearActiveTools,
    confirmOutline,
    generateMultimodal,
    loadSession,
    loadSessions,
    loadDocuments,
    uploadDocument,
    retryUpload,
    removeDocument,
    toggleDocument,
    bindDocuments,
    syncSettings,
    deleteSession,
    newSession,
    retryLast,
    sessionSettings,
    startLecture,
    registerVideoGeneration,
    appendAssistantNote,
  }
}
