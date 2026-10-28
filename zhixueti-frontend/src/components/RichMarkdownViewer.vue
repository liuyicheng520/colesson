<script setup lang="ts">
import { computed } from 'vue'
import MarkdownViewer from './MarkdownViewer.vue'
import MermaidViewer from './MermaidViewer.vue'

const props = withDefaults(defineProps<{ content: string; streaming?: boolean }>(), {
  streaming: false,
})

interface Block {
  type: 'markdown' | 'mermaid'
  content: string
}

function parseBlocks(text: string): Block[] {
  const blocks: Block[] = []
  const regex = /```mermaid\n([\s\S]*?)```/g
  let lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      blocks.push({ type: 'markdown', content: text.slice(lastIndex, match.index) })
    }
    blocks.push({ type: 'mermaid', content: match[1].trim() })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) {
    blocks.push({ type: 'markdown', content: text.slice(lastIndex) })
  }
  if (!blocks.length) {
    blocks.push({ type: 'markdown', content: text })
  }
  return blocks
}

const blocks = computed(() => parseBlocks(props.content || ''))
</script>

<template>
  <div class="rich-markdown">
    <template v-for="(block, i) in blocks" :key="i">
      <MermaidViewer v-if="block.type === 'mermaid' && block.content" :code="block.content" class="mermaid-block" />
      <MarkdownViewer v-else-if="block.content.trim()" :content="block.content" :streaming="streaming" />
    </template>
  </div>
</template>

<style scoped lang="scss">
.rich-markdown {
  .mermaid-block {
    margin: 12px 0;
    padding: 12px;
    background: #fff;
    border-radius: 8px;
    border: 1px solid #e2e8f0;
  }
}
</style>
