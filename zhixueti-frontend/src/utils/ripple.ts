// 按钮涟漪：鸿蒙 / Huawei 风格原生 Ripple（纯视觉层，不拦截交互、不改动按钮原有行为）
// 点击烟花粒子特效已停用；如恢复，两者可并存（粒子全局触发，涟漪只在按钮内部按落点扩散）。

const HOST_SELECTOR = 'button, .btn, .el-button, [role="button"]'
const RIPPLE_CLASS = 'z-ripple'
const HOST_CLASS = 'z-ripple-host'
const STYLE_ID = 'z-ripple-style'
/** 单个按钮内最多保留的并行波纹数（连续点击叠加，超出移除最旧一层） */
const MAX_PER_HOST = 6
/** 扩散时长：克制轻快，无回弹 */
const DURATION_MS = 420

interface Rgba {
  r: number
  g: number
  b: number
  a: number
}

const STYLE_TEXT = `
.${HOST_CLASS} { position: relative; overflow: hidden; }
.${RIPPLE_CLASS} {
  position: absolute;
  display: block;
  border-radius: 50%;
  pointer-events: none;
  z-index: 0;
  transform: scale(0);
  will-change: transform, opacity;
  animation: z-ripple-expand ${DURATION_MS}ms linear forwards;
}
@keyframes z-ripple-expand {
  0% { transform: scale(0); opacity: 1; }
  100% { transform: scale(1); opacity: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .${RIPPLE_CLASS} { display: none; animation: none; }
}
`

function parseColor(raw: string): Rgba | null {
  const m = raw.match(/rgba?\(([^)]+)\)/i)
  if (!m) return null
  const parts = m[1]
    .split(/[,\s/]+/)
    .filter(Boolean)
    .map((v) => Number.parseFloat(v))
  if (parts.length < 3 || parts.some((v) => Number.isNaN(v))) return null
  return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 }
}

function ensureStyle(): void {
  if (document.getElementById(STYLE_ID)) return
  const style = document.createElement('style')
  style.id = STYLE_ID
  style.textContent = STYLE_TEXT
  document.head.appendChild(style)
}

/** 让按钮成为涟漪宿主：定位 + 严格裁剪（不改动 box-shadow / 焦点环） */
function ensureHost(host: HTMLElement): void {
  if (host.classList.contains(HOST_CLASS)) return
  const cs = getComputedStyle(host)
  if (cs.position === 'static') host.style.position = 'relative'
  if (cs.overflow === 'visible') host.style.overflow = 'hidden'
  host.classList.add(HOST_CLASS)
}

/** 单色半透明：按按钮底色明暗取色，贴合主题 */
function resolveRipple(host: HTMLElement): Rgba {
  const cs = getComputedStyle(host)
  const bg = parseColor(cs.backgroundColor)
  const brand =
    parseColor(cs.getPropertyValue('--el-color-primary').trim()) ||
    parseColor(cs.getPropertyValue('--brand').trim()) ||
    { r: 37, g: 99, b: 235, a: 1 }

  // 透明底（幽灵 / 文字按钮）：品牌色淡染
  if (!bg || bg.a < 0.15) return { r: brand.r, g: brand.g, b: brand.b, a: 0.2 }

  // 深色实底：白色涟漪
  const luminance = (0.2126 * bg.r + 0.7152 * bg.g + 0.0722 * bg.b) / 255
  if (luminance < 0.45) return { r: 255, g: 255, b: 255, a: 0.26 }

  // 浅色实底：优先用有彩度的文字色（plain / 幽灵按钮的主色），否则中性淡灰
  const fg = parseColor(cs.color)
  const chroma = fg ? Math.max(fg.r, fg.g, fg.b) - Math.min(fg.r, fg.g, fg.b) : 0
  if (fg && chroma >= 24) return { r: fg.r, g: fg.g, b: fg.b, a: 0.18 }
  return { r: 15, g: 23, b: 42, a: 0.1 }
}

/** 低羽化边缘：主体到 86% 保持纯色，末段收边，无模糊滤镜、无外发光 */
function rippleBackground(c: Rgba): string {
  const solid = `rgba(${c.r}, ${c.g}, ${c.b}, ${c.a})`
  const clear = `rgba(${c.r}, ${c.g}, ${c.b}, 0)`
  return `radial-gradient(circle closest-side, ${solid} 0%, ${solid} 86%, ${clear} 100%)`
}

function isDisabled(host: HTMLElement): boolean {
  if (host.hasAttribute('disabled')) return true
  if (host.getAttribute('aria-disabled') === 'true') return true
  return host.classList.contains('is-disabled')
}

export function installButtonRipple(): void {
  if (typeof window === 'undefined' || typeof document === 'undefined') return
  const w = window as unknown as { __buttonRippleInstalled?: boolean }
  if (w.__buttonRippleInstalled) return
  w.__buttonRippleInstalled = true

  const reduceMq =
    typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-reduced-motion: reduce)')
      : null

  ensureStyle()

  function onPointerDown(e: PointerEvent): void {
    // 仅主键 / 触摸
    if (e.pointerType === 'mouse' && e.button !== 0) return
    // 每帧读取，支持系统设置实时切换
    if (reduceMq?.matches) return

    const target = e.target as Element | null
    if (!target || typeof target.closest !== 'function') return
    const host = target.closest(HOST_SELECTOR) as HTMLElement | null
    if (!host || isDisabled(host)) return

    const rect = host.getBoundingClientRect()
    if (rect.width < 2 || rect.height < 2) return

    ensureHost(host)

    // 以落点为原点；半径取到四角最大距离，展开结束恰好贴合按钮边界
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    const radius = Math.max(
      Math.hypot(x, y),
      Math.hypot(rect.width - x, y),
      Math.hypot(x, rect.height - y),
      Math.hypot(rect.width - x, rect.height - y),
    )
    if (!Number.isFinite(radius) || radius <= 0) return

    const wave = document.createElement('span')
    wave.className = RIPPLE_CLASS
    wave.setAttribute('aria-hidden', 'true')
    wave.style.left = `${x - radius}px`
    wave.style.top = `${y - radius}px`
    wave.style.width = `${radius * 2}px`
    wave.style.height = `${radius * 2}px`
    wave.style.background = rippleBackground(resolveRipple(host))
    host.appendChild(wave)

    // 连续点击叠加；超过上限时移除最旧的一层
    const waves = host.querySelectorAll<HTMLElement>(`.${RIPPLE_CLASS}`)
    if (waves.length > MAX_PER_HOST) waves[0]?.remove()

    // 鼠标松开不中断：动画自然跑完再移除
    wave.addEventListener('animationend', () => wave.remove(), { once: true })
  }

  document.addEventListener('pointerdown', onPointerDown, { passive: true })
}
