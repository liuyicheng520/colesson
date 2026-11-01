<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminContentApi, type AdminDocumentItem, type AdminDocumentSettings } from '@/api/adminContent'
import { hasPerm } from '@/utils/permission'
import AdminContentPreview, { type PreviewPayload } from '@/components/admin/AdminContentPreview.vue'
import AdminPageHero from '@/components/admin/AdminPageHero.vue'

const loading = ref(false)
const docs = ref<AdminDocumentItem[]>([])
const total = ref(0)
const settings = ref<AdminDocumentSettings | null>(null)
const settingsVisible = ref(false)

const previewVisible = ref(false)
const previewLoading = ref(false)
const previewError = ref('')
const previewPayload = ref<PreviewPayload | null>(null)
const previewTitle = ref('')

const query = reactive({
  keyword: '',
  audit_status: undefined as number | undefined,
  page: 1,
  page_size: 15,
})

const settingsForm = reactive({
  audit_enabled: false,
  max_file_mb: 100,
  allowed_extensions: '.pdf,.docx,.pptx',
})

const selectedRows = ref<AdminDocumentItem[]>([])

const auditMap: Record<number, { label: string; type: string }> = {
  0: { label: '待审核', type: 'warning' },
  1: { label: '已通过', type: 'success' },
  2: { label: '已驳回', type: 'danger' },
}

