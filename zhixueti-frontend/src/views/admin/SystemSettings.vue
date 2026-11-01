<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  adminOpsApi,
  type AnnouncementItem,
  type FeedbackItem,
  type SystemSettings,
} from '@/api/adminOps'
import { hasPerm } from '@/utils/permission'
import { formatBeijingDateTime } from '@/utils/datetime'
import AdminPageHero from '@/components/admin/AdminPageHero.vue'

const activeTab = ref('llm')
const loading = ref(false)
const saving = ref(false)
const settings = ref<SystemSettings | null>(null)

const llmForm = reactive({
  llm_default_provider: 'mock',
  llm_fallback_provider: 'mock',
  content_safety_enabled: true,
  profile_min_completeness: 0.8,
  rate_limit_requests: 100,
  tutor_max_tokens: 2048,
  tutor_stream_timeout_sec: 60,
  qwen_api_key: '',
  deepseek_api_key: '',
  spark_api_key: '',
  spark_api_secret: '',
  serper_api_key: '',
})

const featureForm = reactive({
  feature_web_search: true,
  feature_deep_mode: true,
  feature_image_gen: true,
  feature_video_lecture: true,
  feature_voice_input: true,
})

const siteForm = reactive({
  site_name: '',
  site_logo_url: '',
  site_icp_no: '',
  site_footer_text: '',
})

const llmProviders = [
  { label: 'Mock (开发)', value: 'mock' },
  { label: '通义千问', value: 'qwen' },
  { label: 'DeepSeek', value: 'deepseek' },
  { label: '讯飞星火', value: 'spark' },
]

const announcements = ref<AnnouncementItem[]>([])
const annDialog = ref(false)
const annForm = reactive({ id: 0, title: '', content: '', status: 1, priority: 0 })

const feedbackList = ref<FeedbackItem[]>([])
const feedbackTotal = ref(0)
const feedbackPage = ref(1)
const feedbackStatus = ref<number | undefined>(undefined)
const replyDialog = ref(false)
const replyForm = reactive({ id: 0, title: '', content: '', status: 1, admin_reply: '' })

const canEdit = () => hasPerm('btn:settings:edit')

function fillForms(s: SystemSettings) {
  llmForm.llm_default_provider = s.llm_default_provider
  llmForm.llm_fallback_provider = s.llm_fallback_provider
  llmForm.content_safety_enabled = s.content_safety_enabled
  llmForm.profile_min_completeness = s.profile_min_completeness
  llmForm.rate_limit_requests = s.rate_limit_requests
  llmForm.tutor_max_tokens = s.tutor_max_tokens
  llmForm.tutor_stream_timeout_sec = s.tutor_stream_timeout_sec
  llmForm.qwen_api_key = ''
  llmForm.deepseek_api_key = ''
  llmForm.spark_api_key = ''
  llmForm.spark_api_secret = ''
  llmForm.serper_api_key = ''
  Object.assign(featureForm, {
    feature_web_search: s.feature_web_search,
    feature_deep_mode: s.feature_deep_mode,
    feature_image_gen: s.feature_image_gen,
    feature_video_lecture: s.feature_video_lecture,
    feature_voice_input: s.feature_voice_input,
  })
  siteForm.site_name = s.site_name
  siteForm.site_logo_url = s.site_logo_url
  siteForm.site_icp_no = s.site_icp_no
  siteForm.site_footer_text = s.site_footer_text
}

async function loadSettings() {
  loading.value = true
  try {
    settings.value = await adminOpsApi.getSystemSettings()
    fillForms(settings.value)
  } finally {
    loading.value = false
  }
}

