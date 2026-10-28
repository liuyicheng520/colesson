<script setup lang="ts">
import {
  computed,
  onMounted,
  onUnmounted,
  ref,
  shallowRef,
  watch,
  watchEffect,
} from 'vue'
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type Simulation,
  type SimulationLinkDatum,
} from 'd3-force'
import { Search, FullScreen, RefreshRight, Share } from '@element-plus/icons-vue'
import {
  GRAPH_W,
  GRAPH_H,
  NODE_COLORS,
  buildGraph,
  nodeColor,
  typeLabel,
  type GEdge,
  type GNode,
  type GraphNoteMeta,
} from '@/lib/resourceKnowledgeGraph'

const props = withDefaults(
  defineProps<{
    notes: GraphNoteMeta[]
    focusId?: string | null
    focusTitle?: string | null
  }>(),
  {
    focusId: null,
    focusTitle: null,
  },
)

const emit = defineEmits<{
  open: [relPath: string]
  focusConsumed: []
}>()

const FILTERS = [
  { key: 'all', label: '全部', color: '' },
  { key: 'document', label: '课程讲义', color: NODE_COLORS.document },
  { key: 'question', label: '分层习题', color: NODE_COLORS.question },
  { key: 'mindmap', label: '知识图谱', color: NODE_COLORS.mindmap },
  { key: 'reading', label: '拓展阅读', color: NODE_COLORS.reading },
  { key: 'code', label: '实战演练', color: NODE_COLORS.code },
  { key: 'video', label: 'AI视频讲解', color: NODE_COLORS.video },
  { key: 'topic', label: '主题', color: NODE_COLORS.topic },
] as const

interface Cam {
  x: number
  y: number
  k: number
}

interface LiveNode extends GNode {
  vx?: number
  vy?: number
  fx?: number | null
  fy?: number | null
}

interface LiveLink extends SimulationLinkDatum<LiveNode> {
  source: string | LiveNode
  target: string | LiveNode
}

type DragState =
  | { mode: 'pan'; lx: number; ly: number }
  | { mode: 'node'; id: string; moved: boolean; wasSelected: boolean }
  | null

const filter = ref('all')
const query = ref('')
const sel = ref<string | null>(null)
const hoverId = ref<string | null>(null)
const hoverHint = ref('')
const visibleCount = ref(Number.POSITIVE_INFINITY)
const playing = ref(false)
const didAutoPlayedRef = ref(false)
const layoutReady = ref(0)
const zoomPct = ref(100)

const wrapRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const miniRef = ref<HTMLCanvasElement | null>(null)

const camRef = ref<Cam>({ x: 0, y: 0, k: 1 })
const dragRef = ref<DragState>(null)
const miniDragRef = ref(false)
const sizeRef = ref({ w: GRAPH_W, h: GRAPH_H, dpr: 1 })
const liveNodesRef = shallowRef<LiveNode[]>([])
const liveByIdRef = ref(new Map<string, LiveNode>())
const edgesRef = ref<GEdge[]>([])
const simRef = ref<Simulation<LiveNode, LiveLink> | null>(null)
const pulseRafRef = ref(0)
const drawRef = ref<() => void>(() => {})
const drawMiniRef = ref<() => void>(() => {})
const rippleRef = ref<{ id: string; t0: number } | null>(null)
const miniMapRef = ref({
  minX: 0,
  minY: 0,
  scale: 1,
  pad: 8,
  mw: 148,
  mh: 108,
})
const didAutoFitRef = ref(false)

/** 学生端固定浅色主题 */
const themeRef = { dark: false }

const reduceMotion =
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

const uiRef = ref({
  filter: filter.value,
  query: query.value,
  sel: sel.value,
  hoverId: hoverId.value,
  visibleCount: visibleCount.value,
  orderedIds: [] as string[],
})

const graph = computed(() => buildGraph(props.notes))

const ordered = computed(() =>
  [...graph.value.nodes].sort((a, b) => a.t - b.t || a.label.localeCompare(b.label, 'zh')),
)

// ⚠️ 必须定义在 ordered 之后：watchEffect 首次同步执行，若 ordered 仍处于 TDZ 会抛错，
// 且只追踪到 visibleCount，导致 uiRef.orderedIds 长期为空、画布渲染不出节点。
watchEffect(() => {
  uiRef.value = {
    filter: filter.value,
    query: query.value,
    sel: sel.value,
    hoverId: hoverId.value,
    visibleCount: visibleCount.value,
    orderedIds: ordered.value.map((n) => n.id),
  }
})

const hasDates = computed(() =>
  graph.value.nodes.some((n) => n.type !== 'tag' && n.type !== 'topic' && n.created),
)

const empty = computed(() => graph.value.nodes.length === 0)

const shown = computed(() =>
  Math.min(Number.isFinite(visibleCount.value) ? visibleCount.value : ordered.value.length, ordered.value.length),
)

const selNode = computed(() => (sel.value ? liveByIdRef.value.get(sel.value) : undefined))

