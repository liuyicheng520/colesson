<script setup lang="ts">
defineProps<{ description?: string; actionText?: string }>()
defineEmits<{ action: [] }>()
</script>

<template>
  <div class="empty-state">
    <el-empty :description="description || '暂无数据'">
      <el-button v-if="actionText" type="primary" @click="$emit('action')">{{ actionText }}</el-button>
    </el-empty>
  </div>
</template>

<style scoped>
.empty-state { padding: 48px 0; }
</style>
