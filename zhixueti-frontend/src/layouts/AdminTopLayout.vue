<script setup lang="ts">
/**
 * 管理端唯一外壳：顶部导航版。
 *
 * 说明：原先的侧栏版（AdminLayout）已废弃，管理端只保留这一套界面；
 * 14 个功能页的内容与路由保持不变，只替换外层容器，避免"两个管理员端"。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Bell, Menu as MenuIcon } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'
import { formatRole } from '@/utils/permission'
import { formatBeijingDateTime } from '@/utils/datetime'
import { adminOpsApi, type AnnouncementItem } from '@/api/adminOps'

const BRAND_ICON = '/brand-icon.jpg'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const permissionStore = usePermissionStore()

const announcementVisible = ref(false)
const announcements = ref<AnnouncementItem[]>([])
const mobileNavOpen = ref(false)

// 路由淡入：与全站同一套令牌
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
    mobileNavOpen.value = false
  },
)

const activePath = computed(() => {
  const matched = route.matched.find((r) => r.meta?.perm)
  return matched?.path || route.path
})

const currentTitle = computed(() => String(route.meta?.title || '管理端'))

const adminRoleLabel = computed(() => {
  const roles = userStore.userInfo?.roles || []
  const primary = roles.find((r) => r.startsWith('ROLE_'))
  return primary ? formatRole(primary) : '管理员'
})

const publishedAnnouncements = computed(() => announcements.value.filter((a) => a.status === 1))

async function loadAnnouncements() {
  try {
    const list = await adminOpsApi.listAnnouncements()
    announcements.value = Array.isArray(list) ? list : []
  } catch {
    announcements.value = []
  }
}

function handleSelect(path: string) {
  if (path !== route.path) router.push(path)
}

function showAnnouncements() {
  announcementVisible.value = true
}

function goSettings() {
  announcementVisible.value = false
  router.push('/admin/settings')
}

async function logout() {
  await userStore.logout()
  router.replace('/admin/login')
}

onMounted(loadAnnouncements)
onBeforeUnmount(() => {
  if (routeAnimTimer) clearTimeout(routeAnimTimer)
})
</script>

<template>
  <div class="top-admin">
    <header class="top-bar">
      <!-- 第一行：品牌 + 右侧操作 -->
      <div class="bar-main">
        <div class="brand" role="button" tabindex="0" @click="handleSelect('/admin/dashboard')" @keydown.enter="handleSelect('/admin/dashboard')">
          <img :src="BRAND_ICON" alt="" class="brand-mark" />
          <div class="brand-text">
            <strong>智课共生</strong>
            <span>管理端</span>
          </div>
        </div>

        <div class="top-right">
          <button class="hud-entry" type="button" @click="handleSelect('/admin/console')">CONSOLE</button>
          <el-badge :value="publishedAnnouncements.length || undefined" :hidden="!publishedAnnouncements.length">
            <el-tooltip content="系统公告" placement="bottom">
              <button class="icon-btn" type="button" @click="showAnnouncements">
                <el-icon><Bell /></el-icon>
              </button>
            </el-tooltip>
          </el-badge>
          <div class="who">
            <span class="who-name">{{ userStore.userInfo?.username || '管理员' }}</span>
            <span class="who-role">{{ adminRoleLabel }}</span>
          </div>
          <button class="logout" type="button" @click="logout">退出登录</button>
          <button class="icon-btn mobile-only" type="button" @click="mobileNavOpen = !mobileNavOpen">
            <el-icon><MenuIcon /></el-icon>
          </button>
        </div>
      </div>

      <!-- 第二行：功能导航 -->
      <nav class="top-nav" aria-label="管理端导航">
        <button
          v-for="m in permissionStore.menus"
          :key="m.path"
          type="button"
          class="nav-item"
          :class="{ active: activePath === m.path }"
          @click="handleSelect(m.path)"
        >
          {{ m.title }}
        </button>
      </nav>
    </header>

    <nav v-if="mobileNavOpen" class="mobile-nav" aria-label="管理端导航（移动）">
      <button
        v-for="m in permissionStore.menus"
        :key="m.path"
        type="button"
        class="nav-item"
        :class="{ active: activePath === m.path }"
        @click="handleSelect(m.path)"
      >
        {{ m.title }}
      </button>
    </nav>

    <main class="top-main" :class="{ 'route-fade-once': routeAnimating }">
      <div class="page-crumb">
        <span>管理端</span><i>/</i><strong>{{ currentTitle }}</strong>
      </div>
      <router-view />
    </main>

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
  </div>
</template>

<style scoped lang="scss">
.top-admin {
  min-height: 100vh;
  background: $bg-page;
}

/* ---------------- 顶栏 ---------------- */
.top-bar {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.94);
  border-bottom: 1px solid $border-color;
  backdrop-filter: blur(14px) saturate(1.15);
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.04);
}

