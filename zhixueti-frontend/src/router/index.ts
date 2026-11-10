import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { getToken } from '@/api/request'
import { HOST_STUDENT_LOGIN, HOST_STUDENT_REGISTER, redirectToHostStudentLogin } from '@/utils/hostAuth'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'

const ADMIN_ROUTE_PERMS: Record<string, string> = {
  AdminDashboard: 'menu:dashboard',
  UserManage: 'menu:users',
  UserDetail: 'menu:users',
  AdminAccountManage: 'menu:admins',
  MenuManage: 'menu:menus',
  ResourceManage: 'menu:resources',
  ProfileConfigManage: 'menu:profile-config',
  LearningPathManage: 'menu:learning-paths',
  GeneratedContentManage: 'menu:generated-content',
  DocumentAuditManage: 'menu:documents',
  ContentAudit: 'menu:content-audit',
  AgentConfig: 'menu:agents',
  SystemSettings: 'menu:settings',
  OperationLogManage: 'menu:operation-logs',
  ExceptionMonitor: 'menu:exception-monitor',
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { guest: true },
  },
  {
    path: '/admin/login',
    name: 'AdminLogin',
    component: () => import('@/views/admin/AdminLogin.vue'),
    meta: { guest: true, adminGuest: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/Register.vue'),
    meta: { guest: true },
  },
  {
    path: '/student',
    component: () => import('@/layouts/StudentLayout.vue'),
    meta: { requiresAuth: true, role: 'student' },
    redirect: '/student/home',
    children: [
      { path: 'home', name: 'StudentHome', component: () => import('@/views/student/Home.vue'), meta: { title: '首页', keepAlive: true } },
      { path: 'course-center', name: 'CourseCenter', component: () => import('@/views/student/CourseCenter.vue'), meta: { title: '课程中心', keepAlive: true } },
      { path: 'class/:classId', name: 'StudentClassRoom', component: () => import('@/views/student/ClassRoom.vue'), meta: { title: '我的班级' } },
      { path: 'homework', redirect: '/student/course-center' },
      { path: 'course-study', redirect: '/student/course-center' },
      { path: 'profile-dialogue', name: 'ProfileDialogue', component: () => import('@/views/student/ProfileDialogue.vue'), meta: { title: '画像构建', keepAlive: true } },
      { path: 'profile-voice-call', name: 'ProfileVoiceCall', component: () => import('@/views/student/ProfileVoiceCall.vue'), meta: { title: '画像电话沟通' } },
      { path: 'resources', name: 'ResourceCenter', component: () => import('@/views/student/ResourceCenter.vue'), meta: { title: '资源中心', keepAlive: true } },
      { path: 'resources/square', name: 'ResourceSquare', component: () => import('@/views/student/ResourceSquare.vue'), meta: { title: '资源广场', keepAlive: true } },
      { path: 'resources/graph', name: 'ResourceKnowledgeGraph', component: () => import('@/views/student/ResourceKnowledgeGraph.vue'), meta: { title: '知识图谱', keepAlive: true } },
      { path: 'resources/:id', name: 'ResourceDetail', component: () => import('@/views/student/ResourceDetail.vue'), meta: { title: '资源详情' } },
      { path: 'path', name: 'LearningPath', component: () => import('@/views/student/LearningPath.vue'), meta: { title: '学习路径', keepAlive: true } },
      { path: 'tutor', name: 'TutorCenter', component: () => import('@/views/student/TutorCenter.vue'), meta: { title: '智能答疑', keepAlive: true } },
      { path: 'dashboard', name: 'StudentDashboard', component: () => import('@/views/student/Dashboard.vue'), meta: { title: '学习数据', keepAlive: true } },
      { path: 'center', name: 'PersonalCenter', component: () => import('@/views/student/PersonalCenter.vue'), meta: { title: '个人中心', keepAlive: true } },
    ],
  },
  {
    path: '/student/tutor/lecture/generate',
    name: 'TutorLectureGenerate',
    component: () => import('@/views/student/TutorLectureGenerate.vue'),
    meta: { requiresAuth: true, role: 'student', title: '讲解生成中' },
  },
  {
    path: '/student/tutor/lecture/:lectureId',
    name: 'TutorLecture',
    component: () => import('@/views/student/TutorLecture.vue'),
    // allowHostPreview：教师工作台生成的讲解视频可无学生 JWT 预览/学生学习
    meta: { requiresAuth: true, role: 'student', title: '沉浸式讲解', allowHostPreview: true },
  },
  {
    path: '/admin',
    // 管理端唯一外壳：顶栏版（侧栏版已废弃，功能页内容保持不变）
    component: () => import('@/layouts/AdminTopLayout.vue'),
    meta: { requiresAuth: true, role: 'admin' },
    redirect: '/admin/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'AdminDashboard',
        component: () => import('@/views/admin/Dashboard.vue'),
        meta: { title: '数据大盘', perm: 'menu:dashboard' },
      },
      {
        // HUD 控制台：保留侧栏与顶栏，内容区做可视化大屏
        path: 'console',
        name: 'AdminConsole',
        component: () => import('@/views/admin/ConsoleBoard.vue'),
        meta: { title: '控制台' },
      },
      {
        path: 'users',
        name: 'UserManage',
        component: () => import('@/views/admin/UserManage.vue'),
        meta: { title: '用户管理', perm: 'menu:users' },
      },
      {
        path: 'users/:id',
        name: 'UserDetail',
        component: () => import('@/views/admin/UserDetail.vue'),
        meta: { title: '用户详情', perm: 'menu:users' },
      },
      {
        path: 'admins',
        name: 'AdminAccountManage',
        component: () => import('@/views/admin/AdminAccountManage.vue'),
        meta: { title: '管理员账号', perm: 'menu:admins' },
      },
      {
        path: 'menus',
        name: 'MenuManage',
        component: () => import('@/views/admin/MenuManage.vue'),
        meta: { title: '菜单配置', perm: 'menu:menus' },
      },
      {
        path: 'resources',
        name: 'ResourceManage',
        component: () => import('@/views/admin/ResourceManage.vue'),
        meta: { title: '资源管理', perm: 'menu:resources' },
      },
      {
        path: 'profile-config',
        name: 'ProfileConfigManage',
        component: () => import('@/views/admin/ProfileConfigManage.vue'),
        meta: { title: '画像配置', perm: 'menu:profile-config' },
      },
      {
        path: 'learning-paths',
        name: 'LearningPathManage',
        component: () => import('@/views/admin/LearningPathManage.vue'),
        meta: { title: '学习路径', perm: 'menu:learning-paths' },
      },
      {
        path: 'generated-content',
        name: 'GeneratedContentManage',
        component: () => import('@/views/admin/GeneratedContentManage.vue'),
        meta: { title: '生成内容', perm: 'menu:generated-content' },
      },
      {
        path: 'documents',
        name: 'DocumentAuditManage',
        component: () => import('@/views/admin/DocumentAuditManage.vue'),
        meta: { title: '文档审核', perm: 'menu:documents' },
      },
      {
        path: 'content-audit',
        name: 'ContentAudit',
        component: () => import('@/views/admin/ContentAudit.vue'),
        meta: { title: '内容安全', perm: 'menu:content-audit' },
      },
      {
        path: 'agents',
        name: 'AgentConfig',
        component: () => import('@/views/admin/AgentConfig.vue'),
        meta: { title: '智能体配置', perm: 'menu:agents' },
      },
      {
        path: 'settings',
        name: 'SystemSettings',
        component: () => import('@/views/admin/SystemSettings.vue'),
        meta: { title: '系统设置', perm: 'menu:settings' },
      },
      {
        path: 'operation-logs',
        name: 'OperationLogManage',
        component: () => import('@/views/admin/OperationLogManage.vue'),
        meta: { title: '操作日志', perm: 'menu:operation-logs' },
      },
      {
        path: 'exception-monitor',
        name: 'ExceptionMonitor',
        component: () => import('@/views/admin/ExceptionMonitor.vue'),
        meta: { title: '异常监控', perm: 'menu:exception-monitor' },
      },
      {
        path: 'forbidden',
        name: 'AdminForbidden',
        component: () => import('@/views/admin/Forbidden.vue'),
        meta: { title: '无权限' },
      },
    ],
  },
  {
    path: '/',
    redirect: '/student/home',
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

/**
 * 路由级分块加载失败兜底。
 *
 * 场景：版本发布后旧 index.html 仍被引用，按需加载的分块已被替换，用户点菜单得到白屏。
 * 策略：同一次会话内自动整页重载一次（拿到新入口），仍失败则给出可读提示，避免死循环。
 */
const CHUNK_RETRY_KEY = 'spa:chunk-retry'
router.onError((error) => {
  const msg = String((error as Error)?.message || error)
  const isChunkError = /Failed to fetch dynamically imported module|Importing a module script failed|Loading chunk .* failed/i.test(msg)
  if (!isChunkError) return
  if (sessionStorage.getItem(CHUNK_RETRY_KEY) === '1') {
    sessionStorage.removeItem(CHUNK_RETRY_KEY)
    window.alert('页面资源已更新，但自动刷新未生效。请手动刷新页面（Ctrl+F5）后重试。')
    return
  }
  sessionStorage.setItem(CHUNK_RETRY_KEY, '1')
  window.location.reload()
})
// 正常导航成功后清除重试标记，保证下次版本更新仍能自动恢复
// 导航完成后：清除分块重试标记 + 按路由标题更新浏览器标签
router.afterEach((to) => {
  sessionStorage.removeItem(CHUNK_RETRY_KEY)
  const pageTitle = String(to.meta.title || '').trim()
  document.title = pageTitle ? `${pageTitle} · 智课共生` : '智课共生 · AI 互动智课生成与实时问答系统'
})

function withTimeout<T>(promise: Promise<T>, ms = 8000): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) => {
      window.setTimeout(() => reject(new Error('auth_timeout')), ms)
    }),
  ])
}

