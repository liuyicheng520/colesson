<template>
  <div v-if="!bootReady" class="boot-loading">
    <img src="/brand-icon.jpg" alt="智课共生" class="boot-brand" />
    <p>智课共生加载中…</p>
  </div>
  <router-view v-else />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import router from './router'

const bootReady = ref(false)

onMounted(async () => {
  try {
    await router.isReady()
  } finally {
    bootReady.value = true
  }
})
</script>

<style scoped>
.boot-loading {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: linear-gradient(160deg, #0f172a 0%, #1e3a8a 45%, #312e81 100%);
  color: rgba(255, 255, 255, 0.85);
  font-size: 14px;
}

.boot-brand {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  object-fit: cover;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
}
</style>