.bar-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 62px;
  padding: 0 20px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.7);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
  cursor: pointer;
  user-select: none;

  .brand-mark {
    width: 34px;
    height: 34px;
    border-radius: 9px;
    object-fit: cover;
  }

  .brand-text {
    display: flex;
    flex-direction: column;
    line-height: 1.15;

    strong { font-size: 15px; color: $text-primary; letter-spacing: 0.02em; }
    span { font-size: 11px; color: $text-secondary; }
  }
}

.top-nav {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 0 14px;
  height: 46px;
  overflow-x: auto;
  scrollbar-width: none;

  &::-webkit-scrollbar { display: none; }
}

.nav-item {
  position: relative;
  flex: 0 0 auto;
  padding: 8px 12px;
  font-size: 13px;
  color: $text-secondary;
  background: transparent;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  white-space: nowrap;
  transition: color var(--dur-fast, 160ms) var(--ease-standard, cubic-bezier(0.4, 0, 0.2, 1)),
              background-color var(--dur-fast, 160ms) var(--ease-standard, cubic-bezier(0.4, 0, 0.2, 1));

  &:hover { color: $primary; background: rgba(37, 99, 235, 0.06); }

  &.active {
    color: $primary;
    font-weight: 700;
    background: rgba(37, 99, 235, 0.1);
  }

  &.active::after {
    content: '';
    position: absolute;
    left: 12px;
    right: 12px;
    bottom: 2px;
    height: 2px;
    border-radius: 2px;
    background: $primary;
  }
}

.top-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
}

.hud-entry {
  padding: 6px 13px;
  font-size: 11px;
  letter-spacing: 0.16em;
  font-weight: 700;
  color: #a5f3fc;
  background: linear-gradient(135deg, rgba(12, 74, 110, 0.95), rgba(76, 29, 149, 0.9));
  border: 1px solid rgba(34, 211, 238, 0.6);
  border-radius: 5px;
  cursor: pointer;
  transition: box-shadow var(--dur-fast, 160ms) var(--ease-standard, cubic-bezier(0.4, 0, 0.2, 1)),
              transform var(--dur-fast, 160ms) var(--ease-standard, cubic-bezier(0.4, 0, 0.2, 1));

  &:hover { box-shadow: 0 0 14px rgba(34, 211, 238, 0.6); transform: translateY(-1px); }
  &:active { transform: translateY(0); }
}

.icon-btn {
  display: inline-grid;
  place-items: center;
  width: 32px;
  height: 32px;
  color: $text-secondary;
  background: transparent;
  border: none;
  border-radius: 8px;
  cursor: pointer;

  &:hover { color: $primary; background: rgba(37, 99, 235, 0.08); }
}

.who {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 10px;
  border-left: 1px solid $border-color;

  .who-name { font-size: 13px; font-weight: 600; color: $text-primary; }
  .who-role {
    padding: 2px 8px;
    font-size: 11px;
    color: $primary;
    background: rgba(37, 99, 235, 0.1);
    border-radius: 999px;
  }
}

.logout {
  padding: 6px 12px;
  font-size: 12px;
  color: #ef4444;
  background: transparent;
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: 8px;
  cursor: pointer;

  &:hover { background: rgba(239, 68, 68, 0.08); }
}

.mobile-only { display: none; }

.mobile-nav {
  display: none;
  flex-wrap: wrap;
  gap: 6px;
  padding: 10px 14px;
  background: #fff;
  border-bottom: 1px solid $border-color;
}

/* ---------------- 内容区 ---------------- */
.top-main {
  --admin-header-h: 108px;
  padding: 14px 20px 28px;
  max-width: 1440px;
  margin: 0 auto;
}

.page-crumb {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  font-size: 12px;
  color: $text-secondary;

  i { font-style: normal; opacity: 0.5; }
  strong { color: $text-primary; font-weight: 600; }
}

.ann-list { max-height: 360px; overflow-y: auto; }
.ann-item {
  padding: 12px 0;
  border-bottom: 1px solid $border-color;
  &:last-child { border-bottom: none; }
  p { margin: 6px 0; color: $text-secondary; font-size: 13px; line-height: 1.5; }
  .ann-time { font-size: 12px; color: $text-secondary; }
}

@media (max-width: 1080px) {
  .top-nav { display: none; }
  .mobile-only { display: inline-grid; }
  .mobile-nav { display: flex; }
  .who { border-left: none; padding-left: 0; }
}

@media (max-width: 720px) {
  .top-bar { padding: 0 12px; gap: 10px; }
  .brand .brand-text span { display: none; }
  .who .who-name { max-width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .top-main { padding: 12px; }
}
</style>
