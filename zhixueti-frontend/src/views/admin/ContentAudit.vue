<script setup lang="ts">
import { onMounted, ref, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { securityApi, AUDIT_RESULT_MAP, type AuditItem, type LlmLogItem } from '@/api/security'
import { formatBeijingDateTime } from '@/utils/datetime'
import AdminPageHero from '@/components/admin/AdminPageHero.vue'

const audits = ref<AuditItem[]>([])
const logs = ref<LlmLogItem[]>([])
const loading = ref(false)
const auditError = ref('')
const logError = ref('')
const activeTab = ref('audits')
const auditFilter = reactive({ audit_result: undefined as number | undefined, page: 1 })
const logPage = ref(1)
const auditTotal = ref(0)
const logTotal = ref(0)

const RISK_TYPE: Record<number, string> = {
  0: 'info', 1: 'warning', 2: 'danger', 3: 'danger',
}

/** 安全校验审核记录字段，防止异常数据导致渲染崩溃 */
function normalizeAudit(row: unknown): AuditItem | null {
  if (!row || typeof row !== 'object') return null
  const r = row as Record<string, unknown>
  if (typeof r.id !== 'number') return null
  return {
    id: r.id as number,
    audit_no: String(r.audit_no || ''),
    target_type: String(r.target_type || ''),
    target_id: Number(r.target_id) || 0,
    content_snapshot: r.content_snapshot != null ? String(r.content_snapshot) : null,
    audit_type: String(r.audit_type || ''),
    audit_result: Number(r.audit_result) || 0,
    risk_level: Number(r.risk_level) || 0,
    risk_labels: Array.isArray(r.risk_labels) ? r.risk_labels.map(String) : null,
    risk_detail: (r.risk_detail as Record<string, unknown>) || null,
    auditor_id: r.auditor_id != null ? Number(r.auditor_id) : null,
    audit_note: r.audit_note != null ? String(r.audit_note) : null,
    created_at: String(r.created_at || ''),
  }
}

async function loadAudits() {
  loading.value = true
  auditError.value = ''
  try {
    const data = await securityApi.listAudits({
      audit_result: auditFilter.audit_result,
      page: auditFilter.page,
      page_size: 15,
    })
    audits.value = (data.items || []).map(normalizeAudit).filter(Boolean) as AuditItem[]
    auditTotal.value = data.total ?? 0
  } catch (e: unknown) {
    audits.value = []
    auditError.value = (e as Error)?.message || '审核记录加载失败'
    ElMessage.error(auditError.value)
  } finally {
    loading.value = false
  }
}

async function loadLogs() {
  loading.value = true
  logError.value = ''
  try {
    const data = await securityApi.listLlmLogs({ page: logPage.value, page_size: 15 })
    logs.value = Array.isArray(data.items) ? data.items : []
    logTotal.value = data.total ?? 0
  } catch (e: unknown) {
    logs.value = []
    logError.value = (e as Error)?.message || 'LLM 日志加载失败'
    ElMessage.error(logError.value)
  } finally {
    loading.value = false
  }
}

async function handleReview(row: AuditItem, result: number) {
  const { value } = await ElMessageBox.prompt('审核备注（可选）', '人工审核', {
    confirmButtonText: '确认',
    inputPlaceholder: AUDIT_RESULT_MAP[result],
  }).catch(() => ({ value: null }))
  if (value === null) return
  try {
    await securityApi.reviewAudit(row.id, { audit_result: result, audit_note: value || undefined })
    ElMessage.success('审核已更新')
    loadAudits()
  } catch {
    ElMessage.error('审核操作失败')
  }
}

async function handleTakedown(row: AuditItem) {
  if (row.target_type !== 'resource') {
    ElMessage.warning('当前仅支持资源类内容下架')
    return
  }
  const { value } = await ElMessageBox.prompt('下架原因', '违规内容下架', {
    confirmButtonText: '确认下架',
    type: 'warning',
  }).catch(() => ({ value: null }))
  if (!value) return
  try {
    await securityApi.takedown({ target_type: 'resource', target_id: row.target_id, reason: value })
    ElMessage.success('内容已下架')
    loadAudits()
  } catch {
    ElMessage.error('下架操作失败')
  }
}

function onTabChange(name: string | number) {
  if (name === 'logs' && !logs.value.length && !logError.value) loadLogs()
}

onMounted(() => {
  loadAudits()
})
</script>

<template>
  <div class="page-container">
    <AdminPageHero module="security" />

    <el-tabs v-model="activeTab" class="card tabs-panel" @tab-change="onTabChange">
      <el-tab-pane label="审核记录" name="audits">
        <div class="toolbar">
          <el-select v-model="auditFilter.audit_result" placeholder="审核结果" clearable style="width:140px" @change="loadAudits">
            <el-option label="拒绝" :value="0" />
            <el-option label="通过" :value="1" />
            <el-option label="待复核" :value="2" />
          </el-select>
          <el-button @click="loadAudits">刷新</el-button>
        </div>

        <el-alert v-if="auditError" :title="auditError" type="error" show-icon :closable="false" class="error-bar">
          <el-button size="small" type="primary" @click="loadAudits">重试</el-button>
        </el-alert>

        <el-table v-loading="loading" :data="audits" stripe empty-text="暂无审核记录">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="target_type" label="类型" width="90" />
          <el-table-column prop="target_id" label="对象ID" width="80" />
          <el-table-column label="内容快照" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">{{ row.content_snapshot?.slice(0, 80) }}</template>
          </el-table-column>
          <el-table-column label="结果" width="90">
            <template #default="{ row }">
              <el-tag size="small">{{ AUDIT_RESULT_MAP[row.audit_result] || row.audit_result }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="风险" width="80">
            <template #default="{ row }">
              <el-tag size="small" :type="RISK_TYPE[row.risk_level]">{{ row.risk_level }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="时间" width="170">
            <template #default="{ row }">{{ formatBeijingDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="260" fixed="right">
            <template #default="{ row }">
              <div class="action-row">
                <el-button size="small" type="success" @click="handleReview(row, 1)">通过</el-button>
                <el-button size="small" type="warning" @click="handleReview(row, 2)">复核</el-button>
                <el-button size="small" type="danger" @click="handleTakedown(row)">下架</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="LLM 调用追溯" name="logs">
        <el-alert v-if="logError" :title="logError" type="error" show-icon :closable="false" class="error-bar">
          <el-button size="small" type="primary" @click="loadLogs">重试</el-button>
        </el-alert>

        <el-table v-loading="loading" :data="logs" stripe empty-text="暂无调用日志">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="provider" label="Provider" width="90" />
          <el-table-column prop="model_name" label="Model" width="120" />
          <el-table-column prop="user_id" label="用户" width="70" />
          <el-table-column label="Token" width="100">
            <template #default="{ row }">{{ row.total_tokens }}</template>
          </el-table-column>
          <el-table-column label="流式" width="60">
            <template #default="{ row }">{{ row.is_stream ? '是' : '否' }}</template>
          </el-table-column>
          <el-table-column label="校验" width="80">
            <template #default="{ row }">
              <el-tag size="small" :type="row.status === 1 ? 'success' : 'warning'">
                {{ row.validation?.passed === false ? '存疑' : '通过' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="提示词摘要" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">{{ row.prompt_preview?.slice(0, 100) }}</template>
          </el-table-column>
          <el-table-column label="时间" width="170">
            <template #default="{ row }">{{ formatBeijingDateTime(row.created_at) }}</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped lang="scss">
.page-header {
  padding: 20px;
  margin-bottom: 16px;
  h3 { margin: 0 0 8px; }
  p { margin: 0; color: $text-secondary; font-size: 13px; }
}
.tabs-panel { padding: 16px; }
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; }
.error-bar { margin-bottom: 16px; }
</style>
