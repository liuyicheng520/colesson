import { request } from './request'
import type { LearningStats } from '@/types'

export const behaviorApi = {
  getStats(params?: { include_trend_30d?: boolean }) {
    return request<LearningStats>({ method: 'GET', url: '/behavior/stats', params })
  },

  startSession(data: {
    path_id?: number
    node_id?: number
    session_type?: string
    device_type?: string
  }) {
    return request<{ session_id: number }>({ method: 'POST', url: '/behavior/sessions/start', data })
  },

  batchEvents(data: {
    session_id?: number
    events: Array<{
      event_type: string
      event_target?: string
      target_id?: number
      event_data?: Record<string, unknown>
      page_url?: string
    }>
  }) {
    return request<{ accepted: number }>({ method: 'POST', url: '/behavior/events/batch', data })
  },

  endSession(sessionId: number) {
    return request<{ session_id: number }>({ method: 'POST', url: `/behavior/sessions/${sessionId}/end` })
  },
}
