<script setup lang="ts">
import { useRouter } from 'vue-router'
import { WarningFilled } from '@element-plus/icons-vue'

const router = useRouter()
</script>

<template>
  <div class="forbidden-page">
    <div class="card forbidden-card">
      <el-icon class="icon" :size="64" color="#f59e0b"><WarningFilled /></el-icon>
      <h1>403</h1>
      <p>您没有访问该页面的权限</p>
      <p class="hint">请联系超级管理员分配相应菜单或操作权限</p>
      <div class="actions">
        <el-button type="primary" @click="router.push('/admin/dashboard')">返回首页</el-button>
        <el-button @click="router.back()">返回上一页</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.forbidden-page {
  min-height: calc(100vh - 120px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.forbidden-card {
  text-align: center;
  padding: 48px 40px;
  max-width: 420px;
  width: 100%;

  h1 {
    font-size: 48px;
    font-weight: 800;
    color: $text-primary;
    margin: 16px 0 8px;
  }

  p {
    color: $text-secondary;
    margin-bottom: 8px;
  }

  .hint {
    font-size: 13px;
    margin-bottom: 24px;
  }

  .actions {
    display: flex;
    gap: 12px;
    justify-content: center;
  }
}
</style>
