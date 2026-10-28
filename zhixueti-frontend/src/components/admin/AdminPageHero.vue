<script setup lang="ts">
import { computed } from 'vue'
import { ADMIN_HERO_MAP, type AdminHeroKey } from './adminHeroConfig'

const props = defineProps<{
  module: AdminHeroKey
  /** Override title when page title differs slightly */
  title?: string
  subtitle?: string
}>()

const cfg = computed(() => ADMIN_HERO_MAP[props.module])
const title = computed(() => props.title || cfg.value.title)
const subtitle = computed(() => props.subtitle || cfg.value.subtitle)
</script>

<template>
  <section
    class="admin-hero"
    :class="{ compact: cfg.compact }"
    :style="{
      '--hero-accent': cfg.accent,
      '--hero-soft': cfg.accentSoft,
    }"
  >
    <div class="hero-copy">
      <p class="hero-kicker">智课共生管理端</p>
      <h2 class="hero-title">{{ title }}</h2>
      <p class="hero-sub">{{ subtitle }}</p>
    </div>

    <div class="hero-art" aria-hidden="true">
      <!-- 数据大盘：仪表盘 -->
      <svg v-if="module === 'dashboard'" viewBox="0 0 200 120" fill="none">
        <rect x="16" y="18" width="168" height="84" rx="12" fill="var(--hero-soft)" />
        <rect x="28" y="30" width="70" height="40" rx="6" fill="#fff" opacity="0.9" />
        <path d="M36 58 L48 46 L60 52 L78 34" stroke="var(--hero-accent)" stroke-width="3" stroke-linecap="round" fill="none" />
        <rect x="108" y="30" width="64" height="18" rx="4" fill="var(--hero-accent)" opacity="0.85" />
        <rect x="108" y="54" width="44" height="18" rx="4" fill="var(--hero-accent)" opacity="0.45" />
        <circle cx="156" cy="86" r="10" fill="var(--hero-accent)" opacity="0.7" />
        <circle cx="128" cy="86" r="10" fill="#fff" stroke="var(--hero-accent)" stroke-width="2" />
      </svg>

      <!-- 用户管理：学习者 -->
      <svg v-else-if="module === 'users'" viewBox="0 0 200 120" fill="none">
        <rect x="20" y="20" width="160" height="80" rx="14" fill="var(--hero-soft)" />
        <circle cx="70" cy="52" r="16" fill="var(--hero-accent)" opacity="0.9" />
        <path d="M46 88c4-14 14-20 24-20s20 6 24 20" fill="var(--hero-accent)" opacity="0.55" />
        <circle cx="130" cy="48" r="12" fill="#fff" stroke="var(--hero-accent)" stroke-width="2.5" />
        <path d="M112 84c3-11 11-16 18-16s15 5 18 16" fill="#fff" stroke="var(--hero-accent)" stroke-width="2" />
        <rect x="148" y="36" width="22" height="8" rx="4" fill="var(--hero-accent)" opacity="0.35" />
        <rect x="148" y="50" width="16" height="8" rx="4" fill="var(--hero-accent)" opacity="0.25" />
      </svg>

      <!-- 管理员：盾牌钥匙 -->
      <svg v-else-if="module === 'admins'" viewBox="0 0 200 120" fill="none">
        <rect x="18" y="18" width="164" height="84" rx="14" fill="var(--hero-soft)" />
        <path d="M100 28l36 12v22c0 22-14 36-36 44-22-8-36-22-36-44V40l36-12z" fill="#fff" stroke="var(--hero-accent)" stroke-width="3" />
        <circle cx="100" cy="58" r="10" fill="var(--hero-accent)" />
        <rect x="96" y="66" width="8" height="18" rx="2" fill="var(--hero-accent)" />
      </svg>

      <!-- 菜单：层级树 -->
      <svg v-else-if="module === 'menus'" viewBox="0 0 200 120" fill="none">
        <rect x="16" y="16" width="168" height="88" rx="12" fill="var(--hero-soft)" />
        <rect x="36" y="30" width="52" height="16" rx="5" fill="var(--hero-accent)" />
        <path d="M62 46v14M62 60h40M62 60v20M102 60v20" stroke="var(--hero-accent)" stroke-width="2.5" opacity="0.5" />
        <rect x="92" y="70" width="48" height="14" rx="4" fill="#fff" stroke="var(--hero-accent)" stroke-width="2" />
        <rect x="92" y="90" width="40" height="12" rx="4" fill="#fff" stroke="var(--hero-accent)" stroke-width="2" opacity="0.7" />
      </svg>

      <!-- 资源：书本媒体 -->
      <svg v-else-if="module === 'resources'" viewBox="0 0 200 120" fill="none">
        <rect x="14" y="18" width="172" height="84" rx="14" fill="var(--hero-soft)" />
        <rect x="36" y="32" width="40" height="56" rx="4" fill="var(--hero-accent)" opacity="0.9" transform="rotate(-6 56 60)" />
        <rect x="58" y="28" width="42" height="60" rx="4" fill="#fff" stroke="var(--hero-accent)" stroke-width="2.5" />
        <rect x="68" y="40" width="22" height="4" rx="2" fill="var(--hero-accent)" opacity="0.4" />
        <rect x="68" y="50" width="18" height="4" rx="2" fill="var(--hero-accent)" opacity="0.3" />
        <rect x="118" y="36" width="48" height="32" rx="6" fill="var(--hero-accent)" opacity="0.75" />
        <polygon points="136,46 136,58 148,52" fill="#fff" />
        <rect x="118" y="74" width="36" height="8" rx="3" fill="#fff" opacity="0.8" />
      </svg>

      <!-- 画像：雷达 -->
      <svg v-else-if="module === 'profile'" viewBox="0 0 200 120" fill="none">
        <rect x="18" y="16" width="164" height="88" rx="14" fill="var(--hero-soft)" />
        <polygon points="100,28 132,48 120,86 80,86 68,48" fill="#fff" stroke="var(--hero-accent)" stroke-width="2" opacity="0.9" />
        <polygon points="100,40 118,52 112,74 88,74 82,52" fill="var(--hero-accent)" opacity="0.35" />
        <circle cx="100" cy="58" r="4" fill="var(--hero-accent)" />
      </svg>

      <!-- 路径：路线节点 -->
      <svg v-else-if="module === 'paths'" viewBox="0 0 200 120" fill="none">
        <rect x="16" y="18" width="168" height="84" rx="14" fill="var(--hero-soft)" />
        <path d="M36 78 C60 78, 70 40, 100 40 S140 78, 164 42" stroke="var(--hero-accent)" stroke-width="3.5" fill="none" stroke-linecap="round" />
        <circle cx="36" cy="78" r="8" fill="#fff" stroke="var(--hero-accent)" stroke-width="3" />
        <circle cx="100" cy="40" r="9" fill="var(--hero-accent)" />
        <circle cx="164" cy="42" r="8" fill="#fff" stroke="var(--hero-accent)" stroke-width="3" />
      </svg>

      <!-- 生成内容：文档+光点 -->
      <svg v-else-if="module === 'generated'" viewBox="0 0 200 120" fill="none">
        <rect x="20" y="16" width="160" height="88" rx="14" fill="var(--hero-soft)" />
        <rect x="48" y="28" width="70" height="68" rx="8" fill="#fff" stroke="var(--hero-accent)" stroke-width="2.5" />
        <rect x="60" y="42" width="46" height="5" rx="2" fill="var(--hero-accent)" opacity="0.35" />
        <rect x="60" y="54" width="38" height="5" rx="2" fill="var(--hero-accent)" opacity="0.25" />
        <rect x="60" y="66" width="42" height="5" rx="2" fill="var(--hero-accent)" opacity="0.2" />
        <circle cx="140" cy="40" r="6" fill="var(--hero-accent)" />
        <circle cx="156" cy="58" r="4" fill="var(--hero-accent)" opacity="0.55" />
        <circle cx="136" cy="72" r="5" fill="var(--hero-accent)" opacity="0.35" />
      </svg>

      <!-- 文档审核：章 -->
      <svg v-else-if="module === 'documents'" viewBox="0 0 200 120" fill="none">
        <rect x="18" y="18" width="164" height="84" rx="14" fill="var(--hero-soft)" />
        <rect x="44" y="28" width="72" height="68" rx="6" fill="#fff" stroke="var(--hero-accent)" stroke-width="2.5" />
        <rect x="56" y="42" width="48" height="4" rx="2" fill="var(--hero-accent)" opacity="0.3" />
        <rect x="56" y="52" width="40" height="4" rx="2" fill="var(--hero-accent)" opacity="0.25" />
        <circle cx="140" cy="64" r="22" fill="none" stroke="var(--hero-accent)" stroke-width="3" opacity="0.85" />
        <path d="M130 64l6 6 14-14" stroke="var(--hero-accent)" stroke-width="3" stroke-linecap="round" fill="none" />
      </svg>

      <!-- 内容安全：盾牌过滤 -->
      <svg v-else-if="module === 'security'" viewBox="0 0 200 120" fill="none">
        <rect x="16" y="16" width="168" height="88" rx="14" fill="var(--hero-soft)" />
        <path d="M78 30l34 10v20c0 18-12 30-34 36-22-6-34-18-34-36V40l34-10z" fill="#fff" stroke="var(--hero-accent)" stroke-width="3" />
        <path d="M78 48v28M66 62h24" stroke="var(--hero-accent)" stroke-width="3" stroke-linecap="round" />
        <rect x="128" y="38" width="36" height="10" rx="3" fill="var(--hero-accent)" opacity="0.7" />
        <rect x="128" y="54" width="28" height="10" rx="3" fill="var(--hero-accent)" opacity="0.4" />
        <rect x="128" y="70" width="32" height="10" rx="3" fill="var(--hero-accent)" opacity="0.25" />
      </svg>

      <!-- 智能体：节点网络 -->
      <svg v-else-if="module === 'agents'" viewBox="0 0 200 120" fill="none">
        <rect x="16" y="18" width="168" height="84" rx="14" fill="var(--hero-soft)" />
        <circle cx="100" cy="40" r="12" fill="var(--hero-accent)" />
        <circle cx="58" cy="78" r="10" fill="#fff" stroke="var(--hero-accent)" stroke-width="2.5" />
        <circle cx="142" cy="78" r="10" fill="#fff" stroke="var(--hero-accent)" stroke-width="2.5" />
        <circle cx="100" cy="86" r="8" fill="var(--hero-accent)" opacity="0.55" />
        <path d="M100 52 L58 68 M100 52 L142 68 M100 52 L100 78" stroke="var(--hero-accent)" stroke-width="2.5" opacity="0.45" />
      </svg>

      <!-- 系统设置：齿轮 -->
      <svg v-else-if="module === 'settings'" viewBox="0 0 200 120" fill="none">
        <rect x="18" y="18" width="164" height="84" rx="14" fill="var(--hero-soft)" />
        <circle cx="88" cy="60" r="22" fill="#fff" stroke="var(--hero-accent)" stroke-width="8" />
        <circle cx="88" cy="60" r="8" fill="var(--hero-accent)" />
        <rect x="84" y="28" width="8" height="14" rx="2" fill="var(--hero-accent)" />
        <rect x="84" y="78" width="8" height="14" rx="2" fill="var(--hero-accent)" />
        <rect x="56" y="56" width="14" height="8" rx="2" fill="var(--hero-accent)" />
        <rect x="106" y="56" width="14" height="8" rx="2" fill="var(--hero-accent)" />
        <rect x="130" y="42" width="36" height="10" rx="4" fill="var(--hero-accent)" opacity="0.45" />
        <rect x="130" y="58" width="28" height="10" rx="4" fill="var(--hero-accent)" opacity="0.3" />
        <rect x="130" y="74" width="32" height="10" rx="4" fill="var(--hero-accent)" opacity="0.2" />
      </svg>

      <!-- 操作日志：时间轴 -->
      <svg v-else-if="module === 'logs'" viewBox="0 0 200 120" fill="none">
        <rect x="18" y="16" width="164" height="88" rx="14" fill="var(--hero-soft)" />
        <path d="M56 28v64" stroke="var(--hero-accent)" stroke-width="3" opacity="0.4" />
        <circle cx="56" cy="40" r="7" fill="var(--hero-accent)" />
        <circle cx="56" cy="64" r="7" fill="#fff" stroke="var(--hero-accent)" stroke-width="2.5" />
        <circle cx="56" cy="88" r="7" fill="#fff" stroke="var(--hero-accent)" stroke-width="2.5" />
        <rect x="76" y="32" width="80" height="16" rx="5" fill="#fff" />
        <rect x="76" y="56" width="64" height="16" rx="5" fill="#fff" opacity="0.85" />
        <rect x="76" y="80" width="72" height="16" rx="5" fill="#fff" opacity="0.7" />
      </svg>

      <!-- 异常监控：波形告警 -->
      <svg v-else viewBox="0 0 200 120" fill="none">
        <rect x="16" y="18" width="168" height="84" rx="14" fill="var(--hero-soft)" />
        <path d="M28 72 L48 72 L58 40 L72 88 L86 52 L100 72 L120 72 L132 36 L148 80 L164 72 L176 72" stroke="var(--hero-accent)" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round" />
        <circle cx="158" cy="36" r="12" fill="var(--hero-accent)" />
        <path d="M158 30v8M158 42v2" stroke="#fff" stroke-width="2.5" stroke-linecap="round" />
      </svg>
    </div>
  </section>
