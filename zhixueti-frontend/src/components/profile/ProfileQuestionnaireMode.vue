<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { profileApi } from '@/api/profile'
import type { QuestionnaireItem } from '@/types'

const emit = defineEmits<{ submitted: []; 'go-dialogue': [] }>()

const items = ref<QuestionnaireItem[]>([])
const currentIndex = ref(0)
const answers = ref<Record<string, string>>({})
const submitting = ref(false)
const loading = ref(true)

const current = computed(() => items.value[currentIndex.value])
const progress = computed(() => Math.round(((currentIndex.value) / items.value.length) * 100))
const isLast = computed(() => currentIndex.value >= items.value.length - 1)

onMounted(async () => {
  try {
    items.value = await profileApi.getQuestionnaire()
    const cached = sessionStorage.getItem('profile_questionnaire_answers')
    if (cached) answers.value = JSON.parse(cached)
  } catch {
    ElMessage.error('问卷加载失败')
  } finally {
    loading.value = false
  }
})

function selectOption(optionId: string) {
  if (!current.value) return
  answers.value[current.value.dimension_code] = optionId
  sessionStorage.setItem('profile_questionnaire_answers', JSON.stringify(answers.value))
}

function next() {
  if (!current.value || !answers.value[current.value.dimension_code]) {
    ElMessage.warning('请选择一个选项')
    return
  }
  if (isLast.value) submit()
  else currentIndex.value += 1
}

function prev() {
  if (currentIndex.value > 0) currentIndex.value -= 1
}

async function submit() {
  if (items.value.some((i) => !answers.value[i.dimension_code])) {
    ElMessage.warning('请完成全部题目')
    return
  }
  submitting.value = true
  try {
    await profileApi.submitQuestionnaire({
      answers: items.value.map((i) => ({
        dimension_code: i.dimension_code,
        option_id: answers.value[i.dimension_code],
      })),
    })
    sessionStorage.removeItem('profile_questionnaire_answers')
    ElMessage.success('问卷基线已写入（权重 30%），可与对话/测评结果加权融合')
    emit('submitted')
    try {
      await ElMessageBox.confirm(
        '问卷仅提供基础画像。切换至「对话引导式」可针对每个维度 3 轮深挖，权重更高，雷达图将显著精准。是否立即深化？',
        '建议下一步',
        { confirmButtonText: '去对话深化', cancelButtonText: '稍后再说', type: 'info' },
      )
      emit('go-dialogue')
    } catch {
      /* user dismissed */
    }
  } catch {
    ElMessage.error('提交失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div v-loading="loading" class="questionnaire-mode">
    <div v-if="current" class="q-card">
      <div class="q-header">
        <span>第 {{ currentIndex + 1 }} / {{ items.length }} 题</span>
        <el-progress :percentage="progress" :stroke-width="6" style="flex:1; max-width: 200px" />
      </div>
      <h3>{{ current.question }}</h3>
      <div class="options">
        <button
          v-for="opt in current.options"
          :key="opt.id"
          type="button"
          class="option-btn"
          :class="{ selected: answers[current.dimension_code] === opt.id }"
          @click="selectOption(opt.id)"
        >
          {{ opt.label }}
        </button>
      </div>
      <div class="actions">
        <el-button v-if="currentIndex > 0" @click="prev">上一题</el-button>
        <el-button type="primary" :loading="submitting" @click="next">
          {{ isLast ? '提交生成画像' : '下一题' }}
        </el-button>
      </div>
    </div>
    <p class="hint">提交后立即生成基础画像，覆盖约 80% 核心信息</p>
  </div>
</template>

<style scoped lang="scss">
.questionnaire-mode {
  padding: 8px 0;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.q-card {
  flex: 1;
  padding: 24px;
  background: #fff;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  animation: fadeIn 0.3s ease;
  h3 { margin: 20px 0; font-size: 17px; line-height: 1.5; }
}
.q-header {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 13px;
  color: $text-secondary;
}
.options {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.option-btn {
  text-align: left;
  padding: 14px 18px;
  border-radius: 10px;
  border: 2px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.25s ease;
  &:hover { border-color: rgba(37, 99, 235, 0.4); background: #eff6ff; }
  &.selected {
    border-color: $primary;
    background: linear-gradient(135deg, rgba(37,99,235,0.08), rgba(124,58,237,0.06));
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.12);
  }
}
.actions {
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
.hint {
  margin-top: 12px;
  font-size: 12px;
  color: $text-secondary;
  text-align: center;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
