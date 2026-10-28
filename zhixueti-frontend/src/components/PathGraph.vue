<script setup lang="ts">
import { computed, ref } from 'vue'
import type { PathEdge, PathNode } from '@/types'
import { NODE_STATUS_MAP, PHASE_STYLE } from '@/types'

const props = defineProps<{
  nodes: PathNode[]
  edges?: PathEdge[]
  selectedId?: number | null
}>()

const emit = defineEmits<{ nodeClick: [node: PathNode] }>()

const zoom = ref(1)

const PHASE_ORDER = ['intro', 'intermediate', 'advanced'] as const
const PHASE_META: Record<string, { name: string; tip: string }> = {
  intro: { name: '入门', tip: '夯实基础 · 巩固薄弱点' },
  intermediate: { name: '进阶', tip: '核心方法 · 实践深化' },
  advanced: { name: '提升', tip: '综合应用 · 能力拓展' },
}

const columns = computed(() => {
  const grouped = new Map<string, PathNode[]>()
  for (const key of PHASE_ORDER) grouped.set(key, [])
  for (const n of props.nodes) {
    const key = PHASE_ORDER.includes(n.phase as (typeof PHASE_ORDER)[number])
      ? n.phase
      : 'intro'
    if (!grouped.has(key)) grouped.set(key, [])
    grouped.get(key)!.push(n)
  }
  for (const list of grouped.values()) {
    list.sort((a, b) => a.sort_order - b.sort_order)
  }
  return PHASE_ORDER.map((phase) => ({
    phase,
    name: PHASE_META[phase]?.name || phase,
    tip: PHASE_META[phase]?.tip || '',
    style: PHASE_STYLE[phase],
    nodes: grouped.get(phase) || [],
  })).filter((c) => c.nodes.length > 0)
})

function nodeClass(node: PathNode) {
  const classes = [`status-${node.status}`]
  if (node.is_weak) classes.push('is-weak')
  if (node.is_adaptive) classes.push('is-adaptive')
  if (props.selectedId === node.id) classes.push('is-selected')
  if (node.status === 0) classes.push('is-locked')
  return classes
}

function statusLabel(status: number) {
  return NODE_STATUS_MAP[status]?.label || '节点'
}

function zoomIn() {
  zoom.value = Math.min(1.35, +(zoom.value + 0.1).toFixed(2))
}

function zoomOut() {
  zoom.value = Math.max(0.75, +(zoom.value - 0.1).toFixed(2))
}

function zoomReset() {
  zoom.value = 1
}
</script>

<template>
  <div class="path-graph">
    <div class="graph-toolbar">
      <div class="legend">
        <span class="lg"><i class="dot ready" />可学习</span>
        <span class="lg"><i class="dot learning" />学习中</span>
        <span class="lg"><i class="dot done" />已完成</span>
        <span class="lg"><i class="dot locked" />锁定</span>
        <span class="lg"><i class="dot weak" />薄弱考点</span>
        <span class="lg"><i class="dot adaptive" />自适应新增</span>
      </div>
      <div class="zoom-btns">
        <el-button size="small" plain @click="zoomOut">缩小</el-button>
        <el-button size="small" plain @click="zoomReset">{{ Math.round(zoom * 100) }}%</el-button>
        <el-button size="small" plain @click="zoomIn">放大</el-button>
      </div>
    </div>

    <div v-if="!nodes.length" class="graph-empty">
      <p>暂无路径节点，请先生成学习路径</p>
    </div>

    <div v-else class="graph-canvas">
      <div class="canvas-inner" :style="{ transform: `scale(${zoom})` }">
        <div class="phase-row">
          <div
            v-for="col in columns"
            :key="col.phase"
            class="phase-col"
            :style="{ '--phase-color': col.style?.color || '#409EFF', '--phase-bg': col.style?.bg || '#eff6ff' }"
          >
            <div class="phase-banner">
              <span class="phase-icon">{{ col.style?.icon || '📌' }}</span>
              <div>
                <strong>{{ col.name }}</strong>
                <small>{{ col.tip }}</small>
              </div>
              <el-tag size="small" effect="plain" round>{{ col.nodes.length }} 节点</el-tag>
            </div>

            <div class="phase-nodes">
              <button
                v-for="node in col.nodes"
                :key="node.id"
                type="button"
                class="graph-node"
                :class="nodeClass(node)"
                @click="emit('nodeClick', node)"
              >
                <div class="node-top">
                  <span class="status-pill">{{ statusLabel(node.status) }}</span>
                  <span v-if="node.is_weak" class="badge weak">薄弱考点</span>
                  <span v-else-if="node.is_adaptive" class="badge adaptive">自适应新增</span>
                </div>
                <div class="node-title" :title="node.node_name">{{ node.node_name }}</div>
                <div class="node-meta">
                  <span>难度 {{ '★'.repeat(Math.min(5, node.difficulty || 1)) }}</span>
                  <span>{{ node.estimated_min }} 分钟</span>
                </div>
                <div class="node-footer">
                  <span v-if="node.status === 0" class="lock-text">🔒 待解锁</span>
                  <span v-else-if="node.status === 3" class="done-text">✓ 已完成</span>
                  <span v-else-if="(node.learned_resource_count || 0) > 0" class="res-text">
                    已学 {{ node.learned_resource_count }}/{{ node.total_resource_count || node.resource_items?.length || 0 }}
                  </span>
                  <span v-else class="res-text">
                    {{ node.resource_items?.length ? `${node.resource_items.length} 个资源` : '待匹配资源' }}
                  </span>
                </div>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <p class="graph-hint">学习顺序：入门 → 进阶 → 提升 · 点击节点查看右侧详情</p>
  </div>
