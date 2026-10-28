<script setup lang="ts">
import { computed, ref } from 'vue'

interface SourceNode {
  id: string
  label: string
  description?: string
  level?: number
}

interface MapNode extends SourceNode {
  children: MapNode[]
}

interface PositionedNode extends MapNode {
  x: number
  y: number
  depth: number
  parentId?: string
  branchIndex: number
  width: number
  height: number
  color: string
  lines: string[]
  angle: number
}

const props = defineProps<{
  data: Record<string, unknown> | null
  nodes?: SourceNode[]
  edges?: Array<{ from: string; to: string }>
}>()

const selectedId = ref<string | null>(null)
const collapsedIds = ref<Set<string>>(new Set())
const palette = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#06b6d4']

const rawNodes = computed<SourceNode[]>(() => {
  if (props.nodes?.length) return props.nodes
  const d = props.data as { nodes?: SourceNode[] } | null
  return d?.nodes || []
})

const rawEdges = computed(() => {
  if (props.edges?.length) return props.edges
  const d = props.data as { edges?: Array<{ from: string; to: string }> } | null
  return d?.edges || []
})

const treeRoot = computed<MapNode | null>(() => {
  const nodes = rawNodes.value
  if (!nodes.length) return null
  const childIds = new Set(rawEdges.value.map((edge) => edge.to))
  const root = nodes.find((node) => (node.level ?? 1) === 0) || nodes.find((node) => !childIds.has(node.id)) || nodes[0]
  const build = (node: SourceNode, visited = new Set<string>()): MapNode => {
    const nextVisited = new Set(visited)
    nextVisited.add(node.id)
    const children = rawEdges.value
      .filter((edge) => edge.from === node.id)
      .map((edge) => nodes.find((item) => item.id === edge.to))
      .filter((item): item is SourceNode => Boolean(item) && !nextVisited.has(item!.id))
      .map((item) => build(item, nextVisited))
    return { ...node, children }
  }
  return build(root)
})

function leafCount(node: MapNode): number {
  if (!node.children.length || collapsedIds.value.has(node.id)) return 1
  return node.children.reduce((total, child) => total + leafCount(child), 0)
}

function splitLabel(label: string, max = 8): string[] {
  const chars = Array.from(label)
  if (chars.length <= max) return [label]
  const result: string[] = []
  for (let i = 0; i < chars.length; i += max) result.push(chars.slice(i, i + max).join(''))
  return result.slice(0, 2)
}

/** 从中心指向目标，落在圆/矩形外缘 */
function boundaryPoint(
  node: PositionedNode,
  tx: number,
  ty: number,
  pad = 2,
): { x: number; y: number } {
  const dx = tx - node.x
  const dy = ty - node.y
  if (dx === 0 && dy === 0) return { x: node.x, y: node.y }
  if (node.depth === 0) {
    const r = 56 + pad
    const dist = Math.hypot(dx, dy) || 1
    return { x: node.x + (dx / dist) * r, y: node.y + (dy / dist) * r }
  }
  const hw = node.width / 2 + pad
  const hh = node.height / 2 + pad
  const scale = 1 / Math.max(Math.abs(dx) / hw, Math.abs(dy) / hh)
  return { x: node.x + dx * scale, y: node.y + dy * scale }
}

