<script setup lang="ts">
import { nextTick, onActivated, onDeactivated, onMounted, onUnmounted, ref, watch } from 'vue'
import { Setting, Close } from '@element-plus/icons-vue'

const FAB_SIZE = 40
const MARGIN = 12
const GAP = 10
const DRAG_THRESHOLD = 4
const POPOVER_WIDTH = 280

type Corner = 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'

const open = defineModel<boolean>('open', { default: false })

/** keep-alive 下 Teleport 到 body 的 FAB 需在离开智能答疑页时隐藏 */
const pageActive = ref(true)

const pos = ref({ x: 0, y: 0 })
const snappedCorner = ref<Corner>('bottom-right')
const snapping = ref(false)
const dragging = ref(false)
const popoverRef = ref<HTMLElement | null>(null)
const popoverHeight = ref(320)
const popoverStyle = ref({ left: '0px', top: '0px' })
const arrowStyle = ref<{ left: string; top: string }>({ left: '0px', top: '0px' })
const arrowPlacement = ref<'top' | 'bottom' | 'left' | 'right'>('bottom')

let dragStart = { x: 0, y: 0 }
let elemStart = { x: 0, y: 0 }
let hasMoved = false
let activePointerId: number | null = null

function cornerTargets() {
  const vw = window.innerWidth
  const vh = window.innerHeight
  return [
    { x: MARGIN, y: MARGIN, corner: 'top-left' as Corner },
    { x: vw - FAB_SIZE - MARGIN, y: MARGIN, corner: 'top-right' as Corner },
    { x: MARGIN, y: vh - FAB_SIZE - MARGIN, corner: 'bottom-left' as Corner },
    { x: vw - FAB_SIZE - MARGIN, y: vh - FAB_SIZE - MARGIN, corner: 'bottom-right' as Corner },
  ]
}

function clampFab(x: number, y: number) {
  return {
    x: Math.max(MARGIN, Math.min(x, window.innerWidth - FAB_SIZE - MARGIN)),
    y: Math.max(MARGIN, Math.min(y, window.innerHeight - FAB_SIZE - MARGIN)),
  }
}

function snapToNearestCorner(x: number, y: number) {
  const cx = x + FAB_SIZE / 2
  const cy = y + FAB_SIZE / 2
  let nearest = cornerTargets()[3]
  let minDist = Infinity
  for (const item of cornerTargets()) {
    const dist = Math.hypot(cx - (item.x + FAB_SIZE / 2), cy - (item.y + FAB_SIZE / 2))
    if (dist < minDist) {
      minDist = dist
      nearest = item
    }
  }
  return { position: { x: nearest.x, y: nearest.y }, corner: nearest.corner }
}

function computePopoverPosition(corner: Corner, fabPos: { x: number; y: number }, height: number) {
  const vw = window.innerWidth
  const vh = window.innerHeight
  let left = 0
  let top = 0

  switch (corner) {
    case 'top-left':
      left = fabPos.x + FAB_SIZE + GAP
      top = fabPos.y + FAB_SIZE + GAP
      break
    case 'top-right':
      left = fabPos.x - POPOVER_WIDTH - GAP
      top = fabPos.y + FAB_SIZE + GAP
      break
    case 'bottom-left':
      left = fabPos.x + FAB_SIZE + GAP
      top = fabPos.y - height - GAP
      break
    case 'bottom-right':
      left = fabPos.x - POPOVER_WIDTH - GAP
      top = fabPos.y - height - GAP
      break
  }

  left = Math.max(MARGIN, Math.min(left, vw - POPOVER_WIDTH - MARGIN))
  top = Math.max(MARGIN, Math.min(top, vh - height - MARGIN))

  return { left, top }
}

function computeArrow(
  corner: Corner,
  fabPos: { x: number; y: number },
  modalLeft: number,
  modalTop: number,
  modalW: number,
  modalH: number,
) {
  const fabCx = fabPos.x + FAB_SIZE / 2
  const fabCy = fabPos.y + FAB_SIZE / 2
  const arrowHalf = 5

  if (corner === 'top-left' || corner === 'top-right') {
    arrowPlacement.value = 'top'
    return {
      left: `${Math.min(Math.max(fabCx - modalLeft - arrowHalf, 14), modalW - 24)}px`,
      top: '-5px',
    }
  }

  if (corner === 'bottom-left' || corner === 'bottom-right') {
    arrowPlacement.value = 'bottom'
    return {
      left: `${Math.min(Math.max(fabCx - modalLeft - arrowHalf, 14), modalW - 24)}px`,
      top: `${modalH - 5}px`,
    }
  }

  arrowPlacement.value = 'bottom'
  return { left: '50%', top: `${modalH - 5}px` }
}

