<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Close, FullScreen, ArrowLeft } from '@element-plus/icons-vue'
import TutorOutlinePanel from '@/components/tutor/TutorOutlinePanel.vue'
import OpenMaicBackground from '@/components/tutor/OpenMaicBackground.vue'
import type { useVideoGeneration } from '@/composables/useVideoGeneration'

const props = defineProps<{
  sessionNo: string
  videoGen: ReturnType<typeof useVideoGeneration>
}>()

const emit = defineEmits<{ close: [] }>()
const router = useRouter()

// videoGen 作为 prop 传入时，内部 ref 不会自动解包，需显式 .value
const isVisible = computed(() => props.videoGen.visible.value)
const phase = computed(() => props.videoGen.phase.value)
const stepIndex = computed(() => props.videoGen.stepIndex.value)
const steps = computed(() => props.videoGen.steps)
const progressText = computed(() => props.videoGen.progressText.value)
const error = computed(() => props.videoGen.error.value)
const isOutlineStreaming = computed(() => props.videoGen.isOutlineStreaming.value)
const autoContinueHint = computed(() => props.videoGen.autoContinueHint.value)
const confirming = computed(() => props.videoGen.confirming.value)
const reviewIntent = computed(() => props.videoGen.reviewIntent.value)
const lecture = computed(() => props.videoGen.lecture.value)
const activeStep = computed(() => props.videoGen.activeStep.value)

const displayOutline = computed(() => {
  const streaming = props.videoGen.streamingOutline.value
  const final = props.videoGen.outline.value
  return streaming.length ? streaming : final
})

const isReview = computed(() => phase.value === 'review')
const isWorking = computed(() =>
  ['preparing', 'outline', 'generating'].includes(phase.value),
)
const showCard = computed(() => isVisible.value && !isReview.value && phase.value !== 'idle')

const reviewOutlineEnabled = computed({
  get: () => props.videoGen.reviewOutlineEnabled.value,
  set: (v: boolean) => { props.videoGen.reviewOutlineEnabled.value = v },
})

function handleClose() {
  props.videoGen.close()
  emit('close')
}

function enterLecture() {
  const id = lecture.value?.lecture_id
  if (!id || !props.sessionNo) return
  props.videoGen.close()
  emit('close')
  router.push({
    path: `/student/tutor/lecture/${id}`,
    query: { session_no: props.sessionNo },
  })
}
</script>

