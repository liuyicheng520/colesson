<script setup lang="ts">
/**
 * OpenMAIC 首页背景（参考 OpenMAIC app/page.tsx Background Decor）
 * - slate-50 → slate-100 纵向渐变
 * - 左上蓝色 / 右下紫色柔光 orb
 */
withDefaults(defineProps<{
  fullHeight?: boolean
}>(), {
  fullHeight: true,
})
</script>

<template>
  <div class="openmaic-bg" :class="{ 'is-full': fullHeight }">
    <div class="openmaic-bg__decor" aria-hidden="true">
      <div class="openmaic-bg__orb openmaic-bg__orb--blue" />
      <div class="openmaic-bg__orb openmaic-bg__orb--purple" />
    </div>
    <div class="openmaic-bg__content">
      <slot />
    </div>
  </div>
</template>

<style scoped lang="scss">
.openmaic-bg {
  position: relative;
  width: 100%;
  background: linear-gradient(to bottom, #f8fafc 0%, #f1f5f9 100%);
  overflow: hidden;

  &.is-full {
    min-height: 100vh;
    min-height: 100dvh;
  }
}

.openmaic-bg__decor {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
}

.openmaic-bg__orb {
  position: absolute;
  width: 24rem;
  height: 24rem;
  border-radius: 50%;
  filter: blur(64px);
  animation: openmaic-orb-pulse 4s ease-in-out infinite;

  &--blue {
    top: 0;
    left: 25%;
    transform: translateX(-50%);
    background: rgba(59, 130, 246, 0.1);
  }

  &--purple {
    bottom: 0;
    right: 25%;
    transform: translateX(50%);
    background: rgba(168, 85, 247, 0.1);
    animation-duration: 6s;
  }
}

@keyframes openmaic-orb-pulse {
  0%, 100% { opacity: 0.85; transform: translateX(-50%) scale(1); }
  50% { opacity: 1; transform: translateX(-50%) scale(1.06); }
}

.openmaic-bg__orb--purple {
  animation-name: openmaic-orb-pulse-purple;
}

@keyframes openmaic-orb-pulse-purple {
  0%, 100% { opacity: 0.85; transform: translateX(50%) scale(1); }
  50% { opacity: 1; transform: translateX(50%) scale(1.06); }
}

.openmaic-bg__content {
  position: relative;
  z-index: 1;
  width: 100%;
  min-height: inherit;
  display: flex;
  flex-direction: column;
}
</style>
