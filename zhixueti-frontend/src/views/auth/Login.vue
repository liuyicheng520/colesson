<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import ParticleNetworkBackground from '@/components/ParticleNetworkBackground.vue'

const router = useRouter()
const userStore = useUserStore()
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
    if (userStore.isAdmin) {
      userStore.logout()
      ElMessage.warning('管理员账号请使用管理端登录')
      await router.replace('/admin/login')
      return
    }
    await router.replace('/student/home')
  } catch {
    triggerShake()
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page auth-page--dark">
    <ParticleNetworkBackground :enabled="true" :particle-count="64" tone="vivid" />

    <div
      class="auth-glass-card auth-glass-card--student"
      :class="{ 'is-shake': shakeCard }"
    >
      <div class="auth-header auth-header--dark auth-stagger">
        <img src="/brand-icon.jpg" alt="智课共生" class="auth-brand" />
        <h1 class="auth-title">智课共生</h1>
        <p class="auth-subtitle">个性化学习多智能体系统</p>
      </div>

      <el-form class="auth-form auth-stagger" @submit.prevent="handleLogin">
        <el-form-item>
          <el-input
            v-model="form.username"
            placeholder="用户名"
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
          登录
        </el-button>
      </el-form>

      <p class="auth-footer-link auth-footer-link--dark auth-stagger">
        还没有账号？<router-link to="/register">立即注册</router-link>
      </p>
      <p class="auth-footer-link auth-footer-link--dark auth-stagger" style="margin-top: 12px">
        管理员请前往
        <router-link to="/admin/login">管理端登录</router-link>
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
