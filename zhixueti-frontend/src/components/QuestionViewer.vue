<script setup lang="ts">
import { reactive, computed } from 'vue'
import { CircleCheck, CircleClose } from '@element-plus/icons-vue'

const props = defineProps<{
  questions: Array<{
    question_type: string
    stem: string
    options?: string[]
    answer: unknown
    analysis?: string
    difficulty?: number
    error_type?: string
    knowledge_point?: string
  }>
}>()

const typeLabel: Record<string, string> = {
  single_choice: '单选题',
  multi_choice: '多选题',
  fill_blank: '填空题',
  short_answer: '简答题',
  coding: '编程题',
}

/** 每题答题状态 */
interface QuestionState {
  selected: string[]
  textAnswer: string
  submitted: boolean
  correct: boolean | null
}

const states = reactive<Record<number, QuestionState>>({})

function getState(index: number): QuestionState {
  if (!states[index]) {
    states[index] = { selected: [], textAnswer: '', submitted: false, correct: null }
  }
  return states[index]
}

/** 从选项文本提取字母标识 A/B/C/D */
function optionKey(opt: string, index: number): string {
  const m = opt.match(/^([A-Da-d])[.\)、\s]/)
  return m ? m[1].toUpperCase() : String.fromCharCode(65 + index)
}

function normalizeAnswer(answer: unknown): string[] {
  if (Array.isArray(answer)) return answer.map(String).map((a) => a.toUpperCase())
  const s = String(answer).toUpperCase()
  if (s.length > 1 && !s.includes(',')) return s.split('').filter((c) => /[A-D]/.test(c))
  return s.split(/[,，、\s]+/).filter(Boolean).map((a) => a.replace(/[^A-D]/g, '')).filter(Boolean)
}

function isChoiceType(qType: string) {
  return qType === 'single_choice' || qType === 'multi_choice'
}

function isTextType(qType: string) {
  return qType === 'fill_blank' || qType === 'short_answer' || qType === 'coding'
}

function normalizeText(s: string) {
  return s.trim().toLowerCase().replace(/\s+/g, '').replace(/[。．.！!？?，,、；;：:]/g, '')
}

function selectOption(qIndex: number, key: string, qType: string) {
  const st = getState(qIndex)
  if (st.submitted) return
  if (qType === 'single_choice') {
    st.selected = [key]
    submitAnswer(qIndex)
  } else if (qType === 'multi_choice') {
    const idx = st.selected.indexOf(key)
    if (idx >= 0) st.selected.splice(idx, 1)
    else st.selected.push(key)
  }
}

function submitAnswer(qIndex: number) {
  const q = props.questions[qIndex]
  const st = getState(qIndex)
  if (st.submitted) return

  if (isChoiceType(q.question_type)) {
    const correctKeys = normalizeAnswer(q.answer)
    const selected = [...st.selected].sort()
    const expected = [...correctKeys].sort()
    st.submitted = true
    st.correct = selected.length === expected.length && selected.every((v, i) => v === expected[i])
    return
  }

  if (isTextType(q.question_type)) {
    if (!st.textAnswer.trim()) return
    st.submitted = true
    const expected = normalizeText(String(q.answer ?? ''))
    const given = normalizeText(st.textAnswer)
    // 填空题做宽松包含匹配；简答/编程只标记已提交，不做硬判对错
    if (q.question_type === 'fill_blank' && expected) {
      st.correct = given === expected || given.includes(expected) || expected.includes(given)
    } else {
      st.correct = null
    }
  }
}

function optionClass(qIndex: number, key: string, _qType: string): string {
  const st = getState(qIndex)
  const q = props.questions[qIndex]
  const correctKeys = normalizeAnswer(q.answer)
  const isSelected = st.selected.includes(key)
  const isCorrect = correctKeys.includes(key)

  if (!st.submitted) {
    return isSelected ? 'selected' : ''
  }
  if (isCorrect) return 'correct'
  if (isSelected && !isCorrect) return 'wrong'
  return ''
}

function resultText(qIndex: number): string {
  const c = getState(qIndex).correct
  if (c === null) return '已提交，请对照参考答案与解析'
  return c ? '回答正确' : '回答错误'
}

function resultType(qIndex: number): 'success' | 'error' | 'info' {
  const c = getState(qIndex).correct
  if (c === null) return 'info'
  return c ? 'success' : 'error'
}

const answeredCount = computed(() =>
  props.questions.filter((_, i) => getState(i).submitted).length,
)
</script>

