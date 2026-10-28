import { request } from './request'

export interface AuditItem {
  id: number
  audit_no: string
  target_type: string
  target_id: number
  content_snapshot: string | null
  audit_type: string
  audit_result: number
  risk_level: number
  risk_labels: string[] | null
  risk_detail: Record<string, unknown> | null
  auditor_id: number | null
  audit_note: string | null
  created_at: string
}

export interface LlmLogItem {
  id: number
  user_id: number | null
  task_id: number | null
  provider: string
  model_name: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  latency_ms: number | null
  is_stream: number
  status: number
  request_hash: string | null
  prompt_preview: string | null
  response_preview: string | null
  validation: Record<string, unknown> | null
  created_at: string
}

const AUDIT_RESULT_MAP: Record<number, string> = {
  0: '拒绝',
  1: '通过',
  2: '待复核',
}

export { AUDIT_RESULT_MAP }

export const securityApi = {
  listAudits(params?: { audit_result?: number; target_type?: string; page?: number; page_size?: number }) {
    return request<{ items: AuditItem[]; total: number; page: number; page_size: number }>({
      method: 'GET',
      url: '/security/audits',
      params,
    })
  },

  reviewAudit(auditId: number, data: { audit_result: number; audit_note?: string }) {
    return request<AuditItem>({ method: 'PUT', url: `/security/audits/${auditId}/review`, data })
  },

  takedown(data: { target_type: string; target_id: number; reason: string }) {
    return request<{ target_type: string; target_id: number; status?: string }>({
      method: 'POST',
      url: '/security/takedown',
      data,
    })
  },

  listSensitiveWords() {
    return request<{ id: number; word: string; word_type: string; category: string; status: number }[]>({
      method: 'GET',
      url: '/security/sensitive-words',
    })
  },

  addSensitiveWord(data: { word: string; word_type?: string; category?: string }) {
    return request({ method: 'POST', url: '/security/sensitive-words', data })
  },

  listLlmLogs(params?: { page?: number; page_size?: number }) {
    return request<{ items: LlmLogItem[]; total: number }>({
      method: 'GET',
      url: '/security/llm-logs',
      params,
    })
  },
}
