<script setup lang="ts">
import { computed } from 'vue'
import type { DimensionProgressItem } from '@/types'

const props = defineProps<{
  items: DimensionProgressItem[]
  completedCount: number
  totalCount: number
  completedQuestions?: number
  totalQuestions?: number
  clickable?: boolean
}>()

const emit = defineEmits<{ select: [code: string] }>()

const progressPercent = computed(() => {
  if (props.totalQuestions && props.totalQuestions > 0 && props.completedQuestions != null) {
    return Math.round((props.completedQuestions / props.totalQuestions) * 100)
  }
  return Math.round((props.completedCount / props.totalCount) * 100)
})
</script>

<template>
  <div class="dimension-stepper">
    <div class="stepper-header">
      <span class="label">画像构建进度</span>
      <span class="count">
        <template v-if="totalQuestions && completedQuestions != null">
          {{ completedQuestions }} / {{ totalQuestions }} 问
        </template>
        <template v-else>{{ completedCount }} / {{ totalCount }} 维</template>
      </span>
    </div>
    <el-progress
      :percentage="progressPercent"
      :stroke-width="12"
      striped
      :striped-flow="progressPercent < 100"
    />
    <div class="steps">
      <div
        v-for="(item, idx) in items"
        :key="item.dimension_code"
        class="step-item"
        :class="[item.status, { clickable: clickable }]"
        @click="clickable && emit('select', item.dimension_code)"
      >
        <div class="step-badge" :class="item.status">
          {{ item.status === 'completed' ? '✓' : idx + 1 }}
        </div>
        <div class="step-body">
          <div class="step-title">
            <span>{{ item.dimension_name }}</span>
            <el-tag v-if="item.status === 'active'" size="small" type="primary" effect="dark">
              采集中 {{ item.questions_answered ?? 0 }}/{{ item.questions_total ?? 1 }}
            </el-tag>
            <el-tag v-else-if="item.status === 'completed'" size="small" type="success">
              已完成
            </el-tag>
            <el-tag v-else size="small" type="info">待开始</el-tag>
          </div>
          <p v-if="item.status === 'active'" class="step-desc">{{ item.description }}</p>
          <el-progress
            v-if="item.status !== 'pending'"
            :percentage="Math.round(((item.questions_answered ?? 0) / (item.questions_total ?? 1)) * 100)"
            :stroke-width="4"
            :show-text="false"
            class="dim-mini-progress"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.dimension-stepper {
  .stepper-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    .label { font-weight: 600; font-size: 14px; }
    .count { color: $text-secondary; font-size: 13px; }
  }
  .steps { margin-top: 16px; }
}

.step-item {
  display: flex;
  gap: 12px;
  padding: 10px 0;
  border-left: 2px solid #e2e8f0;
  margin-left: 14px;
  padding-left: 16px;
  position: relative;

  &.clickable {
    cursor: pointer;
    &:hover .step-title span { color: $primary; }
  }

  &.completed { border-left-color: #22c55e; }
  &.active { border-left-color: $primary; }

  &:last-child { border-left-color: transparent; }
}

.step-badge {
  position: absolute;
  left: -15px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #e2e8f0;
  color: #64748b;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;

  &.completed { background: #22c55e; color: #fff; }
  &.active { background: $primary; color: #fff; }
}

.step-body { flex: 1; min-width: 0; }

.step-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
}

.step-desc {
  margin-top: 4px;
  font-size: 12px;
  color: $text-secondary;
  line-height: 1.5;
}

.dim-mini-progress { margin-top: 6px; max-width: 200px; }
</style>
