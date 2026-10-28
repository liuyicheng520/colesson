<script setup lang="ts">
defineOptions({ name: 'PersonalCenter' })

import { computed, nextTick, onActivated, onBeforeUnmount, onDeactivated, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules, UploadRequestOptions } from 'element-plus'
import { ElMessage } from 'element-plus'
import {
  Camera, Edit, Lock, Refresh, DataAnalysis, Guide, Collection, Message, Document,
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { useUserStore } from '@/stores/user'
import { useProfileStore } from '@/stores/profile'
import ProfileRadar from '@/components/ProfileRadar.vue'
import EmptyState from '@/components/EmptyState.vue'
import { prepareAvatarFile, resolveAvatarUrl } from '@/utils/avatar'
import { systemApi, type LoginLogItem, type StudentFeedbackItem } from '@/api/system'
import { profileApi } from '@/api/profile'
import { behaviorApi } from '@/api/behavior'
import { pathApi } from '@/api/path'
import { resourceApi } from '@/api/resource'
import { userApi } from '@/api/user'
import type { LearningStats } from '@/types'
import {
  buildProfileTags,
  dimensionSummary,
  EMPTY_DEMO_DIMS,
  toRadarDims,
} from '@/utils/profileTags'
import { formatBeijingDateTime } from '@/utils/datetime'
import {
  loadGongshengOverview,
  type GongshengOverview,
} from '@/utils/gongshengProgress'

const router = useRouter()
const route = useRoute()
// 演示对比仅供答辩演示：?demo=1 才显示
const demoEnabled = computed(() => String(route.query.demo || '') === '1')
const userStore = useUserStore()
const profileStore = useProfileStore()

const pageLoading = ref(true)
const editing = ref(false)
const saving = ref(false)
const uploading = ref(false)
const localPreview = ref('')
const pwdVisible = ref(false)
const pwdLoading = ref(false)
const formRef = ref<FormInstance>()
const pwdFormRef = ref<FormInstance>()

const feedbackVisible = ref(false)
const feedbackLoading = ref(false)
const feedbackForm = reactive({
  category: 'bug',
  title: '',
  content: '',
  screenshot_url: '',
})
const feedbackHistory = ref<StudentFeedbackItem[]>([])
const historyOpen = ref(false)

const loginLogVisible = ref(false)
const loginLogs = ref<LoginLogItem[]>([])
const loginLogLoading = ref(false)
const bindEmailVisible = ref(false)
const bindEmail = ref('')
const bindEmailLoading = ref(false)

const stats = ref<LearningStats | null>(null)
const pathCount = ref(0)
const resourceCount = ref(0)
const gongsheng = ref<GongshengOverview | null>(null)
const overviewLoading = ref(false)
const refreshLoading = ref(false)

/** live | empty | full — 答辩演示对比 */
const demoMode = ref<'live' | 'empty' | 'full'>('live')
const demoStep = ref(0)

const trendChartRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null

const majorOptions = [
  '软件工程2024级',
  '软件工程2023级',
  '计算机科学2024级',
  '计算机科学2023级',
  '人工智能2024级',
  '数据科学2024级',
  '信息安全2024级',
  '网络工程2024级',
]

const form = reactive({
  nickname: '',
  real_name: '',
  major: '',
  email: '',
  phone: '',
  student_no: '',
  bio: '',
})

const pwdForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const pwdComplexity = /^(?=.*[A-Za-z])(?=.*\d).{8,64}$/

const rules: FormRules = {
  nickname: [
    { required: true, message: '请输入昵称', trigger: 'blur' },
    { min: 2, max: 20, message: '昵称长度为 2~20 个字符', trigger: 'blur' },
  ],
  real_name: [
    { required: true, message: '请输入真实姓名', trigger: 'blur' },
    { min: 2, max: 10, message: '真实姓名为 2~10 个字符', trigger: 'blur' },
  ],
  major: [
    { required: true, message: '请选择或输入专业年级', trigger: 'change' },
    { min: 2, max: 128, message: '专业年级格式不正确', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: ['blur', 'change'] },
  ],
  phone: [
    {
      validator: (_r, v, cb) => {
        const s = String(v || '').trim()
        if (!s) return cb()
        if (!/^1[3-9]\d{9}$/.test(s)) cb(new Error('请输入11位中国大陆手机号'))
        else cb()
      },
      trigger: 'blur',
    },
  ],
  student_no: [{ max: 32, message: '学号不超过32个字符', trigger: 'blur' }],
  bio: [{ max: 50, message: '学习目标不超过50字', trigger: 'blur' }],
}

const pwdRules: FormRules = {
  old_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    {
      validator: (_r, v, cb) => {
        if (!pwdComplexity.test(String(v || ''))) {
          cb(new Error('密码需 8~64 位，且同时包含字母与数字'))
        } else cb()
      },
      trigger: 'blur',
    },
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (_r, v, cb) => {
        if (v !== pwdForm.new_password) cb(new Error('两次输入的密码不一致'))
        else cb()
      },
      trigger: 'blur',
    },
  ],
}

