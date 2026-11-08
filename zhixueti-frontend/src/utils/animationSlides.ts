export interface AnimationSlide {
  step?: number
  title?: string
  narration?: string
  visual?: string
  emoji?: string
  duration_sec?: number
  /** concept 为普通讲解；simulation/interactive 为可操作场景。 */
  scene_type?: 'concept' | 'simulation' | 'interactive'
  nodes?: string[]
  interaction?: {
    variable_label?: string
    min?: number
    max?: number
    initial?: number
    unit?: string
    presets?: Array<{ label: string; value: number }>
  }
  /** 由动画智能体生成的独立交互 HTML；始终在无同源权限的 iframe 中运行。 */
  interactive_html?: string
}

function tryParseJson(text: unknown): Record<string, unknown> | null {
  if (typeof text !== 'string') return null
  const s = text.trim()
  if (!s.startsWith('{') && !s.startsWith('[')) return null
  try {
    const cleaned = s.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '')
    const data = JSON.parse(cleaned)
    return data && typeof data === 'object' ? (data as Record<string, unknown>) : null
  } catch {
    return null
  }
}

function looksLikeJsonBlob(value: unknown): boolean {
  if (typeof value !== 'string') return false
  const s = value.trim()
  return s.startsWith('{') && (s.includes('script_content') || s.includes('"slides"'))
}

function asSlideList(value: unknown): AnimationSlide[] {
  return Array.isArray(value) ? (value as AnimationSlide[]) : []
}

/** 从资源详情中解析可用分镜，兼容历史脏数据（整包 JSON 塞进旁白/脚本）。 */
export function normalizeAnimationSlides(detail: Record<string, unknown>): AnimationSlide[] {
  const anim = (detail.animation_data as Record<string, unknown> | undefined) || {}
  let slides = asSlideList(detail.slides)
  if (!slides.length) slides = asSlideList(anim.slides)
  if (!slides.length) slides = asSlideList(detail.storyboard)

  const tryUnpack = (blob: unknown): AnimationSlide[] => {
    const parsed = tryParseJson(blob)
    if (!parsed) return []
    const nested = asSlideList(parsed.slides)
    if (nested.length) return nested
    return asSlideList(parsed.storyboard)
  }

  if (slides.length <= 1) {
    const first = slides[0] || {}
    const candidates = [
      tryUnpack(first.narration),
      tryUnpack(first.visual),
      tryUnpack(detail.script_content),
      tryUnpack(anim.script_content),
    ]
    const unpacked = candidates.find((list) => list.length > 1)
      || candidates.find((list) => list.length === 1 && !looksLikeJsonBlob(list[0]?.narration))
    if (unpacked?.length) slides = unpacked
  }

  return slides
    .map((raw, i) => {
      const narration = String(raw.narration || '').trim()
      const visual = String(raw.visual || '').trim()
      return {
        ...raw,
        step: raw.step ?? i + 1,
        title: String(raw.title || `步骤 ${i + 1}`).slice(0, 80),
        narration: looksLikeJsonBlob(narration)
          ? '本页讲解内容已修复展示，请切换场景继续学习。'
          : narration || '这一部分正在准备讲解内容。',
        visual: looksLikeJsonBlob(visual) ? '跟随旁白观察概念结构' : visual || '概念图示',
        duration_sec: Math.max(6, Number(raw.duration_sec) || 10),
        scene_type: raw.scene_type || 'concept',
        nodes: Array.isArray(raw.nodes) && raw.nodes.length
          ? raw.nodes.map(String)
          : [String(raw.title || '核心概念'), visual || '要点', '掌握要点'],
      } as AnimationSlide
    })
}

/** 将 script_content 或 slides 格式化为可读 Markdown，避免页面展示原始 JSON。 */
export function formatAnimationScript(
  detail: Record<string, unknown>,
  slides?: AnimationSlide[],
): string {
  const resolved = slides?.length ? slides : normalizeAnimationSlides(detail)
  if (resolved.length) {
    return resolved
      .map((s, i) => `## ${s.title || `场景 ${i + 1}`}\n\n${s.narration || ''}`.trim())
      .join('\n\n')
  }
  const raw = detail.script_content
  if (typeof raw !== 'string' || !raw.trim()) return ''
  if (looksLikeJsonBlob(raw)) {
    const parsed = tryParseJson(raw)
    const nested = asSlideList(parsed?.slides)
    if (nested.length) {
      return nested
        .map((s, i) => `## ${s.title || `场景 ${i + 1}`}\n\n${s.narration || ''}`.trim())
        .join('\n\n')
    }
    return '脚本内容格式异常，请重新生成该教学动画资源。'
  }
  return raw
}