async function updatePopoverLayout() {
  if (!open.value) return
  await nextTick()
  if (popoverRef.value) popoverHeight.value = popoverRef.value.offsetHeight

  const { left, top } = computePopoverPosition(snappedCorner.value, pos.value, popoverHeight.value)
  popoverStyle.value = { left: `${left}px`, top: `${top}px` }
  arrowStyle.value = computeArrow(
    snappedCorner.value,
    pos.value,
    left,
    top,
    POPOVER_WIDTH,
    popoverHeight.value,
  )
}

function initPosition() {
  const snap = snapToNearestCorner(
    window.innerWidth - FAB_SIZE - MARGIN,
    window.innerHeight - FAB_SIZE - MARGIN,
  )
  pos.value = snap.position
  snappedCorner.value = snap.corner
}

function onPointerMove(e: PointerEvent) {
  if (activePointerId !== e.pointerId) return
  e.preventDefault()

  const dx = e.clientX - dragStart.x
  const dy = e.clientY - dragStart.y

  if (!hasMoved && (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD)) {
    hasMoved = true
    dragging.value = true
    snapping.value = false
  }

  if (hasMoved) {
    pos.value = clampFab(elemStart.x + dx, elemStart.y + dy)
    const snap = snapToNearestCorner(pos.value.x, pos.value.y)
    snappedCorner.value = snap.corner
    if (open.value) updatePopoverLayout()
  }
}

function onPointerUp(e: PointerEvent) {
  if (activePointerId !== e.pointerId) return

  document.removeEventListener('pointermove', onPointerMove)
  document.removeEventListener('pointerup', onPointerUp)
  document.removeEventListener('pointercancel', onPointerUp)

  if (hasMoved) {
    snapping.value = true
    const snap = snapToNearestCorner(pos.value.x, pos.value.y)
    pos.value = snap.position
    snappedCorner.value = snap.corner
    window.setTimeout(() => {
      snapping.value = false
    }, 260)
    if (open.value) updatePopoverLayout()
  } else {
    open.value = !open.value
  }

  dragging.value = false
  activePointerId = null
}

function onPointerDown(e: PointerEvent) {
  if (e.button !== 0) return
  e.preventDefault()
  e.stopPropagation()

  hasMoved = false
  dragging.value = false
  activePointerId = e.pointerId
  dragStart = { x: e.clientX, y: e.clientY }
  elemStart = { ...pos.value }

  document.addEventListener('pointermove', onPointerMove, { passive: false })
  document.addEventListener('pointerup', onPointerUp)
  document.addEventListener('pointercancel', onPointerUp)
}

function close() {
  open.value = false
}

function onResize() {
  const snap = snapToNearestCorner(pos.value.x, pos.value.y)
  pos.value = snap.position
  snappedCorner.value = snap.corner
  updatePopoverLayout()
}

watch(open, (val) => {
  if (val) updatePopoverLayout()
})

watch(pos, () => {
  if (open.value) updatePopoverLayout()
}, { deep: true })

onMounted(() => {
  initPosition()
  window.addEventListener('resize', onResize)
})

onActivated(() => {
  pageActive.value = true
})

onDeactivated(() => {
  pageActive.value = false
  open.value = false
  dragging.value = false
  document.removeEventListener('pointermove', onPointerMove)
  document.removeEventListener('pointerup', onPointerUp)
  document.removeEventListener('pointercancel', onPointerUp)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  document.removeEventListener('pointermove', onPointerMove)
  document.removeEventListener('pointerup', onPointerUp)
  document.removeEventListener('pointercancel', onPointerUp)
})
</script>

<template>
  <Teleport to="body">
    <template v-if="pageActive">
      <Transition name="fade">
        <div v-if="open" class="settings-overlay" @click="close" />
      </Transition>

      <Transition name="pop">
        <div
          v-if="open"
          ref="popoverRef"
          class="settings-popover"
          :style="popoverStyle"
          @click.stop
        >
          <span class="popover-arrow" :class="`arrow-${arrowPlacement}`" :style="arrowStyle" />
          <header class="popover-header">
            <span class="popover-title">答疑设置</span>
            <button type="button" class="close-btn" aria-label="关闭" @click="close">
              <el-icon><Close /></el-icon>
            </button>
          </header>
          <div class="popover-body">
            <slot />
          </div>
        </div>
      </Transition>

      <button
        type="button"
        class="settings-fab"
        :class="{ dragging, snapping, active: open }"
        :style="{ left: `${pos.x}px`, top: `${pos.y}px` }"
        aria-label="答疑设置"
        @pointerdown="onPointerDown"
      >
        <el-icon class="fab-icon"><Setting /></el-icon>
      </button>
    </template>
  </Teleport>