const avatarSrc = computed(() =>
  localPreview.value || resolveAvatarUrl(userStore.userInfo?.avatar_url, userStore.avatarVersion),
)
const avatarFallback = computed(() => userStore.userInfo?.nickname?.[0] || 'U')
const createdAt = computed(() => formatBeijingDateTime(userStore.userInfo?.created_at))
const lastLoginText = computed(() => {
  const t = userStore.userInfo?.last_login_at
  if (!t) return formatBeijingDateTime(loginLogs.value[0]?.created_at, '暂无记录')
  return formatBeijingDateTime(t)
})

const completenessPct = computed(() => {
  if (demoMode.value === 'empty') return 18
  if (demoMode.value === 'full') return 100
  const p = profileStore.profile
  if (!p) return 0
  const total = p.total_question_count || 6
  const byQuestions = Math.round(((p.completed_question_count ?? 0) / total) * 100)
  if (typeof p.completeness === 'number' && p.completeness > 0) {
    const byCompleteness = Math.round(p.completeness <= 1 ? p.completeness * 100 : p.completeness)
    // 与画像页构建进度对齐，取较大值避免一侧 100% 另一侧偏低
    return Math.max(byQuestions, byCompleteness)
  }
  return byQuestions
})

const showIncompleteBanner = computed(() => completenessPct.value < 60 && demoMode.value !== 'full')

const profileTags = computed(() => {
  const dims = profileStore.profile?.dimensions || []
  if (!dims.length) {
    return { line: '专业：待完善｜薄弱点：待评估｜偏好：待评估｜学习节奏：待评估' }
  }
  return buildProfileTags(dims)
})

const liveRadarDims = computed(() => {
  const p = profileStore.profile
  if (!p?.dimensions?.length) return []
  return toRadarDims(p.dimensions, p.dimension_progress)
})

const displayRadarDims = computed(() => {
  if (demoMode.value === 'empty') return EMPTY_DEMO_DIMS
  if (demoMode.value === 'full') {
    return liveRadarDims.value.length
      ? liveRadarDims.value.map((d) => ({ ...d, value: Math.max(d.value, 0.72), weak: false }))
      : EMPTY_DEMO_DIMS.map((d) => ({ ...d, value: 0.85, weak: false, summary: '演示：维度已完整采集' }))
  }
  return liveRadarDims.value
})

const dimCards = computed(() => {
  const progress = profileStore.profile?.dimension_progress || []
  const dims = profileStore.profile?.dimensions || []
  const dimByCode = Object.fromEntries(dims.map((d) => [d.dimension_code, d]))
  const codes = ['D1', 'D6', 'D5', 'D4', 'D2', 'D3']
  const nameFallback: Record<string, string> = {
    D1: '知识基础',
    D2: '认知风格',
    D3: '学习目标',
    D4: '学习历史',
    D5: '易错点偏好',
    D6: '学习节奏',
  }
  if (demoMode.value === 'empty') {
    return EMPTY_DEMO_DIMS.map((d) => ({
      code: d.code,
      name: d.name,
      score: Math.round(d.value * 100),
      summary: d.summary,
      weak: true,
    }))
  }
  return codes.map((code) => {
    const prog = progress.find((p) => p.dimension_code === code)
    const dim = dimByCode[code]
    const score = Number(prog?.display_score ?? dim?.display_score ?? dim?.confidence ?? 0)
    const value = prog?.dimension_value || dim?.dimension_value
    return {
      code,
      name: prog?.dimension_name || dim?.dimension_name || nameFallback[code],
      score: Math.round((score <= 1 ? score : score / 100) * 100),
      summary: dimensionSummary(code, value),
      weak: (score <= 1 ? score : score / 100) < 0.45,
    }
  })
})

const weakPointCount = computed(() => {
  const d5 = profileStore.profile?.dimensions?.find((d) => d.dimension_code === 'D5')
  const weak = (d5?.dimension_value?.weakPoints as unknown[]) || []
  if (weak.length) return weak.length
  return stats.value?.mastery_items?.filter((m) => m.value < 0.5).length || 0
})

const securityLevel = computed(() => {
  const hasEmail = !!userStore.userInfo?.email
  const hasPhone = !!userStore.userInfo?.phone
  if (hasEmail && hasPhone) return '高'
  if (hasEmail || hasPhone) return '中'
  return '低'
})

function fillFormFromUser() {
  const u = userStore.userInfo
  if (!u) return
  form.nickname = u.nickname || ''
  form.real_name = u.real_name || ''
  form.major = u.major || (u.grade ? `${u.major || ''}${u.grade}年级` : '')
  form.email = u.email || ''
  form.phone = u.phone || ''
  form.student_no = u.student_no || ''
  form.bio = u.bio || ''
}

function startEdit() {
  fillFormFromUser()
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  formRef.value?.clearValidate()
}

async function handleSave() {
  if (!formRef.value || saving.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await userStore.updateProfile({
      nickname: form.nickname.trim(),
      real_name: form.real_name.trim(),
      major: form.major.trim(),
      email: form.email.trim(),
      phone: form.phone.trim() || undefined,
      student_no: form.student_no.trim() || undefined,
      bio: form.bio.trim() || undefined,
    })
    ElMessage.success('资料保存成功，画像基础维度已同步')
    editing.value = false
  } finally {
    saving.value = false
  }
}