<template>
  <div class="question-list">
    <div class="quiz-summary">
      已作答 {{ answeredCount }} / {{ questions.length }} 题
    </div>
    <div v-for="(q, i) in questions" :key="i" class="question-item card">
      <div class="q-header">
        <el-tag size="small">{{ typeLabel[q.question_type] || q.question_type }}</el-tag>
        <el-rate v-if="q.difficulty" :model-value="q.difficulty" disabled :max="5" size="small" />
        <el-tag v-if="q.knowledge_point" size="small" type="info">{{ q.knowledge_point }}</el-tag>
        <el-tag v-if="q.error_type" size="small" type="warning">易错: {{ q.error_type }}</el-tag>
      </div>
      <h4>{{ i + 1 }}. {{ q.stem }}</h4>

      <!-- 选择题交互 -->
      <div v-if="isChoiceType(q.question_type) && q.options?.length" class="options-grid">
        <button
          v-for="(opt, j) in q.options"
          :key="j"
          type="button"
          class="option-btn"
          :class="optionClass(i, optionKey(opt, j), q.question_type)"
          :disabled="getState(i).submitted"
          @click="selectOption(i, optionKey(opt, j), q.question_type)"
        >
          {{ opt }}
        </button>
      </div>

      <el-button
        v-if="q.question_type === 'multi_choice' && !getState(i).submitted"
        type="primary"
        size="small"
        :disabled="!getState(i).selected.length"
        style="margin-top: 12px"
        @click="submitAnswer(i)"
      >
        确认作答
      </el-button>

      <!-- 填空 / 简答 / 编程：先作答再看答案 -->
      <div v-if="isTextType(q.question_type)" class="text-answer">
        <el-input
          v-model="getState(i).textAnswer"
          :type="q.question_type === 'fill_blank' ? 'text' : 'textarea'"
          :rows="q.question_type === 'fill_blank' ? 1 : 4"
          :placeholder="q.question_type === 'fill_blank' ? '请填写答案' : '请先写下你的作答'"
          :disabled="getState(i).submitted"
        />
        <el-button
          v-if="!getState(i).submitted"
          type="primary"
          size="small"
          :disabled="!getState(i).textAnswer.trim()"
          style="margin-top: 12px"
          @click="submitAnswer(i)"
        >
          提交后查看答案
        </el-button>
      </div>

      <!-- 判分反馈：仅作答后显示 -->
      <div v-if="getState(i).submitted" class="result-bar" :class="resultType(i)">
        <el-icon>
          <CircleCheck v-if="getState(i).correct === true" />
          <CircleClose v-else-if="getState(i).correct === false" />
        </el-icon>
        <span>{{ resultText(i) }}</span>
      </div>

      <!-- 作答后才展开答案与解析 -->
      <transition name="fade">
        <div v-if="getState(i).submitted" class="analysis-block">
          <p><strong>参考答案：</strong>{{ typeof q.answer === 'object' ? JSON.stringify(q.answer) : q.answer }}</p>
          <p v-if="q.analysis"><strong>解析：</strong>{{ q.analysis }}</p>
        </div>
      </transition>
    </div>
  </div>
</template>

<style scoped lang="scss">
.question-list { display: flex; flex-direction: column; gap: 16px; }

.quiz-summary {
  font-size: 13px;
  color: $text-secondary;
  padding: 8px 12px;
  background: #f8fafc;
  border-radius: 8px;
}

.question-item {
  padding: 20px;
  h4 { margin: 12px 0; line-height: 1.6; }
}

.q-header { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }

.options-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}

.text-answer {
  margin-top: 12px;
}

.option-btn {
  text-align: left;
  padding: 12px 16px;
  border: 1.5px solid $border-color;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  font-size: 14px;
  line-height: 1.5;
  transition: all 0.15s ease;

  &:hover:not(:disabled) {
    border-color: $primary-light;
    background: #eff6ff;
    transform: scale(0.99);
  }

  &:active:not(:disabled) { transform: scale(0.97); }

  &.selected {
    border-color: $primary;
    background: #eff6ff;
    color: $primary-dark;
    font-weight: 500;
  }

  &.correct {
    border-color: $success;
    background: #ecfdf5;
    color: #047857;
  }

  &.wrong {
    border-color: $danger;
    background: #fef2f2;
    color: #b91c1c;
  }

  &:disabled { cursor: default; }
}

.result-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;

  &.success { background: #ecfdf5; color: #047857; }
  &.error { background: #fef2f2; color: #b91c1c; }
  &.info { background: #eff6ff; color: #1d4ed8; }
}

.analysis-block {
  margin-top: 16px;
  padding: 14px;
  background: #f8fafc;
  border-radius: 8px;
  border-left: 3px solid $primary;
  line-height: 1.7;
  p { margin: 6px 0; }
}

.fade-enter-active { transition: opacity 0.3s ease; }
.fade-enter-from { opacity: 0; }
</style>
