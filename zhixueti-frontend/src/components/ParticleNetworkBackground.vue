<script setup lang="ts">
/**
 * 知识网络粒子背景 — Three.js 3D 交互
 * - WebGL 不可用时降级为渐变静态背景
 * - 页面隐藏时暂停渲染，避免内存与 CPU 浪费
 */
import { ref, onMounted, onUnmounted, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    /** 是否启用 3D 渲染（可复用到其他页面并随时关闭） */
    enabled?: boolean
    /** 粒子数量 150-200 */
    particleCount?: number
    /** vivid=学生端灵动 / muted=管理端沉稳 */
    tone?: 'vivid' | 'muted'
  }>(),
  {
    enabled: true,
    particleCount: 72,
    tone: 'vivid',
  },
)

const containerRef = ref<HTMLElement>()
const webglSupported = ref(true)
const ready = ref(false)

let renderer: import('three').WebGLRenderer | null = null
let scene: import('three').Scene | null = null
let camera: import('three').PerspectiveCamera | null = null
let particles: Float32Array | null = null
let velocities: Float32Array | null = null
let baseColors: Float32Array | null = null
let pointsMesh: import('three').Points | null = null
let linesMesh: import('three').LineSegments | null = null
let animId = 0
let paused = false
let disposed = false

// 鼠标归一化坐标 (-1 ~ 1)
const mouse = { x: 0, y: 0, rawX: 0, rawY: 0 }
const mouseWorld = { x: 0, y: 0 }

function detectWebGL(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext('webgl2') || canvas.getContext('webgl'))
    )
  } catch {
    return false
  }
}

async function initThree() {
  if (!containerRef.value || !props.enabled || disposed) return

  // 背景底色立即显示，避免首屏全白
  ready.value = true

  webglSupported.value = detectWebGL()
  if (!webglSupported.value) return

  try {
    const THREE = await import('three')
    const container = containerRef.value
    const w = container.clientWidth || window.innerWidth
    const h = container.clientHeight || window.innerHeight
    if (w < 10 || h < 10) return

    scene = new THREE.Scene()
    camera = new THREE.PerspectiveCamera(60, w / h, 1, 2000)
  camera.position.z = 500

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(w, h)
  renderer.setClearColor(0x000000, 0)
  container.appendChild(renderer.domElement)

  // 上限压低，避免笔记本 GPU 被粒子连线拖垮
  const count = Math.min(100, Math.max(32, props.particleCount))
  const motionScale = props.tone === 'muted' ? 0.45 : 1
  const lineOpacity = props.tone === 'muted' ? 0.12 : 0.25
  const particleOpacity = props.tone === 'muted' ? 0.55 : 0.88
  particles = new Float32Array(count * 3)
  velocities = new Float32Array(count * 3)
  baseColors = new Float32Array(count * 3)
  const colors = new Float32Array(count * 3)

  // 初始化粒子：前后景层次 + 蓝紫渐变
  for (let i = 0; i < count; i++) {
    const i3 = i * 3
    particles[i3] = (Math.random() - 0.5) * 900
    particles[i3 + 1] = (Math.random() - 0.5) * 600
    particles[i3 + 2] = (Math.random() - 0.5) * 400

    velocities[i3] = (Math.random() - 0.5) * 0.4 * motionScale
    velocities[i3 + 1] = (Math.random() - 0.5) * 0.4 * motionScale
    velocities[i3 + 2] = (Math.random() - 0.5) * 0.15 * motionScale

    const t = Math.random()
    baseColors[i3] = 0.45 + t * 0.25
    baseColors[i3 + 1] = 0.55 + t * 0.15
    baseColors[i3 + 2] = 0.85 + t * 0.1
    colors[i3] = baseColors[i3]
    colors[i3 + 1] = baseColors[i3 + 1]
    colors[i3 + 2] = baseColors[i3 + 2]
  }

  const particleGeo = new THREE.BufferGeometry()
  particleGeo.setAttribute('position', new THREE.BufferAttribute(particles, 3))
  particleGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3))

  const particleMat = new THREE.PointsMaterial({
    size: props.tone === 'muted' ? 2.8 : 3.5,
    vertexColors: true,
    transparent: true,
    opacity: particleOpacity,
    sizeAttenuation: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })
  pointsMesh = new THREE.Points(particleGeo, particleMat)
  scene.add(pointsMesh)

  // 连线（动态更新）
  const maxLines = count * 3
  const linePositions = new Float32Array(maxLines * 2 * 3)
  const lineColors = new Float32Array(maxLines * 2 * 3)
  const lineGeo = new THREE.BufferGeometry()
  lineGeo.setAttribute('position', new THREE.BufferAttribute(linePositions, 3))
  lineGeo.setAttribute('color', new THREE.BufferAttribute(lineColors, 3))
  const lineMat = new THREE.LineBasicMaterial({
    vertexColors: true,
    transparent: true,
    opacity: lineOpacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })
  linesMesh = new THREE.LineSegments(lineGeo, lineMat)
  scene.add(linesMesh)

  animate()
  } catch (err) {
    console.warn('[ParticleNetworkBackground] WebGL init failed, using gradient fallback:', err)
    webglSupported.value = false
    if (renderer?.domElement?.parentNode) {
      renderer.domElement.parentNode.removeChild(renderer.domElement)
    }
    renderer = null
    scene = null
    camera = null
    pointsMesh = null
    linesMesh = null
    particles = null
    velocities = null
    baseColors = null
  }
}