async function handleAvatarUpload(options: UploadRequestOptions) {
  const raw = options.file as File
  const allowed = ['image/jpeg', 'image/png', 'image/jpg']
  const extOk = /\.(jpe?g|png)$/i.test(raw.name)
  if (!allowed.includes(raw.type) && !extOk) {
    ElMessage.error('仅支持 JPG/PNG 格式')
    return
  }
  if (raw.size > 2 * 1024 * 1024) {
    ElMessage.error('头像大小不能超过 2MB')
    return
  }
  uploading.value = true
  const previewUrl = URL.createObjectURL(raw)
  localPreview.value = previewUrl
  try {
    const prepared = await prepareAvatarFile(raw)
    await userStore.uploadAvatar(prepared)
    localPreview.value = ''
    ElMessage.success('头像更新成功')
  } catch {
    localPreview.value = ''
    await userStore.fetchUser()
  } finally {
    URL.revokeObjectURL(previewUrl)
    uploading.value = false
  }
}

async function handleChangePassword() {
  if (!pwdFormRef.value || pwdLoading.value) return
  const valid = await pwdFormRef.value.validate().catch(() => false)
  if (!valid) return
  pwdLoading.value = true
  try {
    await userStore.changePassword(pwdForm.old_password, pwdForm.new_password)
    ElMessage.success('密码更新完成，同步刷新账号安全画像信息')
    pwdVisible.value = false
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    pwdForm.confirm_password = ''
  } finally {
    pwdLoading.value = false
  }
}

async function submitFeedback() {
  if (!feedbackForm.title.trim() || !feedbackForm.content.trim()) {
    ElMessage.warning('请填写标题和内容')
    return
  }
  feedbackLoading.value = true
  try {
    await systemApi.submitFeedback({
      category: feedbackForm.category,
      title: feedbackForm.title.trim(),
      content: feedbackForm.content.trim(),
      screenshot_url: feedbackForm.screenshot_url || undefined,
    })
    ElMessage.success('反馈已提交，后台将根据你的画像学习需求优先优化对应功能')
    feedbackVisible.value = false
    feedbackForm.title = ''
    feedbackForm.content = ''
    feedbackForm.screenshot_url = ''
    await loadFeedbackHistory()
  } finally {
    feedbackLoading.value = false
  }
}

async function handleFeedbackShot(options: UploadRequestOptions) {
  try {
    const res = await systemApi.uploadFeedbackScreenshot(options.file as File)
    feedbackForm.screenshot_url = res.url
    ElMessage.success('截图已上传')
  } catch {
    ElMessage.error('截图上传失败')
  }
}

async function loadFeedbackHistory() {
  try {
    const res = await systemApi.listMyFeedback({ page: 1, page_size: 10 })
    feedbackHistory.value = res.items || []
  } catch {
    feedbackHistory.value = []
  }
}

async function openLoginLogs() {
  loginLogVisible.value = true
  loginLogLoading.value = true
  try {
    loginLogs.value = await systemApi.listLoginLogs()
  } catch {
    loginLogs.value = []
  } finally {
    loginLogLoading.value = false
  }
}

function openBindEmail() {
  bindEmail.value = userStore.userInfo?.email || ''
  bindEmailVisible.value = true
}

async function submitBindEmail() {
  if (!bindEmail.value || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(bindEmail.value)) {
    ElMessage.warning('请输入有效邮箱')
    return
  }
  const u = userStore.userInfo
  if (!u?.real_name || !u?.major || !(u.nickname && u.nickname.length >= 2)) {
    ElMessage.warning('请先完善真实姓名、专业年级与昵称后再绑定邮箱')
    bindEmailVisible.value = false
    startEdit()
    form.email = bindEmail.value
    return
  }
  bindEmailLoading.value = true
  try {
    fillFormFromUser()
    await userApi.updateProfile({
      nickname: form.nickname,
      real_name: form.real_name,
      major: form.major,
      email: bindEmail.value.trim(),
      phone: form.phone || undefined,
      student_no: form.student_no || undefined,
      bio: form.bio || undefined,
    })
    await userStore.fetchUser()
    fillFormFromUser()
    ElMessage.success('邮箱绑定成功，可用于接收学习进度通知')
    bindEmailVisible.value = false
  } finally {
    bindEmailLoading.value = false
  }
}

async function loadOverview() {
  overviewLoading.value = true
  try {
    const [s, paths, resources, gs] = await Promise.all([
      behaviorApi.getStats({ include_trend_30d: false }).catch(() => null),
      pathApi.list().catch(() => []),
      resourceApi.list({ page: 1, page_size: 1 }).catch(() => ({ total: 0, items: [] })),
      loadGongshengOverview().catch(() => null),
    ])
    stats.value = s
    pathCount.value = Array.isArray(paths) ? paths.length : 0
    resourceCount.value = resources?.total ?? 0
    gongsheng.value = gs
    await nextTick()
    renderTrend()
  } finally {
    overviewLoading.value = false
  }
}

function renderTrend() {
  if (!trendChartRef.value) return
  if (!trendChart) trendChart = echarts.init(trendChartRef.value)
  const series = demoMode.value === 'empty'
    ? Array.from({ length: 7 }, (_, i) => ({ date: `D-${6 - i}`, minutes: 0 }))
    : (stats.value?.trend_7d || [])
  trendChart.setOption({
    grid: { left: 36, right: 12, top: 24, bottom: 28 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: series.map((d) => String(d.date).slice(5) || d.date),
      axisLabel: { fontSize: 11 },
    },
    yAxis: { type: 'value', name: '分钟', splitLine: { lineStyle: { type: 'dashed' } } },
    series: [{
      type: 'line',
      smooth: true,
      data: series.map((d) => d.minutes),
      areaStyle: { color: 'rgba(64,158,255,0.15)' },
      lineStyle: { color: '#409EFF', width: 2 },
      itemStyle: { color: '#409EFF' },
    }],
  }, true)
}

