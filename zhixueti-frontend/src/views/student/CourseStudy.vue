<script setup lang="ts">
defineOptions({ name: 'CourseStudy' })

import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Collection,
  Document,
  Guide,
  Monitor,
  QuestionFilled,
  Reading,
  Share,
  VideoCamera,
} from '@element-plus/icons-vue'
import { resourceApi } from '@/api/resource'
import { codeTypeLabel, TYPE_LABELS, formatResourceSummary } from '@/utils/resourceLabels'
import type { ResourceItem } from '@/types'
import EmptyState from '@/components/EmptyState.vue'
import {
  fetchPublishedLessons,
  openGongshengWorkbench,
  readGongshengProgress,
  type GongshengLesson,
} from '@/utils/gongshengProgress'

type ScopeTab = 'mine' | 'public' | 'gongsheng'

const router = useRouter()
const loading = ref(false)
const gongshengLoading = ref(false)
const scope = ref<ScopeTab>('gongsheng')
const resources = ref<ResourceItem[]>([])
const total = ref(0)
const gongshengLessons = ref<GongshengLesson[]>([])
const gongshengHint = ref('')
const progressMap = ref(readGongshengProgress())
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

const pageSubtitle = computed(() => {
  if (scope.value === 'public') return '浏览平台已发布公开课程资源，支持预览与深入学习'
  if (scope.value === 'gongsheng') return '对接智课共生教师发布的智课，查看课件解析资源与学习进度'
  return '查看由多智能体生成的个性化课程资源，跟踪学习进度并进入详情'
})

async function loadMineOrPublic() {
  loading.value = true
  try {
    const params = {
      type_code: filters.type_code || undefined,
      topic: filters.topic || undefined,
      page: filters.page,
      page_size: filters.page_size,
    }
    const data = scope.value === 'public'
      ? await resourceApi.listPublic(params)
      : await resourceApi.list(params)
    resources.value = data.items
    total.value = data.total
  } catch (err) {
    resources.value = []
    total.value = 0
    ElMessage.error('课程列表加载失败，请稍后重试')
    console.error(err)
  } finally {
    loading.value = false
  }
}

function lessonProgress(id: string): number {
  return Math.round(progressMap.value[id]?.percent || 0)
}

async function loadGongshengLessons() {
  gongshengLoading.value = true
  gongshengHint.value = ''
  gongshengLessons.value = []
  progressMap.value = readGongshengProgress()
  try {
    gongshengLessons.value = await fetchPublishedLessons()
    if (!gongshengLessons.value.length) {
      gongshengHint.value = '智课共生暂无已发布课程，请先在教师工作台完成发布。'
    }
  } catch (err) {
    gongshengHint.value = '暂时无法加载已发布智课。请确认宿主服务已启动，或先学习「我的共生课程 / 已发布课程资源」。'
    console.warn(err)
  } finally {
    gongshengLoading.value = false
  }
}

async function loadList() {
  if (scope.value === 'gongsheng') {
    await loadGongshengLessons()
    return
  }
  await loadMineOrPublic()
}

function switchScope(next: ScopeTab) {
  if (scope.value === next) return
  scope.value = next
  filters.page = 1
  void loadList()
}

function openResource(id: number) {
  router.push({
    name: 'ResourceDetail',
    params: { id: String(id) },
    query: scope.value === 'public' ? { scope: 'public' } : undefined,
  })
}

function openGongshengLesson(lesson: GongshengLesson) {
  openGongshengWorkbench(lesson.id)
}

function goResourceCenter() {
  router.push({ name: 'ResourceCenter' })
}

function goLearningPath() {
  router.push({ name: 'LearningPath' })
}

onMounted(() => {
  void loadList()
})
</script>

