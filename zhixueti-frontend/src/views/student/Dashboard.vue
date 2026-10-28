<script setup lang="ts">
defineOptions({ name: 'StudentDashboard' })

import { onMounted, onActivated, onDeactivated, ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import {
  Clock, Collection, Trophy, DataLine, TrendCharts, Guide,
} from '@element-plus/icons-vue'
import { behaviorApi } from '@/api/behavior'
import type { LearningStats } from '@/types'
import { formatPathUserText } from '@/utils/profileDisplay'
import {
  loadGongshengOverview,
  openGongshengWorkbench,
  type GongshengOverview,
} from '@/utils/gongshengProgress'

const router = useRouter()
const loading = ref(true)
const stats = ref<LearningStats | null>(null)
const gongsheng = ref<GongshengOverview | null>(null)
const trendRange = ref<'7d' | '30d'>('7d')
const trendChartRef = ref<HTMLElement>()
const masteryChartRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null
let masteryChart: echarts.ECharts | null = null

const overviewCards = computed(() => {
  const s = stats.value
  if (!s) return []
  return [
    {
      key: 'hours',
      label: '累计学习时长',
      value: `${s.total_study_hours}h`,
      icon: Clock,
      color: '#2563eb',
      bg: '#eff6ff',
      change: s.study_hours_change_pct,
    },
    {
      key: 'resources',
      label: '已学习资源数',
      value: String(s.resources_learned),
      icon: Collection,
      color: '#10b981',
      bg: '#ecfdf5',
      change: s.resources_change_pct,
    },
    {
      key: 'knowledge',
      label: '已完成知识点',
      value: String(s.knowledge_points_completed),
      icon: Trophy,
      color: '#f59e0b',
      bg: '#fffbeb',
      change: s.knowledge_change_pct,
    },
    {
      key: 'accuracy',
      label: '平均正确率',
      value: s.avg_accuracy === null || s.avg_accuracy === undefined ? '暂无' : `${s.avg_accuracy}%`,
      icon: DataLine,
      color: '#8b5cf6',
      bg: '#f5f3ff',
      change: s.accuracy_change_pct,
    },
  ]
})

const trendData = computed(() => {
  if (!stats.value) return []
  return trendRange.value === '7d' ? stats.value.trend_7d : stats.value.trend_30d
})

const pathProgressPercent = computed(() =>
  Math.round((stats.value?.path_progress_rate ?? 0) * 100),
)

const pathRemainingNodes = computed(() => {
  const s = stats.value
  if (!s) return 0
  return Math.max(0, (s.path_total_nodes || 0) - (s.path_completed_nodes || 0))
})

/** 路径节点速览（与掌握度同源节点数据） */
const pathNodePreview = computed(() => {
  const items = stats.value?.mastery_items || []
  return items.slice(0, 6).map((item, idx) => {
    const done = item.value >= 80
    const doing = !done && item.value > 0
    return {
      name: item.name,
      value: item.value,
      status: done ? 'done' : doing ? 'doing' : 'todo',
      label: done ? '已完成' : doing ? '进行中' : idx === 0 && pathProgressPercent.value === 0 ? '待开始' : '未开始',
    }
  })
})

const pathHint = computed(() => {
  const pct = pathProgressPercent.value
  if (!stats.value?.path_total_nodes) return '暂无学习路径，去规划一条专属路径吧'
  if (pct >= 100) return '本路径节点已全部完成，可以生成下一段进阶路径'
  if (pct >= 60) return '进度过半，继续巩固剩余节点即可收官'
  if (pct > 0) return '已进入学习节奏，建议按节点顺序推进'
  return '路径已就绪，从第一个节点开始即可'
})

const displayPathTitle = computed(() =>
  formatPathUserText(stats.value?.path_title, '当前学习路径'),
)

function formatChange(val: number) {
  if (val > 0) return `+${val}%`
  if (val < 0) return `${val}%`
  return '—'
}

function changeType(val: number): 'success' | 'danger' | 'info' {
  if (val > 0) return 'success'
  if (val < 0) return 'danger'
  return 'info'
}

async function loadStats() {
  loading.value = true
  try {
    const [s, gs] = await Promise.all([
      behaviorApi.getStats(),
      loadGongshengOverview().catch(() => null),
    ])
    stats.value = s
    gongsheng.value = gs
    await nextTick()
    refreshCharts()
  } catch {
    ElMessage.error('学习数据加载失败')
  } finally {
    loading.value = false
  }
}

function disposeCharts() {
  trendChart?.dispose()
  masteryChart?.dispose()
  trendChart = null
  masteryChart = null
}

function renderTrendChart() {
  if (!trendChartRef.value) return
  if (!trendChart) trendChart = echarts.init(trendChartRef.value)
  const data = trendData.value
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 24, top: 32, bottom: 32 },
    xAxis: {
      type: 'category',
      data: data.map((d) => d.date.slice(5)),
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisLabel: { color: '#64748b' },
    },
    yAxis: {
      type: 'value',
      name: '分钟',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
      axisLabel: { color: '#64748b' },
    },
    series: [{
      name: '学习时长',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      data: data.map((d) => d.minutes),
      lineStyle: { width: 3, color: '#2563eb' },
      itemStyle: { color: '#2563eb' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(37, 99, 235, 0.25)' },
          { offset: 1, color: 'rgba(37, 99, 235, 0.02)' },
        ]),
      },
    }],
  }, true)
}