/** 更新粒子位置与连线 */
function updateParticles() {
  if (!particles || !velocities || !baseColors || !pointsMesh || !linesMesh) return

  const count = particles.length / 3
  const colorAttr = pointsMesh.geometry.attributes.color.array as Float32Array
  const connectDist = 130
  const connectDistSq = connectDist * connectDist
  const mouseInfluence = 180
  const mouseInfluenceSq = mouseInfluence * mouseInfluence

  // 鼠标世界坐标（近似映射）
  mouseWorld.x = mouse.x * 450
  mouseWorld.y = mouse.y * 300

  for (let i = 0; i < count; i++) {
    const i3 = i * 3
    let px = particles[i3]
    let py = particles[i3 + 1]
    let pz = particles[i3 + 2]

    // 轻微漂移
    px += velocities[i3]
    py += velocities[i3 + 1]
    pz += velocities[i3 + 2]

    // 边界反弹
    if (Math.abs(px) > 450) velocities[i3] *= -1
    if (Math.abs(py) > 300) velocities[i3 + 1] *= -1
    if (Math.abs(pz) > 200) velocities[i3 + 2] *= -1

    // 鼠标引力偏移
    const dx = mouseWorld.x - px
    const dy = mouseWorld.y - py
    const distSq = dx * dx + dy * dy
    if (distSq < mouseInfluenceSq && distSq > 1) {
      const force = (1 - Math.sqrt(distSq) / mouseInfluence) * 0.6
      px += dx * force * 0.02
      py += dy * force * 0.02
      // 悬停区域粒子亮度提升（模拟放大效果）
      const boost = 1 + force * 0.5
      colorAttr[i3] = Math.min(1, baseColors[i3] * boost)
      colorAttr[i3 + 1] = Math.min(1, baseColors[i3 + 1] * boost)
      colorAttr[i3 + 2] = Math.min(1, baseColors[i3 + 2] * boost)
    } else {
      // 平滑恢复颜色
      colorAttr[i3] += (baseColors[i3] - colorAttr[i3]) * 0.08
      colorAttr[i3 + 1] += (baseColors[i3 + 1] - colorAttr[i3 + 1]) * 0.08
      colorAttr[i3 + 2] += (baseColors[i3 + 2] - colorAttr[i3 + 2]) * 0.08
    }

    particles[i3] = px
    particles[i3 + 1] = py
    particles[i3 + 2] = pz
  }

  pointsMesh.geometry.attributes.position.needsUpdate = true
  pointsMesh.geometry.attributes.color.needsUpdate = true

  // 重建连线
  const linePositions = linesMesh.geometry.attributes.position.array as Float32Array
  const lineColors = linesMesh.geometry.attributes.color.array as Float32Array
  let lineIdx = 0
  const maxSegments = linePositions.length / 6

  for (let i = 0; i < count && lineIdx < maxSegments; i++) {
    let connections = 0
    const i3 = i * 3
    for (let j = i + 1; j < count && connections < 3; j++) {
      const j3 = j * 3
      const ddx = particles[i3] - particles[j3]
      const ddy = particles[i3 + 1] - particles[j3 + 1]
      const ddz = particles[i3 + 2] - particles[j3 + 2]
      const dSq = ddx * ddx + ddy * ddy + ddz * ddz
      if (dSq < connectDistSq) {
        const li = lineIdx * 6
        linePositions[li] = particles[i3]
        linePositions[li + 1] = particles[i3 + 1]
        linePositions[li + 2] = particles[i3 + 2]
        linePositions[li + 3] = particles[j3]
        linePositions[li + 4] = particles[j3 + 1]
        linePositions[li + 5] = particles[j3 + 2]

        // 连线亮度：靠近鼠标时提升
        const midX = (particles[i3] + particles[j3]) / 2
        const midY = (particles[i3 + 1] + particles[j3 + 1]) / 2
        const mdx = mouseWorld.x - midX
        const mdy = mouseWorld.y - midY
        const mDist = Math.sqrt(mdx * mdx + mdy * mdy)
        const brightness = mDist < mouseInfluence ? 0.55 : 0.22

        for (let k = 0; k < 2; k++) {
          lineColors[li + k * 3] = brightness * 0.6
          lineColors[li + k * 3 + 1] = brightness * 0.75
          lineColors[li + k * 3 + 2] = brightness
        }

        lineIdx++
        connections++
      }
    }
  }

  // 清除未使用的线段
  for (let i = lineIdx * 6; i < linePositions.length; i++) {
    linePositions[i] = 0
  }
  linesMesh.geometry.setDrawRange(0, lineIdx * 2)
  linesMesh.geometry.attributes.position.needsUpdate = true
  linesMesh.geometry.attributes.color.needsUpdate = true
}