<template>
  <Teleport to="body">
    <Transition name="vg-fade">
      <div v-if="isVisible" class="video-gen-overlay" @click.self="handleClose">
        <OpenMaicBackground :full-height="false" class="video-gen-bg">
          <div class="video-gen-bg-inner" />
        </OpenMaicBackground>

        <!-- 审阅模式：全屏大纲编辑（参考 OpenMAIC review phase） -->
        <Transition name="vg-slide">
          <div v-if="isReview" class="review-shell">
            <button type="button" class="back-btn" @click="videoGen.collapseReview()">
              <el-icon><ArrowLeft /></el-icon>
              返回预览
            </button>

            <div class="review-head">
              <div class="progress-dots">
                <span
                  v-for="(step, idx) in steps"
                  :key="step.id"
                  class="dot"
                  :class="{ active: idx === 1, done: idx < 1 }"
                />
              </div>
              <h2>审阅课程大纲</h2>
              <p v-if="isOutlineStreaming">大纲仍在生成，可先编辑已出现的节点</p>
              <p v-else>确认后将自动生成沉浸式讲解与语音</p>
            </div>

            <TutorOutlinePanel
              v-if="displayOutline.length"
              class="review-panel"
              :outline="displayOutline"
              :loading="confirming || isOutlineStreaming"
              @confirm="videoGen.confirmReview"
              @cancel="handleClose"
            />
          </div>
        </Transition>

        <!-- 卡片模式：分步动画 + 流式大纲预览 -->
        <Transition name="vg-scale">
          <div v-if="showCard" class="gen-card" :class="{ 'is-review-ready': phase === 'outline' && displayOutline.length }">
            <button type="button" class="close-btn" aria-label="关闭" @click="handleClose">
              <el-icon><Close /></el-icon>
            </button>

            <div class="progress-dots top-dots">
              <span
                v-for="(step, idx) in steps"
                :key="step.id"
                class="dot"
                :class="{
                  active: idx === stepIndex,
                  done: idx < stepIndex || phase === 'done',
                }"
              />
            </div>

            <div class="card-body">
              <!-- 完成 -->
              <div v-if="phase === 'done'" class="state-block done">
                <div class="state-icon success">✅</div>
                <h3>讲解已就绪</h3>
                <p>共 {{ lecture?.slides?.length || 0 }} 页内容，点击进入沉浸式讲解</p>
                <div class="action-row">
                  <el-button type="primary" size="large" @click="enterLecture">进入讲解</el-button>
                  <el-button size="large" @click="handleClose">留在对话</el-button>
                </div>
              </div>

              <!-- 错误 -->
              <div v-else-if="phase === 'error'" class="state-block error">
                <div class="state-icon fail">⚠️</div>
                <h3>生成失败</h3>
                <p>{{ error }}</p>
                <div class="action-row">
                  <el-button type="primary" @click="videoGen.retry()">重新生成</el-button>
                  <el-button @click="handleClose">关闭</el-button>
                </div>
              </div>

              <!-- 进行中 -->
              <template v-else>
                <div class="visualizer-wrap">
                  <!-- 大纲步骤：可点击展开审阅 -->
                  <div
                    v-if="phase === 'outline'"
                    class="outline-card"
                    :class="{ interactive: displayOutline.length || isOutlineStreaming }"
                    role="button"
                    tabindex="0"
                    @click="videoGen.expandReview()"
                    @keydown.enter.prevent="videoGen.expandReview()"
                    @keydown.space.prevent="videoGen.expandReview()"
                  >
                    <div class="outline-card-head">
                      <span class="mini-bar" />
                      <span class="live-dot" />
                    </div>
                    <div class="outline-spine">
                      <template v-if="!displayOutline.length">
                        <div v-for="i in 4" :key="i" class="skel-row" :style="{ animationDelay: `${i * 0.12}s` }">
                          <span class="skel-dot" />
                          <span class="skel-line" :style="{ width: `${50 + i * 10}%` }" />
                        </div>
                      </template>
                      <template v-else>
                        <div
                          v-for="(item, i) in displayOutline.slice(0, 4)"
                          :key="i"
                          class="outline-row anim-in"
                          :style="{ animationDelay: `${i * 0.08}s` }"
                        >
                          <span class="row-dot" />
                          <div class="row-text">
                            <strong>{{ i + 1 }}. {{ item.title }}</strong>
                            <small>{{ (item.objectives || []).join('、') || '…' }}</small>
                          </div>
                        </div>
                        <div v-if="displayOutline.length > 4" class="more-tag">+{{ displayOutline.length - 4 }}</div>
                      </template>
                    </div>
                    <div v-if="displayOutline.length || isOutlineStreaming" class="expand-hint">
                      <el-icon><FullScreen /></el-icon>
                      点击审阅大纲
                    </div>
                  </div>

                  <!-- 其他步骤：通用加载动画 -->
                  <div v-else class="loader-visual">
                    <div class="orbit" />
                    <div class="center-icon">
                      {{ phase === 'preparing' ? '🔍' : phase === 'generating' ? '🎬' : '✨' }}
                    </div>
                  </div>
                </div>

                <div class="status-text">
                  <h3>{{ activeStep.label }}</h3>
                  <p>{{ progressText || 'AI 正在为您生成视频讲解…' }}</p>
                  <p v-if="autoContinueHint" class="auto-hint">{{ autoContinueHint }}</p>
                </div>

                <label v-if="phase === 'outline' && !reviewIntent" class="review-toggle">
                  <el-switch v-model="reviewOutlineEnabled" size="small" />
                  <span>每次暂停审阅大纲</span>
                </label>

                <div v-if="isWorking" class="working-footer">
                  <span class="spark">✦</span>
                  AI 生成中
                </div>
              </template>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped lang="scss">
.video-gen-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.video-gen-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
}

.video-gen-bg-inner {
  position: absolute;
  inset: 0;
  background: rgba(248, 250, 252, 0.72);
  backdrop-filter: blur(4px);
}

.gen-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 520px;
  min-height: 420px;
  padding: 28px 28px 24px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(148, 163, 184, 0.2);
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.1);
  display: flex;
  flex-direction: column;
}

.close-btn {
  position: absolute;
  top: 14px;
  right: 14px;
  border: none;
  background: #f1f5f9;
  border-radius: 8px;
  width: 32px;
  height: 32px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  z-index: 2;
  &:hover { background: #e2e8f0; color: #334155; }
}

.progress-dots {
  display: flex;
  justify-content: center;
  gap: 6px;
  margin-bottom: 8px;

  .dot {
    height: 6px;
    width: 6px;
    border-radius: 999px;
    background: #cbd5e1;
    transition: all 0.45s ease;

    &.done { background: rgba(37, 99, 235, 0.35); }
    &.active { width: 28px; background: $primary; }
  }
}

.top-dots { margin-top: 4px; }

.card-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 16px;
}

