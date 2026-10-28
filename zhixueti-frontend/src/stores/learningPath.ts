import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { PathSummary } from '@/api/path'
import type { PathData } from '@/types'

/** 学习路径会话缓存 — 切页返回时复用，避免重复请求 */
export const useLearningPathStore = defineStore('learningPath', () => {
  const paths = ref<PathSummary[]>([])
  const currentPath = ref<PathData | null>(null)
  const selectedNodeId = ref<number | null>(null)
  const viewMode = ref<'timeline' | 'graph'>('timeline')
  const planForm = ref({
    goal: '掌握机器学习基础',
    domain: 'machine_learning',
    title: '',
    ignore_profile: false,
    supplement: '',
  })
  const cached = ref(false)
  const cachedAt = ref(0)

  function saveSnapshot(payload: {
    paths: PathSummary[]
    currentPath: PathData | null
    selectedNodeId: number | null
    viewMode: 'timeline' | 'graph'
    planForm: typeof planForm.value
  }) {
    paths.value = payload.paths
    currentPath.value = payload.currentPath
    selectedNodeId.value = payload.selectedNodeId
    viewMode.value = payload.viewMode
    planForm.value = { ...payload.planForm }
    cached.value = Boolean(payload.currentPath)
    cachedAt.value = Date.now()
  }

  function patchCurrentPath(path: PathData, selectedId?: number | null) {
    currentPath.value = path
    if (selectedId != null) selectedNodeId.value = selectedId
    cached.value = true
    cachedAt.value = Date.now()
  }

  function clearCache() {
    paths.value = []
    currentPath.value = null
    selectedNodeId.value = null
    viewMode.value = 'timeline'
    planForm.value = {
      goal: '掌握机器学习基础',
      domain: 'machine_learning',
      title: '',
      ignore_profile: false,
      supplement: '',
    }
    cached.value = false
    cachedAt.value = 0
  }

  return {
    paths,
    currentPath,
    selectedNodeId,
    viewMode,
    planForm,
    cached,
    cachedAt,
    saveSnapshot,
    patchCurrentPath,
    clearCache,
  }
})
