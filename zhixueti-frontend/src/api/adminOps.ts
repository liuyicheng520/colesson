import { request } from './request'

export interface AdminOverviewStats {
  total_users: number
  dau_users: number
  total_study_hours: number
  qa_total: number
  multimodal_total: number
}

export interface AdminTrendStats {
  days: number
  dates: string[]
  registrations: number[]
  qa_counts: number[]
  lecture_counts: number[]
}

export interface FeatureUsageItem {
  name: string
  value: number
}

export interface TopTopicItem {
  topic: string
  count: number
}

export interface SystemSettings {
  llm_default_provider: string
  llm_fallback_provider: string
  content_safety_enabled: boolean
  profile_min_completeness: number
  rate_limit_requests: number
  tutor_max_tokens: number
  tutor_stream_timeout_sec: number
  feature_web_search: boolean
  feature_deep_mode: boolean
  feature_image_gen: boolean
  feature_video_lecture: boolean
  feature_voice_input: boolean
  site_name: string
  site_logo_url: string
  site_icp_no: string
  site_footer_text: string
  has_qwen_key: boolean
  has_deepseek_key: boolean
  has_spark_key: boolean
  has_serper_key: boolean
}

export interface AnnouncementItem {
  id: number
  title: string
  content: string
  status: number
  priority: number
  published_at: string | null
  created_at: string
}

export interface FeedbackItem {
  id: number
  user_id: number
  username: string | null
  category: string
  title: string
  content: string
  status: number
  admin_reply: string | null
  created_at: string
}

export const adminOpsApi = {
  overview() {
    return request<AdminOverviewStats>({ method: 'GET', url: '/admin/analytics/overview' })
  },

  trends(days: 7 | 30 = 7) {
    return request<AdminTrendStats>({ method: 'GET', url: '/admin/analytics/trends', params: { days } })
  },

  featureUsage() {
    return request<FeatureUsageItem[]>({ method: 'GET', url: '/admin/analytics/feature-usage' })
  },

  topTopics() {
    return request<TopTopicItem[]>({ method: 'GET', url: '/admin/analytics/top-topics' })
  },

  getSystemSettings() {
    return request<SystemSettings>({ method: 'GET', url: '/admin/settings/system' })
  },

  updateSystemSettings(data: Partial<SystemSettings> & Record<string, unknown>) {
    return request<SystemSettings>({ method: 'PUT', url: '/admin/settings/system', data })
  },

  listAnnouncements() {
    return request<AnnouncementItem[]>({ method: 'GET', url: '/admin/announcements' })
  },

  createAnnouncement(data: { title: string; content: string; status?: number; priority?: number }) {
    return request<AnnouncementItem>({ method: 'POST', url: '/admin/announcements', data })
  },

  updateAnnouncement(id: number, data: Partial<AnnouncementItem>) {
    return request<AnnouncementItem>({ method: 'PUT', url: `/admin/announcements/${id}`, data })
  },

  deleteAnnouncement(id: number) {
    return request({ method: 'DELETE', url: `/admin/announcements/${id}` })
  },

  listFeedback(params?: { status?: number; page?: number; page_size?: number }) {
    return request<{ items: FeedbackItem[]; total: number; page: number; page_size: number }>({
      method: 'GET',
      url: '/admin/feedback',
      params,
    })
  },

  replyFeedback(id: number, data: { status: number; admin_reply?: string }) {
    return request<FeedbackItem>({ method: 'PUT', url: `/admin/feedback/${id}`, data })
  },
}
