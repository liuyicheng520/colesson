<script setup lang="ts">
/**
 * 管理端通用内容预览组件 — 文档/讲解/资源统一入口
 */
import { computed, ref, watch } from 'vue'
import {
  ArrowLeft,
  ArrowRight,
  ZoomIn,
  ZoomOut,
  VideoPause,
  VideoPlay,
  Mute,
} from '@element-plus/icons-vue'
import MarkdownViewer from '@/components/MarkdownViewer.vue'
import MermaidViewer from '@/components/MermaidViewer.vue'
import TeachingAnimationPlayer from '@/components/TeachingAnimationPlayer.vue'
import { normalizeAnimationSlides } from '@/utils/animationSlides'
import type {
  AdminDocumentPreview,
  AdminLecturePreview,
  AdminResourcePreview,
} from '@/api/adminContent'

export type PreviewPayload =
  | { kind: 'document'; data: AdminDocumentPreview }
  | { kind: 'lecture'; data: AdminLecturePreview }
  | { kind: 'resource'; data: AdminResourcePreview }

const props = defineProps<{
  visible: boolean
  title?: string
  loading?: boolean
  error?: string
  payload: PreviewPayload | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  retry: []
}>()

const docPage = ref(1)
const docZoom = ref(100)

// 讲解幻灯片播放器状态
const slideIndex = ref(0)
const playing = ref(false)
const muted = ref(false)
const playProgress = ref(0)
let playTimer: ReturnType<typeof setInterval> | null = null

const drawerTitle = computed(() => props.title || props.payload?.data?.title || '内容预览')

const docPages = computed(() => {
  if (props.payload?.kind !== 'document') return []
  return props.payload.data.pages || []
})

const currentDocText = computed(() => {
  const pages = docPages.value
  if (pages.length) {
    const p = pages[docPage.value - 1]
    return (p?.text as string) || ''
  }
  if (props.payload?.kind === 'document') return props.payload.data.full_text || ''
  return ''
})

const lectureSlides = computed(() => {
  if (props.payload?.kind !== 'lecture') return []
  return props.payload.data.slides || []
})

const lectureVideoUrl = computed(() => {
  if (props.payload?.kind !== 'lecture') return ''
  return props.payload.data.video_url || ''
})

const currentSlide = computed(() => lectureSlides.value[slideIndex.value])

const resourcePreview = computed(() =>
  props.payload?.kind === 'resource' ? props.payload.data : null,
)

const resourceAnimationSlides = computed(() => {
  const content = resourcePreview.value?.content as Record<string, unknown> | undefined
  if (!content) return []
  return normalizeAnimationSlides(content)
})

function close() {
  stopPlay()
  emit('update:visible', false)
}

function prevDocPage() {
  if (docPage.value > 1) docPage.value--
}

function nextDocPage() {
  if (docPage.value < docPages.value.length) docPage.value++
}

function zoomIn() {
  docZoom.value = Math.min(150, docZoom.value + 10)
}

function zoomOut() {
  docZoom.value = Math.max(70, docZoom.value - 10)
}

function stopPlay() {
  if (playTimer) {
    clearInterval(playTimer)
    playTimer = null
  }
  playing.value = false
}

function togglePlay() {
  if (lectureVideoUrl.value) return
  if (playing.value) {
    stopPlay()
    return
  }
  playing.value = true
  playTimer = setInterval(() => {
    playProgress.value = Math.min(100, playProgress.value + 1)
    if (playProgress.value >= 100) {
      if (slideIndex.value < lectureSlides.value.length - 1) {
        slideIndex.value++
        playProgress.value = 0
      } else {
        stopPlay()
      }
    }
  }, 80)
}

function onProgressInput(val: number) {
  playProgress.value = val
  const idx = Math.floor((val / 100) * Math.max(lectureSlides.value.length - 1, 0))
  slideIndex.value = idx
}

function prevSlide() {
  if (slideIndex.value > 0) slideIndex.value--
  playProgress.value = 0
}

function nextSlide() {
  if (slideIndex.value < lectureSlides.value.length - 1) slideIndex.value++
  playProgress.value = 0
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      docPage.value = 1
      docZoom.value = 100
      slideIndex.value = 0
      playProgress.value = 0
      stopPlay()
    }
  },
)
</script>

