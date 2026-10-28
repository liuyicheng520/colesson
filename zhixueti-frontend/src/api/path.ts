import { request, API_TIMEOUT } from './request'
import type { PathData } from '@/types'

export interface PathSummary {
  id: number
  path_no: string
  title: string
  goal: string
  path_version: number
  total_nodes: number
  estimated_hours: number
  status: number
  progress_rate: number
  path_mode?: 'profile' | 'standard'
  weak_focus?: string[]
  adaptive_node_count?: number
  created_at: string
  nodes?: PathData['nodes']
}

export const pathApi = {
  plan(data: {
    goal: string
    domain?: string
    title?: string
    ignore_profile?: boolean
    supplement?: string
    adaptive?: boolean
  }) {
    return request<PathData>({ method: 'POST', url: '/paths/plan', data, timeout: API_TIMEOUT.llm })
  },

  list() {
    return request<PathSummary[]>({ method: 'GET', url: '/paths' })
  },

  get(id: number) {
    return request<PathData>({ method: 'GET', url: `/paths/${id}` })
  },

  updateNodeProgress(nodeId: number, data: {
    status: number
    study_duration_sec?: number
    mastery_score?: number
    resource_id?: number
    mark_resource_done?: boolean
  }) {
    return request<PathData>({
      method: 'PUT',
      url: `/paths/nodes/${nodeId}/progress`,
      data,
    })
  },

  replan(pathId: number, data: { trigger_type?: string; reason?: string } = {}) {
    return request<PathData>({
      method: 'POST',
      url: `/paths/${pathId}/replan`,
      data,
    })
  },

  pushResources(nodeId: number, resourceIds: number[], resourceRole = 'primary') {
    return request<{ node_id: number; resource_ids: number[] }>({
      method: 'POST',
      url: `/paths/nodes/${nodeId}/resources`,
      data: { resource_ids: resourceIds, resource_role: resourceRole },
    })
  },
}
