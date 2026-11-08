import { usePermissionStore } from '@/stores/permission'

/** 按钮/菜单权限校验 */
export function hasPerm(code: string): boolean {
  return usePermissionStore().hasPerm(code)
}

/** 任一权限命中 */
export function hasAnyPerm(...codes: string[]): boolean {
  const store = usePermissionStore()
  return codes.some((c) => store.hasPerm(c))
}

export const ADMIN_ROLE_LABELS: Record<string, string> = {
  ROLE_SUPER_ADMIN: '超级管理员',
  ROLE_CONTENT_ADMIN: '内容管理员',
  ROLE_OPS_ADMIN: '运维管理员',
  ROLE_ADMIN: '管理员',
}

export function formatRole(code: string): string {
  return ADMIN_ROLE_LABELS[code] || code
}

export { formatBeijingDateTime as formatDateTime } from './datetime'
