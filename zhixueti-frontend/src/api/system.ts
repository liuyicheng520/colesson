import { request } from './request'
import type { AnnouncementItem } from './adminOps'

export interface PublicSystemInfo {
  site_name: string
  site_logo_url: string
  site_icp_no: string
  site_footer_text: string
  features: {
    web_search: boolean
    deep_mode: boolean
    image_gen: boolean
    video_lecture: boolean
    voice_input: boolean
  }
  announcements: AnnouncementItem[]
}

export interface StudentFeedbackItem {
  id: number
  category: string
  title: string
  content: string
  status: number
  admin_reply: string | null
  created_at: string
}

export interface LoginLogItem {
  id: number
  ip_address: string | null
  user_agent: string | null
  created_at: string
  success: boolean
}

export const systemApi = {
  publicInfo() {
    return request<PublicSystemInfo>({ method: 'GET', url: '/system/public' })
  },

  submitFeedback(data: {
    category?: string
    title: string
    content: string
    screenshot_url?: string
  }) {
    return request<{ id: number; status: number }>({ method: 'POST', url: '/system/feedback', data })
  },

  listMyFeedback(params?: { page?: number; page_size?: number }) {
    return request<{ items: StudentFeedbackItem[]; total: number }>({
      method: 'GET',
      url: '/system/feedback/mine',
      params,
    })
  },

  listLoginLogs() {
    return request<LoginLogItem[]>({ method: 'GET', url: '/system/login-logs' })
  },

  uploadFeedbackScreenshot(file: File) {
    const form = new FormData()
    form.append('file', file)
    return request<{ url: string }>({
      method: 'POST',
      url: '/system/feedback/screenshot',
      data: form,
    })
  },
}
