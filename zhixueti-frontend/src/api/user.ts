import { request } from './request'
import type { UserInfo } from '@/types'

export interface UserUpdatePayload {
  nickname: string
  real_name: string
  major: string
  email: string
  phone?: string
  student_no?: string
  bio?: string
}

export const userApi = {
  updateProfile(data: UserUpdatePayload) {
    return request<UserInfo>({ method: 'PUT', url: '/users/me', data })
  },

  uploadAvatar(file: File) {
    const form = new FormData()
    form.append('file', file)
    return request<UserInfo>({
      method: 'POST',
      url: '/users/me/avatar',
      data: form,
    })
  },

  changePassword(data: { old_password: string; new_password: string }) {
    return request<{ message: string }>({ method: 'PUT', url: '/users/me/password', data })
  },
}
