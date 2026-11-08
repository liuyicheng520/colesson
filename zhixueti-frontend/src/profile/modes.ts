/** 画像构建模式定义 — 4 种分层采集方式 */

export type ProfileBuildMode = 'dialogue' | 'questionnaire' | 'assessment' | 'behavior'

export interface ProfileModeMeta {
  id: ProfileBuildMode
  name: string
  tagline: string
  duration: string
  audience: string
  icon: string
}

export const PROFILE_MODES: ProfileModeMeta[] = [
  {
    id: 'dialogue',
    name: '对话引导式',
    tagline: 'AI 递进追问，深度精准',
    duration: '约 8~12 分钟',
    audience: '追求高精准画像的用户',
    icon: 'ChatDotRound',
  },
  {
    id: 'questionnaire',
    name: '结构化问卷式',
    tagline: '6 题速填，高效稳定',
    duration: '约 1 分钟',
    audience: '希望快速完成基础画像',
    icon: 'Document',
  },
  {
    id: 'assessment',
    name: '自适应测评式',
    tagline: 'IRT 自适应出题，量化知识水平',
    duration: '约 3~5 分钟',
    audience: '需要客观能力评估',
    icon: 'TrendCharts',
  },
  {
    id: 'behavior',
    name: '行为静默式',
    tagline: '基于学习记录自动生成',
    duration: '约 30 秒',
    audience: '有平台学习记录的老用户',
    icon: 'DataAnalysis',
  },
]

export const MODE_STORAGE_KEY = 'edunexus_profile_mode'
export const MODE_INTRO_SEEN_KEY = 'edunexus_profile_intro_seen'
