<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { profileApi } from '@/api/profile'
import { ASSESSMENT_BANK } from '@/profile/assessmentBank'
import {
  createAssessmentState,
  selectNextQuestion,
  recordAnswer,
  isConverged,
  initialThetaFromProfile,
  thetaToLevel,
  type AssessmentQuestion,
  type AssessmentState,
} from '@/profile/assessmentEngine'

const emit = defineEmits<{ submitted: [] }>()

const userStore = useUserStore()
const phase = ref<'intro' | 'testing' | 'done'>('intro')
const bank = ref<AssessmentQuestion[]>([...ASSESSMENT_BANK])
const state = ref<AssessmentState | null>(null)
const currentQ = ref<AssessmentQuestion | null>(null)
const selected = ref<number | null>(null)
const submitting = ref(false)

const abilityPercent = computed(() =>
  state.value ? Math.round(((state.value.theta + 2.5) / 5) * 100) : 50,
)
const progressPercent = computed(() =>
  state.value ? Math.round((state.value.answered.length / 15) * 100) : 0,
)

onMounted(() => {
  // 题库使用本地 IRT 引擎专用副本（含答案参数）
})

function startTest() {
  const user = userStore.userInfo
  const theta0 = initialThetaFromProfile(user?.grade, user?.major)
  state.value = createAssessmentState(theta0)
  currentQ.value = selectNextQuestion(state.value, bank.value as AssessmentQuestion[])
  phase.value = 'testing'
}

function confirmAnswer() {
  if (!state.value || !currentQ.value || selected.value === null) return
  const q = bank.value.find((b) => b.id === currentQ.value!.id)!
  state.value = recordAnswer(state.value, q, selected.value)
  selected.value = null

  if (isConverged(state.value)) {
    finishTest()
    return
  }
  currentQ.value = selectNextQuestion(state.value, bank.value as AssessmentQuestion[])
  if (!currentQ.value) finishTest()
}

async function finishTest() {
  if (!state.value) return
  phase.value = 'done'
  submitting.value = true
  try {
    await profileApi.submitAssessment({
      answers: state.value.answered.map((a) => ({
        question_id: a.questionId,
        selected_index: a.selectedIndex,
      })),
      theta: state.value.theta,
      standard_error: state.value.standardError,
    })
    ElMessage.success(`测评完成！知识水平估值：${thetaToLevel(state.value.theta)} 级`)
    emit('submitted')
  } catch {
    ElMessage.error('测评提交失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="assessment-mode">
    <div v-if="phase === 'intro'" class="intro-card">
      <h3>精准测评知识水平</h3>
      <p>系统将根据你的答题表现动态调整题目难度，用最少题目获得最精准的能力评估。</p>
      <ul>
        <li>基于简化 IRT（项目反应理论）自适应出题</li>
        <li>达到收敛阈值后自动结束，预计 3~5 分钟</li>
        <li>主要精准刻画「知识基础」维度，并补充其他维度基础标签</li>
      </ul>
      <el-button type="primary" size="large" @click="startTest">开始测评</el-button>
    </div>

    <div v-else-if="phase === 'testing' && currentQ && state" class="test-card">
      <div class="test-header">
        <span>第 {{ state.answered.length + 1 }} 题</span>
        <el-progress :percentage="progressPercent" :stroke-width="6" style="flex:1; max-width:180px" />
        <span class="theta">能力估值 {{ abilityPercent }}%</span>
      </div>
      <el-tag size="small" effect="plain">{{ currentQ.topic }}</el-tag>
      <h3>{{ currentQ.stem }}</h3>
      <div class="options">
        <button
          v-for="(opt, idx) in currentQ.options"
          :key="idx"
          type="button"
          class="option-btn"
          :class="{ selected: selected === idx }"
          @click="selected = idx"
        >
          {{ String.fromCharCode(65 + idx) }}. {{ opt }}
        </button>
      </div>
      <el-button type="primary" :disabled="selected === null" @click="confirmAnswer">确认作答</el-button>
    </div>

    <div v-else-if="phase === 'done' && state" class="done-card">
      <el-result icon="success" title="测评完成">
        <template #sub-title>
          能力值 θ = {{ state.theta.toFixed(2) }}，对应知识水平 {{ thetaToLevel(state.theta) }} 级
        </template>
        <template #extra>
          <el-button type="primary" :loading="submitting" @click="emit('submitted')">查看画像结果</el-button>
          <p class="hint">可切换至对话模式完善其他维度</p>
        </template>
      </el-result>
    </div>
  </div>
</template>

<style scoped lang="scss">
.assessment-mode { height: 100%; }
.intro-card, .test-card, .done-card {
  padding: 28px;
  background: #fff;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  animation: fadeIn 0.3s ease;
}
.intro-card {
  h3 { margin: 0 0 12px; }
  p { color: $text-secondary; line-height: 1.6; }
  ul { margin: 16px 0 24px; padding-left: 20px; color: #475569; font-size: 14px; li { margin: 6px 0; } }
}
.test-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  font-size: 13px;
  color: $text-secondary;
  .theta { color: $primary; font-weight: 600; }
}
.test-card h3 { margin: 16px 0 20px; font-size: 16px; line-height: 1.5; }
.options { display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; }
.option-btn {
  text-align: left;
  padding: 12px 16px;
  border-radius: 10px;
  border: 2px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
  transition: all 0.25s ease;
  &:hover { border-color: rgba(37,99,235,0.4); }
  &.selected { border-color: $primary; background: #eff6ff; }
}
.hint { margin-top: 12px; font-size: 12px; color: $text-secondary; }
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