</template>

<style scoped lang="scss">
.settings-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: rgba(15, 23, 42, 0.2);
}

.settings-popover {
  position: fixed;
  z-index: 2001;
  width: 280px;
  max-height: min(70vh, 420px);
  background: #fff;
  border-radius: $radius-lg;
  border: 1px solid $border-color;
  box-shadow: $shadow-card;
  display: flex;
  flex-direction: column;
  overflow: visible;
}

.popover-arrow {
  position: absolute;
  width: 10px;
  height: 10px;
  background: #fff;
  border: 1px solid $border-color;
  transform: rotate(45deg);
  z-index: 0;
}

.arrow-top {
  border-bottom: none;
  border-right: none;
}

.arrow-bottom {
  border-top: none;
  border-left: none;
}

.popover-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid $border-color;
  flex-shrink: 0;
  background: #fff;
  border-radius: $radius-lg $radius-lg 0 0;
  position: relative;
  z-index: 1;
}

.popover-title {
  font-size: 13px;
  font-weight: 600;
  color: $text-primary;
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: $radius-md;
  background: transparent;
  color: $text-secondary;
  cursor: pointer;

  &:hover {
    background: #f1f5f9;
    color: $text-primary;
  }
}

.popover-body {
  padding: 12px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  position: relative;
  z-index: 1;
  background: #fff;
  border-radius: 0 0 $radius-lg $radius-lg;

  :deep(.settings-block) {
    padding: 12px;
    border-radius: $radius-md;
    border: 1px solid $border-color;
    background: #fafbfc;

    &.priority-high {
      border-color: #bfdbfe;
      background: #eff6ff;
    }

    &.priority-low {
      margin-top: auto;
    }

    h4 {
      margin: 0 0 10px;
      font-size: 13px;
      font-weight: 600;
    }
  }

  :deep(.mode-group) {
    display: flex;
    flex-direction: column;
    gap: 6px;
    width: 100%;

    .el-radio {
      margin-right: 0;
      height: auto;
      padding: 8px 10px;
      white-space: normal;
      width: 100%;
    }

    .mode-desc {
      display: block;
      font-size: 11px;
      color: $text-secondary;
      font-weight: normal;
      margin-top: 2px;
    }
  }

  :deep(.field-row) {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  :deep(.field-label) {
    font-size: 12px;
    color: $text-secondary;
  }

  :deep(.switch-row) {
    display: flex;
    align-items: center;
    justify-content: space-between;

    h4 {
      margin: 0;
    }
  }

  :deep(.field-hint) {
    font-size: 11px;
    color: $text-secondary;
    margin: 6px 0 0;
    line-height: 1.4;
  }

  :deep(.profile-display) {
    margin: 8px 0 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  :deep(.profile-row) {
    display: grid;
    grid-template-columns: 64px 1fr;
    gap: 6px 8px;
    font-size: 12px;
    line-height: 1.45;

    dt {
      margin: 0;
      color: $text-secondary;
      font-weight: 500;
    }

    dd {
      margin: 0;
      color: $text-primary;
      word-break: break-word;
    }
  }
}

.settings-fab {
  position: fixed;
  z-index: 1999;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 50%;
  background: $primary;
  color: #fff;
  cursor: grab;
  box-shadow: $shadow-card;
  display: flex;
  align-items: center;
  justify-content: center;
  touch-action: none;
  user-select: none;

  &.snapping {
    transition: left 0.25s ease, top 0.25s ease, box-shadow 0.2s;
  }

  &.dragging {
    cursor: grabbing;
    box-shadow: 0 6px 20px rgba(37, 99, 235, 0.35);
  }

  &.active {
    box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.2);
  }

  &:hover .fab-icon {
    transform: rotate(60deg);
  }

  .fab-icon {
    font-size: 18px;
    transition: transform 0.3s ease;
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.pop-enter-active,
.pop-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: scale(0.97);
}
</style>
