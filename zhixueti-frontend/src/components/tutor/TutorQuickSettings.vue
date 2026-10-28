<script setup lang="ts">
import { Connection, MagicStick } from '@element-plus/icons-vue'

const deepMode = defineModel<boolean>('deepMode', { required: true })
const webSearchEnabled = defineModel<boolean>('webSearchEnabled', { required: true })

withDefaults(defineProps<{
  showDeepMode?: boolean
  showWebSearch?: boolean
}>(), {
  showDeepMode: true,
  showWebSearch: true,
})

const emit = defineEmits<{
  change: []
}>()

function onToggle() {
  emit('change')
}
</script>

<template>
  <div class="quick-settings">
    <el-tooltip v-if="showDeepMode" content="深度思考：原理拆解 + 案例 + 易错点">
      <button
        type="button"
        class="pill"
        :class="{ active: deepMode }"
        @click="deepMode = !deepMode; onToggle()"
      >
        <el-icon><MagicStick /></el-icon>
        深度思考
      </button>
    </el-tooltip>
    <el-tooltip v-if="showWebSearch" content="联网搜索：检索权威资料并标注引用">
      <button
        type="button"
        class="pill"
        :class="{ active: webSearchEnabled }"
        @click="webSearchEnabled = !webSearchEnabled; onToggle()"
      >
        <el-icon><Connection /></el-icon>
        联网搜索
      </button>
    </el-tooltip>
  </div>
</template>

<style scoped lang="scss">
.quick-settings {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid $border-color;
  background: #fff;
  font-size: 12px;
  font-weight: 500;
  color: $text-secondary;
  cursor: pointer;
  transition: all 0.2s;

  &:hover { border-color: $primary; color: $primary; }

  &.active {
    background: linear-gradient(135deg, #eff6ff, #dbeafe);
    border-color: $primary;
    color: $primary;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.15);
  }
}
</style>