const masterySummary = computed(() => {
  const items = stats.value?.mastery_items || []
  if (!items.length) return null
  const vals = items.map((i) => Number(i.value) || 0)
  const avg = Math.round(vals.reduce((a, b) => a + b, 0) / vals.length)
  const sorted = [...items].sort((a, b) => b.value - a.value)
  return {
    avg,
    strongest: sorted[0],
    weakest: sorted[sorted.length - 1],
    covered: vals.filter((v) => v > 0).length,
    total: items.length,
  }
})

function wrapRadarLabel(name: string, maxPerLine = 5) {
  if (name.length <= maxPerLine) return name
  const parts: string[] = []
  for (let i = 0; i < name.length; i += maxPerLine) {
    parts.push(name.slice(i, i + maxPerLine))
  }
  return parts.join('\n')
}

function renderMasteryChart() {
  if (!masteryChartRef.value || !stats.value?.mastery_items.length) return
  if (!masteryChart) masteryChart = echarts.init(masteryChartRef.value)
  const items = stats.value.mastery_items
  const values = items.map((i) => Number(i.value) || 0)
  const avg = Math.round(values.reduce((a, b) => a + b, 0) / values.length)
  const allZero = values.every((v) => v === 0)
  const chartW = masteryChartRef.value.clientWidth || 480
  // 半宽卡片基本都偏窄，统一上下布局，避免雷达标签与条形互相遮挡
  const stacked = chartW < 720
  const barColor = (v: number) =>
    new echarts.graphic.LinearGradient(0, 0, 1, 0, [
      { offset: 0, color: v >= 80 ? '#34d399' : v > 0 ? '#60a5fa' : '#e2e8f0' },
      { offset: 1, color: v >= 80 ? '#059669' : v > 0 ? '#2563eb' : '#f1f5f9' },
    ])

  masteryChart.setOption({
    animation: true,
    animationDuration: 1200,
    animationDurationUpdate: 800,
    animationEasing: 'cubicOut',
    animationDelay: (idx: number) => idx * 70,
    tooltip: {
      trigger: 'item',
      confine: true,
      formatter: (params: any) => {
        if (params.seriesType === 'bar') {
          return `${params.name || params.data?.name || ''}：${params.value}%`
        }
        if (params.seriesName === '目标参考') return '目标参考线：各维度 70%'
        if (Array.isArray(params.value)) {
          const lines = items.map((it, i) => `${it.name}：${values[i]}%`)
          return [`<b>当前掌握</b> · 综合 ${avg}%`, ...lines].join('<br/>')
        }
        return `${params.name}：${params.value}%`
      },
    },
    legend: {
      show: true,
      top: 0,
      left: 'center',
      itemWidth: 10,
      itemHeight: 10,
      itemGap: 14,
      textStyle: { color: '#64748b', fontSize: 11 },
      data: ['当前掌握', '目标参考', '分项掌握'],
    },
    grid: stacked
      ? { left: 12, right: 40, top: '56%', bottom: 8, containLabel: true }
      : { left: '54%', right: 36, top: 40, bottom: 20, containLabel: true },
    xAxis: {
      type: 'value',
      max: 100,
      show: false,
    },
    yAxis: {
      type: 'category',
      data: items.map((i) => i.name),
      inverse: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: '#475569',
        fontSize: 11,
        interval: 0,
        // 不截断；containLabel 会自动为完整名称留宽
        hideOverlap: false,
      },
    },
    radar: {
      center: stacked ? ['50%', '30%'] : ['26%', '52%'],
      // 缩小半径，给四周标签留白，避免裁切/重叠
      radius: stacked ? '34%' : '48%',
      indicator: items.map((i) => ({ name: i.name, max: 100 })),
      splitNumber: 4,
      axisNameGap: 10,
      axisName: {
        color: '#475569',
        fontSize: 11,
        fontWeight: 500,
        lineHeight: 14,
        formatter: (name: string) => wrapRadarLabel(name, stacked ? 4 : 5),
      },
      axisLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.4)' } },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.32)' } },
      splitArea: {
        areaStyle: {
          color: ['rgba(239, 246, 255, 0.75)', 'rgba(255, 255, 255, 0.98)'],
        },
      },
    },
    graphic: [
      {
        type: 'group',
        left: stacked ? 'center' : '26%',
        top: stacked ? '24%' : '52%',
        bounding: 'raw',
        z: 100,
        silent: true,
        children: [
          {
            type: 'circle',
            shape: { cx: 0, cy: 0, r: stacked ? 26 : 30 },
            style: {
              fill: 'rgba(255,255,255,0.98)',
              shadowBlur: 12,
              shadowColor: 'rgba(37, 99, 235, 0.18)',
            },
          },
          {
            type: 'text',
            style: {
              text: `${avg}`,
              x: 0,
              y: -7,
              fill: '#2563eb',
              fontSize: stacked ? 18 : 22,
              fontWeight: 700,
              align: 'center',
              verticalAlign: 'middle',
            },
          },
          {
            type: 'text',
            style: {
              text: '综合分',
              x: 0,
              y: 12,
              fill: '#94a3b8',
              fontSize: 10,
              align: 'center',
              verticalAlign: 'middle',
            },
          },
        ],
      },
    ],
    series: [
      {
        name: '目标参考',
        type: 'radar',
        silent: true,
        symbol: 'none',
        lineStyle: {
          type: 'dashed',
          width: 1.5,
          color: 'rgba(148, 163, 184, 0.8)',
        },
        areaStyle: { color: 'rgba(148, 163, 184, 0.06)' },
        data: [{ value: items.map(() => 70), name: '目标参考' }],
        z: 1,
      },
      {
        name: '当前掌握',
        type: 'radar',
        // 全 0 时顶点会叠在中心，挡住综合分
        symbol: allZero ? 'none' : 'circle',
        symbolSize: 7,
        lineStyle: {
          width: 2.5,
          color: '#2563eb',
          shadowBlur: allZero ? 0 : 12,
          shadowColor: 'rgba(37, 99, 235, 0.45)',
        },
        itemStyle: {
          color: '#fff',
          borderColor: '#2563eb',
          borderWidth: 2,
        },
        areaStyle: {
          color: allZero
            ? 'rgba(37, 99, 235, 0.04)'
            : new echarts.graphic.RadialGradient(0.5, 0.5, 1, [
                { offset: 0, color: 'rgba(96, 165, 250, 0.5)' },
                { offset: 0.7, color: 'rgba(37, 99, 235, 0.16)' },
                { offset: 1, color: 'rgba(37, 99, 235, 0.04)' },
              ]),
        },
        emphasis: {
          lineStyle: { width: 3.2 },
          areaStyle: { color: 'rgba(37, 99, 235, 0.32)' },
          itemStyle: { borderWidth: 3 },
        },
        data: [{ value: values, name: '当前掌握' }],
        z: 2,
      },
      {
        name: '分项掌握',
        type: 'bar',
        showBackground: true,
        backgroundStyle: {
          color: 'rgba(241, 245, 249, 0.95)',
          borderRadius: [0, 6, 6, 0],
        },
        barWidth: stacked ? 10 : 11,
        label: {
          show: true,
          position: 'right',
          formatter: '{c}%',
          color: '#64748b',
          fontSize: 10,
        },
        data: values.map((v, i) => ({
          value: v,
          name: items[i].name,
          itemStyle: {
            borderRadius: [0, 6, 6, 0],
            color: barColor(v),
          },
        })),
        z: 3,
      },
    ],
  }, true)
}

