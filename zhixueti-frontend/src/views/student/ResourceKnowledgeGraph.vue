<script setup lang="ts">
import { onActivated, onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { resourceApi } from '@/api/resource'
import {
  resourcesToNoteMeta,
  type GraphNoteMeta,
} from '@/lib/resourceKnowledgeGraph'
import ResourceKnowledgeGraphView from '@/components/ResourceKnowledgeGraphView.vue'
import type { ResourceItem } from '@/types'

defineOptions({ name: 'ResourceKnowledgeGraph' })

const router = useRouter()
const loading = ref(false)
const errorMsg = ref('')
const notes = ref<GraphNoteMeta[]>([])
const focusId = ref<string | null>(null)

const empty = computed(() => !loading.value && notes.value.length === 0)

async function loadAllResources() {
  loading.value = true
  errorMsg.value = ''
  try {
    const all: ResourceItem[] = []
    let page = 1
    const pageSize = 100
    // 上限与构图 maxNotes 对齐，避免一次拉太多
    while (all.length < 320) {
      const data = await resourceApi.list({ page, page_size: pageSize })
      all.push(...(data.items || []))
      if (!data.items?.length || all.length >= data.total || page >= (data.pages || 1)) break
      page += 1
    }
    notes.value = resourcesToNoteMeta(all)
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '加载资源失败'
    notes.value = []
  } finally {
    loading.value = false
  }
}

function onOpen(relPath: string) {
  const id = Number(relPath)
  if (!Number.isFinite(id) || id <= 0) return
  router.push({ name: 'ResourceDetail', params: { id: String(id) } })
}

function goBack() {
  router.push({ name: 'ResourceCenter' })
}

function goGenerate() {
  router.push({ name: 'ResourceCenter' })
}

let hydrated = false
onActivated(() => {
  if (hydrated) void loadAllResources()
})
onMounted(() => {
  Promise.resolve(loadAllResources()).finally(() => { hydrated = true })
})
</script>

<template>
  <div class="kg-page">
    <div class="kg-top">
      <el-button :icon="ArrowLeft" text @click="goBack">返回资源中心</el-button>
      <el-button text type="primary" :loading="loading" @click="loadAllResources">刷新</el-button>
    </div>

    <div v-if="loading && !notes.length" class="kg-boot" role="status">正在整理你的学习资源…</div>
    <div v-else-if="errorMsg" class="kg-error">
      <p>{{ errorMsg }}</p>
      <el-button type="primary" @click="loadAllResources">重试</el-button>
    </div>
    <div v-else-if="empty" class="kg-empty card">
      <h2>知识星图还是空的</h2>
      <p>去资源中心生成讲义、习题、思维导图等后，这里会把它们连成知识网络。</p>
      <el-button type="primary" @click="goGenerate">去生成资源</el-button>
    </div>
    <ResourceKnowledgeGraphView
      v-else
      :notes="notes"
      :focus-id="focusId"
      @open="onOpen"
      @focus-consumed="focusId = null"
    />
  </div>
</template>

<style scoped>
.kg-page {
  display: flex;
  flex-direction: column;
  gap: 10px;
  /* 确定高度：min-height 会让 stage 的 flex:1 无界，画布撑到数千像素、节点落到视口外 */
  height: calc(100vh - 120px);
  padding: 8px 4px 20px;
}
.kg-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.kg-boot,
.kg-error,
.kg-empty {
  display: grid;
  place-items: center;
  gap: 12px;
  min-height: 360px;
  text-align: center;
  color: #64748b;
}
.kg-empty.card {
  border: 1px solid #dbe4f0;
  border-radius: 16px;
  background: linear-gradient(180deg, #f8fbff, #eef4ff);
  padding: 40px 24px;
}
.kg-empty h2 {
  margin: 0;
  font-size: 20px;
  color: #0f172a;
}
.kg-empty p {
  margin: 0;
  max-width: 28em;
  line-height: 1.6;
}
.kg-error {
  color: #b91c1c;
}
</style>
