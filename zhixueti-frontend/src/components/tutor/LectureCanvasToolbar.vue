<script setup lang="ts">
import {
  Grid,
  Mute,
  VideoPause,
  VideoPlay,
  ArrowLeft,
  ArrowRight,
  FullScreen,
  ScaleToOriginal,
  ChatDotRound,
} from '@element-plus/icons-vue'

defineProps<{
  currentPage?: number
  totalPages?: number
  previewOpen?: boolean
  muted?: boolean
  autoPlay?: boolean
  speaking?: boolean
  canPrev?: boolean
  canNext?: boolean
  speed?: number
  isPresenting?: boolean
  chatHistoryOpen?: boolean
}>()

const emit = defineEmits<{
  togglePreview: []
  toggleMute: []
  togglePlay: []
  prev: []
  next: []
  speedChange: []
  togglePresentation: []
  toggleChatHistory: []
}>()
</script>

<template>
  <div class="canvas-toolbar">
    <div class="toolbar-left">
      <button
        type="button"
        class="ctrl-btn"
        :class="{ active: previewOpen }"
        title="幻灯片预览"
        @click="emit('togglePreview')"
      >
        <el-icon><Grid /></el-icon>
      </button>
      <span class="page-counter">
        {{ currentPage }}<span class="slash">/</span>{{ totalPages }}
      </span>
    </div>

    <div class="toolbar-center">
      <div class="playback-group">
        <button type="button" class="ctrl-btn" :class="{ active: !muted }" title="静音/取消静音" @click="emit('toggleMute')">
          <el-icon><Mute /></el-icon>
        </button>
        <span class="ctrl-divider" />
        <button type="button" class="ctrl-btn speed-btn" title="倍速" @click="emit('speedChange')">
          {{ speed }}x
        </button>
        <span class="ctrl-divider" />
        <button type="button" class="ctrl-btn" :disabled="!canPrev" title="上一页" @click="emit('prev')">
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <button
          type="button"
          class="ctrl-btn play-btn"
          :class="{ active: speaking }"
          :title="speaking ? '暂停' : '播放'"
          @click="emit('togglePlay')"
        >
          <el-icon><VideoPause v-if="speaking" /><VideoPlay v-else /></el-icon>
        </button>
        <button type="button" class="ctrl-btn" :disabled="!canNext" title="下一页" @click="emit('next')">
          <el-icon><ArrowRight /></el-icon>
        </button>
      </div>
    </div>

    <div class="toolbar-right">
      <span class="ctrl-divider" />
      <button
        type="button"
        class="ctrl-btn"
        :class="{ active: isPresenting }"
        :title="isPresenting ? '退出全屏' : '全屏演示'"
        @click="emit('togglePresentation')"
      >
        <el-icon><ScaleToOriginal v-if="isPresenting" /><FullScreen v-else /></el-icon>
      </button>
      <button
        type="button"
        class="ctrl-btn"
        :class="{ active: chatHistoryOpen }"
        title="查看讲解笔记"
        @click="emit('toggleChatHistory')"
      >
        <el-icon><ChatDotRound /></el-icon>
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.canvas-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(255, 255, 255, 0.55);
  flex-shrink: 0;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.toolbar-left { min-width: 72px; }
.toolbar-right { margin-left: auto; min-width: 72px; justify-content: flex-end; }

.toolbar-center {
  flex: 1;
  display: flex;
  justify-content: center;
  min-width: 0;
}

.playback-group {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 6px;
  border-radius: 8px;
  background: rgba(148, 163, 184, 0.12);
}

.page-counter {
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: #94a3b8;
  user-select: none;
  .slash { opacity: 0.35; margin: 0 1px; }
}

.ctrl-btn {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, color 0.15s, transform 0.1s;
  &:hover:not(:disabled) { background: rgba(100, 116, 139, 0.1); color: #475569; }
  &:active:not(:disabled) { transform: scale(0.92); }
  &:disabled { opacity: 0.25; cursor: not-allowed; }
  &.active { color: #7c3aed; }
  &.play-btn.active { color: #7c3aed; }
}

.speed-btn {
  min-width: 36px;
  padding: 0 4px;
  font-size: 11px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: #7c3aed;
}

.ctrl-divider {
  width: 1px;
  height: 14px;
  background: rgba(148, 163, 184, 0.35);
  margin: 0 2px;
  flex-shrink: 0;
}
</style>
