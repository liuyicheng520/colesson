<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Plus, Delete, Fold, Expand } from '@element-plus/icons-vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useTutorChat } from '@/composables/useTutorChat'
import { useVideoGeneration } from '@/composables/useVideoGeneration'
import { useProfileStore } from '@/stores/profile'
import { useUserStore } from '@/stores/user'
import { getSessionTitle } from '@/api/tutor'
import { formatProfileForStudent } from '@/utils/profileDisplay'
import { formatBeijingFriendly } from '@/utils/datetime'
import TutorStreamChat from '@/components/TutorStreamChat.vue'
import TutorOutlinePanel from '@/components/tutor/TutorOutlinePanel.vue'
import TutorSlideDeck from '@/components/tutor/TutorSlideDeck.vue'
import TutorGenerationSteps from '@/components/tutor/TutorGenerationSteps.vue'
import TutorFloatingSettings from '@/components/tutor/TutorFloatingSettings.vue'
import TutorVideoGenerationModal from '@/components/tutor/TutorVideoGenerationModal.vue'
import type { TutorSessionData } from '@/types'
import type { TutorChatMessage } from '@/composables/useTutorChat'
import { systemApi, type PublicSystemInfo } from '@/api/system'

const route = useRoute()
const router = useRouter()
const profileStore = useProfileStore()
const userStore = useUserStore()
const chatRef = ref<InstanceType<typeof TutorStreamChat>>()
const slideDeckRef = ref<InstanceType<typeof TutorSlideDeck>>()

const {
  sessionNo,
  messages,
  sessions,
  sessionsLoading,
  streaming,
  error,
  lastMeta,
  tutorMode,
  profileAdaptEnabled,
  answerDetail,
  showSteps,
  deepMode,
  webSearchEnabled,
  documentIds,
  documents,
  uploadProgress,
  uploading,
  uploadError,
  pendingOutline,
  genProgress,
  genPhase,
  activeSlides,
  slideIndex,
  showSlideDeck,
  send,
  stopStream,
  activeTool,
  toolLoading,
  initSession,
  loadSession,
  deleteSession,
  newSession,
  retryLast,
  confirmOutline,
  uploadDocument,
  retryUpload,
  removeDocument,
  toggleDocument,
  syncSettings,
  registerVideoGeneration,
  appendAssistantNote,
  lastVideoLectureId,
} = useTutorChat()

const videoGen = useVideoGeneration({
  getSessionNo: () => sessionNo.value,
  ensureSession: async (topic) => {
    if (!sessionNo.value) await initSession(topic, tutorMode.value)
    else await syncSettings()
  },
  getStreamOptions: () => ({
    web_search_enabled: webSearchEnabled.value,
    deep_mode: deepMode.value,
  }),
  onAssistantNote: (content, lecture) => appendAssistantNote(content, lecture),
  onComplete: (lectureId) => { lastVideoLectureId.value = lectureId },
})

registerVideoGeneration((topic) => videoGen.open(topic))

onBeforeUnmount(() => {
  registerVideoGeneration(null)
  videoGen.close()
})

const historyCollapsed = ref(false)
const settingsOpen = ref(false)
const publicInfo = ref<PublicSystemInfo | null>(null)

const features = computed(() => publicInfo.value?.features ?? {
  web_search: true,
  deep_mode: true,
  image_gen: true,
  video_lecture: true,
  voice_input: true,
})

const modes = [
  { value: 'socratic', label: '基础讲解模式', desc: '概念清晰、分步讲解，适合夯实基础知识' },
  { value: 'hint', label: '应试提分模式', desc: '分级提示、考点聚焦，助力考试冲刺提分' },
  { value: 'encourage', label: '启发引导模式', desc: '提问引导思考，培养独立解题能力' },
]

const quickPrompts = [
  { label: '讲解知识点', text: '请帮我系统讲解一下这个知识点的核心概念、原理和应用场景' },
  { label: '生成练习题', text: '请根据当前知识点为我生成 3 道练习题并给出思路提示' },
  { label: '错题分析', text: '我在这道题上出错了，请帮我分析错因并指出知识漏洞' },
  { label: '拓展延伸', text: '请对这个知识点做拓展延伸，介绍进阶应用和相关联系' },
]

const detailOptions = [
  { value: 'brief', label: '简洁' },
  { value: 'normal', label: '标准' },
  { value: 'detailed', label: '详细' },
]

const profileDisplayRows = computed(() =>
  formatProfileForStudent(profileStore.profile, userStore.userInfo?.major),
)

function formatTime(iso: string) {
  return formatBeijingFriendly(iso, '')
}

function sessionTime(s: TutorSessionData) {
  return formatTime(s.updated_at || s.created_at)
}

async function handleSend(content: string) {
  await send(content, false)
}

