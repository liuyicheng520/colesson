<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import {
  Microphone,
  ChatDotRound,
  Promotion,
} from '@element-plus/icons-vue'
import UserAvatar from '@/components/UserAvatar.vue'
import LectureCanvasToolbar from '@/components/tutor/LectureCanvasToolbar.vue'

export interface LectureChatMessage {
  id: string
  role: 'teacher' | 'user'
  content: string
  live?: boolean
}

const props = withDefaults(defineProps<{
  messages?: LectureChatMessage[]
  speaking?: boolean
  autoPlay?: boolean
  muted?: boolean
  canPrev?: boolean
  canNext?: boolean
  speed?: number
  speedOptions?: number[]
  askLoading?: boolean
  currentPage?: number
  totalPages?: number
  previewOpen?: boolean
  isPresenting?: boolean
  notesPanelOpen?: boolean
  embedded?: boolean
}>(), {
  messages: () => [],
  speaking: false,
  autoPlay: true,
  muted: false,
  canPrev: true,
  canNext: true,
  speed: 1,
  speedOptions: () => [1, 1.25, 1.5, 1.75, 2],
  currentPage: 1,
  totalPages: 1,
  previewOpen: false,
  isPresenting: false,
  notesPanelOpen: false,
  embedded: true,
})

const emit = defineEmits<{
  togglePlay: []
  prev: []
  next: []
  toggleMute: []
  speedChange: [value: number]
  sendMessage: [text: string]
  voiceResult: [text: string]
  togglePreview: []
  togglePresentation: []
  toggleChatHistory: []
}>()

const chatOpen = ref(false)
const voiceOpen = ref(false)
const inputText = ref('')
const listening = ref(false)
const scrollEl = ref<HTMLElement | null>(null)

const hasMessages = computed(() => props.messages.length > 0)
const isTeacherSpeaking = computed(() =>
  props.speaking && props.messages.some((m) => m.live && m.role === 'teacher'),
)

function cycleSpeed() {
  const idx = props.speedOptions.indexOf(props.speed)
  emit('speedChange', props.speedOptions[(idx + 1) % props.speedOptions.length])
}

