<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  adminContentApi,
  type AdminKnowledgePoint,
  type AdminPathDetail,
  type AdminPathItem,
} from '@/api/adminContent'
import { hasPerm } from '@/utils/permission'
import AdminPageHero from '@/components/admin/AdminPageHero.vue'

const activeTab = ref('paths')
const pathLoading = ref(false)
const kpLoading = ref(false)
const paths = ref<AdminPathItem[]>([])
const pathTotal = ref(0)
const knowledgePoints = ref<AdminKnowledgePoint[]>([])
const pathDetail = ref<AdminPathDetail | null>(null)
const detailVisible = ref(false)

const pathQuery = reactive({ keyword: '', page: 1, page_size: 15 })

const kpDialog = ref(false)
const kpForm = reactive({
  id: 0,
  point_code: '',
  point_name: '',
  domain: 'machine_learning',
  difficulty: 3,
  estimated_min: 30,
  description: '',
})

async function loadPaths() {
  pathLoading.value = true
  try {
    const data = await adminContentApi.listPaths({
      keyword: pathQuery.keyword || undefined,
      page: pathQuery.page,
      page_size: pathQuery.page_size,
    })
    paths.value = data.items
    pathTotal.value = data.total
  } finally {
    pathLoading.value = false
  }
}

async function loadKnowledgePoints() {
  kpLoading.value = true
  try {
    knowledgePoints.value = await adminContentApi.listKnowledgePoints()
  } finally {
    kpLoading.value = false
  }
}

async function viewPath(row: AdminPathItem) {
  pathDetail.value = await adminContentApi.getPath(row.id)
  detailVisible.value = true
}

function openKpDialog(row?: AdminKnowledgePoint) {
  if (row) Object.assign(kpForm, row)
  else Object.assign(kpForm, { id: 0, point_code: '', point_name: '', domain: 'machine_learning', difficulty: 3, estimated_min: 30, description: '' })
  kpDialog.value = true
}

async function saveKp() {
  if (kpForm.id) {
    await adminContentApi.updateKnowledgePoint(kpForm.id, {
      point_name: kpForm.point_name,
      domain: kpForm.domain,
      difficulty: kpForm.difficulty,
      estimated_min: kpForm.estimated_min,
      description: kpForm.description,
    })
  } else {
    await adminContentApi.createKnowledgePoint({
      point_code: kpForm.point_code,
      point_name: kpForm.point_name,
      domain: kpForm.domain,
      difficulty: kpForm.difficulty,
      estimated_min: kpForm.estimated_min,
      description: kpForm.description,
    })
  }
  ElMessage.success('知识点已保存')
  kpDialog.value = false
  loadKnowledgePoints()
}

async function disableKp(row: AdminKnowledgePoint) {
  await ElMessageBox.confirm(`确定禁用「${row.point_name}」吗？`, '二次确认', { type: 'warning' })
  await adminContentApi.deleteKnowledgePoint(row.id)
  ElMessage.success('已禁用')
  loadKnowledgePoints()
}

onMounted(() => {
  loadPaths()
  loadKnowledgePoints()
})
</script>

<template>
  <div class="page-container">
    <AdminPageHero module="paths" />
    <div class="card table-wrap">
      <h3>学习路径与知识点</h3>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="用户学习路径" name="paths">
          <el-table v-loading="pathLoading" :data="paths" stripe>
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="title" label="路径标题" min-width="160" />
            <el-table-column prop="username" label="用户" width="100" />
            <el-table-column prop="total_nodes" label="节点数" width="80" />
            <el-table-column prop="goal" label="目标" min-width="180" show-overflow-tooltip />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="viewPath(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-model:current-page="pathQuery.page"
            :total="pathTotal"
            :page-size="pathQuery.page_size"
            layout="total, prev, pager, next"
            style="margin-top: 12px"
            @current-change="loadPaths"
          />
        </el-tab-pane>
        <el-tab-pane label="知识点库" name="knowledge">
          <div class="toolbar">
            <el-button v-if="hasPerm('btn:path:edit')" type="primary" size="small" @click="openKpDialog()">新增知识点</el-button>
          </div>
          <el-table v-loading="kpLoading" :data="knowledgePoints" stripe>
            <el-table-column prop="point_code" label="编码" width="100" />
            <el-table-column prop="point_name" label="名称" min-width="140" />
            <el-table-column prop="domain" label="领域" width="140" />
            <el-table-column prop="difficulty" label="难度" width="70" />
            <el-table-column prop="estimated_min" label="预估分钟" width="100" />
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <div class="action-row">
                  <el-button v-if="hasPerm('btn:path:edit')" size="small" type="primary" @click="openKpDialog(row)">编辑</el-button>
                  <el-button v-if="hasPerm('btn:path:edit') && row.status === 1" size="small" type="danger" @click="disableKp(row)">禁用</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="detailVisible" title="路径详情" width="720px">
      <template v-if="pathDetail">
        <p><strong>目标：</strong>{{ pathDetail.goal }}</p>
        <el-table :data="pathDetail.nodes" size="small" stripe max-height="360">
          <el-table-column prop="sort_order" label="#" width="50" />
          <el-table-column prop="node_name" label="节点" min-width="160" />
          <el-table-column prop="node_type" label="类型" width="80" />
          <el-table-column prop="estimated_min" label="分钟" width="70" />
        </el-table>
      </template>
    </el-dialog>

    <el-dialog v-model="kpDialog" :title="kpForm.id ? '编辑知识点' : '新增知识点'" width="480px">
      <el-form label-width="90px">
        <el-form-item label="编码"><el-input v-model="kpForm.point_code" :disabled="!!kpForm.id" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="kpForm.point_name" /></el-form-item>
        <el-form-item label="领域"><el-input v-model="kpForm.domain" /></el-form-item>
        <el-form-item label="难度"><el-input-number v-model="kpForm.difficulty" :min="1" :max="5" /></el-form-item>
        <el-form-item label="预估分钟"><el-input-number v-model="kpForm.estimated_min" :min="5" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="kpForm.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="kpDialog = false">取消</el-button>
        <el-button type="primary" @click="saveKp">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.table-wrap { padding: 24px; h3 { margin-bottom: 16px; } }
.toolbar { margin-bottom: 12px; }
</style>
