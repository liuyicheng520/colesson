<script setup lang="ts">
import { onMounted, onBeforeUnmount, onActivated, ref, computed, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { profileApi } from '@/api/profile'
import { useProfileStore } from '@/stores/profile'
import ProfileRadar from '@/components/ProfileRadar.vue'
import ProfileDimensionCards from '@/components/ProfileDimensionCards.vue'
import ProfileModeSelector from '@/components/profile/ProfileModeSelector.vue'
import ProfileDialogueMode from '@/components/profile/ProfileDialogueMode.vue'
import ProfileQuestionnaireMode from '@/components/profile/ProfileQuestionnaireMode.vue'
import ProfileAssessmentMode from '@/components/profile/ProfileAssessmentMode.vue'
import ProfileBehaviorMode from '@/components/profile/ProfileBehaviorMode.vue'
import {
  MODE_INTRO_SEEN_KEY,
  MODE_STORAGE_KEY,
  type ProfileBuildMode,
} from '@/profile/modes'
import type { DimensionProgressItem } from '@/types'

const profileStore = useProfileStore()

const activeMode = ref<ProfileBuildMode>('dialogue')
const showIntro = ref(false)
const behaviorAvailable = ref(false)
const modeTransition = ref(false)

const dimensionProgress = ref<DimensionProgressItem[]>([])
const completedCount = ref(0)
const totalCount = ref(6)
const completedQuestions = ref(0)
const totalQuestions = ref(6)
const currentDimension = ref<{ code: string; name: string } | null>(null)
const currentQuestionIndex = ref(1)

const editVisible = ref(false)
const editItem = ref<DimensionProgressItem | null>(null)
const editJson = ref('')
const dialogueModeRef = ref<InstanceType<typeof ProfileDialogueMode> | null>(null)
const mainPanelRef = ref<HTMLElement | null>(null)
const sideStackRef = ref<HTMLElement | null>(null)
let sideStackObserver: ResizeObserver | null = null

/** 左侧对话框高度对齐右侧雷达+维度卡片底部 */
function syncDialogueHeight() {
  const side = sideStackRef.value
  const main = mainPanelRef.value
  if (!side || !main) return
  const h = Math.ceil(side.getBoundingClientRect().height)
  if (h < 200) return
  main.style.minHeight = `${h}px`
  main.style.height = `${h}px`
}

function bindHeightSync() {
  sideStackObserver?.disconnect()
  syncDialogueHeight()
  if (!sideStackRef.value || typeof ResizeObserver === 'undefined') return
  sideStackObserver = new ResizeObserver(() => {
    requestAnimationFrame(syncDialogueHeight)
  })
  sideStackObserver.observe(sideStackRef.value)
}

const progressPercent = computed(() => {
  // 与左侧「画像构建进度」同一口径：已答问数 / 总问数
  if (totalQuestions.value > 0) {
    return Math.round((completedQuestions.value / totalQuestions.value) * 100)
  }
  const p = profileStore.profile
  if (p?.completeness != null) {
    const c = Number(p.completeness)
    return Math.round(c <= 1 ? c * 100 : c)
  }
  return 0
})

const loadError = ref('')
const profileLoading = ref(false)

const radarDims = computed(() =>
  dimensionProgress.value
    .filter((d) => d.status === 'completed' || (d.display_score ?? 0) > 0)
    .map((d) => ({ name: d.dimension_name, value: d.display_score || 0.1 })),
)

function syncFromProfile() {
  const p = profileStore.profile
  if (!p) return
  dimensionProgress.value = p.dimension_progress || []
  completedCount.value = p.completed_dimension_count
  totalCount.value = p.core_dimension_count
  completedQuestions.value = p.completed_question_count ?? 0
  totalQuestions.value = p.total_question_count ?? 6
}

async function refreshProfile() {
  profileLoading.value = true
  loadError.value = ''
  try {
    await profileStore.fetchProfile()
    if (!profileStore.profile) {
      loadError.value = '画像数据加载失败，请确认后端服务已启动后点击重试'
      return
    }
    syncFromProfile()
  } catch {
    loadError.value = '画像数据加载失败，请确认后端服务已启动后点击重试'
  } finally {
    profileLoading.value = false
  }
}

function handleModeChange(mode: ProfileBuildMode) {
  if (mode === activeMode.value) return
  modeTransition.value = true
  setTimeout(() => {
    activeMode.value = mode
    localStorage.setItem(MODE_STORAGE_KEY, mode)
    modeTransition.value = false
  }, 150)
}

watch(activeMode, (m) => localStorage.setItem(MODE_STORAGE_KEY, m))

function handleProgress(data: Record<string, unknown>) {
  if (data.dimension_progress) dimensionProgress.value = data.dimension_progress as DimensionProgressItem[]
  if (data.completed_question_count != null) completedQuestions.value = data.completed_question_count as number
  if (data.current_dimension_code && data.current_dimension_name) {
    currentDimension.value = { code: data.current_dimension_code as string, name: data.current_dimension_name as string }
  }
  if (data.current_question_index != null) currentQuestionIndex.value = data.current_question_index as number
}

async function onModeSubmitted() {
  await refreshProfile()
}

function goDialogue() {
  handleModeChange('dialogue')
}

async function tryBehaviorRefresh() {
  try {
    const res = await profileApi.refreshBehaviorProfile()
    if (res.refreshed) await refreshProfile()
  } catch {
    /* silent */
  }
}

onMounted(async () => {
  const savedMode = localStorage.getItem(MODE_STORAGE_KEY) as ProfileBuildMode | null
  if (savedMode) activeMode.value = savedMode

  const introSeen = localStorage.getItem(MODE_INTRO_SEEN_KEY)
  showIntro.value = !introSeen

  await refreshProfile()

  try {
    const meta = await profileApi.getModesMeta()
    behaviorAvailable.value = meta.behavior_available
    if (!introSeen && meta.has_profile_data) {
      showIntro.value = false
      localStorage.setItem(MODE_INTRO_SEEN_KEY, '1')
    }
    if (meta.behavior_available) await tryBehaviorRefresh()
  } catch {
    behaviorAvailable.value = false
  }

  await nextTick()
  bindHeightSync()
  window.addEventListener('resize', syncDialogueHeight)
})

onActivated(() => {
  nextTick(bindHeightSync)
})

onBeforeUnmount(() => {
  sideStackObserver?.disconnect()
  sideStackObserver = null
  window.removeEventListener('resize', syncDialogueHeight)
})

watch(dimensionProgress, () => nextTick(syncDialogueHeight), { deep: true })
watch(activeMode, () => nextTick(() => {
  bindHeightSync()
}))

function confirmIntro(mode: ProfileBuildMode) {
  activeMode.value = mode
  showIntro.value = false
  localStorage.setItem(MODE_INTRO_SEEN_KEY, '1')
  localStorage.setItem(MODE_STORAGE_KEY, mode)
}

function openEdit(item: DimensionProgressItem) {
  editItem.value = item
  editJson.value = JSON.stringify(item.dimension_value || {}, null, 2)
  editVisible.value = true
}

async function onContinueDialogue(payload: { item: DimensionProgressItem; prompt: string }) {
  if (activeMode.value !== 'dialogue') {
    handleModeChange('dialogue')
    await nextTick()
    await new Promise((r) => setTimeout(r, 200))
  }
  await nextTick()
  const api = dialogueModeRef.value
  if (api?.continueFromCard) {
    await api.continueFromCard(payload.item.dimension_code, payload.prompt)
  } else {
    ElMessage.info('请切换到对话模式后继续完善该维度')
    handleModeChange('dialogue')
  }
}

async function saveEdit() {
  if (!editItem.value) return
  try {
    const parsed = JSON.parse(editJson.value)
    await profileApi.updateDimension({
      dimension_code: editItem.value.dimension_code,
      dimension_value: parsed,
      confidence: 0.98,
      source_type: 'manual',
    })
    await refreshProfile()
    editVisible.value = false
    ElMessage.success('维度已更新，画像数据已同步')
  } catch {
    ElMessage.error('JSON 格式无效或保存失败')
  }
}
</script>

<template>
  <div class="page-container profile-page">
    <!-- 首次进入模式选择面板 -->
    <div v-if="showIntro" class="intro-overlay">
      <div class="intro-panel">
        <h2>选择你的画像构建方式</h2>
        <p class="intro-desc">四种模式覆盖深度精准、高效速填、量化测评与无感采集，数据自动融合</p>
        <ProfileModeSelector
          :model-value="activeMode"
          :behavior-available="behaviorAvailable"
          @update:model-value="confirmIntro"
        />
        <el-button class="skip-btn" text @click="confirmIntro('dialogue')">跳过，使用对话模式</el-button>
      </div>
    </div>

    <div class="page-title">
      <div>
        <h2>学习者画像构建</h2>
        <p class="subtitle">多模式分层采集 · 数据融合驱动个性化学习</p>
      </div>
      <el-tag v-if="activeMode === 'dialogue' && currentDimension" type="primary" size="large" effect="plain">
        {{ currentDimension.name }} · {{ completedQuestions }}/{{ totalQuestions }} 问
      </el-tag>
    </div>

    <!-- 对学习者只说明完整度来源，避免「权重相加>100%」的误解 -->
    <p class="fusion-hint">
      画像由问卷、学习行为、对话与测评多路信息融合得到，可反复补充，完整度会持续提高（右侧进度为你的完成度，不是权重之和）。
    </p>
    <el-alert
      v-if="loadError"
      type="error"
      :title="loadError"
      show-icon
      :closable="false"
      class="load-alert"
    >
      <template #default>
        <el-button type="primary" size="small" :loading="profileLoading" @click="refreshProfile">重新加载画像</el-button>
      </template>
    </el-alert>
    <ProfileModeSelector
      :model-value="activeMode"
      :behavior-available="behaviorAvailable"
      compact
      class="mode-tabs"
      @update:model-value="handleModeChange"
    />

    <el-row :gutter="24" class="workspace-row">
      <el-col :xs="24" :lg="15">
        <div ref="mainPanelRef" class="main-panel card">
          <Transition name="mode-fade" mode="out-in">
            <div v-if="!modeTransition" :key="activeMode" class="mode-content">
              <ProfileDialogueMode
                v-if="activeMode === 'dialogue'"
                ref="dialogueModeRef"
                :dimension-progress="dimensionProgress"
                :completed-count="completedCount"
                :total-count="totalCount"
                :completed-questions="completedQuestions"
                :total-questions="totalQuestions"
                @progress="handleProgress"
                @updated="refreshProfile"
              />
              <ProfileQuestionnaireMode
                v-else-if="activeMode === 'questionnaire'"
                @submitted="onModeSubmitted"
                @go-dialogue="goDialogue"
              />
              <ProfileAssessmentMode
                v-else-if="activeMode === 'assessment'"
                @submitted="onModeSubmitted"
              />
              <ProfileBehaviorMode
                v-else-if="activeMode === 'behavior'"
                @generated="onModeSubmitted"
              />
            </div>
          </Transition>
        </div>
      </el-col>

      <el-col :xs="24" :lg="9">
        <div ref="sideStackRef" class="side-stack">
          <div class="card side-panel">
            <div class="panel-top">
              <h3>画像雷达图</h3>
              <el-progress type="circle" :percentage="progressPercent" :width="64" :stroke-width="5" />
            </div>
            <ProfileRadar v-if="radarDims.length >= 2" :dimensions="radarDims" />
            <el-empty v-else description="完成至少 2 个维度后显示雷达图" :image-size="80" />
          </div>
          <div class="card side-panel side-panel--dims">
            <ProfileDimensionCards
              :items="dimensionProgress"
              @edit="openEdit"
              @continue-dialogue="onContinueDialogue"
            />
          </div>
        </div>
      </el-col>
    </el-row>

    <el-dialog v-model="editVisible" title="手动调整维度" width="480px" destroy-on-close>
      <p v-if="editItem" class="edit-hint">{{ editItem.dimension_name }}（{{ editItem.dimension_code }}）</p>
      <el-input v-model="editJson" type="textarea" :rows="10" />
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存并同步</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.profile-page {
  min-height: calc(100vh - 100px);
  position: relative;
}

.intro-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  backdrop-filter: blur(4px);
}

