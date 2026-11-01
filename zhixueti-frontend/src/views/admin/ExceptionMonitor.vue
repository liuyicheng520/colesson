<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  adminAuditApi,
  type AuditOverviewStats,
  type ExceptionLogItem,
} from '@/api/adminAudit'
import { formatDateTime, hasPerm } from '@/utils/permission'
import AdminPageHero from '@/components/admin/AdminPageHero.vue'

const loading = ref(false)
const overview = ref<AuditOverviewStats | null>(null)
const logs = ref<ExceptionLogItem[]>([])
const total = ref(0)
const trendDays = ref<7 | 30>(7)
const trendRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null

const query = reactive({
  keyword: '',
  is_resolved: undefined as number | undefined,
  page: 1,
  page_size: 15,
})

const cards = computed(() => {
  const o = overview.value
  if (!o) return []
  return [
    { label: '异常总数', value: o.exception_total, color: '#ef4444' },
    { label: '未处理', value: o.exception_unresolved, color: '#f59e0b' },
    { label: '24h 新增', value: o.exception_24h, color: '#8b5cf6' },
    { label: '24h 失败请求', value: o.operation_failed_24h, color: '#64748b' },
  ]
})

async function loadOverview() {
  overview.value = await adminAuditApi.overview()
}

async function loadLogs() {
  loading.value = true
  try {
    const res = await adminAuditApi.listExceptionLogs({
      keyword: query.keyword || undefined,
      is_resolved: query.is_resolved,
      page: query.page,
      page_size: query.page_size,
    })
    logs.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

async function loadTrend() {
  const data = await adminAuditApi.exceptionTrends(trendDays.value)
  await nextTick()
  if (!trendRef.value) return
  if (!trendChart) trendChart = echarts.init(trendRef.value)
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, bottom: 28, top: 24 },
    xAxis: { type: 'category', data: data.map((d) => d.date.slice(5)) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{ type: 'bar', data: data.map((d) => d.count), itemStyle: { color: '#ef4444' } }],
  })
}

async function loadAll() {
  await Promise.all([loadOverview(), loadLogs(), loadTrend()])
}

async function resolve(row: ExceptionLogItem, resolved: number) {
  await adminAuditApi.resolveException(row.id, resolved)
  ElMessage.success(resolved ? '已标记为已处理' : '已标记为未处理')
  loadAll()
}

async function purgeLogs() {
  if (!hasPerm('btn:log:purge')) return
  await ElMessageBox.confirm(
    `将清理 ${overview.value?.log_retention_days ?? 90} 天前的操作日志与异常记录，是否继续？`,
    '清理过期日志',
    { type: 'warning' },
  )
  const res = await adminAuditApi.purgeLogs()
  ElMessage.success(`已清理操作日志 ${res.operation_deleted} 条、异常 ${res.exception_deleted} 条`)
  loadAll()
}

watch(trendDays, loadTrend)

onMounted(loadAll)
onBeforeUnmount(() => trendChart?.dispose())
</script>

<template>
  <div class="page-container">
    <AdminPageHero module="exceptions" />
    <el-row :gutter="16" class="stat-row">
      <el-col v-for="c in cards" :key="c.label" :xs="12" :sm="6">
        <div class="stat-card card">
          <div class="val" :style="{ color: c.color }">{{ c.value }}</div>
          <div class="lbl">{{ c.label }}</div>
        </div>
      </el-col>
    </el-row>

    <div class="card chart-wrap">
      <div class="chart-head">
        <h3>异常趋势</h3>
        <div class="head-actions">
          <el-radio-group v-model="trendDays" size="small">
            <el-radio-button :value="7">近7天</el-radio-button>
            <el-radio-button :value="30">近30天</el-radio-button>
          </el-radio-group>
          <el-button v-if="hasPerm('btn:log:purge')" size="small" @click="purgeLogs">清理过期日志</el-button>
        </div>
      </div>
      <div ref="trendRef" class="chart" />
      <p v-if="overview" class="retention-hint">日志保留策略：{{ overview.log_retention_days }} 天（启动时自动清理）</p>
    </div>

    <div class="card table-wrap">
      <div class="toolbar">
        <h3>异常记录</h3>
        <div class="toolbar-right">
          <el-select v-model="query.is_resolved" placeholder="处理状态" clearable style="width:120px" @change="() => { query.page = 1; loadLogs() }">
            <el-option label="未处理" :value="0" />
            <el-option label="已处理" :value="1" />
          </el-select>
          <el-input v-model="query.keyword" placeholder="类型 / 消息 / URL" style="width:200px" clearable @keyup.enter="() => { query.page = 1; loadLogs() }">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button type="primary" @click="() => { query.page = 1; loadLogs() }">搜索</el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="logs" stripe empty-text="暂无异常">
        <el-table-column prop="error_type" label="类型" width="140" show-overflow-tooltip />
        <el-table-column prop="message" label="错误信息" min-width="240" show-overflow-tooltip />
        <el-table-column prop="request_url" label="路径" width="160" show-overflow-tooltip />
        <el-table-column prop="username" label="用户" width="90">
          <template #default="{ row }">{{ row.username || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_resolved ? 'success' : 'danger'" size="small">{{ row.is_resolved ? '已处理' : '未处理' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button v-if="!row.is_resolved" text type="primary" @click="resolve(row, 1)">标记处理</el-button>
            <el-button v-else text @click="resolve(row, 0)">重新打开</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="query.page"
        :total="total"
        :page-size="query.page_size"
        layout="total, prev, pager, next"
        class="pager"
        @current-change="loadLogs"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.stat-row { margin-bottom: 16px; }
.stat-card {
  padding: 18px;
  text-align: center;
  margin-bottom: 12px;
  .val { font-size: 26px; font-weight: 700; }
  .lbl { color: $text-secondary; font-size: 13px; margin-top: 4px; }
}
.chart-wrap { padding: 20px; margin-bottom: 16px; }
.chart-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  h3 { margin: 0; }
  .head-actions { display: flex; gap: 12px; align-items: center; }
}
.chart { height: 240px; }
.retention-hint { font-size: 12px; color: $text-secondary; margin: 8px 0 0; }
.table-wrap { padding: 24px; }
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
  h3 { margin: 0; }
}
.toolbar-right { display: flex; gap: 8px; flex-wrap: wrap; }
.pager { margin-top: 12px; justify-content: flex-end; }
</style>
