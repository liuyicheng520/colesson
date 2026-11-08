/** 智课共生「共生课程学习」进度（与宿主 student/course-study.js 共用 key） */

export const GONGSHENG_PROGRESS_KEY = 'ai_teacher_course_study_progress_v1'

export interface GongshengLesson {
  id: string
  title: string
  subject?: string
  teacher?: string
  status?: string
  summary?: string
  resourceCount?: number
  updatedAt?: string
  publishedAt?: string
}

export interface GongshengLocalProgress {
  percent: number
  updatedAt?: string
  lastSectionId?: string
  completedSections?: string[]
}

export type GongshengProgressMap = Record<string, GongshengLocalProgress>

export function readGongshengProgress(): GongshengProgressMap {
  try {
    const raw = localStorage.getItem(GONGSHENG_PROGRESS_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as GongshengProgressMap
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

export function normalizeGongshengLesson(raw: Record<string, unknown>): GongshengLesson {
  const resourcesField = raw.resources
  const resourceCount = Array.isArray(resourcesField)
    ? resourcesField.length
    : Number(raw.resourceCount || 0)
  const subjectMode = raw.subjectMode ?? raw.subject_mode
  return {
    id: String(raw.id || raw.projectId || ''),
    title: String(raw.lessonTitle || raw.lesson_title || raw.title || raw.name || '未命名智课'),
    subject: raw.subject
      ? String(raw.subject)
      : subjectMode
        ? String(subjectMode)
        : raw.courseName
          ? String(raw.courseName)
          : undefined,
    teacher: raw.teacher
      ? String(raw.teacher)
      : raw.author_name
        ? String(raw.author_name)
        : raw.teacherName
          ? String(raw.teacherName)
          : raw.meta
            ? String(raw.meta)
            : undefined,
    status: raw.status ? String(raw.status) : 'published',
    summary: raw.summary
      ? String(raw.summary)
      : raw.lessonIntro
        ? String(raw.lessonIntro)
        : raw.lesson_intro
          ? String(raw.lesson_intro)
          : raw.description
            ? String(raw.description)
            : undefined,
    resourceCount,
    updatedAt: raw.updatedAt
      ? String(raw.updatedAt)
      : raw.updated_at
        ? String(raw.updated_at)
        : undefined,
    publishedAt: raw.publishedAt
      ? String(raw.publishedAt)
      : raw.published_at
        ? String(raw.published_at)
        : undefined,
  }
}

export async function fetchPublishedLessons(): Promise<GongshengLesson[]> {
  // 带凭据走学生端接口：仅班级可见（发给本班）的智课对学生可见；
  // 匿名公开接口会把这些课过滤掉，导致学生课程中心看不到本班课程。
  const resp = await fetch('/published-lessons', {
    method: 'GET',
    credentials: 'include',
  })
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`)
  }
  const payload = await resp.json()
  const list = (payload?.data?.projects
    || payload?.data?.items
    || payload?.projects
    || []) as Record<string, unknown>[]
  return (Array.isArray(list) ? list : [])
    .map(normalizeGongshengLesson)
    .filter((x) => x.id)
}

export interface GongshengOverview {
  lessonCount: number
  startedCount: number
  completedCount: number
  avgPercent: number
  recent: Array<{ id: string; title: string; percent: number; updatedAt?: string }>
  lessons: GongshengLesson[]
  progressMap: GongshengProgressMap
  error?: string
}

export async function loadGongshengOverview(): Promise<GongshengOverview> {
  const progressMap = readGongshengProgress()
  let lessons: GongshengLesson[] = []
  let error: string | undefined
  try {
    lessons = await fetchPublishedLessons()
  } catch (e) {
    error = e instanceof Error ? e.message : '加载失败'
  }

  const titleById = new Map(lessons.map((l) => [l.id, l.title]))
  const entries = Object.entries(progressMap)
  const startedCount = entries.filter(([, p]) => (p?.percent || 0) > 0).length
  const completedCount = entries.filter(([, p]) => (p?.percent || 0) >= 100).length
  const avgPercent = entries.length
    ? Math.round(entries.reduce((sum, [, p]) => sum + (p?.percent || 0), 0) / entries.length)
    : 0

  const recent = entries
    .map(([id, p]) => ({
      id,
      title: titleById.get(id) || `智课 ${id.slice(0, 8)}`,
      percent: Math.round(p?.percent || 0),
      updatedAt: p?.updatedAt,
    }))
    .sort((a, b) => String(b.updatedAt || '').localeCompare(String(a.updatedAt || '')))
    .slice(0, 5)

  return {
    lessonCount: lessons.length,
    startedCount,
    completedCount,
    avgPercent,
    recent,
    lessons,
    progressMap,
    error,
  }
}

export function openGongshengWorkbench(lessonId: string): void {
  // 沉浸学习页仅学生端；需已登录学生身份（未登录会跳转学生登录）
  const url = `/student.html?projectId=${encodeURIComponent(lessonId)}`
  window.open(url, '_blank', 'noopener')
}

export function clearGongshengProgress(lessonId: string): void {
  const map = readGongshengProgress()
  if (!map[lessonId]) return
  delete map[lessonId]
  localStorage.setItem(GONGSHENG_PROGRESS_KEY, JSON.stringify(map))
}

export function getGongshengProgress(lessonId: string): GongshengLocalProgress | null {
  const p = readGongshengProgress()[lessonId]
  return p || null
}
