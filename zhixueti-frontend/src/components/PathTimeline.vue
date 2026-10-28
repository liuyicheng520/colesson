<script setup lang="ts">
import { computed } from 'vue'
import type { PathNode, PathPhase } from '@/types'
import { NODE_STATUS_MAP, PHASE_STYLE } from '@/types'

const props = defineProps<{
  phases: PathPhase[]
  nodes: PathNode[]
  selectedId?: number | null
}>()

const emit = defineEmits<{
  nodeClick: [node: PathNode]
  resourceClick: [resourceId: number, node: PathNode]
  generateResources: [node: PathNode]
  viewResources: [node: PathNode]
}>()

const TYPE_ICON: Record<string, string> = {
  document: '📄讲义',
  mindmap: '🧠图谱',
  question: '📝习题',
  video: '🎬动画',
  reading: '📖拓展',
  code: '💻实战',
}

const PHASE_NOTE: Record<string, string> = {
  intro: '适配薄弱基础，扩充巩固节点',
  intermediate: '深入核心方法与实践',
  advanced: '综合应用与拓展提升',
}

const nodesByPhase = computed(() => {
  const map: Record<string, PathNode[]> = {}
  for (const phase of props.phases) {
    map[phase.phase] = props.nodes.filter((n) => n.phase === phase.phase)
  }
  return map
})

function statusClass(status: number) {
  return ['locked', 'ready', 'learning', 'done', 'skipped'][status] || 'locked'
}

function nodeVisualClass(node: PathNode) {
  const classes = [statusClass(node.status)]
  if (node.is_weak) classes.push('is-weak')
  if (node.is_adaptive) classes.push('is-adaptive')
  if (props.selectedId === node.id) classes.push('selected')
  return classes
}

function resourceState(node: PathNode): 'empty' | 'pushed' | 'partial' | 'done' {
  if (!node.resource_items.length) return 'empty'
  const learned = node.resource_items.filter((r) => r.is_learned).length
  if (learned > 0 && learned === node.resource_items.length) return 'done'
  if (learned > 0) return 'partial'
  return 'pushed'
}
</script>

<template>
  <div class="path-timeline">
    <div v-for="phase in phases" :key="phase.phase" class="phase-block">
      <div class="phase-header" :style="{ borderColor: PHASE_STYLE[phase.phase]?.color }">
        <span class="phase-icon">{{ PHASE_STYLE[phase.phase]?.icon }}</span>
        <div class="phase-info">
          <h4>{{ phase.phase_name }}</h4>
          <p>{{ PHASE_NOTE[phase.phase] || phase.description }}</p>
        </div>
        <el-tag size="small" :type="phase.completed_count === phase.total_count ? 'success' : 'info'">
          {{ phase.completed_count }}/{{ phase.total_count }}
        </el-tag>
      </div>

      <div class="timeline-nodes">
        <div
          v-for="node in nodesByPhase[phase.phase] || []"
          :key="node.id"
          class="timeline-node"
          :class="nodeVisualClass(node)"
          @click="emit('nodeClick', node)"
        >
          <div class="node-marker" />
          <div class="node-card">
            <div class="node-head">
              <strong>{{ node.node_name }}</strong>
              <div class="head-tags">
                <el-tag v-if="node.is_weak" size="small" type="warning" effect="plain">你的薄弱考点</el-tag>
                <el-tag v-if="node.is_adaptive" size="small" type="success" effect="plain">自适应新增</el-tag>
                <el-tag size="small" :type="(NODE_STATUS_MAP[node.status]?.type as any) || 'info'">
                  {{ NODE_STATUS_MAP[node.status]?.label }}
                </el-tag>
              </div>
            </div>
            <p v-if="node.description" class="node-desc">{{ node.description }}</p>
            <div class="node-meta">
              <span>{{ node.estimated_min }} 分钟</span>
              <span>难度 {{ node.difficulty }}/5</span>
              <span v-if="node.mastery_score != null">掌握度 {{ Math.round(node.mastery_score * 100) }}%</span>
            </div>

            <div v-if="node.status === 0" class="lock-tip">
              需完成 {{ (node.prereq_names || []).join('、') || '前置节点' }} 后解锁
            </div>

            <div v-if="resourceState(node) === 'done'" class="res-done">✓ 全部资源学习完成</div>
            <div v-else-if="resourceState(node) === 'partial'" class="res-partial">
              已学 {{ node.resource_items.filter((r) => r.is_learned).length }}/{{ node.resource_items.length }} 个资源
            </div>
            <div
              v-if="resourceState(node) === 'pushed' || resourceState(node) === 'partial' || resourceState(node) === 'done'"
              class="resource-chips"
            >
              <el-tag
                v-for="r in node.resource_items"
                :key="r.resource_id"
                size="small"
                :effect="r.is_learned ? 'dark' : 'plain'"
                :type="r.is_learned ? 'success' : 'info'"
                class="res-chip"
                :class="{ learned: r.is_learned }"
                :title="r.title"
                @click.stop="emit('resourceClick', r.resource_id, node)"
              >
                {{ r.is_learned ? '✓ ' : '' }}{{ TYPE_ICON[r.type_code] || r.type_name }}
              </el-tag>
            </div>
            <div v-else class="resource-hint">
              <span class="muted">未匹配资源</span>
              <el-button size="small" type="primary" link @click.stop="emit('generateResources', node)">
                一键生成配套资源
              </el-button>
            </div>

            <div class="node-ops" @click.stop>
              <el-button size="small" text type="primary" @click="emit('viewResources', node)">查看配套资源</el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.path-timeline { padding: 8px 0; }
