/** 学习路径 → 资源中心：一键生成意图（sessionStorage，避免 keep-alive / 路由时序丢参） */

export const PATH_GEN_INTENT_KEY = 'edunexus_path_resource_gen_intent'

export interface PathResourceGenIntent {
  topic: string
  goal?: string
  node_id: number
  path_id?: number
  created_at: number
}

export function savePathResourceGenIntent(intent: Omit<PathResourceGenIntent, 'created_at'>) {
  const payload: PathResourceGenIntent = { ...intent, created_at: Date.now() }
  sessionStorage.setItem(PATH_GEN_INTENT_KEY, JSON.stringify(payload))
}

export function consumePathResourceGenIntent(maxAgeMs = 5 * 60 * 1000): PathResourceGenIntent | null {
  const raw = sessionStorage.getItem(PATH_GEN_INTENT_KEY)
  if (!raw) return null
  sessionStorage.removeItem(PATH_GEN_INTENT_KEY)
  try {
    const data = JSON.parse(raw) as PathResourceGenIntent
    if (!data?.topic || !data?.node_id) return null
    if (Date.now() - (data.created_at || 0) > maxAgeMs) return null
    return data
  } catch {
    return null
  }
}

export function peekPathResourceGenIntent(): PathResourceGenIntent | null {
  const raw = sessionStorage.getItem(PATH_GEN_INTENT_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as PathResourceGenIntent
  } catch {
    return null
  }
}
