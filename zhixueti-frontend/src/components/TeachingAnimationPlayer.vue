<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import {
  ArrowLeft,
  ArrowRight,
  Microphone,
  Mute,
  RefreshRight,
  VideoPause,
  VideoPlay,
} from '@element-plus/icons-vue'
import type { AnimationSlide } from '@/utils/animationSlides'
import { stripForTts } from '@/composables/useTtsPlayer'

export type { AnimationSlide }

const props = defineProps<{
  slides: AnimationSlide[]
  teacherName?: string
  animationData?: Record<string, unknown>
}>()

const currentIndex = ref(0)
const playing = ref(false)
const progress = ref(0)
const labRunning = ref(false)
const labValue = ref(50)
const iframeKey = ref(0)
const muted = ref(false)
const speaking = ref(false)
let timer: ReturnType<typeof setInterval> | null = null
let labTimer: ReturnType<typeof setInterval> | null = null
let speechGen = 0

const scene = computed(() => props.slides[currentIndex.value] || {})
const totalSteps = computed(() => props.slides.length)
const duration = computed(() => Math.max(4, scene.value.duration_sec || 10) * 1000)
const sceneType = computed(() => {
  if (scene.value.interactive_html) return 'interactive'
  return scene.value.scene_type || 'concept'
})
const isLabScene = computed(() => sceneType.value === 'simulation')
const sceneNodes = computed(() => {
  if (Array.isArray(scene.value.nodes) && scene.value.nodes.length) return scene.value.nodes.slice(0, 4)
  const visual = (scene.value.visual || '').split(/[，。；、]/).map((part) => part.trim()).filter(Boolean)
  return [scene.value.title || '核心概念', ...visual].slice(0, 4)
})
const interaction = computed(() => scene.value.interaction || {})
const labMin = computed(() => interaction.value.min ?? 0)
const labMax = computed(() => interaction.value.max ?? 100)
const labUnit = computed(() => interaction.value.unit || '%')
const labLabel = computed(() => interaction.value.variable_label || '演示进度')
const narrationText = computed(() => stripForTts(String(scene.value.narration || '')))

const iframeSrcdoc = computed(() => {
  const html = scene.value.interactive_html
  if (!html) return ''
  const patch = `<style>
    html,body{width:100%;min-height:100%;margin:0;overflow:auto;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}
    *,*:before,*:after{box-sizing:border-box}
  </style>`
  const head = html.search(/<head[^>]*>/i)
  if (head < 0) return `${patch}${html}`
  const end = html.indexOf('>', head)
  return end < 0 ? `${patch}${html}` : `${html.slice(0, end + 1)}${patch}${html.slice(end + 1)}`
})

function stopSpeech() {
  speechGen += 1
  speaking.value = false
  if ('speechSynthesis' in window) window.speechSynthesis.cancel()
}

function speakCurrent() {
  stopSpeech()
  if (muted.value || !narrationText.value || !('speechSynthesis' in window)) return
  const myGen = speechGen
  const utter = new SpeechSynthesisUtterance(narrationText.value.slice(0, 1200))
  utter.lang = 'zh-CN'
  utter.rate = 1
  speaking.value = true
  utter.onend = () => {
    if (myGen === speechGen) speaking.value = false
  }
  utter.onerror = () => {
    if (myGen === speechGen) speaking.value = false
  }
  window.speechSynthesis.speak(utter)
}

function stopTimer() {
  if (timer) clearInterval(timer)
  timer = null
  playing.value = false
}

function startTimer(reset = false) {
  if (!totalSteps.value) return
  if (reset) progress.value = 0
  if (timer) clearInterval(timer)
  playing.value = true
  speakCurrent()
  timer = setInterval(() => {
    progress.value = Math.min(100, progress.value + (10000 / duration.value))
    if (progress.value >= 100) {
      if (currentIndex.value < totalSteps.value - 1) moveTo(currentIndex.value + 1, true)
      else {
        stopTimer()
        stopSpeech()
      }
    }
  }, 100)
}

function stopLab() {
  if (labTimer) clearInterval(labTimer)
  labTimer = null
  labRunning.value = false
}

function toggleLab() {
  if (labRunning.value) {
    stopLab()
    return
  }
  labRunning.value = true
  labTimer = setInterval(() => {
    const next = labValue.value + 1
    labValue.value = next > labMax.value ? labMin.value : next
  }, 70)
}

function resetScene() {
  progress.value = 0
  stopLab()
  labValue.value = interaction.value.initial ?? Math.round((labMin.value + labMax.value) / 2)
  iframeKey.value += 1
}