<template>
  <div class="page-container course-study">
    <div class="page-head">
      <div class="head-copy">
        <h2>课程中心（兼容页）</h2>
        <p class="subtitle">{{ pageSubtitle }}</p>
      </div>
      <div class="head-actions">
        <el-button :icon="Collection" @click="goResourceCenter">资源中心</el-button>
        <el-button type="primary" :icon="Guide" @click="goLearningPath">学习路径</el-button>
      </div>
    </div>

    <div class="scope-tabs">
      <button :class="{ active: scope === 'mine' }" type="button" @click="switchScope('mine')">我的共生课程</button>
      <button :class="{ active: scope === 'public' }" type="button" @click="switchScope('public')">已发布课程资源</button>
      <button :class="{ active: scope === 'gongsheng' }" type="button" @click="switchScope('gongsheng')">智课共生发布</button>
    </div>

    <div v-if="scope !== 'gongsheng'" class="filter-bar">
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
        placeholder="搜索课程主题"
        clearable
        style="width: 220px"
        @keyup.enter="() => { filters.page = 1; loadList() }"
      />
      <el-button type="primary" @click="() => { filters.page = 1; loadList() }">搜索</el-button>
    </div>

    <div v-if="scope !== 'gongsheng'" v-loading="loading" class="resource-grid">
      <div
        v-for="r in resources"
        :key="r.id"
        class="resource-card card"
        @click="openResource(r.id)"
      >
        <div class="card-icon">
          <el-icon :size="28"><component :is="typeIcons[r.type_code] || Document" /></el-icon>
        </div>
        <h4>{{ r.title }}</h4>
        <p>{{ formatResourceSummary(r.summary, r.topic).slice(0, 72) || r.topic }}</p>
        <div class="card-meta">
          <el-tag size="small">{{ r.type_code === 'code' ? codeTypeLabel(r.topic) : r.type_name }}</el-tag>
          <el-tag v-if="scope === 'public'" size="small" type="success">已发布</el-tag>
          <span v-if="r.author_name" class="author">{{ r.author_name }}</span>
        </div>
        <div class="card-foot">
          <span>课程资源</span>
          <strong>进入学习</strong>
        </div>
      </div>
      <EmptyState
        v-if="!loading && !resources.length"
        description="暂无课程资源，可先去资源中心生成或等待教师发布"
      />
    </div>

    <div v-else v-loading="gongshengLoading" class="resource-grid">
      <div
        v-for="lesson in gongshengLessons"
        :key="lesson.id"
        class="resource-card card"
        @click="openGongshengLesson(lesson)"
      >
        <div class="card-icon brand">
          <el-icon :size="28"><Reading /></el-icon>
        </div>
        <h4>{{ lesson.title }}</h4>
        <p>{{ lesson.summary || '共生 AI 课件解析生成的智课，点击进入沉浸学习工作台。' }}</p>
        <div class="card-meta">
          <el-tag v-if="lesson.subject" size="small">{{ lesson.subject }}</el-tag>
          <el-tag size="small" type="success">{{ lesson.status || 'published' }}</el-tag>
          <span v-if="lesson.resourceCount" class="author">资源 {{ lesson.resourceCount }}</span>
        </div>
        <div class="card-foot">
          <span>进度 {{ lessonProgress(lesson.id) }}%</span>
          <strong>打开工作台</strong>
        </div>
        <div class="mini-progress"><span :style="{ width: `${lessonProgress(lesson.id)}%` }" /></div>
      </div>
      <EmptyState
        v-if="!gongshengLoading && !gongshengLessons.length"
        :description="gongshengHint || '暂无智课'"
      />
    </div>

    <el-pagination
      v-if="scope !== 'gongsheng' && total > 0"
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
.course-study {
  .page-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 18px;
    flex-wrap: wrap;
  }

  h2 {
    margin: 0;
    font-size: 22px;
    font-weight: 700;
    color: $text-primary;
  }

  .subtitle {
    margin: 8px 0 0;
    color: $text-secondary;
    line-height: 1.6;
  }

  .head-actions {
    display: flex;
    gap: 10px;
  }
}

.scope-tabs {
  display: inline-flex;
  gap: 6px;
  padding: 4px;
  margin-bottom: 16px;
  border-radius: 10px;
  background: #eef2ff;
  border: 1px solid $border-color;

  button {
    border: none;
    background: transparent;
    color: $text-secondary;
    padding: 8px 14px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;

    &.active {
      background: #fff;
      color: $primary;
      font-weight: 700;
      box-shadow: $shadow-card;
    }
  }
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}

.resource-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
  min-height: 180px;
}

.resource-card {
  background: $bg-card;
  border: 1px solid $border-color;
  border-radius: $radius-lg;
  padding: 16px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
  box-shadow: $shadow-card;

  &:hover {
    border-color: rgba(37, 99, 235, 0.35);
    box-shadow: 0 8px 24px rgba(37, 99, 235, 0.08);
    transform: translateY(-2px);
  }

  h4 {
    margin: 12px 0 8px;
    font-size: 16px;
    color: $text-primary;
    line-height: 1.4;
  }

  p {
    margin: 0;
    min-height: 44px;
    color: $text-secondary;
    font-size: 13px;
    line-height: 1.6;
  }
}

.card-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: #eff6ff;
  color: $primary;

  &.brand {
    background: linear-gradient(135deg, #dbeafe, #eff6ff);
  }
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-top: 12px;

  .author {
    color: $text-secondary;
    font-size: 12px;
  }
}

.card-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid $border-color;
  color: $text-secondary;
  font-size: 12px;

  strong {
    color: $primary;
    font-weight: 600;
  }
}

.mini-progress {
  margin-top: 10px;
  height: 6px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;

  > span {
    display: block;
    height: 100%;
    background: #2563eb;
  }
}
</style>
