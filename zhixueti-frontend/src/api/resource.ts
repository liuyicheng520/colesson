import { request, API_TIMEOUT } from './request'
import type { PageData, ResourceItem, ResourceTypeCode } from '@/types'

export const resourceApi = {
  /** 个人资源中心 — 后端强制 user_id=当前用户 */
  list(params: {
    type_code?: string
    topic?: string
    status?: number
    page?: number
    page_size?: number
  }) {
    return request<PageData<ResourceItem>>({ method: 'GET', url: '/resources', params })
  },

  get(id: number) {
    return request<ResourceItem>({ method: 'GET', url: `/resources/${id}` })
  },

  /** 资源广场 — 仅 status=2 已发布公开资源 */
  listPublic(params: {
    type_code?: string
    topic?: string
    page?: number
    page_size?: number
  }) {
    return request<PageData<ResourceItem>>({ method: 'GET', url: '/resources/public', params })
  },

  getPublic(id: number) {
    return request<ResourceItem>({ method: 'GET', url: `/resources/public/${id}` })
  },

  generate(data: {
    topic: string
    goal?: string
    resource_types?: ResourceTypeCode[]
    difficulty?: number
    node_id?: number
    ignore_profile?: boolean
    supplement?: string
    use_scene?: string
    content_focus?: string[]
    content_length?: string
    special_requirements?: string
  }) {
    return request<{ task_no: string; resource_ids: number[] }>({
      method: 'POST',
      url: '/resources/generate',
      data,
      timeout: API_TIMEOUT.llm,
    })
  },
}