</template>

<style scoped lang="scss">
.admin-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  min-height: 118px;
  margin-bottom: 16px;
  padding: 18px 22px;
  border-radius: 12px;
  background:
    linear-gradient(115deg, #ffffff 0%, #ffffff 48%, var(--hero-soft) 100%);
  border: 1px solid rgba(15, 23, 42, 0.06);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
  overflow: hidden;
  position: relative;

  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 12px;
    bottom: 12px;
    width: 4px;
    border-radius: 0 4px 4px 0;
    background: var(--hero-accent);
  }

  &.compact {
    min-height: 88px;
    padding: 14px 20px;
    margin-bottom: 14px;

    .hero-art {
      width: 150px;
    }
  }
}

.hero-copy {
  min-width: 0;
  flex: 1;
  padding-left: 10px;
}

.hero-kicker {
  margin: 0 0 4px;
  font-size: 12px;
  letter-spacing: 0.06em;
  color: var(--hero-accent);
  font-weight: 600;
  opacity: 0.85;
}

.hero-title {
  margin: 0 0 6px;
  font-size: 22px;
  line-height: 1.25;
  color: #0f172a;
  font-weight: 700;
}

.hero-sub {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: #64748b;
  max-width: 520px;
}

.hero-art {
  flex-shrink: 0;
  width: 188px;
  height: 112px;

  svg {
    width: 100%;
    height: 100%;
    display: block;
  }
}

@media (max-width: 768px) {
  .admin-hero {
    .hero-art {
      display: none;
    }
  }
}
</style>
