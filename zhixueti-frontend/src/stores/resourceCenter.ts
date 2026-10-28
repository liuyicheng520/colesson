import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ResourceItem } from '@/types'

/** 资源中心列表状态缓存 — 详情页返回时恢复筛选与滚动位置 */
export const useResourceCenterStore = defineStore('resourceCenter', () => {
  const filters = ref({ type_code: '', topic: '', page: 1, page_size: 20 })
  const resources = ref<ResourceItem[]>([])
  const total = ref(0)
  const scrollTop = ref(0)
  const lastGenForm = ref<{
    topic: string
    goal: string
    resource_types: string[]
    difficulty: number
    node_id?: number
    ignore_profile?: boolean
    supplement?: string
    use_scene?: string
    content_focus?: string[]
    content_length?: string
    special_requirements?: string
  } | null>(null)
  const lastTaskError = ref('')
  const cached = ref(false)

  function saveListState(
    f: typeof filters.value,
    items: ResourceItem[],
    t: number,
    scroll: number,
  ) {
    filters.value = { ...f }
    resources.value = items
    total.value = t
    scrollTop.value = scroll
    cached.value = true
  }

  function saveGenForm(form: NonNullable<typeof lastGenForm.value>) {
    lastGenForm.value = {
      ...form,
      resource_types: [...form.resource_types],
      content_focus: [...(form.content_focus || [])],
    }
  }

  function setTaskError(msg: string) {
    lastTaskError.value = msg
  }

  function clearCache() {
    cached.value = false
    scrollTop.value = 0
    resources.value = []
    total.value = 0
    filters.value = { type_code: '', topic: '', page: 1, page_size: 20 }
    lastGenForm.value = null
    lastTaskError.value = ''
  }

  return {
    filters,
    resources,
    total,
    scrollTop,
    lastGenForm,
    lastTaskError,
    cached,
    saveListState,
    saveGenForm,
    setTaskError,
    clearCache,
  }
})
