/** 统一按北京时间（Asia/Shanghai）展示 */

export const BEIJING_TZ = 'Asia/Shanghai'

/**
 * 解析接口时间。
 * 后端多为 UTC 无时区字符串（datetime.utcnow / timezone.utc 去 tzinfo），
 * 无时区信息时按 UTC 解析，再格式化为北京时间。
 */
export function parseApiDate(value: string | Date | null | undefined): Date | null {
  if (value == null || value === '') return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value

  const raw = String(value).trim()
  if (!raw) return null

  const hasTz = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(raw)
  let normalized = raw
  if (!hasTz) {
    const withT = raw.includes('T') ? raw : raw.replace(' ', 'T')
    normalized = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(withT) ? withT : `${withT}Z`
  }

  const d = new Date(normalized)
  return Number.isNaN(d.getTime()) ? null : d
}

export function formatBeijingDateTime(
  value: string | Date | null | undefined,
  fallback = '-',
): string {
  const d = parseApiDate(value)
  if (!d) return fallback
  return d.toLocaleString('zh-CN', {
    timeZone: BEIJING_TZ,
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

/** MM-DD HH:mm（路径下拉等紧凑展示） */
export function formatBeijingShort(
  value: string | Date | null | undefined,
  fallback = '',
): string {
  const d = parseApiDate(value)
  if (!d) return fallback
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: BEIJING_TZ,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(d)
  const get = (type: string) => parts.find((p) => p.type === type)?.value || ''
  return `${get('month')}-${get('day')} ${get('hour')}:${get('minute')}`
}

/** 相对「今天」的友好时间（答疑会话列表） */
export function formatBeijingFriendly(
  value: string | Date | null | undefined,
  fallback = '',
): string {
  const d = parseApiDate(value)
  if (!d) return fallback
  const now = new Date()
  const sameDay = new Intl.DateTimeFormat('en-CA', { timeZone: BEIJING_TZ }).format(d)
    === new Intl.DateTimeFormat('en-CA', { timeZone: BEIJING_TZ }).format(now)
  if (sameDay) {
    return d.toLocaleTimeString('zh-CN', {
      timeZone: BEIJING_TZ,
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  }
  return d.toLocaleString('zh-CN', {
    timeZone: BEIJING_TZ,
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

/** 仅日期（课件导出等） */
export function formatBeijingDate(
  value: string | Date | null | undefined = new Date(),
  fallback = '',
): string {
  const d = parseApiDate(value) ?? (value == null ? new Date() : null)
  if (!d) return fallback
  return d.toLocaleDateString('zh-CN', {
    timeZone: BEIJING_TZ,
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}
