/** 单维学情分析：以「你是怎样的人」评价为主，系统说明从简 */

import type { DimensionProgressItem } from '@/types'
import { formatContributionTags } from '@/profile/fusion'
import { sanitizeStudentText } from '@/utils/profileDisplay'

export type DimensionAnalysis = {
  /** 人格化评价：你是一个……的人 */
  portrait: string
  /** 一两句补充画像 */
  portraitDetail: string
  /** 简要事实摘要 */
  facts: string[]
  fusionWeights: string
  confidenceText: string
  /** 一句话说明对你学习的影响（非系统说明书） */
  forYou: string
  suggestion: string
  continuePrompt: string
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
  fast: '快速推进',
}

const PRIORITY_MAP: Record<string, string> = {
  high: '高',
  mid: '中',
  medium: '中',
  low: '低',
}

const DOMAIN_MAP: Record<string, string> = {
  machine_learning: '机器学习',
  computer_science: '计算机科学',
  software_engineering: '软件工程',
  computer: '计算机',
}

/** 明显是占位/空目标，不当作真实表述 */
function realGoal(raw: unknown): string | null {
  const g = sanitizeStudentText(raw)
  if (!g) return null
  const noise = /已设定|待补充|待完善|表述可再|学习目标|暂无|未知|null|undefined/i
  if (noise.test(g) && g.length < 20) return null
  if (g.length < 4) return null
  return g
}

function confPct(item: DimensionProgressItem) {
  const c = Number(item.fusion_confidence ?? item.confidence ?? 0)
  return Math.round((c <= 1 ? c : c / 100) * 100)
}

function fusionLine(item: DimensionProgressItem) {
  return formatContributionTags(item) || '暂无多源记录'
}

function confAdvice(conf: number): string {
  if (conf >= 80) return `${conf} 分｜对你的判断比较有把握`
  if (conf >= 50) return `${conf} 分｜大致靠谱，再聊两句会更准`
  return `${conf} 分｜还不够了解你，建议多补充一点`
}

function asList(v: unknown): string[] {
  if (!Array.isArray(v)) return []
  return v.map((x) => sanitizeStudentText(x) || String(x || '')).filter(Boolean)
}

function weeklyHint(v: Record<string, unknown>): string | null {
  for (const k of ['weeklySessions', 'sessionsPerWeek', 'weekly_times', 'frequency']) {
    if (v[k] != null && v[k] !== '') return String(v[k])
  }
  return null
}

export function buildStatusTag(item: DimensionProgressItem): string {
  const v = item.dimension_value
  if (!v) return '维度待采集'
  switch (item.dimension_code) {
    case 'D1': {
      const domain = DOMAIN_MAP[String(v.domain || '')] || String(v.domain || '').replace(/_/g, ' ') || '未知领域'
      return `${domain}・Lv.${v.level ?? '?'}/5`
    }
    case 'D2': {
      const style = STYLE_MAP[String(v.style || '')] || '待识别'
      return `偏好：${style}学习模式`
    }
    case 'D3':
      return realGoal(v.goal) ? '已有明确学习方向' : '学习目标还可以再具体一点'
    case 'D4': {
      const courses = (v.courses as string[]) || []
      const topics = (v.completedTopics as string[]) || []
      const n = courses.length || topics.length
      if (n) return `累计 ${n} 份学习资源记录`
      if (v.totalHours != null) return `累计投入约 ${v.totalHours} 小时`
      return '学习历史待补充'
    }
    case 'D5': {
      const weak = ((v.weakPoints as { topic?: string }[]) || [])
        .map((w) => sanitizeStudentText(w?.topic))
        .filter(Boolean) as string[]
      return weak.length ? `高频薄弱点：${weak.slice(0, 3).join('、')}` : '暂无明显薄弱点聚类'
    }
    case 'D6': {
      const pace = PACE_MAP[String(v.pace || 'medium')] || '适中节奏'
      return `适配${pace}学习节奏`
    }
    default:
      return '已采集'
  }
}

