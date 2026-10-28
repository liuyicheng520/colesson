<script setup lang="ts">
import type { AgentRunInfo, PartialPreview, TaskStage } from '@/types'
import { formatWeakFocusItem, sanitizeStudentText } from '@/utils/profileDisplay'

defineProps<{
  stages: TaskStage[]
  progress: number
  agentRuns: AgentRunInfo[]
  partialPreviews: PartialPreview[]
  learningDiagnosis: Record<string, unknown> | null
}>()

const runStatusMap: Record<number, { label: string; type: string }> = {
  0: { label: '排队', type: 'info' },
  1: { label: '执行中', type: 'warning' },
  2: { label: '完成', type: 'success' },
  3: { label: '失败', type: 'danger' },
}

function weakLabels(points: unknown): string[] {
  if (!Array.isArray(points)) return []
  return points.map((w) => formatWeakFocusItem(w)).filter((x): x is string => Boolean(x))
}

function safePreview(text: unknown): string {
  return sanitizeStudentText(text) || (typeof text === 'string' ? text.slice(0, 120) : '')
}
</script>

<template>
  <div class="agent-progress">
    <div class="overall">
      <span>整体进度</span>
      <el-progress :percentage="progress" :stroke-width="14" striped striped-flow />
    </div>

    <el-steps :active="stages.findIndex(s => s.status === 1) + 1 || stages.filter(s => s.status === 2).length" finish-status="success" align-center class="steps">
      <el-step
        v-for="s in stages"
        :key="s.stage_code"
        :title="s.stage_name"
        :description="s.message || ''"
        :status="s.status === 2 ? 'success' : s.status === 3 ? 'error' : s.status === 1 ? 'process' : 'wait'"
      />
    </el-steps>

    <div v-if="learningDiagnosis" class="diagnosis card">
      <h4>学情分析智能体 · 诊断结果</h4>
      <p>{{ sanitizeStudentText(learningDiagnosis.teaching_strategy) || '已完成学情诊断' }}</p>
      <el-tag v-for="w in weakLabels(learningDiagnosis.weak_points)" :key="w" size="small" type="danger" style="margin:2px">{{ w }}</el-tag>
    </div>

    <div class="agent-grid">
      <div v-for="run in agentRuns" :key="run.id" class="agent-card" :class="'status-' + run.status">
        <div class="agent-head">
          <strong>{{ run.agent_name }}</strong>
          <el-tag size="small" :type="(runStatusMap[run.status]?.type as any) || 'info'">
            {{ runStatusMap[run.status]?.label || '未知' }}
          </el-tag>
        </div>
        <p v-if="run.output_preview" class="preview">{{ safePreview(run.output_preview) }}</p>
      </div>
    </div>

    <div v-if="partialPreviews.length" class="stream-previews">
      <h4>流式中间结果</h4>
      <el-timeline>
        <el-timeline-item v-for="(p, i) in partialPreviews" :key="i" :timestamp="p.agent_name">
          {{ safePreview(p.preview) }}
          <el-link v-if="p.resource_id" type="primary" :href="`/student/resources/${p.resource_id}`">查看资源</el-link>
        </el-timeline-item>
      </el-timeline>
    </div>
  </div>
</template>

<style scoped lang="scss">
.agent-progress { padding: 20px; }
.overall { margin-bottom: 20px; span { display: block; margin-bottom: 8px; font-weight: 600; } }
.steps { margin: 24px 0; }
.diagnosis { padding: 16px; margin: 16px 0; background: #f0f9ff; h4 { margin-bottom: 8px; color: $primary; } }
.agent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
  margin: 16px 0;
}
.agent-card {
  padding: 14px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  &.status-1 { border-color: #f59e0b; background: #fffbeb; }
  &.status-2 { border-color: #10b981; background: #ecfdf5; }
  &.status-3 { border-color: #ef4444; background: #fef2f2; }
  .agent-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .preview { font-size: 12px; color: $text-secondary; line-height: 1.5; max-height: 60px; overflow: hidden; }
}
.stream-previews { margin-top: 20px; h4 { margin-bottom: 12px; } }
</style>
