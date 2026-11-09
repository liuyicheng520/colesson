/**
 * 多源画像加权融合（与后端 profile_fusion.py 一致）
 * 问卷权重最低，对话/测评更高；多源叠加提升融合置信度
 */

import type { DimensionProgressItem } from '@/types'
import type { ProfileBuildMode } from '@/profile/modes'

export type ProfileSourceType = 'assessment' | 'behavior' | 'dialogue' | 'questionnaire' | 'manual'

/** 准确度权重 — 决定各方式对最终画像的影响占比 */
export const SOURCE_ACCURACY_WEIGHT: Record<ProfileSourceType, number> = {
  manual: 1.0,
  assessment: 0.92,
  dialogue: 0.82,
  behavior: 0.55,
  questionnaire: 0.3,
}

export const SOURCE_LABELS: Record<string, string> = {
  questionnaire: '问卷',
  dialogue: '对话',
  assessment: '测评',
  behavior: '行为',
  manual: '手动',
}

export function fusedConfidence(weights: number[]): number {
  if (!weights.length) return 0
  const product = weights.reduce((acc, w) => acc * (1 - Math.min(Math.max(w, 0), 1)), 1)
  return Math.min(0.99, 1 - product)
}

export function formatContributionTags(item: DimensionProgressItem): string {
  const contribs = item.source_contributions || []
  if (!contribs.length) return ''
  return contribs
    .map((c) => {
      const label = SOURCE_LABELS[c.source as string] || c.source
      const pct = Math.round(Number(c.weight) * 100)
      return `${label}${pct}%`
    })
    .join(' + ')
}

export function suggestNextMode(item: DimensionProgressItem): ProfileBuildMode | null {
  const contribs = item.source_contributions || []
  const hasQ = contribs.some((c) => c.source === 'questionnaire')
  const hasDialogue = contribs.some((c) => c.source === 'dialogue')
  if (hasQ && !hasDialogue) return 'dialogue'
  if (item.dimension_code === 'D1' && !contribs.some((c) => c.source === 'assessment')) return 'assessment'
  return null
}
