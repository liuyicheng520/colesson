<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import { Loading, RefreshRight, Headset, VideoCamera } from '@element-plus/icons-vue'
import RichMarkdownViewer from './RichMarkdownViewer.vue'
import MarkdownViewer from './MarkdownViewer.vue'
import UserAvatar from './UserAvatar.vue'
import MermaidViewer from './MermaidViewer.vue'
import MindMapViewer from './MindMapViewer.vue'
import TutorInputComposer from './tutor/TutorInputComposer.vue'
import TutorThinkingBlock from './tutor/TutorThinkingBlock.vue'
import { sanitizeAnswerContent } from '@/utils/thinkStreamParser'
import { useTtsPlayer } from '@/composables/useTtsPlayer'
import type { TutorChatMessage } from '@/composables/useTutorChat'
import type { TutorDocumentItem } from '@/types'

const props = withDefaults(defineProps<{
  messages: TutorChatMessage[]
  streaming?: boolean
  placeholder?: string
  rich?: boolean
  error?: string | null
  genProgress?: string
  showLectureButton?: boolean
  showVoiceControls?: boolean
  documents?: TutorDocumentItem[]
  activeDocumentIds?: string[]
  uploading?: boolean
  uploadProgress?: number
  uploadError?: string | null
  deepMode?: boolean
  webSearchEnabled?: boolean
  showDeepMode?: boolean
  showWebSearch?: boolean
  enableImage?: boolean
  enableVideo?: boolean
  enableVoice?: boolean
  toolLoading?: boolean
  activeTool?: import('@/composables/useTutorChat').ActiveTool | null
}>(), {
  showLectureButton: false,
  showVoiceControls: true,
  documents: () => [],
  activeDocumentIds: () => [],
  showDeepMode: true,
  showWebSearch: true,
  enableImage: true,
  enableVideo: true,
  enableVoice: true,
})

const emit = defineEmits<{
  send: [content: string]
  requestFull: []
  retry: []
  openSlides: [msg: TutorChatMessage]
  startLecture: [msg: TutorChatMessage]
  sttResult: [text: string]
  upload: [file: File]
  removeDocument: [docId: string]
  toggleDocument: [docId: string]
  retryUpload: []
  'update:deepMode': [value: boolean]
  'update:webSearchEnabled': [value: boolean]
  'update:activeTool': [value: import('@/composables/useTutorChat').ActiveTool | null]
  settingsChange: []
  stop: []
}>()

const input = ref('')
const listRef = ref<HTMLElement>()
const tts = useTtsPlayer(1)

const deepModeModel = computed({
  get: () => props.deepMode ?? false,
  set: (v: boolean) => emit('update:deepMode', v),
})
const webSearchModel = computed({
  get: () => props.webSearchEnabled ?? false,
  set: (v: boolean) => emit('update:webSearchEnabled', v),
})
const activeToolModel = computed({
  get: () => props.activeTool ?? null,
  set: (v) => emit('update:activeTool', v),
})

const lastAssistantText = computed(() => {
  const m = [...props.messages].reverse().find((x) => x.role === 'assistant' && x.content)
  return m?.content || ''
})

async function scrollBottom() {
  await nextTick()
  if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight
}

watch(() => props.messages.length, scrollBottom)
watch(() => props.messages.at(-1)?.content, scrollBottom)
watch(() => props.messages.at(-1)?.thinkingContent, scrollBottom)

function handleSend() {
  const text = input.value.trim()
  if (!text || props.streaming) return
  emit('send', text)
  input.value = ''
}

function onComposerSend() {
  if (props.streaming) return
  handleSend()
}

function onSttResult(text: string) {
  input.value = text
  emit('sttResult', text)
}

function fillInput(text: string) {
  input.value = text
}

