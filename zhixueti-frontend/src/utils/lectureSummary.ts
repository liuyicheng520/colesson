import type { TutorLectureSlide } from '@/types'

export interface LectureCompleteStats {
  contentCount: number
  quizCount: number
  quizCorrect: number
  quizTotal: number
  quizPct: number
}

export function summarizeLectureSlides(
  slides: TutorLectureSlide[],
  quizResults: { correct: boolean }[],
): LectureCompleteStats {
  let contentCount = 0
  let quizCount = 0
  for (const s of slides) {
    if (s.type === 'quiz') quizCount += 1
    else contentCount += 1
  }
  const quizTotal = quizResults.length
  const quizCorrect = quizResults.filter((r) => r.correct).length
  const quizPct = quizTotal > 0 ? Math.round((quizCorrect / quizTotal) * 100) : 0
  return { contentCount, quizCount, quizCorrect, quizTotal, quizPct }
}

export function encouragementText(pct: number, hasQuiz = true): string {
  if (!hasQuiz) return '完成本次学习，继续加油'
  if (pct >= 90) return '太棒了！你已经掌握得很好了'
  if (pct >= 70) return '不错哦，再巩固一下就更稳了'
  return '还需要继续努力，同学再接再厉吧'
}
