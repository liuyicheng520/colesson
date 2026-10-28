<script setup lang="ts">
/**
 * Mermaid 图表渲染 — 思维导图交互修复版
 * - 悬停使用描边高亮，避免 scale 导致画布跳脱
 * - 点击仅展示节点释义，不触发路由跳转
 */
import { onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps<{
  code: string
  nodeDescriptions?: Record<string, string>
}>()

const containerRef = ref<HTMLElement>()
const tooltipText = ref('')
const pinnedLabel = ref('')
const hasContent = ref(false)
let renderId = 0
let cleanupFns: Array<() => void> = []

function clearInteractivity() {
  cleanupFns.forEach((fn) => fn())
  cleanupFns = []
}

function extractNodeLabel(el: Element): string {
  const textEl = el.querySelector(
    '.mindmap-node-label, .text-inner-tspan, foreignObject span, text, .nodeLabel, tspan',
  )
  let label = textEl?.textContent?.trim() || ''
  // 去除 Mermaid 语法残留括号
  label = label.replace(/^\(\(/, '').replace(/\)\)$/, '').replace(/^\(/, '').replace(/\)$/, '')
  return label
}

function highlightNode(el: SVGElement, on: boolean) {
  const shapes = el.querySelectorAll('rect, circle, ellipse, polygon, path')
  shapes.forEach((shape) => {
    const s = shape as SVGElement
    if (on) {
      if (!s.dataset.origStroke) {
        s.dataset.origStroke = s.getAttribute('stroke') || 'none'
        s.dataset.origStrokeWidth = s.getAttribute('stroke-width') || ''
      }
      s.setAttribute('stroke', '#2563eb')
      s.setAttribute('stroke-width', '2')
      s.style.filter = 'drop-shadow(0 2px 8px rgba(37,99,235,0.25))'
    } else {
      s.setAttribute('stroke', s.dataset.origStroke || 'none')
      if (s.dataset.origStrokeWidth) {
        s.setAttribute('stroke-width', s.dataset.origStrokeWidth)
      } else {
        s.removeAttribute('stroke-width')
      }
      s.style.filter = ''
    }
  })
}

function showTooltip(label: string, pin = false) {
  if (!label) {
    if (!pinnedLabel.value) tooltipText.value = ''
    return
  }
  const desc = props.nodeDescriptions?.[label]
  tooltipText.value = desc || (label ? `${label}：关联知识点` : '')
  if (pin) pinnedLabel.value = label
}

function attachInteractivity() {
  clearInteractivity()
  const container = containerRef.value
  if (!container) return

  const isMindmap = /^\s*mindmap/i.test(props.code)
  const nodes = container.querySelectorAll('.node, .mindmap-node, g.node, g.mindmap-node')

  nodes.forEach((node) => {
    const el = node as SVGElement
    el.style.cursor = 'pointer'

    const onEnter = () => {
      if (pinnedLabel.value) return
      highlightNode(el, true)
      showTooltip(extractNodeLabel(el))
    }
    const onLeave = () => {
      if (pinnedLabel.value) return
      highlightNode(el, false)
      tooltipText.value = ''
    }
    const onClick = (e: Event) => {
      e.stopPropagation()
      const label = extractNodeLabel(el)
      if (pinnedLabel.value === label) {
        pinnedLabel.value = ''
        tooltipText.value = ''
        highlightNode(el, false)
      } else {
        nodes.forEach((n) => highlightNode(n as SVGElement, false))
        highlightNode(el, true)
        showTooltip(label, true)
      }
    }

    el.addEventListener('mouseenter', onEnter)
    el.addEventListener('mouseleave', onLeave)
    el.addEventListener('click', onClick)
    cleanupFns.push(() => {
      el.removeEventListener('mouseenter', onEnter)
      el.removeEventListener('mouseleave', onLeave)
      el.removeEventListener('click', onClick)
    })
  })

  // 流程图才绑定连线高亮，思维导图跳过避免异常
  if (!isMindmap) {
    const edges = container.querySelectorAll('.edgePath, .edge-pattern-solid, path.flowchart-link')
    edges.forEach((edge) => {
      const el = edge as SVGElement
      const onEnter = () => { el.style.strokeWidth = '3px' }
      const onLeave = () => { el.style.strokeWidth = '' }
      el.addEventListener('mouseenter', onEnter)
      el.addEventListener('mouseleave', onLeave)
      cleanupFns.push(() => {
        el.removeEventListener('mouseenter', onEnter)
        el.removeEventListener('mouseleave', onLeave)
      })
    })
  }

  // 点击空白取消固定
  const onBgClick = () => {
    pinnedLabel.value = ''
    tooltipText.value = ''
    nodes.forEach((n) => highlightNode(n as SVGElement, false))
  }
  container.addEventListener('click', onBgClick)
  cleanupFns.push(() => container.removeEventListener('click', onBgClick))
}

function isErrorSvg(svg: string): boolean {
  return /Syntax error in text|class="error-text"|class='error-text'|error-icon/.test(svg)
}

async function renderMermaid() {
  if (!containerRef.value) return
  pinnedLabel.value = ''
  tooltipText.value = ''
  hasContent.value = false
  clearInteractivity()
  containerRef.value.innerHTML = ''

  const code = props.code?.trim()
  if (!code) return

  const id = `mermaid-${++renderId}`
  try {
    const mermaid = (await import('mermaid')).default
    mermaid.initialize({ startOnLoad: false, theme: 'default', securityLevel: 'loose' })

    try {
      await mermaid.parse(code)
    } catch {
      return
    }

    const { svg } = await mermaid.render(id, code)
    if (isErrorSvg(svg)) return

    containerRef.value.innerHTML = svg
    hasContent.value = true
    attachInteractivity()
  } catch {
    /* 无效 Mermaid 语法时不展示任何内容，避免出现 "Syntax error in text" */
  }
}

watch(() => props.code, renderMermaid)
onMounted(renderMermaid)
onUnmounted(() => {
  clearInteractivity()
  if (containerRef.value) containerRef.value.innerHTML = ''
})
</script>

<template>
  <div v-show="hasContent" class="mermaid-wrap">
    <div ref="containerRef" class="mermaid-viewer" />
    <transition name="tip">
      <div v-if="tooltipText" class="mermaid-tooltip">
        {{ tooltipText }}
        <span v-if="pinnedLabel" class="pin-hint">再次点击取消</span>
      </div>
    </transition>
  </div>
</template>

<style scoped lang="scss">
.mermaid-wrap { position: relative; }

.mermaid-viewer {
  width: 100%;
  min-height: 280px;
  overflow-x: auto;
  :deep(svg) { max-width: 100%; height: auto; display: block; }
  :deep(.error-text),
  :deep(svg[aria-roledescription="error"]) {
    display: none !important;
  }
}

.mermaid-tooltip {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  background: #fff;
  border: 1px solid $primary;
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 13px;
  color: $text-secondary;
  box-shadow: $shadow-card;
  max-width: 360px;
  text-align: center;
  z-index: 5;
  line-height: 1.5;

  .pin-hint {
    display: block;
    font-size: 11px;
    color: $text-secondary;
    margin-top: 4px;
  }
}

.tip-enter-active, .tip-leave-active { transition: opacity 0.2s ease-out; }
.tip-enter-from, .tip-leave-to { opacity: 0; }
</style>