</template>

<style scoped>
.path-graph {
  --blue: #409eff;
  --text: #1e293b;
  --muted: #64748b;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.graph-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
}

.lg {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--muted);
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
  box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.08);
}
.dot.ready { background: #409eff; }
.dot.learning { background: #f59e0b; }
.dot.done { background: #10b981; }
.dot.locked { background: #cbd5e1; }
.dot.weak { background: #fbbf24; box-shadow: 0 0 0 2px #fff7cc; }
.dot.adaptive { background: #34d399; box-shadow: 0 0 0 2px #e6ffe6; }

.zoom-btns {
  display: flex;
  gap: 6px;
}

.graph-empty {
  min-height: 280px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  background: linear-gradient(160deg, #f8fafc, #eef5ff);
  color: var(--muted);
  font-size: 14px;
}

.graph-canvas {
  position: relative;
  overflow: auto;
  border-radius: 16px;
  min-height: 320px;
  background:
    radial-gradient(circle at 12% 18%, rgba(64, 158, 255, 0.12), transparent 42%),
    radial-gradient(circle at 88% 82%, rgba(16, 185, 129, 0.1), transparent 40%),
    linear-gradient(180deg, #f7faff 0%, #f1f5f9 100%);
  border: 1px solid #e2e8f0;
}

.canvas-inner {
  position: relative;
  transform-origin: top left;
  min-width: max-content;
  padding: 28px 24px 36px;
}

.phase-row {
  display: flex;
  align-items: flex-start;
  gap: 40px;
}

.phase-col {
  width: 236px;
  flex-shrink: 0;
}

.phase-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--phase-bg);
  border: 1px solid color-mix(in srgb, var(--phase-color) 28%, white);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
}

.phase-icon {
  font-size: 20px;
  line-height: 1;
}

.phase-banner strong {
  display: block;
  font-size: 15px;
  color: var(--phase-color);
  letter-spacing: 0.02em;
}

.phase-banner small {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: var(--muted);
}

.phase-banner :deep(.el-tag) {
  margin-left: auto;
}

.phase-nodes {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.graph-node {
  width: 100%;
  text-align: left;
  cursor: pointer;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #fff;
  padding: 12px 14px;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.graph-node:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.12);
  border-color: #93c5fd;
}

.graph-node.is-selected {
  border-color: var(--blue);
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.22), 0 12px 28px rgba(37, 99, 235, 0.14);
}

.graph-node.is-weak {
  background: #fffdf3;
  border-color: #f6d36b;
  border-left: 4px solid #f59e0b;
}

.graph-node.is-adaptive {
  background: #f3fff6;
  border-color: #86efac;
  border-left: 4px solid #10b981;
}

.graph-node.is-locked {
  background: #f8fafc;
  opacity: 0.86;
}

.graph-node.status-1 { border-top: 3px solid #409eff; }
.graph-node.status-2 { border-top: 3px solid #f59e0b; }
.graph-node.status-3 {
  border-top: 3px solid #10b981;
  background: linear-gradient(180deg, #f0fdf4, #fff);
}
.graph-node.status-0 { border-top: 3px solid #cbd5e1; }

.node-top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.status-pill {
  font-size: 11px;
  color: #475569;
  background: #f1f5f9;
  border-radius: 999px;
  padding: 2px 8px;
}

.badge {
  font-size: 10px;
  border-radius: 999px;
  padding: 2px 7px;
  font-weight: 600;
}
.badge.weak {
  color: #b45309;
  background: #fff7cc;
}
.badge.adaptive {
  color: #047857;
  background: #e6ffe6;
}

.node-title {
  font-size: 14px;
  font-weight: 650;
  color: var(--text);
  line-height: 1.4;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 2.8em;
}

.node-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  color: var(--muted);
  margin-bottom: 8px;
}

.node-footer {
  font-size: 12px;
  color: #64748b;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}

.lock-text { color: #94a3b8; }
.done-text { color: #059669; font-weight: 600; }
.res-text { color: #2563eb; }

.graph-hint {
  margin: 0;
  text-align: center;
  font-size: 12px;
  color: #94a3b8;
}

@media (max-width: 960px) {
  .phase-col { width: 210px; }
}
</style>