function refreshCharts() {
  renderTrendChart()
  renderMasteryChart()
  trendChart?.resize()
  masteryChart?.resize()
}

function onResize() {
  trendChart?.resize()
  // 宽度变化时重算雷达/条形并排布局
  if (masteryChartRef.value && stats.value?.mastery_items.length) {
    renderMasteryChart()
    masteryChart?.resize()
  } else {
    masteryChart?.resize()
  }
}

watch(trendRange, () => {
  nextTick(renderTrendChart)
})

onMounted(() => {
  loadStats()
  window.addEventListener('resize', onResize)
})

/** keep-alive 切回时容器从隐藏恢复，需重建/resize 图表，否则白屏 */
onActivated(() => {
  if (!stats.value) {
    loadStats()
    return
  }
  // 返回页面时同时拉取最新统计，图表就绪后重绘
  void loadStats()
  nextTick(() => {
    requestAnimationFrame(() => {
      disposeCharts()
      refreshCharts()
    })
  })
})

onDeactivated(() => {
  disposeCharts()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  disposeCharts()
})
</script>

<template>
  <div v-loading="loading" class="page-container dashboard-page">
    <!-- 智课学习概览（学习数据页主指标，勿复用「课程中心」标题） -->
    <div class="card section-card gongsheng-section">
      <div class="section-header">
        <div class="section-title">
          <el-icon><Collection /></el-icon>
          <h3>智课学习概览</h3>
        </div>
        <el-button type="primary" link @click="router.push('/student/course-center')">前往课程中心</el-button>
      </div>
      <el-row :gutter="16" class="gs-metrics">
        <el-col :xs="12" :sm="6">
          <div class="gs-metric">
            <div class="gs-value">{{ gongsheng?.lessonCount ?? 0 }}</div>
            <div class="gs-label">已发布智课</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="gs-metric">
            <div class="gs-value">{{ gongsheng?.startedCount ?? 0 }}</div>
            <div class="gs-label">已开始学习</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="gs-metric">
            <div class="gs-value">{{ gongsheng?.completedCount ?? 0 }}</div>
            <div class="gs-label">已完成课程</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="gs-metric">
            <div class="gs-value">{{ gongsheng?.avgPercent ?? 0 }}%</div>
            <div class="gs-label">平均进度</div>
          </div>
        </el-col>
      </el-row>
      <el-table v-if="gongsheng?.recent?.length" :data="gongsheng.recent" stripe size="small" style="width: 100%; margin-top: 12px">
        <el-table-column prop="title" label="最近学习" min-width="180" />
        <el-table-column prop="percent" label="进度" width="100">
          <template #default="{ row }">{{ row.percent }}%</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="primary" @click="openGongshengWorkbench(row.id)">继续</el-button>
          </template>
        </el-table-column>
      </el-table>
      <p v-else class="gs-empty">{{ gongsheng?.error || '暂无智课学习记录。可前往课程中心加入班级或继续学习。' }}</p>
    </div>

    <template v-if="stats?.has_data">
      <!-- 核心数据概览 -->
      <el-row :gutter="20" class="overview-row">
        <el-col v-for="card in overviewCards" :key="card.key" :xs="12" :sm="6">
          <div class="overview-card card">
            <div class="card-icon" :style="{ background: card.bg, color: card.color }">
              <el-icon :size="22"><component :is="card.icon" /></el-icon>
            </div>
            <div class="card-body">
              <div class="card-value">{{ card.value }}</div>
              <div class="card-label">{{ card.label }}</div>
              <el-tag :type="changeType(card.change)" size="small" effect="plain" class="change-tag">
                环比 {{ formatChange(card.change) }}
              </el-tag>
            </div>
          </div>
        </el-col>
      </el-row>

      <!-- 学习趋势 -->
      <div class="card section-card">
        <div class="section-header">
          <div class="section-title">
            <el-icon><TrendCharts /></el-icon>
            <h3>学习时长趋势</h3>
          </div>
          <el-radio-group v-model="trendRange" size="small">
            <el-radio-button value="7d">近7天</el-radio-button>
            <el-radio-button value="30d">近30天</el-radio-button>
          </el-radio-group>
        </div>
        <div ref="trendChartRef" class="chart trend-chart" />
      </div>

      <el-row :gutter="20" class="mastery-path-row">
        <!-- 知识掌握度 -->
        <el-col :xs="24" :lg="12">
          <div class="card section-card equal-card mastery-section">
            <div class="section-header">
              <div class="section-title">
                <el-icon><DataLine /></el-icon>
                <h3>知识掌握度</h3>
              </div>
            </div>
            <div v-if="masterySummary" class="mastery-summary">
              <div class="ms-item">
                <span class="ms-label">综合掌握</span>
                <strong>{{ masterySummary.avg }}%</strong>
              </div>
              <div class="ms-item">
                <span class="ms-label">已覆盖</span>
                <strong>{{ masterySummary.covered }}/{{ masterySummary.total }}</strong>
              </div>
              <div class="ms-item good" :title="masterySummary.strongest.name">
                <span class="ms-label">最强</span>
                <strong>{{ masterySummary.strongest.name }}</strong>
              </div>
              <div class="ms-item warn" :title="masterySummary.weakest.name">
                <span class="ms-label">待加强</span>
                <strong>{{ masterySummary.weakest.name }}</strong>
              </div>
            </div>
            <div v-if="stats.mastery_items.length" ref="masteryChartRef" class="chart mastery-chart" />
            <el-empty v-else description="暂无掌握度数据" :image-size="80" />
          </div>
        </el-col>

        <!-- 学习路径进度 -->
        <el-col :xs="24" :lg="12">
          <div class="card section-card equal-card path-section">
            <div class="section-header">
              <div class="section-title">
                <el-icon><Guide /></el-icon>
                <h3>学习路径进度</h3>
              </div>
              <el-button type="primary" link @click="router.push('/student/path')">查看路径</el-button>
            </div>

            <p class="path-name">{{ displayPathTitle }}</p>

            <div class="path-progress-block">
              <el-progress
                type="dashboard"
                :percentage="pathProgressPercent"
                :width="120"
                :stroke-width="10"
                :color="pathProgressPercent >= 100 ? '#67C23A' : '#409EFF'"
              />
              <div class="path-progress-side">
                <el-progress
                  :percentage="pathProgressPercent"
                  :stroke-width="12"
                  striped
                  :striped-flow="pathProgressPercent < 100 && pathProgressPercent > 0"
                />
                <p class="path-meta">
                  已完成 <strong>{{ stats.path_completed_nodes }}</strong> / {{ stats.path_total_nodes }} 个节点
                </p>
                <div class="path-chips">
                  <span class="chip">剩余 {{ pathRemainingNodes }} 节点</span>
                  <span class="chip accent">完成度 {{ pathProgressPercent }}%</span>
                </div>
              </div>
            </div>

            <p class="path-hint">{{ pathHint }}</p>

            <div v-if="pathNodePreview.length" class="path-nodes">
              <div class="path-nodes-title">节点速览</div>
              <ul>
                <li v-for="(n, i) in pathNodePreview" :key="i" :class="n.status">
                  <span class="dot" />
                  <span class="node-name">{{ n.name }}</span>
                  <span class="node-status">{{ n.label }}</span>
                </li>
              </ul>
            </div>

            <div class="path-actions">
              <el-button type="primary" @click="router.push('/student/path')">
                {{ pathProgressPercent > 0 ? '继续学习' : '开始学习路径' }}
              </el-button>
            </div>
          </div>
        </el-col>
      </el-row>

      <!-- 近期学习记录 -->
      <div class="card section-card">
        <div class="section-header">
          <h3>近期学习记录</h3>
        </div>
        <el-table :data="stats.recent_records" stripe style="width: 100%">
          <el-table-column prop="resource_name" label="资源/节点" min-width="180" />
          <el-table-column prop="study_time" label="学习时间" width="160" />
          <el-table-column label="学习时长" width="120">
            <template #default="{ row }">{{ row.duration_minutes }} 分钟</template>
          </el-table-column>
        </el-table>
      </div>
    </template>

    <!-- 空状态 -->
    <div v-else-if="!loading" class="card empty-dashboard">
      <div class="empty-illustration">
        <svg viewBox="0 0 200 160" width="200" height="160" aria-hidden="true">
          <rect x="20" y="100" width="160" height="8" rx="4" fill="#e2e8f0" />
          <rect x="40" y="70" width="24" height="30" rx="4" fill="#2563eb" opacity="0.7" />
          <rect x="80" y="50" width="24" height="50" rx="4" fill="#10b981" opacity="0.8" />
          <rect x="120" y="60" width="24" height="40" rx="4" fill="#f59e0b" opacity="0.75" />
          <circle cx="100" cy="36" r="20" fill="#eff6ff" stroke="#2563eb" stroke-width="2" />
          <path d="M92 36 L98 42 L110 30" stroke="#2563eb" stroke-width="2.5" fill="none" stroke-linecap="round" />
        </svg>
      </div>
      <h3>还没有学习数据</h3>
      <p>完成画像构建并开始学习后，这里将展示你的学习时长、掌握度与进度趋势</p>
      <div class="empty-actions">
        <el-button type="primary" @click="router.push('/student/course-center')">课程中心</el-button>
        <el-button @click="router.push('/student/profile-dialogue')">构建学习画像</el-button>
        <el-button @click="router.push('/student/path')">规划学习路径</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.dashboard-page {
  .overview-row { margin-bottom: 20px; }
}

