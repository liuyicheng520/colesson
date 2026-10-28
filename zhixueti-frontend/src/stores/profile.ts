import { defineStore } from 'pinia'
import { ref } from 'vue'
import { profileApi } from '@/api/profile'
import type { ProfileData } from '@/types'

export const useProfileStore = defineStore('profile', () => {
  const profile = ref<ProfileData | null>(null)
  const loading = ref(false)

  async function fetchProfile() {
    loading.value = true
    try {
      profile.value = await profileApi.get()
    } catch {
      /* 网络异常时不阻断页面，避免反复弹出 Network Error */
    } finally {
      loading.value = false
    }
  }

  function resetProfile() {
    profile.value = null
    loading.value = false
  }

  return { profile, loading, fetchProfile, resetProfile }
})
