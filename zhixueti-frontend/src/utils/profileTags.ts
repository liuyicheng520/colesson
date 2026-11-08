/** 从 6 维画像维度值提取个人中心标签与学情摘要 */

import type { DimensionValue, DimensionProgressItem } from '@/types'
import { sanitizeStudentText } from '@/utils/profileDisplay'

const DOMAIN_MAP: Record<string, string> = {
  machine_learning: '机器学习',
  computer_science: '计算机科学',
  software_engineering: '软件工程',
}

const STYLE_MAP: Record<string, string> = {
  visual: '视觉型',
  verbal: '言语型',
  sequential: '顺序型',
  global: '整体型',
}

const PACE_MAP: Record<string, string> = {
  slow: '稳扎稳打',
  medium: '适中节奏',
  fast: '快速',
}

function dimMap(dims: DimensionValue[]) {
  return Object.fromEntries(dims.map((d) => [d.dimension_code, d])) as Record<string, DimensionValue>
}

export function buildProfileTags(dims: DimensionValue[]) {
  const m = dimMap(dims)
  const d1 = m.D1?.dimension_value || {}
  const d2 = m.D2?.dimension_value || {}
  const d5 = m.D5?.dimension_value || {}
  const d6 = m.D6?.dimension_value || {}

  const majorKey = String(d1.domain || '')
  const major = DOMAIN_MAP[majorKey] || majorKey.replace(/_/g, ' ') || '待完善'

  const weak = ((d5.weakPoints as { topic?: string }[]) || [])
    .map((w) => sanitizeStudentText(w?.topic))
    .filter(Boolean) as string[]
  const weakText = weak.slice(0, 2).join('、') || '待评估'

  const styleKey = String(d2.style || '')
  const preference =
    styleKey === 'visual'
      ? '动画+实战代码'
      : styleKey === 'verbal'
        ? '文字讲解+练习'
        : STYLE_MAP[styleKey] || '待评估'

  const pace = PACE_MAP[String(d6.pace || '')] || '待评估'

  return {
    major,
    weakText,
    preference,
    pace,
    line: `专业：${major}｜薄弱点：${weakText}｜偏好：${preference}｜学习节奏：${pace}`,
  }
}

export function dimensionSummary(code: string, value: Record<string, unknown> | null | undefined): string {
  if (!value) return '维度数据待采集'
  switch (code) {
    case 'D1': {
      const domain = DOMAIN_MAP[String(value.domain || '')] || String(value.domain || '未知领域')
      return `知识基础偏${domain}，当前水平约 Lv.${value.level ?? '?'}/5`
    }
    case 'D2': {
      const style = STYLE_MAP[String(value.style || '')] || '待识别'
      return `认知风格为${style}，资源推送将据此偏好呈现`
    }
    case 'D3':
      return sanitizeStudentText(value.goal) || '已设置学习目标'
    case 'D4': {
      const courses = (value.courses as string[]) || []
      return courses.length
        ? `已学课程：${courses.slice(0, 2).join('、')}${courses.length > 2 ? '…' : ''}`
        : '学习历史待补充'
    }
    case 'D5': {
      const weak = ((value.weakPoints as { topic?: string }[]) || [])
        .map((w) => sanitizeStudentText(w?.topic))
        .filter(Boolean) as string[]
      return weak.length
        ? `高频错题集中在${weak.slice(0, 3).join('、')}`
        : '暂无明显易错点聚类'
    }
    case 'D6': {
      const pace = PACE_MAP[String(value.pace || 'medium')] || '适中节奏'
      const mins = value.sessionMinutes != null ? `，单次约 ${value.sessionMinutes} 分钟` : ''
      return `学习节奏：${pace}${mins}`
    }
    default:
      return '已采集'
  }
}

export function toRadarDims(
  dims: DimensionValue[],
  progress?: DimensionProgressItem[],
) {
  const progMap = Object.fromEntries((progress || []).map((p) => [p.dimension_code, p]))
  return dims.map((d) => {
    const score = Number(d.display_score ?? d.confidence ?? 0)
    const summary =
      progMap[d.dimension_code]?.dimension_value
        ? dimensionSummary(d.dimension_code, progMap[d.dimension_code].dimension_value)
        : dimensionSummary(d.dimension_code, d.dimension_value)
    return {
      name: d.dimension_name,
      value: Math.min(1, Math.max(0, score)),
      summary,
      weak: score < 0.45,
      code: d.dimension_code,
    }
  })
}

export const EMPTY_DEMO_DIMS = [
  { name: '知识基础', value: 0.12, summary: '数据不足，无法精准诊断知识水平', weak: true, code: 'D1' },
  { name: '认知风格', value: 0.08, summary: '偏好未采集', weak: true, code: 'D2' },
  { name: '学习目标', value: 0.1, summary: '目标缺失，难以生成专属路径', weak: true, code: 'D3' },
  { name: '学习历史', value: 0.05, summary: '无历史课程记录', weak: true, code: 'D4' },
  { name: '易错点偏好', value: 0.06, summary: '错题信号不足', weak: true, code: 'D5' },
  { name: '学习节奏', value: 0.09, summary: '节奏未知', weak: true, code: 'D6' },
]
