const OPEN_RE = /<(think|thinking|redacted_reasoning)>/i
const CLOSE_RE = /<\/(think|thinking|redacted_reasoning)>/i
const PARTIAL_OPEN_RE = /<(?:\/)?(?:think(?:ing)?|redacted_reasoning)?$/i
const THINK_BLOCK_RE = /<(think|thinking|redacted_reasoning)>[\s\S]*?<\/\1>/gi

export type ThinkFeedResult = {
  thinking: string
  content: string
  thinkStarted: boolean
  thinkEnded: boolean
}

export type SplitStoredMessage = {
  thinkingContent: string
  content: string
}

/** Remove all think-tag blocks and stream markers from answer text */
export function stripThinkTags(text: string): string {
  return text
    .replace(/\x01T\x01/g, '')
    .replace(/\x01C\x01/g, '')
    .replace(THINK_BLOCK_RE, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

/** If answer repeats thinking prefix, remove the overlapping part */
export function dedupeThinkingFromAnswer(content: string, thinking: string): string {
  let answer = stripThinkTags(content)
  const t = thinking.trim()
  if (!t || !answer) return answer

  for (const probeLen of [200, 120, 80, 40]) {
    const probe = t.slice(0, Math.min(probeLen, t.length))
    if (probe.length >= 20 && answer.startsWith(probe)) {
      answer = answer.slice(probe.length).trim()
      break
    }
  }

  if (t.length > 60 && answer.includes(t.slice(0, Math.min(80, t.length)))) {
    answer = answer.replace(t.slice(0, Math.min(80, t.length)), '').trim()
  }

  return answer
}

/** Remove consecutive duplicate paragraphs or repeated halves */
export function removeRepeatedSections(text: string): string {
  const t = text.trim()
  if (!t) return t

  // Detect full copy repeated later (handles with/without blank line separator)
  const anchor = t.split('\n').slice(0, 4).join('\n').trim()
  if (anchor.length >= 12) {
    const repeatAt = t.indexOf(anchor, Math.max(anchor.length, 1))
    if (repeatAt > 0) return t.slice(0, repeatAt).trim()
  }

  const paras = t.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean)
  const seen = new Set<string>()
  const unique: string[] = []
  for (const p of paras) {
    const key = p.replace(/\s+/g, ' ').slice(0, 120)
    if (key.length > 20 && seen.has(key)) continue
    seen.add(key)
    unique.push(p)
  }
  if (unique.length < paras.length) return unique.join('\n\n')

  if (t.length >= 120) {
    const mid = Math.floor(t.length / 2)
    const first = t.slice(0, mid).trim()
    const second = t.slice(mid).trim()
    const probe = first.slice(0, Math.min(100, first.length))
    if (probe.length >= 40 && second.startsWith(probe)) return first
  }

  return t
}

export function sanitizeAnswerContent(content: string, thinking: string): string {
  return removeRepeatedSections(dedupeThinkingFromAnswer(content, thinking))
}

/** Append stream chunk; tolerate cumulative (full-so-far) payloads */
export function appendStreamContent(current: string, chunk: string): string {
  const base = current || ''
  const next = chunk || ''
  if (!next) return base
  if (!base) return next
  if (next.startsWith(base)) return next
  if (base.startsWith(next)) return base
  if (base.endsWith(next)) return base
  return base + next
}

export function splitStoredMessage(raw: string): SplitStoredMessage {
  const match = raw.match(/<(think|thinking|redacted_reasoning)>([\s\S]*?)<\/\1>/i)
  if (!match) {
    return { thinkingContent: '', content: stripThinkTags(raw) }
  }
  return {
    thinkingContent: match[2].trim(),
    content: sanitizeAnswerContent(raw.replace(match[0], ''), match[2]),
  }
}

export function createThinkStreamSplitter() {
  let mode: 'content' | 'think' = 'content'
  let carry = ''
  let thinkStartTime: number | null = null

  function feed(raw: string): ThinkFeedResult {
    let thinking = ''
    let content = ''
    let thinkStarted = false
    let thinkEnded = false
    carry += raw

    while (carry.length) {
      if (mode === 'content') {
        const openMatch = carry.match(OPEN_RE)
        if (openMatch?.index != null) {
          content += carry.slice(0, openMatch.index)
          carry = carry.slice(openMatch.index + openMatch[0].length)
          mode = 'think'
          if (thinkStartTime == null) {
            thinkStartTime = Date.now()
            thinkStarted = true
          }
          continue
        }
        const partial = carry.match(PARTIAL_OPEN_RE)
        if (partial?.index != null && partial.index < carry.length) {
          content += carry.slice(0, partial.index)
          carry = carry.slice(partial.index)
          break
        }
        content += carry
        carry = ''
      } else {
        const closeMatch = carry.match(CLOSE_RE)
        if (closeMatch?.index != null) {
          thinking += carry.slice(0, closeMatch.index)
          carry = carry.slice(closeMatch.index + closeMatch[0].length)
          mode = 'content'
          thinkEnded = true
          continue
        }
        const partial = carry.match(PARTIAL_OPEN_RE)
        if (partial?.index != null && partial.index < carry.length) {
          thinking += carry.slice(0, partial.index)
          carry = carry.slice(partial.index)
          break
        }
        thinking += carry
        carry = ''
      }
    }

    return { thinking, content, thinkStarted, thinkEnded }
  }

  function getThinkDurationSec(): number | null {
    if (thinkStartTime == null) return null
    return Math.max(1, Math.round((Date.now() - thinkStartTime) / 1000))
  }

  function flush(): ThinkFeedResult {
    if (!carry) {
      return { thinking: '', content: '', thinkStarted: false, thinkEnded: false }
    }
    if (mode === 'think') {
      const result = { thinking: carry, content: '', thinkStarted: false, thinkEnded: false }
      carry = ''
      mode = 'content'
      return result
    }
    const result = { thinking: '', content: carry, thinkStarted: false, thinkEnded: false }
    carry = ''
    return result
  }

  function reset() {
    mode = 'content'
    carry = ''
    thinkStartTime = null
  }

  return { feed, flush, getThinkDurationSec, reset }
}

/** Close unclosed inline markdown so partial bold/code render during stream. */
function closeOpenMarkdownDelimiters(text: string): string {
  let out = text
  const boldCount = (out.match(/\*\*/g) || []).length
  if (boldCount % 2 !== 0) out += '**'
  const tickPairs = out.split('```').length - 1
  if (tickPairs % 2 !== 0) out += '\n```'
  return out
}

/** Normalize partial markdown while streaming so headings/bold render incrementally. */
export function normalizeStreamingMarkdown(text: string): string {
  if (!text) return text
  return closeOpenMarkdownDelimiters(
    text
      .replace(/(^|\n)(#{1,6})([^\s#\n])/g, '$1$2 $3')
      .replace(/---+(?=#{1,6})/g, '---\n\n')
      .replace(/([^\n])(#{1,6}\s)/g, '$1\n\n$2')
      .replace(/([^\n])(\*\*[^*\n]{1,40}：\*\*)/g, '$1\n\n$2')
      .replace(/([^\n])(\*\*步骤\s*\d+)/g, '$1\n\n$2')
      .replace(/([^\n])([-*•]\s+\*\*)/g, '$1\n\n$2')
      .replace(/\n{3,}/g, '\n\n'),
  )
}

/** Extract key bullet/numbered lines for compact thinking preview */
export function summarizeThinking(text: string, maxLines = 6): string {
  if (!text.trim()) return ''
  const lines = text
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => l.replace(/^#{1,6}\s*/, ''))

  const keyLines = lines.filter((l) =>
    /^(\d+[\.\)、]|[-*•○]|步骤|分析|确定|起草|Draft\s*\d|首先|其次|最后|结论)/i.test(l),
  )

  const picked = (keyLines.length >= 2 ? keyLines : lines.filter((l) => l.length >= 8))
    .slice(0, maxLines)
    .map((l, i) => {
      const cleaned = l.replace(/^(\d+[\.\)、]|[-*•○]\s*)/, '').trim()
      const body = cleaned.length > 140 ? `${cleaned.slice(0, 137)}…` : cleaned
      return `${i + 1}. ${body}`
    })

  return picked.join('\n')
}
