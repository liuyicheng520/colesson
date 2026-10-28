<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ArrowDown, ArrowRight } from '@element-plus/icons-vue'
import { summarizeThinking } from '@/utils/thinkStreamParser'

const props = defineProps<{
  thinking: string
  durationSec?: number | null
  streaming?: boolean
  hasMainContent?: boolean
}>()

const expanded = ref(false)
const thinkStartAt = ref<number | null>(null)

watch(
  () => props.thinking,
  (val, prev) => {
    if (val && !prev && thinkStartAt.value == null) {
      thinkStartAt.value = Date.now()
    }
  },
  { immediate: true },
)

watch(
  () => props.hasMainContent,
  (has) => {
    if (has) expanded.value = false
  },
)

watch(
  () => props.streaming,
  (s, prev) => {
    if (prev && !s) expanded.value = false
  },
)

const displayLines = computed(() =>
  summarizeThinking(props.thinking)
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean),
)

const elapsedSec = computed(() => {
  if (props.durationSec && props.durationSec > 0) return props.durationSec
  if (thinkStartAt.value == null) return 0
  return Math.max(1, Math.round((Date.now() - thinkStartAt.value) / 1000))
})

const headerLabel = computed(() => {
  if (props.streaming && !props.hasMainContent) return '正在思考…'
  if (elapsedSec.value > 0) return `已思考（用时 ${elapsedSec.value} 秒）`
  return '已思考'
})

const canExpand = computed(() => displayLines.value.length > 0)
const showBody = computed(() => expanded.value && canExpand.value)
const visible = computed(
  () => props.thinking.trim() || (props.streaming && !props.hasMainContent),
)
</script>

<template>
  <div v-if="visible" class="thinking-block">
    <button
      type="button"
      class="thinking-header"
      :disabled="!canExpand"
      @click="canExpand && (expanded = !expanded)"
    >
      <span class="thinking-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
          <circle cx="12" cy="12" r="2.2" fill="#006eff" />
          <ellipse cx="12" cy="12" rx="9" ry="3.5" stroke="#006eff" stroke-width="1.4" />
          <ellipse cx="12" cy="12" rx="9" ry="3.5" stroke="#006eff" stroke-width="1.4" transform="rotate(60 12 12)" />
          <ellipse cx="12" cy="12" rx="9" ry="3.5" stroke="#006eff" stroke-width="1.4" transform="rotate(120 12 12)" />
        </svg>
      </span>
      <span class="thinking-label">{{ headerLabel }}</span>
      <el-icon v-if="canExpand" class="thinking-arrow">
        <ArrowDown v-if="expanded" />
        <ArrowRight v-else />
      </el-icon>
    </button>
    <div v-if="showBody" class="thinking-body">
      <ul class="thinking-list">
        <li v-for="(line, i) in displayLines" :key="i">{{ line.replace(/^\d+\.\s*/, '') }}</li>
      </ul>
    </div>
  </div>
</template>

<style scoped lang="scss">
.thinking-block {
  margin-bottom: 10px;
}

.thinking-header {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 2px 0;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  color: #6b7280;

  &:disabled {
    cursor: default;
  }

  &:hover:not(:disabled) .thinking-label {
    color: #4b5563;
  }
}

.thinking-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.thinking-label {
  font-weight: 500;
  transition: color 0.15s;
}

.thinking-arrow {
  font-size: 12px;
  color: #9ca3af;
}

.thinking-body {
  margin-top: 8px;
  padding: 10px 14px 10px 16px;
  border-radius: 8px;
  background: #f3f4f6;
  border-left: 2px solid #d1d5db;
}

.thinking-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  line-height: 1.75;
  color: #8b8f98;

  li {
    margin-bottom: 4px;

    &:last-child {
      margin-bottom: 0;
    }
  }
}
</style>
