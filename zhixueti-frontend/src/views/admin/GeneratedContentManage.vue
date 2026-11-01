<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminContentApi, type AdminImageItem, type AdminLectureItem } from '@/api/adminContent'
import { hasPerm } from '@/utils/permission'
import AdminContentPreview, { type PreviewPayload } from '@/components/admin/AdminContentPreview.vue'
import AdminPageHero from '@/components/admin/AdminPageHero.vue'

const activeTab = ref('lectures')
const loading = ref(false)
const lectures = ref<AdminLectureItem[]>([])
const images = ref<AdminImageItem[]>([])
const lectureTotal = ref(0)
const imageTotal = ref(0)

const previewVisible = ref(false)
const previewLoading = ref(false)
const previewError = ref('')
const previewPayload = ref<PreviewPayload | null>(null)
const previewTitle = ref('')
let previewLectureRow: AdminLectureItem | null = null

const query = reactive({ keyword: '', page: 1, page_size: 15 })

async function loadLectures() {
  loading.value = true
  try {
    const data = await adminContentApi.listLectures({
      keyword: query.keyword || undefined,
      page: query.page,
      page_size: query.page_size,
    })
    lectures.value = data.items
    lectureTotal.value = data.total
  } finally {
    loading.value = false
  }
}

async function loadImages() {
  loading.value = true
  try {
    const data = await adminContentApi.listImages({
      keyword: query.keyword || undefined,
      page: query.page,
      page_size: query.page_size,
    })
    images.value = data.items
    imageTotal.value = data.total
  } finally {
    loading.value = false
  }
}

function search() {
  query.page = 1
  if (activeTab.value === 'lectures') loadLectures()
  else loadImages()
}

async function deleteLecture(row: AdminLectureItem) {
  await ElMessageBox.confirm(`确定删除讲解「${row.title}」吗？`, '二次确认', { type: 'warning' })
  await adminContentApi.deleteLecture(row.session_id, row.lecture_id)
  ElMessage.success('已删除')
  loadLectures()
}

async function deleteImage(row: AdminImageItem) {
  await ElMessageBox.confirm(`确定删除图像「${row.title}」吗？`, '二次确认', { type: 'warning' })
  await adminContentApi.deleteImage(row.session_id, row.round_no)
  ElMessage.success('已删除')
  loadImages()
}

async function viewLecture(row: AdminLectureItem) {
  previewLectureRow = row
  previewVisible.value = true
  previewLoading.value = true
  previewError.value = ''
  previewPayload.value = null
  previewTitle.value = row.title
  try {
    const data = await adminContentApi.previewLecture(row.session_id, row.lecture_id)
    previewPayload.value = { kind: 'lecture', data }
  } catch (e: unknown) {
    previewError.value = (e as Error)?.message || '讲解内容加载失败'
  } finally {
    previewLoading.value = false
  }
}

function retryPreview() {
  if (previewLectureRow) viewLecture(previewLectureRow)
}

onMounted(loadLectures)
</script>

<template>
  <div class="page-container">
    <AdminPageHero module="generated" />
    <div class="card table-wrap">
      <div class="toolbar">
        <h3>多模态生成内容</h3>
        <div class="toolbar-right">
          <el-input v-model="query.keyword" placeholder="关键词" style="width: 200px" clearable @keyup.enter="search">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button type="primary" @click="search">搜索</el-button>
        </div>
      </div>
      <el-tabs v-model="activeTab" @tab-change="(n: string) => { query.page = 1; n === 'lectures' ? loadLectures() : loadImages() }">
        <el-tab-pane label="视频讲解" name="lectures">
          <el-table v-loading="loading" :data="lectures" stripe>
            <el-table-column prop="title" label="标题" min-width="180" />
            <el-table-column prop="username" label="用户" width="100" />
            <el-table-column prop="slide_count" label="幻灯片" width="80" />
            <el-table-column prop="topic" label="主题" min-width="120" show-overflow-tooltip />
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <div class="action-row">
                  <el-button size="small" type="primary" @click="viewLecture(row)">查看视频</el-button>
                  <el-button v-if="hasPerm('btn:content:delete')" size="small" type="danger" @click="deleteLecture(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination v-model:current-page="query.page" :total="lectureTotal" :page-size="query.page_size" layout="total, prev, pager, next" style="margin-top:12px" @current-change="loadLectures" />
        </el-tab-pane>
        <el-tab-pane label="知识点图像" name="images">
          <el-table v-loading="loading" :data="images" stripe>
            <el-table-column prop="title" label="标题" min-width="160" />
            <el-table-column prop="username" label="用户" width="100" />
            <el-table-column prop="caption" label="说明" min-width="180" show-overflow-tooltip />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button v-if="hasPerm('btn:content:delete')" size="small" type="danger" @click="deleteImage(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination v-model:current-page="query.page" :total="imageTotal" :page-size="query.page_size" layout="total, prev, pager, next" style="margin-top:12px" @current-change="loadImages" />
        </el-tab-pane>
      </el-tabs>
    </div>

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
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.toolbar-right { display: flex; gap: 8px; }
</style>
