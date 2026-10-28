<script setup lang="ts">
import { computed } from 'vue'
import { Document, QuestionFilled } from '@element-plus/icons-vue'
import { encouragementText, type LectureCompleteStats } from '@/utils/lectureSummary'
import { formatBeijingDate } from '@/utils/datetime'

const props = defineProps<{
  title: string
  stats: LectureCompleteStats
}>()

const dateLabel = computed(() => formatBeijingDate(new Date(), new Date().toLocaleDateString('zh-CN')))

const showQuiz = computed(() => props.stats.quizTotal > 0)
const ringOffset = computed(() => {
  const c = 2 * Math.PI * 34
  return c * (1 - props.stats.quizPct / 100)
})
const ringCircumference = 2 * Math.PI * 34
</script>

<template>
  <section class="complete-page" aria-label="课程完成">
    <div class="complete-bg" />
    <div class="complete-glow" />

    <div class="complete-inner">
      <div class="trophy-wrap">
        <div class="trophy-halo" />
        <svg class="trophy-svg" viewBox="0 0 120 150" aria-hidden>
          <defs>
            <linearGradient id="lc-gold" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#fef3c7" />
              <stop offset="35%" stop-color="#fbbf24" />
              <stop offset="75%" stop-color="#d97706" />
              <stop offset="100%" stop-color="#92400e" />
            </linearGradient>
            <linearGradient id="lc-gold-light" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#fcd34d" />
              <stop offset="50%" stop-color="#f59e0b" />
              <stop offset="100%" stop-color="#b45309" />
            </linearGradient>
            <linearGradient id="lc-shine" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#fffbeb" stop-opacity="0.85" />
              <stop offset="100%" stop-color="#fffbeb" stop-opacity="0" />
            </linearGradient>
          </defs>
          <path d="M 28 32 Q 6 32 8 60 Q 10 82 32 86" fill="none" stroke="url(#lc-gold)" stroke-width="7" stroke-linecap="round" />
          <path d="M 92 32 Q 114 32 112 60 Q 110 82 88 86" fill="none" stroke="url(#lc-gold)" stroke-width="7" stroke-linecap="round" />
          <path d="M 25 18 L 95 18 L 95 50 Q 95 90 60 100 Q 25 90 25 50 Z" fill="url(#lc-gold)" />
          <path d="M 33 22 Q 32 60 42 88 L 38 88 Q 30 60 31 22 Z" fill="url(#lc-shine)" />
          <ellipse cx="60" cy="19" rx="36" ry="4.5" fill="#fde68a" />
          <path d="M 60 42 L 63.6 52.3 L 74.5 52.3 L 65.7 58.7 L 69 69 L 60 62.7 L 51 69 L 54.3 58.7 L 45.5 52.3 L 56.4 52.3 Z" fill="#fff" opacity="0.92" />
          <path d="M 52 100 L 68 100 L 66 116 L 54 116 Z" fill="url(#lc-gold)" />
          <rect x="40" y="116" width="40" height="7" rx="2" fill="url(#lc-gold-light)" />
          <rect x="32" y="123" width="56" height="9" rx="2" fill="url(#lc-gold)" />
          <rect x="28" y="132" width="64" height="6" rx="3" fill="url(#lc-gold-light)" />
        </svg>
      </div>

      <div class="ribbon">✦ 课程完成 ✦</div>

      <div class="title-block">
        <h2>{{ title || '课程完成' }}</h2>
        <p class="date">{{ dateLabel }}</p>
      </div>

      <div class="stat-grid" :class="`cols-${Math.min(2, (stats.contentCount > 0 ? 1 : 0) + (stats.quizCount > 0 ? 1 : 0))}`">
        <div v-if="stats.contentCount > 0" class="stat-card">
          <el-icon class="stat-icon"><Document /></el-icon>
          <span class="stat-num">{{ stats.contentCount }}</span>
          <span class="stat-label">页</span>
        </div>
        <div v-if="stats.quizCount > 0" class="stat-card">
          <el-icon class="stat-icon"><QuestionFilled /></el-icon>
          <span class="stat-num">{{ stats.quizCount }}</span>
          <span class="stat-label">小测</span>
        </div>
      </div>

      <div v-if="showQuiz" class="quiz-card">
        <div class="quiz-ring">
          <svg viewBox="0 0 88 88">
            <circle cx="44" cy="44" r="34" fill="none" stroke="rgba(251,191,36,0.35)" stroke-width="8" />
            <circle
              cx="44"
              cy="44"
              r="34"
              fill="none"
              stroke="url(#lc-ring)"
              stroke-width="8"
              stroke-linecap="round"
              :stroke-dasharray="ringCircumference"
              :stroke-dashoffset="ringOffset"
              class="ring-progress"
            />
            <defs>
              <linearGradient id="lc-ring" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stop-color="#fbbf24" />
                <stop offset="100%" stop-color="#f97316" />
              </linearGradient>
            </defs>
          </svg>
          <span class="ring-text">{{ stats.quizPct }}<small>%</small></span>
        </div>
        <div class="quiz-meta">
          <p class="quiz-score">答对 {{ stats.quizCorrect }} / {{ stats.quizTotal }}</p>
          <p class="quiz-tip">{{ encouragementText(stats.quizPct, stats.quizTotal > 0) }}</p>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss">
