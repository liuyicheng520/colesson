/**
 * 学生资源知识图谱：构图内核（移植自 brainbase lib/graph.ts）
 * 边：资源 → 主题枢纽；同主题资源之间适量弱连接。
 */
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
} from 'd3-force'
import type { ResourceItem } from '@/types'

export interface GraphNoteMeta {
  id: string
  relPath: string
  title: string
  type: string
  tags: string[]
  created?: string
  updated?: string
  links: { target: string }[]
}

export interface GNode {
  id: string
  label: string
  type: string
  relPath?: string
  created?: string
  x: number
  y: number
  r: number
  deg: number
  showLabel: boolean
  t: number
}

export interface GEdge {
  source: string
  target: string
}

export const GRAPH_W = 1200
export const GRAPH_H = 720

interface SimNode extends GNode {
  [k: string]: unknown
}

/** 资源 type_code → 图谱节点类型 */
const TYPE_MAP: Record<string, string> = {
  document: 'document',
  question: 'question',
  mindmap: 'mindmap',
  reading: 'reading',
  code: 'code',
  video: 'video',
}

export const NODE_COLORS: Record<string, string> = {
  document: '#2563eb',
  question: '#e07a45',
  mindmap: '#8b5cf6',
  reading: '#3db89a',
  code: '#e0b15a',
  video: '#ec4899',
  topic: '#64748b',
  tag: '#64748b',
}

export const TYPE_LABELS: Record<string, string> = {
  document: '课程讲义',
  question: '分层习题',
  mindmap: '知识图谱',
  reading: '拓展阅读',
  code: '实战演练',
  video: 'AI视频讲解',
  topic: '主题',
  tag: '主题',
}

export function typeLabel(type: string): string {
  return TYPE_LABELS[type] || type
}

export function nodeColor(type: string): string {
  return NODE_COLORS[type] || NODE_COLORS.document
}

export function hash01(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h = Math.imul(h ^ s.charCodeAt(i), 16777619)
  }
  return (h >>> 0) / 4294967296
}

function seedPos(id: string): { x: number; y: number } {
  const a = hash01(id)
  const b = hash01(id + ':y')
  return { x: 80 + a * (GRAPH_W - 160), y: 80 + b * (GRAPH_H - 160) }
}

function parseTime(iso?: string): number {
  if (!iso) return 0
  const t = Date.parse(iso)
  return Number.isFinite(t) ? t : 0
}

/**
 * 将个人资源列表转为构图输入。
 * - 每个资源一个节点（relPath = 资源 id 字符串）
 * - tags 含 topic，用于生成主题枢纽
 * - links 指向同主题其它资源标题，供 buildGraph 建边
 */
export function resourcesToNoteMeta(items: ResourceItem[]): GraphNoteMeta[] {
  const byTopic = new Map<string, ResourceItem[]>()
  for (const it of items) {
    const topic = (it.topic || '').trim() || '未分类'
    if (!byTopic.has(topic)) byTopic.set(topic, [])
    byTopic.get(topic)!.push(it)
  }

  const notes: GraphNoteMeta[] = []
  for (const it of items) {
    const topic = (it.topic || '').trim() || '未分类'
    const peers = byTopic.get(topic) || []
    // 同主题互链（按标题），最多连 4 个其它资源，避免全连通
    const links: { target: string }[] = []
    for (const p of peers) {
      if (p.id === it.id) continue
      if (links.length >= 4) break
      links.push({ target: p.title })
    }
    notes.push({
      id: `res:${it.id}`,
      relPath: String(it.id),
      title: it.title || `资源 ${it.id}`,
      type: TYPE_MAP[it.type_code] || 'document',
      tags: [topic],
      created: it.created_at || undefined,
      updated: it.published_at || it.created_at || undefined,
      links,
    })
  }
  return notes
}