const neighbors = computed(() => {
  void layoutReady.value
  if (!sel.value) return [] as LiveNode[]
  const conn = connOf(sel.value, edgesRef.value)
  return [...conn]
    .filter((id) => id !== sel.value)
    .map((id) => liveByIdRef.value.get(id))
    .filter((n): n is LiveNode => !!n)
    .sort((a, b) => b.deg - a.deg)
})

function matchesQuery(n: GNode, q: string): boolean {
  const qq = q.trim().toLowerCase()
  return !qq || n.label.toLowerCase().includes(qq)
}

function revealedSet(count: number, ids: string[]): Set<string> {
  const set = new Set<string>()
  const limit = Math.min(count, ids.length)
  for (let i = 0; i < limit; i++) set.add(ids[i]!)
  return set
}

function connOf(id: string | null, edges: GEdge[]): Set<string> {
  if (!id) return new Set<string>()
  const s = new Set<string>([id])
  for (const e of edges) {
    if (e.source === id) s.add(e.target)
    if (e.target === id) s.add(e.source)
  }
  return s
}

function isHubType(type: string): boolean {
  return type === 'tag' || type === 'topic'
}

function syncZoomPct(): void {
  zoomPct.value = Math.round(camRef.value.k * 100)
}

function resetCam(): void {
  const { w, h } = sizeRef.value
  const k = Math.min(w / GRAPH_W, h / GRAPH_H) * 0.92
  camRef.value = {
    x: (w - GRAPH_W * k) / 2,
    y: (h - GRAPH_H * k) / 2,
    k,
  }
  syncZoomPct()
  drawRef.value()
}

function fitNodes(): void {
  const { w, h } = sizeRef.value
  const nodes = liveNodesRef.value
  if (!nodes.length || w < 40 || h < 40) {
    resetCam()
    return
  }
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const n of nodes) {
    minX = Math.min(minX, n.x - n.r)
    minY = Math.min(minY, n.y - n.r)
    maxX = Math.max(maxX, n.x + n.r)
    maxY = Math.max(maxY, n.y + n.r)
  }
  const pad = 48
  const bw = Math.max(40, maxX - minX)
  const bh = Math.max(40, maxY - minY)
  const k = Math.min(3.2, Math.max(0.35, Math.min((w - pad * 2) / bw, (h - pad * 2) / bh)))
  camRef.value = {
    k,
    x: w / 2 - ((minX + maxX) / 2) * k,
    y: h / 2 - ((minY + maxY) / 2) * k,
  }
  syncZoomPct()
  drawRef.value()
}

function reheat(target = 0.35): void {
  const sim = simRef.value
  if (!sim) return
  sim.alphaTarget(target).restart()
  window.setTimeout(() => {
    if (simRef.value === sim && !dragRef.value) sim.alphaTarget(0)
  }, 900)
}

function screenToWorld(sx: number, sy: number): { x: number; y: number } {
  const cam = camRef.value
  return { x: (sx - cam.x) / cam.k, y: (sy - cam.y) / cam.k }
}

function hitTest(sx: number, sy: number): LiveNode | null {
  const ui = uiRef.value
  const w = screenToWorld(sx, sy)
  const revealed = revealedSet(ui.visibleCount, ui.orderedIds)
  const q = ui.query
  const focus = ui.hoverId || ui.sel
  const conn = connOf(focus, edgesRef.value)
  let best: LiveNode | null = null
  let bestD = Infinity
  for (const n of liveNodesRef.value) {
    if (!revealed.has(n.id)) continue
    if (ui.filter !== 'all' && n.type !== ui.filter) continue
    if (!matchesQuery(n, q) && !(focus && conn.has(n.id))) continue
    const dx = n.x - w.x
    const dy = n.y - w.y
    const d = Math.hypot(dx, dy)
    const r = n.r + 6 / camRef.value.k
    if (d <= r && d < bestD) {
      best = n
      bestD = d
    }
  }
  return best
}

function playGrowth(): void {
  if (playing.value) {
    playing.value = false
    visibleCount.value = Number.POSITIVE_INFINITY
    return
  }
  sel.value = null
  visibleCount.value = 0
  playing.value = true
}

// 数据从无到有时直接全量显示（生长动画保留为按钮可点）。
// 注意：不能挂在 layoutReady 上——布局就绪常早于数据到达，空数据会把状态瞬间消费掉；
// 自动播放生长动画也存在与数据二次加载的竞态，节点可见性必须无条件保证。
watch(
  () => ordered.value.length,
  (n) => {
    if (n <= 0 || didAutoPlayedRef.value) return
    didAutoPlayedRef.value = true
    visibleCount.value = Number.POSITIVE_INFINITY
    drawRef.value?.()
  },
  // post：等 watchEffect 把 uiRef 快照刷新后再绘制；pre-flush 时读到的是旧快照会画出空画布
  { flush: 'post' },
)

