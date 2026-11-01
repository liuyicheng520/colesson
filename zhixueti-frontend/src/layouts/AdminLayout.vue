<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as ElementPlusIcons from '@element-plus/icons-vue'
import { Fold, Expand, Bell } from '@element-plus/icons-vue'

const BRAND_ICON = '/brand-icon.jpg'
import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'
import { usePermissionStore } from '@/stores/permission'
import { formatRole } from '@/utils/permission'
import { formatBeijingDateTime } from '@/utils/datetime'
import { adminOpsApi, type AnnouncementItem } from '@/api/adminOps'

const route = useRoute()

// 路由淡入：与 StudentLayout 同一套令牌
const routeAnimating = ref(false)
let routeAnimTimer: ReturnType<typeof setTimeout> | null = null
watch(
  () => route.path,
  () => {
    if (routeAnimTimer) clearTimeout(routeAnimTimer)
    routeAnimating.value = false
    requestAnimationFrame(() => {
      routeAnimating.value = true
      routeAnimTimer = setTimeout(() => {
        routeAnimating.value = false
      }, 240)
    })
  },
)
const router = useRouter()
const userStore = useUserStore()
const appStore = useAppStore()
const permissionStore = usePermissionStore()

const announcementVisible = ref(false)
const announcements = ref<AnnouncementItem[]>([])

const activeMenu = computed(() => {
  const matched = route.matched.find((r) => r.meta?.perm)
  return matched?.path || route.path
})

const breadcrumbItems = computed(() => {
  const items: Array<{ title: string; path?: string }> = [{ title: '管理端', path: '/admin/dashboard' }]
  route.matched.forEach((r) => {
    if (r.meta?.title && r.path !== '/admin') {
      items.push({ title: String(r.meta.title), path: r.path.includes(':') ? undefined : r.path })
    }
  })
  return items
})

const adminRoleLabel = computed(() => {
  const roles = userStore.userInfo?.roles || []
  const primary = roles.find((r) => r.startsWith('ROLE_'))
  return primary ? formatRole(primary) : '管理员'
})

const publishedAnnouncements = computed(() =>
  announcements.value.filter((a) => a.status === 1).slice(0, 5),
)

function resolveIcon(name: string) {
  return (ElementPlusIcons as Record<string, unknown>)[name] || ElementPlusIcons.Menu
}

function logout() {
  userStore.logout()
  const href = router.resolve({ path: '/admin/login' }).href
  window.location.replace(href)
}

async function loadAnnouncements() {
  try {
    announcements.value = await adminOpsApi.listAnnouncements()
  } catch {
    announcements.value = []
  }
}

function showAnnouncements() {
  announcementVisible.value = true
}

function goSettings() {
  announcementVisible.value = false
  router.push('/admin/settings')
}

// 小屏自动折叠侧栏，给内容区让出宽度
const syncSidebarToViewport = () => {
  if (window.innerWidth <= 768 && !appStore.sidebarCollapsed) {
    appStore.sidebarCollapsed = true
  }
}

onMounted(() => {
  loadAnnouncements()
  syncSidebarToViewport()
  window.addEventListener('resize', syncSidebarToViewport)
})
onBeforeUnmount(() => window.removeEventListener('resize', syncSidebarToViewport))
</script>