function scrollToBottom() {
  nextTick(() => {
    const el = scrollEl.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

watch(
  () => [props.messages.length, props.messages.at(-1)?.content, props.askLoading],
  scrollToBottom,
  { deep: true },
)

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let recognition: any = null

function stopVoice() {
  if (listening.value && recognition) {
    try { recognition.stop() } catch { /* ignore */ }
  }
  listening.value = false
}

function onMicClick() {
  if (voiceOpen.value || listening.value) {
    voiceOpen.value = false
    stopVoice()
    return
  }
  chatOpen.value = false
  voiceOpen.value = true
  startVoice()
}

function toggleChat() {
  chatOpen.value = !chatOpen.value
  voiceOpen.value = false
  stopVoice()
}

function startVoice() {
  const w = window as Window & { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown }
  const SR = (w.SpeechRecognition || w.webkitSpeechRecognition) as (new () => {
    lang: string
    interimResults: boolean
    start: () => void
    stop: () => void
    onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
    onerror: (() => void) | null
    onend: (() => void) | null
  }) | undefined
  if (!SR) return
  if (listening.value) { stopVoice(); return }

  recognition = new SR()
  recognition.lang = 'zh-CN'
  recognition.interimResults = true
  recognition.onresult = (e) => {
    let text = ''
    for (let i = 0; i < e.results.length; i++) text += e.results[i][0]?.transcript || ''
    if (text.trim()) {
      emit('voiceResult', text.trim())
      stopVoice()
      voiceOpen.value = false
    }
  }
  recognition.onerror = () => { listening.value = false }
  recognition.onend = () => { listening.value = false }
  listening.value = true
  recognition.start()
}

function sendChat() {
  const t = inputText.value.trim()
  if (!t) return
  emit('sendMessage', t)
  inputText.value = ''
  chatOpen.value = false
}
</script>

<template>
  <footer class="roundtable-shell" :class="{ embedded, presenting: isPresenting }">
    <Transition name="panel-fade">
      <div v-if="chatOpen" class="input-float">
        <div class="input-float-inner">
          <textarea
            v-model="inputText"
            rows="1"
            placeholder="结合当前讲解提问…"
            autofocus
            @keydown.enter.exact.prevent="sendChat"
          />
          <button type="button" class="send-btn" :disabled="askLoading" @click="sendChat">
            <el-icon><Promotion /></el-icon>
          </button>
        </div>
      </div>
    </Transition>

    <Transition name="panel-fade">
      <div v-if="voiceOpen" class="input-float">
        <div class="voice-float-inner">
          <div class="voice-bars"><span v-for="i in 10" :key="i" :style="{ animationDelay: `${i * 0.07}s` }" /></div>
          <span class="voice-label">{{ listening ? '正在聆听…' : '请说话' }}</span>
          <button type="button" class="voice-mic-btn" @click="startVoice">
            <el-icon><Microphone /></el-icon>
          </button>
        </div>
      </div>
    </Transition>

    <!-- 全宽外围框（参考 OpenMAIC roundtable w-full border-t） -->
    <div class="roundtable-panel">
      <LectureCanvasToolbar
        :current-page="currentPage"
        :total-pages="totalPages"
        :preview-open="previewOpen"
        :muted="muted"
        :auto-play="autoPlay"
        :speaking="speaking"
        :can-prev="canPrev"
        :can-next="canNext"
        :speed="speed"
        :is-presenting="isPresenting"
        :chat-history-open="notesPanelOpen"
        @toggle-preview="emit('togglePreview')"
        @toggle-mute="emit('toggleMute')"
        @toggle-play="emit('togglePlay')"
        @prev="emit('prev')"
        @next="emit('next')"
        @speed-change="cycleSpeed"
        @toggle-presentation="emit('togglePresentation')"
        @toggle-chat-history="emit('toggleChatHistory')"
      />
      <div class="dock-row">
        <div class="dock-left">
          <div class="teacher-ring" :class="{ speaking: isTeacherSpeaking }">
            <div class="teacher-avatar"><span>👨‍🏫</span></div>
          </div>
          <span class="role-badge">AI 教师</span>
        </div>

        <div class="chat-stage">
          <div class="chat-stage-frame">
            <div ref="scrollEl" class="chat-stage-inner">
              <p v-if="!hasMessages && !askLoading" class="chat-empty">
                点击右侧麦克风或聊天，随时提问
              </p>

              <div
                v-for="msg in messages"
                :key="msg.id"
                class="msg-row"
                :class="msg.role === 'user' ? 'msg-row--right' : 'msg-row--left'"
              >
                <div
                  class="msg-bubble"
                  :class="[
                    msg.role === 'user' ? 'msg-bubble--user' : 'msg-bubble--teacher',
                    { live: msg.live, speaking: msg.live && speaking && msg.role === 'teacher' },
                  ]"
                >
                  <div class="bubble-head" :class="{ 'bubble-head--reverse': msg.role === 'user' }">
                    <div v-if="msg.role === 'teacher'" class="bubble-mini-avatar teacher"><span>👨‍🏫</span></div>
                    <div class="bubble-meta" :class="{ 'align-right': msg.role === 'user' }">
                      <span class="bubble-role" :class="{ user: msg.role === 'user' }">
                        {{ msg.role === 'user' ? '我' : 'AI 教师' }}
                      </span>
                      <span class="bubble-name">{{ msg.role === 'user' ? '我' : 'AI 教师' }}</span>
                    </div>
                    <div v-if="msg.role === 'user'" class="bubble-mini-avatar user">
                      <UserAvatar :size="32" />
                    </div>
                    <span v-if="msg.live && speaking && msg.role === 'teacher'" class="speaking-dot" />
                  </div>
                  <div class="bubble-body" :class="{ 'bubble-body--user': msg.role === 'user' }">
                    <p class="bubble-text">{{ msg.content }}</p>
                  </div>
                  <button
                    v-if="msg.role === 'teacher' && msg.live"
                    type="button"
                    class="bubble-play"
                    :title="speaking ? '暂停' : '播放'"
                    @click="emit('togglePlay')"
                  >
                    <el-icon><VideoPause v-if="speaking" /><VideoPlay v-else /></el-icon>
                  </button>
                </div>
              </div>

              <div v-if="askLoading" class="msg-row msg-row--left">
                <div class="msg-bubble msg-bubble--teacher loading">
                  <div class="bubble-head">
                    <div class="bubble-mini-avatar teacher"><span>👨‍🏫</span></div>
                    <div class="bubble-meta">
                      <span class="bubble-role">AI 教师</span>
                      <span class="bubble-name">AI 教师</span>
                    </div>
                  </div>
                  <div class="bubble-body">
                    <p class="bubble-text loading">
                      <span class="dot-pulse" /><span class="dot-pulse" /><span class="dot-pulse" />
                      思考中…
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="dock-right">
          <div class="user-actions-col">
            <button
              type="button"
              class="dock-icon-btn"
              :class="{ active: voiceOpen || listening }"
              title="语音答疑"
              @click="onMicClick"
            >
              <el-icon><Microphone /></el-icon>
            </button>
            <button
              type="button"
              class="dock-icon-btn"
              :class="{ active: chatOpen }"
              title="文字答疑"
              @click="toggleChat"
            >
              <el-icon><ChatDotRound /></el-icon>
            </button>
          </div>
          <div class="user-avatar-wrap" :class="{ active: messages.at(-1)?.role === 'user' }">
            <UserAvatar :size="40" />
          </div>
          <span class="role-badge">我</span>
        </div>
      </div>
    </div>
  </footer>
</template>

<style scoped lang="scss">
.roundtable-shell {
  z-index: 10;
  pointer-events: none;

  &.embedded {
    position: relative;
    left: auto;
    right: auto;
    bottom: auto;
    flex-shrink: 0;
    pointer-events: auto;
  }
}

/* 全宽外围面板 — 对齐 OpenMAIC h-[192px] w-full border-t */
.roundtable-panel {
  pointer-events: auto;
  width: 100%;
  min-height: 228px;
  border-top: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(16px);
  box-shadow: 0 -12px 40px rgba(15, 23, 42, 0.06);
  display: flex;
  flex-direction: column;
}

.input-float {
  pointer-events: auto;
  position: absolute;
  left: 50%;
  bottom: calc(100% - 6px);
  transform: translateX(-50%);
  width: min(480px, calc(100vw - 2rem));
  z-index: 60;
}

.input-float-inner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px 6px 16px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(148, 163, 184, 0.3);
  box-shadow: 0 8px 32px rgba(15, 23, 42, 0.1);
  textarea {
    flex: 1;
    border: none;
    outline: none;
    resize: none;
    background: transparent;
    font-size: 14px;
    font-family: inherit;
    color: #1e293b;
  }
}

.send-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: linear-gradient(135deg, #9333ea, #6366f1);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.voice-float-inner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 18px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(148, 163, 184, 0.3);
  box-shadow: 0 8px 32px rgba(15, 23, 42, 0.1);
}

.voice-bars {
  display: flex;
  align-items: center;
  gap: 2px;
  height: 24px;
  span {
    width: 3px;
    height: 8px;
    border-radius: 2px;
    background: linear-gradient(to top, #a855f7, #6366f1);
    animation: voice-bar 0.8s ease-in-out infinite;
  }
}

@keyframes voice-bar {
  0%, 100% { height: 5px; opacity: 0.4; }
  50% { height: 20px; opacity: 1; }
}

.voice-label { font-size: 11px; font-weight: 600; color: #9333ea; }

.voice-mic-btn {
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 50%;
  background: linear-gradient(135deg, #9333ea, #4338ca);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dock-row {
  display: flex;
  align-items: stretch;
  width: 100%;
  flex: 1;
  min-height: 192px;
}

.dock-left {
  width: 90px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px 8px;
  border-right: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(255, 255, 255, 0.35);
}

.dock-right {
  width: 76px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 6px;
  border-left: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(255, 255, 255, 0.35);
}

.role-badge {
  font-size: 10px;
  font-weight: 600;
  color: #9333ea;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(147, 51, 234, 0.25);
  background: rgba(245, 243, 255, 0.8);
  white-space: nowrap;
}

.teacher-ring {
  position: relative;
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  &::before {
    content: '';
    position: absolute;
    inset: -3px;
    border-radius: 50%;
    border: 2px solid rgba(147, 51, 234, 0.2);
    transition: all 0.3s;
  }
  &.speaking::before {
    border-color: rgba(147, 51, 234, 0.55);
    box-shadow: 0 0 0 4px rgba(147, 51, 234, 0.1), 0 0 18px rgba(99, 102, 241, 0.3);
  }
}

.teacher-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: linear-gradient(145deg, #ecfdf5, #bbf7d0);
  border: 2px solid rgba(16, 185, 129, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  z-index: 1;
}

.chat-stage {
  flex: 1;
  min-width: 0;
  position: relative;
  margin: 8px 12px 10px;
  display: flex;
}

/* 内层圆角聊天框 — 对齐 OpenMAIC rounded-[2.5rem] */
.chat-stage-frame {
  flex: 1;
  min-width: 0;
  min-height: 168px;
  border-radius: 40px;
  border: 1px solid rgba(255, 255, 255, 0.65);
  background: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.55) 0%,
    rgba(255, 255, 255, 0.88) 100%
  );
  backdrop-filter: blur(20px);
  box-shadow:
    0 20px 60px -15px rgba(15, 23, 42, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.95);
  overflow: hidden;
}

.chat-stage-inner {
  width: 100%;
  height: 100%;
  min-height: 168px;
  max-height: 168px;
  padding: 14px 20px;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  gap: 10px;
  scroll-behavior: smooth;
  transition: max-height 0.25s ease;

  &::-webkit-scrollbar { width: 5px; }
  &::-webkit-scrollbar-thumb {
    background: rgba(148, 163, 184, 0.45);
    border-radius: 999px;
  }
}

.chat-empty {
  margin: auto;
  text-align: center;
  font-size: 14px;
  color: #94a3b8;
}

.msg-row {
  display: flex;
  width: 100%;
  flex-shrink: 0;
  &--left { justify-content: flex-start; }
  &--right { justify-content: flex-end; }
}

.msg-bubble {
  position: relative;
  width: fit-content;
  max-width: min(720px, 78%);
  min-width: 120px;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.3);
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.07);
  padding-bottom: 6px;
  transition: border-color 0.25s, box-shadow 0.25s;

  &--teacher {
    &.speaking, &.live.speaking {
      border-color: rgba(147, 51, 234, 0.35);
      box-shadow: 0 8px 24px rgba(147, 51, 234, 0.12);
    }
    &.loading { border-color: rgba(148, 163, 184, 0.25); }
  }

  &--user {
    background: rgba(245, 243, 255, 0.92);
    border-color: rgba(139, 92, 246, 0.35);
  }
}

.bubble-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px 4px;
  &--reverse { flex-direction: row-reverse; }
}