.gongsheng-section {
  .gs-metrics { margin-top: 4px; }
  .gs-metric {
    padding: 12px 14px;
    border-radius: 10px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
  }
  .gs-value {
    font-size: 22px;
    font-weight: 700;
    color: $text-primary;
  }
  .gs-label {
    margin-top: 4px;
    font-size: 12px;
    color: $text-secondary;
  }
  .gs-empty {
    margin: 14px 0 0;
    color: $text-secondary;
    font-size: 13px;
  }
}

.overview-card {
  display: flex;
  gap: 16px;
  padding: 20px;
  align-items: flex-start;
  transition: box-shadow 0.2s, transform 0.2s;
  &:hover { box-shadow: $shadow-card; transform: translateY(-2px); }

  .card-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .card-value {
    font-size: 26px;
    font-weight: 700;
    color: $text-primary;
    line-height: 1.2;
  }

  .card-label {
    font-size: 13px;
    color: $text-secondary;
    margin: 4px 0 8px;
  }

  .change-tag { font-size: 11px; }
}

.section-card {
  padding: 24px;
  margin-bottom: 20px;
  border-radius: 12px;
  box-shadow: $shadow-card;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;

  h3 { margin: 0; font-size: 16px; font-weight: 600; }
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: $text-primary;
}

.chart { width: 100%; }
.trend-chart { height: 300px; }
.mastery-chart {
  flex: 1;
  width: 100%;
  min-height: 520px;
  height: 520px;
}

