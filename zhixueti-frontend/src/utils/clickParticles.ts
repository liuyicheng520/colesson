// 全站点击特效：彩色粒子爆裂 + 扩散光圈（纯视觉层，不拦截任何交互）
const COLORS = ['#60a5fa', '#818cf8', '#a78bfa', '#f472b6', '#fbbf24', '#34d399', '#22d3ee', '#fb923c']

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  size: number
  color: string
  born: number
  ttl: number
}

interface Ring {
  x: number
  y: number
  born: number
  ttl: number
}

export function installClickParticles(): void {
  if (typeof window === 'undefined' || typeof document === 'undefined') return
  const w = window as unknown as { __clickParticlesInstalled?: boolean }
  if (w.__clickParticlesInstalled) return
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  w.__clickParticlesInstalled = true

  const canvas = document.createElement('canvas')
  canvas.setAttribute('aria-hidden', 'true')
  canvas.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;pointer-events:none;z-index:99999;'
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const resize = () => {
    canvas.width = Math.max(1, Math.round(window.innerWidth * dpr))
    canvas.height = Math.max(1, Math.round(window.innerHeight * dpr))
  }
  resize()
  window.addEventListener('resize', resize, { passive: true })

  let particles: Particle[] = []
  let rings: Ring[] = []
  let raf = 0

  function spawn(x: number, y: number) {
    const now = performance.now()
    const count = 16
    for (let i = 0; i < count; i++) {
      const angle = (Math.PI * 2 * i) / count + Math.random() * 0.6
      const speed = 2.2 + Math.random() * 4.6
      particles.push({
        x,
        y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 1.6,
        size: 1.8 + Math.random() * 2.6,
        color: COLORS[(Math.random() * COLORS.length) | 0],
        born: now,
        ttl: 520 + Math.random() * 420,
      })
    }
    rings.push({ x, y, born: now, ttl: 420 })
    if (!raf) raf = requestAnimationFrame(tick)
  }

  function tick() {
    const now = performance.now()
    ctx!.clearRect(0, 0, canvas.width, canvas.height)
    ctx!.save()
    ctx!.scale(dpr, dpr)
    particles = particles.filter((p) => {
      const t = (now - p.born) / p.ttl
      if (t >= 1) return false
      p.x += p.vx
      p.y += p.vy
      p.vy += 0.16
      p.vx *= 0.985
      p.vy *= 0.985
      ctx!.globalAlpha = 1 - t
      ctx!.fillStyle = p.color
      ctx!.beginPath()
      ctx!.arc(p.x, p.y, Math.max(0.4, p.size * (1 - t * 0.4)), 0, Math.PI * 2)
      ctx!.fill()
      return true
    })
    rings = rings.filter((r) => {
      const t = (now - r.born) / r.ttl
      if (t >= 1) return false
      ctx!.globalAlpha = (1 - t) * 0.55
      ctx!.strokeStyle = '#93c5fd'
      ctx!.lineWidth = 2 * (1 - t) + 0.5
      ctx!.beginPath()
      ctx!.arc(r.x, r.y, 6 + t * 34, 0, Math.PI * 2)
      ctx!.stroke()
      return true
    })
    ctx!.restore()
    if (particles.length || rings.length) {
      raf = requestAnimationFrame(tick)
    } else {
      raf = 0
      ctx!.clearRect(0, 0, canvas.width, canvas.height)
    }
  }

  function onPointer(e: PointerEvent) {
    if (e.pointerType === 'mouse' && e.button !== 0) return
    spawn(e.clientX, e.clientY)
  }

  document.body.appendChild(canvas)
  window.addEventListener('pointerdown', onPointer, { passive: true })
}