async function load() {
  loading.value = true
  try {
    const data = await adminContentApi.listDocuments({
      keyword: query.keyword || undefined,
      audit_status: query.audit_status,
      page: query.page,
      page_size: query.page_size,
    })
    docs.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function openSettings() {
  settings.value = await adminContentApi.getDocumentSettings()
  settingsForm.audit_enabled = settings.value.audit_enabled
  settingsForm.max_file_mb = settings.value.max_file_mb
  settingsForm.allowed_extensions = settings.value.allowed_extensions.join(',')
  settingsVisible.value = true
}

async function saveSettings() {
  const exts = settingsForm.allowed_extensions.split(',').map((s) => s.trim()).filter(Boolean)
  settings.value = await adminContentApi.updateDocumentSettings({
    audit_enabled: settingsForm.audit_enabled,
    max_file_mb: settingsForm.max_file_mb,
    allowed_extensions: exts,
  })
  ElMessage.success('文档配置已更新')
  settingsVisible.value = false
}

async function audit(row: AdminDocumentItem, status: number, label: string) {
  await ElMessageBox.confirm(`确定${label}文档「${row.filename}」吗？`, '二次确认', { type: 'warning' })
  await adminContentApi.auditDocument(row.user_id, row.doc_id, status)
  ElMessage.success(`${label}成功`)
  load()
}

async function remove(row: AdminDocumentItem) {
  await ElMessageBox.confirm(`确定删除「${row.filename}」吗？`, '二次确认', { type: 'warning' })
  await adminContentApi.deleteDocument(row.user_id, row.doc_id)
  ElMessage.success('已删除')
  load()
}

function onSelectionChange(rows: AdminDocumentItem[]) {
  selectedRows.value = rows
}

async function batchAudit(status: number, label: string) {
  if (!selectedRows.value.length) {
    ElMessage.warning('请先选择文档')
    return
  }
  await ElMessageBox.confirm(`确定批量${label} ${selectedRows.value.length} 个文档吗？`, '二次确认', { type: 'warning' })
  const res = await adminContentApi.batchAuditDocuments(
    selectedRows.value.map((r) => ({ user_id: r.user_id, doc_id: r.doc_id })),
    status,
  )
  ElMessage.success(`已${label} ${res.updated} 个文档`)
  selectedRows.value = []
  load()
}

async function viewDocument(row: AdminDocumentItem) {
  previewVisible.value = true
  previewLoading.value = true
  previewError.value = ''
  previewPayload.value = null
  previewTitle.value = row.filename
  try {
    const data = await adminContentApi.previewDocument(row.user_id, row.doc_id)
    previewPayload.value = { kind: 'document', data }
  } catch (e: unknown) {
    previewError.value = (e as Error)?.message || '文档加载失败'
  } finally {
    previewLoading.value = false
  }
}

function retryPreview() {
  const row = docs.value.find((d) => d.filename === previewTitle.value)
  if (row) viewDocument(row)
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <AdminPageHero module="documents" />
    <div class="card table-wrap">
      <div class="toolbar">
        <h3>用户上传文档</h3>
        <div class="toolbar-right">
          <el-select v-model="query.audit_status" placeholder="审核状态" clearable style="width:120px" @change="() => { query.page = 1; load() }">
            <el-option label="待审核" :value="0" />
            <el-option label="已通过" :value="1" />
            <el-option label="已驳回" :value="2" />
          </el-select>
          <el-input v-model="query.keyword" placeholder="文件名" style="width:200px" clearable @keyup.enter="() => { query.page = 1; load() }">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button v-if="hasPerm('btn:document:audit')" @click="openSettings">审核配置</el-button>
        </div>
      </div>

      <div v-if="hasPerm('btn:document:audit') && selectedRows.length" class="batch-bar">
        <span>已选 {{ selectedRows.length }} 项</span>
        <el-button size="small" type="success" @click="batchAudit(1, '通过')">批量通过</el-button>
        <el-button size="small" type="warning" @click="batchAudit(2, '驳回')">批量驳回</el-button>
      </div>

      <el-table v-loading="loading" :data="docs" stripe @selection-change="onSelectionChange">
        <el-table-column v-if="hasPerm('btn:document:audit')" type="selection" width="45" />
        <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip />
        <el-table-column prop="username" label="用户" width="100" />
        <el-table-column prop="page_count" label="页数" width="70" />
        <el-table-column label="大小" width="90">
          <template #default="{ row }">{{ row.file_size ? `${Math.round(row.file_size / 1024)} KB` : '-' }}</template>
        </el-table-column>
        <el-table-column label="审核" width="90">
          <template #default="{ row }">
            <el-tag :type="(auditMap[row.audit_status]?.type as any)" size="small">{{ auditMap[row.audit_status]?.label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <div class="action-row">
              <el-button size="small" type="primary" @click="viewDocument(row)">查看文档</el-button>
              <el-button v-if="hasPerm('btn:document:audit') && row.audit_status !== 1" size="small" type="success" @click="audit(row, 1, '通过')">通过</el-button>
              <el-button v-if="hasPerm('btn:document:audit') && row.audit_status !== 2" size="small" type="warning" @click="audit(row, 2, '驳回')">驳回</el-button>
              <el-button v-if="hasPerm('btn:content:delete')" size="small" type="danger" @click="remove(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination v-model:current-page="query.page" :total="total" :page-size="query.page_size" layout="total, prev, pager, next" style="margin-top:12px" @current-change="load" />
    </div>

    <el-dialog v-model="settingsVisible" title="文档审核配置" width="480px">
      <el-form label-width="120px">
        <el-form-item label="开启审核">
          <el-switch v-model="settingsForm.audit_enabled" />
          <div class="hint">开启后用户上传文档需审核通过才可用于问答</div>
        </el-form-item>
        <el-form-item label="单文件上限(MB)">
          <el-input-number v-model="settingsForm.max_file_mb" :min="1" :max="500" />
        </el-form-item>
        <el-form-item label="允许格式">
          <el-input v-model="settingsForm.allowed_extensions" placeholder=".pdf,.docx,.pptx" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="settingsVisible = false">取消</el-button>
        <el-button type="primary" @click="saveSettings">保存</el-button>
      </template>
    </el-dialog>

    <AdminContentPreview
      v-model:visible="previewVisible"
      :title="previewTitle"
      :loading="previewLoading"
      :error="previewError"
      :payload="previewPayload"
      @retry="retryPreview"
    />
  </div>
</template>

<style scoped lang="scss">
.table-wrap { padding: 24px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px; }
.toolbar-right { display: flex; gap: 8px; flex-wrap: wrap; }
.batch-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; padding: 8px 12px; background: #f8fafc; border-radius: 6px; font-size: 13px; }
.hint { font-size: 12px; color: $text-secondary; margin-top: 4px; }
</style>
