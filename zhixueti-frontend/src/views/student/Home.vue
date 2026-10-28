<script setup lang="ts">
import { onActivated, onMounted, onUnmounted, computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { systemApi, type PublicSystemInfo } from '@/api/system'
import { useUserStore } from '@/stores/user'
import { classroomApi, type HomeworkView } from '@/api/classroom'
import {
  loadGongshengOverview,
  openGongshengWorkbench,
  type GongshengOverview,
} from '@/utils/gongshengProgress'

const router = useRouter()
const userStore = useUserStore()
const publicInfo = ref<PublicSystemInfo | null>(null)
const pendingHw = ref<HomeworkView[]>([])
const gongsheng = ref<GongshengOverview | null>(null)
const classCount = ref(0)
const workbenchReady = ref(false)

const announcements = computed(() => publicInfo.value?.announcements ?? [])
const isLoggedIn = computed(() => userStore.isLoggedIn)
const displayName = computed(() => {
  const n = userStore.displayName
  return n === '请填入真实姓名' ? '同学' : n
})
const pendingCount = computed(() => pendingHw.value.filter((h) => !h.submitted).length)
const continueLesson = computed(() => gongsheng.value?.recent?.[0] || null)
const avgPercent = computed(() => gongsheng.value?.avgPercent ?? 0)
const pulseLabel = computed(() => (isLoggedIn.value ? (pendingCount.value > 0 ? '待办' : '就绪') : '探索'))
const tickerItems = [
  '多智能体协同规划学习路径',
  '画像诊断后资源更贴合你',
  '作业与智课可在课程中心继续',
  '答疑围绕盲点追问，讲透为止',
]
const quickEntries = [
  { label: '课程中心', path: '/student/course-center', hint: '智课与作业' },
  { label: '画像构建', path: '/student/profile-dialogue', hint: '六维诊断' },
  { label: '智能答疑', path: '/student/tutor', hint: '追问讲解' },
  { label: '学习数据', path: '/student/dashboard', hint: '进度回看' },
]

const stats = [
  { value: '6 维', label: '学习画像诊断' },
  { value: '5+ 类', label: '多模态资源生成' },
  { value: '多智能体', label: '协同规划与答疑' },
  { value: '千人千面', label: '路径与内容适配' },
]

const features = [
  {
    num: '01',
    title: '多维学习画像',
    desc: '对话式完成学习风格、知识基础、目标诉求等维度诊断，让后续生成真正「对得上你」。',
    path: '/student/profile-dialogue',
  },
  {
    num: '02',
    title: '课程中心',
    desc: '汇聚教师发布智课与平台课程资源，按学科与教师筛选，从继续学习一键进入工作台。',
    path: '/student/course-center',
  },
  {
    num: '03',
    title: '多模态资源生成',
    desc: '讲解文档、思维导图、练习题、拓展阅读、案例/课件等按需生成，覆盖理解、巩固与应用。',
    path: '/student/resources',
  },
  {
    num: '04',
    title: '个性化学习路径',
    desc: '依据画像与目标动态规划节点顺序，资源与练习随路径推送，减少盲目刷资料。',
    path: '/student/path',
  },
  {
    num: '05',
    title: '智能答疑辅导',
    desc: '围绕你的盲点追问与讲解，把疑难讲透，而不是只丢一篇长文。',
    path: '/student/tutor',
  },
  {
    num: '06',
    title: '学情可视回看',
    desc: '用数据回看掌握度与进度，让每一次调整都有依据，学习过程可复盘。',
    path: '/student/dashboard',
  },
]

let revealObserver: IntersectionObserver | null = null
let ticking = false

function onScroll() {
  if (ticking) return
  ticking = true
  requestAnimationFrame(() => {
    const scrollY = window.scrollY
    const orbs = document.querySelectorAll('.home-landing .ambient-orb')
    if (orbs[0]) (orbs[0] as HTMLElement).style.transform = `translateY(${scrollY * 0.08}px)`
    if (orbs[1]) (orbs[1] as HTMLElement).style.transform = `translateY(${scrollY * -0.05}px)`
    if (orbs[2]) (orbs[2] as HTMLElement).style.transform = `translateY(${scrollY * 0.03}px)`
    ticking = false
  })
}

function scrollToFeatures() {
  document.getElementById('home-features')?.scrollIntoView({ behavior: 'smooth' })
}

async function loadWorkbench() {
  if (!userStore.isLoggedIn) return
  try {
    const [hw, classes, overview] = await Promise.all([
      classroomApi.listMyHomeworks().catch(() => ({ items: [] as HomeworkView[] })),
      classroomApi.listMyClasses().catch(() => ({ items: [] })),
      loadGongshengOverview().catch(() => null),
    ])
    pendingHw.value = hw.items || []
    classCount.value = (classes.items || []).length
    gongsheng.value = overview
  } catch {
    /* ignore */
  } finally {
    workbenchReady.value = true
  }
}

let hydrated = false
onActivated(() => {
  // keep-alive 返回时刷新工作台统计
  if (hydrated) void loadWorkbench()
})

onMounted(async () => {
  try {
    publicInfo.value = await systemApi.publicInfo()
  } catch {
    /* ignore */
  }
  await loadWorkbench()
  hydrated = true

  const revealEls = document.querySelectorAll('.home-landing .reveal')
  revealEls.forEach((el) => el.classList.add('reveal-pending'))

  revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible')
          entry.target.classList.remove('reveal-pending')
          revealObserver?.unobserve(entry.target)
        }
      })
    },
    { threshold: 0.1, rootMargin: '0px 0px -50px 0px' },
  )
  revealEls.forEach((el) => revealObserver?.observe(el))

  window.addEventListener('scroll', onScroll, { passive: true })
})

