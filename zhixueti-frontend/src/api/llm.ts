import { getToken } from './request'
import { stripLlmStreamMarkers } from '@/utils/llmStreamMarkers'
import type { ApiResponse } from '@/types'

export const llmApi = {
  async chatStream(
    messages: { role: string; content: string }[],
    onChunk: (text: string) => void,
    provider?: string,
  ): Promise<void> {
    const base = import.meta.env.VITE_API_BASE || '/api/v1'
    const resp = await fetch(`${base}/llm/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${getToken()}`,
      },
      body: JSON.stringify({ messages, provider, stream: true }),
    })
    if (!resp.ok || !resp.body) throw new Error('流式请求失败')

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const payload = line.slice(6).trim()
          if (payload === '[DONE]') return
          try {
            const json = JSON.parse(payload)
            if (json.content) onChunk(stripLlmStreamMarkers(String(json.content)))
          } catch { /* skip */ }
        }
      }
    }
    buffer += decoder.decode()
    if (buffer.trim()) {
      for (const line of buffer.split('\n')) {
        if (line.startsWith('data: ')) {
          const payload = line.slice(6).trim()
          if (payload === '[DONE]') return
          try {
            const json = JSON.parse(payload)
            if (json.content) onChunk(stripLlmStreamMarkers(String(json.content)))
          } catch { /* skip */ }
        }
      }
    }
  },

  chat(messages: { role: string; content: string }[], provider?: string) {
    return fetch(`${import.meta.env.VITE_API_BASE || '/api/v1'}/llm/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${getToken()}`,
      },
      body: JSON.stringify({ messages, provider }),
    }).then(async (r) => {
      const json: ApiResponse<{ content: string }> = await r.json()
      if (json.code !== 0) throw new Error(json.message)
      return json.data
    })
  },

  audit(content: string, targetType = 'message') {
    return fetch(`${import.meta.env.VITE_API_BASE || '/api/v1'}/llm/audit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${getToken()}`,
      },
      body: JSON.stringify({ content, target_type: targetType }),
    }).then((r) => r.json())
  },
}
