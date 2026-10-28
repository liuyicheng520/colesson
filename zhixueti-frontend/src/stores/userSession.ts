/**
 * 用户会话级状态清理 — 登出/401/切换账号时必须调用，防止 Pinia 缓存跨用户串号。
 */
import { useProfileStore } from './profile'
import { useResourceCenterStore } from './resourceCenter'
import { useLearningPathStore } from './learningPath'
import { usePermissionStore } from './permission'

export function clearAllUserScopedStores(): void {
  useProfileStore().resetProfile()
  useResourceCenterStore().clearCache()
  useLearningPathStore().clearCache()
  usePermissionStore().reset()
}
