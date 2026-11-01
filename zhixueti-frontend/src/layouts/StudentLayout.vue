<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  HomeFilled, Reading, User, Collection, Guide, ChatDotRound,
  DataAnalysis, Setting, SwitchButton,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import UserAvatar from '@/components/UserAvatar.vue'
import { HOST_STUDENT_LOGIN } from '@/utils/hostAuth'

const BRAND_ICON = '/brand-icon.jpg'

const route = useRoute()

// 路由淡入：不重构 keep-alive 结构，只给内容容器挂一次性动画类
const routeAnimating = ref(false)
let routeAnimTimer: ReturnType<typeof setTimeout> | null = null
watch(
  () => route.path,
  () => {
    if (routeAnimTimer) clearTimeout(routeAnimTimer)
    routeAnimating.value = false
    // 下一帧重新挂类，保证连续切换也能重放动画
    requestAnimationFrame(() => {
      routeAnimating.value = true
      routeAnimTimer = setTimeout(() => {
        routeAnimating.value = false
      }, 240)
    })
  },
)
const userStore = useUserStore()

/** 顶栏全部展开，不再收入「更多」；按学习闭环依赖排序：画像 → 资源 → 路径 → 课程 → 答疑 → 数据 */
const primaryMenus = [
  { path: '/student/home', title: '首页', icon: HomeFilled },
  { path: '/student/profile-dialogue', title: '画像构建', icon: User },
  { path: '/student/resources', title: '资源中心', icon: Collection },
  { path: '/student/path', title: '学习路径', icon: Guide },
  { path: '/student/course-center', title: '课程', icon: Reading },
  { path: '/student/tutor', title: '答疑', icon: ChatDotRound },
  { path: '/student/dashboard', title: '学习数据', icon: DataAnalysis },
  { path: '/student/center', title: '我的', icon: Setting },
]

/** 班级详情页隐藏顶部图标导航，由页面内自己承载功能入口 */
const hideTopMenu = computed(() => route.path.startsWith('/student/class/'))

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/student/course-center') || path.startsWith('/student/course-study') || path.startsWith('/student/class/')) {
    return '/student/course-center'
  }
  if (path.startsWith('/student/resources')) return '/student/resources'
  if (path.startsWith('/student/path')) return '/student/path'
  if (path.startsWith('/student/dashboard')) return '/student/dashboard'
  if (path.startsWith('/student/profile-dialogue') || path.startsWith('/student/profile-voice-call')) {
    return '/student/profile-dialogue'
  }
  return path
})

onMounted(() => {
  if (userStore.isLoggedIn) {
    void userStore.fetchUser()
  }
})

function logout() {
  userStore.logout()
  window.location.replace(HOST_STUDENT_LOGIN)
}
</script>

<template>
  <div
    class="student-layout"
    :class="{
      'is-home': route.path === '/student/home',
      'is-class-immersive': hideTopMenu,
    }"
  >
    <header v-if="!hideTopMenu" class="top-nav">
      <div class="nav-inner">
        <router-link to="/student/home" class="logo">
          <img :src="BRAND_ICON" alt="智课共生" class="brand-mark" />
          <span>智课共生</span>
        </router-link>

        <el-menu
          mode="horizontal"
          :default-active="activeMenu"
          router
          class="top-menu"
          :ellipsis="false"
        >
          <el-menu-item v-for="m in primaryMenus" :key="m.path" :index="m.path">
            <el-icon><component :is="m.icon" /></el-icon>
            <span>{{ m.title }}</span>
          </el-menu-item>
        </el-menu>

        <div class="nav-actions">
          <router-link to="/student/center" class="header-user">
            <UserAvatar :size="32" />
            <span :class="{ 'name-placeholder': !userStore.hasRealName }">{{ userStore.displayName }}</span>
          </router-link>
          <el-button text type="danger" @click="logout">
            <el-icon><SwitchButton /></el-icon> 退出
          </el-button>
        </div>
      </div>
    </header>

    <main class="main" :class="{ 'route-fade-once': routeAnimating }">
      <router-view v-slot="{ Component, route: r }">
        <keep-alive>
          <component
            :is="Component"
            v-if="r.meta.keepAlive"
            :key="String(r.name || r.path)"
          />
        </keep-alive>
        <component
          :is="Component"
          v-if="!r.meta.keepAlive"
          :key="r.fullPath"
        />
      </router-view>
    </main>
  </div>
</template>

<style scoped lang="scss">
.student-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;

  &.is-home {
    background: #ffffff;
  }

  &.is-class-immersive .main {
    background: #eef3f8;
  }
}

.top-nav {
  position: relative;
  z-index: 1000;
  flex-shrink: 0;
  background: #fff;
  border-bottom: 1px solid $border-color;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.06);
}

.nav-inner {
  display: flex;
  align-items: center;
  height: 60px;
  padding: 0 20px;
  gap: 16px;
}

.logo {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: $text-primary;
  font-weight: 700;
  font-size: 16px;
  text-decoration: none;
  white-space: nowrap;

  &:hover {
    color: $primary;
  }
}

.brand-mark {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  object-fit: cover;
  display: block;
}

.top-menu {
  flex: 1;
  min-width: 0;
  height: 60px;
  border-bottom: none;
  background: transparent;

  :deep(.el-menu-item) {
    height: 60px;
    line-height: 60px;
    color: $text-secondary;
    border-bottom: 2px solid transparent;

    .el-icon {
      margin-right: 4px;
    }

    &:hover {
      color: $primary;
      background: #f1f5f9 !important;
    }
  }

  :deep(.el-menu-item.is-active) {
    color: $primary;
    font-weight: 600;
    border-bottom-color: $primary;
    background: transparent !important;
  }
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;

  .header-user {
    display: flex;
    align-items: center;
    gap: 8px;
    text-decoration: none;
    color: $text-primary;
    font-size: 14px;
    padding: 4px 8px;
    border-radius: 8px;
    transition: background 0.2s;

    &:hover {
      background: #f1f5f9;
    }

    .name-placeholder {
      color: $text-secondary;
      font-style: italic;
    }
  }
}

.main {
  flex: 1;
  min-height: 0;
  background: $bg-page;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior-y: contain;
  -webkit-overflow-scrolling: touch;
}

.student-layout.is-home .main {
  background: transparent;
}

@media (max-width: 1100px) {
  .nav-inner {
    padding: 0 12px;
    gap: 8px;
  }

  .logo {
    font-size: 14px;
    span { display: none; }
  }

  .top-menu {
    overflow-x: auto;

    :deep(.el-menu-item) {
      padding: 0 12px;
      font-size: 13px;
    }
  }

  .nav-actions .header-user span:not(.el-avatar) {
    display: none;
  }
}
</style>
