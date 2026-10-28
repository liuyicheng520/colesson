<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { Loading, Microphone, Phone } from '@element-plus/icons-vue'
import MarkdownViewer from './MarkdownViewer.vue'
import UserAvatar from './UserAvatar.vue'
import { useBrowserStt } from '@/composables/useBrowserStt'
import { systemApi } from '@/api/system'
import type { ChatMessage } from '@/types'

const props = withDefaults(defineProps<{
  messages: ChatMessage[]
  streaming?: boolean
  placeholder?: string
  enableVoice?: boolean
  enableCall?: boolean
}>(), {
  enableVoice: true,
  enableCall: true,
})

const emit = defineEmits<{
  send: [content: string]
  call: []
}>()

const input = ref('')
const listRef = ref<HTMLElement>()
const voiceEnabled = ref(true)

const { listening, start, stop } = useBrowserStt({
  onFinal: (text) => {
    input.value = input.value ? `${input.value} ${text}` : text
  },
  onInterim: (text) => {
    /* preview in title only */
    void text
  },
})

onMounted(async () => {
  try {
    const info = await systemApi.publicInfo()
    voiceEnabled.value = info.features?.voice_input !== false
  } catch {
    voiceEnabled.value = true
  }
})

async function scrollBottom() {
  await nextTick()
  if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight
}

watch(() => props.messages.length, scrollBottom)
watch(() => props.messages.at(-1)?.content, scrollBottom)

function handleSend() {
  const text = input.value.trim()
  if (!text || props.streaming) return
  stop()
  emit('send', text)
  input.value = ''
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function toggleVoice() {
  if (listening.value) stop()
  else start()
}
</script>

<template>
  <div class="stream-chat">
    <div ref="listRef" class="chat-list" role="log" aria-live="polite">
      <div v-if="!messages.length" class="chat-empty">
        <p>{{ placeholder || '开始对话吧…' }}</p>
      </div>
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="chat-item"
        :class="msg.role"
      >
        <UserAvatar v-if="msg.role === 'user'" :size="36" />
        <div v-else class="avatar ai-avatar">AI</div>
        <div class="bubble">
          <MarkdownViewer v-if="msg.role === 'assistant'" :content="msg.content || ' '" />
          <p v-else class="user-text">{{ msg.content }}</p>
          <span v-if="msg.streaming" class="cursor-blink">▊</span>
        </div>
      </div>
      <div v-if="streaming && !messages.at(-1)?.content" class="typing">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在思考…</span>
      </div>
    </div>
    <div class="chat-input">
      <el-input
        v-model="input"
        type="textarea"
        :rows="2"
        :disabled="streaming"
        :placeholder="listening ? '正在聆听…' : '输入消息，Enter 发送，Shift+Enter 换行'"
        resize="none"
        @keydown="onKeydown"
      />
      <div class="input-actions">
        <el-button
          v-if="enableVoice && voiceEnabled"
          circle
          :type="listening ? 'danger' : 'default'"
          :title="listening ? '停止语音输入' : '语音输入'"
          :disabled="streaming"
          @click="toggleVoice"
        >
          <el-icon><Microphone /></el-icon>
        </el-button>
        <el-button
          v-if="enableCall && voiceEnabled"
          circle
          type="success"
          plain
          title="电话沟通（实时语音画像）"
          :disabled="streaming"
          @click="emit('call')"
        >
          <el-icon><Phone /></el-icon>
        </el-button>
        <el-button type="primary" :loading="streaming" :disabled="!input.trim()" @click="handleSend">
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.stream-chat {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  max-height: 100%;
  background: transparent;
  /* 嵌在左侧主面板内，不再单独描边成浮窗 */
  border: none;
  border-radius: 0;
  overflow: hidden;
}

.chat-list {
  flex: 1 1 0;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  /* 可滚时由本层承接滚轮；不可滚时允许冒泡到页面，避免「悬停对话框滚轮失效」 */
  overscroll-behavior-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 4px 2px 12px;
  scroll-behavior: smooth;
  background: transparent;
  touch-action: pan-y;

  &::-webkit-scrollbar { width: 6px; }
  &::-webkit-scrollbar-thumb {
    background: rgba(144, 147, 153, 0.4);
    border-radius: 999px;
  }
}

.chat-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  height: 100%;
  color: $text-secondary;
}

.chat-item {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;

  &.user {
    flex-direction: row-reverse;
    .bubble { background: $primary; color: #fff; }
    .user-text { color: #fff; }
  }

  &.assistant .bubble { background: #f5f7fa; }
}

.avatar, .ai-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
  color: #fff;
}

.ai-avatar {
  background: $primary-light;
}

.bubble {
  max-width: 75%;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  position: relative;
}

.user-text { white-space: pre-wrap; word-break: break-word; margin: 0; }

.cursor-blink {
  animation: blink 1s infinite;
  color: $primary;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.typing {
  display: flex;
  align-items: center;
  gap: 8px;
  color: $text-secondary;
  padding: 8px 16px;
}

.chat-input {
  flex-shrink: 0;
  display: flex;
  gap: 12px;
  padding: 12px 0 0;
  border-top: 1px solid $border-color;
  align-items: flex-end;
  background: transparent;

  .el-textarea { flex: 1; }
}

.input-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}
</style>
