<script setup lang="ts">
import { computed } from 'vue'
import { ChatDotRound, Document, TrendCharts, DataAnalysis } from '@element-plus/icons-vue'
import { PROFILE_MODES, type ProfileBuildMode } from '@/profile/modes'

const props = defineProps<{
  modelValue: ProfileBuildMode
  behaviorAvailable?: boolean
  compact?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [mode: ProfileBuildMode]
}>()

const iconMap = {
  ChatDotRound,
  Document,
  TrendCharts,
  DataAnalysis,
}

const modes = computed(() =>
  PROFILE_MODES.map((m) => ({
    ...m,
    disabled: m.id === 'behavior' && !props.behaviorAvailable,
    disabledHint: m.id === 'behavior' ? '暂无学习数据，可选择其他方式' : '',
  })),
)

function select(mode: ProfileBuildMode, disabled?: boolean) {
  if (disabled) return
  emit('update:modelValue', mode)
}
</script>

<template>
  <div class="mode-selector" :class="{ compact }">
    <template v-if="!compact">
      <div
        v-for="m in modes"
        :key="m.id"
        class="mode-card"
        :class="{ active: modelValue === m.id, disabled: m.disabled }"
        @click="select(m.id, m.disabled)"
      >
        <div class="card-icon">
          <el-icon :size="28"><component :is="iconMap[m.icon as keyof typeof iconMap]" /></el-icon>
        </div>
        <h4>{{ m.name }}</h4>
        <p class="tagline">{{ m.tagline }}</p>
        <span class="duration">{{ m.duration }}</span>
        <p class="audience">{{ m.audience }}</p>
        <p v-if="m.disabled" class="disabled-hint">{{ m.disabledHint }}</p>
      </div>
    </template>
    <template v-else>
      <button
        v-for="m in modes"
        :key="m.id"
        type="button"
        class="mode-tab"
        :class="{ active: modelValue === m.id, disabled: m.disabled }"
        :disabled="m.disabled"
        :title="m.disabled ? m.disabledHint : m.tagline"
        @click="select(m.id, m.disabled)"
      >
        {{ m.name }}
      </button>
    </template>
  </div>
</template>

<style scoped lang="scss">
.mode-selector {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;

  &.compact {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
}

.mode-card {
  padding: 20px 16px;
  border-radius: 14px;
  border: 2px solid #e2e8f0;
  background: #fff;
  cursor: pointer;
  transition: all 0.3s ease;
  text-align: center;

  &:hover:not(.disabled) {
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(37, 99, 235, 0.12);
    border-color: rgba(37, 99, 235, 0.4);
  }

  &.active {
    border-image: linear-gradient(135deg, #2563eb, #7c3aed) 1;
    border: 2px solid transparent;
    background: linear-gradient(#fff, #fff) padding-box,
      linear-gradient(135deg, #2563eb, #7c3aed) border-box;
    box-shadow: 0 8px 28px rgba(37, 99, 235, 0.18);
    transform: translateY(-2px);
  }

  &.disabled {
    opacity: 0.5;
    cursor: not-allowed;
    filter: grayscale(0.3);
  }

  h4 { margin: 10px 0 6px; font-size: 15px; font-weight: 700; }
  .tagline { margin: 0 0 8px; font-size: 12px; color: $text-secondary; line-height: 1.4; }
  .duration { font-size: 11px; color: #94a3b8; }
  .audience { margin: 8px 0 0; font-size: 11px; color: #64748b; }
  .disabled-hint { margin: 6px 0 0; font-size: 11px; color: #ef4444; }
  .card-icon { color: $primary; }
}

.mode-tab {
  padding: 8px 16px;
  border-radius: 20px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.25s ease;
  color: #475569;

  &:hover:not(.disabled):not(.active) {
    border-color: rgba(37, 99, 235, 0.35);
    color: $primary;
  }

  &.active {
    background: linear-gradient(135deg, #2563eb, #7c3aed);
    color: #fff;
    border-color: transparent;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.3);
  }

  &.disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

@media (max-width: 1024px) {
  .mode-selector:not(.compact) {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 640px) {
  .mode-selector:not(.compact) {
    grid-template-columns: 1fr;
  }
}
</style>