<template>
  <el-container class="admin-layout">
    <el-aside :width="appStore.sidebarCollapsed ? '64px' : '220px'" class="sidebar admin-sidebar">
      <div class="logo">
        <img :src="BRAND_ICON" alt="智课共生" class="brand-mark" />
        <span v-if="!appStore.sidebarCollapsed">智课共生管理端</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="appStore.sidebarCollapsed"
        router
        background-color="#0f172a"
        text-color="#94a3b8"
        active-text-color="#fff"
        :default-openeds="[]"
      >
        <el-menu-item
          v-for="m in permissionStore.menus"
          :key="m.path"
          :index="m.path"
        >
          <el-icon><component :is="resolveIcon(m.icon)" /></el-icon>
          <template #title><span>{{ m.title }}</span></template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-button text @click="appStore.toggleSidebar">
            <el-icon><Fold v-if="!appStore.sidebarCollapsed" /><Expand v-else /></el-icon>
          </el-button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item
              v-for="(item, idx) in breadcrumbItems"
              :key="idx"
              :to="item.path ? { path: item.path } : undefined"
            >
              {{ item.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-tooltip content="全屏可视化控制台" placement="bottom">
            <button class="hud-entry" type="button" @click="router.push('/admin/console')">
              CONSOLE
            </button>
          </el-tooltip>
          <el-badge :value="publishedAnnouncements.length || undefined" :hidden="!publishedAnnouncements.length">
            <el-tooltip content="系统公告" placement="bottom">
              <el-button text circle @click="showAnnouncements">
                <el-icon><Bell /></el-icon>
              </el-button>
            </el-tooltip>
          </el-badge>
          <div class="user-info">
            <span class="username">智课共生管理端</span>
            <el-tag type="danger" size="small">{{ adminRoleLabel }}</el-tag>
          </div>
          <el-button text type="danger" @click="logout">退出登录</el-button>
        </div>
      </el-header>
      <el-main class="main" :class="{ 'route-fade-once': routeAnimating }">
        <router-view />
      </el-main>
    </el-container>

    <el-dialog v-model="announcementVisible" title="系统公告" width="520px">
      <el-empty v-if="!publishedAnnouncements.length" description="暂无已发布公告" />
      <div v-else class="ann-list">
        <div v-for="a in publishedAnnouncements" :key="a.id" class="ann-item">
          <strong>{{ a.title }}</strong>
          <p>{{ a.content }}</p>
          <span class="ann-time">{{ formatBeijingDateTime(a.published_at || a.created_at) }}</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="announcementVisible = false">关闭</el-button>
        <el-button type="primary" @click="goSettings">管理公告</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<style scoped lang="scss">
.admin-layout { height: 100vh; }
.admin-sidebar { background: #0f172a !important; }
.sidebar {
  transition: width 0.28s ease;
  .logo {
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: #fff;
    font-weight: 700;
    border-bottom: 1px solid #334155;
    font-size: 14px;
    letter-spacing: 0.02em;
    padding: 0 12px;
  }
  .brand-mark {
    width: 28px;
    height: 28px;
    border-radius: 7px;
    object-fit: cover;
    flex-shrink: 0;
  }
  .el-menu {
    border-right: none;
    padding: 8px 0;
  }
  .el-menu-item .el-icon {
    font-size: 18px;
  }
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid $border-color;
  height: 60px;
  padding: 0 20px;
  .header-left {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .header-right {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;

    .el-button {
      transition: color 0.2s ease, background-color 0.2s ease;
    }
  }
  .user-info {
    display: flex;
    align-items: center;
    gap: 8px;
    .username { font-weight: 500; color: $text-primary; }
  }
}
.main { background: $bg-page; overflow-y: auto; }
/* HUD 控制台入口：霓虹描边，与深色侧栏呼应 */
.hud-entry {
  padding: 5px 12px;
  font-size: 11px;
  letter-spacing: 0.16em;
  font-weight: 700;
  color: #a5f3fc;
  background: linear-gradient(135deg, rgba(12, 74, 110, 0.9), rgba(76, 29, 149, 0.85));
  border: 1px solid rgba(34, 211, 238, 0.6);
  border-radius: 4px;
  cursor: pointer;
  transition: box-shadow var(--dur-fast, 160ms) var(--ease-standard, cubic-bezier(0.4, 0, 0.2, 1)),
              transform var(--dur-fast, 160ms) var(--ease-standard, cubic-bezier(0.4, 0, 0.2, 1));
  &:hover { box-shadow: 0 0 14px rgba(34, 211, 238, 0.65); transform: translateY(-1px); }
  &:active { transform: translateY(0); }
}
/* 小屏头部收纳：隐藏长文本，面包屑截断，防止撑破 375px */
@media (max-width: 768px) {
  .header {
    padding: 0 12px;
    .header-left { flex: 1; }
    .el-breadcrumb { white-space: nowrap; overflow: hidden; }
    .header-right { gap: 8px; }
    .user-info .username { display: none; }
  }
}
.ann-list { max-height: 360px; overflow-y: auto; }
.ann-item {
  padding: 12px 0;
  border-bottom: 1px solid $border-color;
  &:last-child { border-bottom: none; }
  p { margin: 6px 0; color: $text-secondary; font-size: 13px; line-height: 1.5; }
  .ann-time { font-size: 12px; color: $text-secondary; }
}
</style>
