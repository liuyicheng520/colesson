<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { profileApi } from '@/api/profile'
import StreamChat from '@/components/StreamChat.vue'
import ProfileDimensionStepper from '@/components/ProfileDimensionStepper.vue'
import { parseUserInput, applySemanticPreview } from '@/profile/semanticParser'
import { stripLlmStreamMarkers } from '@/utils/llmStreamMarkers'
import type { DimensionProgressItem } from '@/types'

const props = defineProps<{
  dimensionProgress: DimensionProgressItem[]
  completedCount: number
  totalCount: number
  completedQuestions: number
  totalQuestions: number
}>()

const emit = defineEmits<{
  progress: [data: Partial<{
    dimension_progress: DimensionProgressItem[]
    completed_question_count: number
    current_dimension_code: string
    current_dimension_name: string
    current_question_index: number
  }>]
  updated: []
  'dimension-jump': [code: string]
}>()

const router = useRouter()
const sessionNo = ref('')
const sending = ref(false)
const messages = ref<{ id: string; role: 'user' | 'assistant'; content: string; streaming?: boolean }[]>([])
const localProgress = ref<DimensionProgressItem[]>([])
const currentDimension = ref<{ code: string; name: string } | null>(null)
const currentQuestionIndex = ref(1)
const previewKeywords = ref<string[]>([])
const softHint = ref('')
let msgId = 0

const FALLBACK_FIRST_Q =
  '你好！我是你的画像助教。先从学习基础问起：你目前最想补强的一门课或知识点是什么？用一两句话说说现状就好。'

const quickChips = computed(() => {
  const dim = currentDimension.value?.name || ''
  if (dim.includes('风格') || dim.includes('偏好')) {
    return [
      { label: '喜欢看视频讲解', text: '我更喜欢先看视频讲解，再自己动手练习巩固。' },
      { label: '喜欢读文档', text: '我更习惯先读文档和笔记，把概念理清再做题。' },
      { label: '边学边练', text: '我喜欢边学边练，讲一点就做几道相关练习。' },
    ]
  }
  if (dim.includes('目标') || dim.includes('诉求')) {
    return [
      { label: '期末冲刺', text: '我的目标是期末冲刺提分，希望路径偏考点与易错点。' },
      { label: '夯实基础', text: '我想先把基础概念打牢，再进入进阶内容。' },
      { label: '项目实战', text: '我更想做项目实战，少背理论，多动手落地。' },
    ]
  }
  if (dim.includes('基础') || dim.includes('知识')) {
    return [
      { label: '刚入门', text: '这方面我还是刚入门，很多概念只听过名字。' },
      { label: '学过一些', text: '我学过一些相关内容，但掌握不扎实，容易忘。' },
      { label: '比较熟悉', text: '基础概念我比较熟悉，主要卡在综合应用上。' },
    ]
  }
  return [
    { label: '用一句话介绍自己', text: '我是一名在校学生，希望系统提升课程掌握度。' },
    { label: '说说薄弱点', text: '我目前最薄弱的是基础概念，做题时经常卡壳。' },
    { label: '说说学习习惯', text: '我平时碎片时间学，更适合短讲解加小练习。' },
  ]
})

function isLikelyDetailedAnswer(content: string) {
  const compact = content.replace(/\s+/g, '')
  const invalid = new Set(['1', '2', '3', '4', '5', '嗯', '哦', 'ok', 'yes', 'no', '好的', '不知道', '随便', '无'])
  return compact.length >= 4 && !invalid.has(compact.toLowerCase())
}

watch(() => props.dimensionProgress, (v) => { localProgress.value = [...v] }, { immediate: true, deep: true })

onMounted(async () => {
  await initDialogue()
})

async function initDialogue() {
  messages.value = []
  sessionNo.value = ''
  softHint.value = ''
  try {
    const data = await profileApi.startDialogue()
    sessionNo.value = data.session_no
    const history = data.messages?.length
      ? data.messages
      : [{ role: 'assistant' as const, content: data.message || FALLBACK_FIRST_Q }]
    messages.value = history.map((m) => ({
      id: `m-${++msgId}`,
      role: m.role as 'user' | 'assistant',
      content: m.role === 'assistant' ? stripLlmStreamMarkers(m.content) : m.content,
    }))
    if (!messages.value.length || !messages.value.some((m) => m.role === 'assistant' && m.content.trim())) {
      messages.value = [{ id: `m-${++msgId}`, role: 'assistant', content: FALLBACK_FIRST_Q }]
    }
    syncFromApi(data)
  } catch {
    sessionNo.value = 'local-fallback'
    messages.value = [{ id: `m-${++msgId}`, role: 'assistant', content: FALLBACK_FIRST_Q }]
    ElMessage.warning('画像服务暂不可用，可先用下方快捷答法试答')
  }
}

function useChip(text: string) {
  softHint.value = ''
  void handleSend(text)
}

// 接口返回结构随模式变化，此处按字段读取，参数放宽为 any 以避免各模式自定义类型互相冲突
function syncFromApi(data: any) {
  if (data.dimension_progress) localProgress.value = data.dimension_progress as DimensionProgressItem[]
  if (data.current_dimension_code && data.current_dimension_name) {
    currentDimension.value = { code: data.current_dimension_code as string, name: data.current_dimension_name as string }
  }
  if (data.current_question_index != null) currentQuestionIndex.value = data.current_question_index as number
  emit('progress', {
    dimension_progress: localProgress.value,
    completed_question_count: data.completed_question_count as number | undefined,
    current_dimension_code: data.current_dimension_code as string | undefined,
    current_dimension_name: data.current_dimension_name as string | undefined,
    current_question_index: data.current_question_index as number | undefined,
  })
}

