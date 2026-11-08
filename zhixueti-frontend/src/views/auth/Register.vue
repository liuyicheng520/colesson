<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock, Reading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import ParticleNetworkBackground from '@/components/ParticleNetworkBackground.vue'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const shakeCard = ref(false)
const form = reactive({
  username: '',
  password: '',
  major: '',
  grade: 2024,
})

/** 入学年级选项：2020级 ~ 2026级 */
const gradeOptions = [2020, 2021, 2022, 2023, 2024, 2025, 2026]

const fieldErrors = reactive({
  username: '',
  password: '',
})

function clearErrors() {
  fieldErrors.username = ''
  fieldErrors.password = ''
}

function triggerShake() {
  shakeCard.value = true
  setTimeout(() => { shakeCard.value = false }, 450)
}

function validate(): boolean {
  clearErrors()
  let ok = true
  if (!form.username.trim()) {
    fieldErrors.username = '请输入用户名'
    ok = false
  } else if (form.username.length < 3) {
    fieldErrors.username = '用户名至少 3 个字符'
    ok = false
  }
  if (!form.password) {
    fieldErrors.password = '请输入密码'
    ok = false
  } else if (form.password.length < 6) {
    fieldErrors.password = '密码至少 6 个字符'
    ok = false
  }
  if (!ok) {
    ElMessage.warning('请完善表单信息')
    triggerShake()
  }
  return ok
}

async function handleRegister() {
  if (!validate()) return
  loading.value = true
  try {
    await userStore.register({
      username: form.username,
      password: form.password,
      nickname: form.username,
      major: form.major,
      grade: form.grade,
      user_type: 1,
    })
    router.push('/student/profile-dialogue')
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
      class="auth-glass-card auth-glass-card--student auth-glass-card--register-wide"
      :class="{ 'is-shake': shakeCard }"
    >
      <div class="auth-header auth-header--dark auth-stagger">
        <img src="/brand-icon.jpg" alt="智课共生" class="auth-brand" />
        <h1 class="auth-title">创建学习账号</h1>
        <p class="auth-subtitle">加入智课共生，开启个性化学习之旅</p>
      </div>

      <el-form
        class="auth-form auth-stagger"
        label-position="top"
        @submit.prevent="handleRegister"
      >
        <el-form-item label="用户名" :error="fieldErrors.username">
          <el-input v-model="form.username" size="large" placeholder="至少 3 个字符" :prefix-icon="User" />
        </el-form-item>
        <el-form-item label="密码" :error="fieldErrors.password">
          <el-input
            v-model="form.password"
            type="password"
            size="large"
            placeholder="至少 6 个字符"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-form-item label="专业">
          <el-input v-model="form.major" size="large" placeholder="如：计算机科学" :prefix-icon="Reading" />
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="form.grade" size="large" placeholder="请选择年级" style="width: 100%">
            <el-option v-for="y in gradeOptions" :key="y" :label="`${y}级`" :value="y" />
          </el-select>
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="auth-submit-btn"
          :loading="loading"
          @click="handleRegister"
        >
          注册并开始
        </el-button>
      </el-form>

      <p class="auth-footer-link auth-footer-link--dark auth-stagger">
        已有账号？<router-link to="/login">去登录</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/assets/styles/auth-design-system.scss' as *;

/* 注册表单字段较多，略放宽卡片宽度，视觉风格与学生登录一致 */
.auth-glass-card--register-wide {
  max-width: 440px;
}

.auth-form {
  @include auth-input-dark;

  :deep(.el-form-item__label) {
    color: rgba(255, 255, 255, 0.72);
    font-weight: 500;
    font-size: 13px;
    padding-bottom: 6px;
    line-height: 1.4;
  }

  :deep(.el-form-item__error) {
    color: #fca5a5;
    font-size: 12px;
    padding-top: 4px;
  }

  :deep(.el-select__wrapper) {
    background: rgba(255, 255, 255, 0.07);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: $auth-radius-input;
    box-shadow: none;
    transition:
      border-color $auth-duration $auth-ease,
      background $auth-duration $auth-ease,
      box-shadow $auth-duration $auth-ease,
      transform $auth-duration $auth-ease;

    &:hover {
      border-color: rgba(255, 255, 255, 0.22);
      background: rgba(255, 255, 255, 0.1);
    }

    &.is-focused {
      border-color: rgba(124, 58, 237, 0.65);
      background: rgba(255, 255, 255, 0.12);
      box-shadow:
        0 0 0 3px rgba(37, 99, 235, 0.18),
        0 0 20px rgba(124, 58, 237, 0.12);
      transform: translateY(-1px);
    }
  }

  :deep(.el-select__placeholder),
  :deep(.el-select__selected-item) {
    color: #fff;
  }

  :deep(.el-select__caret) {
    color: rgba(255, 255, 255, 0.55);
  }
}
</style>