async function refreshProfileFromBehavior() {
  refreshLoading.value = true
  try {
    const res = await profileApi.refreshBehaviorProfile()
    await profileStore.fetchProfile()
    await loadOverview()
    if (res.refreshed) {
      ElMessage.success(`画像已刷新${res.updated_dimensions?.length ? `：${res.updated_dimensions.join('、')}` : ''}`)
    } else {
      ElMessage.info(res.reason || '近期学习行为不足，暂无明显更新')
    }
    demoMode.value = 'live'
  } catch {
    ElMessage.warning('刷新失败，请稍后再试或前往画像构建')
  } finally {
    refreshLoading.value = false
  }
}

function runDemoCompare() {
  demoStep.value = (demoStep.value % 2) + 1
  if (demoStep.value === 1) {
    demoMode.value = 'empty'
    ElMessage.warning('演示：低完整度画像 — 缺失维度，无法生成精细化个性化路径')
  } else {
    demoMode.value = 'full'
    ElMessage.success('演示：完整 6 维画像 — 可生成专属路径与多模态资源')
  }
  nextTick(renderTrend)
}

function go(path: string) {
  router.push(path)
}

function feedbackStatusText(status: number) {
  if (status === 1) return '处理中'
  if (status === 2) return '已回复'
  return '待处理'
}

async function bootstrap() {
  // 有本地用户缓存时立刻渲染，避免整页骨架挡住已有数据
  const hasCache = !!userStore.userInfo
  pageLoading.value = !hasCache
  if (hasCache) fillFormFromUser()

  try {
    const critical: Promise<unknown>[] = []
    if (!userStore.userInfo) critical.push(userStore.fetchUser())
    else void userStore.fetchUser() // 后台刷新，不阻塞首屏
    if (!profileStore.profile) critical.push(profileStore.fetchProfile())
    else void profileStore.fetchProfile()

    if (critical.length) await Promise.all(critical)
    fillFormFromUser()
  } finally {
    pageLoading.value = false
    await nextTick()
    renderTrend()
  }

  // 次要数据后台加载，不阻塞首屏
  void loadOverview()
  void loadFeedbackHistory()
}

watch(demoMode, () => nextTick(renderTrend))

onMounted(bootstrap)
onActivated(() => {
  nextTick(() => {
    trendChart?.resize()
  })
})
onDeactivated(() => {
  trendChart?.dispose()
  trendChart = null
})
onBeforeUnmount(() => {
  trendChart?.dispose()
  trendChart = null
})
</script>

