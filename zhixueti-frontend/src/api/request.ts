import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import type { ApiResponse } from '@/types'
import { HOST_STUDENT_LOGIN } from '@/utils/hostAuth'

const TOKEN_KEY = 'edunexus_token'
const REFRESH_TOKEN_KEY = 'edunexus_refresh_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setRefreshToken(token: string): void {
  localStorage.setItem(REFRESH_TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

/** 401 时同步清理 Pinia 用户态，避免 token 双存储不一致导致白屏/重载循环 */
let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler
}

/** 常规 API 60s；LLM/多智能体长任务单独传 timeout */
export const API_TIMEOUT = {
  default: 60_000,
  long: 180_000,
  llm: 300_000,
} as const

function formatErrorMessage(error: { message?: string; code?: string; response?: { data?: { message?: string } } }): string {
  const rawMsg = error.response?.data?.message || error.message || '网络错误'
  if (error.code === 'ECONNABORTED' || /timeout of \d+ms exceeded/i.test(rawMsg)) {
    return '请求超时：服务器处理时间较长，请稍后重试；若频繁出现请确认智课共生后端与 LLM 配置正常'
  }
  if (rawMsg === 'Network Error' || rawMsg === 'Failed to fetch') {
    return '暂时无法连接后端 API。请确认宿主 8082 已启动，且智课共生 FastAPI 已作为内部服务运行'
  }
  return rawMsg
}

function isTransientNetworkError(error: { message?: string; code?: string; response?: unknown }): boolean {
  if (error.response) return false
  const msg = error.message || ''
  return error.code === 'ERR_NETWORK' || msg === 'Network Error' || msg === 'Failed to fetch'
}

const service: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api/v1',
  timeout: API_TIMEOUT.default,
  headers: { 'Content-Type': 'application/json' },
})

service.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // FormData 需由浏览器自动设置 multipart boundary
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type']
  }
  return config
})

let refreshPromise: Promise<string | null> | null = null

async function tryRefreshToken(): Promise<string | null> {
  const refresh = getRefreshToken()
  if (!refresh) return null
  if (!refreshPromise) {
    refreshPromise = service
      .post<ApiResponse<{ access_token: string; refresh_token: string }>>('/auth/refresh', {
        refresh_token: refresh,
      })
      .then((res) => {
        const data = res.data.data
        if (!data?.access_token) return null
        setToken(data.access_token)
        if (data.refresh_token) setRefreshToken(data.refresh_token)
        return data.access_token
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

function redirectToLogin() {
  const path = window.location.pathname
  if (path.startsWith('/admin')) {
    if (!path.startsWith('/admin/login')) {
      window.location.replace('/admin/login')
    }
    return
  }
  if (!path.startsWith(HOST_STUDENT_LOGIN) && !path.startsWith('/student/login')) {
    window.location.replace(HOST_STUDENT_LOGIN)
  }
}

service.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    const res = response.data
    if (res.code !== 0) {
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message))
    }
    return response
  },
  async (error) => {
    const original = error.config as AxiosRequestConfig & { _retried?: boolean; _netRetried?: boolean }

    // 后端 --reload 或短暂断连时自动重试一次，减少误报弹窗
    if (original && !original._netRetried && isTransientNetworkError(error)) {
      original._netRetried = true
      await new Promise((r) => setTimeout(r, 800))
      try {
        return await service.request(original)
      } catch (retryErr) {
        error = retryErr
      }
    }

    const msg = formatErrorMessage(error)
    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true
      const newToken = await tryRefreshToken()
      if (newToken) {
        original.headers = original.headers || {}
        original.headers.Authorization = `Bearer ${newToken}`
        return service.request(original)
      }
      clearToken()
      onUnauthorized?.()
      redirectToLogin()
    } else if (error.response?.status === 401) {
      clearToken()
      onUnauthorized?.()
      redirectToLogin()
    } else if (error.response?.status === 403) {
      ElMessage.error(msg || '无权限访问')
    } else {
      ElMessage.error(msg)
    }
    return Promise.reject(error)
  },
)

export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  const res = await service.request<ApiResponse<T>>(config)
  return res.data.data as T
}

export default service