async function handleRequestFull() {
  const lastUser = [...messages.value].reverse().find((m) => m.role === 'user')
  if (lastUser) await send('请给出完整解析', true)
}

async function handleQuickPrompt(text: string) {
  if (!sessionNo.value) await initSession(text.slice(0, 100), tutorMode.value)
  await send(text, false)
}

function handleStop() {
  stopStream()
}

async function handleNewChat() {
  if (streaming.value) return
  newSession()
}

async function handleSelectSession(no: string) {
  if (no === sessionNo.value || streaming.value) return
  await loadSession(no)
  router.replace({ query: { ...route.query, session_no: no } })
}

async function handleDeleteSession(no: string, e: Event) {
  e.stopPropagation()
  try {
    await ElMessageBox.confirm('确定删除该会话？删除后无法恢复。', '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteSession(no)
    if (route.query.session_no === no) {
      const q = { ...route.query }
      delete q.session_no
      router.replace({ query: q })
    }
  } catch { /* cancelled */ }
}

async function handleDocUpload(file: File) {
  try {
    await uploadDocument(file)
    ElMessage.success(`${file.name} 上传成功`)
  } catch {
    /* error shown in doc bar */
  }
}

async function handleRemoveDocument(docId: string) {
  try {
    await removeDocument(docId)
    ElMessage.success('文档已移除')
  } catch (e) {
    ElMessage.error((e as Error).message || '删除失败')
  }
}

async function navigateToLectureGenerate(topic: string, sourceText?: string) {
  if (!sessionNo.value) {
    await initSession(topic.slice(0, 100), tutorMode.value)
  }
  const key = `edunexus_lecture_gen_${sessionNo.value}`
  sessionStorage.setItem(`${key}_source`, sourceText?.slice(0, 4000) || '')
  sessionStorage.setItem(key, JSON.stringify({
    sessionNo: sessionNo.value,
    topic,
    status: 'generating',
    jobStartedAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }))
  // 使用 replace 避免生成页被浏览器后退立刻带回对话页
  await router.replace({
    path: '/student/tutor/lecture/generate',
    query: { session_no: sessionNo.value, topic: topic.slice(0, 120) },
  })
}

async function handleStartLecture(msg: TutorChatMessage) {
  const lectureId =
    msg.meta?.lecture_id ||
    videoGen.lecture.value?.lecture_id ||
    lastVideoLectureId.value
  if (lectureId && sessionNo.value) {
    await router.push({
      path: `/student/tutor/lecture/${lectureId}`,
      query: { session_no: sessionNo.value },
    })
    return
  }
  const lastUser = [...messages.value].reverse().find((m) => m.role === 'user')
  const topic = lastUser?.content?.slice(0, 120) || '知识点讲解'
  await navigateToLectureGenerate(topic, msg.content)
}

function handleSTT(text: string) {
  chatRef.value?.fillInput(text)
}

function handleSlideAsk(text: string) {
  send(text, false)
}

async function handleSettingsChange() {
  if (!sessionNo.value) return
  try {
    await syncSettings()
  } catch {
    /* 设置同步失败不阻断对话 */
  }
}

function handleOpenSlides(msg: TutorChatMessage) {
  const slides = msg.slides || (msg.meta?.slides as typeof activeSlides.value) || []
  if (slides.length) {
    activeSlides.value = slides
    slideIndex.value = 0
    showSlideDeck.value = true
  }
}

function cancelOutline() {
  pendingOutline.value = null
  genPhase.value = 'idle'
}

function goResource(id: number) {
  router.push(`/student/resources/${id}`)
}

const isMobile = computed(() => typeof window !== 'undefined' && window.innerWidth < 992)

onMounted(async () => {
  await profileStore.fetchProfile()
  // 有历史会话时自动选中最近一条，避免空态死路
  try {
    if (!sessionNo.value && sessions.value.length) {
      await loadSession(sessions.value[0].session_no)
    }
  } catch { /* 静默 */ }
  try {
    publicInfo.value = await systemApi.publicInfo()
    if (!features.value.web_search) webSearchEnabled.value = false
    if (!features.value.deep_mode) deepMode.value = false
  } catch {
    /* ignore */
  }
  if (isMobile.value) {
    historyCollapsed.value = true
  }
  const topic = route.query.topic as string | undefined
  if (topic && !sessionNo.value) {
    await initSession(topic, tutorMode.value)
    await send(topic, false)
  }
})
</script>

<template>
  <div class="tutor-page">
    <aside class="history-panel" :class="{ collapsed: historyCollapsed }">
      <div class="history-header">
        <el-button
          v-show="!historyCollapsed"
          type="primary"
          class="new-chat-btn"
          :icon="Plus"
          :disabled="streaming"
          @click="handleNewChat"
        >
          新建对话
        </el-button>
        <el-button
          :icon="historyCollapsed ? Expand : Fold"
          text
          class="collapse-btn"
          :aria-label="historyCollapsed ? '展开历史会话' : '收起历史会话'"
          @click="historyCollapsed = !historyCollapsed"
        />
      </div>
      <div v-show="!historyCollapsed" v-loading="sessionsLoading" class="history-list">
        <div
          v-for="s in sessions"
          :key="s.session_no"
          class="history-item"
          :class="{ active: s.session_no === sessionNo }"
          @click="handleSelectSession(s.session_no)"
        >
          <div class="history-item-main">
            <span class="history-title">{{ getSessionTitle(s) }}</span>
            <span class="history-time">{{ sessionTime(s) }}</span>
          </div>
          <el-button class="delete-btn" :icon="Delete" text size="small" @click="handleDeleteSession(s.session_no, $event)" />
        </div>
        <div v-if="!sessions.length && !sessionsLoading" class="history-empty">暂无历史会话</div>
      </div>
    </aside>

    <main class="chat-panel">
      <header class="chat-header">
        <div class="header-left">
          <h2>智能答疑辅导</h2>
          <p class="subtitle">多模态 · 文档问答 · 联网检索 · 幻灯片讲解 · 语音交互</p>
        </div>
        <div class="header-right" />
      </header>

      <TutorGenerationSteps
        v-if="!videoGen.visible.value && (genPhase === 'outline' || genPhase === 'confirm' || genPhase === 'modules')"
        :phase="genPhase"
        :progress-message="genProgress"
      />

      <TutorOutlinePanel
        v-if="!videoGen.visible.value && pendingOutline?.length"
        :outline="pendingOutline"
        :loading="streaming"
        @confirm="confirmOutline"
        @cancel="cancelOutline"
      />

      <TutorSlideDeck
        v-if="showSlideDeck && activeSlides.length"
        ref="slideDeckRef"
        v-model="slideIndex"
        :slides="activeSlides"
        @ask="handleSlideAsk"
      />

      <TutorStreamChat
        ref="chatRef"
        class="tutor-stream-host"
        :messages="messages"
        :streaming="streaming"
        :error="error"
        :gen-progress="genProgress"
        :show-voice-controls="features.voice_input"
        :documents="documents"
        :active-document-ids="documentIds"
        :uploading="uploading"
        :upload-progress="uploadProgress"
        :upload-error="uploadError"
        v-model:deep-mode="deepMode"
        v-model:web-search-enabled="webSearchEnabled"
        :show-deep-mode="features.deep_mode"
        :show-web-search="features.web_search"
        :enable-image="features.image_gen"
        :enable-video="features.video_lecture"
        :enable-voice="features.voice_input"
        v-model:active-tool="activeTool"
        :tool-loading="toolLoading"
        rich
        placeholder="输入问题开始对话；生成思维导图可点工具箱，或直接说「生成xx思维导图」…"
        @send="handleSend"
        @stop="handleStop"
        @request-full="handleRequestFull"
        @retry="retryLast"
        @open-slides="handleOpenSlides"
        @start-lecture="handleStartLecture"
        @upload="handleDocUpload"
        @remove-document="handleRemoveDocument"
        @toggle-document="toggleDocument"
        @retry-upload="retryUpload"
        @stt-result="handleSTT"
        @settings-change="handleSettingsChange"
      >
        <template #quickPrompts>
          <div v-if="!messages.length" class="prompt-row empty-prompts">
            <span class="prompt-label">试试这样问</span>
            <div class="prompt-btns">
              <el-button
                v-for="p in quickPrompts"
                :key="p.label"
                size="small"
                round
                :disabled="streaming"
                @click="handleQuickPrompt(p.text)"
              >
                {{ p.label }}
              </el-button>
            </div>
          </div>
          <div v-else class="prompt-row">
            <span class="prompt-label">快速提问</span>
            <div class="prompt-btns">
              <el-button
                v-for="p in quickPrompts"
                :key="p.label"
                size="small"
                round
                :disabled="streaming"
                @click="handleQuickPrompt(p.text)"
              >
                {{ p.label }}
              </el-button>
            </div>
          </div>
        </template>
      </TutorStreamChat>

      <div v-if="lastMeta?.knowledge_points?.length || lastMeta?.related_resources?.length" class="meta-bar">
        <div v-if="lastMeta?.knowledge_points?.length" class="meta-section">
          <span class="meta-label">关联知识点</span>
          <el-tag v-for="kp in lastMeta.knowledge_points" :key="kp.point_code" size="small" type="primary" effect="plain">
            {{ kp.point_name }}
          </el-tag>
        </div>
        <div v-if="lastMeta?.related_resources?.length" class="meta-section">
          <span class="meta-label">推荐资源</span>
          <span v-for="r in lastMeta.related_resources" :key="r.resource_id" class="res-chip" @click="goResource(r.resource_id)">
            {{ r.title }}
          </span>
        </div>
      </div>
    </main>

    <TutorFloatingSettings v-model:open="settingsOpen">
      <div class="settings-block priority-high">
        <h4>辅导模式</h4>
        <el-radio-group v-model="tutorMode" class="mode-group" @change="handleSettingsChange">
          <el-radio v-for="m in modes" :key="m.value" :value="m.value" border>
            <strong>{{ m.label }}</strong>
            <span class="mode-desc">{{ m.desc }}</span>
          </el-radio>
        </el-radio-group>
        <p class="field-hint">修改后对下一条回复生效</p>
      </div>

      <div class="settings-block">
        <h4>回答偏好</h4>
        <div class="field-row">
          <span class="field-label">详细程度</span>
          <el-segmented v-model="answerDetail" :options="detailOptions" size="small" @change="handleSettingsChange" />
        </div>
        <div class="field-row switch-row">
          <span class="field-label">展示步骤</span>
          <el-switch v-model="showSteps" @change="handleSettingsChange" />
        </div>
      </div>

      <div class="settings-block priority-low">
        <div class="switch-row">
          <h4>画像适配</h4>
          <el-switch v-model="profileAdaptEnabled" @change="handleSettingsChange" />
        </div>
        <dl v-if="profileAdaptEnabled && profileDisplayRows.length" class="profile-display">
          <div v-for="row in profileDisplayRows" :key="row.label" class="profile-row">
            <dt>{{ row.label }}</dt>
            <dd>{{ row.value }}</dd>
          </div>
        </dl>
        <p v-else-if="profileAdaptEnabled" class="field-hint">暂无画像数据，请前往「画像构建」完善学习画像</p>
        <p class="field-hint">
          {{ profileAdaptEnabled
            ? `已启用 · 完整度 ${((profileStore.profile?.completeness || 0) * 100).toFixed(0)}%`
            : '关闭后按通用水平答疑' }}
        </p>
      </div>
    </TutorFloatingSettings>

    <TutorVideoGenerationModal
      :session-no="sessionNo"
      :video-gen="videoGen"
      @close="lastVideoLectureId = videoGen.lecture.value?.lecture_id || lastVideoLectureId"
    />
  </div>
</template>

<style scoped lang="scss">
.tutor-page {
  display: flex;
  height: calc(100vh - 100px);
  gap: 0;
  background: $bg-page;
  border-radius: $radius-lg;
  overflow: hidden;
  position: relative;
}

.history-panel {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-right: 1px solid $border-color;
  transition: width 0.25s ease;
  &.collapsed { width: 48px; .history-header { justify-content: center; padding: 12px 8px; } }
}

.history-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 12px 12px;
  border-bottom: 1px solid $border-color;
  .new-chat-btn { flex: 1; font-weight: 600; }
}

