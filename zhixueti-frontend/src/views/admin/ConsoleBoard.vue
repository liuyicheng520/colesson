<script setup lang="ts">
/**
 * 管理端 · HUD 控制台（全屏可视化）
 *
 * 数据全部来自真实接口：概览、趋势、功能分布、TOP 主题、异常、待审资源、智能体。
 * 无数据时显示「暂无」，绝不填充假数字。
 * 动效仅使用 canvas 重绘与 CSS transform/opacity；prefers-reduced-motion 下静态呈现。
 */
import { computed, onActivated, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { adminOpsApi, type AdminOverviewStats, type AdminTrendStats } from '@/api/adminOps'
import { adminAuditApi, type AuditOverviewStats, type ExceptionTrendItem } from '@/api/adminAudit'
import { adminContentApi } from '@/api/adminContent'
import { agentApi } from '@/api/agent'

const loading = ref(true)
const failed = ref(false)
const overview = ref<AdminOverviewStats | null>(null)
const audit = ref<AuditOverviewStats | null>(null)
const trends = ref<AdminTrendStats | null>(null)
const exceptionTrend = ref<ExceptionTrendItem[]>([])
const pendingResources = ref<number | null>(null)
const agentCount = ref<number | null>(null)
const trendDays = ref<7 | 30>(7)

const streamRef = ref<HTMLElement | null>(null)
const anomalyRef = ref<HTMLElement | null>(null)
const netRef = ref<HTMLCanvasElement | null>(null)
let streamChart: echarts.ECharts | null = null
let anomalyChart: echarts.ECharts | null = null
let rafId = 0
let stopNet: (() => void) | null = null

const reduceMotion =
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

const fmt = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined || Number.isNaN(v) ? '暂无' : Number(v).toFixed(digits)

const leftCards = computed(() => [
  { label: '总用户数', value: fmt(overview.value?.total_users), unit: '', tone: 'magenta' },
  { label: '日活用户', value: fmt(overview.value?.dau_users), unit: '', tone: 'pink' },
  { label: '学习时长', value: fmt(overview.value?.total_study_hours, 2), unit: 'h', tone: 'cyan' },
  { label: '问答总量', value: fmt(overview.value?.qa_total), unit: '', tone: 'amber' },
  { label: '多模态生成', value: fmt(overview.value?.multimodal_total), unit: '', tone: 'cyan' },
  { label: '待审核资源', value: fmt(pendingResources.value), unit: '', tone: 'amber' },
])

const rightCards = computed(() => [
  { label: '异常总数', value: fmt(audit.value?.exception_total), unit: '', tone: 'pink' },
  { label: '未处理异常', value: fmt(audit.value?.exception_unresolved), unit: '', tone: 'amber' },
  { label: '24h 新增异常', value: fmt(audit.value?.exception_24h), unit: '', tone: 'magenta' },
  { label: '在线智能体', value: fmt(agentCount.value), unit: '个', tone: 'cyan' },
  { label: '操作总数', value: fmt(audit.value?.operation_total), unit: '', tone: 'cyan' },
  { label: '操作失败 24h', value: fmt(audit.value?.operation_failed_24h), unit: '', tone: 'amber' },
])

async function loadAll() {
  loading.value = true
  try {
    const [ov, tr, au, ex, pending, agents] = await Promise.allSettled([
      adminOpsApi.overview(),
      adminOpsApi.trends(trendDays.value),
      adminAuditApi.overview(),
      adminAuditApi.exceptionTrends(trendDays.value),
      adminContentApi.listResources({ status: 1, page: 1, page_size: 1 }),
      agentApi.listDefinitions(),
    ])
    overview.value = ov.status === 'fulfilled' ? ov.value : null
    trends.value = tr.status === 'fulfilled' ? tr.value : null
    audit.value = au.status === 'fulfilled' ? au.value : null
    exceptionTrend.value = ex.status === 'fulfilled' ? ex.value : []
    pendingResources.value =
      pending.status === 'fulfilled' ? (pending.value?.total ?? 0) : null
    agentCount.value = agents.status === 'fulfilled' ? (agents.value?.length ?? 0) : null
    failed.value = ov.status !== 'fulfilled' || tr.status !== 'fulfilled'
  } finally {
    loading.value = false
  }
}

const axisTheme = {
  axisLine: { lineStyle: { color: 'rgba(120, 200, 255, 0.35)' } },
  axisLabel: { color: '#8fb6d9', fontSize: 10 },
  splitLine: { lineStyle: { color: 'rgba(120, 200, 255, 0.08)' } },
}

function renderStream() {
  const el = streamRef.value
  if (!el) return
  if (!streamChart) streamChart = echarts.init(el)
  const t = trends.value
  const dates = (t?.dates || []).map((d) => d.slice(5))
  streamChart.setOption(
    {
      animation: !reduceMotion,
      animationDuration: 600,
      grid: { left: 42, right: 12, top: 28, bottom: 26 },
      tooltip: { trigger: 'axis', backgroundColor: 'rgba(10,12,32,0.92)', borderColor: '#7c3aed', textStyle: { color: '#dbeafe', fontSize: 11 } },
      legend: {
        top: 4, right: 8, itemWidth: 8, itemHeight: 8,
        textStyle: { color: '#93c5fd', fontSize: 10 },
      },
      xAxis: { type: 'category', data: dates, ...axisTheme },
      yAxis: { type: 'value', ...axisTheme },
      series: [
        { name: '用户注册', type: 'bar', data: t?.registrations || [], barMaxWidth: 10,
          itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#22d3ee' }, { offset: 1, color: 'rgba(34,211,238,0.15)' }]), borderRadius: [2, 2, 0, 0] } },
        { name: '问答量', type: 'bar', data: t?.qa_counts || [], barMaxWidth: 10,
          itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#a855f7' }, { offset: 1, color: 'rgba(168,85,247,0.15)' }]), borderRadius: [2, 2, 0, 0] } },
        { name: '视频讲解', type: 'bar', data: t?.lecture_counts || [], barMaxWidth: 10,
          itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#f472b6' }, { offset: 1, color: 'rgba(244,114,182,0.15)' }]), borderRadius: [2, 2, 0, 0] } },
      ],
    },
    true,
  )
}

function renderAnomaly() {
  const el = anomalyRef.value
  if (!el) return
  if (!anomalyChart) anomalyChart = echarts.init(el)
  const rows = exceptionTrend.value
  anomalyChart.setOption(
    {
      animation: !reduceMotion,
      animationDuration: 600,
      grid: { left: 42, right: 14, top: 28, bottom: 26 },
      tooltip: { trigger: 'axis', backgroundColor: 'rgba(10,12,32,0.92)', borderColor: '#7c3aed', textStyle: { color: '#dbeafe', fontSize: 11 } },
      legend: { top: 4, right: 8, itemWidth: 8, itemHeight: 8, textStyle: { color: '#93c5fd', fontSize: 10 } },
      xAxis: { type: 'category', data: rows.map((r) => String(r.date).slice(5)), ...axisTheme },
      yAxis: { type: 'value', ...axisTheme },
      series: [
        {
          name: '异常数', type: 'line', smooth: true, data: rows.map((r) => r.count),
          symbolSize: 5, lineStyle: { width: 2, color: '#f472b6', shadowColor: 'rgba(244,114,182,0.8)', shadowBlur: 12 },
          itemStyle: { color: '#fbcfe8' },
          areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(244,114,182,0.35)' }, { offset: 1, color: 'rgba(244,114,182,0.02)' }]) },
        },
      ],
    },
    true,
  )
}

/** 中心粒子网络：节点数取自真实智能体数量，连线为纯视觉编排 */
function startNetwork() {
  const canvas = netRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  let w = 0
  let h = 0
  const nodes: { x: number; y: number; vx: number; vy: number; r: number; hue: number }[] = []

  const resize = () => {
    const rect = canvas.getBoundingClientRect()
    w = Math.max(1, rect.width)
    h = Math.max(1, rect.height)
    canvas.width = Math.floor(w * dpr)
    canvas.height = Math.floor(h * dpr)
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  }

  const seed = () => {
    const count = Math.max(10, Math.min(26, agentCount.value || 14))
    nodes.length = 0
    for (let i = 0; i < count; i++) {
      nodes.push({
        x: w / 2 + (Math.random() - 0.5) * w * 0.52,
        y: h / 2 + (Math.random() - 0.5) * h * 0.52,
        vx: (Math.random() - 0.5) * 0.28,
        vy: (Math.random() - 0.5) * 0.28,
        r: 2.2 + Math.random() * 3.4,
        hue: Math.random() > 0.5 ? 300 : 190,
      })
    }
  }

  const draw = (t: number) => {
    ctx.clearRect(0, 0, w, h)
    // 连线
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x
        const dy = nodes[i].y - nodes[j].y
        const d = Math.hypot(dx, dy)
        if (d > Math.min(w, h) * 0.46) continue
        const a = (1 - d / (Math.min(w, h) * 0.46)) * 0.55
        ctx.strokeStyle = `hsla(${(nodes[i].hue + nodes[j].hue) / 2}, 90%, 68%, ${a})`
        ctx.lineWidth = 0.7
        ctx.beginPath()
        ctx.moveTo(nodes[i].x, nodes[i].y)
        ctx.lineTo(nodes[j].x, nodes[j].y)
        ctx.stroke()
      }
    }
    // 节点
    for (const n of nodes) {
      const pulse = reduceMotion ? 1 : 0.88 + 0.12 * Math.sin(t / 520 + n.x * 0.02)
      const grd = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, n.r * 5)
      grd.addColorStop(0, `hsla(${n.hue}, 100%, 78%, ${0.95 * pulse})`)
      grd.addColorStop(0.35, `hsla(${n.hue}, 100%, 62%, ${0.5 * pulse})`)
      grd.addColorStop(1, `hsla(${n.hue}, 100%, 50%, 0)`)
      ctx.fillStyle = grd
      ctx.beginPath()
      ctx.arc(n.x, n.y, n.r * 5, 0, Math.PI * 2)
      ctx.fill()
      ctx.fillStyle = `hsla(${n.hue}, 100%, 92%, 1)`
      ctx.beginPath()
      ctx.arc(n.x, n.y, n.r * 0.62, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  const tick = (t: number) => {
    for (const n of nodes) {
      n.x += n.vx
      n.y += n.vy
      if (n.x < w * 0.12 || n.x > w * 0.88) n.vx *= -1
      if (n.y < h * 0.12 || n.y > h * 0.88) n.vy *= -1
    }
    draw(t)
    rafId = requestAnimationFrame(tick)
  }

  resize()
  seed()
  if (reduceMotion) {
    draw(0)
  } else {
    rafId = requestAnimationFrame(tick)
  }

  const onResize = () => {
    resize()
    seed()
    if (reduceMotion) draw(0)
  }
  window.addEventListener('resize', onResize)
  stopNet = () => {
    cancelAnimationFrame(rafId)
    window.removeEventListener('resize', onResize)
  }
}

function fitCharts() {
  streamChart?.resize()
  anomalyChart?.resize()
}

async function reload() {
  await loadAll()
  renderStream()
  renderAnomaly()
  if (netRef.value) {
    stopNet?.()
    startNetwork()
  }
}

onMounted(async () => {
  await loadAll()
  renderStream()
  renderAnomaly()
  startNetwork()
  window.addEventListener('resize', fitCharts)
})

onActivated(() => {
  void reload()
})

onBeforeUnmount(() => {
  stopNet?.()
  cancelAnimationFrame(rafId)
  streamChart?.dispose()
  anomalyChart?.dispose()
  streamChart = null
  anomalyChart = null
  window.removeEventListener('resize', fitCharts)
})
</script>

<template>
  <div class="hud">
    <div class="hud-grid" aria-hidden="true" />
    <header class="hud-head">
      <div class="hud-head-line left" aria-hidden="true" />
      <h1 class="hud-title">
        <span class="cn">智课共生</span>
        <span class="en">CONSOLE</span>
      </h1>
      <div class="hud-head-line right" aria-hidden="true" />
    </header>

    <section class="hud-body">
      <div class="metric-col">
        <div v-for="c in leftCards" :key="c.label" class="metric" :class="c.tone">
          <span class="metric-label">{{ c.label }}</span>
          <strong class="metric-value">{{ c.value }}<i v-if="c.unit">{{ c.unit }}</i></strong>
        </div>
      </div>

      <div class="hud-core">
        <canvas ref="netRef" class="hud-net" aria-hidden="true" />
        <div class="core-caption">
          <span>智能体协作网络</span>
          <em>{{ agentCount ?? '—' }} 个节点 · 实时编排</em>
        </div>
      </div>

      <div class="metric-col">
        <div v-for="c in rightCards" :key="c.label" class="metric" :class="c.tone">
          <span class="metric-label">{{ c.label }}</span>
          <strong class="metric-value">{{ c.value }}<i v-if="c.unit">{{ c.unit }}</i></strong>
        </div>
      </div>
    </section>

    <section class="hud-bottom">
      <div class="panel">
        <div class="panel-head">
          <span class="dot" />实时事件流
          <div class="seg">
            <button type="button" :class="{ on: trendDays === 7 }" @click="trendDays = 7; reload()">7天</button>
            <button type="button" :class="{ on: trendDays === 30 }" @click="trendDays = 30; reload()">30天</button>
          </div>
        </div>
        <div ref="streamRef" class="panel-chart" />
      </div>
      <div class="panel">
        <div class="panel-head"><span class="dot warn" />异常监控</div>
        <div ref="anomalyRef" class="panel-chart" />
      </div>
    </section>

    <div v-if="loading" class="hud-mask">数据加载中…</div>
    <div v-else-if="failed" class="hud-mask">数据加载失败，请确认已登录管理端</div>
  </div>
</template>

<style scoped lang="scss">
$bg0: #060a1c;
$bg1: #0a0f2b;
$cyan: #22d3ee;
$magenta: #e879f9;
$pink: #f472b6;
$amber: #fbbf24;

.hud {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  /* 布局内展示：精确占满内容区剩余高度（顶栏 60 + 内容区上下 padding 40），
     超出部分内部滚动，保证底部两张图表始终可见 */
  height: calc(100vh - var(--admin-header-h, 108px) - 46px);
  box-sizing: border-box;
  overflow: hidden;
  padding: 10px 12px 12px;
  border-radius: 12px;
  color: #dbeafe;
  background:
    radial-gradient(ellipse 60% 50% at 50% 0%, rgba(88, 28, 135, 0.55), transparent 70%),
    radial-gradient(ellipse 50% 40% at 10% 100%, rgba(14, 116, 144, 0.35), transparent 70%),
    linear-gradient(160deg, $bg0, $bg1 55%, #090c22);
  overflow: hidden;
}

.hud-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(56, 189, 248, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(56, 189, 248, 0.06) 1px, transparent 1px);
  background-size: 42px 42px;
  mask-image: radial-gradient(ellipse 70% 60% at 50% 45%, #000 40%, transparent 100%);
  pointer-events: none;
}

.hud-head {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 58px;
  flex: 0 0 auto;
}

.hud-title {
  display: flex;
  align-items: baseline;
  gap: 14px;
  margin: 0;
  padding: 0 34px;
  letter-spacing: 0.22em;

  .cn {
    font-size: 30px;
    font-weight: 800;
    color: #67e8f9;
    text-shadow: 0 0 12px rgba(34, 211, 238, 0.85), 0 0 34px rgba(34, 211, 238, 0.45);
  }

  .en {
    font-size: 30px;
    font-weight: 800;
    color: $magenta;
    text-shadow: 0 0 12px rgba(232, 121, 249, 0.85), 0 0 34px rgba(232, 121, 249, 0.4);
  }
}

.hud-head-line {
  flex: 1;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(34, 211, 238, 0.75), rgba(232, 121, 249, 0.75), transparent);
  box-shadow: 0 0 12px rgba(34, 211, 238, 0.6);

  &.left { margin-right: 20px; }
  &.right { margin-left: 20px; }
}


.hud-body {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  grid-template-columns: 250px 1fr 250px;
  gap: 16px;
}

.metric-col {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 8px;
  min-height: 0;
  overflow: hidden;
}

.metric {
  position: relative;
  flex: 1 1 0;
  min-height: 0;
  max-height: 88px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  padding: 8px 14px;
  border-radius: 6px;
  background: linear-gradient(145deg, rgba(12, 18, 46, 0.9), rgba(8, 12, 32, 0.75));
  border: 1px solid rgba(56, 189, 248, 0.28);
  box-shadow: inset 0 0 22px rgba(56, 189, 248, 0.08), 0 0 18px rgba(0, 0, 0, 0.4);
  overflow: hidden;

  &::after {
    content: '';
    position: absolute;
    inset: 0 auto auto 0;
    width: 40%;
    height: 1px;
    background: linear-gradient(90deg, rgba(255, 255, 255, 0.75), transparent);
    opacity: 0.5;
  }

  .metric-label {
    font-size: 12px;
    letter-spacing: 0.12em;
    color: #93c5fd;
  }

  .metric-value {
    font-family: 'DS-Digital', 'Segoe UI', ui-monospace, monospace;
    font-size: clamp(26px, 2.4vw, 38px);
    line-height: 1.05;
    letter-spacing: 0.06em;
    font-variant-numeric: tabular-nums;

    i { font-size: 13px; margin-left: 4px; font-style: normal; opacity: 0.75; }
  }

  &.cyan    { border-color: rgba(34, 211, 238, 0.45); box-shadow: inset 0 0 22px rgba(34, 211, 238, 0.12), 0 0 18px rgba(0, 0, 0, 0.4);
              .metric-value { color: #67e8f9; text-shadow: 0 0 14px rgba(34, 211, 238, 0.85); } }
  &.magenta { border-color: rgba(232, 121, 249, 0.45); box-shadow: inset 0 0 22px rgba(232, 121, 249, 0.12), 0 0 18px rgba(0, 0, 0, 0.4);
              .metric-value { color: #f0abfc; text-shadow: 0 0 14px rgba(232, 121, 249, 0.85); } }
  &.pink    { border-color: rgba(244, 114, 182, 0.45); box-shadow: inset 0 0 22px rgba(244, 114, 182, 0.12), 0 0 18px rgba(0, 0, 0, 0.4);
              .metric-value { color: #f9a8d4; text-shadow: 0 0 14px rgba(244, 114, 182, 0.8); } }
  &.amber   { border-color: rgba(251, 191, 36, 0.45); box-shadow: inset 0 0 22px rgba(251, 191, 36, 0.12), 0 0 18px rgba(0, 0, 0, 0.4);
              .metric-value { color: #fcd34d; text-shadow: 0 0 14px rgba(251, 191, 36, 0.8); } }
}

.hud-core {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  border-radius: 10px;
  background: radial-gradient(ellipse 60% 60% at 50% 50%, rgba(76, 29, 149, 0.35), transparent 72%);
}

.hud-net {
  width: 100%;
  height: 100%;
  display: block;
}

.core-caption {
  position: absolute;
  top: 6px;
  right: 14px;
  align-items: flex-end;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  letter-spacing: 0.16em;
  color: #a5b4fc;
  text-shadow: 0 0 10px rgba(129, 140, 248, 0.7);

  em { font-style: normal; font-size: 11px; color: #67e8f9; opacity: 0.85; }
}

.hud-bottom {
  flex: 0 0 26%;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  min-height: 0;
}

.panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 8px 10px 6px;
  border-radius: 8px;
  background: linear-gradient(160deg, rgba(11, 16, 40, 0.92), rgba(7, 10, 26, 0.85));
  border: 1px solid rgba(56, 189, 248, 0.26);
  box-shadow: inset 0 0 30px rgba(56, 189, 248, 0.06), 0 0 22px rgba(0, 0, 0, 0.45);
}

.panel-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  letter-spacing: 0.14em;
  color: #93c5fd;

  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: $cyan;
    box-shadow: 0 0 10px rgba(34, 211, 238, 0.9);

    &.warn { background: $pink; box-shadow: 0 0 10px rgba(244, 114, 182, 0.9); }
  }

  .seg {
    margin-left: auto;
    display: flex;
    gap: 4px;

    button {
      padding: 2px 9px;
      font-size: 11px;
      color: #93c5fd;
      background: transparent;
      border: 1px solid rgba(56, 189, 248, 0.35);
      border-radius: 3px;
      cursor: pointer;
      transition: all 160ms cubic-bezier(0.4, 0, 0.2, 1);

      &.on, &:hover { color: #ecfeff; border-color: $cyan; box-shadow: 0 0 10px rgba(34, 211, 238, 0.5); }
    }
  }
}

.panel-chart {
  flex: 1 1 auto;
  min-height: 0;
}

.hud-mask {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-size: 13px;
  letter-spacing: 0.1em;
  color: #a5f3fc;
  background: rgba(4, 7, 20, 0.72);
  backdrop-filter: blur(2px);
}

@media (max-width: 1100px) {
  .hud-body { grid-template-columns: 190px 1fr 190px; }
  .metric .metric-value { font-size: 24px; }
}

@media (max-width: 860px) {
  .hud { padding: 10px 10px 12px; }
  .hud-body { grid-template-columns: 1fr 1fr; grid-template-rows: auto 1fr; }
  .hud-core { grid-column: 1 / -1; order: -1; min-height: 180px; }
  .metric-col { display: grid; grid-template-columns: 1fr 1fr; grid-auto-rows: 68px; align-content: start; overflow: visible; }
  .hud-bottom { grid-template-columns: 1fr; flex-basis: 40%; }
  .hud-title .cn, .hud-title .en { font-size: 20px; }
}

@media (prefers-reduced-motion: reduce) {
  .hud-exit, .panel-head .seg button { transition: none; }
}
</style>
