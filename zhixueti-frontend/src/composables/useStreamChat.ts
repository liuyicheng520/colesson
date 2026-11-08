import { ref } from 'vue'
import { llmApi } from '@/api/llm'
import type { ChatMessage } from '@/types'

let msgCounter = 0

export function useStreamChat() {
  const messages = ref<ChatMessage[]>([])
  const streaming = ref(false)
  const error = ref<string | null>(null)

  function addMessage(role: ChatMessage['role'], content: string): ChatMessage {
    const msg: ChatMessage = { id: `msg-${++msgCounter}`, role, content }
    messages.value.push(msg)
    return msg
  }

  async function send(content: string, systemPrompt?: string) {
    if (!content.trim() || streaming.value) return
    error.value = null
    addMessage('user', content)

    const assistant = addMessage('assistant', '')
    assistant.streaming = true
    streaming.value = true

    const apiMessages: { role: string; content: string }[] = []
    if (systemPrompt) apiMessages.push({ role: 'system', content: systemPrompt })
    for (const m of messages.value) {
      if (m.id === assistant.id) continue
      apiMessages.push({ role: m.role, content: m.content })
    }

    try {
      await llmApi.chatStream(apiMessages, (chunk) => {
        assistant.content += chunk
      })
    } catch (e) {
      error.value = (e as Error).message
      if (!assistant.content) {
        assistant.content = '抱歉，回答生成失败，请稍后重试。'
      }
    } finally {
      assistant.streaming = false
      streaming.value = false
    }
  }

  function clear() {
    messages.value = []
    error.value = null
  }

  return { messages, streaming, error, send, clear, addMessage }
}
