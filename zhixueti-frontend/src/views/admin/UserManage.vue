<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, type AdminUserListItem } from '@/api/admin'
import { hasPerm, formatDateTime } from '@/utils/permission'
import AdminPageHero from '@/components/admin/AdminPageHero.vue'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const users = ref<AdminUserListItem[]>([])
const total = ref(0)
const selectedIds = ref<number[]>([])

const query = reactive({
  keyword: '',
  status: undefined as number | undefined,
  dateRange: [] as string[],
  page: 1,
  page_size: 20,
})

function toDateParam(d: string, endOfDay = false): string {
  return endOfDay ? `${d}T23:59:59` : `${d}T00:00:00`
}

async function loadUsers() {
  loading.value = true
  try {
    const data = await adminApi.listUsers({
      keyword: query.keyword || undefined,
      status: query.status,
      created_from: query.dateRange[0] ? toDateParam(query.dateRange[0]) : undefined,
      created_to: query.dateRange[1] ? toDateParam(query.dateRange[1], true) : undefined,
      page: query.page,
      page_size: query.page_size,
    })
    users.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  loadUsers()
}

function handlePageChange(page: number) {
  query.page = page
  loadUsers()
}

function handleSizeChange(size: number) {
  query.page_size = size
  query.page = 1
  loadUsers()
}

async function toggleStatus(row: AdminUserListItem) {
  const next = row.status === 1 ? 0 : 1
  const action = next === 0 ? '禁用' : '启用'
  await ElMessageBox.confirm(`确定要${action}用户「${row.username}」吗？`, '二次确认', {
    type: 'warning',
    confirmButtonText: action,
  })
  await adminApi.setUserStatus(row.id, next)
  ElMessage.success(`${action}成功`)
  loadUsers()
}

async function resetPassword(row: AdminUserListItem) {
  const { value } = await ElMessageBox.prompt('请输入新密码（至少6位）', '重置密码', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputPattern: /.{6,}/,
    inputErrorMessage: '密码至少6位',
  })
  await adminApi.resetUserPassword(row.id, value)
  ElMessage.success('密码已重置')
}

function viewDetail(row: AdminUserListItem) {
  router.push(`/admin/users/${row.id}`)
}

function onSelectionChange(rows: AdminUserListItem[]) {
  selectedIds.value = rows.map((r) => r.id)
}

async function batchStatus(status: number, label: string) {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先选择用户')
    return
  }
  await ElMessageBox.confirm(`确定批量${label} ${selectedIds.value.length} 个用户吗？`, '二次确认', { type: 'warning' })
  const res = await adminApi.batchUserStatus(selectedIds.value, status)
  ElMessage.success(`已${label} ${res.updated} 个用户`)
  selectedIds.value = []
  loadUsers()
}

/* ---------------- 密码重置队列（并入本页，管理端只保留一套） ---------------- */
interface ResetItem {
  id: string
  username: string
  status: string
  createdAt?: string
  note?: string
}
const resetVisible = ref(false)
const resetLoading = ref(false)
const resetItems = ref<ResetItem[]>([])

async function loadResets() {
  resetLoading.value = true
  try {
    const resp = await fetch('/admin-api/password-resets?status=pending', {
      credentials: 'same-origin',
    })
    const payload = await resp.json().catch(() => ({ code: 1, message: '返回格式异常' }))
    if (!resp.ok || payload.code !== 0) {
      throw new Error(payload.message || '获取重置申请失败')
    }
    resetItems.value = (payload.data?.items || []) as ResetItem[]
  } catch (e) {
    resetItems.value = []
    ElMessage.error(e instanceof Error ? e.message : '获取重置申请失败')
  } finally {
    resetLoading.value = false
  }
}

async function resolveReset(id: string, action: 'approve' | 'reject') {
  try {
    const resp = await fetch(`/admin-api/password-resets/${encodeURIComponent(id)}/resolve`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    })
    const payload = await resp.json().catch(() => ({ code: 1, message: '返回格式异常' }))
    if (!resp.ok || payload.code !== 0) {
      throw new Error(payload.message || '处理失败')
    }
    ElMessage.success(action === 'approve' ? '已通过并重置密码' : '已驳回')
    await loadResets()
    loadUsers()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '处理失败')
  }
}

function openResets() {
  resetVisible.value = true
  void loadResets()
}

