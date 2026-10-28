<script setup lang="ts">
import { onActivated, onMounted, ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Document, Share, Reading, VideoCamera, Monitor, QuestionFilled } from '@element-plus/icons-vue'
import { resourceApi } from '@/api/resource'
import { codeTypeLabel, TYPE_LABELS, formatResourceSummary } from '@/utils/resourceLabels'
import type { ResourceItem } from '@/types'
import EmptyState from '@/components/EmptyState.vue'

defineOptions({ name: 'ResourceSquare' })

const router = useRouter()
const loading = ref(false)
const resources = ref<ResourceItem[]>([])
const total = ref(0)
const filters = reactive({ type_code: '', topic: '', page: 1, page_size: 20 })

const typeIcons: Record<string, unknown> = {
  document: Document,
  question: QuestionFilled,
  mindmap: Share,
  reading: Reading,
  video: VideoCamera,
  code: Monitor,
}

const typeLabels = TYPE_LABELS

async function loadList() {
  loading.value = true
  try {
    const data = await resourceApi.listPublic({
      type_code: filters.type_code || undefined,
      topic: filters.topic || undefined,
      page: filters.page,
      page_size: filters.page_size,
    })
    resources.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function openDetail(id: number) {
  router.push({
    name: 'ResourceDetail',
    params: { id: String(id) },
    query: { scope: 'public' },
  })
}

function goBack() {
  router.push({ name: 'ResourceCenter' })
}

function goKnowledgeGraph() {
  router.push({ name: 'ResourceKnowledgeGraph' })
}

let hydrated = false
onActivated(() => {
  // keep-alive 返回时刷新资源列表
  if (hydrated) void loadList()
})
onMounted(() => {
  loadList().finally(() => { hydrated = true })
})
</script>

<template>
  <div class="page-container">
    <div class="page-head">
      <div class="head-left">
        <el-button :icon="ArrowLeft" text @click="goBack">返回个人中心</el-button>
        <div>
          <h2>资源广场</h2>
          <p class="subtitle">全平台已发布公开资源，支持完整预览</p>
        </div>
      </div>
      <div class="head-right">
        <button class="kg-btn" type="button" @click="goKnowledgeGraph">
          <el-icon class="kg-btn-icon"><Share /></el-icon>
          <span>知识图谱</span>
          <span class="kg-btn-arrow">→</span>
        </button>
      </div>
    </div>

    <div class="filter-bar">
      <div class="filter-left">
        <el-select
          v-model="filters.type_code"
          placeholder="资源类型"
          clearable
          style="width: 140px"
          @change="() => { filters.page = 1; loadList() }"
        >
          <el-option v-for="(label, code) in typeLabels" :key="code" :label="label" :value="code" />
        </el-select>
        <el-input
          v-model="filters.topic"
          placeholder="搜索主题"
          clearable
          style="width: 200px"
          @keyup.enter="() => { filters.page = 1; loadList() }"
        />
        <el-button type="primary" @click="() => { filters.page = 1; loadList() }">搜索</el-button>
        <el-select
          v-model="filters.page_size"
          style="width: 120px"
          @change="() => { filters.page = 1; loadList() }"
        >
          <el-option :value="20" label="每页 20 条" />
          <el-option :value="40" label="每页 40 条" />
          <el-option :value="60" label="每页 60 条" />
        </el-select>
      </div>
    </div>

    <div v-loading="loading" class="resource-grid">
      <div
        v-for="r in resources"
        :key="r.id"
        class="resource-card card stagger-item"
        @click="openDetail(r.id)"
      >
        <div class="card-icon">
          <el-icon :size="28"><component :is="typeIcons[r.type_code] || Document" /></el-icon>
        </div>
        <h4>{{ r.title }}</h4>
        <p>{{ formatResourceSummary(r.summary, r.topic).slice(0, 60) || r.topic }}</p>
        <div class="card-meta">
          <el-tag size="small">{{ r.type_code === 'code' ? codeTypeLabel(r.topic) : r.type_name }}</el-tag>
          <el-tag size="small" type="success">已发布</el-tag>
          <span v-if="r.author_name" class="author">{{ r.author_name }}</span>
        </div>
      </div>
      <EmptyState v-if="!loading && !resources.length" description="暂无已发布公开资源" />
    </div>

    <el-pagination
      v-if="total > 0"
      v-model:current-page="filters.page"
      v-model:page-size="filters.page_size"
      :page-sizes="[20, 40, 60]"
      :total="total"
      layout="total, sizes, prev, pager, next"
      @current-change="loadList"
      @size-change="() => { filters.page = 1; loadList() }"
    />
  </div>
</template>

<style scoped lang="scss">
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;

  .head-left {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .head-right {
    display: flex;
    align-items: center;
    padding-top: 6px;
  }

  h2 {
    margin: 0 0 4px;
    font-size: 22px;
    font-weight: 700;
  }

  .subtitle {
    margin: 0;
    font-size: 13px;
    color: $text-secondary;
  }
}

.kg-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 22px;
  border: none;
  border-radius: 999px;
  cursor: pointer;
  overflow: hidden;
  color: #fff;
  font-family: inherit;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.02em;
  background: linear-gradient(135deg, #6366f1 0%, #3b82f6 45%, #06b6d4 100%);
  background-size: 170% 170%;
  background-position: 0% 50%;
  box-shadow: 0 6px 20px rgba(59, 130, 246, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.25);
  transition: transform 0.2s ease, box-shadow 0.2s ease, background-position 0.45s ease;

  &::after {
    content: '';
    position: absolute;
    top: 0;
    left: -70%;
    width: 40%;
    height: 100%;
    background: linear-gradient(100deg, transparent, rgba(255, 255, 255, 0.38), transparent);
    transform: skewX(-20deg);
    animation: kg-shine 3.2s ease-in-out infinite;
  }

  &:hover {
    transform: translateY(-2px);
    background-position: 95% 50%;
    box-shadow: 0 10px 28px rgba(99, 102, 241, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.25);

    .kg-btn-arrow {
      transform: translateX(3px);
    }
  }

  &:active {
    transform: translateY(0) scale(0.97);
  }

  .kg-btn-icon {
    font-size: 16px;
  }

  .kg-btn-arrow {
    font-size: 13px;
    opacity: 0.85;
    transition: transform 0.2s ease;
  }
}

@keyframes kg-shine {
  0%, 55% {
    left: -70%;
  }
  85%, 100% {
    left: 135%;
  }
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
}

.filter-left {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.resource-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
  min-height: 200px;
}

.resource-card {
  padding: 20px;
  cursor: pointer;
  transition: transform 0.2s ease-out, box-shadow 0.2s ease-out;

  &:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(37, 99, 235, 0.12);
  }

  h4 { margin: 12px 0 8px; font-size: 15px; }
  p { font-size: 13px; color: $text-secondary; margin-bottom: 12px; }
  .card-icon { color: $primary; }
  .card-meta {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }
  .author {
    font-size: 12px;
    color: $text-secondary;
    margin-left: auto;
  }
}
</style>
