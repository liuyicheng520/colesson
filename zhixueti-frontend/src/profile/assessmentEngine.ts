/**
 * 简化版 IRT 自适应测评引擎
 * 2PL 模型: P(θ) = 1 / (1 + exp(-a(θ - b)))
 * 收敛条件: SE < 0.35 或 答题数 >= 15
 */

export interface AssessmentQuestion {
  id: string
  topic: string
  stem: string
  options: string[]
  difficulty: number
  discrimination: number
  answer?: number
}

export interface AssessmentAnswer {
  questionId: string
  selectedIndex: number
  correct: boolean
}

export interface AssessmentState {
  theta: number
  standardError: number
  answered: AssessmentAnswer[]
  usedIds: Set<string>
  topicStats: Record<string, { correct: number; total: number }>
}

const CONVERGENCE_SE = 0.35
const MAX_QUESTIONS = 15
const MIN_QUESTIONS = 5

export function createAssessmentState(initialTheta = 0): AssessmentState {
  return {
    theta: initialTheta,
    standardError: 1.0,
    answered: [],
    usedIds: new Set(),
    topicStats: {},
  }
}

function probCorrect(theta: number, a: number, b: number): number {
  return 1 / (1 + Math.exp(-a * (theta - b)))
}

/** 单步能力值更新（牛顿法一步近似） */
export function updateTheta(state: AssessmentState, q: AssessmentQuestion, correct: boolean): AssessmentState {
  const a = q.discrimination
  const b = q.difficulty
  const p = probCorrect(state.theta, a, b)
  const u = correct ? 1 : 0
  const info = a * a * p * (1 - p)
  const delta = info > 0.01 ? (a * (u - p)) / info : a * (u - p)
  const newTheta = Math.max(-2.5, Math.min(2.5, state.theta + delta * 0.5))
  const n = state.answered.length + 1
  const se = Math.max(0.15, 1 / Math.sqrt(n * Math.max(info, 0.3)))

  const topicStats = { ...state.topicStats }
  if (!topicStats[q.topic]) topicStats[q.topic] = { correct: 0, total: 0 }
  topicStats[q.topic].total += 1
  if (correct) topicStats[q.topic].correct += 1

  return {
    ...state,
    theta: newTheta,
    standardError: se,
    topicStats,
  }
}

/** 选题：最大信息量原则，排除已用题 */
export function selectNextQuestion(state: AssessmentState, bank: AssessmentQuestion[]): AssessmentQuestion | null {
  const available = bank.filter((q) => !state.usedIds.has(q.id))
  if (!available.length) return null

  let best = available[0]
  let bestInfo = -1
  for (const q of available) {
    const p = probCorrect(state.theta, q.discrimination, q.difficulty)
    const info = q.discrimination ** 2 * p * (1 - p)
  // 偏好难度接近当前 θ 的题目
    const proximity = 1 / (1 + Math.abs(q.difficulty - state.theta))
    const score = info * proximity
    if (score > bestInfo) {
      bestInfo = score
      best = q
    }
  }
  return best
}

export function recordAnswer(
  state: AssessmentState,
  q: AssessmentQuestion,
  selectedIndex: number,
): AssessmentState {
  const correct = selectedIndex === q.answer
  const answered: AssessmentAnswer = { questionId: q.id, selectedIndex, correct }
  const usedIds = new Set(state.usedIds)
  usedIds.add(q.id)
  const next = updateTheta({ ...state, answered: [...state.answered, answered], usedIds }, q, correct)
  return next
}

export function isConverged(state: AssessmentState): boolean {
  return state.answered.length >= MIN_QUESTIONS && (
    state.standardError < CONVERGENCE_SE || state.answered.length >= MAX_QUESTIONS
  )
}

/** 根据用户年级/专业调整初始 θ */
export function initialThetaFromProfile(grade?: number | string | null, major?: string | null): number {
  let theta = 0
  if (grade != null) {
    const year = typeof grade === 'number' ? grade : parseInt(String(grade).replace(/\D/g, ''), 10)
    if (year >= 2022) theta -= 0.2
    if (year <= 2021) theta += 0.2
  }
  if (major && /计算机|软件|信息|人工智能|数据/.test(major)) theta += 0.3
  return theta
}

export function thetaToLevel(theta: number): number {
  if (theta < -1) return 1
  if (theta < -0.3) return 2
  if (theta < 0.5) return 3
  if (theta < 1.2) return 4
  return 5
}