onUnmounted(() => {
  revealObserver?.disconnect()
  window.removeEventListener('scroll', onScroll)
})
</script>

<template>
  <div class="home-landing">
    <div class="ambient-orb orb-a" />
    <div class="ambient-orb orb-b" />
    <div class="ambient-orb orb-c" />

    <div class="landing-inner">
      <div v-if="announcements.length" class="announce-bar">
        <el-carousel
          height="40px"
          direction="vertical"
          :autoplay="announcements.length > 1"
          indicator-position="none"
        >
          <el-carousel-item v-for="a in announcements" :key="a.id">
            <div class="announce-item">
              <span class="announce-badge">公告</span>
              <strong>{{ a.title }}</strong>
              <span class="announce-content">{{ a.content }}</span>
            </div>
          </el-carousel-item>
        </el-carousel>
      </div>

      <section class="hero" :class="{ 'is-workbench': isLoggedIn }">
        <div class="hero-copy-col">
          <template v-if="isLoggedIn">
            <div class="hero-eyebrow">学习工作台</div>
            <h1 class="hero-title">
              {{ displayName }}，
              <br />
              <em>今天学什么</em>
            </h1>
            <p class="hero-desc">
              <template v-if="workbenchReady">
                {{ classCount }} 个班级 ·
                {{ pendingCount }} 份待交作业 ·
                平均进度 {{ avgPercent }}%
              </template>
              <template v-else>正在汇总你的学习待办…</template>
            </p>
            <div class="live-row">
              <span class="live-chip"><i class="pulse" />在线学习</span>
              <span class="live-chip"><i class="pulse warn" />班级 <b>{{ classCount }}</b></span>
              <span class="live-chip"><i class="pulse warn" />待交 <b>{{ pendingCount }}</b></span>
              <span class="live-chip"><i class="pulse warn" />进度 <b>{{ avgPercent }}%</b></span>
            </div>
            <div class="hero-actions">
              <button
                v-if="continueLesson"
                class="btn-primary"
                type="button"
                @click="openGongshengWorkbench(continueLesson.id)"
              >
                继续：{{ continueLesson.title }} <span>→</span>
              </button>
              <button
                v-else
                class="btn-primary"
                type="button"
                @click="router.push('/student/course-center')"
              >
                去课程中心 <span>→</span>
              </button>
              <button
                class="btn-ghost"
                type="button"
                @click="router.push(pendingCount ? '/student/course-center' : '/student/path')"
              >
                {{ pendingCount ? `待交作业 ${pendingCount}` : '查看学习路径' }}
              </button>
              <button class="btn-ghost" type="button" @click="scrollToFeatures">能力一览</button>
            </div>
            <div class="flow-rail" aria-hidden="true">
              <div class="flow-node"><div class="dot-lg" /><strong>画像</strong><span>了解你</span></div>
              <div class="flow-node"><div class="dot-lg" /><strong>资源</strong><span>为你生成</span></div>
              <div class="flow-node"><div class="dot-lg" /><strong>路径</strong><span>带你学</span></div>
              <div class="flow-node"><div class="dot-lg" /><strong>回看</strong><span>再迭代</span></div>
            </div>
          </template>
          <template v-else>
            <div class="hero-eyebrow">多智能体驱动的个性化学习</div>
            <h1 class="hero-title">
              让学习，
              <br />
              <em>因你而改</em>
            </h1>
            <p class="hero-desc">
              多智能体协同构建你的学习画像，按需生成多模态学习资源，规划专属路径——不是千人一面的资料堆，而是专属于你的学习系统。
            </p>
            <div class="live-row">
              <span class="live-chip"><i class="pulse" />系统在线</span>
              <span class="live-chip"><i class="pulse warn" />6 维画像</span>
              <span class="live-chip"><i class="pulse warn" />多智能体</span>
            </div>
            <div class="hero-actions">
              <button class="btn-primary" type="button" @click="router.push('/student/profile-dialogue')">
                开始构建画像 <span>→</span>
              </button>
              <button class="btn-ghost" type="button" @click="scrollToFeatures">
                看看系统能做什么
              </button>
            </div>
            <div class="flow-rail" aria-hidden="true">
              <div class="flow-node"><div class="dot-lg" /><strong>画像</strong><span>了解你</span></div>
              <div class="flow-node"><div class="dot-lg" /><strong>资源</strong><span>为你生成</span></div>
              <div class="flow-node"><div class="dot-lg" /><strong>路径</strong><span>带你学</span></div>
              <div class="flow-node"><div class="dot-lg" /><strong>回看</strong><span>再迭代</span></div>
            </div>
          </template>

          <div class="ticker" aria-hidden="true">
            <div class="ticker-track">
              <span v-for="(t, i) in [...tickerItems, ...tickerItems]" :key="i" class="ticker-item">
                <i />{{ t }}
              </span>
            </div>
          </div>
        </div>

        <div class="hero-visual" aria-hidden="true">
          <div class="sat s1">
            <span class="ring" />
            <span><b>{{ isLoggedIn ? classCount : '6' }}</b><small>{{ isLoggedIn ? '班级' : '画像维' }}</small></span>
          </div>
          <div class="sat s2">
            <span class="ring" />
            <span><b>{{ isLoggedIn ? pendingCount : '5+' }}</b><small>{{ isLoggedIn ? '待交' : '资源类' }}</small></span>
          </div>
          <div class="sat s3">
            <span class="ring" />
            <span><b>{{ isLoggedIn ? avgPercent + '%' : 'AI' }}</b><small>{{ isLoggedIn ? '进度' : '协同' }}</small></span>
          </div>
          <div class="sat s4">
            <span class="ring" />
            <span><b>{{ pulseLabel }}</b><small>学习脉搏</small></span>
          </div>
          <div class="orbit-wrap">
            <div class="hero-ring ring-a">
              <span class="orbit-dot d1" /><span class="orbit-dot d2" /><span class="orbit-dot d3" />
              <span class="orbit-dot d4" /><span class="orbit-dot d5" /><span class="orbit-dot d6" />
            </div>
            <div class="hero-ring ring-b">
              <span class="orbit-dot d1" /><span class="orbit-dot d2" /><span class="orbit-dot d3" />
              <span class="orbit-dot d4" /><span class="orbit-dot d5" />
            </div>
            <div class="hero-ring ring-c">
              <span class="orbit-dot d1" /><span class="orbit-dot d2" /><span class="orbit-dot d3" />
              <span class="orbit-dot d4" />
            </div>
            <div class="hero-ring ring-d">
              <span class="orbit-dot d1" /><span class="orbit-dot d2" /><span class="orbit-dot d3" />
            </div>
            <div class="hero-core" />
            <div class="hero-core-label">学</div>
          </div>
        </div>
      </section>

      <div class="quick-strip reveal">
        <button
          v-for="item in quickEntries"
          :key="item.path"
          type="button"
          class="quick-pill"
          @click="router.push(item.path)"
        >
          <span class="bar"><i /></span>
          <span class="quick-copy">
            <strong>{{ item.label }}</strong>
            <small>{{ item.hint }}</small>
          </span>
        </button>
      </div>

      <div class="stats-strip reveal">
        <div v-for="(stat, i) in stats" :key="i" class="stat-item">
          <div class="stat-value">{{ stat.value }}</div>
          <div class="stat-label">{{ stat.label }}</div>
          <div class="stat-spark" aria-hidden="true">
            <span /><span /><span /><span /><span />
          </div>
        </div>
      </div>

      <section id="home-features" class="features-section">
        <div class="features-header reveal">
          <div>
            <div class="section-label">核心能力</div>
            <h2 class="section-title">
              为真正的
              <br />
              个性化学习而设计
            </h2>
          </div>
          <p class="section-desc">
            从学情诊断、资源生成到路径推送与智能答疑，多智能体分工协作，把「了解你 → 为你生成 → 带你学下去」连成一条闭环。
          </p>
        </div>

        <div class="features-grid reveal">
          <button
            v-for="feature in features"
            :key="feature.num"
            type="button"
            class="feature-card"
            @click="router.push(feature.path)"
          >
            <div class="feature-num">{{ feature.num }}</div>
            <div class="feature-line" />
            <h3>{{ feature.title }}</h3>
            <p>{{ feature.desc }}</p>
          </button>
        </div>
      </section>

      <footer class="footer-bar">
        <div class="footer-inner">
          <span class="footer-text">智课共生 · 个性化资源生成与学习多智能体系统</span>
          <ul class="footer-links">
            <li><a href="#home-features">核心能力</a></li>
            <li><router-link to="/student/resources">资源中心</router-link></li>
            <li><router-link to="/student/tutor">智能答疑</router-link></li>
          </ul>
        </div>
      </footer>
    </div>
  </div>