const layout = computed(() => {
  const root = treeRoot.value
  if (!root) return { nodes: [] as PositionedNode[], byId: new Map<string, PositionedNode>() }

  const nodes: PositionedNode[] = []
  const byId = new Map<string, PositionedNode>()
  const centerX = 600
  const centerY = 390
  const gap = 0.045 // 分支间最小角缝，减少线交叉感

  const place = (node: MapNode, depth: number, start: number, end: number, parentId?: string, branchIndex = 0) => {
    const span = end - start
    const angle = depth === 0 ? -Math.PI / 2 : (start + end) / 2
    // 椭圆半径：层级拉开，叶子略外扩，避免挤在一起
    const radiusX = depth === 0 ? 0 : depth === 1 ? 268 : Math.min(490, 268 + (depth - 1) * 198)
    const radiusY = depth === 0 ? 0 : depth === 1 ? 188 : Math.min(310, 188 + (depth - 1) * 118)
    const lines = splitLabel(node.label, depth === 0 ? 9 : depth === 1 ? 7 : 8)
    const item: PositionedNode = {
      ...node,
      x: centerX + Math.cos(angle) * radiusX,
      y: centerY + Math.sin(angle) * radiusY,
      depth,
      parentId,
      branchIndex,
      width: depth === 0 ? 172 : depth === 1 ? 158 : 136,
      height: depth === 0 ? 66 : lines.length > 1 ? 58 : 44,
      color: depth === 0 ? '#2563eb' : palette[branchIndex % palette.length],
      lines,
      angle,
    }
    nodes.push(item)
    byId.set(item.id, item)

    if (!node.children.length || collapsedIds.value.has(node.id)) return

    const n = node.children.length
    // 一级分支：等角均分，观感更整齐；更深层仍按叶子权重分配扇区
    if (depth === 0) {
      const slice = (Math.PI * 2) / n
      node.children.forEach((child, index) => {
        const a0 = -Math.PI / 2 + index * slice + gap
        const a1 = -Math.PI / 2 + (index + 1) * slice - gap
        place(child, 1, a0, a1, node.id, index)
      })
      return
    }

    const childTotal = node.children.reduce((total, child) => total + leafCount(child), 0)
    const usable = Math.max(0.08, span - gap * 2)
    let childCursor = start + gap
    node.children.forEach((child) => {
      const ratio = leafCount(child) / childTotal
      const childEnd = childCursor + usable * ratio
      place(child, depth + 1, childCursor, childEnd, node.id, branchIndex)
      childCursor = childEnd
    })
  }

  place(root, 0, 0, Math.PI * 2)
  return { nodes, byId }
})

const edges = computed(() => layout.value.nodes.filter((node) => node.parentId))
const selectedNode = computed(() => layout.value.byId.get(selectedId.value || '') || null)

/** 沿径向的平滑三次贝塞尔，从节点外缘到外缘，避免穿过卡片 */
function edgePath(child: PositionedNode): string {
  const parent = layout.value.byId.get(child.parentId || '')
  if (!parent) return ''
  const start = boundaryPoint(parent, child.x, child.y, 3)
  const end = boundaryPoint(child, parent.x, parent.y, 3)
  const dx = end.x - start.x
  const dy = end.y - start.y
  const dist = Math.hypot(dx, dy) || 1
  // 控制点沿连线方向，弯曲幅度随距离自适应，斜向时不再出现硬直角折线
  const t = Math.min(0.42, Math.max(0.28, 90 / dist))
  const c1x = start.x + dx * t
  const c1y = start.y + dy * t
  const c2x = end.x - dx * t
  const c2y = end.y - dy * t
  return `M ${start.x.toFixed(1)} ${start.y.toFixed(1)} C ${c1x.toFixed(1)} ${c1y.toFixed(1)}, ${c2x.toFixed(1)} ${c2y.toFixed(1)}, ${end.x.toFixed(1)} ${end.y.toFixed(1)}`
}

function toggleNode(node: PositionedNode) {
  selectedId.value = node.id
  if (!node.children.length) return
  const next = new Set(collapsedIds.value)
  if (next.has(node.id)) next.delete(node.id)
  else next.add(node.id)
  collapsedIds.value = next
}

function expandAll() {
  collapsedIds.value = new Set()
}

function collapseBranches() {
  const root = treeRoot.value
  collapsedIds.value = new Set(root?.children.map((child) => child.id) || [])
}
</script>