.phase-block { margin-bottom: 28px; }

.phase-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-left: 4px solid;
  background: #f8fafc;
  border-radius: 0 8px 8px 0;
  margin-bottom: 16px;

  .phase-icon { font-size: 22px; }
  .phase-info {
    flex: 1;
    h4 { margin: 0 0 2px; font-size: 16px; }
    p { margin: 0; font-size: 12px; color: $text-secondary; }
  }
}

.timeline-nodes {
  margin-left: 20px;
  border-left: 2px solid #e2e8f0;
  padding-left: 24px;
}

.timeline-node {
  position: relative;
  margin-bottom: 16px;
  cursor: pointer;

  &.selected .node-card {
    border-color: #409eff;
    box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.15);
  }

  &.done .node-marker { background: #10b981; border-color: #10b981; }
  &.learning .node-marker { background: #f59e0b; border-color: #f59e0b; }
  &.ready .node-marker { background: #409eff; border-color: #409eff; }
  &.locked .node-marker { background: #e2e8f0; border-color: #94a3b8; }
  &.locked .node-card { opacity: 0.78; background: #f8fafc; }

  &.is-weak .node-card {
    background: #fff7cc;
    border-left: 3px solid #e6a23c;
  }

  &.is-adaptive .node-card {
    background: #e6ffe6;
    border-left: 3px solid #67c23a;
  }
}

.node-marker {
  position: absolute;
  left: -31px;
  top: 18px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 3px solid #94a3b8;
  background: #fff;
}

.node-card {
  padding: 14px 16px;
  border: 1px solid $border-color;
  border-radius: 10px;
  background: #fff;
  transition: box-shadow 0.2s, border-color 0.2s;

  &:hover { box-shadow: 0 6px 16px rgba(64, 158, 255, 0.12); }
}

.node-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 6px;
}

.head-tags { display: flex; flex-wrap: wrap; gap: 4px; justify-content: flex-end; }

.node-desc {
  font-size: 13px;
  color: $text-secondary;
  margin: 0 0 8px;
  line-height: 1.5;
}

.node-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: $text-secondary;
  margin-bottom: 8px;
}

.lock-tip {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 8px;
}

.resource-chips, .resource-hint {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.muted { font-size: 12px; color: #94a3b8; }
.res-done { font-size: 13px; color: #67c23a; font-weight: 600; margin-bottom: 6px; }
.res-partial { font-size: 13px; color: #e6a23c; font-weight: 600; margin-bottom: 6px; }
.res-chip { cursor: pointer; }
.res-chip:hover { color: #409eff; border-color: #409eff; }
.res-chip.learned { font-weight: 600; }

.node-ops {
  margin-top: 8px;
  display: flex;
  justify-content: flex-end;
  opacity: 0;
  transition: opacity 0.15s;
}

.timeline-node:hover .node-ops { opacity: 1; }
</style>
