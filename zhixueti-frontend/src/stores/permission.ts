import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { adminApi, type AdminMenuItem } from '@/api/admin'

export const usePermissionStore = defineStore('permission', () => {
  const permissions = ref<string[]>([])
  const menus = ref<AdminMenuItem[]>([])
  const loaded = ref(false)
  const loading = ref(false)

  const permissionSet = computed(() => new Set(permissions.value))

  function hasPerm(code: string): boolean {
    return permissionSet.value.has(code)
  }

  async function loadAdminContext(force = false) {
    if (loaded.value && !force) return
    loading.value = true
    try {
      const data = await adminApi.me()
      permissions.value = data.permissions
      menus.value = data.menus
      loaded.value = true
    } finally {
      loading.value = false
    }
  }

  function reset() {
    permissions.value = []
    menus.value = []
    loaded.value = false
    loading.value = false
  }

  return {
    permissions,
    menus,
    loaded,
    loading,
    hasPerm,
    loadAdminContext,
    reset,
  }
})