async function saveLlm() {
  if (!canEdit()) return
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      llm_default_provider: llmForm.llm_default_provider,
      llm_fallback_provider: llmForm.llm_fallback_provider,
      content_safety_enabled: llmForm.content_safety_enabled,
      profile_min_completeness: llmForm.profile_min_completeness,
      rate_limit_requests: llmForm.rate_limit_requests,
      tutor_max_tokens: llmForm.tutor_max_tokens,
      tutor_stream_timeout_sec: llmForm.tutor_stream_timeout_sec,
    }
    if (llmForm.qwen_api_key) payload.qwen_api_key = llmForm.qwen_api_key
    if (llmForm.deepseek_api_key) payload.deepseek_api_key = llmForm.deepseek_api_key
    if (llmForm.spark_api_key) payload.spark_api_key = llmForm.spark_api_key
    if (llmForm.spark_api_secret) payload.spark_api_secret = llmForm.spark_api_secret
    if (llmForm.serper_api_key) payload.serper_api_key = llmForm.serper_api_key
    settings.value = await adminOpsApi.updateSystemSettings(payload)
    fillForms(settings.value!)
    ElMessage.success('系统参数已保存')
  } finally {
    saving.value = false
  }
}

async function saveFeatures() {
  if (!canEdit()) return
  saving.value = true
  try {
    settings.value = await adminOpsApi.updateSystemSettings({ ...featureForm })
    ElMessage.success('功能开关已保存')
  } finally {
    saving.value = false
  }
}

async function saveSite() {
  if (!canEdit()) return
  saving.value = true
  try {
    settings.value = await adminOpsApi.updateSystemSettings({ ...siteForm })
    ElMessage.success('站点信息已保存')
  } finally {
    saving.value = false
  }
}

async function loadAnnouncements() {
  announcements.value = await adminOpsApi.listAnnouncements()
}

function openAnnDialog(row?: AnnouncementItem) {
  if (row) Object.assign(annForm, row)
  else Object.assign(annForm, { id: 0, title: '', content: '', status: 1, priority: 0 })
  annDialog.value = true
}

async function saveAnnouncement() {
  if (!canEdit()) return
  if (!annForm.title.trim() || !annForm.content.trim()) {
    ElMessage.warning('请填写标题和内容')
    return
  }
  if (annForm.id) {
    await adminOpsApi.updateAnnouncement(annForm.id, {
      title: annForm.title,
      content: annForm.content,
      status: annForm.status,
      priority: annForm.priority,
    })
    ElMessage.success('公告已更新')
  } else {
    await adminOpsApi.createAnnouncement({
      title: annForm.title,
      content: annForm.content,
      status: annForm.status,
      priority: annForm.priority,
    })
    ElMessage.success('公告已发布')
  }
  annDialog.value = false
  loadAnnouncements()
}

async function removeAnnouncement(row: AnnouncementItem) {
  if (!canEdit()) return
  await ElMessageBox.confirm(`确定删除公告「${row.title}」吗？`, '二次确认', { type: 'warning' })
  await adminOpsApi.deleteAnnouncement(row.id)
  ElMessage.success('已删除')
  loadAnnouncements()
}

async function loadFeedback() {
  const res = await adminOpsApi.listFeedback({
    status: feedbackStatus.value,
    page: feedbackPage.value,
    page_size: 10,
  })
  feedbackList.value = res.items
  feedbackTotal.value = res.total
}

function openReply(row: FeedbackItem) {
  Object.assign(replyForm, {
    id: row.id,
    title: row.title,
    content: row.content,
    status: row.status === 0 ? 1 : row.status,
    admin_reply: row.admin_reply || '',
  })
  replyDialog.value = true
}

async function submitReply() {
  if (!canEdit()) return
  await adminOpsApi.replyFeedback(replyForm.id, {
    status: replyForm.status,
    admin_reply: replyForm.admin_reply || undefined,
  })
  ElMessage.success('回复已保存')
  replyDialog.value = false
  loadFeedback()
}

function statusLabel(s: number) {
  return ['待处理', '处理中', '已关闭'][s] ?? '未知'
}

function annStatusLabel(s: number) {
  return s === 1 ? '已发布' : '草稿'
}

onMounted(async () => {
  await loadSettings()
  await loadAnnouncements()
  await loadFeedback()
})
</script>