function moveTo(index: number, keepPlaying = false) {
  if (index < 0 || index >= totalSteps.value) return
  const shouldPlay = keepPlaying || playing.value
  stopTimer()
  stopSpeech()
  currentIndex.value = index
  resetScene()
  if (shouldPlay) startTimer(true)
  else if (!muted.value) speakCurrent()
}

function togglePlay() {
  if (playing.value) {
    stopTimer()
    stopSpeech()
  } else {
    startTimer()
  }
}

function toggleMute() {
  muted.value = !muted.value
  if (muted.value) stopSpeech()
  else if (playing.value) speakCurrent()
}

function prev() { moveTo(currentIndex.value - 1) }
function next() { moveTo(currentIndex.value + 1) }
function onSeek(value: number | number[]) {
  progress.value = Array.isArray(value) ? value[0] : value
}

watch(currentIndex, resetScene)
watch(() => props.slides, () => {
  currentIndex.value = 0
  resetScene()
  stopSpeech()
}, { deep: true })

onUnmounted(() => {
  stopTimer()
  stopLab()
  stopSpeech()
})
</script>

<template>
  <section class="anim-player" aria-label="互动教学动画播放器">
    <header class="player-head">
      <div class="teacher-chip">
        <span class="teacher-avatar">{{ scene.emoji || '🎥' }}</span>
        <span>
          <b>{{ teacherName || 'AI 教师' }}</b>
          <small>{{ speaking ? '正在讲解…' : '互动讲解' }}</small>
        </span>
      </div>
      <div class="scene-meta">
        <el-tag size="small" effect="plain" :type="sceneType === 'concept' ? 'info' : 'success'">
          {{ sceneType === 'interactive' ? '互动场景' : sceneType === 'simulation' ? '探索实验' : '概念讲解' }}
        </el-tag>
        <span>{{ currentIndex + 1 }} / {{ totalSteps }}</span>
      </div>
    </header>

    <div class="scene-rail" aria-label="讲解场景进度">
      <button
        v-for="(_, index) in slides"
        :key="index"
        type="button"
        :class="['rail-dot', { active: index === currentIndex, seen: index < currentIndex }]"
        :aria-label="`跳至第 ${index + 1} 个场景`"
        @click="moveTo(index)"
      />
    </div>

    <main class="stage">
      <Transition name="scene-swap" mode="out-in">
        <iframe
          v-if="sceneType === 'interactive' && iframeSrcdoc"
          :key="`iframe-${currentIndex}-${iframeKey}`"
          class="interactive-frame"
          :srcdoc="iframeSrcdoc"
          sandbox="allow-scripts allow-forms"
          title="互动教学场景"
        />

        <div v-else :key="`scene-${currentIndex}`" class="scene-grid">
          <div class="scene-copy">
            <p class="eyebrow">SCENE {{ String(currentIndex + 1).padStart(2, '0') }}</p>
            <h3>{{ scene.title || `步骤 ${currentIndex + 1}` }}</h3>
            <p class="visual-desc">{{ scene.visual || '跟随讲解，观察概念之间的联系。' }}</p>
            <div class="narration-box" :class="{ live: speaking }">
              <span class="sound-wave" aria-hidden="true"><i /><i /><i /><i /></span>
              <p>{{ scene.narration || '这一部分正在准备讲解内容。' }}</p>
            </div>
          </div>

          <div v-if="isLabScene" class="lab-panel">
            <div class="lab-topline"><span class="pulse-dot" :class="{ running: labRunning }" />{{ labRunning ? '实验运行中' : '等待操作' }}</div>
            <div class="lab-canvas">
              <div class="orbit orbit-a" :style="{ transform: `rotate(${labValue * 2}deg)` }"><i /></div>
              <div class="orbit orbit-b" :style="{ transform: `rotate(${-labValue}deg)` }"><i /></div>
              <div class="core-orb">{{ scene.emoji || '✦' }}</div>
              <span class="lab-value">{{ labValue }}{{ labUnit }}</span>
            </div>
            <label class="lab-control">
              <span>{{ labLabel }}</span>
              <el-slider v-model="labValue" :min="labMin" :max="labMax" :show-tooltip="false" />
            </label>
            <div class="preset-row">
              <el-button size="small" type="primary" plain @click="toggleLab">{{ labRunning ? '暂停实验' : '启动实验' }}</el-button>
              <el-button
                v-for="preset in interaction.presets || []"
                :key="preset.label"
                size="small"
                @click="labValue = preset.value"
              >{{ preset.label }}</el-button>
            </div>
          </div>

          <div v-else class="concept-map" :class="{ moving: playing }">
            <div v-for="(node, index) in sceneNodes" :key="`${node}-${index}`" class="concept-node" :style="{ '--delay': `${index * 120}ms` }">
              <span>{{ index + 1 }}</span><b>{{ node }}</b>
            </div>
            <div class="map-flow">⇢</div>
          </div>
        </div>
      </Transition>
    </main>

    <footer class="controls">
      <el-slider :model-value="progress" :show-tooltip="false" @input="onSeek" />
      <div class="control-row">
        <el-button :icon="ArrowLeft" circle :disabled="currentIndex === 0" @click="prev" />
        <el-button type="primary" size="large" circle @click="togglePlay">
          <el-icon><VideoPause v-if="playing" /><VideoPlay v-else /></el-icon>
        </el-button>
        <el-button :icon="RefreshRight" circle @click="resetScene" />
        <el-button :icon="ArrowRight" circle :disabled="currentIndex >= totalSteps - 1" @click="next" />
        <el-button circle :title="muted ? '开启语音' : '关闭语音'" @click="toggleMute">
          <el-icon><Mute v-if="muted" /><Microphone v-else /></el-icon>
        </el-button>
      </div>
      <p>点击播放将朗读旁白；可手动跳转场景。遇到“探索实验”时可调节参数并启动演示。</p>
    </footer>
  </section>
