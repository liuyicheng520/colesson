<script setup lang="ts">
import { ref, watch } from 'vue'
import type { TutorOutlineItem } from '@/types'

const props = defineProps<{
  outline: TutorOutlineItem[]
  loading?: boolean
}>()

const emit = defineEmits<{
  confirm: [outline: TutorOutlineItem[]]
  cancel: []
}>()

const items = ref<TutorOutlineItem[]>([])

watch(
  () => props.outline,
  (v) => { items.value = v.map((o) => ({ ...o, objectives: [...(o.objectives || [])] })) },
  { immediate: true },
)

function addItem() {
  items.value.push({ title: '新小节', objectives: [''], duration_min: 5 })
}

function removeItem(i: number) {
  items.value.splice(i, 1)
}
</script>

<template>
  <div class="outline-panel">
    <div class="panel-head">
      <div class="head-left">
        <span class="pulse-dot" />
        <h4>课程大纲预览</h4>
      </div>
      <span class="hint">可编辑节点后确认生成</span>
    </div>

    <div class="outline-list">
      <div v-for="(item, i) in items" :key="i" class="outline-item">
        <span class="idx">{{ i + 1 }}</span>
        <div class="fields">
          <el-input v-model="item.title" placeholder="小节标题" />
          <el-input
            :model-value="(item.objectives || []).join('、')"
            placeholder="学习目标"
            @update:model-value="(v: string) => { item.objectives = v.split('、') }"
          />
        </div>
        <el-button text type="danger" @click="removeItem(i)">删</el-button>
      </div>
    </div>

    <div class="actions">
      <el-button size="small" @click="addItem">添加节点</el-button>
      <div class="right">
        <el-button @click="emit('cancel')">取消</el-button>
        <el-button type="primary" :loading="loading" @click="emit('confirm', items)">
          确认生成
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.outline-panel {
  margin: 12px 16px;
  padding: 16px;
  border-radius: 12px;
  border: 1px solid #bfdbfe;
  background: linear-gradient(135deg, #eff6ff, #fff);
  animation: slideIn 0.35s ease;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  h4 { margin: 0; font-size: 15px; }
  .hint { font-size: 12px; color: $text-secondary; }
}

.head-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: $primary;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.outline-list { display: flex; flex-direction: column; gap: 10px; }

.outline-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  .idx {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: $primary;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    flex-shrink: 0;
    margin-top: 6px;
  }
  .fields { flex: 1; display: flex; flex-direction: column; gap: 6px; }
}

.actions {
  display: flex;
  justify-content: space-between;
  margin-top: 14px;
  .right { display: flex; gap: 8px; }
}
</style>