.intro-panel {
  background: #fff;
  border-radius: 20px;
  padding: 36px 32px;
  max-width: 960px;
  width: 100%;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.18);
  h2 { margin: 0 0 8px; text-align: center; font-size: 22px; }
  .intro-desc { text-align: center; color: $text-secondary; margin: 0 0 28px; font-size: 14px; }
  .skip-btn { display: block; margin: 20px auto 0; }
}

.page-title {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
  h2 { margin: 0 0 4px; font-size: 20px; }
  .subtitle { margin: 0; color: $text-secondary; font-size: 13px; }
}

.mode-tabs { margin-bottom: 16px; }

.fusion-hint {
  margin: 0 0 10px;
  font-size: 12px;
  color: $text-secondary;
  padding: 8px 12px;
  background: linear-gradient(90deg, rgba(37,99,235,0.06), rgba(124,58,237,0.04));
  border-radius: 8px;
  border-left: 3px solid $primary;
}
.load-alert { margin-bottom: 12px; }

.workspace-row {
  align-items: stretch;

  :deep(> .el-col) {
    display: flex;
    flex-direction: column;
  }
}

.main-panel {
  flex: 1;
  width: 100%;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  /* 与右侧雷达+维度卡片同高，底部对齐 */
  align-self: stretch;
  height: 100%;
  min-height: 560px;
}

.mode-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}

.side-stack {
  flex: 1;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-self: stretch;
  min-height: 560px;
}

.side-panel {
  padding: 20px;
  flex-shrink: 0;
  h3 { margin: 0; font-size: 15px; }
  .panel-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }
}

.edit-hint { margin-bottom: 12px; color: $text-secondary; font-size: 13px; }

.mode-fade-enter-active,
.mode-fade-leave-active { transition: opacity 0.3s ease; }
.mode-fade-enter-from,
.mode-fade-leave-to { opacity: 0; }
</style>
