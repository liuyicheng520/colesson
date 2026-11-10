<script setup lang="ts">
import { ref, computed, onBeforeUnmount, onMounted, watch, nextTick } from 'vue'
import {
  Plus,
  Microphone,
  Picture,
  VideoCamera,
  Document,
  Close,
  Tools,
  Loading,
  Right,
  VideoPause,
  Share,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import TutorQuickSettings from './TutorQuickSettings.vue'
import type { TutorDocumentItem } from '@/types'
import type { ActiveTool } from '@/composables/useTutorChat'

export interface PendingImage {
  id: string
  file: File
  url: string
}

const props = withDefaults(defineProps<{
  modelValue: string
  streaming?: boolean
  placeholder?: string
  documents?: TutorDocumentItem[]
  activeDocumentIds?: string[]
  uploading?: boolean
  uploadProgress?: number
  uploadError?: string | null
  deepMode?: boolean
  webSearchEnabled?: boolean
  showDeepMode?: boolean
  showWebSearch?: boolean
  enableImage?: boolean
  enableVideo?: boolean
  enableVoice?: boolean
  toolLoading?: boolean
  activeTool?: ActiveTool | null
}>(), {
  documents: () => [],
  activeDocumentIds: () => [],
  showDeepMode: true,
  showWebSearch: true,
  enableImage: true,
  enableVideo: true,
  enableVoice: true,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'update:deepMode': [value: boolean]
  'update:webSearchEnabled': [value: boolean]
  'update:activeTool': [value: ActiveTool | null]
  send: []
  stop: []
  upload: [file: File]
  removeDocument: [docId: string]
  toggleDocument: [docId: string]
  retryUpload: []
  sttResult: [text: string]
  settingsChange: []
}>()

const TOOL_LABELS: Record<ActiveTool, string> = {
  image: '思维导图',
  video: '视频生成',
  tts: '语音合成',
}

const TOOL_ICONS: Record<ActiveTool, typeof Picture> = {
  image: Share,
  video: VideoCamera,
  tts: Microphone,
}

const inputRef = ref<HTMLTextAreaElement>()
const fileRef = ref<HTMLInputElement>()
const imageRef = ref<HTMLInputElement>()
const shellRef = ref<HTMLElement>()
const uploadWrapRef = ref<HTMLElement>()
const uploadDropdownStyle = ref<{ top: string; left: string }>({ top: '0px', left: '0px' })

const focused = ref(false)
const dragOver = ref(false)
const dragCounter = ref(0)
const toolboxOpen = ref(false)
const uploadMenuOpen = ref(false)
const previewImageUrl = ref('')
const previewVisible = ref(false)

const listening = ref(false)

const pendingImages = ref<PendingImage[]>([])

const deepModeModel = computed({
  get: () => props.deepMode ?? false,
  set: (v: boolean) => emit('update:deepMode', v),
})
const webSearchModel = computed({
  get: () => props.webSearchEnabled ?? false,
  set: (v: boolean) => emit('update:webSearchEnabled', v),
})

const activeToolModel = computed({
  get: () => props.activeTool ?? null,
  set: (v: ActiveTool | null) => emit('update:activeTool', v),
})

const hasAttachments = computed(
  () => props.documents.length > 0 || pendingImages.value.length > 0,
)

const DOC_EXT = ['pdf', 'doc', 'docx', 'ppt', 'pptx']
const MAX_SIZE = 100 * 1024 * 1024

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let recognition: any = null

function onInput(e: Event) {
  emit('update:modelValue', (e.target as HTMLTextAreaElement).value)
}

function handleInput(e: Event) {
  onInput(e)
  autoResize()
}

function handlePrimaryAction() {
  if (props.streaming) {
    emit('stop')
    return
  }
  if (!props.modelValue.trim()) return
  emit('send')
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handlePrimaryAction()
  }
}

function selectTool(tool: ActiveTool) {
  activeToolModel.value = tool
  toolboxOpen.value = false
}

function deactivateTool() {
  if (props.toolLoading) return
  activeToolModel.value = null
}

function autoResize() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 160)}px`
}

function isImageFile(file: File) {
  return file.type.startsWith('image/') || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(file.name)
}

function isDocFile(file: File) {
  const ext = file.name.split('.').pop()?.toLowerCase()
  return DOC_EXT.includes(ext || '')
}

function addPendingImage(file: File) {
  if (!isImageFile(file)) {
    ElMessage.error(`${file.name}：请选择图片文件`)
    return
  }
  if (file.size > MAX_SIZE) {
    ElMessage.error(`${file.name}：单文件不能超过 100MB`)
    return
  }
  pendingImages.value.push({
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    file,
    url: URL.createObjectURL(file),
  })
}

function removePendingImage(id: string) {
  const item = pendingImages.value.find((p) => p.id === id)
  if (item) URL.revokeObjectURL(item.url)
  pendingImages.value = pendingImages.value.filter((p) => p.id !== id)
}

function processFiles(files: FileList | File[]) {
  for (const file of Array.from(files)) {
    if (isImageFile(file)) {
      addPendingImage(file)
    } else if (isDocFile(file)) {
      if (file.size > MAX_SIZE) {
        ElMessage.error(`${file.name}：单文件不能超过 100MB`)
        continue
      }
      emit('upload', file)
    } else {
      ElMessage.error(`${file.name}：支持图片或 PDF/Word/PPT 文档`)
    }
  }
}

function onDragEnter(e: DragEvent) {
  e.preventDefault()
  dragCounter.value++
  if (e.dataTransfer?.types.includes('Files')) dragOver.value = true
}

function onDragLeave(e: DragEvent) {
  e.preventDefault()
  dragCounter.value--
  if (dragCounter.value <= 0) {
    dragCounter.value = 0
    dragOver.value = false
  }
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  dragCounter.value = 0
  dragOver.value = false
  const files = e.dataTransfer?.files
  if (files?.length) processFiles(files)
}

function openImagePicker() {
  uploadMenuOpen.value = false
  imageRef.value?.click()
}

function openFilePicker() {
  uploadMenuOpen.value = false
  fileRef.value?.click()
}

function updateUploadDropdownPosition() {
  const el = uploadWrapRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  uploadDropdownStyle.value = {
    top: `${rect.top - 8}px`,
    left: `${rect.right}px`,
  }
}

function toggleUploadMenu() {
  if (!uploadMenuOpen.value) {
    updateUploadDropdownPosition()
  }
  uploadMenuOpen.value = !uploadMenuOpen.value
}

function onDocumentClick(e: MouseEvent) {
  const target = e.target as Node
  if (uploadWrapRef.value?.contains(target)) return
  if ((target as Element).closest?.('.upload-dropdown')) return
  uploadMenuOpen.value = false
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
})

watch(() => props.modelValue, () => {
  nextTick(autoResize)
})

function onImageChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) processFiles(input.files)
  input.value = ''
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) processFiles(input.files)
  input.value = ''
}

function startSTT() {
  const w = window as unknown as Record<string, unknown>
  const SR = (w.SpeechRecognition || w.webkitSpeechRecognition) as (new () => {
    lang: string
    interimResults: boolean
    onresult: ((e: { results: { [i: number]: { [j: number]: { transcript: string } } } }) => void) | null
    onerror: (() => void) | null
    onend: (() => void) | null
    start: () => void
    stop: () => void
  }) | undefined
  if (!SR) {
    ElMessage.warning('当前浏览器不支持语音识别，请使用 Chrome/Edge')
    return
  }
  if (listening.value && recognition) {
    recognition.stop()
    return
  }
  recognition = new SR()
  recognition.lang = 'zh-CN'
  recognition.interimResults = true
  recognition.onresult = (e: any) => {
    const text = Array.from({ length: e.results.length }, (_, i) => e.results[i][0].transcript).join('')
    const last = e.results[e.results.length - 1]
    if (last?.[0] && (last as { isFinal?: boolean }).isFinal !== false) {
      emit('sttResult', text)
      listening.value = false
    }
  }
  recognition.onerror = () => { listening.value = false }
  recognition.onend = () => { listening.value = false }
  recognition.start()
  listening.value = true
}

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  pendingImages.value.forEach((p) => URL.revokeObjectURL(p.url))
})

defineExpose({ pendingImages, autoResize })
</script>

<template>
  <div class="input-composer">
    <!-- 文件回显区 -->
    <div v-if="hasAttachments || uploading" class="attachment-strip">
      <div class="attachment-scroll">
        <div
          v-for="img in pendingImages"
          :key="img.id"
          class="attachment-item image-item"
          @click="previewImageUrl = img.url; previewVisible = true"
        >
          <img :src="img.url" :alt="img.file.name" />
          <button type="button" class="item-remove" @click.stop="removePendingImage(img.id)">
            <el-icon><Close /></el-icon>
          </button>
        </div>

        <div
          v-for="doc in documents"
          :key="doc.doc_id"
          class="attachment-item doc-item"
          :class="{ active: activeDocumentIds.includes(doc.doc_id) }"
          @click="emit('toggleDocument', doc.doc_id)"
        >
          <el-icon class="doc-icon"><Document /></el-icon>
          <span class="doc-name">{{ doc.filename }}</span>
          <span class="doc-pages">{{ doc.page_count }}页</span>
          <button type="button" class="item-remove" @click.stop="emit('removeDocument', doc.doc_id)">
            <el-icon><Close /></el-icon>
          </button>
        </div>

        <div v-if="uploading" class="attachment-item uploading-item">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>上传中 {{ uploadProgress ?? 0 }}%</span>
        </div>
      </div>
    </div>

    <div v-if="uploadError" class="upload-error">
      <span>{{ uploadError }}</span>
      <el-button size="small" type="warning" link @click="emit('retryUpload')">重试</el-button>
    </div>

    <!-- 输入容器 -->
    <div
      ref="shellRef"
      class="input-shell"
      :class="{ focused, 'drag-over': dragOver }"
      @dragenter="onDragEnter"
      @dragleave="onDragLeave"
      @dragover="onDragOver"
      @drop="onDrop"
    >
      <div v-if="dragOver" class="drop-overlay">
        <span>松开上传文件</span>
      </div>

      <div class="input-main">
        <textarea
          ref="inputRef"
          :value="modelValue"
          class="input-textarea"
          :rows="1"
          :placeholder="placeholder || '输入消息，Enter 发送，Shift+Enter 换行'"
          @input="handleInput"
          @focus="focused = true"
          @blur="focused = false"
          @keydown="onKeydown"
        />
      </div>

      <div class="input-footer">
        <div class="footer-left">
          <div
            v-if="activeToolModel"
            class="tool-chip"
            :class="{ loading: toolLoading }"
          >
            <span v-if="toolLoading" class="chip-spinner" />
            <el-icon v-else class="chip-icon"><component :is="TOOL_ICONS[activeToolModel]" /></el-icon>
            <span>{{ TOOL_LABELS[activeToolModel] }}</span>
            <span
              class="chip-close"
              role="button"
              tabindex="0"
              :class="{ disabled: toolLoading }"
              title="取消"
              @click.stop="!toolLoading && deactivateTool()"
              @keydown.enter.stop="!toolLoading && deactivateTool()"
            >
              <el-icon><Close /></el-icon>
            </span>
          </div>

          <TutorQuickSettings
            v-if="showDeepMode || showWebSearch"
            v-model:deep-mode="deepModeModel"
            v-model:web-search-enabled="webSearchModel"
            :show-deep-mode="showDeepMode"
            :show-web-search="showWebSearch"
            @change="emit('settingsChange')"
          />

          <el-popover
            v-if="enableImage || enableVideo"
            v-model:visible="toolboxOpen"
            placement="top-start"
            :width="200"
            trigger="click"
            teleported
            popper-class="toolbox-popover"
          >
            <template #reference>
              <button
                type="button"
                class="toolbox-btn"
                aria-label="打开工具箱"
                :disabled="streaming && !toolLoading"
              >
                <el-icon class="toolbox-icon"><Tools /></el-icon>
                <span>工具箱</span>
              </button>
            </template>
            <div class="toolbox-panel">
              <button
                v-if="enableImage"
                type="button"
                class="toolbox-item"
                aria-label="生成思维导图"
                :disabled="streaming"
                @click="selectTool('image')"
              >
                <el-icon><Share /></el-icon>
                <span>思维导图</span>
              </button>
              <button
                v-if="enableVideo"
                type="button"
                class="toolbox-item"
                aria-label="生成视频讲解"
                :disabled="streaming"
                @click="selectTool('video')"
              >
                <el-icon><VideoCamera /></el-icon>
                <span>视频生成</span>
              </button>
            </div>
          </el-popover>
        </div>
        <div class="footer-right">
          <div ref="uploadWrapRef" class="upload-wrap">
            <button
              type="button"
              class="circle-btn upload-btn"
              title="上传图片或文件"
              aria-label="上传图片或文件"
              :disabled="streaming || uploading"
              @click.stop="toggleUploadMenu"
            >
              <el-icon><Plus /></el-icon>
            </button>
            <Teleport to="body">
              <Transition name="upload-menu-fade">
                <div
                  v-if="uploadMenuOpen"
                  class="upload-dropdown upload-dropdown--teleport"
                  :style="{
                    top: uploadDropdownStyle.top,
                    left: uploadDropdownStyle.left,
                  }"
                  @click.stop
                >
                  <button type="button" class="upload-dropdown-item" @click="openImagePicker">
                    <el-icon class="item-icon"><Picture /></el-icon>
                    <span>图片</span>
                  </button>
                  <button type="button" class="upload-dropdown-item" @click="openFilePicker">
                    <el-icon class="item-icon"><Document /></el-icon>
                    <span>本地文件</span>
                  </button>
                </div>
              </Transition>
            </Teleport>
          </div>

          <input ref="imageRef" type="file" accept="image/*" multiple hidden @change="onImageChange" />
          <input ref="fileRef" type="file" accept=".pdf,.doc,.docx,.ppt,.pptx" multiple hidden @change="onFileChange" />

          <el-tooltip v-if="enableVoice" content="语音输入" placement="top">
            <button
              type="button"
              class="circle-btn mic-btn"
              aria-label="语音输入"
              :class="{ listening }"
              :disabled="streaming"
              @click="startSTT"
            >
              <el-icon><Microphone /></el-icon>
            </button>
          </el-tooltip>

          <button
            type="button"
            class="circle-btn send-btn"
            :class="{ streaming, stopping: streaming }"
            :disabled="!streaming && !modelValue.trim()"
            :title="streaming ? '停止生成' : '发送'"
            :aria-label="streaming ? '停止生成' : '发送'"
            @click="handlePrimaryAction"
          >
            <el-icon v-if="streaming" class="stop-icon"><VideoPause /></el-icon>
            <el-icon v-else><Right /></el-icon>
          </button>
        </div>
      </div>
    </div>

    <!-- 图片预览 -->
    <el-dialog v-model="previewVisible" title="图片预览" width="auto" append-to-body destroy-on-close>
      <img v-if="previewImageUrl" :src="previewImageUrl" class="preview-img" alt="预览" />
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.input-composer {
  padding: 16px 20px 20px;
  background: #fff;
  border-top: 1px solid #e0e0e0;
}

.attachment-strip {
  margin-bottom: 10px;
  overflow: hidden;
}

.attachment-scroll {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 4px;
  scrollbar-width: thin;

  &::-webkit-scrollbar { height: 4px; }
  &::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 2px; }
}

.attachment-item {
  position: relative;
  flex-shrink: 0;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
  background: #f9fafb;
  cursor: pointer;
  transition: border-color 0.2s;

  &.active { border-color: #006eff; background: #eff6ff; }

  .item-remove {
    position: absolute;
    top: -6px;
    right: -6px;
    width: 18px;
    height: 18px;
    border: none;
    border-radius: 50%;
    background: #374151;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 10px;
    opacity: 0;
    transition: opacity 0.15s;
    z-index: 1;
  }

  &:hover .item-remove { opacity: 1; }
}

.image-item {
  width: 64px;
  height: 64px;
  overflow: hidden;
  padding: 0;

  img { width: 100%; height: 100%; object-fit: cover; }
}

.doc-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 28px 8px 10px;
  max-width: 200px;

  .doc-icon { color: #006eff; font-size: 16px; flex-shrink: 0; }
  .doc-name {
    font-size: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100px;
  }
  .doc-pages { font-size: 11px; color: $text-secondary; flex-shrink: 0; }
}

.uploading-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  font-size: 12px;
  color: $text-secondary;
}

.upload-error {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #dc2626;
  margin-bottom: 8px;
}

.input-shell {
  position: relative;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  padding: 12px 14px;
  background: #fff;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.08), 0 1px 3px rgba(15, 23, 42, 0.04);
  transition: border-color 0.2s, box-shadow 0.2s;

  &.focused {
    border-color: #006eff;
    box-shadow: 0 4px 20px rgba(0, 110, 255, 0.18), 0 2px 8px rgba(0, 110, 255, 0.1);
  }

  &.drag-over {
    border-color: #006eff;
    box-shadow: 0 4px 20px rgba(0, 110, 255, 0.18), 0 2px 8px rgba(0, 110, 255, 0.1);
  }
}

.drop-overlay {
  position: absolute;
  inset: 0;
  border-radius: 12px;
  background: rgba(0, 110, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  pointer-events: none;

  span {
    padding: 8px 20px;
    background: rgba(0, 110, 255, 0.85);
    color: #fff;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
  }
}

.input-main {
  margin-bottom: 10px;
}

.toolbox-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid $border-color;
  background: #fff;
  font-size: 12px;
  font-weight: 500;
  color: $text-secondary;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.2s;
  white-space: nowrap;

  .toolbox-icon { font-size: 14px; color: #006eff; }

  &:hover:not(:disabled) {
    border-color: $primary;
    color: $primary;
  }

  &:disabled { opacity: 0.5; cursor: not-allowed; }
}

.tool-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px 6px 12px;
  border-radius: 999px;
  border: none;
  background: #006eff;
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  cursor: default;
  flex-shrink: 0;

  .chip-icon { font-size: 14px; }

  &.loading { padding-left: 10px; }

  .chip-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.35);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    flex-shrink: 0;
  }

  .chip-close {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    margin-left: 2px;
    border: none;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.22);
    color: #fff;
    cursor: pointer;
    font-size: 12px;
    padding: 0;

    &:hover:not(.disabled) { background: rgba(255, 255, 255, 0.35); }
    &.disabled { opacity: 0.5; cursor: not-allowed; }
  }
}

.input-textarea {
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  font-size: 14px;
  line-height: 1.6;
  min-height: 24px;
  max-height: 160px;
  background: transparent;
  color: $text-primary;
  font-family: inherit;
  display: block;

  &::placeholder { color: #9ca3af; }
  &:disabled { opacity: 0.6; cursor: not-allowed; }
}

.input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.footer-left {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
  gap: 8px;
  flex-wrap: wrap;
}

.footer-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.upload-wrap {
  position: relative;
}

.upload-menu-fade-enter-active,
.upload-menu-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.upload-menu-fade-enter-from,
.upload-menu-fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.circle-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: #f3f4f6;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 18px;
  flex-shrink: 0;

  &:hover:not(:disabled) {
    background: #e5e7eb;
    color: #374151;
  }

  &:disabled { opacity: 0.45; cursor: not-allowed; }

  &.mic-btn.listening {
    background: #fef2f2;
    color: #ef4444;
    animation: micPulse 1.2s infinite;
  }

  &.send-btn {
    background: #006eff;
    color: #fff;

    &:hover:not(:disabled) { background: #0058cc; }

    &.stopping {
      background: #374151;
      animation: sendPulse 1.2s ease-in-out infinite;

      &:hover:not(:disabled) { background: #1f2937; }
    }
  }
}

.stop-icon {
  font-size: 18px;
}

@keyframes sendPulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(55, 65, 81, 0.35); }
  50% { box-shadow: 0 0 0 6px rgba(55, 65, 81, 0); }
}

.send-loading {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.preview-img {
  max-width: 80vw;
  max-height: 70vh;
  object-fit: contain;
  display: block;
}

@keyframes micPulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.35); }
  50% { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>

<style lang="scss">
.toolbox-popover {
  padding: 6px !important;
}

.upload-dropdown {
  min-width: 148px;
  padding: 8px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(15, 23, 42, 0.12), 0 2px 8px rgba(15, 23, 42, 0.06);
  border: 1px solid #f0f0f0;
  z-index: 3000;
}

.upload-dropdown--teleport {
  position: fixed;
  transform: translate(-100%, -100%);
}

.upload-dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  font-size: 14px;
  color: #374151;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s;

  .item-icon {
    font-size: 20px;
    color: #4b5563;
    flex-shrink: 0;
  }

  &:hover { background: #f3f4f6; }
}

.toolbox-panel {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.toolbox-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  font-size: 13px;
  color: #374151;
  cursor: pointer;
  width: 100%;
  text-align: left;
  transition: background 0.15s;

  &:hover:not(:disabled) { background: #f3f4f6; }
  &:disabled { opacity: 0.5; cursor: not-allowed; }
}
</style>
