/** 宿主班级/作业 API（走 Cookie 会话） */

export interface ClassRoom {
  id: string
  name: string
  subject?: string
  description?: string
  inviteCode?: string
  teacherUsername?: string
  memberUsernames?: string[]
  projectIds?: string[]
  publishedProjectIds?: string[]
  updatedAt?: string
  createdAt?: string
}

export interface Homework {
  id: string
  classId: string
  title: string
  content?: string
  dueAt?: string
  allowText?: boolean
  allowFile?: boolean
  allowImage?: boolean
  /** 截止后是否允许补交 */
  allowLate?: boolean
  attachments?: Attachment[]
  createdAt?: string
}

export interface Attachment {
  id: string
  name: string
  kind?: string
  size?: number
}

export interface Submission {
  id: string
  textContent?: string
  submittedAt?: string
  attachments?: Attachment[]
  status?: string
  score?: number
  feedback?: string
  featured?: boolean
  studentUsername?: string
  /** 是否补交（截止后提交） */
  late?: boolean
}

export interface HomeworkView {
  homework: Homework
  classId: string
  className: string
  submitted: boolean
  submission?: Submission | null
  overdue?: boolean
  /** 是否仍可提交/补交 */
  canResubmit?: boolean
  canSubmit?: boolean
  late?: boolean
}

export interface Announcement {
  id: string
  title: string
  content?: string
  authorUsername?: string
  createdAt?: string
}

export interface CheckinSession {
  id: string
  classId: string
  title: string
  status: string
  createdAt?: string
}

export interface ClassLesson {
  id: string
  name?: string
  lessonTitle?: string
  digitalUrl?: string
  classOnly?: boolean
}

export interface ClassMaterial {
  id: string
  classId: string
  title: string
  description?: string
  uploaderUsername?: string
  attachment?: Attachment
  createdAt?: string
}

export interface ClassChatMessage {
  id: string
  classId: string
  username: string
  content: string
  createdAt?: string
}

export interface MemberBrief {
  username: string
  displayName?: string
  status?: string
  roleLabel?: string
  submissionCount?: number
  exists?: boolean
}

async function hostJson<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, {
    credentials: 'same-origin',
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(init?.headers || {}),
    },
  })
  const payload = await resp.json().catch(() => ({})) as {
    code?: number
    message?: string
    msg?: string
    data?: T
  }
  if (!resp.ok || payload.code !== 0) {
    throw new Error(payload.message || payload.msg || `请求失败 ${resp.status}`)
  }
  return (payload.data || {}) as T
}

export const classroomApi = {
  requestJoinCode(inviteCode: string, email: string) {
    return hostJson<{ email: string; expiresInSec: number; demoCode?: string; hint?: string }>(
      '/api/v1/classes/join/request-code',
      {
        method: 'POST',
        body: JSON.stringify({ inviteCode, email }),
      },
    )
  },
  join(inviteCode: string, email: string, emailCode: string) {
    return hostJson<{ class: ClassRoom }>('/api/v1/classes/join', {
      method: 'POST',
      body: JSON.stringify({ inviteCode, email, emailCode }),
    })
  },
  listMyClasses() {
    return hostJson<{ items: ClassRoom[] }>('/api/v1/student/classes')
  },
  getClass(classId: string) {
    return hostJson<{
      class: ClassRoom
      members?: MemberBrief[]
      assistants?: MemberBrief[]
      projects?: Array<{ id: string; name?: string; digitalUrl?: string; published?: boolean }>
      publishedProjects?: Array<{ id: string; name?: string; digitalUrl?: string }>
      overview?: Record<string, number>
      isTeacher?: boolean
      isStaff?: boolean
    }>(`/api/v1/classes/${encodeURIComponent(classId)}`)
  },
  listClassHomeworks(classId: string) {
    return hostJson<{ items: Homework[] }>(`/api/v1/classes/${encodeURIComponent(classId)}/homeworks`)
  },
  listMyHomeworks() {
    return hostJson<{ items: HomeworkView[] }>('/api/v1/student/homeworks')
  },
  submit(homeworkId: string, textContent: string, files: File[]) {
    const form = new FormData()
    if (textContent) form.append('textContent', textContent)
    files.forEach((f) => form.append('files', f))
    return hostJson<{ submission: Submission }>(`/api/v1/student/homeworks/${encodeURIComponent(homeworkId)}/submit`, {
      method: 'POST',
      body: form,
    })
  },
  listAnnouncements(classId: string) {
    return hostJson<{ items: Announcement[] }>(`/api/v1/classes/${encodeURIComponent(classId)}/announcements`)
  },
  listCheckins(classId: string) {
    return hostJson<{ items: CheckinSession[] }>(`/api/v1/classes/${encodeURIComponent(classId)}/checkins`)
  },
  signCheckin(classId: string, checkinId: string) {
    return hostJson<{ record: unknown }>(
      `/api/v1/classes/${encodeURIComponent(classId)}/checkins/${encodeURIComponent(checkinId)}/sign`,
      { method: 'POST', body: '{}' },
    )
  },
  listFeatured(classId: string) {
    return hostJson<{ items: Submission[] }>(`/api/v1/classes/${encodeURIComponent(classId)}/featured`)
  },
  listClassLessons() {
    return hostJson<{ items: ClassLesson[] }>('/api/v1/student/class-lessons')
  },
  listMaterials(classId: string) {
    return hostJson<{ items: ClassMaterial[] }>(`/api/v1/classes/${encodeURIComponent(classId)}/materials`)
  },
  listChat(classId: string, limit = 80) {
    return hostJson<{ items: ClassChatMessage[] }>(
      `/api/v1/classes/${encodeURIComponent(classId)}/chat?limit=${limit}`,
    )
  },
  postChat(classId: string, content: string) {
    return hostJson<{ message: ClassChatMessage }>(`/api/v1/classes/${encodeURIComponent(classId)}/chat`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    })
  },
}
