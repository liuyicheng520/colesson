<script setup lang="ts">
import MarkdownIt from 'markdown-it'
import mdKatex from 'markdown-it-katex'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { normalizeStreamingMarkdown } from '@/utils/thinkStreamParser'

const props = withDefaults(defineProps<{ content: string; streaming?: boolean }>(), {
  streaming: false,
})

function createMd(breaks: boolean) {
  const md = new MarkdownIt({
    html: false,
    linkify: true,
    typographer: true,
    breaks,
    highlight(str, lang) {
      if (lang && hljs.getLanguage(lang)) {
        try {
          return `<pre class="hljs"><code>${hljs.highlight(str, { language: lang }).value}</code></pre>`
        } catch { /* fallthrough */ }
      }
      return `<pre class="hljs"><code>${md.utils.escapeHtml(str)}</code></pre>`
    },
  })
  return md.use(mdKatex)
}

const mdNormal = createMd(false)
const mdStream = createMd(true)

const renderSource = ref('')
let rafId = 0

watch(
  () => [props.content, props.streaming] as const,
  ([raw, streaming]) => {
    cancelAnimationFrame(rafId)
    if (!streaming) {
      renderSource.value = raw || ''
      return
    }
    rafId = requestAnimationFrame(() => {
      renderSource.value = raw || ''
    })
  },
  { immediate: true },
)

onBeforeUnmount(() => cancelAnimationFrame(rafId))

const html = computed(() => {
  const raw = renderSource.value || ''
  const source = props.streaming ? normalizeStreamingMarkdown(raw) : raw
  return (props.streaming ? mdStream : mdNormal).render(source)
})
</script>

<template>
  <div class="markdown-body" v-html="html" />
</template>
