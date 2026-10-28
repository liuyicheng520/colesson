<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Microphone, PhoneFilled, Close, ChatDotRound } from '@element-plus/icons-vue'
import { profileApi } from '@/api/profile'
import { useBrowserStt } from '@/composables/useBrowserStt'
import { useBrowserTts } from '@/composables/useBrowserTts'
import { stripLlmStreamMarkers } from '@/utils/llmStreamMarkers'
import type { DialogueMessageData, DimensionProgressItem } from '@/types'

type CallPhase = 'idle' | 'listening' | 'thinking' | 'speaking'

const route = useRoute()
const router = useRouter()

const sessionNo = ref((route.query.session_no as string) || '')
const phase = ref<CallPhase>('idle')
const caption = ref('')
const interimCaption = ref('')
const statusHint = ref('准备开始…')
const dimLabel = ref('')
const progressHint = ref('')
const muted = ref(false)
const ending = ref(false)

let abortCtrl: AbortController | null = null
let quietTimer: ReturnType<typeof setTimeout> | null = null
let utteranceBuf = ''
let bargeArmed = false

const { speaking, speak, stop: stopTts } = useBrowserTts()

const {
  listening,
  interim: sttInterim,
  start: startStt,
  stop: stopStt,
} = useBrowserStt({
  continuous: true,
  onInterim: (text) => {
    if (phase.value === 'listening') interimCaption.value = text
    if (phase.value === 'speaking' && bargeArmed && text.replace(/\s/g, '').length >= 2) {
      bargeIn()
    }
  },
  onFinal: (text) => {
    if (phase.value !== 'listening') return
    utteranceBuf = `${utteranceBuf} ${text}`.trim()
    interimCaption.value = ''
    caption.value = utteranceBuf
    scheduleCommit()
  },
  onSpeechStart: () => {
    if (phase.value === 'speaking' && bargeArmed) bargeIn()
  },
})

void speaking
void sttInterim

const phaseLabel = computed(() => {
  switch (phase.value) {
    case 'listening': return '正在听你说…'
    case 'thinking': return 'AI 正在组织下一问…'
    case 'speaking': return 'AI 正在提问…'
    default: return '通话已暂停'
  }
})

function clearQuietTimer() {
  if (quietTimer) {
    clearTimeout(quietTimer)
    quietTimer = null
  }
}

function scheduleCommit() {
  clearQuietTimer()
  quietTimer = setTimeout(() => {
    const text = utteranceBuf.trim()
    if (text.length >= 4) void submitAnswer(text)
  }, 1400)
}

function syncMeta(data: Partial<DialogueMessageData> | Record<string, unknown>) {
  const code = data.current_dimension_code as string | null | undefined
  const name = data.current_dimension_name as string | null | undefined
  const q = data.current_question_index as number | undefined
  const cq = data.completed_question_count as number | undefined
  const tq = data.total_question_count as number | undefined
  if (name) dimLabel.value = code ? `${code} · ${name}` : name
  if (q != null) progressHint.value = `第 ${q} 问`
  if (cq != null && tq != null) progressHint.value = `${cq}/${tq} · ${progressHint.value || ''}`.trim()
  const dims = data.dimension_progress as DimensionProgressItem[] | undefined
  if (dims?.length) {
    const active = dims.find((d) => d.status === 'active') || dims.find((d) => d.status !== 'completed')
    if (active) dimLabel.value = `${active.dimension_code} · ${active.dimension_name}`
  }
}

async function ensureSession() {
  const data = await profileApi.startDialogue()
  sessionNo.value = data.session_no
  syncMeta(data)
  const opening = data.message || data.messages?.filter((m) => m.role === 'assistant').at(-1)?.content || ''
  if (opening) await playAssistant(opening)
  else enterListening()
}

async function playAssistant(text: string) {
  phase.value = 'speaking'
  statusHint.value = phaseLabel.value
  caption.value = text
  bargeArmed = false
  startStt()
  window.setTimeout(() => { bargeArmed = true }, 600)
  if (!muted.value) await speak(text)
  else await new Promise((r) => setTimeout(r, 400))
  bargeArmed = false
  enterListening()
}

function enterListening() {
  if (ending.value) return
  phase.value = 'listening'
  statusHint.value = phaseLabel.value
  utteranceBuf = ''
  interimCaption.value = ''
  caption.value = '请开始回答…'
  startStt()
}

function bargeIn() {
  if (phase.value !== 'speaking' && phase.value !== 'thinking') return
  bargeArmed = false
  stopTts()
  if (abortCtrl) {
    abortCtrl.abort()
    abortCtrl = null
  }
  if (phase.value === 'thinking') {
    ElMessage.info('已打断，请继续说')
  }
  enterListening()
}