<template>
  <div class="mindmap-interactive">
    <div v-if="!treeRoot" class="empty"><el-empty description="暂无导图数据" /></div>
    <template v-else>
      <div class="map-toolbar">
        <span><i /> 交互式思维导图</span>
        <div>
          <el-button size="small" text @click="expandAll">展开全部</el-button>
          <el-button size="small" text @click="collapseBranches">收起分支</el-button>
        </div>
      </div>
      <div class="map-stage">
        <svg viewBox="0 0 1200 780" role="img" :aria-label="`${treeRoot.label} 知识思维导图`">
          <defs>
            <filter id="map-shadow" x="-30%" y="-40%" width="160%" height="180%">
              <feDropShadow dx="0" dy="3" stdDeviation="4" flood-opacity=".12" />
            </filter>
            <radialGradient id="root-gradient" cx="35%" cy="30%" r="70%">
              <stop offset="0" stop-color="#93c5fd" />
              <stop offset="0.55" stop-color="#3b82f6" />
              <stop offset="1" stop-color="#1d4ed8" />
            </radialGradient>
            <linearGradient
              v-for="node in edges"
              :id="`edge-grad-${node.id}`"
              :key="`grad-${node.id}`"
              gradientUnits="userSpaceOnUse"
              :x1="layout.byId.get(node.parentId || '')?.x || 0"
              :y1="layout.byId.get(node.parentId || '')?.y || 0"
              :x2="node.x"
              :y2="node.y"
            >
              <stop offset="0" :stop-color="layout.byId.get(node.parentId || '')?.color || node.color" stop-opacity="0.35" />
              <stop offset="1" :stop-color="node.color" stop-opacity="0.75" />
            </linearGradient>
          </defs>

          <g class="edges-layer">
            <path
              v-for="node in edges"
              :key="`edge-${node.id}`"
              :d="edgePath(node)"
              class="map-edge"
              :stroke="`url(#edge-grad-${node.id})`"
              :stroke-width="node.depth === 1 ? 2.8 : 2.1"
            />
          </g>

          <g
            v-for="node in layout.nodes"
            :key="node.id"
            class="map-node"
            :class="{ selected: selectedId === node.id, root: node.depth === 0, collapsible: node.children.length }"
            @click="toggleNode(node)"
          >
            <circle
              v-if="node.depth === 0"
              :cx="node.x"
              :cy="node.y"
              r="56"
              fill="url(#root-gradient)"
              filter="url(#map-shadow)"
            />
            <rect
              v-else
              :x="node.x - node.width / 2"
              :y="node.y - node.height / 2"
              :width="node.width"
              :height="node.height"
              rx="14"
              fill="#fff"
              :stroke="node.color"
              :stroke-width="selectedId === node.id ? 2.5 : 1.6"
              filter="url(#map-shadow)"
            />
            <rect
              v-if="node.depth > 0"
              :x="node.x - node.width / 2"
              :y="node.y - node.height / 2"
              :width="5"
              :height="node.height"
              :rx="2"
              :fill="node.color"
              opacity="0.9"
            />
            <text
              :x="node.x"
              :y="node.y - (node.lines.length - 1) * 8"
              text-anchor="middle"
              dominant-baseline="middle"
              :fill="node.depth === 0 ? '#fff' : '#1e293b'"
              :font-size="node.depth === 0 ? 18 : node.depth === 1 ? 14 : 12.5"
              :font-weight="node.depth < 2 ? 700 : 600"
            >
              <tspan
                v-for="(line, index) in node.lines"
                :key="`${node.id}-${index}`"
                :x="node.x"
                :dy="index === 0 ? 0 : 16"
              >{{ line }}</tspan>
            </text>
            <g v-if="node.children.length && node.depth > 0" class="toggle-badge">
              <circle
                :cx="node.x + node.width / 2 - 2"
                :cy="node.y + node.height / 2 - 2"
                r="9"
                fill="#fff"
                :stroke="node.color"
                stroke-width="1.4"
              />
              <text
                :x="node.x + node.width / 2 - 2"
                :y="node.y + node.height / 2 - 1.5"
                text-anchor="middle"
                dominant-baseline="middle"
                :fill="node.color"
                font-size="12"
                font-weight="700"
              >{{ collapsedIds.has(node.id) ? '+' : '−' }}</text>
            </g>
          </g>
        </svg>
        <p class="map-hint">点击节点查看说明；角落按钮可收起 / 展开分支</p>
      </div>
      <transition name="detail">
        <aside v-if="selectedNode" class="node-detail" :style="{ '--accent': selectedNode.color }">
          <span class="detail-dot" />
          <div>
            <strong>{{ selectedNode.label }}</strong>
            <p>{{ selectedNode.description || '该节点是当前知识结构中的关联知识点。' }}</p>
          </div>
        </aside>
      </transition>
    </template>
  </div>
