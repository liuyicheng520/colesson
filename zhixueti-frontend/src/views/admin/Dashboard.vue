<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import echarts, { type ECharts } from '@/utils/echarts'
import { ElMessage } from 'element-plus'
import { adminOpsApi, type AdminOverviewStats, type AdminTrendStats } from '@/api/adminOps'
import AdminPageHero from '@/components/admin/AdminPageHero.vue'

const loading = ref(true)
const overview = ref<AdminOverviewStats | null>(null)
const trends = ref<AdminTrendStats | null>(null)
const featureUsage = ref<{ name: string; value: number }[]>([])
const topTopics = ref<{ topic: string; count: number }[]>([])
const trendDays = ref<7 | 30>(7)

const trendRef = ref<HTMLElement>()
const pieRef = ref<HTMLElement>()
let trendChart: ECharts | null = null
let pieChart: ECharts | null = null

const cards = computed(() => {
  const o = overview.value
  if (!o) return []
  return [
    { label: '总用户数', value: o.total_users, color: '#2563eb' },
    { label: '日活用户', value: o.dau_users, color: '#10b981' },
    { label: '累计学习时长(h)', value: o.total_study_hours, color: '#f59e0b' },
    { label: '问答总量', value: o.qa_total, color: '#8b5cf6' },
    { label: '多模态生成', value: o.multimodal_total, color: '#ec4899' },
  ]
})

async function loadAll() {
  loading.value = true
  try {
    const [ov, tr, fu, tt] = await Promise.all([
      adminOpsApi.overview(),
      adminOpsApi.trends(trendDays.value),
      adminOpsApi.featureUsage(),
      adminOpsApi.topTopics(),
    ])
    overview.value = ov
    trends.value = tr
    featureUsage.value = fu
    topTopics.value = tt
    await nextTick()
    renderCharts()
  } catch {
    ElMessage.error('数据加载失败')
  } finally {
    loading.value = false
  }
}

async function reloadTrends() {
  trends.value = await adminOpsApi.trends(trendDays.value)
  await nextTick()
  renderTrendChart()
}

function renderTrendChart() {
  if (!trendRef.value || !trends.value) return
  if (!trendChart) trendChart = echarts.init(trendRef.value)
  const t = trends.value
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['用户注册', '问答量', '视频讲解'] },
    grid: { left: 48, right: 24, bottom: 32, top: 40 },
    xAxis: { type: 'category', data: t.dates.map((d) => d.slice(5)) },
    yAxis: { type: 'value' },
    series: [
      { name: '用户注册', type: 'line', smooth: true, data: t.registrations },
      { name: '问答量', type: 'line', smooth: true, data: t.qa_counts },
      { name: '视频讲解', type: 'line', smooth: true, data: t.lecture_counts },
    ],
  })
}

function renderPieChart() {
  if (!pieRef.value) return
  if (!pieChart) pieChart = echarts.init(pieRef.value)
  // 移除 labelLine 引导线，避免容器裁切；标签内嵌展示
  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', left: 'left', top: 'middle', textStyle: { fontSize: 12 } },
    series: [
      {
        type: 'pie',
        radius: ['42%', '62%'],
        center: ['58%', '50%'],
        avoidLabelOverlap: true,
        label: { show: true, position: 'inside', formatter: '{d}%', fontSize: 9, color: '#fff' },
        labelLine: { show: false },
        data: featureUsage.value.length ? featureUsage.value : [{ name: '暂无数据', value: 1 }],
      },
    ],
  })
}

function renderCharts() {
  renderTrendChart()
  renderPieChart()
}

watch(trendDays, reloadTrends)

onMounted(loadAll)
onBeforeUnmount(() => {
  trendChart?.dispose()
  pieChart?.dispose()
})
</script>

<template>
  <div v-loading="loading" class="page-container">
    <AdminPageHero module="dashboard" />
    <el-row :gutter="16" class="stat-row">
      <el-col v-for="c in cards" :key="c.label" :xs="12" :sm="8" :md="4">
        <div class="stat-card card">
          <div class="val" :style="{ color: c.color }">{{ c.value }}</div>
          <div class="lbl">{{ c.label }}</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="16" :xs="24">
        <div class="card chart-wrap">
          <div class="chart-head">
            <h3>平台趋势</h3>
            <el-radio-group v-model="trendDays" size="small">
              <el-radio-button :value="7">近7天</el-radio-button>
              <el-radio-button :value="30">近30天</el-radio-button>
            </el-radio-group>
          </div>
          <div ref="trendRef" class="chart" />
        </div>
      </el-col>
      <el-col :span="8" :xs="24">
        <div class="card chart-wrap">
          <h3>功能使用占比</h3>
          <div ref="pieRef" class="chart pie" />
        </div>
      </el-col>
    </el-row>

    <div class="card table-wrap">
      <h3>热门知识点 TOP10</h3>
      <el-table :data="topTopics" stripe empty-text="暂无数据">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="topic" label="知识点/主题" min-width="240" show-overflow-tooltip />
        <el-table-column prop="count" label="提问次数" width="120" />
      </el-table>
    </div>
  </div>
</template>

<style scoped lang="scss">
.stat-row { margin-bottom: 20px; }
.stat-card {
  padding: 20px 16px;
  text-align: center;
  margin-bottom: 12px;
  .val { font-size: 28px; font-weight: 700; }
  .lbl { color: $text-secondary; margin-top: 4px; font-size: 13px; }
}
.chart-wrap {
  padding: 20px;
  margin-bottom: 20px;
  h3 { margin-bottom: 12px; font-size: 16px; }
  .chart-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; h3 { margin: 0; } }
}
.chart { height: 320px; }
.chart.pie { height: 300px; min-height: 280px; }
.table-wrap { padding: 20px; h3 { margin-bottom: 16px; } }
</style>