function animate() {
  if (disposed || paused || !props.enabled) return
  animId = requestAnimationFrame(animate)
  // 禁止每帧动态 import('three')，否则 Promise 微任务会持续拖垮主线程
  if (!renderer || !scene || !camera) return
  updateParticles()
  if (pointsMesh) pointsMesh.rotation.y += 0.0003
  if (linesMesh) linesMesh.rotation.y += 0.0003
  renderer.render(scene, camera)
}

function onResize() {
  if (!containerRef.value || !renderer || !camera) return
  const w = containerRef.value.clientWidth || window.innerWidth
  const h = containerRef.value.clientHeight || window.innerHeight
  if (w < 10 || h < 10) return
  camera.aspect = w / h
  camera.updateProjectionMatrix()
  renderer.setSize(w, h)
}

function onMouseMove(e: MouseEvent) {
  if (!containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  mouse.rawX = e.clientX - rect.left
  mouse.rawY = e.clientY - rect.top
  mouse.x = (mouse.rawX / rect.width) * 2 - 1
  mouse.y = -(mouse.rawY / rect.height) * 2 + 1
}

function onVisibilityChange() {
  paused = document.hidden
  if (!paused && props.enabled && !disposed) {
    cancelAnimationFrame(animId)
    animate()
  }
}

function disposeThree() {
  disposed = true
  cancelAnimationFrame(animId)
  window.removeEventListener('resize', onResize)
  window.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('visibilitychange', onVisibilityChange)

  if (pointsMesh) {
    pointsMesh.geometry.dispose()
    ;(pointsMesh.material as import('three').Material).dispose()
  }
  if (linesMesh) {
    linesMesh.geometry.dispose()
    ;(linesMesh.material as import('three').Material).dispose()
  }
  if (renderer) {
    renderer.dispose()
    if (renderer.domElement.parentNode) {
      renderer.domElement.parentNode.removeChild(renderer.domElement)
    }
  }
  renderer = null
  scene = null
  camera = null
  pointsMesh = null
  linesMesh = null
  particles = null
  velocities = null
  baseColors = null
}

watch(
  () => props.enabled,
  (val) => {
    if (val && !disposed && webglSupported.value) {
      paused = false
      animate()
    } else {
      paused = true
      cancelAnimationFrame(animId)
    }
  },
)

onMounted(() => {
  disposed = false
  window.addEventListener('resize', onResize)
  window.addEventListener('mousemove', onMouseMove)
  document.addEventListener('visibilitychange', onVisibilityChange)
  // 渐进加载：下一帧初始化 Three，让登录表单先渲染
  requestAnimationFrame(() => initThree())
})

onUnmounted(disposeThree)
</script>

<template>
  <div
    ref="containerRef"
    class="particle-network-bg"
    :class="{ ready, fallback: !webglSupported, 'tone-muted': tone === 'muted' }"
  >
    <!-- WebGL 降级：高级渐变静态背景 -->
    <div v-if="!webglSupported" class="gradient-fallback" />
    <div class="radial-overlay" />
  </div>
</template>

<style scoped lang="scss">
.particle-network-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  background: radial-gradient(ellipse at 30% 20%, #1e3a8a 0%, #0f172a 45%, #0c1222 100%);
  opacity: 1;

  &.tone-muted {
    background: radial-gradient(ellipse at 40% 15%, #172554 0%, #0a0f1a 50%, #060910 100%);
  }

  :deep(canvas) {
    display: block;
    width: 100% !important;
    height: 100% !important;
  }
}

.gradient-fallback {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 80% 60% at 50% 40%, rgba(96, 165, 250, 0.25) 0%, transparent 60%),
    radial-gradient(ellipse 60% 50% at 80% 70%, rgba(167, 139, 250, 0.18) 0%, transparent 55%),
    linear-gradient(160deg, #0f172a 0%, #1e3a8a 40%, #312e81 100%);

  &::after {
    content: '';
    position: absolute;
    inset: 0;
    background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
    opacity: 0.6;
  }
}

/* 微弱径向渐变叠加，增强纵深感 */
.radial-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(ellipse at center, transparent 30%, rgba(15, 23, 42, 0.4) 100%);
}
</style>
