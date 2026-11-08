import { behaviorApi } from '@/api/behavior'

export interface StudyEvent {
  event_type: string
  event_target?: string
  target_id?: number
  event_data?: Record<string, unknown>
  page_url?: string
}

/**
 * 学习会话追踪：进入学习面时开启会话，离开/完成时结束。
 * 服务端按 started_at/ended_at 计算真实学习时长，喂给学习数据看板。
 */
export function useStudySession() {
  let sessionId: number | null = null
  let ending = false

  async function start(ctx: { path_id?: number; node_id?: number; session_type?: string }) {
    if (sessionId !== null) return // 已有进行中的会话
    try {
      const res = await behaviorApi.startSession({
        path_id: ctx.path_id,
        node_id: ctx.node_id,
        session_type: ctx.session_type || 'path_study',
        device_type: 'web',
      })
      sessionId = res.session_id
    } catch {
      /* 上报失败静默：埋点不干扰学习 */
    }
  }

  async function track(event: StudyEvent) {
    if (sessionId === null) return
    try {
      await behaviorApi.batchEvents({
        session_id: sessionId,
        events: [{ page_url: location.pathname, ...event }],
      })
    } catch {
      /* ignore */
    }
  }

  async function end() {
    if (sessionId === null || ending) return
    ending = true
    const id = sessionId
    sessionId = null
    try {
      await behaviorApi.endSession(id)
    } catch {
      /* ignore */
    } finally {
      ending = false
    }
  }

  return { start, track, end, isActive: () => sessionId !== null }
}
