<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminAuditApi, type OperationLogItem } from '@/api/adminAudit'
import { formatDateTime } from '@/utils/permission'
import AdminPageHero from '@/components/admin/AdminPageHero.vue'

const loading = ref(false)
const logs = ref<OperationLogItem[]>([])
const total = ref(0)

const query = reactive({
  keyword: '',
  module: '',
  status: undefined as number | undefined,
  dateRange: [] as string[],
  page: 1,
  page_size: 20,
})

async function load() {
  loading.value = true
  try {
    const res = await adminAuditApi.listOperationLogs({
      keyword: query.keyword || undefined,
      module: query.module || undefined,
      status: query.status,
      date_from: query.dateRange[0] ? `${query.dateRange[0]}T00:00:00` : undefined,
      date_to: query.dateRange[1] ? `${query.dateRange[1]}T23:59:59` : undefined,
      page: query.page,
      page_size: query.page_size,
    })
    logs.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  load()
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <AdminPageHero module="logs" />
    <div class="card table-wrap">
      <div class="toolbar">
        <h3>操作日志</h3>
        <div class="toolbar-right">
          <el-date-picker
            v-model="query.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DD"
            style="width: 260px"
            @change="handleSearch"
          />
          <el-select v-model="query.status" placeholder="结果" clearable style="width:100px" @change="handleSearch">
            <el-option label="成功" :value="1" />
            <el-option label="失败" :value="0" />
          </el-select>
          <el-input v-model="query.module" placeholder="模块" style="width:100px" clearable @keyup.enter="handleSearch" />
          <el-input v-model="query.keyword" placeholder="URL / 错误信息" style="width:180px" clearable @keyup.enter="handleSearch">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="logs" stripe empty-text="暂无日志">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="用户" width="100">
          <template #default="{ row }">{{ row.username || '-' }}</template>
        </el-table-column>
        <el-table-column prop="module" label="模块" width="90" />
        <el-table-column prop="request_method" label="方法" width="70" />
        <el-table-column prop="request_url" label="请求路径" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态码" width="80">
          <template #default="{ row }">{{ row.response_code ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="耗时" width="80">
          <template #default="{ row }">{{ row.duration_ms != null ? `${row.duration_ms}ms` : '-' }}</template>
        </el-table-column>
        <el-table-column label="结果" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">{{ row.status === 1 ? '成功' : '失败' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip_address" label="IP" width="120" />
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        class="pager"
        @current-change="load"
        @size-change="() => { query.page = 1; load() }"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.table-wrap { padding: 24px; }
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
  h3 { margin: 0; }
}
.toolbar-right { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.pager { margin-top: 16px; justify-content: flex-end; }
</style>
