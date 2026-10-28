import { request } from './request'
import type { PageData } from '@/types'

export interface AdminResourceItem {
  id: number
  resource_no: string
  user_id: number
  username: string | null
  type_code: string
  type_name: string
  title: string
  topic: string
  difficulty: number
  status: number
  fact_check_status: number
  created_at: string
  published_at: string | null
}

export interface AdminProfileDimension {
  id: number
  dimension_code: string
  dimension_name: string
  dimension_desc: string | null
  collect_method: string
  weight: number
  sort_order: number
  is_required: number
  status: number
  guide_questions: string[]
  tags: string[]
}

export interface AdminProfileTag {
  code: string
  label: string
  category: string
  status: number
}

export interface AdminKnowledgePoint {
  id: number
  point_code: string
  point_name: string
  domain: string
  difficulty: number
  estimated_min: number
  description: string | null
  prerequisite_ids: number[] | null
  status: number
}

export interface AdminPathItem {
  id: number
  path_no: string
  user_id: number
  username: string | null
  title: string
  goal: string
  total_nodes: number
  status: number
  created_at: string
}

export interface AdminPathDetail extends AdminPathItem {
  nodes: Array<Record<string, unknown>>
  edges: Array<Record<string, unknown>>
}

export interface AdminLectureItem {
  session_id: number
  session_no: string
  user_id: number
  username: string | null
  lecture_id: string
  title: string
  topic: string | null
  slide_count: number
  created_at: string | null
}

export interface AdminImageItem {
  session_id: number
  session_no: string
  user_id: number
  username: string | null
  round_no: string
  title: string
  caption: string | null
  created_at: string | null
}

export interface AdminDocumentItem {
  doc_id: string
  user_id: number
  username: string | null
  session_no: string | null
  filename: string
  page_count: number
  audit_status: number
  file_size: number | null
  uploaded_at: string | null
}

export interface AdminDocumentSettings {
  audit_enabled: boolean
  max_file_mb: number
  allowed_extensions: string[]
}

export interface AdminDocumentPreview {
  doc_id: string
  user_id: number
  filename: string
  page_count: number
  pages: Array<{ page?: number; text?: string }>
  full_text: string
  truncated: boolean
}

export interface AdminLecturePreview {
  session_id: number
  lecture_id: string
  title: string
  topic: string | null
  slides: Array<Record<string, unknown>>
  video_url: string | null
  recommendations: string[]
}

export interface AdminResourcePreview {
  id: number
  title: string
  type_code: string
  type_name: string
  status: number
  topic: string
  summary: string | null
  preview_type: string
  content: Record<string, unknown>
}

