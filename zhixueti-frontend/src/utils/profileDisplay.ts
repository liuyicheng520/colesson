import type { ProfileData } from '@/types'

export interface ProfileDisplayRow {
  label: string
  value: string
}

const STYLE_LABELS: Record<string, string> = {
  visual: '视觉型',
  verbal: '言语型',
  sequential: '顺序型',
  global: '整体型',
}

const PACE_LABELS: Record<string, string> = {
  slow: '稳扎稳打',
  medium: '适中节奏',
  fast: '快节奏',
}

const DOMAIN_LABELS: Record<string, string> = {
  machine_learning: '机器学习',
  computer_science: '计算机科学',
  software_engineering: '软件工程',
  data_structure: '数据结构',
  algorithm: '算法',
  mathematics: '数学',
  linear_algebra: '线性代数',
}

function getDimValue(profile: ProfileData | null, code: string) {
  return profile?.dimensions?.find((d) => d.dimension_code === code)?.dimension_value
}

function formatDomain(domain: unknown): string {
  if (!domain) return '暂未识别'
  const key = String(domain).trim()
  if (DOMAIN_LABELS[key]) return DOMAIN_LABELS[key]
  return key.replace(/_/g, ' ')
}

function formatGaps(gaps: unknown): string | null {
  if (!Array.isArray(gaps) || !gaps.length) return null
  const items = gaps
    .map((g) => formatWeakFocusItem(g))
    .filter((x): x is string => Boolean(x))
  return items.length ? items.join('、') : null
}