.bubble-mini-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  font-size: 18px;
  &.teacher {
    background: linear-gradient(145deg, #ecfdf5, #bbf7d0);
    border: 2px solid rgba(147, 51, 234, 0.25);
  }
  &.user { border: 2px solid rgba(139, 92, 246, 0.35); }
}

.bubble-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
  &.align-right { text-align: right; }
}

.bubble-role {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #9333ea;
  &.user { color: #7c3aed; }
}

.bubble-name {
  font-size: 12px;
  font-weight: 600;
  color: #1e293b;
}

.speaking-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #9333ea;
  margin-left: auto;
  animation: pulse-dot 1.2s ease infinite;
  flex-shrink: 0;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.bubble-body {
  padding: 0 12px 8px 52px;
  &--user { padding: 0 52px 8px 12px; }
}

.bubble-text {
  margin: 0;
  font-size: 15px;
  line-height: 1.65;
  color: #334155;
  text-align: left;
  word-break: break-word;
  white-space: pre-wrap;

  &.loading {
    display: flex;
    align-items: center;
    gap: 6px;
    color: #94a3b8;
    font-style: italic;
  }
}

.dot-pulse {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #9333ea;
  animation: pulse-dot 1s ease infinite;
  &:nth-child(2) { animation-delay: 0.2s; }
  &:nth-child(3) { animation-delay: 0.4s; }
}

.bubble-play {
  position: absolute;
  right: 8px;
  bottom: 8px;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.7);
  color: #94a3b8;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  &:hover { background: #f3e8ff; color: #9333ea; }
}

.user-actions-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.dock-icon-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(148, 163, 184, 0.28);
  color: #64748b;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
  transition: background 0.15s, color 0.15s, transform 0.1s;
  &:hover { background: #f8fafc; color: #475569; }
  &.active { background: #9333ea; border-color: #9333ea; color: #fff; }
}

.user-avatar-wrap {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  &.active { box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.45); }
}

.panel-fade-enter-active,
.panel-fade-leave-active { transition: opacity 0.2s, transform 0.2s; }
.panel-fade-enter-from,
.panel-fade-leave-to { opacity: 0; transform: translateX(-50%) translateY(8px); }

@media (max-width: 768px) {
  .dock-left { width: 72px; }
  .dock-right { width: 68px; }
  .chat-stage { margin: 6px 8px 8px; }
  .chat-stage-frame,
  .chat-stage-inner {
    min-height: 140px;
    max-height: 140px;
    border-radius: 28px;
  }
  .bubble-body, .bubble-body--user { padding-left: 12px; padding-right: 12px; }
  .msg-bubble { max-width: 92%; }
}
</style>
