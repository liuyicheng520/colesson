import { request } from './request'
import { useUserStore } from '@/stores/user'
import type { AgentDefinition, TaskData } from '@/types'

export const agentApi = {
  listDefinitions() {
    return request<AgentDefinition[]>({ method: 'GET', url: '/agents/definitions' })
  },

  updateDefinition(
    agentCode: string,
    data: {
      agent_name?: string
      description?: string
      default_model?: string
      prompt_template?: string
      timeout_sec?: number
      max_retry?: number
      status?: number
    },
  ) {
    return request<AgentDefinition>({ method: 'PUT', url: `/agents/definitions/${agentCode}`, data })
  },

  getTask(taskNo: string) {
    return request<TaskData>({ method: 'GET', url: `/agents/tasks/${taskNo}` })
  },

  createTask(data: { task_type: string; task_name: string; input_params?: Record<string, unknown> }) {
    return request<TaskData>({ method: 'POST', url: '/agents/tasks', data })
  },

  /** SSE stream for real-time multi-agent progress */
  streamTask(
    taskNo: string,
    onMessage: (task: TaskData) => void,
    onError?: (err: Error) => void,
  ): () => void {
    const userStore = useUserStore()
    const controller = new AbortController()
    const url = `/api/v1/agents/tasks/${taskNo}/stream`

    fetch(url, {
      headers: { Authorization: `Bearer ${userStore.token}` },
      signal: controller.signal,
    })
      .then(async (resp) => {
        if (!resp.ok) throw new Error(`SSE failed: ${resp.status}`)
        const reader = resp.body?.getReader()
        if (!reader) return
        const decoder = new TextDecoder()
        let buffer = ''
        let lastStatus: number | null = null
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const parts = buffer.split('\n\n')
          buffer = parts.pop() || ''
          for (const part of parts) {
            const line = part.trim()
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6)) as TaskData
                lastStatus = data.status
                onMessage(data)
              } catch { /* skip malformed */ }
            }
          }
        }
        buffer += decoder.decode()
        if (buffer.trim()) {
          const line = buffer.trim()
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6)) as TaskData
              lastStatus = data.status
              onMessage(data)
            } catch { /* skip */ }
          }
        }
        // 流正常结束但任务未终态时，走 onError 触发轮询兜底
        if (lastStatus == null || ![2, 3, 4, 5].includes(lastStatus)) {
          onError?.(new Error('progress stream ended before task finished'))
        }
      })
      .catch((e) => {
        if (e.name !== 'AbortError') onError?.(e)
      })

    return () => controller.abort()
  },
}