function strategyLabel(msg: TutorChatMessage): string | null {
  const meta = msg.meta
  if (!meta || msg.role !== 'assistant') return null
  if (msg.slides?.length || meta.message_type === 'lecture') return null
  if (meta.lecture_id || meta.message_type === 'video_lecture') return null

  const key = meta.strategy_used || ''
  const labels: Record<string, string | null> = {
    socratic_hint: '习题引导',
    exercise_resolve: '习题解析',
    feedback: '习题解析',
    code_demo: '代码演示',
    multimodal: '多模态讲解',
    lecture_outline: '课程大纲',
    lecture_slides: '幻灯片讲解',
    explanation: null,
  }

  if (key.startsWith('multimodal_')) return '多模态生成'
  return labels[key] ?? (meta.is_exercise ? '习题引导' : null)
}

function displayContent(msg: TutorChatMessage): string {
  if (msg.role !== 'assistant') return msg.content
  return sanitizeAnswerContent(msg.content || '', msg.thinkingContent || '')
}

defineExpose({ fillAndSend: (text: string) => emit('send', text), fillInput, lastAssistantText })
</script>

<template>
  <div class="stream-chat">
    <div ref="listRef" class="chat-list">
      <div v-if="!messages.length" class="chat-empty">
        <div class="empty-icon">💬</div>
        <p>{{ placeholder || '开始对话吧，描述你的学习问题…' }}</p>
      </div>
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="chat-item"
        :class="[msg.role, { failed: msg.failed }]"
      >
        <UserAvatar v-if="msg.role === 'user'" :size="36" />
        <div v-else class="avatar ai-avatar">AI</div>
        <div class="bubble-wrap">
          <div class="bubble">
            <div v-if="msg.progressMessage && msg.streaming && !msg.content && !msg.thinkingContent" class="gen-progress">
              <el-icon class="is-loading"><Loading /></el-icon>
              {{ msg.progressMessage }}
            </div>
            <TutorThinkingBlock
              v-if="msg.role === 'assistant' && (msg.thinkingContent?.trim() || (msg.streaming && !displayContent(msg).trim()))"
              :thinking="msg.thinkingContent || ''"
              :duration-sec="msg.thinkingDurationSec"
              :streaming="!!msg.streaming && !displayContent(msg).trim()"
              :has-main-content="!!displayContent(msg).trim()"
            />
            <div v-if="msg.role === 'assistant' && displayContent(msg)" class="assistant-markdown">
              <RichMarkdownViewer
                v-if="rich"
                :content="displayContent(msg)"
                :streaming="!!msg.streaming"
              />
              <MarkdownViewer
                v-else
                :content="displayContent(msg)"
                :streaming="!!msg.streaming"
              />
              <span v-if="msg.streaming" class="cursor-blink inline-cursor">▊</span>
            </div>
            <p v-else-if="msg.role === 'user'" class="user-text">{{ msg.content }}</p>

            <!-- 多模态：思维导图（优先交互式节点图，其次 Mermaid） -->
            <div
              v-if="msg.multimodal && (msg.multimodal.nodes || msg.multimodal.mermaid)"
              class="mm-block"
            >
              <MindMapViewer
                v-if="Array.isArray(msg.multimodal.nodes) && (msg.multimodal.nodes as unknown[]).length"
                :data="null"
                :nodes="msg.multimodal.nodes as []"
                :edges="(msg.multimodal.edges as []) || []"
              />
              <MermaidViewer
                v-else-if="msg.multimodal.mermaid"
                :code="String(msg.multimodal.mermaid)"
              />
              <p v-if="msg.multimodal.caption" class="mm-caption">{{ msg.multimodal.caption }}</p>
            </div>
            <!-- 多模态：视频分步 -->
            <div v-if="msg.multimodal?.steps" class="video-steps">
              <h4>{{ msg.multimodal.title }}</h4>
              <div v-for="(step, si) in (msg.multimodal.steps as Array<{label:string;content:string}>)" :key="si" class="vstep">
                <span class="vstep-label">{{ step.label }}</span>
                <p>{{ step.content }}</p>
              </div>
            </div>

            <div v-if="msg.role === 'assistant' && msg.meta?.web_sources?.length" class="citations">
              <span class="cite-label">参考来源</span>
              <a
                v-for="(s, i) in msg.meta.web_sources"
                :key="i"
                :href="s.url"
                target="_blank"
                rel="noopener"
              >{{ s.title }}</a>
            </div>
            <div v-if="msg.role === 'assistant' && msg.meta?.doc_citations?.length" class="citations doc-cite">
              <span class="cite-label">文档引用</span>
              <span v-for="(c, i) in msg.meta.doc_citations" :key="i">
                {{ c.filename }} 第{{ c.page }}页
              </span>
            </div>
            <p
              v-if="msg.role === 'assistant' && msg.meta?.web_search_timeout && !(msg.meta?.web_sources?.length)"
              class="web-timeout"
            >
              未能获取网络资料，已为您生成通用解答
            </p>

            <div v-if="msg.role === 'assistant' && displayContent(msg) && !msg.streaming && (showVoiceControls || msg.meta?.lecture_id)" class="msg-actions">
              <template v-if="showVoiceControls">
                <button
                  type="button"
                  class="tts-btn"
                  :class="{ active: tts.playingId === msg.id }"
                  @click="tts.toggle(msg.id, displayContent(msg))"
                >
                  <el-icon><Headset /></el-icon>
                  {{ tts.playingId === msg.id ? (tts.paused ? '继续' : '暂停') : '播放语音' }}
                </button>
                <el-progress
                  v-if="tts.playingId === msg.id"
                  :percentage="Math.round(tts.progress)"
                  :stroke-width="3"
                  style="width: 80px"
                />
                <button
                  v-if="tts.playingId === msg.id"
                  type="button"
                  class="tts-btn stop"
                  @click="tts.stop()"
                >
                  停止
                </button>
              </template>
              <el-button
                v-if="msg.meta?.lecture_id"
                size="small"
                type="primary"
                :icon="VideoCamera"
                @click="emit('startLecture', msg)"
              >
                进入视频讲解
                <template v-if="msg.meta.lecture_slide_count">（{{ msg.meta.lecture_slide_count }} 页）</template>
              </el-button>
            </div>

            <div v-if="strategyLabel(msg)" class="msg-meta">
              <el-tag size="small" type="info">{{ strategyLabel(msg) }}</el-tag>
              <el-button
                v-if="msg.slides?.length || msg.meta?.message_type === 'lecture'"
                size="small"
                type="primary"
                link
                @click="$emit('openSlides', msg)"
              >
                📑 幻灯片讲解 ({{ msg.slides?.length || msg.meta?.slides?.length || 0 }}页)
              </el-button>
            </div>
            <div v-if="msg.failed" class="error-bar">
              <span>生成失败</span>
              <el-button size="small" type="primary" link :icon="RefreshRight" @click="emit('retry')">重试</el-button>
            </div>
          </div>
        </div>
      </div>
      <div v-if="streaming && genProgress && !messages.at(-1)?.content" class="typing">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>{{ genProgress }}</span>
      </div>
      <div v-else-if="streaming && !messages.at(-1)?.content && !messages.at(-1)?.progressMessage" class="typing">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>AI 正在思考…</span>
      </div>
    </div>

    <div v-if="$slots.quickPrompts" class="quick-prompts">
      <slot name="quickPrompts" />
    </div>

    <TutorInputComposer
      v-model="input"
      v-model:active-tool="activeToolModel"
      :streaming="streaming"
      :tool-loading="toolLoading"
      :placeholder="placeholder"
      :documents="documents"
      :active-document-ids="activeDocumentIds"
      :uploading="uploading"
      :upload-progress="uploadProgress"
      :upload-error="uploadError"
      v-model:deep-mode="deepModeModel"
      v-model:web-search-enabled="webSearchModel"
      :show-deep-mode="showDeepMode"
      :show-web-search="showWebSearch"
      :enable-image="enableImage"
      :enable-video="enableVideo"
      :enable-voice="enableVoice"
      @send="onComposerSend"
      @stop="emit('stop')"
      @upload="emit('upload', $event)"
      @remove-document="emit('removeDocument', $event)"
      @toggle-document="emit('toggleDocument', $event)"
      @retry-upload="emit('retryUpload')"
      @stt-result="onSttResult"
      @settings-change="emit('settingsChange')"
    />
  </div>