function installDraw(): void {
  drawRef.value = () => {
    const canvas = canvasRef.value
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const { w, h, dpr } = sizeRef.value
    const cam = camRef.value
    const ui = uiRef.value
    const nodes = liveNodesRef.value
    const byId = liveByIdRef.value
    const edges = edgesRef.value
    const q = ui.query.trim().toLowerCase()
    const revealed = revealedSet(ui.visibleCount, ui.orderedIds)
    const focus = ui.hoverId || ui.sel
    const conn = connOf(focus, edges)
    const t = performance.now()

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, w, h)

    const dark = themeRef.dark
    const palette = dark
      ? {
          bg0: '#121a2e',
          bg1: '#070b16',
          edgeDim: '#64748b',
          edge: '#94a3b8',
          edgeHot: '#38bdf8',
          label: '#e8eef8',
          ring: '#e2e8f0',
          ringHover: 'rgba(226,232,240,0.7)',
          ghost: '#94a3b8',
        }
      : {
          bg0: '#f4f6f8',
          bg1: '#e8edf2',
          edgeDim: '#94a3b8',
          edge: '#7b8798',
          edgeHot: '#2f5d8c',
          label: '#1c2430',
          ring: '#2f5d8c',
          ringHover: 'rgba(47,93,140,0.55)',
          ghost: '#9aa3b0',
        }

    const g = ctx.createRadialGradient(w * 0.5, h * 0.4, 20, w * 0.5, h * 0.5, Math.max(w, h) * 0.7)
    g.addColorStop(0, palette.bg0)
    g.addColorStop(1, palette.bg1)
    ctx.fillStyle = g
    ctx.fillRect(0, 0, w, h)

    ctx.save()
    ctx.translate(cam.x, cam.y)
    ctx.scale(cam.k, cam.k)

    const drawEdge = (e: GEdge, alpha: number, width: number, color: string, flow = false) => {
      const a = byId.get(e.source)
      const b = byId.get(e.target)
      if (!a || !b) return
      if (!revealed.has(a.id) || !revealed.has(b.id)) return
      ctx.beginPath()
      ctx.moveTo(a.x, a.y)
      ctx.lineTo(b.x, b.y)
      ctx.strokeStyle = color
      ctx.globalAlpha = alpha
      ctx.lineWidth = width / cam.k
      if (flow && !reduceMotion) {
        const dash = 6 / cam.k
        ctx.setLineDash([dash, dash * 1.2])
        ctx.lineDashOffset = -t / 40
      } else {
        ctx.setLineDash([])
      }
      ctx.stroke()
      ctx.setLineDash([])
      ctx.globalAlpha = 1
    }

    for (const e of edges) {
      const a = byId.get(e.source)
      const b = byId.get(e.target)
      if (!a || !b) continue
      if (!revealed.has(a.id) || !revealed.has(b.id)) continue

      let dim = false
      let hl = false
      if (ui.filter !== 'all' && a.type !== ui.filter && b.type !== ui.filter) dim = true
      if (q && !matchesQuery(a, q) && !matchesQuery(b, q)) dim = true
      if (focus) {
        if (e.source === focus || e.target === focus) {
          hl = true
          dim = false
        } else if (ui.filter === 'all' && !q) dim = true
      }
      if (dim) drawEdge(e, dark ? 0.05 : 0.08, 1, palette.edgeDim)
      else if (hl) drawEdge(e, 0.95, 2.4, palette.edgeHot, true)
      else drawEdge(e, dark ? 0.32 : 0.38, 1.2, palette.edge)
    }

    for (const n of nodes) {
      if (!revealed.has(n.id)) continue
      let dim = false
      if (ui.filter !== 'all' && n.type !== ui.filter) dim = true
      if (q && !matchesQuery(n, q) && !(focus && conn.has(n.id))) dim = true
      if (focus && !conn.has(n.id)) dim = true

      const color = nodeColor(n.type)
      const isHot = ui.sel === n.id || ui.hoverId === n.id
      const pulse = isHot && !reduceMotion ? 1 + 0.1 * Math.sin(t / 220) : 1
      const r = n.r * pulse

      ctx.globalAlpha = dim ? 0.12 : 0.95

      if (!dim && (isHot || n.deg >= 3)) {
        ctx.beginPath()
        ctx.arc(n.x, n.y, r + (isHot ? 12 : 8), 0, Math.PI * 2)
        ctx.fillStyle = color
        ctx.globalAlpha = dim ? 0.05 : isHot ? 0.28 : 0.16
        ctx.fill()
        ctx.globalAlpha = dim ? 0.12 : 0.95
      }

      const rip = rippleRef.value
      if (rip && rip.id === n.id && !reduceMotion) {
        const age = (t - rip.t0) / 200
        if (age < 1) {
          ctx.beginPath()
          ctx.arc(n.x, n.y, r + 4 + age * 18, 0, Math.PI * 2)
          ctx.strokeStyle = color
          ctx.globalAlpha = 0.55 * (1 - age)
          ctx.lineWidth = 2 / cam.k
          ctx.stroke()
          ctx.globalAlpha = dim ? 0.12 : 0.95
        }
      }

      ctx.beginPath()
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2)
      ctx.fillStyle = color
      ctx.fill()

      if (ui.sel === n.id) {
        ctx.strokeStyle = palette.ring
        ctx.lineWidth = 2.5 / cam.k
        ctx.stroke()
      } else if (ui.hoverId === n.id) {
        ctx.strokeStyle = palette.ringHover
        ctx.lineWidth = 1.8 / cam.k
        ctx.stroke()
      }

      const labelOk = cam.k >= 0.85 || n.deg >= 4 || isHot || (q && matchesQuery(n, q))
      const showLabel =
        (n.showLabel || isHot || (q && matchesQuery(n, q))) && !dim && labelOk
      if (showLabel) {
        ctx.font = `12px var(--rkg-font-ui, system-ui), sans-serif`
        ctx.fillStyle = palette.label
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        ctx.globalAlpha = dim ? 0.2 : cam.k < 1 ? 0.75 : 0.92
        ctx.fillText(n.label.length > 18 ? n.label.slice(0, 17) + '…' : n.label, n.x, n.y + r + 4)
      }
      ctx.globalAlpha = 1
    }

    if (nodes.length === 0) {
      ctx.globalAlpha = dark ? 0.15 : 0.22
      for (let i = 0; i < 5; i++) {
        ctx.beginPath()
        ctx.arc(GRAPH_W * (0.3 + i * 0.1), GRAPH_H * (0.4 + (i % 2) * 0.08), 8 + i, 0, Math.PI * 2)
        ctx.fillStyle = palette.ghost
        ctx.fill()
      }
      ctx.globalAlpha = 1
    }

    ctx.restore()
    drawMiniRef.value()
  }

  drawMiniRef.value = () => {
    const mini = miniRef.value
    if (!mini) return
    const mctx = mini.getContext('2d')
    if (!mctx) return
    const nodes = liveNodesRef.value
    const dark = themeRef.dark
    const mw = 148
    const mh = 108
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    if (mini.width !== Math.floor(mw * dpr) || mini.height !== Math.floor(mh * dpr)) {
      mini.width = Math.floor(mw * dpr)
      mini.height = Math.floor(mh * dpr)
      mini.style.width = mw + 'px'
      mini.style.height = mh + 'px'
    }
    mctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    mctx.clearRect(0, 0, mw, mh)
    mctx.fillStyle = dark ? 'rgba(7,11,22,0.82)' : 'rgba(255,255,255,0.88)'
    mctx.strokeStyle = dark ? 'rgba(148,163,184,0.35)' : 'rgba(47,93,140,0.28)'
    mctx.lineWidth = 1
    mctx.beginPath()
    mctx.roundRect(0.5, 0.5, mw - 1, mh - 1, 8)
    mctx.fill()
    mctx.stroke()

    if (!nodes.length) return

    let minX = Infinity
    let minY = Infinity
    let maxX = -Infinity
    let maxY = -Infinity
    for (const n of nodes) {
      minX = Math.min(minX, n.x - n.r)
      minY = Math.min(minY, n.y - n.r)
      maxX = Math.max(maxX, n.x + n.r)
      maxY = Math.max(maxY, n.y + n.r)
    }
    const pad = 10
    const bw = Math.max(40, maxX - minX)
    const bh = Math.max(40, maxY - minY)
    const scale = Math.min((mw - pad * 2) / bw, (mh - pad * 2) / bh)
    miniMapRef.value = { minX, minY, scale, pad, mw, mh }

    const toMini = (x: number, y: number) => ({
      x: pad + (x - minX) * scale,
      y: pad + (y - minY) * scale,
    })

    for (const e of edgesRef.value) {
      const a = liveByIdRef.value.get(e.source)
      const b = liveByIdRef.value.get(e.target)
      if (!a || !b) continue
      const pa = toMini(a.x, a.y)
      const pb = toMini(b.x, b.y)
      mctx.beginPath()
      mctx.moveTo(pa.x, pa.y)
      mctx.lineTo(pb.x, pb.y)
      mctx.strokeStyle = dark ? 'rgba(148,163,184,0.35)' : 'rgba(123,135,152,0.45)'
      mctx.lineWidth = 0.8
      mctx.stroke()
    }

    for (const n of nodes) {
      const p = toMini(n.x, n.y)
      mctx.beginPath()
      mctx.arc(p.x, p.y, Math.max(1.6, n.r * scale * 0.45), 0, Math.PI * 2)
      mctx.fillStyle = nodeColor(n.type)
      mctx.globalAlpha = 0.9
      mctx.fill()
    }
    mctx.globalAlpha = 1

    const { w, h } = sizeRef.value
    const cam = camRef.value
    const vx0 = -cam.x / cam.k
    const vy0 = -cam.y / cam.k
    const vx1 = (w - cam.x) / cam.k
    const vy1 = (h - cam.y) / cam.k
    const a = toMini(vx0, vy0)
    const b = toMini(vx1, vy1)
    mctx.strokeStyle = dark ? '#38bdf8' : '#2f5d8c'
    mctx.lineWidth = 1.4
    mctx.strokeRect(
      Math.min(a.x, b.x),
      Math.min(a.y, b.y),
      Math.max(8, Math.abs(b.x - a.x)),
      Math.max(8, Math.abs(b.y - a.y)),
    )
  }

  drawRef.value()
}

