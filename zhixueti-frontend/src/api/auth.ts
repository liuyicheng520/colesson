import { request, setRefreshToken } from './request'
import type { TokenData, UserInfo } from '@/types'

export const authApi = {
  register(data: {
    username: string
    password: string
    email?: string
    nickname?: string
    major?: string
    grade?: number
    user_type?: number
  }) {
    return request<UserInfo>({ method: 'POST', url: '/auth/register', data })
  },

  async login(data: { username: string; password: string }) {
    const tokenData = await request<TokenData>({ method: 'POST', url: '/auth/login', data })
    if (tokenData.refresh_token) setRefreshToken(tokenData.refresh_token)
    return tokenData
  },

  me() {
    return request<UserInfo>({ method: 'GET', url: '/auth/me' })
  },
}