/** 从类 JSON / Python dict 字符串中尽量抽取 topic 可读字段 */
function extractTopicFromRaw(text: string): string | null {
  const m =
    text.match(/['"]topic['"]\s*:\s*['"]([^'"]+)['"]/) ||
    text.match(/topic['"]?\s*[:=]\s*['"]([^'"]+)['"]/i)
  return m?.[1]?.trim() || null
}

/**
 * 过滤后端合成提示、JSON、问卷基线等不应展示给学生的内容。
 * 用于学习目标、路径标题、薄弱点等所有学生可见文案。
 */
export function sanitizeStudentText(raw: unknown): string | null {
  if (raw == null) return null

  if (typeof raw === 'object') {
    const o = raw as Record<string, unknown>
    if (o.topic != null) return sanitizeStudentText(o.topic)
    if (o.goal != null) return sanitizeStudentText(o.goal)
    if (o.name != null) return sanitizeStudentText(o.name)
    if (o.title != null) return sanitizeStudentText(o.title)
    return null
  }

  let text = String(raw).trim()
  if (!text) return null

  // 纯技术载荷直接丢弃
  if (/^[\{\[]/.test(text) && /["']pace["']|sessionMinutes|errorType|frequency|fast\|medium\|slow/i.test(text)) {
    const topic = extractTopicFromRaw(text)
    return topic ? sanitizeStudentText(topic) : null
  }

  const backendMarkers = [
    /提取提示\s*[:：]/i,
    /用户多轮回答\s*[:：]/i,
    /维度\s*[:：]\s*D\d+/i,
    /第\d+轮回答\s*[:：]/,
    /问卷基线\s*[:：]/i,
    /请返回形如/i,
    /用户多轮/i,
    /dimension_code/i,
    /"pace"\s*:/i,
    /sessionMinutes/i,
  ]

  for (const pattern of backendMarkers) {
    const match = text.match(pattern)
    if (match?.index != null) {
      text = text.slice(0, match.index).trim()
    }
  }

  // 残留的 JSON / 伪 JSON 块
  text = text
    .replace(/\{[^{}]*\}/g, (block) => {
      const topic = extractTopicFromRaw(block)
      return topic || ''
    })
    .replace(/\[[^\[\]]*\]/g, '')
    .replace(/\bd\d+_\d+\b/gi, '')
    .replace(/\bfast\|medium\|slow\b/gi, '')
    .replace(/\berrorType\b|\bfrequency\b|\bsessionMinutes\b|\b"pace"\b/gi, '')
    .replace(/[:：]\s*$/g, '')
    .replace(/\s+/g, ' ')
    .trim()

  if (!text || /^(无|null|none|undefined)$/i.test(text)) return null
  if (/提取提示|用户多轮|问卷基线|sessionMinutes|"pace"|errorType|frequency/i.test(text)) return null
  // 仍像代码脚本则不展示
  if (/[{}\[\]\|]|[=:]{2}/.test(text) && /pace|Minutes|errorType|维度|D\d/i.test(text)) return null

  return text.length > 80 ? `${text.slice(0, 80)}…` : text
}

/** 薄弱点单项 → 可读短名 */
export function formatWeakFocusItem(raw: unknown): string | null {
  if (raw == null) return null
  if (typeof raw === 'object') {
    const o = raw as Record<string, unknown>
    return sanitizeStudentText(o.topic ?? o.name ?? o.point ?? o.label)
  }
  const text = String(raw).trim()
  if (!text) return null
  if (text.includes('topic') && (text.includes('{') || text.includes("'"))) {
    const topic = extractTopicFromRaw(text)
    if (topic) return sanitizeStudentText(topic)
  }
  return sanitizeStudentText(text)
}

/** 薄弱聚焦列表 → 「A、B、C」或「暂无」 */
export function formatWeakFocusList(items: unknown[] | null | undefined, empty = '暂无'): string {
  if (!items?.length) return empty
  const labels = items.map((x) => formatWeakFocusItem(x)).filter((x): x is string => Boolean(x))
  return labels.length ? labels.join('、') : empty
}

/** 路径标题 / 目标等通用展示 */
export function formatPathUserText(raw: unknown, fallback: string): string {
  return sanitizeStudentText(raw) || fallback
}

export function resolveStudentLearningGoal(profile: ProfileData | null, fallback = '掌握机器学习基础'): string {
  const d3 = getDimValue(profile, 'D3')
  return sanitizeStudentText(d3?.goal) || sanitizeStudentText(profile?.learning_goal) || fallback
}

function resolveLearningGoal(profile: ProfileData | null): string | null {
  const d3 = getDimValue(profile, 'D3')
  const fromDim = sanitizeStudentText(d3?.goal)
  if (fromDim) return fromDim
  return sanitizeStudentText(profile?.learning_goal)
}

/** 路径页画像同步短字段（答辩可视，避免长段落） */
export function formatPathProfileFields(
  profile: ProfileData | null,
  major?: string | null,
  grade?: string | number | null,
): { major: string; weakPoint: string; learnStyle: string; grade: string } {
  const rows = formatProfileForStudent(profile, major)
  const pick = (label: string) => rows.find((r) => r.label === label)?.value || '—'
  const knowledge = pick('知识基础')
  const weakMatch = knowledge.match(/待加强\s*(.+)$/)
  return {
    major: pick('专业') === '—' ? (major?.trim() || '未填写') : pick('专业'),
    weakPoint: weakMatch?.[1]?.trim() || (knowledge !== '—' ? knowledge : '待完善'),
    learnStyle: pick('认知风格') === '—' ? '综合型' : pick('认知风格'),
    grade: grade == null || grade === '' ? '—' : String(grade),
  }
}

/** 将画像数据格式化为学生可读的摘要条目（不含后端原始字段） */
export function formatProfileForStudent(
  profile: ProfileData | null,
  major?: string | null,
): ProfileDisplayRow[] {
  const rows: ProfileDisplayRow[] = []

  const majorText = major?.trim()
  if (majorText) {
    rows.push({ label: '专业', value: majorText })
  }

  const d1 = getDimValue(profile, 'D1')
  if (d1) {
    const parts: string[] = []
    if (d1.domain) parts.push(formatDomain(d1.domain))
    if (d1.level != null && d1.level !== '') parts.push(`掌握水平 ${d1.level}/5`)
    const gaps = formatGaps(d1.gaps)
    if (gaps) parts.push(`待加强 ${gaps}`)
    if (parts.length) rows.push({ label: '知识基础', value: parts.join('，') })
  }

  const d2 = getDimValue(profile, 'D2')
  if (d2?.style) {
    const styleKey = String(d2.style)
    rows.push({
      label: '认知风格',
      value: STYLE_LABELS[styleKey] || styleKey,
    })
  }

  const goalText = resolveLearningGoal(profile)
  if (goalText) {
    rows.push({ label: '学习目标', value: goalText })
  }

  const d6 = getDimValue(profile, 'D6')
  if (d6) {
    const paceKey = d6.pace ? String(d6.pace) : 'medium'
    const paceText = PACE_LABELS[paceKey] || '适中节奏'
    const minutes = d6.sessionMinutes != null ? `，每次约 ${d6.sessionMinutes} 分钟` : ''
    rows.push({ label: '学习节奏', value: `${paceText}${minutes}` })
  }

  return rows
}
