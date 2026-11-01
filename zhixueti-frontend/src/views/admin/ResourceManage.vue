<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminContentApi, type AdminResourceItem } from '@/api/adminContent'
import { hasPerm } from '@/utils/permission'
import AdminContentPreview, { type PreviewPayload } from '@/components/admin/AdminContentPreview.vue'
import AdminPageHero from '@/components/admin/AdminPageHero.vue'

const loading = ref(false)
const resources = ref<AdminResourceItem[]>([])
const total = ref(0)
const selected = ref<AdminResourceItem[]>([])

const previewVisible = ref(false)
const previewLoading = ref(false)
const previewError = ref('')
const previewPayload = ref<PreviewPayload | null>(null)
const previewRow = ref<AdminResourceItem | null>(null)

const query = reactive({
  keyword: '',
  status: undefined as number | undefined,
  type_code: '',
  page: 1,
  page_size: 15,
})

const statusMap: Record<number, { label: string; type: string }> = {
  0: { label: '生成中', type: 'info' },
  1: { label: '待审核', type: 'warning' },
  2: { label: '已发布', type: 'success' },
  3: { label: '已拒绝', type: 'danger' },
}

async function load() {
  loading.value = true
  try {
    const data = await adminContentApi.listResources({
      keyword: query.keyword || undefined,
      status: query.status,
      type_code: query.type_code || undefined,
      page: query.page,
      page_size: query.page_size,
    })
    resources.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  load()
}

async function setStatus(row: AdminResourceItem, status: number, label: string) {
  await ElMessageBox.confirm(`确定将「${row.title}」设为${label}吗？`, '二次确认', { type: 'warning' })
  await adminContentApi.setResourceStatus(row.id, status)
  ElMessage.success('操作成功')
  load()
}

async function batchStatus(status: number, label: string) {
  if (!selected.value.length) {
    ElMessage.warning('请先选择资源')
    return
  }
  await ElMessageBox.confirm(`确定批量${label} ${selected.value.length} 项资源吗？`, '二次确认', { type: 'warning' })
  await adminContentApi.batchResourceStatus(
    selected.value.map((r) => r.id),
    status,
  )
  ElMessage.success('批量操作成功')
  selected.value = []
  load()
}

async function removeResource(row: AdminResourceItem) {
  await ElMessageBox.confirm(`确定删除「${row.title}」吗？此操作不可恢复。`, '二次确认', { type: 'warning' })
  await adminContentApi.deleteResource(row.id)
  ElMessage.success('已删除')
  load()
}

async function exportJson() {
  const data = await adminContentApi.exportResources()
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `resources-export-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

async function viewContent(row: AdminResourceItem) {
  previewRow.value = row
  previewVisible.value = true
  previewLoading.value = true
  previewError.value = ''
  previewPayload.value = null
  try {
    const data = await adminContentApi.previewResource(row.id)
    previewPayload.value = { kind: 'resource', data }
  } catch (e: unknown) {
    previewError.value = (e as Error)?.message || '资源内容加载失败'
  } finally {
    previewLoading.value = false
  }
}

function retryPreview() {
  if (previewRow.value) viewContent(previewRow.value)
}

async function previewSetStatus(status: number, label: string) {
  if (!previewRow.value) return
  await setStatus(previewRow.value, status, label)
  previewVisible.value = false
}

async function previewRemove() {
  if (!previewRow.value) return
  await removeResource(previewRow.value)
  previewVisible.value = false
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <AdminPageHero module="resources" />
    <div class="card table-wrap">
      <div class="toolbar">
        <h3>学习资源管理</h3>
        <div class="toolbar-right">
          <el-select v-model="query.status" placeholder="状态" clearable style="width: 120px" @change="handleSearch">
            <el-option label="待审核" :value="1" />
            <el-option label="已发布" :value="2" />
            <el-option label="已拒绝" :value="3" />
          </el-select>
          <el-input v-model="query.keyword" placeholder="标题/主题" style="width: 200px" clearable @keyup.enter="handleSearch">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button v-if="hasPerm('btn:resource:publish')" @click="exportJson">导出 JSON</el-button>
        </div>
      </div>

      <div v-if="hasPerm('btn:resource:publish')" class="batch-bar">
        <el-button size="small" type="success" @click="batchStatus(2, '发布')">批量发布</el-button>
        <el-button size="small" type="warning" @click="batchStatus(1, '下架')">批量下架</el-button>
      </div>

      <el-table v-loading="loading" :data="resources" stripe @selection-change="(rows: AdminResourceItem[]) => (selected = rows)">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="type_name" label="类型" width="100" />
        <el-table-column prop="username" label="用户" width="100" />
        <el-table-column prop="topic" label="主题" width="120" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="(statusMap[row.status]?.type as any)" size="small">{{ statusMap[row.status]?.label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <div class="action-row">
              <el-button size="small" type="primary" @click="viewContent(row)">查看内容</el-button>
              <el-button v-if="hasPerm('btn:resource:publish') && row.status !== 2" size="small" type="success" @click="setStatus(row, 2, '已发布')">发布</el-button>
              <el-button v-if="hasPerm('btn:resource:publish') && row.status === 2" size="small" type="warning" @click="setStatus(row, 1, '待审核')">下架</el-button>
              <el-button v-if="hasPerm('btn:resource:delete')" size="small" type="danger" @click="removeResource(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="query.page"
        :total="total"
        :page-size="query.page_size"
        layout="total, prev, pager, next"
        style="margin-top: 16px"
        @current-change="load"
      />
    </div>

    <AdminContentPreview
      v-model:visible="previewVisible"
      :title="previewRow?.title"
      :loading="previewLoading"
      :error="previewError"
      :payload="previewPayload"
      @retry="retryPreview"
    >
      <template v-if="previewRow" #footer-actions>
        <el-button
          v-if="hasPerm('btn:resource:publish') && previewRow.status !== 2"
          size="small"
          type="success"
          @click="previewSetStatus(2, '已发布')"
        >发布</el-button>
        <el-button
          v-if="hasPerm('btn:resource:publish') && previewRow.status === 2"
          size="small"
          type="warning"
          @click="previewSetStatus(1, '待审核')"
        >下架</el-button>
        <el-button
          v-if="hasPerm('btn:resource:delete')"
          size="small"
          type="danger"
          @click="previewRemove"
        >删除</el-button>
      </template>
    </AdminContentPreview>
  </div>
</template>

<style scoped lang="scss">
.table-wrap { padding: 24px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 12px; }
.toolbar-right { display: flex; gap: 8px; flex-wrap: wrap; }
.batch-bar { margin-bottom: 12px; display: flex; gap: 8px; }
</style>
