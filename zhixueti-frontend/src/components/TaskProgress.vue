<script setup lang="ts">
import type { TaskStage } from '@/types'

defineProps<{ stages: TaskStage[]; progress: number }>()

const STATUS_ICON: Record<number, string> = {
  0: 'Clock',
  1: 'Loading',
  2: 'CircleCheck',
  3: 'CircleClose',
  4: 'Remove',
}
</script>

<template>
  <div class="task-progress">
    <el-progress :percentage="progress" :stroke-width="10" striped striped-flow />
    <el-steps :active="stages.findIndex(s => s.status === 1) + 1" finish-status="success" align-center class="steps">
      <el-step
        v-for="s in stages"
        :key="s.stage_code"
        :title="s.stage_name"
        :description="s.message || ''"
        :status="s.status === 2 ? 'success' : s.status === 3 ? 'error' : s.status === 1 ? 'process' : 'wait'"
      />
    </el-steps>
  </div>
</template>

<style scoped lang="scss">
.task-progress {
  padding: 20px;
  .steps { margin-top: 24px; }
}
</style>