export const adminContentApi = {
  listResources(params: {
    keyword?: string
    type_code?: string
    status?: number
    user_id?: number
    page?: number
    page_size?: number
  }) {
    return request<PageData<AdminResourceItem>>({ method: 'GET', url: '/admin/resources', params })
  },

  setResourceStatus(id: number, status: number) {
    return request({ method: 'PUT', url: `/admin/resources/${id}/status`, data: { status } })
  },

  batchResourceStatus(ids: number[], status: number) {
    return request({ method: 'POST', url: '/admin/resources/batch-status', data: { ids, status } })
  },

  deleteResource(id: number) {
    return request({ method: 'DELETE', url: `/admin/resources/${id}` })
  },

  exportResources() {
    return request<Record<string, unknown>[]>({ method: 'GET', url: '/admin/resources/export' })
  },

  listDimensions() {
    return request<AdminProfileDimension[]>({ method: 'GET', url: '/admin/profile/dimensions' })
  },

  createDimension(data: Partial<AdminProfileDimension> & { dimension_code: string; dimension_name: string }) {
    return request<AdminProfileDimension>({ method: 'POST', url: '/admin/profile/dimensions', data })
  },

  updateDimension(id: number, data: Partial<AdminProfileDimension>) {
    return request<AdminProfileDimension>({ method: 'PUT', url: `/admin/profile/dimensions/${id}`, data })
  },

  deleteDimension(id: number) {
    return request({ method: 'DELETE', url: `/admin/profile/dimensions/${id}` })
  },

  listTags() {
    return request<AdminProfileTag[]>({ method: 'GET', url: '/admin/profile/tags' })
  },

  upsertTag(data: AdminProfileTag) {
    return request<AdminProfileTag[]>({ method: 'POST', url: '/admin/profile/tags', data })
  },

  deleteTag(code: string) {
    return request<AdminProfileTag[]>({ method: 'DELETE', url: `/admin/profile/tags/${encodeURIComponent(code)}` })
  },

  listPaths(params: { keyword?: string; user_id?: number; page?: number; page_size?: number }) {
    return request<PageData<AdminPathItem>>({ method: 'GET', url: '/admin/paths', params })
  },

  getPath(id: number) {
    return request<AdminPathDetail>({ method: 'GET', url: `/admin/paths/${id}` })
  },

  listKnowledgePoints() {
    return request<AdminKnowledgePoint[]>({ method: 'GET', url: '/admin/knowledge-points' })
  },

  createKnowledgePoint(data: Partial<AdminKnowledgePoint> & { point_code: string; point_name: string }) {
    return request<AdminKnowledgePoint>({ method: 'POST', url: '/admin/knowledge-points', data })
  },

  updateKnowledgePoint(id: number, data: Partial<AdminKnowledgePoint>) {
    return request<AdminKnowledgePoint>({ method: 'PUT', url: `/admin/knowledge-points/${id}`, data })
  },

  deleteKnowledgePoint(id: number) {
    return request({ method: 'DELETE', url: `/admin/knowledge-points/${id}` })
  },

  listLectures(params: { keyword?: string; user_id?: number; page?: number; page_size?: number }) {
    return request<PageData<AdminLectureItem>>({ method: 'GET', url: '/admin/generated/lectures', params })
  },

  deleteLecture(sessionId: number, lectureId: string) {
    return request({ method: 'DELETE', url: `/admin/generated/lectures/${sessionId}/${encodeURIComponent(lectureId)}` })
  },

  listImages(params: { keyword?: string; user_id?: number; page?: number; page_size?: number }) {
    return request<PageData<AdminImageItem>>({ method: 'GET', url: '/admin/generated/images', params })
  },

  deleteImage(sessionId: number, roundNo: string) {
    return request({ method: 'DELETE', url: `/admin/generated/images/${sessionId}/${encodeURIComponent(roundNo)}` })
  },

  listDocuments(params: {
    keyword?: string
    audit_status?: number
    user_id?: number
    page?: number
    page_size?: number
  }) {
    return request<PageData<AdminDocumentItem>>({ method: 'GET', url: '/admin/documents', params })
  },

  auditDocument(userId: number, docId: string, audit_status: number, reason?: string) {
    return request({
      method: 'PUT',
      url: `/admin/documents/${userId}/${encodeURIComponent(docId)}/audit`,
      data: { audit_status, reason },
    })
  },

  batchAuditDocuments(items: { user_id: number; doc_id: string }[], audit_status: number, reason?: string) {
    return request<{ updated: number; audit_status: number }>({
      method: 'POST',
      url: '/admin/documents/batch-audit',
      data: { items, audit_status, reason },
    })
  },

  deleteDocument(userId: number, docId: string) {
    return request({ method: 'DELETE', url: `/admin/documents/${userId}/${encodeURIComponent(docId)}` })
  },

  getDocumentSettings() {
    return request<AdminDocumentSettings>({ method: 'GET', url: '/admin/documents/settings' })
  },

  updateDocumentSettings(data: Partial<AdminDocumentSettings>) {
    return request<AdminDocumentSettings>({ method: 'PUT', url: '/admin/documents/settings', data })
  },

  previewDocument(userId: number, docId: string) {
    return request<AdminDocumentPreview>({
      method: 'GET',
      url: `/admin/documents/${userId}/${encodeURIComponent(docId)}/preview`,
    })
  },

  previewLecture(sessionId: number, lectureId: string) {
    return request<AdminLecturePreview>({
      method: 'GET',
      url: `/admin/generated/lectures/${sessionId}/${encodeURIComponent(lectureId)}/preview`,
    })
  },

  previewResource(resourceId: number) {
    return request<AdminResourcePreview>({
      method: 'GET',
      url: `/admin/resources/${resourceId}/preview`,
    })
  },
}