async function submitAnswer(text: string) {
  if (!sessionNo.value || phase.value === 'thinking' || phase.value === 'speaking') return
  clearQuietTimer()
  utteranceBuf = ''
  interimCaption.value = ''
  phase.value = 'thinking'
  statusHint.value = phaseLabel.value
  caption.value = text
  stopStt()

  abortCtrl = new AbortController()
  let streamed = ''
  try {
    await profileApi.streamMessage(
      sessionNo.value,
      text,
      {
        onChunk: (c) => {
          streamed += c
          caption.value = streamed
          phase.value = 'speaking'
          statusHint.value = 'AI 正在提问…'
        },
        onReplace: (c) => {
          streamed = c
          caption.value = c
        },
        onDone: (data) => {
          syncMeta(data)
          if (data.assistant_message) streamed = stripLlmStreamMarkers(data.assistant_message)
        },
      },
      { signal: abortCtrl.signal },
    )
    abortCtrl = null
    if (ending.value) return
    await playAssistant(streamed || caption.value)
  } catch (e) {
    abortCtrl = null
    if ((e as Error).name === 'AbortError') return
    ElMessage.error('通话请求失败，请重试')
    enterListening()
  }
}

async function startCall() {
  try {
    await ensureSession()
    if (!caption.value || phase.value === 'idle') {
      // ensureSession already played opening when message set
      if (phase.value !== 'listening' && phase.value !== 'speaking') enterListening()
    }
  } catch {
    ElMessage.error('无法进入语音画像通话')
  }
}

function endCall() {
  ending.value = true
  clearQuietTimer()
  stopTts()
  stopStt()
  if (abortCtrl) abortCtrl.abort()
  router.push('/student/profile-dialogue')
}

onMounted(() => {
  void startCall()
})

onBeforeUnmount(() => {
  ending.value = true
  clearQuietTimer()
  stopTts()
  stopStt()
  if (abortCtrl) abortCtrl.abort()
})
</script>

<template>
  <div class="voice-call">
    <header class="call-top">
      <div class="meta">
        <h1>画像电话沟通</h1>
        <p class="sub">{{ dimLabel || '对话式画像' }} <span v-if="progressHint">· {{ progressHint }}</span></p>
      </div>
      <el-button text type="danger" :icon="Close" @click="endCall">结束通话</el-button>
    </header>

    <main class="call-stage">
      <div class="avatar-ring" :class="phase">
        <div class="pulse" />
        <div class="core">AI</div>
      </div>
      <p class="phase-text">{{ phaseLabel }}</p>
      <div class="caption-card">
        <p class="final">{{ caption }}</p>
        <p v-if="interimCaption" class="interim">{{ interimCaption }}</p>
      </div>
      <p class="tip">说话后略停顿即可提交；AI 朗读时可直接开口打断。</p>
    </main>

    <footer class="call-bar">
      <el-button circle size="large" :type="muted ? 'info' : 'primary'" plain @click="muted = !muted">
        {{ muted ? '取消静音' : '静音' }}
      </el-button>
      <el-button
        circle
        size="large"
        type="warning"
        :disabled="phase === 'listening' || phase === 'idle'"
        @click="bargeIn"
      >
        打断
      </el-button>
      <el-button
        circle
        size="large"
        :type="listening && phase === 'listening' ? 'danger' : 'success'"
        :icon="Microphone"
        @click="phase === 'listening' ? (listening ? stopStt() : startStt()) : bargeIn()"
      />
      <el-button circle size="large" type="danger" :icon="PhoneFilled" @click="endCall" />
      <el-button circle size="large" plain :icon="ChatDotRound" title="回文字对话" @click="endCall" />
    </footer>
  </div>
</template>

<style scoped lang="scss">
.voice-call {
  min-height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(ellipse at 50% 0%, #dbeafe 0%, transparent 55%),
    linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
  border-radius: 16px;
  overflow: hidden;
}

.call-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  h1 { margin: 0; font-size: 20px; color: #0f172a; }
  .sub { margin: 4px 0 0; color: #64748b; font-size: 13px; }
}

.call-stage {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  gap: 16px;
}

.avatar-ring {
  position: relative;
  width: 132px;
  height: 132px;
  display: grid;
  place-items: center;
  .core {
    width: 88px;
    height: 88px;
    border-radius: 50%;
    background: #2563eb;
    color: #fff;
    font-weight: 700;
    display: grid;
    place-items: center;
    z-index: 1;
  }
  .pulse {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 2px solid rgba(37, 99, 235, 0.35);
    opacity: 0;
  }
  &.listening .pulse,
  &.speaking .pulse,
  &.thinking .pulse {
    animation: pulse 1.6s ease-out infinite;
  }
  &.speaking .core { background: #0ea5e9; }
  &.listening .core { background: #16a34a; }
  &.thinking .core { background: #7c3aed; }
}

@keyframes pulse {
  0% { transform: scale(0.85); opacity: 0.7; }
  100% { transform: scale(1.25); opacity: 0; }
}

.phase-text {
  margin: 0;
  color: #334155;
  font-size: 15px;
  font-weight: 600;
}

.caption-card {
  width: min(720px, 100%);
  min-height: 140px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 20px 24px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
  .final {
    margin: 0;
    font-size: 18px;
    line-height: 1.7;
    color: #0f172a;
    white-space: pre-wrap;
  }
  .interim {
    margin: 12px 0 0;
    color: #94a3b8;
    font-size: 15px;
  }
}

.tip {
  margin: 0;
  color: #94a3b8;
  font-size: 12px;
}

.call-bar {
  display: flex;
  justify-content: center;
  gap: 16px;
  padding: 20px 24px 28px;
  flex-wrap: wrap;
}
</style>