onMounted(() => {
  loadUsers()
  if (route.query.resets === '1') {
    openResets()
  }
})
</script>

<template>
  <div class="page-container">
    <AdminPageHero module="users" />
    <div class="card table-wrap">
      <div class="toolbar">
        <h3>学生用户管理</h3>
        <div class="toolbar-right">
          <el-button plain @click="openResets">
            密码重置队列
            <el-badge v-if="resetItems.length" :value="resetItems.length" style="margin-left: 6px" />
          </el-button>
          <el-date-picker
            v-model="query.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="注册起"
            end-placeholder="注册止"
            value-format="YYYY-MM-DD"
            style="width: 260px"
            @change="handleSearch"
          />
          <el-select
            v-model="query.status"
            placeholder="账号状态"
            clearable
            style="width: 120px"
            @change="handleSearch"
          >
            <el-option label="正常" :value="1" />
            <el-option label="禁用" :value="0" />
          </el-select>
          <el-input
            v-model="query.keyword"
            placeholder="用户名 / 姓名"
            style="width: 220px"
            clearable
            @keyup.enter="handleSearch"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
        </div>
      </div>

      <div v-if="hasPerm('btn:user:batch') && selectedIds.length" class="batch-bar">
        <span>已选 {{ selectedIds.length }} 项</span>
        <el-button size="small" type="danger" @click="batchStatus(0, '禁用')">批量禁用</el-button>
        <el-button size="small" type="success" @click="batchStatus(1, '启用')">批量启用</el-button>
      </div>

      <el-table v-loading="loading" :data="users" stripe @selection-change="onSelectionChange">
        <el-table-column v-if="hasPerm('btn:user:batch')" type="selection" width="45" />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="账号" min-width="120" />
        <el-table-column label="姓名" min-width="100">
          <template #default="{ row }">{{ row.real_name || row.nickname || '-' }}</template>
        </el-table-column>
        <el-table-column prop="major" label="专业" min-width="120" show-overflow-tooltip />
        <el-table-column label="画像完整度" width="140">
          <template #default="{ row }">
            <el-progress
              v-if="row.profile_completeness != null"
              :percentage="Math.round(row.profile_completeness * 100)"
              :stroke-width="8"
            />
            <span v-else class="muted">未构建</span>
          </template>
        </el-table-column>
        <el-table-column label="注册时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="最后登录" width="170">
          <template #default="{ row }">{{ formatDateTime(row.last_login_at) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <div class="action-row">
              <el-button size="small" type="primary" @click="viewDetail(row)">详情</el-button>
              <el-button
                v-if="hasPerm('btn:user:disable')"
                size="small"
                :type="row.status === 1 ? 'danger' : 'success'"
                @click="toggleStatus(row)"
              >
                {{ row.status === 1 ? '禁用' : '启用' }}
              </el-button>
              <el-button
                v-if="hasPerm('btn:user:reset_password')"
                size="small"
                type="warning"
                @click="resetPassword(row)"
              >
                重置密码
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </div>

    <el-dialog v-model="resetVisible" title="密码重置申请" width="620px">
      <div v-loading="resetLoading">
        <el-empty v-if="!resetLoading && !resetItems.length" description="暂无待处理的重置申请" />
        <div v-for="it in resetItems" :key="it.id" class="reset-row">
          <div class="reset-main">
            <strong>{{ it.username }}</strong>
            <span class="reset-meta">{{ it.createdAt || '—' }}<template v-if="it.note"> · {{ it.note }}</template></span>
          </div>
          <div class="reset-actions">
            <el-button size="small" type="primary" @click="resolveReset(it.id, 'approve')">通过并重置</el-button>
            <el-button size="small" @click="resolveReset(it.id, 'reject')">驳回</el-button>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.reset-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid $border-color;

  &:last-child { border-bottom: none; }

  .reset-main { display: flex; flex-direction: column; gap: 3px; }
  .reset-meta { font-size: 12px; color: $text-secondary; }
  .reset-actions { display: flex; gap: 8px; }
}

.table-wrap { padding: 24px; }
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}
.toolbar-right { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.pagination { margin-top: 20px; display: flex; justify-content: flex-end; }
.batch-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: #f8fafc;
  border-radius: 6px;
  font-size: 13px;
}
.muted { color: $text-secondary; font-size: 13px; }
.action-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
  white-space: nowrap;
}
</style>
