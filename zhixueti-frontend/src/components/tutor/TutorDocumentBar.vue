<script setup lang="ts">
import { ref } from 'vue'
import { Upload, Document, Close } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { TutorDocumentItem } from '@/types'

const props = defineProps<{
  documents: TutorDocumentItem[]
  activeIds: string[]
  uploading?: boolean
  progress?: number
  uploadError?: string | null
}>()

const emit = defineEmits<{
  upload: [file: File]
  toggle: [docId: string]
  remove: [docId: string]
  retry: []
}>()

const fileRef = ref<HTMLInputElement>()
const MAX_SIZE = 100 * 1024 * 1024

function onPick() {
  fileRef.value?.click()
}

function onChange(e: Event) {
  const input = e.target as HTMLInputElement
  const files = input.files
  if (!files?.length) return
  for (const file of Array.from(files)) {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!['pdf', 'doc', 'docx', 'ppt', 'pptx'].includes(ext || '')) {
      ElMessage.error(`${file.name}：仅支持 PDF、Word、PPT 格式`)
      continue
    }
    if (file.size > MAX_SIZE) {
      ElMessage.error(`${file.name}：单文件不能超过 100MB`)
      continue
    }
    emit('upload', file)
  }
  input.value = ''
}
</script>

<template>
  <div class="doc-bar">
    <el-button type="primary" plain size="small" :icon="Upload" :loading="uploading" @click="onPick">
      上传文档
    </el-button>
    <input ref="fileRef" type="file" accept=".pdf,.doc,.docx,.ppt,.pptx" multiple hidden @change="onChange" />

    <el-progress
      v-if="uploading && (progress ?? 0) > 0"
      :percentage="progress"
      :stroke-width="4"
      style="width: 140px"
    />

    <div v-if="uploadError" class="upload-err">
      <span>{{ uploadError }}</span>
      <el-button size="small" type="warning" link @click="emit('retry')">重试</el-button>
    </div>

    <div v-if="documents.length" class="doc-chips">
      <div v-for="d in documents" :key="d.doc_id" class="doc-chip-wrap">
        <el-check-tag
          :checked="activeIds.includes(d.doc_id)"
          class="doc-chip"
          @change="emit('toggle', d.doc_id)"
        >
          <el-icon><Document /></el-icon>
          {{ d.filename }}
          <span class="pages">{{ d.page_count }}页</span>
        </el-check-tag>
        <button type="button" class="doc-remove" title="删除" @click.stop="emit('remove', d.doc_id)">
          <el-icon><Close /></el-icon>
        </button>
      </div>
    </div>
    <span v-else class="hint">上传 PDF/Word/PPT（最大 100MB）后可基于文档问答</span>
  </div>
</template>

<style scoped lang="scss">
.doc-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 16px;
  background: #f8fafc;
  border-bottom: 1px solid $border-color;
}

.doc-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.doc-chip-wrap {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.doc-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  cursor: pointer;
  .pages { color: $text-secondary; margin-left: 4px; }
}

.doc-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 50%;
  background: #fee2e2;
  color: #dc2626;
  cursor: pointer;
  &:hover { background: #fecaca; }
}

.upload-err {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #dc2626;
}

.hint { font-size: 12px; color: $text-secondary; }
</style>
