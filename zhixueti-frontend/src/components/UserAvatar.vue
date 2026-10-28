<script setup lang="ts">
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'
import { resolveAvatarUrl } from '@/utils/avatar'

const props = withDefaults(
  defineProps<{
    size?: number
    shape?: 'circle' | 'square'
    fallback?: string
  }>(),
  { size: 36, shape: 'circle' },
)

const userStore = useUserStore()

const src = computed(() =>
  resolveAvatarUrl(userStore.userInfo?.avatar_url, userStore.avatarVersion),
)

const fallbackText = computed(
  () => props.fallback || userStore.userInfo?.real_name?.[0] || userStore.userInfo?.nickname?.[0] || userStore.userInfo?.username?.[0] || 'U',
)
</script>

<template>
  <el-avatar :size="size" :src="src" :shape="shape" class="user-avatar">
    {{ fallbackText }}
  </el-avatar>
</template>

<style scoped lang="scss">
.user-avatar {
  flex-shrink: 0;
  background: $primary;
  color: #fff;
  font-weight: 600;
}
</style>
