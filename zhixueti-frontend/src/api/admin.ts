import { request } from './request'
import type { PageData } from '@/types'

export interface AdminStats {
  user_count: number
  resource_count: number
  task_count: number
  published_count: number
  published_rate: number
}

export interface AdminMenuItem {
  path: string
  title: string
  icon: string
  perm_code: string
  sort?: number
  children?: AdminMenuItem[]
}

export interface AdminMenuConfigItem {
  perm_code: string
  path: string
  title: string
  icon: string
  sort: number
}

export interface AdminMeData {
  permissions: string[]
  menus: AdminMenuItem[]
}

export interface AdminUserListItem {
  id: number
  username: string
  nickname: string
  real_name: string | null
  email: string | null
  student_no: string | null
  major: string | null
  grade: number | null
  user_type: number
  status: number
  roles: string[]
  profile_completeness: number | null
  last_login_at: string | null
  created_at: string
}

export interface AdminUserDetail {
  id: number
  username: string
  nickname: string
  real_name: string | null
  email: string | null
  phone: string | null
  student_no: string | null
  major: string | null
  bio: string | null
  grade: number | null
  user_type: number
  status: number
  roles: string[]
  avatar_url: string | null
  last_login_at: string | null
  last_login_ip: string | null
  created_at: string
  profile: Record<string, unknown> | null
  learning_stats: Record<string, unknown> | null
  recent_tutor_sessions: Array<{
    session_no: string
    topic: string
    total_rounds: number
    status: number
    updated_at: string | null
  }>
}

export const ADMIN_ROLE_OPTIONS = [
  { code: 'ROLE_SUPER_ADMIN', label: '超级管理员' },
  { code: 'ROLE_CONTENT_ADMIN', label: '内容管理员' },
  { code: 'ROLE_OPS_ADMIN', label: '运维管理员' },
] as const

export const adminApi = {
  stats() {
    return request<AdminStats>({ method: 'GET', url: '/admin/stats' })
  },

  me() {
    return request<AdminMeData>({ method: 'GET', url: '/admin/me' })
  },

  listUsers(params: {
    keyword?: string
    status?: number
    created_from?: string
    created_to?: string
    page?: number
    page_size?: number
  }) {
    return request<PageData<AdminUserListItem>>({
      method: 'GET',
      url: '/admin/users',
      params,
    })
  },

  getUser(id: number) {
    return request<AdminUserDetail>({ method: 'GET', url: `/admin/users/${id}` })
  },

  setUserStatus(id: number, status: number) {
    return request<{ user_id: number; status: number }>({
      method: 'PUT',
      url: `/admin/users/${id}/status`,
      data: { status },
    })
  },

  batchUserStatus(ids: number[], status: number) {
    return request<{ updated: number; status: number }>({
      method: 'POST',
      url: '/admin/users/batch-status',
      data: { ids, status },
    })
  },

  resetUserPassword(id: number, new_password: string) {
    return request<{ user_id: number; reset: boolean }>({
      method: 'PUT',
      url: `/admin/users/${id}/password`,
      data: { new_password },
    })
  },

  patchUserProfile(id: number, dimension_code: string, value: Record<string, unknown>) {
    return request<{ user_id: number; dimension_code: string }>({
      method: 'PATCH',
      url: `/admin/users/${id}/profile`,
      data: { dimension_code, value },
    })
  },

  listAdmins(params: { keyword?: string; page?: number; page_size?: number }) {
    return request<PageData<AdminUserListItem>>({
      method: 'GET',
      url: '/admin/admins',
      params,
    })
  },

  createAdmin(data: {
    username: string
    password: string
    nickname?: string
    real_name?: string
    role_code: string
  }) {
    return request<{ id: number; username: string }>({
      method: 'POST',
      url: '/admin/admins',
      data,
    })
  },

  updateAdmin(
    id: number,
    data: {
      nickname?: string
      real_name?: string
      status?: number
      role_code?: string
    },
  ) {
    return request<{ id: number; username: string; status: number }>({
      method: 'PUT',
      url: `/admin/admins/${id}`,
      data,
    })
  },

  listMenus() {
    return request<AdminMenuConfigItem[]>({ method: 'GET', url: '/admin/menus' })
  },

  updateMenu(perm_code: string, data: { title: string; sort: number }) {
    return request<AdminMenuConfigItem>({
      method: 'PUT',
      url: `/admin/menus/${encodeURIComponent(perm_code)}`,
      data,
    })
  },
}