<template>
  <div class="page-container personal-center">
    <!-- 画像完整度不足提示 -->
    <el-alert
      v-if="showIncompleteBanner"
      class="incomplete-banner"
      type="warning"
      show-icon
      :closable="false"
      title="你的学习画像数据不足，前往完善 6 维维度，解锁完整个性化学习功能"
    >
      <template #default>
        <el-button type="warning" size="small" @click="go('/student/profile-dialogue')">去完善</el-button>
      </template>
    </el-alert>

    <el-skeleton v-if="pageLoading" animated :rows="10" />

    <template v-else>
      <el-row :gutter="24" class="profile-radar-row">
        <!-- 区域1：个人信息 -->
        <el-col :xs="24" :lg="14" class="profile-col">
          <div class="card profile-card hover-lift">
            <div class="profile-header">
              <div class="avatar-wrap">
                <el-upload
                  class="avatar-uploader"
                  :show-file-list="false"
                  accept="image/jpeg,image/png,image/jpg,.jpg,.jpeg,.png"
                  :http-request="handleAvatarUpload"
                  :disabled="uploading"
                >
                  <div class="avatar-trigger" :class="{ uploading }">
                    <el-avatar :size="88" :src="avatarSrc || undefined" class="avatar">
                      {{ avatarFallback }}
                    </el-avatar>
                    <div class="avatar-mask">
                      <el-icon v-if="uploading" class="is-loading"><Camera /></el-icon>
                      <template v-else>
                        <el-icon><Camera /></el-icon>
                        <span>更换头像</span>
                      </template>
                    </div>
                  </div>
                </el-upload>
                <a class="link-to-profile" @click="go('/student/profile-dialogue')">前往画像构建 →</a>
              </div>
              <div class="header-meta">
                <h2>
                  <span :class="{ 'name-placeholder': !userStore.hasRealName }">{{ userStore.displayName }}</span>
                </h2>
                <p class="username">@{{ userStore.userInfo?.username }}</p>
                <p class="tag-line">{{ profileTags.line }}</p>
                <p v-if="userStore.userInfo?.bio && !editing" class="bio-preview">{{ userStore.userInfo.bio }}</p>
              </div>
              <div class="header-actions">
                <el-tooltip content="修改基础信息同步更新学习画像基础维度" placement="top">
                  <el-button v-if="!editing" type="primary" :icon="Edit" @click="startEdit">编辑资料</el-button>
                </el-tooltip>
                <template v-if="editing">
                  <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
                  <el-button :disabled="saving" @click="cancelEdit">取消</el-button>
                </template>
              </div>
            </div>

            <el-divider />

            <el-form
              ref="formRef"
              :model="form"
              :rules="rules"
              label-width="110px"
              class="profile-form"
              :disabled="!editing"
            >
              <div class="form-section-title">账号基础信息</div>
              <el-form-item label="用户 ID">
                <el-input :model-value="String(userStore.userInfo?.id ?? '')" disabled class="readonly-field" />
              </el-form-item>
              <el-form-item label="登录账号">
                <el-input :model-value="userStore.userInfo?.username" disabled class="readonly-field" />
              </el-form-item>
              <el-form-item label="注册时间">
                <el-input :model-value="createdAt" disabled class="readonly-field" />
              </el-form-item>
              <el-form-item label="手机号" prop="phone">
                <el-input
                  v-model="form.phone"
                  maxlength="11"
                  clearable
                  placeholder="选填，11位中国大陆手机号"
                />
              </el-form-item>
              <el-form-item label="学号" prop="student_no">
                <el-input
                  v-model="form.student_no"
                  maxlength="32"
                  clearable
                  placeholder="选填，如学号/工号"
                />
              </el-form-item>

              <div class="form-section-title">画像核心信息</div>
              <el-form-item label="昵称" prop="nickname" required>
                <el-input v-model="form.nickname" maxlength="20" show-word-limit placeholder="2~20 个字符" />
              </el-form-item>
              <el-form-item label="真实姓名" prop="real_name" required>
                <el-input v-model="form.real_name" maxlength="10" show-word-limit />
              </el-form-item>
              <el-form-item label="专业年级" prop="major" required>
                <el-select
                  v-model="form.major"
                  filterable
                  allow-create
                  default-first-option
                  placeholder="选择或输入，如软件工程2024级"
                  style="width: 100%"
                >
                  <el-option v-for="m in majorOptions" :key="m" :label="m" :value="m" />
                </el-select>
              </el-form-item>
              <el-form-item label="邮箱" prop="email" required>
                <el-input v-model="form.email" placeholder="name@example.com" />
              </el-form-item>
              <el-form-item label="学习目标" prop="bio" required class="bio-item">
                <el-input
                  v-model="form.bio"
                  type="textarea"
                  :rows="6"
                  class="bio-textarea"
                  maxlength="50"
                  show-word-limit
                  placeholder="直接影响路径生成，如：希望掌握机器学习基础"
                  resize="none"
                />
                <p class="field-hint">该内容将作为 AI 生成个性化学习路径的核心依据</p>
              </el-form-item>
            </el-form>

            <div class="quick-links">
              <el-button size="small" :icon="Guide" @click="go('/student/path')">我的学习路径</el-button>
              <el-button size="small" :icon="Collection" @click="go('/student/course-center')">课程中心</el-button>
              <el-button size="small" :icon="Collection" @click="go('/student/resources')">我的资源库</el-button>
              <el-button size="small" :icon="DataAnalysis" @click="go('/student/dashboard')">学习数据报告</el-button>
            </div>
          </div>
        </el-col>

        <!-- 区域2：学习画像雷达 -->
        <el-col :xs="24" :lg="10" class="radar-col">
          <div class="card radar-card hover-lift">
            <div class="radar-head">
              <h3>我的学习画像</h3>
              <div class="radar-actions">
                <el-button size="small" :icon="Refresh" :loading="refreshLoading" @click="refreshProfileFromBehavior">
                  刷新画像数据
                </el-button>
                <el-button v-if="demoEnabled" size="small" type="primary" plain @click="runDemoCompare">演示对比模式</el-button>
              </div>
            </div>
            <p class="completeness-text">
              画像完整度 {{ completenessPct }}%｜
              <template v-if="completenessPct >= 100 || demoMode === 'full'">
                6 大维度数据已全部采集，系统将基于该画像生成专属学习路径与多模态资源
              </template>
              <template v-else-if="demoMode === 'empty'">
                维度缺失，无法生成精细化个性化路径，请完善画像
              </template>
              <template v-else>
                {{ profileStore.profile?.completed_dimension_count ?? 0 }}/6 维已采集，完善后可解锁更精准的路径与资源
              </template>
            </p>
            <el-progress
              :percentage="completenessPct"
              :stroke-width="14"
              :color="completenessPct < 60 ? '#E6A23C' : '#409EFF'"
              striped
              style="margin: 8px 0 12px"
            />

            <ProfileRadar
              v-if="displayRadarDims.length >= 2"
              :dimensions="displayRadarDims"
            />
            <EmptyState
              v-else
              description="尚未构建学习画像"
              action-text="去构建"
              @action="go('/student/profile-dialogue')"
            />

            <div class="dim-panel">
              <div
                v-for="c in dimCards"
                :key="c.code"
                class="dim-mini hover-lift"
                :class="{ weak: c.weak }"
              >
                <div class="dim-name">{{ c.name }}</div>
                <div class="dim-score" :style="{ color: c.weak ? '#E6A23C' : '#67C23A' }">{{ c.score }}</div>
                <p class="dim-summary">{{ c.summary }}</p>
                <el-button link type="primary" size="small" @click="go('/student/profile-dialogue')">调整维度</el-button>
              </div>
            </div>
            <p class="radar-foot-hint">
              学习路径、资源推送、智能答疑全部基于本 6 维画像数据个性化生成，学习行为会自动更新画像分值。
            </p>
          </div>
        </el-col>
      </el-row>

      <!-- 区域3：全局学习总览 -->
      <div v-loading="overviewLoading" class="card overview-card hover-lift">
        <h3>我的学习全局数据 <span class="sub">（基于画像与历史学习行为统计）</span></h3>
        <el-row :gutter="16" class="overview-metrics">
          <el-col :xs="12" :sm="6">
            <div class="metric">
              <div class="metric-label">已生成个性化路径</div>
              <div class="metric-value">{{ demoMode === 'empty' ? 0 : pathCount }} <small>条</small></div>
              <el-button link type="primary" @click="go('/student/path')">查看路径</el-button>
            </div>
          </el-col>
          <el-col :xs="12" :sm="6">
            <div class="metric">
              <div class="metric-label">定制多模态资源</div>
              <div class="metric-value">{{ demoMode === 'empty' ? 0 : resourceCount }} <small>份</small></div>
              <el-button link type="primary" @click="go('/student/resources')">资源中心</el-button>
            </div>
          </el-col>
          <el-col :xs="12" :sm="6">
            <div class="metric">
              <div class="metric-label">累计学习时长</div>
              <div class="metric-value">
                {{ demoMode === 'empty' ? 0 : (stats?.total_study_hours ?? 0) }} <small>小时</small>
              </div>
            </div>
          </el-col>
          <el-col :xs="12" :sm="6">
            <div class="metric">
              <div class="metric-label">错题薄弱知识点</div>
              <div class="metric-value">{{ demoMode === 'empty' ? 0 : weakPointCount }} <small>个</small></div>
              <el-button link type="primary" @click="go('/student/dashboard')">查看学习数据</el-button>
            </div>
          </el-col>
          <el-col :xs="12" :sm="6">
            <div class="metric">
              <div class="metric-label">共生已发布智课</div>
              <div class="metric-value">{{ demoMode === 'empty' ? 0 : (gongsheng?.lessonCount ?? 0) }} <small>门</small></div>
              <el-button link type="primary" @click="go('/student/course-center')">课程中心</el-button>
            </div>
          </el-col>
          <el-col :xs="12" :sm="6">
            <div class="metric">
              <div class="metric-label">共生学习进度</div>
              <div class="metric-value">{{ demoMode === 'empty' ? 0 : (gongsheng?.avgPercent ?? 0) }} <small>%</small></div>
              <div class="metric-sub">已开始 {{ demoMode === 'empty' ? 0 : (gongsheng?.startedCount ?? 0) }} / 完成 {{ demoMode === 'empty' ? 0 : (gongsheng?.completedCount ?? 0) }}</div>
            </div>
          </el-col>
        </el-row>
        <div v-if="gongsheng?.recent?.length && demoMode !== 'empty'" class="gs-recent">
          <p class="trend-title">最近课程中心</p>
          <el-table :data="gongsheng.recent" size="small" stripe style="width: 100%">
            <el-table-column prop="title" label="课程" min-width="160" />
            <el-table-column prop="percent" label="进度" width="90">
              <template #default="{ row }">{{ row.percent }}%</template>
            </el-table-column>
          </el-table>
        </div>
        <div v-if="demoMode === 'empty' || (!pathCount && !resourceCount && !(stats?.has_data) && !(gongsheng?.lessonCount))" class="empty-guide">
          <EmptyState
            description="暂无学习路径 / 资源 / 课程数据"
            action-text="去课程中心"
            @action="go('/student/course-center')"
          />
          <div class="empty-extra-actions">
            <el-button @click="go('/student/profile-dialogue')">先完善画像</el-button>
            <el-button @click="go('/student/path')">生成路径</el-button>
          </div>
        </div>
        <div v-else>
          <p class="trend-title">近 7 天学习时长变化趋势</p>
          <div ref="trendChartRef" class="trend-chart" />
        </div>
      </div>

      <el-row :gutter="24">
        <!-- 区域4：账号安全 -->
        <el-col :xs="24" :lg="12">
          <div class="card security-card hover-lift">
            <h3>账号安全</h3>
            <p class="security-status">
              账号安全等级：<strong>{{ securityLevel }}</strong>
              ｜最近登录时间：{{ lastLoginText }}
            </p>
            <div class="security-row">
              <div>
                <strong>登录密码</strong>
                <p>定期更换密码可提升账号安全性</p>
              </div>
              <el-button :icon="Lock" @click="pwdVisible = true">修改密码</el-button>
            </div>
            <div class="security-row">
              <div>
                <strong>绑定邮箱</strong>
                <p>用于接收资源更新、学习进度通知</p>
              </div>
              <el-button :icon="Message" @click="openBindEmail">绑定邮箱</el-button>
            </div>
            <div class="security-row">
              <div>
                <strong>登录日志</strong>
                <p>查看近期登录记录，保障账号安全</p>
              </div>
              <el-button :icon="Document" @click="openLoginLogs">登录日志</el-button>
            </div>
          </div>
        </el-col>

        <!-- 区域5：意见反馈 -->
        <el-col :xs="24" :lg="12">
          <div class="card feedback-card hover-lift">
            <h3>意见反馈</h3>
            <p class="feedback-hint">遇到问题或有改进建议？欢迎告诉我们。</p>
            <el-button type="primary" plain @click="feedbackVisible = true">提交反馈</el-button>
            <el-collapse v-model="historyOpen" class="feedback-history">
              <el-collapse-item title="历史反馈记录" name="1">
                <div v-if="!feedbackHistory.length" class="muted">暂无反馈记录</div>
                <div v-for="item in feedbackHistory" :key="item.id" class="fb-item">
                  <div class="fb-title">
                    {{ item.title }}
                    <el-tag size="small" :type="item.status === 2 ? 'success' : 'info'">
                      {{ feedbackStatusText(item.status) }}
                    </el-tag>
                  </div>
                  <p class="fb-meta">{{ formatBeijingDateTime(item.created_at) }} · {{ item.category }}</p>
                  <p v-if="item.admin_reply" class="fb-reply">回复：{{ item.admin_reply }}</p>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
        </el-col>
      </el-row>

      <p class="safety-footer">
        本系统所有个性化学习路径、多模态资源由多智能体协同校验生成，无事实错误与违规内容
      </p>
    </template>

    <el-dialog v-model="feedbackVisible" title="提交反馈" width="520px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="分类">
          <el-select v-model="feedbackForm.category" style="width:100%">
            <el-option label="功能 BUG" value="bug" />
            <el-option label="页面优化" value="ui" />
            <el-option label="资源需求" value="resource" />
            <el-option label="路径规划建议" value="path" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="feedbackForm.title" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="feedbackForm.content" type="textarea" :rows="6" maxlength="2000" show-word-limit />
        </el-form-item>
        <el-form-item label="截图">
          <el-upload
            :show-file-list="false"
            accept="image/*"
            :http-request="handleFeedbackShot"
          >
            <el-button size="small">上传页面截图</el-button>
          </el-upload>
          <span v-if="feedbackForm.screenshot_url" class="shot-ok">已上传</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="feedbackVisible = false">取消</el-button>
        <el-button type="primary" :loading="feedbackLoading" @click="submitFeedback">提交</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="pwdVisible" title="修改密码" width="460px" destroy-on-close>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="密码需 8~64 位，且同时包含字母与数字"
        style="margin-bottom: 16px"
      />
      <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="100px">
        <el-form-item label="当前密码" prop="old_password">
          <el-input v-model="pwdForm.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="pwdForm.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input v-model="pwdForm.confirm_password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="pwdLoading" @click="handleChangePassword">确认修改</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="bindEmailVisible" title="绑定邮箱" width="420px" destroy-on-close>
      <el-input v-model="bindEmail" placeholder="用于接收学习进度通知" />
      <template #footer>
        <el-button @click="bindEmailVisible = false">取消</el-button>
        <el-button type="primary" :loading="bindEmailLoading" @click="submitBindEmail">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="loginLogVisible" title="登录日志" width="640px" destroy-on-close>
      <el-table v-loading="loginLogLoading" :data="loginLogs" size="small" max-height="360">
        <el-table-column prop="created_at" label="时间" min-width="160">
          <template #default="{ row }">{{ formatBeijingDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="ip_address" label="IP" width="130" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'" size="small">
              {{ row.success ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="user_agent" label="设备" min-width="180" show-overflow-tooltip />
      </el-table>
      <el-empty v-if="!loginLogLoading && !loginLogs.length" description="暂无登录记录" />
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.personal-center {
  position: relative;

  .incomplete-banner {
    margin-bottom: 16px;
    :deep(.el-alert__content) { width: 100%; }
    :deep(.el-alert__description) { margin-top: 8px; }
  }

  .card {
    padding: 24px;
    margin-bottom: 24px;
    border-radius: 12px;
    background: #fff;
    transition: box-shadow 0.2s ease, transform 0.2s ease;
    h3 { margin-bottom: 8px; }
  }

  .hover-lift:hover {
    box-shadow: 0 6px 18px rgba(64, 158, 255, 0.12);
  }

  .profile-header {
    display: flex;
    align-items: flex-start;
    gap: 20px;
    flex-wrap: wrap;
  }

  .avatar-wrap {
    position: relative;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;

    .avatar-uploader :deep(.el-upload) { border: none; cursor: pointer; }
    .avatar-trigger {
      position: relative;
      border-radius: 50%;
      overflow: hidden;
      &.uploading { pointer-events: none; }
    }
    .avatar { font-size: 32px; background: #409EFF; display: block; }
    .avatar-mask {
      position: absolute;
      inset: 0;
      border-radius: 50%;
      background: rgba(15, 23, 42, 0.45);
      color: #fff;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 4px;
      font-size: 12px;
      opacity: 0;
      transition: opacity 0.2s;
      .el-icon { font-size: 20px; }
    }
    .avatar-trigger:hover .avatar-mask,
    .avatar-trigger.uploading .avatar-mask { opacity: 1; }
  }

  .link-to-profile {
    color: #409EFF;
    font-size: 13px;
    cursor: pointer;
    &:hover { text-decoration: underline; filter: brightness(1.1); }
  }

  .header-meta {
    flex: 1;
    min-width: 180px;
    h2 { margin: 0 0 4px; font-size: 22px; }
    .username { color: $text-secondary; margin: 0 0 8px; }
    .tag-line {
      margin: 0 0 8px;
      font-size: 13px;
      line-height: 1.5;
      color: #606266;
      background: #F5F7FA;
      border-radius: 8px;
      padding: 8px 10px;
    }
    .name-placeholder { color: $text-secondary; font-style: italic; }
    .bio-preview { color: $text-secondary; font-size: 13px; margin: 0; line-height: 1.5; }
  }

  .header-actions { display: flex; gap: 8px; flex-shrink: 0; }

  .profile-radar-row {
    align-items: stretch;
    .profile-col,
    .radar-col {
      display: flex;
    }
  }

  .profile-card {
    width: 100%;
    display: flex;
    flex-direction: column;
    .profile-form {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }
    .bio-item {
      flex: 1;
      margin-bottom: 0;
      display: flex;
      flex-direction: column;
      :deep(.el-form-item__content) {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: stretch;
      }
      .bio-textarea {
        flex: 1;
        display: flex;
        flex-direction: column;
        :deep(.el-textarea) {
          flex: 1;
          display: flex;
          flex-direction: column;
        }
        :deep(.el-textarea__inner) {
          flex: 1;
          min-height: 140px !important;
          height: 100% !important;
        }
      }
    }
  }

  .radar-card {
    width: 100%;
    display: flex;
    flex-direction: column;
  }

  .form-section-title {
    font-size: 14px;
    font-weight: 600;
    color: #303133;
    margin: 8px 0 12px;
    padding-left: 8px;
    border-left: 3px solid #409EFF;
  }

  .field-hint {
    margin: 6px 0 0;
    font-size: 12px;
    color: $text-secondary;
    line-height: 1.4;
  }

  .readonly-field :deep(.el-input__wrapper) {
    background: #F5F7FA !important;
  }

  .quick-links {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
    padding-top: 16px;
    border-top: 1px solid #ebeef5;
  }

  .radar-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    h3 { margin: 0; }
  }
  .radar-actions { display: flex; gap: 8px; flex-wrap: wrap; }
  .completeness-text {
    margin: 12px 0 0;
    font-size: 13px;
    color: $text-secondary;
    line-height: 1.5;
  }

  .dim-panel {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    margin-top: 12px;
  }
  .dim-mini {
    background: #F5F7FA;
    border-radius: 10px;
    padding: 10px 12px;
    border: 1px solid transparent;
    &.weak { background: #FFF7CC; border-color: #f5e6a3; }
    .dim-name { font-size: 13px; font-weight: 600; }
    .dim-score { font-size: 20px; font-weight: 700; margin: 4px 0; }
    .dim-summary { font-size: 12px; color: $text-secondary; margin: 0 0 4px; line-height: 1.4; min-height: 34px; }
  }
  .radar-foot-hint {
    margin: 12px 0 0;
    font-size: 12px;
    color: $text-secondary;
    line-height: 1.5;
  }

  .overview-card {
    .sub { font-size: 13px; color: $text-secondary; font-weight: 400; }
  }
  .empty-extra-actions {
    display: flex;
    justify-content: center;
    gap: 8px;
    margin-top: -12px;
    margin-bottom: 8px;
    flex-wrap: wrap;
  }
  .overview-metrics { margin-top: 12px; }
  .metric-sub { margin-top: 6px; font-size: 12px; color: $text-secondary; }
  .gs-recent { margin-top: 16px; }
  .metric {
    background: #F5F7FA;
    border-radius: 10px;
    padding: 14px;
    min-height: 110px;
    transition: box-shadow 0.2s;
    &:hover { box-shadow: 0 4px 12px rgba(64, 158, 255, 0.1); }
  }
  .metric-label { font-size: 13px; color: $text-secondary; }
  .metric-value {
    font-size: 26px;
    font-weight: 700;
    color: #303133;
    margin: 8px 0;
    small { font-size: 13px; font-weight: 400; color: $text-secondary; }
  }
  .trend-title { margin: 16px 0 8px; font-size: 13px; color: $text-secondary; }
  .trend-chart { width: 100%; height: 220px; }

  .security-status {
    margin: 0 0 16px;
    font-size: 13px;
    color: $text-secondary;
    strong { color: #67C23A; }
  }
  .security-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 12px 0;
    border-bottom: 1px solid #ebeef5;
    &:last-child { border-bottom: none; }
    p { margin: 4px 0 0; color: $text-secondary; font-size: 13px; }
  }

  .feedback-hint { color: $text-secondary; font-size: 13px; margin: 0 0 12px; }
  .feedback-history { margin-top: 16px; }
  .fb-item {
    padding: 10px 0;
    border-bottom: 1px solid #ebeef5;
    &:last-child { border-bottom: none; }
  }
  .fb-title { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 13px; }
  .fb-meta { margin: 4px 0; font-size: 12px; color: $text-secondary; }
  .fb-reply { margin: 0; font-size: 12px; color: #409EFF; }
  .muted { color: $text-secondary; font-size: 13px; }
  .shot-ok { margin-left: 8px; color: #67C23A; font-size: 12px; }

  .safety-footer {
    text-align: center;
    font-size: 12px;
    color: #909399;
    margin: 8px 0 48px;
    line-height: 1.6;
  }

  a.link-hover:hover,
  :deep(.el-button.is-link:hover) {
    color: #409EFF;
    filter: brightness(1.05);
  }
}
</style>
