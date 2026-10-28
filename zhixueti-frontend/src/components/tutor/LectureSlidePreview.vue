<script setup lang="ts">
import { computed } from 'vue'
import { DArrowLeft, Document, QuestionFilled, Trophy } from '@element-plus/icons-vue'
import type { TutorLectureSlide } from '@/types'

const props = defineProps<{
  open: boolean
  slides: TutorLectureSlide[]
  currentIndex: number
  topic: string
  completionIndex: number
  embedded?: boolean
}>()

const emit = defineEmits<{
  close: []
  select: [index: number]
}>()

const totalWithComplete = computed(() => props.slides.length + 1)

function slideTitle(slide: TutorLectureSlide, index: number): string {
  if (slide.type === 'quiz') return slide.question || `小测 ${index + 1}`
  return slide.title || `第 ${index + 1} 页`
}

function onSelect(index: number) {
  emit('select', index)
}
</script>

<template>
  <aside
    class="preview-panel"
    :class="{ open, embedded }"
    aria-label="幻灯片预览"
  >
    <header class="preview-header">
      <div class="brand-block">
        <img src="/brand-icon.jpg" alt="" class="brand-mark" />
        <span class="brand-logo">智课共生</span>
      </div>
      <button v-if="embedded" type="button" class="collapse-btn" title="收起预览" @click="emit('close')">
        <el-icon><DArrowLeft /></el-icon>
      </button>
    </header>

    <p v-if="topic" class="topic-line">{{ topic }}</p>

    <div class="preview-list">
      <button
        v-for="(slide, index) in slides"
        :key="slide.id ?? index"
        type="button"
        class="preview-item"
        :class="{ active: currentIndex === index }"
        @click="onSelect(index)"
      >
        <span class="item-badge">{{ index + 1 }}</span>
        <div class="thumb">
          <template v-if="slide.type === 'quiz'">
            <div class="thumb-quiz">
              <el-icon><QuestionFilled /></el-icon>
              <span>{{ slideTitle(slide, index) }}</span>
            </div>
          </template>
          <template v-else>
            <div class="thumb-content">
              <p class="thumb-title">{{ slide.title || `第 ${index + 1} 页` }}</p>
              <ul v-if="slide.bullets?.length">
                <li v-for="(b, bi) in slide.bullets.slice(0, 3)" :key="bi">{{ b }}</li>
              </ul>
            </div>
          </template>
        </div>
        <p class="item-label">{{ slideTitle(slide, index) }}</p>
      </button>

      <button
        type="button"
        class="preview-item complete-item"
        :class="{ active: currentIndex === completionIndex }"
        @click="onSelect(completionIndex)"
      >
        <span class="item-badge complete-badge">{{ totalWithComplete }}</span>
        <div class="thumb thumb-complete">
          <el-icon class="trophy-icon"><Trophy /></el-icon>
          <span>课程完成</span>
        </div>
        <p class="item-label">课程完成</p>
      </button>
    </div>
  </aside>
</template>

<style scoped lang="scss">
.preview-panel {
  flex-shrink: 0;
  width: 0;
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(20px);
  border-right: 1px solid transparent;
  transition: width 0.28s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.28s;

  &.embedded.open {
    width: 240px;
    border-right-color: rgba(148, 163, 184, 0.28);
    box-shadow: 2px 0 24px rgba(15, 23, 42, 0.04);
  }
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px 8px;
  flex-shrink: 0;
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.brand-mark {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  object-fit: cover;
  flex-shrink: 0;
}

.brand-logo {
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: #2563eb;
}

.collapse-btn {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  &:hover { background: rgba(100, 116, 139, 0.1); color: #334155; }
}

.topic-line {
  margin: 0;
  padding: 0 14px 10px;
  font-size: 12px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}

.preview-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px 10px 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;

  &::-webkit-scrollbar { width: 5px; }
  &::-webkit-scrollbar-thumb {
    background: rgba(148, 163, 184, 0.45);
    border-radius: 999px;
  }
}

.preview-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
  border-radius: 12px;
  transition: background 0.15s;

  &:hover .thumb { border-color: rgba(147, 51, 234, 0.35); }
  &.active .thumb {
    border-color: rgba(147, 51, 234, 0.55);
    box-shadow: 0 0 0 2px rgba(147, 51, 234, 0.15);
  }
  &.active .item-label { color: #7c3aed; font-weight: 600; }
}

.item-badge {
  align-self: flex-start;
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(148, 163, 184, 0.15);
  &.complete-badge {
    background: rgba(251, 191, 36, 0.25);
    color: #b45309;
  }
}

.thumb {
  width: 100%;
  aspect-ratio: 16 / 10;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: #fff;
  overflow: hidden;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.thumb-content {
  padding: 10px 12px;
  height: 100%;
  overflow: hidden;
  .thumb-title {
    margin: 0 0 6px;
    font-size: 11px;
    font-weight: 700;
    color: #0f172a;
    line-height: 1.3;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  ul {
    margin: 0;
    padding-left: 14px;
    li {
      font-size: 9px;
      color: #64748b;
      line-height: 1.35;
      margin: 2px 0;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
  }
}

.thumb-quiz {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  background: linear-gradient(135deg, #faf5ff, #f5f3ff);
  color: #7c3aed;
  .el-icon { font-size: 28px; }
  span {
    font-size: 10px;
    text-align: center;
    line-height: 1.35;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
}

.thumb-complete {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: linear-gradient(135deg, #fffbeb, #ffedd5);
  color: #b45309;
  .trophy-icon { font-size: 32px; }
  span { font-size: 12px; font-weight: 700; }
}

.complete-item.active .thumb-complete {
  border-color: rgba(245, 158, 11, 0.55);
  box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.2);
}

.item-label {
  margin: 0;
  font-size: 11px;
  color: #64748b;
  padding: 0 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
