<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ArrowLeft, ArrowRight, ChatDotRound, Microphone } from '@element-plus/icons-vue'
import MermaidViewer from '@/components/MermaidViewer.vue'
import type { TutorSlide } from '@/types'

const props = defineProps<{
  slides: TutorSlide[]
  modelValue?: number
}>()

const emit = defineEmits<{
  'update:modelValue': [index: number]
  ask: [text: string]
  sttResult: [text: string]
}>()

const idx = computed({
  get: () => props.modelValue ?? 0,
  set: (v) => emit('update:modelValue', v),
})

const current = computed(() => props.slides[idx.value])
const total = computed(() => props.slides.length)
const askVisible = ref(false)
const askText = ref('')
const slideAnim = ref(false)
const listening = ref(false)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let recognition: any = null

watch(idx, () => {
  slideAnim.value = true
  window.setTimeout(() => { slideAnim.value = false }, 350)
})

function prev() {
  if (idx.value > 0) idx.value -= 1
}

function next() {
  if (idx.value < total.value - 1) idx.value += 1
}

function goTo(i: number) {
  idx.value = i
}

function onSlider(v: number | number[]) {
  idx.value = Array.isArray(v) ? v[0] : v
}

function submitAsk() {
  if (!askText.value.trim()) return
  emit('ask', askText.value.trim())
  askVisible.value = false
  askText.value = ''
}

function startSTT() {
  const w = window as unknown as Record<string, unknown>
  const SR = (w.SpeechRecognition || w.webkitSpeechRecognition) as (new () => {
    lang: string; interimResults: boolean
    onresult: ((e: { results: { [i: number]: { [j: number]: { transcript: string } } } }) => void) | null
    onerror: (() => void) | null; onend: (() => void) | null; start: () => void; stop: () => void
  }) | undefined
  if (!SR) return
  if (listening.value && recognition) { recognition.stop(); return }
  recognition = new SR()
  recognition.lang = 'zh-CN'
  recognition.interimResults = true
  recognition.onresult = (e) => {
    const text = Array.from({ length: e.results.length }, (_, i) => e.results[i][0].transcript).join('')
    askText.value = text
    const last = e.results[e.results.length - 1]
    if (last?.[0] && (last as { isFinal?: boolean }).isFinal !== false) {
      listening.value = false
    }
  }
  recognition.onerror = () => { listening.value = false }
  recognition.onend = () => { listening.value = false }
  recognition.start()
  listening.value = true
}

defineExpose({ askText })
</script>

<template>
  <div v-if="slides.length" class="slide-deck">
    <div class="deck-layout">
      <!-- 目录缩略图 -->
      <aside class="thumb-sidebar">
        <div
          v-for="(s, i) in slides"
          :key="i"
          class="thumb-item"
          :class="{ active: i === idx }"
          @click="goTo(i)"
        >
          <span class="thumb-num">{{ i + 1 }}</span>
          <span class="thumb-title">{{ s.title }}</span>
        </div>
      </aside>

      <!-- 主幻灯片区 -->
      <div class="deck-main">
        <div class="deck-header">
          <h3>📑 幻灯片讲解</h3>
          <span>{{ idx + 1 }} / {{ total }}</span>
        </div>

        <el-slider :model-value="idx" :max="Math.max(total - 1, 0)" :show-tooltip="false" @change="onSlider" />

        <div v-if="current" class="slide-card" :class="{ animating: slideAnim }">
          <h2>{{ current.title }}</h2>
          <p v-if="current.highlight" class="highlight">{{ current.highlight }}</p>
          <ul v-if="current.bullets?.length" class="bullets">
            <li v-for="(b, i) in current.bullets" :key="i">{{ b }}</li>
          </ul>
          <MermaidViewer v-if="current.mermaid" :code="current.mermaid" class="mermaid-block" />
        </div>

        <div class="deck-nav">
          <el-button :icon="ArrowLeft" :disabled="idx <= 0" @click="prev">上一页</el-button>
          <el-button type="primary" :icon="ArrowRight" :disabled="idx >= total - 1" @click="next">
            下一页
          </el-button>
        </div>
      </div>
    </div>

    <el-button class="float-ask" type="primary" circle :icon="ChatDotRound" @click="askVisible = true" />

    <el-drawer v-model="askVisible" title="讲解中提问" direction="rtl" size="380px" append-to-body>
      <p class="ask-hint">提问以侧边弹窗展示，不打断当前讲解页</p>
      <el-input v-model="askText" type="textarea" :rows="4" placeholder="输入问题…" />
      <div class="ask-actions">
        <el-button :type="listening ? 'danger' : 'default'" :icon="Microphone" @click="startSTT">
          {{ listening ? '停止' : '语音' }}
        </el-button>
        <el-button type="primary" @click="submitAsk">发送提问</el-button>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped lang="scss">
.slide-deck {
  position: relative;
  margin: 12px 0;
  padding: 16px;
  border-radius: 14px;
  background: linear-gradient(160deg, #0f172a, #1e293b);
  color: #f1f5f9;
  animation: fadeIn 0.4s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.deck-layout {
  display: flex;
  gap: 16px;
  min-height: 280px;
}

.thumb-sidebar {
  width: 140px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 360px;
  overflow-y: auto;
  padding-right: 4px;
}

.thumb-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid transparent;
  transition: all 0.2s;

  &:hover { background: rgba(255, 255, 255, 0.08); }
  &.active {
    background: rgba(37, 99, 235, 0.25);
    border-color: rgba(96, 165, 250, 0.5);
  }

  .thumb-num {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.15);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    flex-shrink: 0;
  }
  &.active .thumb-num { background: $primary; }

  .thumb-title {
    font-size: 11px;
    line-height: 1.3;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }
}

.deck-main { flex: 1; min-width: 0; }

.deck-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  h3 { margin: 0; font-size: 14px; font-weight: 600; opacity: 0.9; }
  span { font-size: 13px; opacity: 0.7; }
}

.slide-card {
  min-height: 180px;
  padding: 24px;
  margin: 12px 0;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: opacity 0.3s, transform 0.3s;

  &.animating {
    opacity: 0.6;
    transform: translateX(8px);
  }

  h2 { margin: 0 0 12px; font-size: 22px; }
  .highlight {
    font-size: 15px;
    color: #93c5fd;
    margin-bottom: 16px;
    padding: 8px 12px;
    background: rgba(37, 99, 235, 0.2);
    border-radius: 6px;
  }
  .bullets {
    margin: 0;
    padding-left: 20px;
    line-height: 1.8;
    font-size: 15px;
  }
  .mermaid-block { margin-top: 16px; background: #fff; border-radius: 8px; padding: 12px; }
}

.deck-nav {
  display: flex;
  justify-content: center;
  gap: 12px;
}

.float-ask {
  position: absolute;
  right: 16px;
  bottom: 16px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
  z-index: 2;
}

.ask-hint { font-size: 12px; color: $text-secondary; margin: 0 0 12px; }
.ask-actions { display: flex; gap: 8px; margin-top: 12px; }

@media (max-width: 768px) {
  .thumb-sidebar { display: none; }
}
</style>