function rebuildSimulation(): void {
  simRef.value?.stop()
  const g = graph.value
  const nodes: LiveNode[] = g.nodes.map((n) => ({ ...n, vx: 0, vy: 0, fx: null, fy: null }))
  liveNodesRef.value = nodes
  liveByIdRef.value = new Map(nodes.map((n) => [n.id, n]))
  edgesRef.value = g.edges.map((e) => ({ ...e }))

  const links: LiveLink[] = g.edges.map((e) => ({ source: e.source, target: e.target }))

  const sim = forceSimulation(nodes)
    .force(
      'link',
      forceLink<LiveNode, LiveLink>(links)
        .id((d) => d.id)
        .distance((l) => {
          const a =
            typeof l.source === 'object' ? l.source : liveByIdRef.value.get(String(l.source))
          const b =
            typeof l.target === 'object' ? l.target : liveByIdRef.value.get(String(l.target))
          const ra = a?.r ?? 10
          const rb = b?.r ?? 10
          return 70 + ra + rb
        })
        .strength(0.45),
    )
    .force('charge', forceManyBody<LiveNode>().strength((d) => (isHubType(d.type) ? -140 : -200)))
    .force('center', forceCenter(GRAPH_W / 2, GRAPH_H / 2).strength(0.04))
    .force('x', forceX(GRAPH_W / 2).strength(0.035))
    .force('y', forceY(GRAPH_H / 2).strength(0.03))
    .force(
      'collide',
      forceCollide<LiveNode>()
        .radius((d) => d.r + 14)
        .strength(0.85),
    )
    .velocityDecay(0.35)
    .alphaDecay(0.022)
    .alphaMin(0.001)
    .alpha(0.55)
    .on('tick', () => drawRef.value())

  simRef.value = sim
  layoutReady.value += 1
  drawRef.value()
}

