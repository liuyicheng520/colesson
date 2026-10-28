import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import { userApi, type UserUpdatePayload } from '@/api/user'
import { setToken, clearToken, getToken } from '@/api/request'
import { clearAllUserScopedStores } from './userSession'
import { usePermissionStore } from './permission'
import type { UserInfo } from '@/types'

const ADMIN_ROLE_CODES = new Set([
  'ROLE_ADMIN',
  'ROLE_SUPER_ADMIN',
  'ROLE_CONTENT_ADMIN',
  'ROLE_OPS_ADMIN',
])

/** 与 token 分离的用户资料缓存，避免刷新后空白等待 /me */
const USER_CACHE_KEY = 'edunexus_user_cache'
const USER_CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000

interface UserCachePayload {
  tokenMark: string
  user: UserInfo
  cachedAt: number
}

function tokenMark(token: string): string {
  return `${token.length}:${token.slice(0, 6)}:${token.slice(-6)}`
}

function readUserCache(token: string | null): UserInfo | null {
  if (!token) return null
  try {
    const raw = localStorage.getItem(USER_CACHE_KEY)
    if (!raw) return null
    const data = JSON.parse(raw) as UserCachePayload
    if (!data?.user || data.tokenMark !== tokenMark(token)) return null
    if (Date.now() - (data.cachedAt || 0) > USER_CACHE_TTL_MS) return null
    return data.user
  } catch {
    return null
  }
}

function writeUserCache(token: string, user: UserInfo): void {
  try {
    const payload: UserCachePayload = {
      tokenMark: tokenMark(token),
      user,
      cachedAt: Date.now(),
    }
    localStorage.setItem(USER_CACHE_KEY, JSON.stringify(payload))
  } catch {
    /* quota / private mode */
  }
}

function clearUserCache(): void {
  localStorage.removeItem(USER_CACHE_KEY)
}

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error('auth_timeout')), ms)
    promise.then(
      (v) => {
        window.clearTimeout(timer)
        resolve(v)
      },
      (e) => {
        window.clearTimeout(timer)
        reject(e)
      },
    )
  })
}

export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(getToken())
  const userInfo = ref<UserInfo | null>(readUserCache(token.value))
  const avatarVersion = ref(0)

  /** 合并并发 /me；generation 用于作废过期的 in-flight */
  let inflightFetch: Promise<void> | null = null
  let fetchGeneration = 0

  function syncTokenFromStorage() {
    const stored = getToken()
    if (stored !== token.value) {
      token.value = stored
      if (!stored) {
        userInfo.value = null
        clearUserCache()
      } else if (!userInfo.value) {
        userInfo.value = readUserCache(stored)
      } else if (readUserCache(stored)?.id !== userInfo.value.id) {
        userInfo.value = readUserCache(stored)
      }
    }
  }

  function setUserInfo(user: UserInfo | null) {
    userInfo.value = user
    if (user && token.value) writeUserCache(token.value, user)
    else clearUserCache()
  }

  const isLoggedIn = computed(() => !!getToken() || !!token.value)
  const isAdmin = computed(() => {
    if (userInfo.value?.user_type === 3) return true
    return userInfo.value?.roles?.some((r) => ADMIN_ROLE_CODES.has(r)) ?? false
  })
  const isStudent = computed(() => !isAdmin.value)

  /** 全局统一展示名：优先真实姓名，空时显示引导占位 */
  const displayName = computed(() => {
    const name = userInfo.value?.real_name?.trim()
    if (name) return name
    const nick = userInfo.value?.nickname?.trim()
    if (nick) return nick
    return '请填入真实姓名'
  })

  const hasRealName = computed(() => !!userInfo.value?.real_name?.trim())

  async function login(username: string, password: string) {
    clearAllUserScopedStores()
    setUserInfo(null)
    const data = await authApi.login({ username, password })
    token.value = data.access_token
    setToken(data.access_token)
    // 登录后尽快进首页：/me 最多等 5s，超时不阻断（有 token，布局会再拉）
    try {
      await withTimeout(fetchUser(true), 5000)
    } catch {
      /* 稍后由布局/路由补拉 */
    }
    return data
  }

  async function register(payload: Parameters<typeof authApi.register>[0]) {
    clearAllUserScopedStores()
    setUserInfo(null)
    await authApi.register(payload)
    return login(payload.username, payload.password)
  }

  /**
   * 拉取当前用户。
   * - force=true 时作废旧请求并立刻发新请求（不无限等待挂起的旧 /me）
   */
  async function fetchUser(force = false) {
    syncTokenFromStorage()
    if (!token.value) return

    if (inflightFetch && !force) return inflightFetch

    const generation = ++fetchGeneration
    const tokenAtStart = token.value
    const run = (async () => {
      try {
        const me = await authApi.me()
        if (generation !== fetchGeneration) return
        if (token.value !== tokenAtStart) return
        setUserInfo(me)
      } catch {
        /* 静默失败；401 时 request 拦截器会清 token */
      }
    })()

    inflightFetch = run
    try {
      await run
    } finally {
      if (inflightFetch === run) inflightFetch = null
    }
  }

  async function updateProfile(payload: UserUpdatePayload) {
    setUserInfo(await userApi.updateProfile(payload))
  }

  async function uploadAvatar(file: File) {
    setUserInfo(await userApi.uploadAvatar(file))
    avatarVersion.value += 1
    return userInfo.value!.avatar_url
  }

  async function changePassword(oldPassword: string, newPassword: string) {
    await userApi.changePassword({ old_password: oldPassword, new_password: newPassword })
  }

  function logout() {
    fetchGeneration += 1
    inflightFetch = null
    token.value = null
    setUserInfo(null)
    avatarVersion.value = 0
    clearToken()
    try {
      usePermissionStore().reset()
    } catch {
      /* ignore */
    }
    try {
      clearAllUserScopedStores()
    } catch {
      /* 清理失败不阻断退出跳转 */
    }
  }

  return {
    token,
    userInfo,
    avatarVersion,
    isLoggedIn,
    isAdmin,
    isStudent,
    displayName,
    hasRealName,
    login,
    register,
    fetchUser,
    updateProfile,
    uploadAvatar,
    changePassword,
    logout,
    syncTokenFromStorage,
  }
})