.history-list { flex: 1; overflow-y: auto; padding: 8px; }

.history-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  &:hover { background: #f1f5f9; .delete-btn { opacity: 1; } }
  &.active { background: #eff6ff; border-left: 3px solid $primary; padding-left: 9px; }
}

.history-item-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.history-title { font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.history-time { font-size: 11px; color: $text-secondary; }
.delete-btn { opacity: 0; flex-shrink: 0; &:hover { color: $danger; } }
.history-empty { text-align: center; color: $text-secondary; font-size: 13px; padding: 24px 0; }

.chat-panel {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 16px 20px 12px;
  gap: 0;
}

.tutor-stream-host {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-shrink: 0;
  margin-bottom: 12px;
  h2 { margin: 0 0 4px; font-size: 20px; font-weight: 700; }
  .subtitle { margin: 0; font-size: 12px; color: $text-secondary; }
  .header-right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
}

.prompt-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding-bottom: 10px; }
.empty-prompts {
  padding: 12px 14px;
  border-radius: 12px;
  background: #f8fbff;
  border: 1px dashed #bfdbfe;
  width: 100%;
  box-sizing: border-box;
}
.prompt-label { font-size: 12px; color: $text-secondary; flex-shrink: 0; }
.prompt-btns { display: flex; flex-wrap: wrap; gap: 8px; }

.meta-bar {
  flex-shrink: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  padding: 10px 14px;
  margin-top: 12px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid $border-color;
  font-size: 12px;
}
.meta-section { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.meta-label { color: $text-secondary; margin-right: 4px; }
.res-chip {
  color: $primary; cursor: pointer; padding: 2px 8px; border-radius: 4px; background: #eff6ff;
  &:hover { background: #dbeafe; }
}

@media (max-width: 991px) {
  .history-panel.collapsed { width: 40px; }
}
</style>
