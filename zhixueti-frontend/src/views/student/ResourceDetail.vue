<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { resourceApi } from '@/api/resource'
import { useStudySession } from '@/composables/useStudySession'
import { pathApi } from '@/api/path'
import { getTypeLabel, formatResourceSummary, tryParseCodePayload } from '@/utils/resourceLabels'
import type { ResourceItem } from '@/types'
import MarkdownViewer from '@/components/MarkdownViewer.vue'
import MindMapViewer from '@/components/MindMapViewer.vue'
import MermaidViewer from '@/components/MermaidViewer.vue'
import QuestionViewer from '@/components/QuestionViewer.vue'
import PracticeViewer from '@/components/PracticeViewer.vue'
import EmptyState from '@/components/EmptyState.vue'
import { normalizeAnimationSlides } from '@/utils/animationSlides'

const route = useRoute()
const router = useRouter()
const resource = ref<ResourceItem | null>(null)
const loading = ref(true)
const loadError = ref('')
const completing = ref(false)

/** 来自资源广场时为公开预览模式 */
const isPublicScope = computed(
  () => route.query.scope === 'public' || route.query.from === 'square',
)

const nodeId = computed(() => {
  const id = Number(route.query.node_id)
  return Number.isFinite(id) && id > 0 ? id : null
})
const pathId = computed(() => {
  const id = Number(route.query.path_id)
  return Number.isFinite(id) && id > 0 ? id : null
})

const detail = computed(() => resource.value?.detail || {})