</template>

<style scoped lang="scss">
.anim-player { overflow: hidden; border: 1px solid #dbeafe; border-radius: 18px; background: #fff; box-shadow: 0 16px 44px rgba(30, 64, 175, .10); }
.player-head { min-height: 70px; padding: 13px 18px; display: flex; align-items: center; justify-content: space-between; gap: 14px; border-bottom: 1px solid #e8eefb; background: linear-gradient(105deg, #eff6ff, #f5f3ff); }
.teacher-chip { display: flex; align-items: center; gap: 10px; .teacher-avatar { display: grid; place-items: center; width: 40px; height: 40px; border-radius: 13px; background: linear-gradient(135deg, #2563eb, #7c3aed); font-size: 22px; box-shadow: 0 8px 18px rgba(79, 70, 229, .22); } b, small { display: block; } b { font-size: 14px; color: #1e293b; } small { margin-top: 2px; color: #64748b; font-size: 11px; } }
.scene-meta { display: flex; align-items: center; gap: 9px; color: #64748b; font-size: 12px; white-space: nowrap; }
.scene-rail { display: flex; gap: 7px; padding: 12px 18px 0; .rail-dot { border: 0; width: 10px; height: 10px; padding: 0; border-radius: 50%; background: #dbe4f3; cursor: pointer; transition: .2s; &.seen { background: #93c5fd; } &.active { width: 28px; border-radius: 8px; background: #2563eb; } &:focus-visible { outline: 2px solid #1d4ed8; outline-offset: 3px; } } }
.stage { min-height: 390px; padding: 14px 18px 18px; background: radial-gradient(circle at 78% 12%, #e0e7ff 0, transparent 26%), linear-gradient(140deg, #f8fbff, #fff 52%, #f0fdfa); }
.scene-grid { min-height: 356px; display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(280px, .95fr); gap: 22px; align-items: center; }
.eyebrow { margin: 0 0 8px; color: #2563eb; font-weight: 800; font-size: 11px; letter-spacing: 1.4px; }
.scene-copy h3 { margin: 0; color: #172554; font-size: clamp(21px, 3vw, 30px); line-height: 1.3; }
.visual-desc { min-height: 46px; margin: 12px 0 18px; color: #64748b; line-height: 1.75; font-size: 14px; }
.narration-box {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 15px;
  border: 1px solid #dbeafe;
  border-radius: 14px;
  background: rgba(255,255,255,.86);
  box-shadow: 0 8px 22px rgba(37, 99, 235, .06);
  p { margin: 0; color: #334155; line-height: 1.75; font-size: 14px; white-space: pre-wrap; word-break: break-word; }
  &.live {
    border-color: #93c5fd;
    box-shadow: 0 8px 22px rgba(37, 99, 235, .12);
    .sound-wave i { animation-play-state: running; }
  }
}
.sound-wave { display: flex; align-items: center; gap: 2px; height: 30px; flex: 0 0 auto; i { width: 3px; height: 10px; border-radius: 3px; background: #2563eb; animation: wave 1s ease-in-out infinite; &:nth-child(2){ animation-delay: .15s; height: 22px } &:nth-child(3){ animation-delay: .3s; height: 16px } &:nth-child(4){ animation-delay: .45s; height: 25px } } }
.concept-map { min-height: 280px; position: relative; display: grid; align-content: center; gap: 13px; padding: 26px 24px; border-radius: 20px; overflow: hidden; background: linear-gradient(145deg, #172554, #1e3a8a 58%, #312e81); box-shadow: 0 18px 36px rgba(30, 58, 138, .22); &::before { content: ''; position: absolute; width: 240px; height: 240px; border: 1px solid rgba(255,255,255,.13); border-radius: 50%; right: -80px; top: -100px; } }
.concept-node { position: relative; z-index: 1; display: flex; align-items: center; gap: 10px; padding: 11px 13px; border: 1px solid rgba(191,219,254,.28); border-radius: 12px; background: rgba(255,255,255,.10); color: #eff6ff; backdrop-filter: blur(8px); animation: nodeIn .45s both; animation-delay: var(--delay); span { display: grid; place-items: center; width: 23px; height: 23px; border-radius: 50%; background: #60a5fa; font-size: 12px; font-weight: 800; } b { font-size: 13px; font-weight: 600; } }
.map-flow { position: absolute; right: 16px; bottom: 12px; color: #93c5fd; font-size: 30px; opacity: .8; }.moving .map-flow { animation: drift 1s ease-in-out infinite; }
.lab-panel { min-height: 294px; padding: 16px; border: 1px solid #bae6fd; border-radius: 20px; background: linear-gradient(145deg, #ecfeff, #eff6ff); box-shadow: 0 16px 32px rgba(14, 116, 144, .10); }.lab-topline { display: flex; align-items: center; gap: 7px; color: #1d4ed8; font-size: 12px; font-weight: 700; }.pulse-dot { width: 8px; height: 8px; border-radius: 50%; background: #94a3b8; &.running { background: #10b981; animation: pulse 1s infinite; } }
.lab-canvas { position: relative; height: 170px; display: grid; place-items: center; overflow: hidden; }.orbit { position: absolute; width: 142px; height: 82px; border: 2px solid rgba(37,99,235,.32); border-radius: 50%; transition: transform .08s linear; i { position:absolute; width: 12px; height: 12px; border-radius: 50%; background: #38bdf8; top: 4px; left: 18px; box-shadow: 0 0 14px #38bdf8; } }.orbit-b { width: 205px; height: 116px; border-color: rgba(124,58,237,.26); i { background:#a78bfa; box-shadow: 0 0 14px #a78bfa; right: 18px; left:auto; bottom:4px; top:auto; } }.core-orb { z-index: 1; display:grid; place-items:center; width:64px; height:64px; border-radius:50%; background:linear-gradient(135deg,#2563eb,#7c3aed); color:#fff; font-size:28px; box-shadow:0 0 0 10px rgba(96,165,250,.18), 0 12px 24px rgba(37,99,235,.25); }.lab-value { position:absolute; bottom:3px; right:8px; color:#1e3a8a; font-weight:800; font-size:13px; }.lab-control { display:block; color:#475569; font-size:12px; font-weight:700; }.preset-row { display:flex; flex-wrap:wrap; gap:7px; margin-top:8px; }
.interactive-frame { display: block; width: 100%; min-height: 356px; border: 1px solid #c7d2fe; border-radius: 16px; background: #fff; }
.controls { padding: 13px 20px 16px; border-top: 1px solid #edf2f7; background: #fff; .control-row { display:flex; align-items:center; justify-content:center; gap:12px; margin-top:10px; } p { margin: 10px 0 0; text-align:center; color:#94a3b8; font-size:11px; } }
.scene-swap-enter-active, .scene-swap-leave-active { transition: opacity .22s ease, transform .22s ease; }.scene-swap-enter-from, .scene-swap-leave-to { opacity:0; transform: translateY(8px); }
@keyframes wave { 50% { transform: scaleY(.45); opacity:.45; } } @keyframes nodeIn { from{ opacity:0; transform:translateX(14px) } to{ opacity:1; transform:none } } @keyframes drift { 50%{ transform:translateX(-8px) } } @keyframes pulse { 50%{ transform:scale(1.7); opacity:.35 } }
@media (max-width: 700px) { .player-head { padding: 12px; }.scene-grid { grid-template-columns: 1fr; gap: 14px; }.stage { min-height: auto; padding: 12px; }.concept-map { min-height: 230px; }.lab-panel { min-height: 275px; }.interactive-frame { min-height: 430px; }.scene-meta { font-size:11px; }.controls { padding-inline: 13px; } }
</style>