router.beforeEach(async (to, _from, next) => {
  const userStore = useUserStore()
  const permissionStore = usePermissionStore()
  userStore.syncTokenFromStorage()

  // 智课共生 /login|/register 不再作为对外主入口，硬跳宿主原登录/注册页
  if (to.path === '/login' || to.path === '/register') {
    const target = to.path === '/register' ? HOST_STUDENT_REGISTER : HOST_STUDENT_LOGIN
    window.location.replace(target)
    return next(false)
  }

  if (to.meta.guest) {
    if (userStore.isLoggedIn && userStore.userInfo) {
      if (to.meta.adminGuest) {
        // 管理员直接进大盘；非管理员停在登录页（避免 /admin/login → /admin/login 死循环），可直接输入管理员账号
        if (userStore.isAdmin) return next('/admin/dashboard')
        return next()
      }
      return next(userStore.isAdmin ? '/admin/dashboard' : '/student/home')
    }
    if (userStore.isLoggedIn && !userStore.userInfo) {
      try {
        await withTimeout(userStore.fetchUser(), 4000)
      } catch {
        /* 超时或失败：清掉失效会话，停留登录页 */
      }
      if (userStore.isLoggedIn && userStore.userInfo) {
        if (to.meta.adminGuest) {
          if (userStore.isAdmin) return next('/admin/dashboard')
          return next()
        }
        return next(userStore.isAdmin ? '/admin/dashboard' : '/student/home')
      }
      // 仅在仍有 token 但拿不到资料时清理，避免挡登录页
      if (getToken()) userStore.logout()
      return next()
    }
    return next()
  }

  if (to.meta.requiresAuth) {
    if (!getToken()) {
      if (to.meta.role === 'admin') {
        return next('/admin/login')
      }
      const lectureId = String(to.params.lectureId || '')
      if (
        to.meta.allowHostPreview
        && (to.query.from === 'host' || lectureId.startsWith('host-'))
      ) {
        return next()
      }
      // 无智课共生 JWT：回宿主原登录页重新桥接；避免与宿主 session 形成「假登录」死循环
      redirectToHostStudentLogin(to.fullPath)
      return next(false)
    }
    // 无资料时短等 /me；超时不踢出（有 token 先进入，布局再补拉）
    if (!userStore.userInfo) {
      try {
        await withTimeout(userStore.fetchUser(), 4000)
      } catch {
        /* ignore */
      }
      if (!getToken()) {
        userStore.logout()
        if (to.meta.role === 'admin') {
          return next('/admin/login')
        }
        redirectToHostStudentLogin(to.fullPath)
        return next(false)
      }
    } else {
      void userStore.fetchUser().catch(() => undefined)
    }
    if (to.meta.role === 'admin') {
      if (!userStore.isAdmin) {
        return next('/student/home')
      }
      try {
        await withTimeout(permissionStore.loadAdminContext())
      } catch {
        userStore.logout()
        return next('/admin/login')
      }
      const routeName = String(to.name || '')
      const requiredPerm = String(to.meta.perm || ADMIN_ROUTE_PERMS[routeName] || '')
      if (requiredPerm && !permissionStore.hasPerm(requiredPerm)) {
        return next('/admin/forbidden')
      }
    }
    if (to.meta.role === 'student') {
      if (userStore.isAdmin) {
        return next('/admin/dashboard')
      }
    }
  }
  next()
})

export default router
