<script setup lang="ts">
import { computed } from 'vue'

export type GenPhase = 'idle' | 'outline' | 'confirm' | 'modules' | 'done'

const props = defineProps<{
  phase: GenPhase
  progressMessage?: string
}>()

const steps = [
  { key: 'outline', label: '生成大纲', icon: '📋' },
  { key: 'confirm', label: '预览确认', icon: '✏️' },
  { key: 'modules', label: '分模块输出', icon: '📚' },
] as const

const activeIdx = computed(() => {
  if (props.phase === 'outline') return 0
  if (props.phase === 'confirm') return 1
  if (props.phase === 'modules') return 2
  if (props.phase === 'done') return 3
  return -1
})
</script>

<template>
  <div v-if="phase !== 'idle'" class="gen-steps">
    <div class="steps-track">
      <div
        v-for="(step, i) in steps"
        :key="step.key"
        class="step-node"
        :class="{ active: i === activeIdx, done: i < activeIdx || phase === 'done' }"
      >
        <span class="step-icon">{{ step.icon }}</span>
        <span class="step-label">{{ step.label }}</span>
        <span v-if="i < steps.length - 1" class="step-line" />
      </div>
    </div>
    <p v-if="progressMessage" class="progress-shimmer">
      <span class="shimmer-dot" />
      {{ progressMessage }}
    </p>
  </div>
</template>

<style scoped lang="scss">
.gen-steps {
  margin: 0 16px 12px;
  padding: 14px 16px;
  border-radius: 10px;
  background: linear-gradient(135deg, #f0f9ff, #fff);
  border: 1px solid #bae6fd;
  animation: slideDown 0.35s ease;
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}

.steps-track {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.step-node {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  position: relative;
  opacity: 0.45;
  transition: opacity 0.3s;

  &.active, &.done { opacity: 1; }

  .step-icon {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: #e2e8f0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    transition: all 0.3s;
  }

  &.active .step-icon {
    background: $primary;
    box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.2);
    animation: pulse 1.5s infinite;
  }

  &.done .step-icon { background: #22c55e; }

  .step-label { font-size: 11px; color: $text-secondary; font-weight: 500; }
  &.active .step-label { color: $primary; font-weight: 600; }

  .step-line {
    position: absolute;
    top: 18px;
    left: calc(50% + 22px);
    width: calc(100% - 44px);
    height: 2px;
    background: #e2e8f0;
    z-index: -1;
  }
  &.done .step-line { background: #86efac; }
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}

.progress-shimmer {
  margin: 10px 0 0;
  font-size: 13px;
  color: $primary;
  display: flex;
  align-items: center;
  gap: 8px;
}

.shimmer-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: $primary;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
</style>