<template>
  <el-drawer
    :model-value="visible"
    :title="drawerTitle"
    direction="rtl"
    size="72%"
    class="admin-preview-drawer"
    destroy-on-close
    @close="close"
  >
    <div v-loading="loading" class="preview-body">
      <el-result v-if="error" icon="error" :title="error" sub-title="请检查网络或稍后重试">
        <template #extra>
          <el-button type="primary" @click="emit('retry')">重试</el-button>
        </template>
      </el-result>

      <!-- 文档预览：分页 + 缩放 -->
      <template v-else-if="payload?.kind === 'document'">
        <div class="doc-toolbar">
          <div class="doc-nav">
            <el-button size="small" :disabled="docPage <= 1" @click="prevDocPage">
              <el-icon><ArrowLeft /></el-icon>
            </el-button>
            <span class="page-info">
              {{ docPages.length ? `第 ${docPage} / ${docPages.length} 页` : '全文预览' }}
            </span>
            <el-button size="small" :disabled="docPage >= docPages.length" @click="nextDocPage">
              <el-icon><ArrowRight /></el-icon>
            </el-button>
          </div>
          <div class="doc-zoom">
            <el-button size="small" circle @click="zoomOut"><el-icon><ZoomOut /></el-icon></el-button>
            <span>{{ docZoom }}%</span>
            <el-button size="small" circle @click="zoomIn"><el-icon><ZoomIn /></el-icon></el-button>
          </div>
        </div>
        <div class="doc-content" :style="{ fontSize: `${docZoom}%` }">
          <pre v-if="currentDocText" class="doc-text">{{ currentDocText }}</pre>
          <el-empty v-else description="文档无文本内容" />
        </div>
        <p v-if="payload.data.truncated" class="hint">部分内容因长度限制已截断</p>
      </template>

      <!-- 讲解预览：视频或幻灯片播放器 -->
      <template v-else-if="payload?.kind === 'lecture'">
        <div v-if="lectureVideoUrl" class="video-wrap">
          <video :src="lectureVideoUrl" controls class="video-player">您的浏览器不支持视频播放</video>
        </div>
        <template v-else-if="lectureSlides.length">
          <div class="slide-stage">
            <div v-if="currentSlide?.type === 'quiz'" class="slide-quiz">
              <h3>随堂测验</h3>
              <p>{{ currentSlide.question }}</p>
              <ul>
                <li v-for="(opt, i) in currentSlide.options || []" :key="i">{{ opt }}</li>
              </ul>
            </div>
            <div v-else class="slide-content">
              <h3>{{ currentSlide?.title }}</h3>
              <ul v-if="currentSlide?.bullets?.length">
                <li v-for="(b, i) in currentSlide.bullets" :key="i">{{ b }}</li>
              </ul>
              <p v-if="currentSlide?.highlight" class="highlight">{{ currentSlide.highlight }}</p>
              <MermaidViewer v-if="currentSlide?.mermaid" :code="currentSlide.mermaid" />
            </div>
          </div>
          <div class="player-controls">
            <el-button circle size="small" :disabled="slideIndex <= 0" @click="prevSlide">
              <el-icon><ArrowLeft /></el-icon>
            </el-button>
            <el-button circle size="small" type="primary" @click="togglePlay">
              <el-icon><VideoPause v-if="playing" /><VideoPlay v-else /></el-icon>
            </el-button>
            <el-button circle size="small" :disabled="slideIndex >= lectureSlides.length - 1" @click="nextSlide">
              <el-icon><ArrowRight /></el-icon>
            </el-button>
            <el-slider
              v-model="playProgress"
              :show-tooltip="false"
              class="progress-bar"
              @input="onProgressInput"
            />
            <span class="slide-counter">{{ slideIndex + 1 }} / {{ lectureSlides.length }}</span>
            <el-button circle size="small" text @click="muted = !muted">
              <el-icon><Mute /></el-icon>
            </el-button>
          </div>
        </template>
        <el-empty v-else description="讲解内容为空" />
      </template>

      <!-- 资源预览：按类型适配 -->
      <template v-else-if="payload?.kind === 'resource' && resourcePreview">
        <div class="resource-meta">
          <el-tag size="small">{{ resourcePreview.type_name }}</el-tag>
          <el-tag size="small" type="info">{{ resourcePreview.topic }}</el-tag>
          <span v-if="resourcePreview.summary" class="summary">{{ resourcePreview.summary }}</span>
        </div>
        <div class="resource-body">
          <MarkdownViewer
            v-if="resourcePreview.preview_type === 'document'"
            :content="(resourcePreview.content.content_md as string) || ''"
          />
          <MermaidViewer
            v-else-if="resourcePreview.preview_type === 'mindmap'"
            :code="(resourcePreview.content.mermaid as string) || 'flowchart TD\n  A[暂无数据]'"
          />
          <div v-else-if="resourcePreview.preview_type === 'video'">
            <video
              v-if="resourcePreview.content.video_url"
              :src="String(resourcePreview.content.video_url)"
              controls
              class="video-player"
            />
            <TeachingAnimationPlayer
              v-else-if="resourceAnimationSlides.length"
              :slides="resourceAnimationSlides"
            />
            <MarkdownViewer
              v-else
              :content="(resourcePreview.content.script_content as string) || '暂无视频内容'"
            />
          </div>
          <div v-else-if="resourcePreview.preview_type === 'reading'" class="reading-list">
            <div
              v-for="(item, i) in (resourcePreview.content.reading_list as Record<string, unknown>[]) || []"
              :key="i"
              class="reading-item"
            >
              <strong>{{ item.title || `条目 ${i + 1}` }}</strong>
              <p>{{ item.summary || item.description }}</p>
              <p v-if="item.content" class="reading-preview-body">{{ String(item.content).slice(0, 280) }}{{ String(item.content).length > 280 ? '…' : '' }}</p>
              <ul v-if="Array.isArray(item.recommendations) && item.recommendations.length" class="rec-preview">
                <li v-for="(rec, ri) in (item.recommendations as Record<string, unknown>[]).slice(0, 3)" :key="ri">
                  {{ rec.type || '资料' }} · {{ rec.title }}{{ rec.author ? `（${rec.author}）` : '' }}
                </li>
              </ul>
            </div>
          </div>
          <pre
            v-else-if="resourcePreview.preview_type === 'code'"
            class="code-block"
          >{{ resourcePreview.content.code_content }}</pre>
          <div v-else-if="resourcePreview.preview_type === 'question'">
            <div
              v-for="(q, i) in (resourcePreview.content.questions as Record<string, unknown>[]) || []"
              :key="i"
              class="question-item"
            >
              <p><strong>Q{{ i + 1 }}.</strong> {{ q.stem }}</p>
            </div>
          </div>
          <p v-else class="plain-text">{{ resourcePreview.content.text || resourcePreview.summary || '暂无预览内容' }}</p>
        </div>
      </template>

      <el-empty v-else-if="!loading" description="暂无预览数据" />
    </div>

    <template #footer>
      <slot name="footer-actions" />
      <el-button @click="close">关闭</el-button>
    </template>
  </el-drawer>
