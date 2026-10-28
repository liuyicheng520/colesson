<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { Close, Reading } from '@element-plus/icons-vue'
import type { TutorLectureSlide } from '@/types'
import type { LectureChatMessage } from '@/components/tutor/TutorLectureRoundtable.vue'

export interface LectureNoteEntry {
  slideIndex: number
  title: string
  items: Array<{ kind: 'speech'; text: string }>
}

const props = defineProps<{
  open: boolean
  slides: TutorLectureSlide[]
  currentIndex: number
  slideTranscripts?: Record<number, string>
  chatMessages?: LectureChatMessage[]
}>()

const emit = defineEmits<{
  close: []
}>()

const activeTab = ref<'notes' | 'chat'>('notes')
const listRef = ref<HTMLElement | null>(null)

const notes = computed((): LectureNoteEntry[] =>
  props.slides.map((slide, index) => {
    const items: LectureNoteEntry['items'] = []
    const live = props.slideTranscripts?.[index]?.trim()
    if (live) {
      items.push({ kind: 'speech', text: live })
    } else if (slide.narration?.trim()) {
      items.push({ kind: 'speech', text: slide.narration.trim() })
    }
    if (slide.type === 'content') {
      slide.bullets?.forEach((b) => {
        if (b.trim()) items.push({ kind: 'speech', text: b.trim() })
      })
      if (slide.highlight?.trim()) items.push({ kind: 'speech', text: slide.highlight.trim() })
    }
    if (slide.type === 'quiz' && slide.question?.trim()) {
      items.unshift({ kind: 'speech', text: `【测验】${slide.question.trim()}` })
    }
    const title =
      slide.type === 'quiz'
        ? slide.question || `小测 ${index + 1}`
        : slide.title || `第 ${index + 1} 页`
    return { slideIndex: index, title, items }
  }),
)

const qaMessages = computed(() => props.chatMessages?.filter((m) => m.content.trim()) ?? [])

watch(
  () => [props.open, props.currentIndex],
  () => {
    if (!props.open) return
    nextTick(() => {
      const el = listRef.value?.querySelector(`[data-slide-index="${props.currentIndex}"]`)
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
  },
)
</script>

<template>
  <aside class="notes-panel" :class="{ open }" aria-label="讲解笔记">
    <header class="notes-header">
      <div class="tabs">
        <button type="button" class="tab" :class="{ active: activeTab === 'notes' }" @click="activeTab = 'notes'">
          笔记
        </button>
        <button type="button" class="tab" :class="{ active: activeTab === 'chat' }" @click="activeTab = 'chat'">
          对话
        </button>
      </div>
      <button type="button" class="close-btn" title="关闭" @click="emit('close')">
        <el-icon><Close /></el-icon>
      </button>
    </header>

    <div v-if="activeTab === 'notes'" ref="listRef" class="notes-body">
      <div v-if="!notes.length" class="notes-empty">
        <el-icon><Reading /></el-icon>
        <p>播放后将在此显示每页讲解内容</p>
      </div>
      <article
        v-for="note in notes"
        :key="note.slideIndex"
        :data-slide-index="note.slideIndex"
        class="note-card"
        :class="{ current: currentIndex === note.slideIndex }"
      >
        <div class="note-head">
          <span class="dot" />
          <span class="page-label">第 {{ note.slideIndex + 1 }} 页</span>
          <span v-if="currentIndex === note.slideIndex" class="current-tag">当前页</span>
        </div>
        <h4 class="note-title">{{ note.title }}</h4>
        <div class="note-items">
          <p v-for="(item, i) in note.items" :key="i" class="note-speech">
            <span class="speech-icon">👨‍🏫</span>
            {{ item.text }}
          </p>
        </div>
      </article>
    </div>

    <div v-else class="notes-body chat-tab">
      <div v-if="!qaMessages.length" class="notes-empty">
        <p>暂无问答记录</p>
      </div>
      <div v-for="msg in qaMessages" :key="msg.id" class="chat-item" :class="msg.role">
        <span class="chat-role">{{ msg.role === 'user' ? '我' : 'AI 教师' }}</span>
        <p>{{ msg.content }}</p>
      </div>
    </div>
  </aside>
</template>

<style scoped lang="scss">
.notes-panel {
  flex-shrink: 0;
  width: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(20px);
  border-left: 1px solid transparent;
  transition: width 0.28s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.28s;

  &.open {
    width: 320px;
    border-left-color: rgba(148, 163, 184, 0.28);
    box-shadow: -4px 0 24px rgba(15, 23, 42, 0.05);
  }
}

.notes-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  flex-shrink: 0;
}

.tabs {
  display: flex;
  gap: 4px;
}

.tab {
  border: none;
  background: transparent;
  padding: 8px 14px 10px;
  font-size: 13px;
  font-weight: 600;
  color: #94a3b8;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  &.active {
    color: #7c3aed;
    border-bottom-color: #7c3aed;
  }
}

.close-btn {
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
  &:hover { background: rgba(100, 116, 139, 0.1); }
}

.notes-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px;
  &::-webkit-scrollbar { width: 5px; }
  &::-webkit-scrollbar-thumb {
    background: rgba(148, 163, 184, 0.45);
    border-radius: 999px;
  }
}

.notes-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #94a3b8;
  font-size: 13px;
  text-align: center;
  padding: 24px;
  .el-icon { font-size: 32px; color: #c4b5fd; }
}

.note-card {
  margin-bottom: 12px;
  padding: 12px;
  border-radius: 10px;
  background: rgba(248, 250, 252, 0.9);
  transition: background 0.2s;
  &.current {
    background: rgba(245, 243, 255, 0.95);
    box-shadow: inset 0 0 0 1px rgba(147, 51, 234, 0.25);
  }
}

.note-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #cbd5e1;
  flex-shrink: 0;
  .current & { background: #9333ea; box-shadow: 0 0 0 3px rgba(147, 51, 234, 0.15); }
}

.page-label {
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
  letter-spacing: 0.04em;
  .current & { color: #7c3aed; }
}

.current-tag {
  font-size: 9px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(147, 51, 234, 0.12);
  color: #7c3aed;
}

.note-title {
  margin: 0 0 8px;
  padding-left: 16px;
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  line-height: 1.4;
}

.note-items {
  padding-left: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.note-speech {
  margin: 0;
  font-size: 12px;
  line-height: 1.65;
  color: #475569;
  display: flex;
  gap: 6px;
  align-items: flex-start;
}

.speech-icon {
  flex-shrink: 0;
  font-size: 14px;
  line-height: 1.4;
}

.chat-tab .chat-item {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f8fafc;
  &.user { background: #f5f3ff; }
  .chat-role {
    display: block;
    font-size: 10px;
    font-weight: 700;
    color: #9333ea;
    margin-bottom: 4px;
  }
  p { margin: 0; font-size: 13px; line-height: 1.55; color: #334155; }
}
</style>
