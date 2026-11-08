/** 根据主题动态显示 code 类型资源标签 */
const PROGRAMMING_KEYWORDS = [
  'python', 'java', 'c++', '编程', '代码', '算法', '计算机', '机器学习', '深度学习',
  'javascript', '前端', '后端', 'sql', '数据结构', '软件',
]

export function isProgrammingTopic(topic: string, goal?: string): boolean {
  const text = `${topic} ${goal || ''}`.toLowerCase()
  return PROGRAMMING_KEYWORDS.some((kw) => text.includes(kw.toLowerCase()))
}

/** 统一展示为「实战演练」（兼容历史「代码实操」文案） */
export function codeTypeLabel(_topic?: string, _goal?: string): string {
  return '实战演练'
}

export const TYPE_LABELS: Record<string, string> = {
  document: '课程讲义',
  question: '分层习题',
  mindmap: '知识图谱',
  reading: '拓展阅读',
  code: '实战演练',
  video: 'AI视频讲解',
}

export function getTypeLabel(typeCode: string, topic?: string, goal?: string): string {
  if (typeCode === 'code') return codeTypeLabel(topic, goal)
  return TYPE_LABELS[typeCode] || typeCode
}

/** 若摘要/字段是整段 JSON 资源载荷，尝试解析 */
export function tryParseCodePayload(raw: unknown): Record<string, unknown> | null {
  if (typeof raw !== 'string') return null
  const s = raw.trim()
  if (!s.startsWith('{') || !s.includes('content_mode')) return null
  try {
    const obj = JSON.parse(s) as Record<string, unknown>
    if (obj && (obj.code_content || obj.practice_items || obj.explanation)) return obj
  } catch {
    // 常见：代码块里裸换行导致非法 JSON，此时无法在前端可靠修复
  }
  return null
}

/** 资源卡片/标题下摘要：避免把 JSON 原文直接展示 */
export function formatResourceSummary(summary: string | undefined | null, topic?: string): string {
  const text = (summary || '').trim()
  if (!text) return topic || ''
  const parsed = tryParseCodePayload(text)
  if (parsed) {
    const expl = parsed.explanation
    if (typeof expl === 'string' && expl.trim() && !expl.trim().startsWith('{')) {
      return expl.trim().slice(0, 120) + (expl.length > 120 ? '…' : '')
    }
    return topic ? `${topic} · 实战演练` : '实战演练'
  }
  return text
}