/** 从笔记构建图谱：资源节点 + 主题/标签节点；边 = 标题互链 + 资源-主题 */
export function buildGraph(
  notes: GraphNoteMeta[],
  maxNotes = 320,
  maxTags = 40,
): { nodes: GNode[]; edges: GEdge[] } {
  if (notes.length === 0) return { nodes: [], edges: [] }

  const byTitle = new Map<string, GraphNoteMeta>()
  for (const n of notes) byTitle.set(n.title.trim().toLowerCase(), n)

  const linkScore = new Map<string, number>()
  for (const n of notes) {
    let s = n.tags.length * 0.5
    for (const l of n.links) {
      const t = byTitle.get(l.target.trim().toLowerCase())
      if (t && t.id !== n.id) {
        s += 1
        linkScore.set(t.id, (linkScore.get(t.id) || 0) + 0.35)
      }
    }
    linkScore.set(n.id, (linkScore.get(n.id) || 0) + s)
  }

  const ranked = [...notes].sort((a, b) => (linkScore.get(b.id) || 0) - (linkScore.get(a.id) || 0))
  const picked = ranked.slice(0, maxNotes)
  const pickedIds = new Set(picked.map((n) => n.id))

  const nodes: SimNode[] = picked.map((n) => {
    const pos = seedPos(n.id)
    const created = n.created || n.updated
    return {
      id: n.id,
      label: n.title,
      type: n.type,
      relPath: n.relPath,
      created,
      x: pos.x,
      y: pos.y,
      r: 10,
      deg: 0,
      showLabel: false,
      t: parseTime(created) || seedPos(n.id).x,
    }
  })
  const nodeById = new Map(nodes.map((n) => [n.id, n]))

  const edges: GEdge[] = []
  const seen = new Set<string>()
  for (const n of picked) {
    for (const l of n.links) {
      const t = byTitle.get(l.target.trim().toLowerCase())
      if (!t || !pickedIds.has(t.id) || t.id === n.id) continue
      const key = [n.id, t.id].sort().join('|')
      if (seen.has(key)) continue
      seen.add(key)
      edges.push({ source: n.id, target: t.id })
    }
  }

  const tagCount = new Map<string, number>()
  for (const n of picked) for (const t of n.tags) tagCount.set(t, (tagCount.get(t) || 0) + 1)
  const topTags = [...tagCount.entries()].sort((a, b) => b[1] - a[1]).slice(0, maxTags)

  let maxNoteT = 0
  for (const n of nodes) maxNoteT = Math.max(maxNoteT, n.t)

  for (const [tag] of topTags) {
    const id = 'tag:' + tag
    const pos = seedPos(id)
    nodes.push({
      id,
      label: tag,
      type: 'topic',
      x: pos.x,
      y: pos.y,
      r: 7,
      deg: 0,
      showLabel: false,
      t: maxNoteT + 1 + seedPos(id).x,
    })
    nodeById.set(id, nodes[nodes.length - 1])
  }
  for (const n of picked) {
    for (const t of n.tags) {
      if (topTags.some(([tt]) => tt === t)) {
        edges.push({ source: n.id, target: 'tag:' + t })
      }
    }
  }

  const deg = new Map<string, number>()
  for (const e of edges) {
    deg.set(e.source, (deg.get(e.source) || 0) + 1)
    deg.set(e.target, (deg.get(e.target) || 0) + 1)
  }
  for (const n of nodes) {
    n.deg = deg.get(n.id) || 0
    const base = n.type === 'topic' || n.type === 'tag' ? 6 : n.type === 'video' || n.type === 'mindmap' ? 12 : 9
    n.r = base + Math.min(8, n.deg) * 1.1
    n.showLabel = n.deg >= 2 || n.type === 'topic' || n.type === 'tag' || n.type === 'mindmap'
  }

  const sim = forceSimulation(nodes)
    .force(
      'link',
      forceLink(edges)
        .id((d) => (d as unknown as SimNode).id)
        .distance(95)
        .strength(0.5),
    )
    .force('charge', forceManyBody().strength(-220))
    .force('center', forceCenter(GRAPH_W / 2, GRAPH_H / 2))
    .force('x', forceX(GRAPH_W / 2).strength(0.06))
    .force('y', forceY(GRAPH_H / 2).strength(0.05))
    .force(
      'collide',
      forceCollide<SimNode>().radius((d) => d.r + 26),
    )
    .stop()
  for (let i = 0; i < 320; i++) sim.tick()

  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  for (const n of nodes) {
    minX = Math.min(minX, n.x)
    maxX = Math.max(maxX, n.x)
    minY = Math.min(minY, n.y)
    maxY = Math.max(maxY, n.y)
  }
  const pad = 46
  const sx = (GRAPH_W - pad * 2) / Math.max(1, maxX - minX)
  const sy = (GRAPH_H - pad * 2) / Math.max(1, maxY - minY)
  const s = Math.min(sx, sy, 1.6)
  for (const n of nodes) {
    n.x = pad + (n.x - minX) * s + (GRAPH_W - pad * 2 - (maxX - minX) * s) / 2
    n.y = pad + (n.y - minY) * s + (GRAPH_H - pad * 2 - (maxY - minY) * s) / 2
  }

  const cleanEdges: GEdge[] = edges.map((e) => ({
    source:
      typeof e.source === 'object' && e.source && 'id' in (e.source as object)
        ? String((e.source as { id: string }).id)
        : String(e.source),
    target:
      typeof e.target === 'object' && e.target && 'id' in (e.target as object)
        ? String((e.target as { id: string }).id)
        : String(e.target),
  }))

  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      label: n.label,
      type: n.type,
      relPath: n.relPath,
      created: n.created,
      x: n.x,
      y: n.y,
      r: n.r,
      deg: n.deg,
      showLabel: n.showLabel,
      t: n.t,
    })),
    edges: cleanEdges,
  }
}

export function growthOrder(nodes: GNode[]): string[] {
  return [...nodes].sort((a, b) => a.t - b.t || a.label.localeCompare(b.label, 'zh')).map((n) => n.id)
}
