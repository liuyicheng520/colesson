<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  adminApi,
  ADMIN_ROLE_OPTIONS,
  type AdminUserListItem,
} from '@/api/admin'
import { formatDateTime, formatRole, hasPerm } from '@/utils/permission'
import AdminPageHero from '@/components/admin/AdminPageHero.vue'

const loading = ref(false)
const admins = ref<AdminUserListItem[]>([])
const total = ref(0)

const query = reactive({
  keyword: '',
  page: 1,
  page_size: 20,
})

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editingId = ref<number | null>(null)
const form = reactive({
  username: '',
  password: '',
  nickname: '',
  real_name: '',
  role_code: 'ROLE_CONTENT_ADMIN',
  status: 1,
})

function resetForm() {
  form.username = ''
  form.password = ''
  form.nickname = ''
  form.real_name = ''
  form.role_code = 'ROLE_CONTENT_ADMIN'
  form.status = 1
  editingId.value = null
}

function openCreate() {
  resetForm()
  dialogMode.value = 'create'
  dialogVisible.value = true
}

function openEdit(row: AdminUserListItem) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  form.username = row.username
  form.password = ''
  form.nickname = row.nickname
  form.real_name = row.real_name || ''
  form.role_code = row.roles[0] || 'ROLE_CONTENT_ADMIN'
  form.status = row.status
  dialogVisible.value = true
}

async function loadAdmins() {
  loading.value = true
  try {
    const data = await adminApi.listAdmins({
      keyword: query.keyword || undefined,
      page: query.page,
      page_size: query.page_size,
    })
    admins.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  loadAdmins()
}

async function submitForm() {
  if (dialogMode.value === 'create') {
    if (!form.username || !form.password) {
      ElMessage.warning('请填写账号和密码')
      return
    }
    await adminApi.createAdmin({
      username: form.username,
      password: form.password,
      nickname: form.nickname || undefined,
      real_name: form.real_name || undefined,
      role_code: form.role_code,
    })
    ElMessage.success('管理员已创建')
  } else if (editingId.value) {
    await adminApi.updateAdmin(editingId.value, {
      nickname: form.nickname || undefined,
      real_name: form.real_name || undefined,
      role_code: form.role_code,
      status: form.status,
    })
    ElMessage.success('管理员已更新')
  }
  dialogVisible.value = false
  loadAdmins()
}

async function toggleStatus(row: AdminUserListItem) {
  const next = row.status === 1 ? 0 : 1
  const action = next === 0 ? '禁用' : '启用'
  await ElMessageBox.confirm(`确定要${action}管理员「${row.username}」吗？`, '二次确认', {
    type: 'warning',
  })
  await adminApi.updateAdmin(row.id, { status: next })
  ElMessage.success(`${action}成功`)
  loadAdmins()
}

onMounted(loadAdmins)
</script>

<template>
  <div class="page-container">
    <AdminPageHero module="admins" />
    <div class="card table-wrap">
      <div class="toolbar">
        <h3>管理员账号</h3>
        <div class="toolbar-right">
          <el-input
            v-model="query.keyword"
            placeholder="搜索账号 / 姓名"
            style="width: 220px"
            clearable
            @keyup.enter="handleSearch"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button v-if="hasPerm('btn:admin:create')" type="primary" plain @click="openCreate">
            新增管理员
          </el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="admins" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="账号" min-width="120" />
        <el-table-column label="姓名" min-width="100">
          <template #default="{ row }">{{ row.real_name || row.nickname || '-' }}</template>
        </el-table-column>
        <el-table-column label="角色" min-width="130">
          <template #default="{ row }">
            <el-tag v-for="r in row.roles" :key="r" size="small" style="margin-right: 4px">
              {{ formatRole(r) }}
            </el-tag>
          </template>
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
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-if="hasPerm('btn:admin:edit')" text type="primary" @click="openEdit(row)">
              编辑
            </el-button>
            <el-button
              v-if="hasPerm('btn:admin:disable')"
              text
              :type="row.status === 1 ? 'danger' : 'success'"
              @click="toggleStatus(row)"
            >
              {{ row.status === 1 ? '禁用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="(p: number) => { query.page = p; loadAdmins() }"
          @size-change="(s: number) => { query.page_size = s; query.page = 1; loadAdmins() }"
        />
      </div>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新增管理员' : '编辑管理员'"
      width="480px"
    >
      <el-form label-width="90px">
        <el-form-item label="账号" required>
          <el-input v-model="form.username" :disabled="dialogMode === 'edit'" />
        </el-form-item>
        <el-form-item v-if="dialogMode === 'create'" label="密码" required>
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="form.nickname" />
        </el-form-item>
        <el-form-item label="真实姓名">
          <el-input v-model="form.real_name" />
        </el-form-item>
        <el-form-item label="角色" required>
          <el-select v-model="form.role_code" style="width: 100%">
            <el-option
              v-for="r in ADMIN_ROLE_OPTIONS"
              :key="r.code"
              :label="r.label"
              :value="r.code"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="dialogMode === 'edit'" label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
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
</style>