async function handleSend(content: string) {
  if (!sessionNo.value || sending.value) return
  if (sessionNo.value === 'local-fallback') {
    ElMessage.warning('画像服务未就绪，请稍后重试或刷新页面')
    return
  }
  if (!isLikelyDetailedAnswer(content)) {
    softHint.value = '再多说一点：补上「现状 / 原因 / 大概水平」中的任意两点，就能计入进度。'
    ElMessage.warning('请至少用一句完整的话说明具体情况；过短回答不会计入画像进度。')
    return
  }
  softHint.value = ''

  const parsed = parseUserInput(content, currentDimension.value?.code)
  previewKeywords.value = parsed.keywords
  localProgress.value = applySemanticPreview(localProgress.value, parsed.preview)
  emit('progress', { dimension_progress: localProgress.value })

  messages.value.push({ id: `m-${++msgId}`, role: 'user', content })
  const assistant = { id: `m-${++msgId}`, role: 'assistant' as const, content: '', streaming: true }
  messages.value.push(assistant)
  sending.value = true
  try {
    await profileApi.streamMessage(sessionNo.value, content, {
      onChunk: (text) => {
        assistant.content += text
      },
      onReplace: (text) => {
        assistant.content = text
      },
      onDone: (res) => {
        assistant.content = stripLlmStreamMarkers(res.assistant_message || assistant.content)
        assistant.streaming = false
        syncFromApi(res)
        emit('updated')
        if (res.is_completed) ElMessage.success('6维画像构建完成！')
        else if (res.updated_dimensions?.length) ElMessage.info(`已更新：${res.updated_dimensions.join('、')}`)
      },
    })
    assistant.streaming = false
  } catch (e) {
    const aborted = (e as Error).name === 'AbortError' || (e as DOMException).name === 'AbortError'
    assistant.content = aborted
      ? '响应超时或已中断，请重试；若经常超时，请检查 LLM API 配置'
      : '消息发送失败，请重试'
    assistant.streaming = false
  } finally {
    sending.value = false
  }
}

async function jumpDimension(code: string) {
  if (!sessionNo.value) return
  try {
    const data = await profileApi.switchDimension(sessionNo.value, code)
    messages.value.push({ id: `m-${++msgId}`, role: 'assistant', content: data.message })
    syncFromApi(data)
    emit('dimension-jump', code)
  } catch {
    ElMessage.error('维度切换失败')
  }
}

function openVoiceCall() {
  if (!sessionNo.value) {
    ElMessage.warning('会话尚未就绪，请稍候')
    return
  }
  router.push({
    path: '/student/profile-voice-call',
    query: { session_no: sessionNo.value },
  })
}

/** 从维度卡片详情弹窗跳转：切换维度并发送完善指令 */
async function continueFromCard(code: string, prompt: string) {
  if (!sessionNo.value) {
    ElMessage.warning('会话尚未就绪，请稍候再试')
    return
  }
  try {
    if (currentDimension.value?.code !== code) {
      await jumpDimension(code)
    }
  } catch {
    /* jump 失败仍尝试发送 */
  }
  await handleSend(prompt)
}

defineExpose({ jumpDimension, continueFromCard })
</script>

<template>
  <div class="dialogue-mode">
    <ProfileDimensionStepper
      v-if="localProgress.length"
      :items="localProgress"
      :completed-count="completedCount"
      :total-count="totalCount"
      :completed-questions="completedQuestions"
      :total-questions="totalQuestions"
      clickable
      class="stepper"
      @select="jumpDimension"
    />
    <div v-if="previewKeywords.length" class="keyword-bar">
      <span class="label">实时解析：</span>
      <el-tag v-for="kw in previewKeywords" :key="kw" size="small" effect="plain">{{ kw }}</el-tag>
    </div>
    <p class="answer-tip">请用完整句子回答；也可点下方快捷答法，再按需改几个字发送。</p>
    <p v-if="softHint" class="soft-hint">{{ softHint }}</p>
    <div v-if="!sending && messages.length" class="chip-row" aria-label="快捷答法">
      <button
        v-for="chip in quickChips"
        :key="chip.label"
        type="button"
        class="chip"
        :disabled="sending || !sessionNo"
        @click="useChip(chip.text)"
      >
        {{ chip.label }}
      </button>
    </div>
    <StreamChat
      :messages="messages"
      :streaming="sending"
      :placeholder="currentDimension ? `请回答「${currentDimension.name}」第 ${currentQuestionIndex} 问…` : '用一句话开始，或点快捷答法…'"
      class="chat-area"
      @send="handleSend"
      @call="openVoiceCall"
    />
  </div>
</template>

<style scoped lang="scss">
.dialogue-mode {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  height: 100%;

  .stepper { margin-bottom: 12px; flex-shrink: 0; }

  .chat-area {
    flex: 1 1 0;
    min-height: 0;
    width: 100%;
  }
}
.keyword-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
  padding: 8px 12px;
  background: #f0f9ff;
  border-radius: 8px;
  font-size: 12px;
  flex-shrink: 0;
  .label { color: $text-secondary; }
}
.answer-tip {
  margin: 0 0 8px;
  color: $text-secondary;
  font-size: 12px;
  line-height: 1.5;
  flex-shrink: 0;
}
.soft-hint {
  margin: 0 0 8px;
  padding: 8px 12px;
  border-radius: 8px;
  background: #fff7e6;
  color: #ad6800;
  font-size: 12px;
  line-height: 1.5;
  flex-shrink: 0;
}
.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
  flex-shrink: 0;
}
.chip {
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 999px;
  padding: 6px 14px;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}
.chip:hover:not(:disabled) {
  background: #dbeafe;
  border-color: #93c5fd;
}
.chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
