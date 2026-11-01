<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'
import ParticleNetworkBackground from '@/components/ParticleNetworkBackground.vue'

const router = useRouter()
const userStore = useUserStore()
const permissionStore = usePermissionStore()
const loading = ref(false)
const shakeCard = ref(false)
const form = reactive({ username: '', password: '' })

function triggerShake() {
  shakeCard.value = true
  setTimeout(() => { shakeCard.value = false }, 450)
}

async function handleLogin() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入账号和密码')
    triggerShake()
    return
  }
  loading.value = true
  try {
    await userStore.login(form.username, form.password)
    if (!userStore.isAdmin) {
      userStore.logout()
      ElMessage.error('该账号无管理员权限，请使用超级管理员账号登录')
      triggerShake()
      return
    }
    await permissionStore.loadAdminContext(true)
    // 单一账号体系：同时建立宿主会话，供 /admin-api（密码重置队列等）使用。
    // 失败不影响主流程——SPA 主体走 JWT。
    void fetch('/auth/login', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: form.username, password: form.password, entryRole: 'admin' }),
    }).catch(() => undefined)
    ElMessage.success('登录成功')
    await router.replace('/admin/dashboard')
  } catch (e) {
    triggerShake()
    const msg = e instanceof Error ? e.message : '登录失败，请检查账号密码或后端服务是否已启动'
    if (!msg.includes('请求失败') && !msg.includes('网络')) {
      ElMessage.error(msg)
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page auth-page--dark">
    <ParticleNetworkBackground :enabled="true" :particle-count="48" tone="muted" />

    <div
      class="auth-glass-card auth-glass-card--admin"
      :class="{ 'is-shake': shakeCard }"
    >
      <div class="auth-header auth-header--admin auth-stagger">
        <img src="/brand-icon.jpg" alt="智课共生" class="auth-brand" />
        <h1 class="auth-title">智课共生管理端</h1>
        <p class="auth-subtitle">智能教学系统 · 后台管理登录</p>
      </div>

      <el-form class="auth-form auth-stagger" @submit.prevent="handleLogin">
        <el-form-item>
          <el-input
            v-model="form.username"
            placeholder="管理员账号"
            size="large"
            :prefix-icon="User"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            size="large"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="auth-submit-btn"
          :loading="loading"
          @click="handleLogin"
        >
          登录管理端
        </el-button>
      </el-form>

      <p class="auth-footer-link auth-footer-link--dark auth-stagger">
        学生用户请前往
        <router-link to="/login">学生端登录</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/assets/styles/auth-design-system.scss' as *;

.auth-form {
  @include auth-input-dark;
}
</style>
