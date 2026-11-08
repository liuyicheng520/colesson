/**
 * 轻量语义解析 — 对话输入实时提取关键词并映射画像标签
 * 纯前端实现，降低后端依赖，用于右侧进度实时预览
 */

import type { DimensionProgressItem } from '@/types'

type PartialProfile = Record<string, Record<string, unknown>>

const DIMENSION_KEYWORDS: Record<string, { keywords: string[]; hints: Record<string, unknown> }> = {
  D1: {
    keywords: ['基础', '掌握', '薄弱', '专业', '领域', '水平', '知识', '技能', '入门', '精通'],
    hints: { domain: '已识别领域', level: 3 },
  },
  D2: {
    keywords: ['视觉', '图表', '视频', '文字', '阅读', '顺序', '整体', '框架', '动手', '听觉'],
    hints: { style: 'visual', score: 0.75 },
  },
  D3: {
    keywords: ['目标', '考试', '认证', '项目', '期限', '优先', '计划', '提升', '就业'],
    hints: { goal: '学习目标', priority: 'mid' },
  },
  D4: {
    keywords: ['课程', '学过', '完成', '小时', '培训', '自学', '项目经验', '学习经历'],
    hints: { courses: ['相关课程'], totalHours: 50 },
  },
  D5: {
    keywords: ['错题', '易错', '薄弱点', '粗心', '概念', '不会', '反复', '错误'],
    hints: { weakPoints: [{ topic: '薄弱知识点', errorType: 'concept', frequency: 2 }] },
  },
  D6: {
    keywords: ['节奏', '快', '慢', '分钟', '专注', '碎片', '稳扎稳打', '时段', '每周'],
    hints: { pace: 'medium', sessionMinutes: 40 },
  },
}

export interface SemanticParseResult {
  matchedDimensions: string[]
  preview: PartialProfile
  keywords: string[]
}

export function parseUserInput(text: string, currentCode?: string): SemanticParseResult {
  const lower = text.toLowerCase()
  const matchedDimensions: string[] = []
  const keywords: string[] = []
  const preview: PartialProfile = {}

  for (const [code, cfg] of Object.entries(DIMENSION_KEYWORDS)) {
    const hits = cfg.keywords.filter((kw) => lower.includes(kw.toLowerCase()) || text.includes(kw))
    if (hits.length > 0 || code === currentCode) {
      matchedDimensions.push(code)
      keywords.push(...hits)
      preview[code] = { ...cfg.hints, _keywords: hits }
    }
  }

  // 数字识别 → D1 level
  const levelMatch = text.match(/([1-5])\s*分/)
  if (levelMatch) {
    preview.D1 = { ...(preview.D1 || {}), level: Number(levelMatch[1]) }
    if (!matchedDimensions.includes('D1')) matchedDimensions.push('D1')
  }

  return { matchedDimensions, preview, keywords: [...new Set(keywords)] }
}

/** 将语义预览合并到维度进度（仅 UI 预览，不写库） */
export function applySemanticPreview(
  items: DimensionProgressItem[],
  preview: PartialProfile,
): DimensionProgressItem[] {
  return items.map((item) => {
    const p = preview[item.dimension_code]
    if (!p || item.status === 'completed') return item
    return {
      ...item,
      dimension_value: { ...(item.dimension_value || {}), ...p },
      display_score: Math.min(item.display_score + 0.08, 0.95),
      status: item.status === 'pending' ? 'active' : item.status,
    }
  })
}