.visualizer-wrap {
  width: 100%;
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loader-visual {
  position: relative;
  width: 140px;
  height: 140px;
  .center-icon {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 42px;
    z-index: 1;
  }
  .orbit {
    position: absolute;
    inset: 8px;
    border-radius: 50%;
    border: 3px solid transparent;
    border-top-color: $primary;
    border-right-color: rgba(37, 99, 235, 0.3);
    animation: spin 1.2s linear infinite;
  }
}

@keyframes spin { to { transform: rotate(360deg); } }

.outline-card {
  width: 200px;
  min-height: 208px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #fff;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.12);
  padding: 12px;
  text-align: left;
  position: relative;
  transform: rotate(-2deg);
  transition: transform 0.25s ease, box-shadow 0.25s ease;

  &.interactive {
    cursor: pointer;
    &:hover {
      transform: rotate(0deg) translateY(-4px) scale(1.03);
      box-shadow: 0 16px 40px rgba(37, 99, 235, 0.18);
      border-color: #93c5fd;
    }
  }
}

.outline-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  .mini-bar { width: 40px; height: 4px; border-radius: 4px; background: #e2e8f0; }
  .live-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: $primary;
    animation: blink 1.2s infinite;
  }
}

.outline-spine {
  position: relative;
  padding-left: 14px;
  &::before {
    content: '';
    position: absolute;
    left: 4px;
    top: 4px;
    bottom: 4px;
    width: 1px;
    background: #e2e8f0;
  }
}

.skel-row, .outline-row {
  position: relative;
  margin-bottom: 10px;
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.skel-dot, .row-dot {
  position: absolute;
  left: -12px;
  top: 4px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 1px solid #93c5fd;
  background: #fff;
}

.skel-line {
  height: 8px;
  border-radius: 4px;
  background: #f1f5f9;
  animation: skelPulse 1.2s infinite;
}

.skel-row { animation: skelPulse 1.2s infinite; }

.row-text {
  min-width: 0;
  strong {
    display: block;
    font-size: 10px;
    color: #334155;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  small {
    display: block;
    font-size: 8px;
    color: #94a3b8;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

.anim-in { animation: slideIn 0.35s ease both; }

@keyframes slideIn {
  from { opacity: 0; transform: translateX(-8px); }
  to { opacity: 1; transform: translateX(0); }
}

@keyframes skelPulse {
  0%, 100% { opacity: 0.45; }
  50% { opacity: 0.9; }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

.more-tag { font-size: 9px; color: $primary; font-weight: 600; }

.expand-hint {
  position: absolute;
  left: 50%;
  bottom: 10px;
  transform: translateX(-50%);
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  background: $primary;
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.35);
  animation: float 2.4s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateX(-50%) translateY(0); }
  50% { transform: translateX(-50%) translateY(-3px); }
}

.status-text {
  h3 { margin: 0 0 6px; font-size: 20px; font-weight: 700; color: #0f172a; }
  p { margin: 0; font-size: 14px; color: #64748b; line-height: 1.5; }
  .auto-hint { margin-top: 8px; color: $primary; font-size: 13px; }
}

.review-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
  cursor: pointer;
}

.working-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #94a3b8;
  font-weight: 600;
  .spark { animation: blink 1.5s infinite; color: $primary; }
}

.state-block {
  padding: 12px 0;
  .state-icon {
    width: 72px;
    height: 72px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 32px;
    margin: 0 auto 16px;
    &.success { background: #dcfce7; }
    &.fail { background: #fee2e2; }
  }
  h3 { margin: 0 0 8px; font-size: 20px; }
  p { margin: 0 0 20px; color: #64748b; font-size: 14px; }
}

.action-row {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

.review-shell {
  position: relative;
  z-index: 2;
  width: 100%;
  max-width: 720px;
  max-height: calc(100vh - 48px);
  overflow-y: auto;
  padding: 48px 20px 24px;
}

.back-btn {
  position: absolute;
  top: 8px;
  left: 8px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  background: rgba(255, 255, 255, 0.9);
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: #475569;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  &:hover { background: #fff; }
}

.review-head {
  text-align: center;
  margin-bottom: 16px;
  h2 { margin: 12px 0 6px; font-size: 22px; color: #0f172a; }
  p { margin: 0; font-size: 14px; color: #64748b; }
}

.review-panel {
  margin: 0 !important;
  background: rgba(255, 255, 255, 0.97) !important;
}

.vg-fade-enter-active, .vg-fade-leave-active { transition: opacity 0.25s ease; }
.vg-fade-enter-from, .vg-fade-leave-to { opacity: 0; }

.vg-scale-enter-active, .vg-scale-leave-active { transition: all 0.3s ease; }
.vg-scale-enter-from, .vg-scale-leave-to { opacity: 0; transform: scale(0.92) translateY(12px); }

.vg-slide-enter-active, .vg-slide-leave-active { transition: all 0.35s ease; }
.vg-slide-enter-from, .vg-slide-leave-to { opacity: 0; transform: translateY(16px); }
</style>