<template>
  <div v-loading="loading" class="page-container">
    <AdminPageHero module="settings" />
    <el-tabs v-model="activeTab">
      <el-tab-pane label="LLM 与参数" name="llm">
        <div class="card section">
          <el-form label-width="160px" :disabled="!canEdit()">
            <el-row :gutter="24">
              <el-col :xs="24" :lg="12">
                <el-form-item label="默认 LLM 提供商">
                  <el-select v-model="llmForm.llm_default_provider" style="width:100%">
                    <el-option v-for="p in llmProviders" :key="p.value" :label="p.label" :value="p.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="备用 LLM 提供商">
                  <el-select v-model="llmForm.llm_fallback_provider" style="width:100%">
                    <el-option v-for="p in llmProviders" :key="p.value" :label="p.label" :value="p.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="内容安全审核">
                  <el-switch v-model="llmForm.content_safety_enabled" />
                </el-form-item>
                <el-form-item label="画像完整度阈值">
                  <el-slider v-model="llmForm.profile_min_completeness" :min="0.5" :max="1" :step="0.05" show-input />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :lg="12">
                <el-form-item label="接口限流(次/分)">
                  <el-input-number v-model="llmForm.rate_limit_requests" :min="10" :max="5000" />
                </el-form-item>
                <el-form-item label="答疑最大 Token">
                  <el-input-number v-model="llmForm.tutor_max_tokens" :min="128" :max="8192" :step="128" />
                </el-form-item>
                <el-form-item label="流式超时(秒)">
                  <el-input-number v-model="llmForm.tutor_stream_timeout_sec" :min="10" :max="120" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-divider>API 密钥（留空则不修改）</el-divider>
            <el-row :gutter="24">
              <el-col :xs="24" :lg="12">
                <el-form-item label="通义千问 Key">
                  <el-input v-model="llmForm.qwen_api_key" type="password" show-password :placeholder="settings?.has_qwen_key ? '已配置 ****' : '未配置'" />
                </el-form-item>
                <el-form-item label="DeepSeek Key">
                  <el-input v-model="llmForm.deepseek_api_key" type="password" show-password :placeholder="settings?.has_deepseek_key ? '已配置 ****' : '未配置'" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :lg="12">
                <el-form-item label="讯飞星火 Key">
                  <el-input v-model="llmForm.spark_api_key" type="password" show-password :placeholder="settings?.has_spark_key ? '已配置 ****' : '未配置'" />
                </el-form-item>
                <el-form-item label="讯飞星火 Secret">
                  <el-input v-model="llmForm.spark_api_secret" type="password" show-password placeholder="与 Key 配套" />
                </el-form-item>
                <el-form-item label="Serper 搜索 Key">
                  <el-input v-model="llmForm.serper_api_key" type="password" show-password :placeholder="settings?.has_serper_key ? '已配置 ****' : '未配置'" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-button v-if="canEdit()" type="primary" :loading="saving" @click="saveLlm">保存参数</el-button>
          </el-form>
        </div>
      </el-tab-pane>

      <el-tab-pane label="功能开关" name="features">
        <div class="card section">
          <el-form label-width="160px" :disabled="!canEdit()">
            <el-form-item label="联网搜索">
              <el-switch v-model="featureForm.feature_web_search" />
            </el-form-item>
            <el-form-item label="深度模式">
              <el-switch v-model="featureForm.feature_deep_mode" />
            </el-form-item>
            <el-form-item label="图像生成">
              <el-switch v-model="featureForm.feature_image_gen" />
            </el-form-item>
            <el-form-item label="视频讲解">
              <el-switch v-model="featureForm.feature_video_lecture" />
            </el-form-item>
            <el-form-item label="语音输入/合成">
              <el-switch v-model="featureForm.feature_voice_input" />
            </el-form-item>
            <el-button v-if="canEdit()" type="primary" :loading="saving" @click="saveFeatures">保存开关</el-button>
          </el-form>
        </div>
      </el-tab-pane>

      <el-tab-pane label="站点信息" name="site">
        <div class="card section">
          <el-form label-width="120px" :disabled="!canEdit()">
            <el-form-item label="站点名称">
              <el-input v-model="siteForm.site_name" maxlength="64" />
            </el-form-item>
            <el-form-item label="Logo URL">
              <el-input v-model="siteForm.site_logo_url" placeholder="https://..." />
            </el-form-item>
            <el-form-item label="ICP 备案号">
              <el-input v-model="siteForm.site_icp_no" />
            </el-form-item>
            <el-form-item label="页脚文案">
              <el-input v-model="siteForm.site_footer_text" type="textarea" :rows="3" />
            </el-form-item>
            <el-button v-if="canEdit()" type="primary" :loading="saving" @click="saveSite">保存站点信息</el-button>
          </el-form>
        </div>
      </el-tab-pane>

      <el-tab-pane label="公告管理" name="announcements">
        <div class="card section">
          <div class="section-head">
            <h3>系统公告</h3>
            <el-button v-if="canEdit()" type="primary" @click="openAnnDialog()">新建公告</el-button>
          </div>
          <el-table :data="announcements" stripe empty-text="暂无公告">
            <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">{{ annStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="priority" label="优先级" width="80" />
            <el-table-column prop="created_at" label="创建时间" width="170">
              <template #default="{ row }">{{ formatBeijingDateTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column v-if="canEdit()" label="操作" width="140">
              <template #default="{ row }">
                <el-button text type="primary" @click="openAnnDialog(row)">编辑</el-button>
                <el-button text type="danger" @click="removeAnnouncement(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="反馈工单" name="feedback">
        <div class="card section">
          <div class="section-head">
            <h3>用户反馈</h3>
            <el-select v-model="feedbackStatus" clearable placeholder="全部状态" style="width:140px" @change="feedbackPage = 1; loadFeedback()">
              <el-option label="待处理" :value="0" />
              <el-option label="处理中" :value="1" />
              <el-option label="已关闭" :value="2" />
            </el-select>
          </div>
          <el-table :data="feedbackList" stripe empty-text="暂无反馈">
            <el-table-column prop="title" label="标题" min-width="140" show-overflow-tooltip />
            <el-table-column prop="username" label="用户" width="100" />
            <el-table-column prop="category" label="分类" width="90" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="row.status === 2 ? 'info' : row.status === 1 ? 'warning' : 'danger'">
                  {{ statusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="提交时间" width="170">
              <template #default="{ row }">{{ formatBeijingDateTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column v-if="canEdit()" label="操作" width="80">
              <template #default="{ row }">
                <el-button text type="primary" @click="openReply(row)">处理</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-if="feedbackTotal > 10"
            v-model:current-page="feedbackPage"
            :page-size="10"
            :total="feedbackTotal"
            layout="prev, pager, next"
            class="pager"
            @current-change="loadFeedback"
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="annDialog" :title="annForm.id ? '编辑公告' : '新建公告'" width="560px" destroy-on-close>
      <el-form label-width="80px">
        <el-form-item label="标题">
          <el-input v-model="annForm.title" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="annForm.content" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="annForm.status">
            <el-radio :value="1">发布</el-radio>
            <el-radio :value="0">草稿</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="annForm.priority" :min="0" :max="99" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="annDialog = false">取消</el-button>
        <el-button type="primary" @click="saveAnnouncement">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="replyDialog" title="处理反馈" width="560px" destroy-on-close>
      <p class="fb-title"><strong>{{ replyForm.title }}</strong></p>
      <p class="fb-content">{{ replyForm.content }}</p>
      <el-form label-width="80px">
        <el-form-item label="状态">
          <el-select v-model="replyForm.status" style="width:100%">
            <el-option label="处理中" :value="1" />
            <el-option label="已关闭" :value="2" />
          </el-select>
        </el-form-item>
        <el-form-item label="回复">
          <el-input v-model="replyForm.admin_reply" type="textarea" :rows="4" placeholder="管理员回复（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="replyDialog = false">取消</el-button>
        <el-button type="primary" @click="submitReply">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.section { padding: 24px; margin-bottom: 16px; }
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  h3 { margin: 0; }
}
.pager { margin-top: 16px; justify-content: flex-end; }
.fb-title { margin: 0 0 8px; }
.fb-content { color: $text-secondary; font-size: 13px; margin: 0 0 16px; line-height: 1.6; }
</style>