/** 讲义正文：优先 detail.content_md；缺失时用 summary 兜底（历史孤儿资源） */
const documentMarkdown = computed(() => {
  const md = detail.value.content_md
  if (typeof md === 'string' && md.trim()) return md
  const summary = resource.value?.summary
  if (typeof summary === 'string' && summary.trim() && /[#*`\-]/.test(summary)) return summary
  return '暂无内容'
})

/** 头部摘要：讲义不把整篇 Markdown 堆在标题下；代码类避免展示 JSON 原文 */
const headerSummary = computed(() => {
  if (!resource.value) return ''
  if (resource.value.type_code === 'document') {
    const md = typeof detail.value.content_md === 'string' ? detail.value.content_md : ''
    if (md.trim()) {
      const plain = md.replace(/[#>*_`\[\]()]/g, ' ').replace(/\s+/g, ' ').trim()
      return plain.slice(0, 120) + (plain.length > 120 ? '…' : '')
    }
    return '专业课程讲义'
  }
  if (resource.value.type_code === 'code') {
    const d = detail.value as Record<string, unknown>
    const expl = typeof d.explanation === 'string' ? d.explanation : ''
    if (expl.trim() && !tryParseCodePayload(expl)) {
      return expl.slice(0, 120) + (expl.length > 120 ? '…' : '')
    }
    return formatResourceSummary(resource.value.summary, resource.value.topic)
  }
  return formatResourceSummary(resource.value.summary, resource.value.topic)
})

const typeDisplayName = computed(() => {
  if (!resource.value) return ''
  if (resource.value.type_code === 'code') return '实战演练'
  return resource.value.type_name || getTypeLabel(resource.value.type_code, resource.value.topic)
})

const resolvedCodeDetail = computed(() => {
  const d = { ...(detail.value as Record<string, unknown>) }
  const fromExpl = tryParseCodePayload(d.explanation)
  const fromCode = tryParseCodePayload(d.code_content)
  const parsed = fromCode || fromExpl
  if (!parsed) return d
  return {
    ...d,
    ...parsed,
    code_content: parsed.code_content ?? d.code_content,
    explanation:
      typeof parsed.explanation === 'string' && !String(parsed.explanation).trim().startsWith('{')
        ? parsed.explanation
        : fromExpl
          ? ''
          : d.explanation,
    language: parsed.language || d.language,
    practice_items: parsed.practice_items ?? d.practice_items,
    practice_type: parsed.practice_type ?? d.practice_type,
    objective: parsed.objective ?? d.objective,
  }
})

const isProgrammingCode = computed(() => {
  const d = resolvedCodeDetail.value
  const items = d.practice_items
  const hasPractice = Array.isArray(items) && items.length > 0
  if (hasPractice || d.content_mode === 'practice') return false
  return d.is_programming !== false
})

const nodeDescMap = computed(() => {
  const nodes = (detail.value.nodes as Array<{ label: string; description?: string }>) || []
  const map: Record<string, string> = {}
  nodes.forEach((n) => {
    if (n.label && n.description) map[n.label] = n.description
  })
  return map
})

const hasMindmapNodes = computed(() => {
  const nodes = detail.value.nodes as unknown[] | undefined
  return Array.isArray(nodes) && nodes.length > 0
})

const animationSlides = computed(() =>
  normalizeAnimationSlides(detail.value as Record<string, unknown>),
)

const immersiveLectureLink = computed(() => {
  if (resource.value?.type_code !== 'video') return null
  const d = detail.value as Record<string, unknown>
  const ad = (d.animation_data as Record<string, unknown> | undefined) || {}
  const lecture = (ad.lecture || d.lecture) as { lecture_id?: string; slides?: unknown[] } | undefined
  const sessionNo = ad.session_no || d.session_no
  const lectureId =
    ad.lecture_id || d.lecture_id || lecture?.lecture_id || `resource-${resource.value.id}`
  const hasSlides =
    (Array.isArray(lecture?.slides) && lecture.slides.length > 0) || animationSlides.value.length > 0
  if (!hasSlides && !sessionNo) return null
  return {
    path: `/student/tutor/lecture/${lectureId}`,
    query: {
      ...(sessionNo ? { session_no: String(sessionNo) } : {}),
      from: 'resource',
      resource_id: String(resource.value.id),
      ...(nodeId.value ? { node_id: String(nodeId.value) } : {}),
      ...(pathId.value ? { path_id: String(pathId.value) } : {}),
      ...(isPublicScope.value ? { scope: 'public' } : {}),
    },
  }
})

function enterImmersiveLecture() {
  if (!immersiveLectureLink.value) return
  router.push(immersiveLectureLink.value)
}

function goBack() {
  if (isPublicScope.value) {
    router.push({ name: 'ResourceSquare' })
    return
  }
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push({ name: 'ResourceCenter' })
  }
}

async function completeAndReturn() {
  if (!nodeId.value || !resource.value) return
  completing.value = true
  try {
    await pathApi.updateNodeProgress(nodeId.value, {
      status: 2,
      study_duration_sec: 300,
      resource_id: resource.value.id,
      mark_resource_done: true,
    })
    ElMessage.success('本资源已标记为学完，可在路径页查看进度')
    if (pathId.value) router.push('/student/path')
  } catch {
    ElMessage.error('进度更新失败')
  } finally {
    completing.value = false
  }
}

// 资源学习会话：记录真实查看时长
const studySession = useStudySession()
let sessionIdPending = true

onBeforeUnmount(() => {
  sessionIdPending = false
  void studySession.end()
})

onMounted(async () => {
  const id = Number(route.params.id)
  if (!Number.isFinite(id) || id <= 0) {
    loadError.value = '无效的资源 ID'
    loading.value = false
    sessionIdPending = false
    return
  }
  void studySession.start({ session_type: 'resource_view' }).then(() => {
    if (sessionIdPending) void studySession.track({ event_type: 'resource_open', target_id: id })
  })
  try {
    // 广场预览走公开接口，个人中心走私有接口
    resource.value = isPublicScope.value
      ? await resourceApi.getPublic(id)
      : await resourceApi.get(id)
    if (!isPublicScope.value && nodeId.value) {
      await pathApi.updateNodeProgress(nodeId.value, { status: 2 })
    }
    // AI视频讲解：直接进入图二沉浸式讲义（幻灯片 + AI 教师），不再停在动画预览
    if (resource.value?.type_code === 'video') {
      const d = (resource.value.detail || {}) as Record<string, unknown>
      const ad = (d.animation_data as Record<string, unknown> | undefined) || {}
      const lecture = (ad.lecture || d.lecture) as { lecture_id?: string; slides?: unknown[] } | undefined
      const sessionNo = ad.session_no || d.session_no
      const lectureId =
        ad.lecture_id || d.lecture_id || lecture?.lecture_id || `resource-${resource.value.id}`
      const slides = normalizeAnimationSlides(d)
      const hasContent =
        (Array.isArray(lecture?.slides) && lecture.slides.length > 0) || slides.length > 0
      if (hasContent) {
        await router.replace({
          path: `/student/tutor/lecture/${lectureId}`,
          query: {
            ...(sessionNo ? { session_no: String(sessionNo) } : {}),
            from: 'resource',
            resource_id: String(resource.value.id),
            ...(nodeId.value ? { node_id: String(nodeId.value) } : {}),
            ...(pathId.value ? { path_id: String(pathId.value) } : {}),
            ...(isPublicScope.value ? { scope: 'public' } : {}),
          },
        })
        return
      }
    }
  } catch {
    loadError.value = isPublicScope.value ? '资源未发布或不存在' : '资源不存在或加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-loading="loading" class="page-container detail-page">
    <nav v-if="resource" class="detail-nav">
      <el-button :icon="ArrowLeft" @click="goBack">返回</el-button>
      <el-breadcrumb separator="/">
        <el-breadcrumb-item>
          <a
            class="crumb-link"
            @click.prevent="router.push({ name: isPublicScope ? 'ResourceSquare' : 'ResourceCenter' })"
          >
            {{ isPublicScope ? '资源广场' : '个人资源中心' }}
          </a>
        </el-breadcrumb-item>
        <el-breadcrumb-item>{{ resource.topic }}</el-breadcrumb-item>
        <el-breadcrumb-item>{{ typeDisplayName }}</el-breadcrumb-item>
      </el-breadcrumb>
    </nav>

    <EmptyState v-if="!loading && loadError" :description="loadError" />
    <div v-else-if="resource" class="detail-content">
      <div class="detail-header card">
        <el-tag>{{ typeDisplayName }}</el-tag>
        <el-tag v-if="isPublicScope" type="success" size="small" style="margin-left: 8px">公开</el-tag>
        <h2>{{ resource.title }}</h2>
        <p v-if="headerSummary">{{ headerSummary }}</p>
        <div class="meta">
          <span>主题: {{ resource.topic }}</span>
          <span>难度: {{ resource.difficulty }}/5</span>
          <span v-if="resource.author_name && isPublicScope">作者: {{ resource.author_name }}</span>
          <span v-if="resource.citation_count">引用: {{ resource.citation_count }}</span>
        </div>
      </div>

      <div class="detail-body card">
        <MarkdownViewer
          v-if="resource.type_code === 'document'"
          :content="documentMarkdown"
        />

        <template v-else-if="resource.type_code === 'mindmap'">
          <!-- 有结构化节点时优先用树形组件，交互更稳定 -->
          <MindMapViewer
            v-if="hasMindmapNodes"
            :data="(detail.map_data as Record<string, unknown>) || null"
            :nodes="(detail.nodes as []) || undefined"
            :edges="(detail.edges as []) || undefined"
          />
          <MermaidViewer
            v-else-if="detail.mermaid"
            :code="detail.mermaid as string"
            :node-descriptions="nodeDescMap"
          />
          <EmptyState v-else description="暂无思维导图内容" />
        </template>

        <div v-else-if="resource.type_code === 'reading'" class="reading-list">
          <div class="reading-intro">
            <strong>建议学习方式：</strong>先读正文掌握概念，再对照阅读要点自检，最后按推荐书目/文章深入；文末思考题用于检验迁移。
          </div>
          <article v-for="(item, i) in (detail.reading_list as Record<string, unknown>[])" :key="i" class="reading-item">
            <div class="reading-heading">
              <span class="reading-index">{{ i + 1 }}</span>
              <div>
                <h4>{{ item.title }}</h4>
                <p class="reading-meta">{{ item.author || '智课共生学习导读' }} · {{ item.difficulty || '基础' }} · 约 {{ item.estimated_minutes || 10 }} 分钟</p>
              </div>
            </div>
            <p v-if="item.summary" class="reading-summary">{{ item.summary }}</p>
            <div v-if="item.content" class="reading-body">
              <strong>阅读正文</strong>
              <p v-for="(para, pi) in String(item.content).split(/\n+/).filter(Boolean)" :key="pi">{{ para }}</p>
            </div>
            <div v-if="Array.isArray(item.tags) && item.tags.length" class="reading-tags">
              <el-tag v-for="tag in item.tags" :key="String(tag)" size="small" effect="plain">{{ tag }}</el-tag>
            </div>
            <div v-if="Array.isArray(item.key_points) && item.key_points.length" class="key-points">
              <strong>阅读要点</strong>
              <ul><li v-for="point in item.key_points" :key="String(point)">{{ point }}</li></ul>
            </div>
            <div
              v-if="Array.isArray(item.recommendations) && item.recommendations.length"
              class="recommendations"
            >
              <strong>建议阅读</strong>
              <ul>
                <li v-for="(rec, ri) in (item.recommendations as Record<string, unknown>[])" :key="ri">
                  <span class="rec-type">{{ rec.type || '资料' }}</span>
                  <template v-if="rec.url">
                    <a :href="String(rec.url)" target="_blank" rel="noopener">{{ rec.title }}</a>
                  </template>
                  <template v-else>
                    <em>{{ rec.title }}</em>
                  </template>
                  <span v-if="rec.author" class="rec-author"> — {{ rec.author }}</span>
                  <span v-if="rec.why" class="rec-why">：{{ rec.why }}</span>
                </li>
              </ul>
            </div>
            <div v-if="item.reflection" class="reflection"><strong>想一想：</strong>{{ item.reflection }}</div>
            <a v-if="item.url" class="reading-link" :href="String(item.url)" target="_blank" rel="noopener">阅读原文 →</a>
          </article>
        </div>

        <div v-else-if="resource.type_code === 'video'">
          <div v-if="immersiveLectureLink" class="immersive-link-bar">
            <el-button type="primary" size="large" @click="enterImmersiveLecture">
              进入完整沉浸式讲解
            </el-button>
            <span class="immersive-hint">正在打开 AI 教师讲义页（幻灯片 + 旁白）…</span>
          </div>
          <video
            v-if="detail.video_url"
            :src="String(detail.video_url)"
            controls
            class="video-player"
          />
          <EmptyState
            v-else-if="!immersiveLectureLink"
            description="暂无视频讲解内容，请重新生成「AI视频讲解」资源"
          />
        </div>

        <div v-else-if="resource.type_code === 'code'">
          <template v-if="isProgrammingCode">
            <el-tag>{{ resolvedCodeDetail.language || 'python' }}</el-tag>
            <pre class="code-block">{{ resolvedCodeDetail.code_content }}</pre>
            <p v-if="resolvedCodeDetail.explanation" class="explain">{{ resolvedCodeDetail.explanation }}</p>
          </template>
          <PracticeViewer
            v-else
            :items="(resolvedCodeDetail.practice_items as []) || []"
            :explanation="resolvedCodeDetail.explanation as string"
            :practice-type="resolvedCodeDetail.practice_type as string"
            :objective="resolvedCodeDetail.objective as string"
            :resource-key="route.params.id as string"
          />
        </div>

        <QuestionViewer
          v-else-if="resource.type_code === 'question'"
          :questions="(detail.questions as []) || []"
        />

        <EmptyState v-else description="暂不支持预览此类型资源" />
      </div>

      <div v-if="nodeId && !isPublicScope" class="path-action card">
        <p>学完本资源后标记进度；该知识点下全部资源都学完后，节点才会变为「已完成」。</p>
        <el-button type="success" :loading="completing" @click="completeAndReturn">
          标记本资源已学完
        </el-button>
        <el-button link type="primary" @click="router.push('/student/path')">返回路径</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.detail-page { padding-top: 0; }

.detail-nav {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  padding: 12px 0;
  position: sticky;
  top: 0;
  z-index: 20;
  background: $bg-page;

  .crumb-link {
    color: $primary;
    cursor: pointer;
    text-decoration: none;
    &:hover { text-decoration: underline; }
  }
}

.detail-header {
  padding: 24px;
  margin-bottom: 16px;
  h2 { margin: 12px 0 8px; }
  .meta { display: flex; gap: 16px; font-size: 13px; color: $text-secondary; margin-top: 12px; flex-wrap: wrap; }
}

.detail-body { padding: 24px; min-height: 300px; }

.video-player {
  width: 100%;
  max-height: 480px;
  border-radius: 8px;
  background: #000;
  margin-bottom: 16px;
}

.path-action {
  margin-top: 16px;
  padding: 16px 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  p { margin: 0; font-size: 13px; color: $text-secondary; flex: 1; }
}

.reading-list { display: grid; gap: 16px; }
.reading-intro { padding: 13px 16px; color: #1d4ed8; background: #eff6ff; border-radius: 10px; line-height: 1.6; }
.reading-item { padding: 20px; border: 1px solid #e5eaf3; border-radius: 12px; background: #fff; box-shadow: 0 3px 10px rgba(31, 55, 92, .04); line-height: 1.75;
  h4 { margin: 0 0 3px; font-size: 18px; }
}
.reading-heading { display: flex; gap: 12px; align-items: flex-start; }
.reading-index { display: grid; place-items: center; flex: 0 0 30px; width: 30px; height: 30px; border-radius: 50%; background: #e8f1ff; color: $primary; font-weight: 700; }
.reading-meta { margin: 0; color: $text-secondary; font-size: 13px; }
.reading-summary { margin: 14px 0 8px; color: $text-secondary; }
.reading-body {
  margin: 10px 0 14px; padding: 14px 16px; background: #fafbfd; border: 1px solid #eef2f7; border-radius: 10px;
  strong { display: block; margin-bottom: 8px; color: $text-primary; }
  p { margin: 0 0 10px; color: $text-primary; text-align: justify; }
  p:last-child { margin-bottom: 0; }
}
.reading-tags { display: flex; flex-wrap: wrap; gap: 7px; margin: 12px 0; }
.key-points { margin-top: 12px; padding: 12px 14px; background: #f8fafc; border-radius: 8px; color: $text-primary;
  ul { margin: 5px 0 0; padding-left: 20px; }
}
.recommendations {
  margin-top: 12px; padding: 12px 14px; background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px;
  strong { color: #92400e; }
  ul { margin: 8px 0 0; padding-left: 18px; }
  li { margin-bottom: 8px; color: $text-primary; line-height: 1.55; }
  .rec-type {
    display: inline-block; margin-right: 6px; padding: 1px 7px; border-radius: 999px;
    background: #fef3c7; color: #92400e; font-size: 12px; font-weight: 600;
  }
  .rec-author { color: $text-secondary; }
  .rec-why { color: $text-secondary; }
  a { color: $primary; text-decoration: none; font-weight: 600; &:hover { text-decoration: underline; } }
  em { font-style: normal; font-weight: 600; }
}
.reading-link { display: inline-block; margin-top: 10px; color: $primary; font-weight: 600; }
.reflection { margin-top: 12px; padding: 10px 13px; border-left: 3px solid #60a5fa; background: #f0f7ff; color: #334155; }
.code-block { background: #1e293b; color: #e2e8f0; padding: 16px; border-radius: 8px; overflow-x: auto; margin-top: 12px; font-size: 13px; }
.explain { margin-top: 16px; line-height: 1.7; color: $text-secondary; }
.immersive-link-bar {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  .immersive-hint { font-size: 13px; color: $text-secondary; }
}
</style>
