<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, type AdminUserDetail } from '@/api/admin'
import { hasPerm, formatDateTime } from '@/utils/permission'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const detail = ref<AdminUserDetail | null>(null)

const userId = computed(() => Number(route.params.id))

const profileDimensions = [
  { code: 'D1', name: '知识基础' },
  { code: 'D2', name: '认知风格' },
  { code: 'D3', name: '学习目标' },
  { code: 'D4', name: '学习历史' },
  { code: 'D5', name: '易错点偏好' },
  { code: 'D6', name: '学习节奏' },
  { code: 'D7', name: '模态偏好' },
  { code: 'D8', name: '专业背景' },
]

const profileEditVisible = ref(false)
const editDimensionCode = ref('D1')
const editDimensionValue = ref('{}')

async function loadDetail() {
  loading.value = true
  try {
    detail.value = await adminApi.getUser(userId.value)
  } catch {
    router.replace('/admin/users')
  } finally {
    loading.value = false
  }
}

async function toggleStatus() {
  if (!detail.value) return
  const next = detail.value.status === 1 ? 0 : 1
  const action = next === 0 ? '禁用' : '启用'
  await ElMessageBox.confirm(`确定要${action}该用户吗？`, '二次确认', { type: 'warning' })
  await adminApi.setUserStatus(detail.value.id, next)
  ElMessage.success(`${action}成功`)
  loadDetail()
}

async function resetPassword() {
  if (!detail.value) return
  const { value } = await ElMessageBox.prompt('请输入新密码（至少6位）', '重置密码', {
    inputPattern: /.{6,}/,
    inputErrorMessage: '密码至少6位',
  })
  await adminApi.resetUserPassword(detail.value.id, value)
  ElMessage.success('密码已重置')
}

function openProfileEdit() {
  editDimensionCode.value = 'D1'
  editDimensionValue.value = '{}'
  profileEditVisible.value = true
}

async function submitProfileEdit() {
  if (!detail.value) return
  let parsed: Record<string, unknown>
  try {
    parsed = JSON.parse(editDimensionValue.value)
  } catch {
    ElMessage.error('维度值必须是合法 JSON')
    return
  }
  await adminApi.patchUserProfile(detail.value.id, editDimensionCode.value, parsed)
  ElMessage.success('画像维度已更新')
  profileEditVisible.value = false
  loadDetail()
}

function sessionStatusLabel(status: number): string {
  return status === 0 ? '进行中' : '已结束'
}

function sessionStatusType(status: number): 'success' | 'info' {
  return status === 0 ? 'success' : 'info'
}

onMounted(loadDetail)
</script>

<template>
  <div v-loading="loading" class="page-container">
    <div class="page-header">
      <el-button text @click="router.push('/admin/users')">← 返回列表</el-button>
      <div v-if="detail" class="actions">
        <el-button
          v-if="hasPerm('btn:user:disable')"
          :type="detail.status === 1 ? 'danger' : 'success'"
          @click="toggleStatus"
        >
          {{ detail.status === 1 ? '禁用账号' : '启用账号' }}
        </el-button>
        <el-button v-if="hasPerm('btn:user:reset_password')" @click="resetPassword">
          重置密码
        </el-button>
        <el-button v-if="hasPerm('btn:user:edit_profile')" type="primary" @click="openProfileEdit">
          修正画像
        </el-button>
      </div>
    </div>

    <template v-if="detail">
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="card section">
            <h3>基础信息</h3>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="用户名">{{ detail.username }}</el-descriptions-item>
              <el-descriptions-item label="昵称">{{ detail.nickname }}</el-descriptions-item>
              <el-descriptions-item label="真实姓名">{{ detail.real_name || '-' }}</el-descriptions-item>
              <el-descriptions-item label="学号">{{ detail.student_no || '-' }}</el-descriptions-item>
              <el-descriptions-item label="专业">{{ detail.major || '-' }}</el-descriptions-item>
              <el-descriptions-item label="年级">{{ detail.grade ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="邮箱">{{ detail.email || '-' }}</el-descriptions-item>
              <el-descriptions-item label="手机">{{ detail.phone || '-' }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="detail.status === 1 ? 'success' : 'danger'" size="small">
                  {{ detail.status === 1 ? '正常' : '禁用' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="注册时间">{{ formatDateTime(detail.created_at) }}</el-descriptions-item>
              <el-descriptions-item label="最后登录">{{ formatDateTime(detail.last_login_at) }}</el-descriptions-item>
              <el-descriptions-item label="登录 IP">{{ detail.last_login_ip || '-' }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </el-col>

        <el-col :span="12">
          <div class="card section">
            <h3>学习数据概览</h3>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="画像完整度">
                {{
                  detail.profile?.completeness != null
                    ? `${Math.round(Number(detail.profile.completeness) * 100)}%`
                    : '未构建'
                }}
              </el-descriptions-item>
              <el-descriptions-item label="答疑会话数">
                {{ detail.learning_stats?.tutor_sessions ?? 0 }}
              </el-descriptions-item>
            </el-descriptions>
            <div v-if="detail.profile?.dimensions" class="profile-block">
              <h4>画像维度快照</h4>
              <pre class="json-preview">{{ JSON.stringify(detail.profile.dimensions, null, 2) }}</pre>
            </div>
          </div>
        </el-col>
      </el-row>

      <div class="card section">
        <h3>最近答疑会话</h3>
        <el-table :data="detail.recent_tutor_sessions" stripe empty-text="暂无会话记录">
          <el-table-column prop="session_no" label="会话编号" min-width="180" />
          <el-table-column prop="topic" label="主题" min-width="200" show-overflow-tooltip />
          <el-table-column prop="total_rounds" label="轮次" width="80" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="sessionStatusType(row.status)">
                {{ sessionStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="更新时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
        </el-table>
      </div>
    </template>

    <el-dialog v-model="profileEditVisible" title="修正用户画像维度" width="520px">
      <el-form label-width="100px">
        <el-form-item label="维度">
          <el-select v-model="editDimensionCode" style="width: 100%">
            <el-option
              v-for="d in profileDimensions"
              :key="d.code"
              :label="`${d.code} · ${d.name}`"
              :value="d.code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="维度值 JSON">
          <el-input
            v-model="editDimensionValue"
            type="textarea"
            :rows="8"
            placeholder='例如 {"level":"intermediate","topics":["线性代数"]}'
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="profileEditVisible = false">取消</el-button>
        <el-button type="primary" @click="submitProfileEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.actions { display: flex; gap: 8px; }
.section {
  padding: 24px;
  margin-bottom: 20px;
  h3 { margin-bottom: 16px; font-size: 16px; }
  h4 { margin: 16px 0 8px; font-size: 14px; color: $text-secondary; }
}
.json-preview {
  background: #f8fafc;
  border: 1px solid $border-color;
  border-radius: 8px;
  padding: 12px;
  font-size: 12px;
  overflow: auto;
  max-height: 240px;
}
</style>
