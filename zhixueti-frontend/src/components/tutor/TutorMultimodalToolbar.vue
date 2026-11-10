<script setup lang="ts">
import { ref } from 'vue'
import { Picture, VideoCamera, Microphone } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

withDefaults(defineProps<{
  disabled?: boolean
  loading?: boolean
  lastAssistantText?: string
  enableImage?: boolean
  enableVideo?: boolean
  enableVoice?: boolean
}>(), {
  enableImage: true,
  enableVideo: true,
  enableVoice: true,
})

const emit = defineEmits<{
  image: [prompt: string]
  video: [topic: string]
  sttResult: [text: string]
}>()

const imagePrompt = ref('')
const videoTopic = ref('')
const imageVisible = ref(false)
const videoVisible = ref(false)
const listening = ref(false)

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let recognition: any = null

function startSTT() {
  const w = window as unknown as Record<string, unknown>
  const SR = (w.SpeechRecognition || w.webkitSpeechRecognition) as (new () => {
    lang: string
    interimResults: boolean
    onresult: ((e: { results: { [i: number]: { [j: number]: { transcript: string } } } }) => void) | null
    onerror: (() => void) | null
    onend: (() => void) | null
    start: () => void
    stop: () => void
  }) | undefined
  if (!SR) {
    ElMessage.warning('当前浏览器不支持语音识别，请使用 Chrome/Edge')
    return
  }
  if (listening.value && recognition) {
    recognition.stop()
    return
  }
  recognition = new SR()
  recognition.lang = 'zh-CN'
  recognition.interimResults = true
  recognition.onresult = (e: any) => {
    const text = Array.from({ length: e.results.length }, (_, i) => e.results[i][0].transcript).join('')
    const last = e.results[e.results.length - 1]
    if (last?.[0] && (last as { isFinal?: boolean }).isFinal !== false) {
      emit('sttResult', text)
      listening.value = false
    }
  }
  recognition.onerror = () => { listening.value = false }
  recognition.onend = () => { listening.value = false }
  recognition.start()
  listening.value = true
}

function submitImage() {
  if (!imagePrompt.value.trim()) return
  emit('image', imagePrompt.value.trim())
  imageVisible.value = false
  imagePrompt.value = ''
}

function submitVideo() {
  if (!videoTopic.value.trim()) return
  emit('video', videoTopic.value.trim())
  videoVisible.value = false
  videoTopic.value = ''
}
</script>

<template>
  <div class="mm-toolbar">
    <button v-if="enableImage" type="button" class="mm-pill" :disabled="disabled" @click="imageVisible = true">
      <el-icon><Picture /></el-icon>
      <span>思维导图</span>
    </button>
    <button v-if="enableVideo" type="button" class="mm-pill" :disabled="disabled" @click="videoVisible = true">
      <el-icon><VideoCamera /></el-icon>
      <span>视频讲解</span>
    </button>
    <button
      v-if="enableVoice"
      type="button"
      class="mm-pill mic"
      :class="{ listening }"
      :disabled="disabled"
      @click="startSTT"
    >
      <el-icon><Microphone /></el-icon>
      <span>{{ listening ? '停止' : '语音输入' }}</span>
    </button>

    <el-dialog v-model="imageVisible" title="生成思维导图" width="440px" destroy-on-close>
      <el-input v-model="imagePrompt" type="textarea" :rows="3" placeholder="输入主题，例如：数据库 / 高等数学极限…" />
      <template #footer>
        <el-button @click="imageVisible = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="submitImage">生成导图</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="videoVisible" title="生成沉浸式视频讲解" width="440px" destroy-on-close>
      <el-input v-model="videoTopic" placeholder="输入知识点主题，生成幻灯片+语音讲解" />
      <template #footer>
        <el-button @click="videoVisible = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="submitVideo">开始生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.mm-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.mm-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  background: #fff;
  font-size: 13px;
  color: #374151;
  cursor: pointer;
  &:hover:not(:disabled) { border-color: $primary; color: $primary; }
  &:disabled { opacity: .5; cursor: not-allowed; }
  &.mic.listening { background: #fef2f2; border-color: #f87171; color: #dc2626; }
}
</style>