function onKeyDown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && sel.value) {
    e.preventDefault()
    sel.value = null
  }
}

function onCanvasPointerDown(e: PointerEvent): void {
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const sx = e.clientX - rect.left
  const sy = e.clientY - rect.top
  const hit = hitTest(sx, sy)
  if (hit) {
    hoverId.value = hit.id
    hoverHint.value = hit.label + ' · ' + typeLabel(hit.type)
    const world = screenToWorld(sx, sy)
    hit.fx = world.x
    hit.fy = world.y
    dragRef.value = {
      mode: 'node',
      id: hit.id,
      moved: false,
      wasSelected: sel.value === hit.id,
    }
    simRef.value?.alphaTarget(0.28).restart()
    canvas.setPointerCapture(e.pointerId)
    canvas.style.cursor = 'grabbing'
  } else {
    sel.value = null
    dragRef.value = { mode: 'pan', lx: e.clientX, ly: e.clientY }
    canvas.setPointerCapture(e.pointerId)
    canvas.style.cursor = 'grabbing'
  }
}

function onCanvasPointerMove(e: PointerEvent): void {
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const sx = e.clientX - rect.left
  const sy = e.clientY - rect.top
  const drag = dragRef.value

  if (drag?.mode === 'pan') {
    const dx = e.clientX - drag.lx
    const dy = e.clientY - drag.ly
    drag.lx = e.clientX
    drag.ly = e.clientY
    camRef.value.x += dx
    camRef.value.y += dy
    drawRef.value()
    return
  }

  if (drag?.mode === 'node') {
    const node = liveByIdRef.value.get(drag.id)
    if (node) {
      const world = screenToWorld(sx, sy)
      node.fx = world.x
      node.fy = world.y
      drag.moved = true
      drawRef.value()
    }
    return
  }

  const hit = hitTest(sx, sy)
  const nextId = hit?.id ?? null
  if (nextId !== hoverId.value) hoverId.value = nextId
  hoverHint.value = hit ? hit.label + ' · ' + typeLabel(hit.type) + ' · 拖拽移动' : ''
  canvas.style.cursor = hit ? 'grab' : 'grab'
}

function onCanvasPointerUp(e: PointerEvent): void {
  const canvas = canvasRef.value
  const drag = dragRef.value
  if (drag?.mode === 'node') {
    const node = liveByIdRef.value.get(drag.id)
    if (node) {
      node.fx = null
      node.fy = null
    }
    if (drag.moved) {
      sel.value = drag.id
    } else {
      sel.value = drag.wasSelected ? null : drag.id
    }
    simRef.value?.alphaTarget(0)
  }
  dragRef.value = null
  try {
    ;(e.target as HTMLElement).releasePointerCapture(e.pointerId)
  } catch {
    /* already released */
  }
  if (canvas) {
    const rect = canvas.getBoundingClientRect()
    const hit = hitTest(e.clientX - rect.left, e.clientY - rect.top)
    canvas.style.cursor = hit ? 'grab' : 'grab'
  }
}

function onCanvasPointerLeave(): void {
  if (!dragRef.value) {
    hoverId.value = null
    hoverHint.value = ''
  }
}

