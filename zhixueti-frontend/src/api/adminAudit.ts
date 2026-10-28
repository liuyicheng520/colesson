import { request } from './request'

export interface AuditOverviewStats {
  operation_total: number
  operation_failed_24h: number
  exception_total: number
  exception_unresolved: number
  exception_24h: number
  log_retention_days: number
}

export interface OperationLogItem {
  id: number
  user_id: number | null
  username: string | null
  module: string
  action: string
  target_type: string | null
  target_id: number | null
  request_method: string | null
  request_url: string | null
  response_code: number | null
  ip_address: string | null
  duration_ms: number | null
  status: number
  error_message: string | null
  created_at: string
}

export interface ExceptionLogItem {
  id: number
  error_code: number | null
  error_type: string
  message: string
  request_method: string | null
  request_url: string | null
  user_id: number | null
  username: string | null
  ip_address: string | null
  severity: string
  is_resolved: number
  created_at: string
}

export interface ExceptionTrendItem {
  date: string
  count: number
}

export const adminAuditApi = {
  overview() {
    return request<AuditOverviewStats>({ method: 'GET', url: '/admin/audit/overview' })
  },

  listOperationLogs(params?: {
    module?: string
    action?: string
    status?: number
    user_id?: number
    keyword?: string
    date_from?: string
    date_to?: string
    page?: number
    page_size?: number
  }) {
    return request<{ items: OperationLogItem[]; total: number; page: number; page_size: number }>({
      method: 'GET',
      url: '/admin/audit/operation-logs',
      params,
    })
  },

  listExceptionLogs(params?: {
    severity?: string
    is_resolved?: number
    keyword?: string
    date_from?: string
    date_to?: string
    page?: number
    page_size?: number
  }) {
    return request<{ items: ExceptionLogItem[]; total: number; page: number; page_size: number }>({
      method: 'GET',
      url: '/admin/audit/exception-logs',
      params,
    })
  },

  exceptionTrends(days: 7 | 30 = 7) {
    return request<ExceptionTrendItem[]>({ method: 'GET', url: '/admin/audit/exception-trends', params: { days } })
  },

  resolveException(id: number, is_resolved: number) {
    return request<ExceptionLogItem>({
      method: 'PUT',
      url: `/admin/audit/exception-logs/${id}`,
      data: { is_resolved },
    })
  },

  purgeLogs() {
    return request<{ operation_deleted: number; exception_deleted: number; retention_days: number }>({
      method: 'POST',
      url: '/admin/audit/purge',
    })
  },
}