</template>

<style scoped lang="scss">
.preview-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 16px 20px;
  overflow: hidden;
}

.doc-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.doc-nav, .doc-zoom {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-info { font-size: 13px; color: $text-secondary; min-width: 100px; text-align: center; }

.doc-content {
  flex: 1;
  overflow: auto;
  background: #f8fafc;
  border-radius: 8px;
  padding: 20px;
  border: 1px solid $border-color;
}

.doc-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  line-height: 1.75;
  margin: 0;
}

.hint { font-size: 12px; color: $warning; margin-top: 8px; }

.video-wrap, .video-player {
  width: 100%;
  max-height: 480px;
  border-radius: 8px;
  background: #000;
}

.slide-stage {
  flex: 1;
  overflow: auto;
  background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
  border-radius: 12px;
  padding: 32px;
  color: #fff;
  min-height: 320px;
}

.slide-content h3, .slide-quiz h3 { margin-bottom: 16px; font-size: 22px; }
.slide-content ul { padding-left: 1.5em; line-height: 1.8; }
.highlight { margin-top: 16px; padding: 12px; background: rgba(37, 99, 235, 0.3); border-radius: 8px; }

.player-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 8px;
  flex-shrink: 0;
}

.progress-bar { flex: 1; margin: 0 8px; }
.slide-counter { font-size: 13px; color: $text-secondary; min-width: 56px; }

.resource-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
  .summary { font-size: 13px; color: $text-secondary; }
}

.resource-body {
  flex: 1;
  overflow: auto;
}

.reading-item, .question-item {
  padding: 12px 0;
  border-bottom: 1px solid $border-color;
  p { margin: 6px 0 0; color: $text-secondary; font-size: 13px; }
  .reading-preview-body { color: $text-primary; line-height: 1.6; }
  .rec-preview { margin: 8px 0 0; padding-left: 18px; color: #92400e; font-size: 12px; }
}

.code-block {
  background: #1e293b;
  color: #e2e8f0;
  padding: 16px;
  border-radius: 8px;
  overflow: auto;
  font-size: 13px;
}

.plain-text { line-height: 1.75; color: $text-secondary; }
</style>
