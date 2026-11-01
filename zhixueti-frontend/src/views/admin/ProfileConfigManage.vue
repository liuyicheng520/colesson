<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminContentApi, type AdminProfileDimension, type AdminProfileTag } from '@/api/adminContent'
import { hasPerm } from '@/utils/permission'
import AdminPageHero from '@/components/admin/AdminPageHero.vue'

const activeTab = ref('dimensions')
const loading = ref(false)
const dimensions = ref<AdminProfileDimension[]>([])
const tags = ref<AdminProfileTag[]>([])

const dimDialog = ref(false)
const dimForm = reactive({
  id: 0,
  dimension_code: '',
  dimension_name: '',
  dimension_desc: '',
  sort_order: 0,
  weight: 1,
  is_required: 1,
  guide_questions: [''] as string[],
})

const tagDialog = ref(false)
const tagForm = reactive({ code: '', label: '', category: 'general', status: 1 })

async function loadDimensions() {
  loading.value = true
  try {
    dimensions.value = await adminContentApi.listDimensions()
  } finally {
    loading.value = false
  }
}

async function loadTags() {
  tags.value = await adminContentApi.listTags()
}

function openEditDim(row: AdminProfileDimension) {
  dimForm.id = row.id
  dimForm.dimension_code = row.dimension_code
  dimForm.dimension_name = row.dimension_name
  dimForm.dimension_desc = row.dimension_desc || ''
  dimForm.sort_order = row.sort_order
  dimForm.weight = row.weight
  dimForm.is_required = row.is_required
  dimForm.guide_questions = [
    (row.guide_questions?.length ? row.guide_questions.join('\n') : '') || '',
  ]
  dimDialog.value = true
}

async function saveDim() {
  await adminContentApi.updateDimension(dimForm.id, {
    dimension_name: dimForm.dimension_name,
    dimension_desc: dimForm.dimension_desc,
    sort_order: dimForm.sort_order,
    weight: dimForm.weight,
    is_required: dimForm.is_required,
    guide_questions: dimForm.guide_questions.filter(Boolean),
  })
  ElMessage.success('维度已保存')
  dimDialog.value = false
  loadDimensions()
}

async function disableDim(row: AdminProfileDimension) {
  await ElMessageBox.confirm(`确定禁用维度「${row.dimension_name}」吗？`, '二次确认', { type: 'warning' })
  await adminContentApi.deleteDimension(row.id)
  ElMessage.success('已禁用')
  loadDimensions()
}

function openTagDialog(row?: AdminProfileTag) {
  if (row) Object.assign(tagForm, row)
  else Object.assign(tagForm, { code: '', label: '', category: 'general', status: 1 })
  tagDialog.value = true
}

async function saveTag() {
  await adminContentApi.upsertTag({ ...tagForm })
  ElMessage.success('标签已保存')
  tagDialog.value = false
  loadTags()
}

async function removeTag(code: string) {
  await ElMessageBox.confirm('确定删除该标签吗？', '二次确认', { type: 'warning' })
  tags.value = await adminContentApi.deleteTag(code)
  ElMessage.success('已删除')
}

onMounted(() => {
  loadDimensions()
  loadTags()
})
</script>

<template>
  <div class="page-container">
    <AdminPageHero module="profile" />
    <div class="card table-wrap">
      <h3>画像体系配置</h3>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="画像维度" name="dimensions">
          <el-table v-loading="loading" :data="dimensions" stripe>
            <el-table-column prop="sort_order" label="排序" width="70" />
            <el-table-column prop="dimension_code" label="编码" width="80" />
            <el-table-column prop="dimension_name" label="名称" min-width="120" />
            <el-table-column label="问题指引" min-width="200">
              <template #default="{ row }">{{ row.guide_questions?.[0]?.slice(0, 40) || '—' }}{{ (row.guide_questions?.[0]?.length || 0) > 40 ? '…' : '' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">{{ row.status === 1 ? '启用' : '禁用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <div class="action-row">
                  <el-button v-if="hasPerm('btn:profile-config:edit')" size="small" type="primary" @click="openEditDim(row)">编辑</el-button>
                  <el-button v-if="hasPerm('btn:profile-config:edit') && row.status === 1" size="small" type="danger" @click="disableDim(row)">禁用</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="标签库" name="tags">
          <div class="tag-toolbar">
            <el-button v-if="hasPerm('btn:profile-config:edit')" type="primary" size="small" @click="openTagDialog()">新增标签</el-button>
          </div>
          <el-table :data="tags" stripe>
            <el-table-column prop="code" label="编码" width="120" />
            <el-table-column prop="label" label="名称" min-width="140" />
            <el-table-column prop="category" label="分类" width="120" />
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <div class="action-row">
                  <el-button v-if="hasPerm('btn:profile-config:edit')" size="small" type="primary" @click="openTagDialog(row)">编辑</el-button>
                  <el-button v-if="hasPerm('btn:profile-config:edit')" size="small" type="danger" @click="removeTag(row.code)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="dimDialog" title="编辑画像维度" width="560px">
      <el-form label-width="100px">
        <el-form-item label="编码"><el-input :model-value="dimForm.dimension_code" disabled /></el-form-item>
        <el-form-item label="名称"><el-input v-model="dimForm.dimension_name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="dimForm.dimension_desc" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="dimForm.sort_order" :min="0" /></el-form-item>
        <el-form-item label="权重"><el-input-number v-model="dimForm.weight" :min="0" :max="10" :step="0.1" /></el-form-item>
        <el-form-item label="问题指引">
          <el-input
            v-model="dimForm.guide_questions[0]"
            type="textarea"
            :rows="4"
            placeholder="说明本维要采到什么信息（非既定问句），由大模型结合上文自由提问"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dimDialog = false">取消</el-button>
        <el-button type="primary" @click="saveDim">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="tagDialog" title="标签" width="420px">
      <el-form label-width="80px">
        <el-form-item label="编码"><el-input v-model="tagForm.code" :disabled="!!tagForm.code && tags.some(t => t.code === tagForm.code)" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="tagForm.label" /></el-form-item>
        <el-form-item label="分类"><el-input v-model="tagForm.category" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="tagDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTag">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.table-wrap { padding: 24px; h3 { margin-bottom: 16px; } }
.tag-toolbar { margin-bottom: 12px; }
</style>