</template>

<style scoped lang="scss">
.home-landing {
  --accent: #2563eb;
  --accent-light: #3b82f6;
  --accent-soft: #93c5fd;
  --accent-dim: #1d4ed8;
  --bg: #ffffff;
  --bg-soft: #f8fbff;
  --bg-elevated: #eef4ff;
  --text: #0f172a;
  --text-body: #334155;
  --text-secondary: #64748b;
  --text-muted: #94a3b8;
  --border: rgba(37, 99, 235, 0.12);
  --border-strong: rgba(37, 99, 235, 0.22);
  --glow: rgba(37, 99, 235, 0.08);

  position: relative;
  min-height: calc(100vh - 60px);
  background:
    radial-gradient(ellipse 80% 60% at 100% 0%, rgba(59, 130, 246, 0.12), transparent 55%),
    radial-gradient(ellipse 70% 50% at 0% 100%, rgba(147, 197, 253, 0.16), transparent 50%),
    linear-gradient(180deg, #ffffff 0%, #f8fbff 55%, #ffffff 100%);
  color: var(--text);
  overflow: hidden;
  font-family: 'Plus Jakarta Sans', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.ambient-orb {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  filter: blur(120px);
  z-index: 0;
  opacity: 0.45;
}

.orb-a {
  width: 520px;
  height: 520px;
  background: #60a5fa;
  top: -180px;
  right: -140px;
  animation: homeOrbFloat1 20s ease-in-out infinite;
}

.orb-b {
  width: 380px;
  height: 380px;
  background: #93c5fd;
  bottom: 8%;
  left: -100px;
  animation: homeOrbFloat2 25s ease-in-out infinite;
}

.orb-c {
  width: 280px;
  height: 280px;
  background: #bfdbfe;
  top: 48%;
  right: 18%;
  animation: homeOrbFloat3 18s ease-in-out infinite;
}

.landing-inner {
  position: relative;
  z-index: 1;
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 40px 24px;
}

.announce-bar {
  margin-top: 16px;
  background: linear-gradient(90deg, rgba(239, 246, 255, 0.96), rgba(219, 234, 254, 0.9));
  border: 1px solid rgba(59, 130, 246, 0.28);
  border-radius: 12px;
  padding: 0 16px;
  box-shadow: 0 4px 16px rgba(37, 99, 235, 0.06);

  .announce-item {
    display: flex;
    align-items: center;
    gap: 10px;
    height: 40px;
    font-size: 13px;
    overflow: hidden;
    color: var(--text);

    strong {
      font-weight: 650;
      color: #1e3a8a;
      letter-spacing: 0.01em;
    }
  }

  .announce-badge {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    height: 22px;
    padding: 0 8px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    color: #1d4ed8;
    background: rgba(37, 99, 235, 0.1);
    border: 1px solid rgba(37, 99, 235, 0.28);
  }

  .announce-content {
    color: #475569;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

.hero {
  padding: 72px 0 56px;
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(280px, 0.95fr);
  gap: clamp(24px, 4vw, 56px);
  align-items: center;
}

.hero-copy-col {
  position: relative;
  z-index: 2;
  min-width: 0;
}

.live-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 22px;
}

.live-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 7px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(37, 99, 235, 0.14);
  font-size: 0.8rem;
  font-weight: 650;
  color: #334155;
  backdrop-filter: blur(8px);

  b {
    color: #1d4ed8;
    font-variant-numeric: tabular-nums;
    font-weight: 800;
  }

  .pulse {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #22c55e;
    box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.5);
    animation: homeChipPulse 1.8s ease-out infinite;

    &.warn {
      background: #0ea5e9;
      box-shadow: 0 0 0 0 rgba(14, 165, 233, 0.45);
    }
  }
}

.flow-rail {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0;
  margin-top: 26px;
  max-width: 420px;
  position: relative;

  &::before {
    content: '';
    position: absolute;
    left: 10%;
    right: 10%;
    top: 13px;
    height: 2px;
    background: linear-gradient(90deg, #93c5fd, #2563eb, #7dd3fc);
    background-size: 200% 100%;
    animation: homeLine 5s linear infinite;
    opacity: 0.75;
  }
}

.flow-node {
  text-align: center;
  position: relative;
  z-index: 1;

  .dot-lg {
    width: 11px;
    height: 11px;
    margin: 8px auto 8px;
    border-radius: 50%;
    background: #2563eb;
    box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.4);
    animation: homeChipPulse 2.2s ease-out infinite;
  }

  &:nth-child(2) .dot-lg { animation-delay: .35s; background: #0ea5e9; }
  &:nth-child(3) .dot-lg { animation-delay: .7s; background: #38bdf8; }
  &:nth-child(4) .dot-lg { animation-delay: 1.05s; background: #60a5fa; }

  strong {
    display: block;
    font-size: 0.86rem;
    font-weight: 750;
    margin-bottom: 2px;
  }

  span {
    font-size: 0.72rem;
    color: var(--text-muted);
  }
}

.ticker {
  position: relative;
  overflow: hidden;
  margin-top: 20px;
  max-width: 480px;
  height: 32px;
  mask-image: linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent);
}

.ticker-track {
  display: flex;
  gap: 28px;
  width: max-content;
  animation: homeTicker 24s linear infinite;
}

.ticker-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
  font-size: 0.8rem;
  color: var(--text-secondary);
  font-weight: 600;

  i {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #38bdf8;
    display: inline-block;
    animation: homeCorePulse 2s ease-in-out infinite;
  }
}

.quick-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin: 8px 0 28px;
}

.quick-pill {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(8px);
  cursor: pointer;
  font: inherit;
  color: inherit;
  text-align: left;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;

  &:hover {
    transform: translateY(-3px);
    border-color: rgba(37, 99, 235, 0.35);
    box-shadow: 0 10px 24px rgba(37, 99, 235, 0.1);
  }

  .bar {
    width: 4px;
    height: 32px;
    border-radius: 999px;
    background: rgba(37, 99, 235, 0.12);
    overflow: hidden;
    flex-shrink: 0;

    i {
      display: block;
      width: 100%;
      height: 40%;
      border-radius: inherit;
      background: linear-gradient(180deg, #0ea5e9, #2563eb);
      animation: homeBarSlide 2.4s ease-in-out infinite;
    }
  }

  &:nth-child(2) .bar i { animation-delay: .3s; }
  &:nth-child(3) .bar i { animation-delay: .6s; }
  &:nth-child(4) .bar i { animation-delay: .9s; }

  .quick-copy {
    display: grid;
    gap: 2px;
    min-width: 0;

    strong {
      font-size: 0.92rem;
      font-weight: 750;
    }

    small {
      color: var(--text-muted);
      font-size: 0.74rem;
    }
  }
}

.hero-eyebrow {
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 28px;
  display: flex;
  align-items: center;
  gap: 12px;

  &::before {
    content: '';
    width: 40px;
    height: 1px;
    background: var(--accent);
  }
}

.hero-title {
  font-family: 'Plus Jakarta Sans', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-weight: 800;
  line-height: 1.12;
  letter-spacing: -0.035em;
  color: var(--text);
  margin-bottom: 28px;
  max-width: 760px;
  font-size: clamp(2.6rem, 6vw, 4.4rem);

  em {
    font-style: normal;
    font-weight: 800;
    color: var(--accent);
    position: relative;
    background: linear-gradient(120deg, #2563eb 0%, #3b82f6 55%, #60a5fa 100%);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;

    &::after {
      content: '';
      position: absolute;
      bottom: 2px;
      left: 0;
      right: 0;
      height: 3px;
      border-radius: 2px;
      background: linear-gradient(90deg, #2563eb, rgba(96, 165, 250, 0.5));
      opacity: 0.45;
    }
  }
}

.hero-desc {
  font-size: 1.1rem;
  line-height: 1.75;
  color: var(--text-secondary);
  max-width: 540px;
  margin-bottom: 44px;
}

.hero.is-workbench .hero-title {
  font-size: clamp(2.2rem, 5vw, 3.4rem);
}
.hero.is-workbench .hero-desc {
  margin-bottom: 28px;
}

.hero-actions {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.btn-primary,
.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 14px 32px;
  border-radius: 999px;
  font-weight: 600;
  font-size: 0.95rem;
  cursor: pointer;
  transition: all 0.3s ease;
}

.btn-primary {
  background: var(--accent);
  color: #fff;
  border: none;
  box-shadow: 0 10px 28px rgba(37, 99, 235, 0.28);

  &:hover {
    transform: translateY(-2px);
    background: var(--accent-light);
    box-shadow: 0 14px 36px rgba(37, 99, 235, 0.35);
  }
}

.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-strong);

  &:hover {
    color: var(--accent);
    border-color: var(--accent);
    background: var(--glow);
  }
}

.hero-visual {
  position: relative;
  width: min(100%, 440px);
  aspect-ratio: 1;
  margin: 0 auto;
  justify-self: end;
}

.orbit-wrap {
  position: absolute;
  inset: 10%;
}

.sat {
  position: absolute;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(37, 99, 235, 0.16);
  box-shadow: 0 10px 26px rgba(37, 99, 235, 0.12);
  backdrop-filter: blur(10px);
  animation: homeSatFloat 4.5s ease-in-out infinite;
  white-space: nowrap;

  b {
    display: block;
    font-size: 1.05rem;
    font-weight: 800;
    color: #2563eb;
    font-variant-numeric: tabular-nums;
    line-height: 1.1;
  }

  small {
    display: block;
    font-size: 0.7rem;
    color: var(--text-muted);
    font-weight: 600;
  }

  .ring {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    border: 2px solid rgba(37, 99, 235, 0.18);
    border-top-color: #2563eb;
    animation: homeRingRotate 1.6s linear infinite;
    flex-shrink: 0;
  }

  &.s1 { top: 4%; left: 0; }
  &.s2 { top: 14%; right: 0; animation-delay: .7s; .ring { animation-duration: 2.1s; border-top-color: #0ea5e9; } }
  &.s3 { bottom: 14%; left: -2%; animation-delay: 1.2s; .ring { animation-duration: 1.9s; animation-direction: reverse; } }
  &.s4 { bottom: 2%; right: 2%; animation-delay: 1.8s; .ring { animation-duration: 2.4s; } }
}

.hero-ring {
  position: absolute;
  border-radius: 50%;
  border: 1px solid rgba(37, 99, 235, 0.22);
}

.ring-a {
  inset: 0;
  animation: homeRingRotate 18s linear infinite;
  border-color: rgba(37, 99, 235, 0.34);
}

.ring-b {
  inset: 11%;
  animation: homeRingRotate 12s linear infinite reverse;
  border-color: rgba(59, 130, 246, 0.28);
  border-style: dashed;
}

.ring-c {
  inset: 22%;
  animation: homeRingRotate 9s linear infinite;
  border-color: rgba(96, 165, 250, 0.36);
}

.ring-d {
  inset: 33%;
  animation: homeRingRotate 6s linear infinite reverse;
  border-color: rgba(147, 197, 253, 0.48);
}

.hero-core {
  position: absolute;
  inset: 42%;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.4) 0%, rgba(37, 99, 235, 0.1) 55%, transparent 70%);
  box-shadow: 0 0 40px rgba(59, 130, 246, 0.28);
  animation: homeCorePulse 3.2s ease-in-out infinite;
}

.hero-core-label {
  position: absolute;
  inset: 42%;
  display: grid;
  place-items: center;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #1d4ed8;
  z-index: 2;
  animation: homeCorePulse 3.2s ease-in-out infinite;
}

.orbit-dot {
  position: absolute;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 8px rgba(59, 130, 246, 0.75);
}

.ring-a .orbit-dot {
  width: 7px;
  height: 7px;

  &.d1 { top: 50%; left: -3.5px; margin-top: -3.5px; }
  &.d2 { top: -3.5px; left: 50%; margin-left: -3.5px; }
  &.d3 { top: 50%; right: -3.5px; margin-top: -3.5px; }
  &.d4 { bottom: -3.5px; left: 50%; margin-left: -3.5px; }
  &.d5 { top: 14%; left: 14%; width: 5px; height: 5px; background: #60a5fa; }
  &.d6 { bottom: 18%; right: 12%; width: 4px; height: 4px; background: #93c5fd; }
}

.ring-b .orbit-dot {
  width: 6px;
  height: 6px;
  background: #3b82f6;

  &.d1 { top: 50%; left: -3px; margin-top: -3px; }
  &.d2 { top: -3px; left: 62%; }
  &.d3 { top: 68%; right: -3px; }
  &.d4 { bottom: 8%; left: 22%; width: 4px; height: 4px; background: #93c5fd; }
  &.d5 { top: 22%; right: 18%; width: 5px; height: 5px; background: #60a5fa; }
}

.ring-c .orbit-dot {
  width: 5px;
  height: 5px;
  background: #60a5fa;

  &.d1 { top: 50%; left: -2.5px; }
  &.d2 { top: -2.5px; left: 40%; }
  &.d3 { bottom: 20%; right: -2.5px; width: 4px; height: 4px; }
  &.d4 { top: 30%; left: 8%; width: 3px; height: 3px; background: #bfdbfe; }
}

.ring-d .orbit-dot {
  width: 4px;
  height: 4px;
  background: #93c5fd;

  &.d1 { top: 50%; left: -2px; }
  &.d2 { top: -2px; left: 55%; }
  &.d3 { bottom: -2px; right: 28%; width: 3px; height: 3px; background: #bfdbfe; }
}

.stats-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(8px);
}

.stat-item {
  padding: 36px 24px;
  text-align: center;
  position: relative;

  &:not(:last-child)::after {
    content: '';
    position: absolute;
    right: 0;
    top: 22%;
    height: 56%;
    width: 1px;
    background: var(--border);
  }
}

.stat-value {
  font-family: 'Plus Jakarta Sans', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: clamp(1.8rem, 3vw, 2.5rem);
  font-weight: 800;
  color: #1d4ed8;
  line-height: 1.15;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 0.82rem;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.stat-spark {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 3px;
  height: 22px;
  margin-top: 12px;

  span {
    width: 4px;
    border-radius: 2px 2px 0 0;
    background: linear-gradient(180deg, #60a5fa, #2563eb);
    opacity: 0.75;
    transform-origin: bottom;
    animation: homeSpark 1.8s ease-in-out infinite;

    &:nth-child(1) { height: 40%; }
    &:nth-child(2) { height: 70%; animation-delay: .12s; }
    &:nth-child(3) { height: 55%; animation-delay: .24s; }
    &:nth-child(4) { height: 88%; animation-delay: .36s; }
    &:nth-child(5) { height: 48%; animation-delay: .48s; }
  }
}

.features-section {
  padding: 96px 0 72px;
}

.features-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 56px;
  gap: 40px;
}

.section-label {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 14px;
}

.section-title {
  font-family: 'Plus Jakarta Sans', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: clamp(1.85rem, 3.2vw, 2.55rem);
  font-weight: 800;
  line-height: 1.25;
  letter-spacing: -0.03em;
  color: var(--text);
}

.section-desc {
  font-size: 1.02rem;
  line-height: 1.75;
  color: var(--text-secondary);
  max-width: 440px;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 2px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: 16px;
  overflow: hidden;
}

.feature-card {
  background: var(--bg);
  padding: 44px 32px;
  position: relative;
  overflow: hidden;
  transition: all 0.45s ease;
  cursor: pointer;
  text-align: left;
  border: none;
  font: inherit;
  color: inherit;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    opacity: 0;
    transition: opacity 0.45s ease;
    background: linear-gradient(135deg, var(--glow), transparent 60%);
  }

  &:hover {
    transform: translateY(-3px);
    z-index: 1;

    &::before {
      opacity: 1;
    }

    .feature-num {
      color: rgba(37, 99, 235, 0.42);
    }

    .feature-line {
      width: 64px;
    }
  }
}

.feature-num {
  font-family: 'Plus Jakarta Sans', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 3.2rem;
  font-weight: 800;
  color: rgba(37, 99, 235, 0.32);
  line-height: 1;
  margin-bottom: 20px;
  transition: color 0.45s ease;
  letter-spacing: -0.04em;
}

.feature-line {
  width: 32px;
  height: 2px;
  background: var(--accent);
  margin-bottom: 18px;
  transition: width 0.3s ease;
}

.feature-card h3 {
  font-family: 'Plus Jakarta Sans', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 1.2rem;
  font-weight: 700;
  margin-bottom: 12px;
  color: var(--text);
  letter-spacing: -0.01em;
}

.feature-card p {
  color: var(--text-secondary);
  line-height: 1.7;
  font-size: 0.92rem;
}

.footer-bar {
  padding: 32px 0 16px;
  border-top: 1px solid var(--border);
}

.footer-inner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.footer-text {
  color: var(--text-muted);
  font-size: 0.82rem;
}

.footer-links {
  display: flex;
  gap: 22px;
  list-style: none;

  a {
    color: var(--text-muted);
    text-decoration: none;
    font-size: 0.82rem;
    transition: color 0.25s ease;

    &:hover {
      color: var(--accent);
    }
  }
}

.reveal {
  opacity: 1;
  transform: none;
  transition:
    opacity 0.8s cubic-bezier(0.16, 1, 0.3, 1),
    transform 0.8s cubic-bezier(0.16, 1, 0.3, 1);

  &.reveal-pending {
    opacity: 0;
    transform: translateY(28px);
  }

  &.visible {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes homeOrbFloat1 {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
  }
  33% {
    transform: translate(-60px, 40px) scale(1.08);
  }
  66% {
    transform: translate(30px, -24px) scale(0.95);
  }
}

@keyframes homeOrbFloat2 {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
  }
  50% {
    transform: translate(48px, -56px) scale(1.1);
  }
}

@keyframes homeOrbFloat3 {
  0%,
  100% {
    transform: translate(0, 0);
  }
  50% {
    transform: translate(-36px, 28px);
  }
}

@keyframes homeRingRotate {
  to {
    transform: rotate(360deg);
  }
}

@keyframes homeChipPulse {
  0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.45); }
  70% { box-shadow: 0 0 0 9px rgba(34, 197, 94, 0); }
  100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
}

@keyframes homeSatFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

@keyframes homeTicker {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}

@keyframes homeLine {
  to { background-position: 200% 0; }
}

@keyframes homeCorePulse {
  0%, 100% { transform: scale(1); opacity: 0.9; }
  50% { transform: scale(1.06); opacity: 1; }
}

@keyframes homeBarSlide {
  0%, 100% { transform: translateY(40%); height: 35%; }
  50% { transform: translateY(0); height: 70%; }
}

@keyframes homeSpark {
  0%, 100% { transform: scaleY(0.85); opacity: 0.65; }
  50% { transform: scaleY(1.15); opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .ambient-orb,
  .hero-ring,
  .hero-core,
  .hero-core-label,
  .sat,
  .sat .ring,
  .live-chip .pulse,
  .flow-node .dot-lg,
  .ticker-track,
  .quick-pill .bar i,
  .stat-spark span {
    animation: none !important;
  }
}

@media (max-width: 1024px) {
  .hero {
    grid-template-columns: 1fr;
  }

  .hero-visual {
    width: min(340px, 78vw);
    justify-self: center;
    margin-top: 8px;
  }

  .quick-strip {
    grid-template-columns: repeat(2, 1fr);
  }

  .features-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .landing-inner {
    padding: 0 20px 20px;
  }

  .hero {
    padding: 48px 0 40px;
  }

  .sat {
    padding: 8px 10px;
    b { font-size: 0.92rem; }
  }

  .quick-strip {
    grid-template-columns: 1fr 1fr;
  }

  .stats-strip {
    grid-template-columns: repeat(2, 1fr);
  }

  .stat-item:nth-child(2)::after {
    display: none;
  }

  .features-grid {
    grid-template-columns: 1fr;
  }

  .features-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .features-section {
    padding: 64px 0 48px;
  }

  .footer-inner {
    flex-direction: column;
    align-items: flex-start;
  }

  .hero-actions {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