function onCanvasDoubleClick(e: MouseEvent): void {
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const hit = hitTest(e.clientX - rect.left, e.clientY - rect.top)
  if (hit?.relPath) emit('open', hit.relPath)
}

function onMiniPointerDown(e: PointerEvent): void {
  e.stopPropagation()
  const mini = miniRef.value
  if (!mini) return
  miniDragRef.value = true
  mini.setPointerCapture(e.pointerId)
  panMiniToEvent(e)
}

function onMiniPointerMove(e: PointerEvent): void {
  if (!miniDragRef.value) return
  e.stopPropagation()
  panMiniToEvent(e)
}

function onMiniPointerUp(e: PointerEvent): void {
  miniDragRef.value = false
  try {
    ;(e.target as HTMLElement).releasePointerCapture(e.pointerId)
  } catch {
    /* already released */
  }
}

function panMiniToEvent(e: PointerEvent): void {
  const mini = miniRef.value
  if (!mini) return
  const rect = mini.getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top
  const { minX, minY, scale, pad } = miniMapRef.value
  const wx = minX + (mx - pad) / scale
  const wy = minY + (my - pad) / scale
  const { w, h } = sizeRef.value
  const cam = camRef.value
  camRef.value = {
    k: cam.k,
    x: w / 2 - wx * cam.k,
    y: h / 2 - wy * cam.k,
  }
  syncZoomPct()
  drawRef.value()
}

function openSelected(): void {
  if (selNode.value?.relPath) emit('open', selNode.value.relPath)
}

function onNeighborClick(n: LiveNode): void {
  if (n.relPath) emit('open', n.relPath)
  else sel.value = n.id
}

let resizeObserver: ResizeObserver | null = null
let wheelCanvas: HTMLCanvasElement | null = null

function onWheel(e: WheelEvent): void {
  e.preventDefault()
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const sx = e.clientX - rect.left
  const sy = e.clientY - rect.top
  const cam = camRef.value
  const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12
  const nk = Math.min(4, Math.max(0.35, cam.k * factor))
  const wx = (sx - cam.x) / cam.k
  const wy = (sy - cam.y) / cam.k
  camRef.value = { k: nk, x: sx - wx * nk, y: sy - wy * nk }
  syncZoomPct()
  drawRef.value()
}

watch(sel, (id) => {
  if (id) rippleRef.value = { id, t0: performance.now() }
})

watch(
  graph,
  () => {
    rebuildSimulation()
  },
  { immediate: true },
)

watch([layoutReady, filter, query, sel, hoverId, visibleCount, ordered], () => {
  installDraw()
})

watch([hoverId, sel], ([h, s]) => {
  if (pulseRafRef.value) cancelAnimationFrame(pulseRafRef.value)
  pulseRafRef.value = 0
  if (!h && !s) return
  let alive = true
  const loop = (): void => {
    if (!alive) return
    drawRef.value()
    pulseRafRef.value = requestAnimationFrame(loop)
  }
  pulseRafRef.value = requestAnimationFrame(loop)
  return () => {
    alive = false
    cancelAnimationFrame(pulseRafRef.value)
    pulseRafRef.value = 0
  }
})

watch(
  () => [props.focusId, props.focusTitle, layoutReady.value] as const,
  () => {
    if (!props.focusId && !props.focusTitle) return
    let node: LiveNode | undefined
    if (props.focusId) node = liveByIdRef.value.get(props.focusId)
    if (!node && props.focusTitle) {
      const t = props.focusTitle.trim().toLowerCase()
      node = liveNodesRef.value.find((n) => n.label.trim().toLowerCase() === t)
    }
    if (!node) {
      emit('focusConsumed')
      return
    }
    sel.value = node.id
    visibleCount.value = Number.POSITIVE_INFINITY
    playing.value = false

    const applyCam = (): boolean => {
      const { w, h } = sizeRef.value
      if (w < 40 || h < 40) return false
      const live = liveByIdRef.value.get(node!.id) || node!
      const k = Math.max(1.15, Math.min(w / GRAPH_W, h / GRAPH_H) * 1.2)
      camRef.value = {
        k,
        x: w / 2 - live.x * k,
        y: h / 2 - live.y * k,
      }
      drawRef.value()
      return true
    }

    if (applyCam()) {
      syncZoomPct()
      emit('focusConsumed')
      return
    }
    let tries = 0
    const timer = window.setInterval(() => {
      tries += 1
      if (applyCam() || tries > 20) {
        syncZoomPct()
        window.clearInterval(timer)
        emit('focusConsumed')
      }
    }, 50)
    return () => window.clearInterval(timer)
  },
)

watch([playing, visibleCount, () => ordered.value.length, hasDates], () => {
  if (!playing.value) return
  if (visibleCount.value >= ordered.value.length) {
    playing.value = false
    return
  }
  const id = window.setTimeout(() => {
    visibleCount.value = Math.min(
      ordered.value.length,
      (Number.isFinite(visibleCount.value) ? visibleCount.value : 0) + 1,
    )
    reheat(0.25)
  }, hasDates.value ? 55 : 28)
  return () => window.clearTimeout(id)
})

