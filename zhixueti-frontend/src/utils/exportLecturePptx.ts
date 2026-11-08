import type { TutorLectureSlide } from '@/types'
import { formatBeijingDate } from '@/utils/datetime'

/** 与讲解页 slide-frame 一致的配色 */
const THEME = {
  purple: '7C3AED',
  purpleLight: 'EDE9FE',
  indigo: '6366F1',
  slate900: '0F172A',
  slate700: '334155',
  slate500: '64748B',
  slate400: '94A3B8',
  bg: 'F8FAFC',
  card: 'FFFFFF',
  highlightBg: 'EFF6FF',
  highlightBorder: '2563EB',
  quizAccent: 'F59E0B',
  font: 'Microsoft YaHei',
} as const

const SLIDE = { w: 10, h: 5.625 } as const

function safeFilename(topic: string): string {
  const base = topic.replace(/[\\/*?:"<>|]/g, '_').trim().slice(0, 40) || 'lecture'
  return base.endsWith('.pptx') ? base : `${base}.pptx`
}

function formatDate(): string {
  return formatBeijingDate(new Date(), new Date().toLocaleDateString('zh-CN'))
}

function arrayBufferToDataUri(buffer: ArrayBuffer, mime: string): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  const chunk = 8192
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk))
  }
  return `data:${mime};base64,${btoa(binary)}`
}

async function svgToPngDataUri(svg: string, scale = 2): Promise<string | null> {
  const parser = new DOMParser()
  const doc = parser.parseFromString(svg, 'image/svg+xml')
  const svgEl = doc.documentElement
  if (svgEl.querySelector('parsererror')) return null

  let width = parseFloat(String(svgEl.getAttribute('width') || '').replace(/px$/, ''))
  let height = parseFloat(String(svgEl.getAttribute('height') || '').replace(/px$/, ''))
  if (!width || !height) {
    const vb = svgEl.getAttribute('viewBox')?.trim().split(/[\s,]+/).map(Number)
    if (vb && vb.length === 4) {
      width = vb[2]
      height = vb[3]
    }
  }
  if (!width || !height) {
    width = 960
    height = 540
  }

  svgEl.setAttribute('width', String(width))
  svgEl.setAttribute('height', String(height))
  if (!svgEl.getAttribute('xmlns')) svgEl.setAttribute('xmlns', 'http://www.w3.org/2000/svg')

  const serialized = new XMLSerializer().serializeToString(svgEl)
  const blob = new Blob([serialized], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(blob)

  try {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = () => reject(new Error('svg load failed'))
      img.src = url
    })

    const canvas = document.createElement('canvas')
    canvas.width = Math.ceil(width * scale)
    canvas.height = Math.ceil(height * scale)
    const ctx = canvas.getContext('2d')
    if (!ctx) return null

    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.scale(scale, scale)
    ctx.drawImage(img, 0, 0, width, height)

    return canvas.toDataURL('image/png')
  } catch {
    return null
  } finally {
    URL.revokeObjectURL(url)
  }
}

/** Kroki 服务端渲染 PNG，兼容 mindmap 等复杂语法 */
async function mermaidToPngViaKroki(code: string): Promise<string | null> {
  try {
    const resp = await fetch('https://kroki.io/mermaid/png', {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain' },
      body: code,
    })
    if (!resp.ok) return null
    const buf = await resp.arrayBuffer()
    if (!buf.byteLength) return null
    return arrayBufferToDataUri(buf, 'image/png')
  } catch {
    return null
  }
}

async function mermaidToPngLocal(code: string): Promise<string | null> {
  const trimmed = code.trim()
  if (!trimmed) return null

  const mermaid = (await import('mermaid')).default
  mermaid.initialize({
    startOnLoad: false,
    theme: 'default',
    securityLevel: 'loose',
    fontFamily: 'Microsoft YaHei, sans-serif',
    flowchart: { htmlLabels: false, useMaxWidth: false },
    sequence: { htmlLabels: false },
    er: { htmlLabels: false },
  })

  try {
    await mermaid.parse(trimmed)
  } catch {
    return null
  }

  const id = `lecture-export-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const { svg } = await mermaid.render(id, trimmed)
  if (/Syntax error in text|class="error-text"|error-icon/.test(svg)) return null

  return svgToPngDataUri(svg)
}

/** 导出用 PNG：优先 Kroki 服务端渲染（文字完整），离线时回退本地 */
async function mermaidToPngDataUri(code: string): Promise<string | null> {
  const trimmed = code.trim()
  if (!trimmed) return null

  const kroki = await mermaidToPngViaKroki(trimmed)
  if (kroki) return kroki

  return mermaidToPngLocal(trimmed)
}

type PptxSlide = {
  addShape: (shape: string, opts: Record<string, unknown>) => void
  addText: (text: unknown, opts?: Record<string, unknown>) => void
  addImage: (opts: Record<string, unknown>) => void
  addNotes: (notes: string) => void
  background?: { color?: string }
}

function addTopAccentBar(page: PptxSlide) {
  page.addShape('rect', {
    x: 0,
    y: 0,
    w: SLIDE.w,
    h: 0.14,
    fill: { color: THEME.purple },
    line: { color: THEME.purple, width: 0 },
  })
}

function addSlideFooter(page: PptxSlide, topic: string, pageNum: number, total: number) {
  page.addShape('rect', {
    x: 0,
    y: SLIDE.h - 0.38,
    w: SLIDE.w,
    h: 0.38,
    fill: { color: THEME.bg },
    line: { color: 'E2E8F0', width: 0.5 },
  })
  page.addText(topic, {
    x: 0.45,
    y: SLIDE.h - 0.32,
    w: 6,
    h: 0.25,
    fontSize: 8,
    color: THEME.slate400,
    fontFace: THEME.font,
    truncate: true,
  })
  page.addText(`智课共生  ·  ${pageNum} / ${total}`, {
    x: 7.2,
    y: SLIDE.h - 0.32,
    w: 2.35,
    h: 0.25,
    fontSize: 8,
    color: THEME.slate400,
    fontFace: THEME.font,
    align: 'right',
  })
}

function addTitleSlide(pptx: { addSlide: () => PptxSlide }, topic: string, slideCount: number) {
  const page = pptx.addSlide()
  page.background = { color: THEME.purple }

  page.addShape('rect', {
    x: 0,
    y: 3.2,
    w: SLIDE.w,
    h: 2.425,
    fill: { color: THEME.bg },
    line: { color: THEME.bg, width: 0 },
  })

  page.addText('智课共生', {
    x: 0.8,
    y: 0.55,
    w: 3,
    h: 0.45,
    fontSize: 14,
    bold: true,
    color: 'FFFFFF',
    fontFace: THEME.font,
    charSpacing: 2,
  })

  page.addText(topic, {
    x: 0.8,
    y: 1.35,
    w: 8.4,
    h: 1.6,
    fontSize: 36,
    bold: true,
    color: 'FFFFFF',
    fontFace: THEME.font,
    valign: 'top',
  })

  page.addText('AI 沉浸式讲解', {
    x: 0.8,
    y: 3.45,
    w: 4,
    h: 0.4,
    fontSize: 13,
    color: THEME.slate500,
    fontFace: THEME.font,
  })

  page.addText(`${formatDate()}  ·  共 ${slideCount} 页`, {
    x: 0.8,
    y: 3.95,
    w: 5,
    h: 0.35,
    fontSize: 11,
    color: THEME.slate400,
    fontFace: THEME.font,
  })
}

function addClosingSlide(
  pptx: { addSlide: () => PptxSlide },
  topic: string,
  stats: { content: number; quiz: number },
  pageNum: number,
  total: number,
) {
  const page = pptx.addSlide()
  page.background = { color: THEME.bg }
  addTopAccentBar(page)

  page.addShape('roundRect', {
    x: 1.2,
    y: 0.55,
    w: 7.6,
    h: 4.35,
    fill: { color: THEME.card },
    line: { color: 'E2E8F0', width: 1 },
    rectRadius: 0.08,
  })

  page.addText('课程完成', {
    x: 1.6,
    y: 0.85,
    w: 6.8,
    h: 0.55,
    fontSize: 26,
    bold: true,
    color: THEME.slate900,
    fontFace: THEME.font,
    align: 'center',
  })

  page.addText(`恭喜完成「${topic}」的学习`, {
    x: 1.6,
    y: 1.45,
    w: 6.8,
    h: 0.45,
    fontSize: 14,
    color: THEME.slate500,
    fontFace: THEME.font,
    align: 'center',
  })

  page.addShape('rect', {
    x: 2.2,
    y: 2.15,
    w: 2.2,
    h: 1.35,
    fill: { color: THEME.purpleLight },
    line: { color: 'DDD6FE', width: 0.5 },
  })
  page.addText(String(stats.content), {
    x: 2.2,
    y: 2.35,
    w: 2.2,
    h: 0.55,
    fontSize: 28,
    bold: true,
    color: THEME.purple,
    fontFace: THEME.font,
    align: 'center',
  })
  page.addText('内容页', {
    x: 2.2,
    y: 2.95,
    w: 2.2,
    h: 0.35,
    fontSize: 11,
    color: THEME.slate500,
    fontFace: THEME.font,
    align: 'center',
  })

  page.addShape('rect', {
    x: 5.6,
    y: 2.15,
    w: 2.2,
    h: 1.35,
    fill: { color: 'FEF3C7' },
    line: { color: 'FDE68A', width: 0.5 },
  })
  page.addText(String(stats.quiz), {
    x: 5.6,
    y: 2.35,
    w: 2.2,
    h: 0.55,
    fontSize: 28,
    bold: true,
    color: THEME.quizAccent,
    fontFace: THEME.font,
    align: 'center',
  })
  page.addText('测验题', {
    x: 5.6,
    y: 2.95,
    w: 2.2,
    h: 0.35,
    fontSize: 11,
    color: THEME.slate500,
    fontFace: THEME.font,
    align: 'center',
  })

  page.addText('继续探索，保持好奇心 ✦', {
    x: 1.6,
    y: 3.75,
    w: 6.8,
    h: 0.4,
    fontSize: 12,
    italic: true,
    color: THEME.indigo,
    fontFace: THEME.font,
    align: 'center',
  })

  addSlideFooter(page, topic, pageNum, total)
}

async function addContentSlide(
  pptx: { addSlide: () => PptxSlide; ShapeType: { roundRect: string } },
  slide: TutorLectureSlide,
  topic: string,
  pageNum: number,
  total: number,
) {
  const page = pptx.addSlide()
  page.background = { color: THEME.bg }
  addTopAccentBar(page)

  page.addText(slide.title || '', {
    x: 0.55,
    y: 0.28,
    w: 8.9,
    h: 0.65,
    fontSize: 24,
    bold: true,
    color: THEME.slate900,
    fontFace: THEME.font,
    valign: 'middle',
  })

  const hasMermaid = Boolean(slide.mermaid?.trim())
  const textW = hasMermaid ? 4.85 : 8.85
  const bullets = slide.bullets || []

  page.addShape('roundRect', {
    x: 0.45,
    y: 1.05,
    w: textW + 0.1,
    h: slide.highlight ? 3.55 : 3.85,
    fill: { color: THEME.card },
    line: { color: 'E2E8F0', width: 0.75 },
    rectRadius: 0.06,
  })

  if (bullets.length) {
    const bulletLines = bullets.map((b) => ({
      text: b,
      options: { bullet: { code: '2022' }, fontSize: 14, color: THEME.slate700, fontFace: THEME.font },
    }))
    page.addText(bulletLines, {
      x: 0.65,
      y: 1.2,
      w: textW - 0.2,
      h: slide.highlight ? 2.4 : 3.5,
      valign: 'top',
      paraSpaceBefore: 8,
      lineSpacingMultiple: 1.15,
    })
  }

  if (slide.highlight) {
    page.addShape('rect', {
      x: 0.65,
      y: bullets.length ? 3.55 : 2.0,
      w: textW - 0.4,
      h: 0.85,
      fill: { color: THEME.highlightBg },
      line: { color: THEME.highlightBorder, width: 0 },
    })
    page.addShape('rect', {
      x: 0.65,
      y: bullets.length ? 3.55 : 2.0,
      w: 0.06,
      h: 0.85,
      fill: { color: THEME.highlightBorder },
      line: { color: THEME.highlightBorder, width: 0 },
    })
    page.addText(slide.highlight, {
      x: 0.85,
      y: bullets.length ? 3.62 : 2.08,
      w: textW - 0.65,
      h: 0.7,
      fontSize: 12,
      bold: true,
      color: '1D4ED8',
      fontFace: THEME.font,
      valign: 'middle',
    })
  }

  if (hasMermaid && slide.mermaid) {
    page.addShape('roundRect', {
      x: 5.55,
      y: 1.05,
      w: 4.0,
      h: 3.85,
      fill: { color: THEME.card },
      line: { color: 'DDD6FE', width: 0.75 },
      rectRadius: 0.06,
    })
    page.addText('知识图解', {
      x: 5.7,
      y: 1.12,
      w: 2,
      h: 0.28,
      fontSize: 9,
      bold: true,
      color: THEME.purple,
      fontFace: THEME.font,
    })
    const imgData = await mermaidToPngDataUri(slide.mermaid)
    if (imgData) {
      page.addImage({
        data: imgData,
        x: 5.65,
        y: 1.42,
        w: 3.8,
        h: 3.35,
        sizing: { type: 'contain', w: 3.8, h: 3.35 },
      })
    }
  }

  addSlideFooter(page, topic, pageNum, total)

  if (slide.narration) {
    page.addNotes(`【讲解稿】\n${slide.narration}`)
  }
}

function addQuizSlide(
  pptx: { addSlide: () => PptxSlide },
  slide: TutorLectureSlide,
  topic: string,
  pageNum: number,
  total: number,
) {
  const page = pptx.addSlide()
  page.background = { color: THEME.bg }
  addTopAccentBar(page)

  page.addShape('roundRect', {
    x: 0.55,
    y: 0.35,
    w: 1.35,
    h: 0.38,
    fill: { color: 'FEF3C7' },
    line: { color: 'FDE68A', width: 0.5 },
    rectRadius: 0.08,
  })
  page.addText('随堂测验', {
    x: 0.55,
    y: 0.38,
    w: 1.35,
    h: 0.32,
    fontSize: 10,
    bold: true,
    color: 'B45309',
    fontFace: THEME.font,
    align: 'center',
  })

  page.addText(slide.question || '', {
    x: 0.55,
    y: 0.9,
    w: 8.9,
    h: 0.9,
    fontSize: 20,
    bold: true,
    color: THEME.slate900,
    fontFace: THEME.font,
    valign: 'top',
  })

  const options = slide.options || []
  options.forEach((opt, i) => {
    const y = 1.95 + i * 0.72
    page.addShape('roundRect', {
      x: 0.65,
      y,
      w: 8.7,
      h: 0.58,
      fill: { color: THEME.card },
      line: { color: 'E2E8F0', width: 0.75 },
      rectRadius: 0.05,
    })
    page.addText(opt, {
      x: 0.85,
      y: y + 0.1,
      w: 8.3,
      h: 0.4,
      fontSize: 14,
      color: THEME.slate700,
      fontFace: THEME.font,
      valign: 'middle',
    })
  })

  if (slide.multi) {
    page.addText('（多选题）', {
      x: 2.0,
      y: 0.38,
      w: 1.2,
      h: 0.32,
      fontSize: 9,
      color: THEME.slate400,
      fontFace: THEME.font,
    })
  }

  addSlideFooter(page, topic, pageNum, total)

  const noteParts = [slide.narration, slide.analysis ? `【解析】${slide.analysis}` : ''].filter(Boolean)
  if (noteParts.length) page.addNotes(noteParts.join('\n\n'))
}

/**
 * 客户端导出讲解 PPTX：封面 + 内容/测验 + 封底，含 Mermaid 图解与品牌样式。
 */
export async function exportLecturePptxClient(topic: string, slides: TutorLectureSlide[]): Promise<void> {
  const PptxGenJS = (await import('pptxgenjs')).default
  const pptx = new PptxGenJS()
  pptx.layout = 'LAYOUT_16x9'
  pptx.author = '智课共生'
  pptx.company = '智课共生'
  pptx.subject = topic
  pptx.title = topic

  const contentCount = slides.filter((s) => s.type !== 'quiz').length
  const quizCount = slides.filter((s) => s.type === 'quiz').length
  const totalPages = slides.length + 2

  addTitleSlide(pptx, topic, slides.length)

  let pageNum = 2
  for (const slide of slides) {
    if (slide.type === 'quiz') {
      addQuizSlide(pptx, slide, topic, pageNum, totalPages)
    } else {
      await addContentSlide(pptx, slide, topic, pageNum, totalPages)
    }
    pageNum += 1
  }

  addClosingSlide(pptx, topic, { content: contentCount, quiz: quizCount }, totalPages, totalPages)

  await pptx.writeFile({ fileName: safeFilename(topic) })
}