</template>

<style scoped lang="scss">
.mindmap-interactive {
  padding: 18px;
  border: 1px solid #e5edf9;
  border-radius: $radius-lg;
  background: linear-gradient(160deg, #f7fbff 0%, #fff 48%, #f8fafc 100%);
  min-height: 420px;
}
.empty { min-height: 280px; display: grid; place-items: center; }
.map-toolbar {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  color: $text-primary; font-weight: 600; padding: 0 4px 10px;
  span { display: flex; align-items: center; gap: 8px; }
  i { width: 9px; height: 9px; border-radius: 50%; background: #2563eb; box-shadow: 0 0 0 5px #dbeafe; }
}
.map-stage {
  position: relative; overflow: hidden; border-radius: 16px;
  border: 1px solid #e8eef6;
  background:
    radial-gradient(ellipse 70% 55% at 50% 48%, #fff 0%, #f5f9ff 55%, #eef3fb 100%);
}
.map-stage::before {
  content: ''; position: absolute; inset: 0; pointer-events: none;
  background-image: radial-gradient(#c5d0de 0.9px, transparent 0.9px);
  background-size: 20px 20px; opacity: .18;
}
svg { position: relative; z-index: 1; display: block; width: 100%; min-width: 720px; height: auto; }
.map-edge {
  fill: none;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.map-node { cursor: pointer; }
.map-node:hover rect:first-of-type { filter: brightness(1.03); }
.map-node.selected circle:first-of-type { stroke: #fff; stroke-width: 3.5; }
.map-node text { pointer-events: none; font-family: inherit; }
.toggle-badge { pointer-events: none; }
.map-hint {
  position: absolute; z-index: 2; bottom: 12px; left: 50%; transform: translateX(-50%);
  margin: 0; padding: 6px 14px; border-radius: 999px;
  background: rgba(255, 255, 255, .9); color: $text-secondary; font-size: 12px;
  white-space: nowrap; box-shadow: 0 2px 8px rgba(15, 23, 42, .06);
}
.node-detail {
  --accent: #2563eb;
  display: flex; gap: 11px; align-items: flex-start; margin-top: 14px;
  padding: 14px 16px; border: 1px solid color-mix(in srgb, var(--accent) 24%, white);
  border-radius: 12px; background: #fff; box-shadow: 0 3px 12px rgba(15, 23, 42, .05);
  .detail-dot { margin-top: 6px; width: 10px; height: 10px; border-radius: 50%; flex: 0 0 10px; background: var(--accent); }
  strong { color: $text-primary; }
  p { margin: 4px 0 0; color: $text-secondary; line-height: 1.65; }
}
.detail-enter-active, .detail-leave-active { transition: all .2s ease; }
.detail-enter-from, .detail-leave-to { opacity: 0; transform: translateY(-6px); }
@media (max-width: 760px) {
  .mindmap-interactive { padding: 10px; }
  .map-stage { overflow-x: auto; }
  .map-toolbar { align-items: flex-start; flex-direction: column; }
}
</style>