</template>

<style scoped lang="scss">
.stream-chat {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: #fff;
  border-radius: $radius-lg;
  border: 1px solid $border-color;
  box-shadow: $shadow-card;
  overflow: hidden;
}

.chat-list { flex: 1; overflow-y: auto; padding: 20px 24px; }

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: $text-secondary;
  gap: 12px;
  .empty-icon { font-size: 40px; opacity: 0.6; }
  p { margin: 0; font-size: 14px; }
}

.chat-item {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  animation: fadeIn 0.25s ease;
  &.user {
    flex-direction: row-reverse;
    .bubble-wrap { align-items: flex-end; }
    .bubble { background: linear-gradient(135deg, $primary, $primary-light); color: #fff; }
    .user-text { color: #fff; }
  }
  &.assistant .bubble { background: #f8fafc; border: 1px solid $border-color; max-width: 100%; }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

.bubble-wrap { display: flex; flex-direction: column; max-width: 82%; gap: 4px; }

.avatar, .ai-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 600; flex-shrink: 0; color: #fff;
}
.ai-avatar { background: linear-gradient(135deg, $primary-light, $primary); }

.bubble {
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.65;
  position: relative;
  width: 100%;
  font-size: 14px;

  :deep(.markdown-body) {
    font-size: 14px;
    line-height: 1.65;

    h1 {
      font-size: 16px;
      margin: 0.6em 0 0.35em;
    }
    h2 {
      font-size: 15px;
      margin: 0.55em 0 0.3em;
    }
    h3, h4, h5, h6 {
      font-size: 14px;
      margin: 0.45em 0 0.25em;
    }
    p {
      margin: 0.4em 0;
      font-size: 14px;
    }
    ul, ol {
      margin: 0.35em 0;
      padding-left: 1.25em;
      font-size: 14px;
    }
    li {
      margin: 0.12em 0;
    }
    blockquote {
      margin: 0.45em 0;
      padding: 0.35em 0.75em;
      font-size: 13px;
    }
    pre {
      margin: 0.6em 0;
      padding: 10px 12px;
      font-size: 12px;
    }
  }
}
.user-text { white-space: pre-wrap; word-break: break-word; margin: 0; }

.gen-progress {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; color: $primary; margin-bottom: 8px;
}

.citations {
  margin-top: 10px; font-size: 12px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  .cite-label { color: $text-secondary; }
  a { color: $primary; }
}
.disclaimer { font-size: 11px; color: $text-secondary; margin-top: 8px; font-style: italic; }
.web-timeout { font-size: 12px; color: #d97706; margin-top: 6px; }

.msg-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.tts-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid $border-color;
  border-radius: 999px;
  background: #f8fafc;
  font-size: 12px;
  cursor: pointer;
  &.active { border-color: $primary; color: $primary; }
  &.stop { color: $danger; border-color: #fecaca; }
}

.mm-block { margin-top: 12px; .mm-caption { font-size: 12px; color: $text-secondary; margin-top: 6px; } }

.video-steps {
  margin-top: 12px;
  h4 { margin: 0 0 8px; }
  .vstep {
    padding: 8px 12px; margin-bottom: 8px; border-radius: 8px; background: #eff6ff;
    .vstep-label { font-weight: 600; color: $primary; font-size: 13px; }
    p { margin: 4px 0 0; font-size: 13px; }
  }
}

.msg-meta { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.assistant-markdown {
  position: relative;

  .inline-cursor {
    display: inline-block;
    margin-left: 2px;
    vertical-align: baseline;
  }
}
.cursor-blink { animation: blink 1s infinite; color: $primary; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

.error-bar { display: flex; align-items: center; gap: 8px; margin-top: 8px; font-size: 12px; color: $danger; }
.typing { display: flex; align-items: center; gap: 8px; color: $text-secondary; padding: 8px 16px; font-size: 13px; }

.quick-prompts { padding: 10px 16px 0; border-top: 1px solid $border-color; background: #fafbfc; }
</style>
