/** 宿主智课共生学生登录入口（非智课共生 Vue Login） */
export const HOST_STUDENT_LOGIN = '/student/login.html'
export const HOST_STUDENT_REGISTER = '/student/register.html'
export const HOST_AUTH_USER_KEY = 'ai_teacher_auth_user_v2'

export function readHostAuthUser(): { activeRole?: string; roles?: string[]; username?: string } | null {
  try {
    const raw = localStorage.getItem(HOST_AUTH_USER_KEY)
    if (!raw) return null
    const user = JSON.parse(raw)
    return user && typeof user === 'object' ? user : null
  } catch {
    return null
  }
}

export function isHostStudentLoggedIn(): boolean {
  const user = readHostAuthUser()
  if (!user) return false
  if (user.activeRole === 'student') return true
  return Array.isArray(user.roles) && user.roles.includes('student')
}

/** 未登录或仅有宿主会话时，硬跳转到原学生登录页 */
export function redirectToHostStudentLogin(returnTo?: string): void {
  const params = new URLSearchParams()
  if (returnTo && returnTo.startsWith('/')) {
    params.set('returnTo', returnTo)
  }
  if (!isHostStudentLoggedIn()) {
    params.set('reason', 'unauthorized')
  }
  const qs = params.toString()
  window.location.replace(HOST_STUDENT_LOGIN + (qs ? `?${qs}` : ''))
}