.complete-page {
  position: relative;
  width: 100%;
  min-height: 420px;
  border-radius: 20px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.complete-bg {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, #fffbeb 0%, #fff 45%, #ffedd5 100%);
}

.complete-glow {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 50% 42%, rgba(251, 191, 36, 0.32), rgba(249, 115, 22, 0.1) 38%, transparent 68%);
  pointer-events: none;
}

.complete-inner {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  padding: 32px 24px 40px;
  max-width: 640px;
  width: 100%;
}

.trophy-wrap {
  position: relative;
  width: 160px;
  height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.trophy-halo {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(251, 191, 36, 0.45), transparent 72%);
  filter: blur(12px);
  animation: halo-pulse 2.6s ease-in-out infinite alternate;
}

.trophy-svg {
  width: 120px;
  height: 150px;
  filter: drop-shadow(0 10px 18px rgba(180, 83, 9, 0.35));
  animation: trophy-float 3s ease-in-out infinite;
}

@keyframes halo-pulse {
  from { opacity: 0.5; transform: scale(0.95); }
  to { opacity: 0.85; transform: scale(1.05); }
}

@keyframes trophy-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-5px); }
}

.ribbon {
  padding: 6px 16px;
  border-radius: 999px;
  background: linear-gradient(90deg, #fbbf24, #fb923c, #fbbf24);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  box-shadow: 0 4px 16px rgba(245, 158, 11, 0.35);
}

.title-block {
  text-align: center;
  h2 {
    margin: 0;
    font-size: clamp(22px, 4vw, 32px);
    font-weight: 900;
    background: linear-gradient(135deg, #b45309, #ea580c, #b45309);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    line-height: 1.25;
  }
  .date {
    margin: 6px 0 0;
    font-size: 13px;
    color: #78716c;
  }
}

.stat-grid {
  display: grid;
  gap: 12px;
  width: 100%;
  max-width: 360px;
  &.cols-1 { grid-template-columns: 1fr; max-width: 180px; }
  &.cols-2 { grid-template-columns: 1fr 1fr; }
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 16px 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(251, 191, 36, 0.35);
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
}

.stat-icon {
  font-size: 24px;
  color: #f59e0b;
}

.stat-num {
  font-size: 28px;
  font-weight: 900;
  color: #1c1917;
  line-height: 1;
}

.stat-label {
  font-size: 11px;
  color: #78716c;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.quiz-card {
  width: 100%;
  max-width: 420px;
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 20px 24px;
  border-radius: 16px;
  background: linear-gradient(135deg, #fef3c7, #fff7ed, #fef3c7);
  border: 1px solid rgba(251, 191, 36, 0.45);
  box-shadow: 0 6px 20px rgba(245, 158, 11, 0.15);
}

.quiz-ring {
  position: relative;
  width: 88px;
  height: 88px;
  flex-shrink: 0;
  svg {
    width: 100%;
    height: 100%;
    transform: rotate(-90deg);
  }
  .ring-progress {
    transition: stroke-dashoffset 1s cubic-bezier(0.16, 1, 0.3, 1);
  }
}

.ring-text {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 900;
  color: #b45309;
  small { font-size: 13px; font-weight: 700; }
}

.quiz-meta {
  flex: 1;
  min-width: 0;
}

.quiz-score {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #b45309;
}

.quiz-tip {
  margin: 6px 0 0;
  font-size: 13px;
  color: rgba(180, 83, 9, 0.85);
  line-height: 1.5;
}
</style>