.mastery-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 8px;
}

.ms-item {
  padding: 8px 10px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #eef2f7;
  min-width: 0;

  .ms-label {
    display: block;
    font-size: 11px;
    color: #94a3b8;
    margin-bottom: 2px;
  }
  strong {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    font-size: 12px;
    line-height: 1.35;
    color: #334155;
    overflow: hidden;
    white-space: normal;
    word-break: break-all;
  }
  &.good strong { color: #059669; }
  &.warn strong { color: #d97706; }
}

.mastery-section {
  .section-header { margin-bottom: 10px; }
}

.mastery-path-row {
  :deep(> .el-col) {
    display: flex;
  }
}

.equal-card {
  width: 100%;
  display: flex;
  flex-direction: column;
  min-height: 620px;
}

.path-section {
  .path-name {
    font-size: 14px;
    color: $text-secondary;
    margin: 0 0 16px;
    line-height: 1.5;
  }

  .path-progress-block {
    display: flex;
    align-items: center;
    gap: 20px;
    margin-bottom: 14px;
  }

  .path-progress-side {
    flex: 1;
    min-width: 0;
  }

  .path-meta {
    margin: 10px 0 8px;
    font-size: 13px;
    color: $text-secondary;
    strong { color: $primary; font-size: 16px; }
  }

  .path-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 12px;
    color: #606266;
    background: #f5f7fa;
    &.accent {
      color: #409EFF;
      background: #ecf5ff;
    }
  }

  .path-hint {
    margin: 0 0 14px;
    padding: 10px 12px;
    border-radius: 8px;
    background: #f8fafc;
    color: #606266;
    font-size: 13px;
    line-height: 1.55;
  }

  .path-nodes {
    flex: 1;
    margin-bottom: 14px;
  }

  .path-nodes-title {
    font-size: 13px;
    font-weight: 600;
    color: #303133;
    margin-bottom: 8px;
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  li {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 8px;
    background: #fafafa;
    border: 1px solid #eef0f3;
    font-size: 13px;

    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #c0c4cc;
      flex-shrink: 0;
    }
    .node-name {
      flex: 1;
      min-width: 0;
      color: #303133;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .node-status {
      flex-shrink: 0;
      font-size: 12px;
      color: #909399;
    }

    &.done {
      background: #f0f9eb;
      border-color: #e1f3d8;
      .dot { background: #67C23A; }
      .node-status { color: #67C23A; }
    }
    &.doing {
      background: #ecf5ff;
      border-color: #d9ecff;
      .dot { background: #409EFF; }
      .node-status { color: #409EFF; }
    }
  }

  .path-actions {
    margin-top: auto;
    padding-top: 4px;
  }
}

.empty-dashboard {
  padding: 64px 32px;
  text-align: center;
  border-radius: 12px;

  .empty-illustration { margin-bottom: 24px; }
  h3 { font-size: 20px; margin: 0 0 8px; }
  p { color: $text-secondary; margin: 0 0 24px; max-width: 420px; margin-left: auto; margin-right: auto; }
  .empty-actions { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
}

@media (max-width: 768px) {
  .overview-card .card-value { font-size: 22px; }
  .trend-chart { height: 240px; }
  .mastery-chart { min-height: 480px; height: 480px; }
  .mastery-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .path-progress-block { flex-direction: column; align-items: flex-start; }
  .equal-card { min-height: 0; }
}
</style>
