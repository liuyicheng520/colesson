<script setup lang="ts">
import { computed, onMounted, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  items: Array<{
    type?: string
    title?: string
    content?: string
    answer?: string
    steps?: string[]
  }>
  explanation?: string
  objective?: string
  practiceType?: string
  /** 用于草稿持久化的稳定键（资源 id 等）；缺省时退化为练习标题 */
  resourceKey?: string
}>()

const typeLabels: Record<string, string> = {
  grammar_fill: '语法填空',
  translation: '翻译练习',
  dialogue: '情景对话',
  calculation: '计算应用',
  proof: '证明题',
  application: '应用题',
  exercise: '实操练习',
}

type SelfCheck = '' | 'mastered' | 'retry'
const draftKey = (i: number) => `practice_draft:${props.resourceKey || 'default'}:${i}`
const checkKey = (i: number) => `practice_check:${props.resourceKey || 'default'}:${i}`

const drafts = reactive<string[]>(props.items.map(() => ''))
const checks = reactive<SelfCheck[]>(props.items.map(() => ''))
const revealed = reactive<boolean[]>(props.items.map(() => false))

function loadPersisted() {
  props.items.forEach((_, i) => {
    try {
      drafts[i] = localStorage.getItem(draftKey(i)) || ''
      checks[i] = (localStorage.getItem(checkKey(i)) as SelfCheck) || ''
    } catch { /* localStorage 不可用时静默降级为纯浏览 */ }
  })
}

function persistDraft(i: number) {
  try {
    localStorage.setItem(draftKey(i), drafts[i])
  } catch { /* ignore */ }
}

function persistCheck(i: number) {
  try {
    if (checks[i]) localStorage.setItem(checkKey(i), checks[i])
    else localStorage.removeItem(checkKey(i))
  } catch { /* ignore */ }
}

function reveal(i: number) {
  revealed[i] = true
}

function resetItem(i: number) {
  drafts[i] = ''
  checks[i] = ''
  revealed[i] = false
  try {
    localStorage.removeItem(draftKey(i))
    localStorage.removeItem(checkKey(i))
  } catch { /* ignore */ }
  ElMessage.success('本练习已重置')
}

const doneCount = computed(() => checks.filter((c) => c).length)

const checkLabels: Record<string, string> = {
  mastered: '已掌握',
  retry: '需再练',
}

watch(
  () => props.items.length,
  () => {
    // 详情异步加载完成后重建状态数组（保持已有草稿不丢）
    const n = props.items.length
    while (drafts.length > n) drafts.pop()
    while (checks.length > n) checks.pop()
    while (revealed.length > n) revealed.pop()
    while (drafts.length < n) drafts.push('')
    while (checks.length < n) checks.push('')
    while (revealed.length < n) revealed.push(false)
    loadPersisted()
  },
  { immediate: true },
)
onMounted(loadPersisted)
</script>

<template>
  <div class="practice-viewer">
    <el-alert v-if="objective" type="info" :closable="false" show-icon :title="`练习目标：${objective}`" />
    <div v-if="items.length" class="practice-overview">
      <span>共 {{ items.length }} 个实战任务 · 已自测 {{ doneCount }}/{{ items.length }}</span>
      <span>先在下方写出你的思路，再对照参考答案自评</span>
    </div>
    <div v-for="(item, i) in items" :key="i" class="practice-item card">
      <div class="item-head">
        <el-tag size="small" type="primary">{{ typeLabels[item.type || ''] || item.type || '练习' }}</el-tag>
        <strong>{{ item.title || `练习 ${i + 1}` }}</strong>
        <el-tag v-if="checks[i]" size="small" :type="checks[i] === 'mastered' ? 'success' : 'warning'" class="self-tag">
          {{ checkLabels[checks[i]] }}
        </el-tag>
      </div>
      <div class="item-content">{{ item.content }}</div>
      <el-input
        v-model="drafts[i]"
        type="textarea"
        :rows="3"
        maxlength="2000"
        placeholder="写下你的作答或思路（自动保存草稿）…"
        @input="persistDraft(i)"
      />
      <div class="item-actions">
        <el-button size="small" type="primary" plain :disabled="revealed[i]" @click="reveal(i)">
          {{ revealed[i] ? '参考答案已展开' : '对照参考答案' }}
        </el-button>
        <template v-if="revealed[i]">
          <span class="self-label">自评：</span>
          <el-radio-group
            :model-value="checks[i]"
            size="small"
            @update:model-value="(v: string | number | boolean | undefined) => { checks[i] = (v as SelfCheck); persistCheck(i) }"
          >
            <el-radio-button value="mastered">已掌握</el-radio-button>
            <el-radio-button value="retry">需再练</el-radio-button>
          </el-radio-group>
        </template>
        <el-button v-if="drafts[i] || checks[i] || revealed[i]" text size="small" @click="resetItem(i)">重置</el-button>
      </div>
      <div v-show="revealed[i]" class="ref-answer">
        <p v-if="item.answer"><strong>答案：</strong>{{ item.answer }}</p>
        <ol v-if="item.steps?.length">
          <li v-for="(s, j) in item.steps" :key="j">{{ s }}</li>
        </ol>
        <p v-if="!item.answer && !item.steps?.length" class="muted">暂无参考答案</p>
      </div>
    </div>
    <div v-if="explanation" class="explain">
      <h4>学习要点</h4>
      <p>{{ explanation }}</p>
    </div>
  </div>
</template>

<style scoped lang="scss">
.practice-viewer { display: flex; flex-direction: column; gap: 16px; }
.practice-overview {
  display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;
  padding: 10px 14px; border-radius: 10px; background: #f8fafc; color: $text-secondary; font-size: 13px;
  span:first-child { color: $primary; font-weight: 700; }
}
.practice-item {
  padding: 20px;
  .item-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
  .item-content { white-space: pre-wrap; line-height: 1.7; margin: 0 0 12px; }
  .item-actions {
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 12px;
    .self-label { color: $text-secondary; font-size: 13px; }
  }
  .self-tag { margin-left: auto; }
  .ref-answer {
    margin-top: 12px; padding: 12px 14px; border-radius: 8px;
    background: #f8fafc; border: 1px solid #e2e8f0;
    p, ol { margin: 0; line-height: 1.7; }
    ol { padding-left: 20px; }
    .muted { color: $text-secondary; }
  }
}
.explain {
  padding: 16px;
  background: #f0f9ff;
  border-radius: 8px;
  h4 { margin: 0 0 8px; color: $primary; }
  p { margin: 0; line-height: 1.7; color: $text-secondary; }
}
</style>