export function buildDimensionAnalysis(item: DimensionProgressItem): DimensionAnalysis {
  const v = (item.dimension_value || {}) as Record<string, unknown>
  const name = item.dimension_name
  const code = item.dimension_code
  const conf = confPct(item)
  const continuePrompt = `我想补充完善${code}${name}维度，请继续针对该维度提问，帮我把画像做得更完整。`

  let portrait = `你是一个正在完善「${name}」画像的学习者。`
  let portraitDetail = ''
  let facts: string[] = []
  let forYou = '我们会按你在这一维的特点，调整学习路径和资源形态。'
  let suggestion = '用一两句更具体的话补充该维度，评价会更贴你。'

  switch (code) {
    case 'D1': {
      const domain =
        DOMAIN_MAP[String(v.domain || '')] ||
        sanitizeStudentText(v.domain) ||
        String(v.domain || '')
      const levelNum = Number(v.level)
      const gaps = asList(v.gaps)
      const hasDomain = !!domain && domain !== '当前领域'

      if (hasDomain && Number.isFinite(levelNum) && levelNum <= 2) {
        portrait = `你是一个刚在「${domain}」站稳脚跟、愿意正视短板的入门型学习者。`
        portraitDetail = '你不回避基础薄弱，这反而适合用「小步巩固」把地基打牢，而不是一上来追综合项目。'
      } else if (hasDomain && Number.isFinite(levelNum) && levelNum === 3) {
        portrait = `你是一个在「${domain}」已有中等基础、正在往上爬坡的进阶型学习者。`
        portraitDetail = '你会的部分已经够用入门场景，接下来更需要把零散知识串成能动手的能力。'
      } else if (hasDomain && Number.isFinite(levelNum) && levelNum >= 4) {
        portrait = `你是一个在「${domain}」基础较扎实、追求更高阶应用的学习者。`
        portraitDetail = '重复入门对你意义不大；你更适合把时间花在难点突破和综合实践上。'
      } else if (hasDomain) {
        portrait = `你是一个以「${domain}」为主战场、正在摸清自己底子的学习者。`
        portraitDetail = '方向已经有了，下一步把「会什么 / 不会什么」说得更清楚，学习会少走弯路。'
      } else {
        portrait = '你是一个学习意愿明确、但知识坐标还不够清晰的探索型学习者。'
        portraitDetail = '先锁定主攻领域和大致水平，后面的路径才知道从哪一级起跑。'
      }

      facts = [
        hasDomain ? `主攻方向：${domain}` : '主攻方向：尚未明确',
        Number.isFinite(levelNum) ? `自评水平：Lv.${levelNum}/5` : '自评水平：待补充',
        gaps.length ? `你自己点名的短板：${gaps.slice(0, 4).join('、')}` : '具体短板：还没写清楚',
      ]
      forYou =
        gaps.length
          ? `针对「${gaps[0]}」这类短板，我们会先帮你补前置，再推正式内容，减少听不懂的挫败感。`
          : '我们会按你的起点选难度，避免内容突然跳太高或讲得太浅。'
      suggestion = gaps.length
        ? `再聊聊「${gaps[0]}」卡在哪——概念、练习还是项目？评价会更准。`
        : '用两三句话说清：学什么领域、大概几分水平、最头疼的一两个点。'
      break
    }
    case 'D2': {
      const styleKey = String(v.style || '')
      const style = STYLE_MAP[styleKey] || ''
      if (styleKey === 'visual') {
        portrait = '你是一个「看见才会」的视觉型学习者。'
        portraitDetail = '长文堆砌容易让你走神；图、流程、演示更能帮你把知识在脑子里立起来。'
        forYou = '给你的材料会更偏图解和演示，少用干巴巴的纯文字说明书。'
      } else if (styleKey === 'verbal') {
        portrait = '你是一个靠文字与讲解就能吃透内容的言语型学习者。'
        portraitDetail = '清晰定义、完整步骤和例子，对你往往比花哨动画更有用。'
        forYou = '讲义会写得更完整、步骤更清楚，方便你按文字节奏消化。'
      } else if (styleKey === 'sequential') {
        portrait = '你是一个讨厌跳跃、喜欢一步一步来的顺序型学习者。'
        portraitDetail = '缺了前置就往下推，你会明显别扭；线性、可检查的进度更适合你。'
        forYou = '路径会尽量按顺序推进，每一步都能自测再往下走。'
      } else if (styleKey === 'global') {
        portrait = '你是一个先要看见全貌、再愿意钻细节的整体型学习者。'
        portraitDetail = '没有地图时你容易迷失；先框架后细节，效率会高很多。'
        forYou = '我们会先给你学习地图和章节关系，再下钻具体内容。'
      } else {
        portrait = '你是一个学习方式还比较灵活、主导偏好尚未完全定型的人。'
        portraitDetail = '多种方式你都能用一点；再回忆一次「学得最投入」的场景，画像会更鲜明。'
        forYou = '暂时用均衡的材料组合；等偏好更清晰后，再帮你收窄形态。'
      }
      facts = [
        style ? `更明显的风格：${style}` : '主导风格：待识别',
        '这类偏好决定你「怎样学最省力」，不是能力高低',
      ]
      suggestion = '讲一次你学得最投入的经历：当时用了什么材料、怎么推进的。'
      break
    }
    case 'D3': {
      const goal = realGoal(v.goal)
      const deadline = v.deadline ? String(v.deadline) : ''
      const priorityKey = String(v.priority || '').toLowerCase()
      const priority = PRIORITY_MAP[priorityKey] || ''

      if (goal && priorityKey === 'high' && !deadline) {
        portrait = '你是一个目标感很强、把这件事放在很高优先级，但时间边界还比较模糊的人。'
        portraitDetail = `你心里已经有方向——「${goal}」，也愿意把它排在前面；若再补上期限，冲刺节奏会更踏实。`
      } else if (goal && deadline && priorityKey === 'high') {
        portrait = '你是一个目标清晰、期限在握、执行意愿很强的目标导向型学习者。'
        portraitDetail = `「${goal}」对你不是随便聊聊，而是有DDL的事；适合用里程碑把大目标拆小。`
      } else if (goal && !deadline) {
        portrait = '你是一个知道自己想去哪、但还没给旅程标上日期的人。'
        portraitDetail = `方向「${goal}」已经够用起步；缺的是「什么时候算到达」，否则容易学着学着漂起来。`
      } else if (goal) {
        portrait = '你是一个带着明确学习意图上路的人。'
        portraitDetail = `当前方向是「${goal}」` + (priority ? `，优先级偏「${priority}」` : '') + '。把验收标准写清，会更有成就感。'
      } else if (priorityKey === 'high') {
        portrait = '你是一个学习驱动力很强、把提升自己看得很重的人。'
        portraitDetail = '优先级已经拉满，但目标表述还偏笼统——越具体，越容易坚持。'
      } else {
        portrait = '你是一个愿意学习、但「学成什么样」还需要被问清楚的人。'
        portraitDetail = '有意愿是好事；再用一句话说清想达成的结果，画像会立刻立体起来。'
      }

      facts = [
        goal ? `你想达成：${goal}` : '具体目标：表述还比较笼统',
        deadline ? `你给自己的时间点：${deadline}` : '期限：还没定',
        priority ? `在你心里的优先级：${priority}` : '优先级：未标注',
      ]
      forYou = goal
        ? '后续内容和答疑会尽量围着这个方向转，少推与你无关的拓展。'
        : '目标越具体，我们越能帮你挡住无关内容，把时间留给真正重要的事。'
      suggestion = '试着用一句验收标准写清：做到什么就算学会；若有考试/项目日，一并写上。'
      break
    }
    case 'D4': {
      const courses = asList(v.courses)
      const topics = asList(v.completedTopics)
      const hours = v.totalHours != null ? Number(v.totalHours) : null
      const rich = courses.length + topics.length >= 2

      if (rich) {
        portrait = '你是一个并非从零开始、已经走过一段学习路程的人。'
        portraitDetail = '你有可复用的背景；再学新内容时，重复讲「入门第一课」对你往往是浪费。'
      } else if (courses.length || topics.length || (hours != null && hours > 0)) {
        portrait = '你是一个有一些相关经历、但仍在积累「可证明的学习轨迹」的人。'
        portraitDetail = '已有记录是好的起点；再补全学过的课与主题，我们才敢大胆帮你跳过重复部分。'
      } else {
        portrait = '你是一个学习历史画像还比较空白、一切有待被看见的人。'
        portraitDetail = '不是没学过，而是还没被写进来；补上几门课或项目，你的「存量」才会被尊重。'
      }

      facts = [
        courses.length ? `相关课程：${courses.slice(0, 4).join('、')}` : '相关课程：暂无记录',
        topics.length ? `已完成主题：${topics.slice(0, 4).join('、')}` : '已完成主题：暂无记录',
        hours != null && !Number.isNaN(hours) ? `大概投入：约 ${hours} 小时` : '投入时长：未知',
      ]
      forYou = rich
        ? '我们会尽量少让你「重听会的」，把课时留给真正的新东西。'
        : '历史越清楚，越不会把你已经会的内容再推一遍。'
      suggestion = '列 2～3 门相关课或项目，并注明是否学完。'
      break
    }
    case 'D5': {
      const weakRaw = (v.weakPoints as { topic?: string; errorType?: string }[]) || []
      const weak = weakRaw
        .map((w) => ({
          topic: sanitizeStudentText(w?.topic) || '',
          errorType: sanitizeStudentText(w?.errorType) || '',
        }))
        .filter((w) => w.topic)
      const prefer = String(v.prefer || v.preference || v.fixPrefer || '').toLowerCase()

      if (weak.length) {
        const top = weak[0]
        portrait = `你是一个对自己的「坑」有觉察、愿意正视薄弱点的学习者。`
        portraitDetail =
          `你已经能点出例如「${top.topic}」` +
          (top.errorType ? `（更像${top.errorType}类问题）` : '') +
          '——这种自我诊断，比盲目刷题更接近有效进步。'
        forYou = prefer.includes('原理')
          ? '你会更吃「先讲清楚再练」的方式，我们会少催着你盲目刷题。'
          : prefer.includes('练')
            ? '你更相信练中学，我们会提高变式练习的比重。'
            : `围绕「${top.topic}」会多给巩固，并按你的错因来拆解。`
      } else {
        portrait = '你是一个暂时还没把「易错模式」说清楚的学习者。'
        portraitDetail = '不是没有弱点，而是还没被命名；点名 1～2 个反复错的点，训练会立刻更对症。'
        forYou = '在薄弱点清晰之前，巩固只能偏通用；说得越具体，补强越省力。'
      }

      facts = weak.length
        ? weak.slice(0, 3).map((w) => (w.errorType ? `${w.topic}（${w.errorType}）` : w.topic))
        : ['薄弱清单：还空着']
      suggestion = weak.length
        ? `再补一句「${weak[0].topic}」为什么错，以及你更想多练还是先懂原理。`
        : '举 1～2 个反复出错的知识点或题型即可。'
      break
    }
    case 'D6': {
      const paceKey = String(v.pace || 'medium')
      const pace = PACE_MAP[paceKey] || '适中节奏'
      const mins = v.sessionMinutes != null ? Number(v.sessionMinutes) : null
      const weekly = weeklyHint(v)

      if (paceKey === 'fast' && mins != null && mins <= 45) {
        portrait = '你是一个精力偏「短而密」、喜欢快速推进的冲刺型学习者。'
        portraitDetail = `单次大约 ${mins} 分钟的高效窗口，说明你适合小块内容快速迭代，而不是一次灌输很长篇。`
      } else if (paceKey === 'fast') {
        portrait = '你是一个节奏偏快、不喜欢拖沓的学习者。'
        portraitDetail = '铺垫太长会消耗你的耐心；紧凑的反馈环更符合你的习惯。'
      } else if (paceKey === 'slow') {
        portrait = '你是一个宁可慢一点也要学扎实的稳扎稳打型学习者。'
        portraitDetail = '连续高压输入不合你的胃口；留出消化和复盘，你反而走得更远。'
      } else if (mins != null) {
        portrait = `你是一个单次专注大约 ${mins} 分钟、节奏比较均衡的学习者。`
        portraitDetail = '既不极端求快，也不过度拖延；把内容切到贴近这个窗口，完成感会更好。'
      } else {
        portrait = '你是一个学习节奏画像还在成型中的人。'
        portraitDetail = '补上「一次能学多久、一周几次」，我们才知道该把内容切大还是切小。'
      }

      facts = [
        `推进风格：${pace}`,
        mins != null && !Number.isNaN(mins) ? `单次高效窗口：约 ${mins} 分钟` : '单次时长：待补充',
        weekly ? `每周大约：${weekly} 次` : '每周次数：待补充',
      ]
      forYou =
        mins != null
          ? `内容会尽量切成接近 ${mins} 分钟能完成的一块，减少学到一半就断掉。`
          : '节奏清楚以后，节点长短会更贴你的专注力。'
      suggestion = weekly
        ? '可以再告诉我最容易坚持的时段。'
        : '补充每周能学几次，或比较固定的时间段。'
      break
    }
    default:
      portrait = `你是一个正在完善「${name}」相关画像的学习者。`
      portraitDetail = '再补充一点具体经历或偏好，对你的描述会更立体。'
      facts = [`维度：${name}`]
  }

  return {
    portrait,
    portraitDetail,
    facts,
    fusionWeights: fusionLine(item),
    confidenceText: confAdvice(conf),
    forYou,
    suggestion,
    continuePrompt,
  }
}

export function progressBarColor(code: string): string {
  return code === 'D1' ? '#E6A23C' : '#67C23A'
}