watch([layoutReady, empty], () => {
  if (!layoutReady.value || empty.value || didAutoFitRef.value) return
  didAutoFitRef.value = true
  const t = window.setTimeout(() => fitNodes(), 80)
  return () => window.clearTimeout(t)
})

onMounted(() => {
  installDraw()

  const el = wrapRef.value
  if (el) {
    resizeObserver = new ResizeObserver(() => {
      const r = el.getBoundingClientRect()
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      sizeRef.value = { w: r.width, h: r.height, dpr }
      const c = canvasRef.value
      if (c) {
        c.width = Math.max(1, Math.floor(r.width * dpr))
        c.height = Math.max(1, Math.floor(r.height * dpr))
        c.style.width = r.width + 'px'
        c.style.height = r.height + 'px'
      }
      if (camRef.value.k === 1 && camRef.value.x === 0) resetCam()
      else drawRef.value()
    })
    resizeObserver.observe(el)
    resetCam()
  }

  wheelCanvas = canvasRef.value
  wheelCanvas?.addEventListener('wheel', onWheel, { passive: false })
  window.addEventListener('keydown', onKeyDown)
})

onUnmounted(() => {
  simRef.value?.stop()
  simRef.value = null
  resizeObserver?.disconnect()
  wheelCanvas?.removeEventListener('wheel', onWheel)
  window.removeEventListener('keydown', onKeyDown)
  if (pulseRafRef.value) cancelAnimationFrame(pulseRafRef.value)
})
</script>

<template>
  <section class="bb-view bb-graph-view rkg-graph">
    <header class="bb-view-head">
      <div>
        <h1 class="bb-h1">知识图谱</h1>
        <p class="bb-sub">
          {{
            empty
              ? '还没有资源可展示'
              : `${graph.nodes.length} 个节点 · ${graph.edges.length} 条连接 · 拖拽节点 · 空白平移 · 滚轮缩放 · 双击打开`
          }}
        </p>
      </div>
      <div class="bb-graph-toolbar">
        <label class="bb-graph-search">
          <el-icon :size="14"><Search /></el-icon>
          <input
            v-model="query"
            placeholder="搜索节点…"
            aria-label="搜索图谱节点"
          />
        </label>
        <span class="bb-graph-zoom" title="当前缩放">{{ zoomPct }}%</span>
        <button
          type="button"
          class="bb-btn sm"
          :disabled="empty"
          title="适配全部节点到视野"
          @click="fitNodes()"
        >
          <el-icon :size="13"><FullScreen /></el-icon>
          适配
        </button>
        <button
          type="button"
          class="bb-btn sm"
          title="重置视图并轻微抖动布局"
          @click="
            () => {
              resetCam()
              reheat(0.4)
            }
          "
        >
          <el-icon :size="13"><RefreshRight /></el-icon>
          重置
        </button>
        <button
          type="button"
          class="bb-btn sm primary"
          :disabled="empty"
          :title="playing ? '停止生长并显示全部' : hasDates ? '按创建时间生长' : '依次点亮节点'"
          @click="playGrowth()"
        >
          <el-icon :size="13"><Share /></el-icon>
          {{ playing ? `停止 ${shown}/${ordered.length}` : '生长动画' }}
        </button>
      </div>
    </header>

    <div class="bb-legend" role="group" aria-label="按类型过滤">
      <button
        v-for="f in FILTERS"
        :key="f.key"
        type="button"
        :class="['bb-chip', { 'is-on': filter === f.key }]"
        @click="filter = f.key"
      >
        <span v-if="f.color" class="bb-legend-dot" :style="{ background: f.color }" />
        {{ f.label }}
      </button>
    </div>

    <div ref="wrapRef" class="bb-graph-stage">
      <canvas
        ref="canvasRef"
        class="bb-graph-canvas"
        role="img"
        aria-label="资源知识图谱：课程资源与主题之间的关联网络"
        @pointerdown="onCanvasPointerDown"
        @pointermove="onCanvasPointerMove"
        @pointerup="onCanvasPointerUp"
        @pointerleave="onCanvasPointerLeave"
        @dblclick="onCanvasDoubleClick"
      />
      <div v-if="empty" class="bb-graph-empty">
        <p>还没有资源可展示</p>
        <p class="bb-sub">去资源中心生成讲义、习题等后，这里会形成知识网络</p>
      </div>
      <canvas
        v-if="!empty"
        ref="miniRef"
        class="bb-graph-minimap"
        aria-label="图谱小地图，点击或拖拽可快速定位"
        title="小地图 · 点击定位"
        @pointerdown="onMiniPointerDown"
        @pointermove="onMiniPointerMove"
        @pointerup="onMiniPointerUp"
      />
    </div>

    <div class="bb-graph-detail" aria-live="polite">
      <span class="bb-sub">
        {{
          selNode
            ? `已选：${selNode.label} · ${typeLabel(selNode.type)} · ${selNode.deg} 条连接 · Esc 取消`
            : hoverHint || '拖拽节点 · 空白平移 · 滚轮缩放 · 双击打开'
        }}
      </span>
      <button
        v-if="selNode?.relPath"
        type="button"
        class="bb-btn sm primary"
        @click="openSelected()"
      >
        打开
      </button>
    </div>

    <div v-if="selNode && neighbors.length > 0" class="bb-graph-neighbors">
      <span class="bb-sub">邻居</span>
      <div class="bb-chips">
        <button
          v-for="n in neighbors.slice(0, 16)"
          :key="n.id"
          type="button"
          class="bb-chip"
          :title="typeLabel(n.type)"
          @click="onNeighborClick(n)"
        >
          {{ n.label }}
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.rkg-graph {
  --rkg-font-ui: 'Segoe UI Variable', 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  --bb-accent: #2f5d8c;
  --bb-accent-hover: #264d75;
  --bb-accent-soft: #e8f0f6;
  --bb-bg: #f7f6f3;
  --bb-surface: #fffcf7;
  --bb-surface-2: #f0efea;
  --bb-border: #e4e2db;
  --bb-text: #1c2430;
  --bb-muted: #78716c;
  --bb-radius: 12px;
  --bb-dur-fast: 160ms;
  --bb-dur-normal: 240ms;
  --bb-ease-out: cubic-bezier(0.22, 1, 0.36, 1);
  color: var(--bb-text);
  font-family: var(--rkg-font-ui);
  font-size: 13px;
}

.bb-view {
  max-width: none;
  width: 100%;
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.bb-h1 {
  font-size: 21px;
  font-weight: 500;
  margin: 0;
}

.bb-sub {
  margin: 4px 0 0;
  color: var(--bb-muted);
  font-size: 13px;
}

.bb-view-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.bb-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border: 1px solid var(--bb-border);
  border-radius: 9px;
  background: var(--bb-surface);
  color: var(--bb-text);
  font-size: 13.5px;
  font-family: inherit;
  cursor: pointer;
  transition:
    background var(--bb-dur-fast) var(--bb-ease-out),
    border-color var(--bb-dur-fast) var(--bb-ease-out);
}

.bb-btn:hover:not(:disabled) {
  background: var(--bb-surface-2);
}

.bb-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.bb-btn.primary {
  background: var(--bb-accent);
  border-color: var(--bb-accent);
  color: #fff;
}

.bb-btn.primary:hover:not(:disabled) {
  background: var(--bb-accent-hover);
  border-color: var(--bb-accent-hover);
}

.bb-btn.sm {
  padding: 5px 9px;
  font-size: 12.5px;
  border-radius: 8px;
}

.bb-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 24px;
  padding: 0 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: var(--bb-surface-2);
  color: var(--bb-muted);
  font-size: 12.5px;
  font-family: inherit;
  cursor: pointer;
  transition:
    background var(--bb-dur-fast) var(--bb-ease-out),
    color var(--bb-dur-fast) var(--bb-ease-out);
}

.bb-chip.is-on {
  background: var(--bb-accent-soft);
  color: var(--bb-accent);
}

button.bb-chip:hover {
  color: var(--bb-text);
}

button.bb-chip.is-on:hover {
  color: var(--bb-accent);
}

.bb-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}

.bb-legend {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.bb-legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: none;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.12);
}

.bb-graph-zoom {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  color: var(--bb-muted);
  min-width: 3.2em;
  text-align: center;
}

.bb-graph-view {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}

.bb-graph-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
}

.bb-graph-search {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid var(--bb-border);
  border-radius: 999px;
  background: var(--bb-surface);
  color: var(--bb-muted);
}

.bb-graph-search input {
  border: 0;
  background: transparent;
  outline: none;
  width: 140px;
  color: var(--bb-text);
  font: inherit;
}

.bb-graph-stage {
  --bb-graph-bg: #e8edf2;
  position: relative;
  flex: 1;
  min-height: 420px;
  border-radius: var(--bb-radius);
  overflow: hidden;
  border: 1px solid var(--bb-border);
  background: var(--bb-graph-bg);
  touch-action: none;
}

.bb-graph-canvas {
  display: block;
  width: 100%;
  height: 100%;
  cursor: grab;
}

.bb-graph-canvas:active {
  cursor: grabbing;
}

.bb-graph-minimap {
  position: absolute;
  right: 12px;
  bottom: 12px;
  width: 148px;
  height: 108px;
  border-radius: 10px;
  cursor: crosshair;
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.18);
  z-index: 2;
}

.bb-graph-minimap:active {
  cursor: grabbing;
}

.bb-graph-empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  pointer-events: none;
  color: var(--bb-muted);
  text-align: center;
  padding: 24px;
}

.bb-graph-empty p {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--bb-text);
}

.bb-graph-empty .bb-sub {
  margin-top: 6px;
  color: var(--bb-muted);
  font-weight: 400;
  font-size: 13px;
  max-width: 22em;
}

.bb-graph-detail {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 10px;
  min-height: 32px;
  flex-wrap: wrap;
}

.bb-graph-detail .bb-btn {
  margin-left: auto;
}

.bb-graph-neighbors {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  width: 100%;
  margin-top: 8px;
  align-items: center;
}
</style>
