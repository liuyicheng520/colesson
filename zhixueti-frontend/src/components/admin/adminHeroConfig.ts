export type AdminHeroKey =
  | 'dashboard'
  | 'users'
  | 'admins'
  | 'menus'
  | 'resources'
  | 'profile'
  | 'paths'
  | 'generated'
  | 'documents'
  | 'security'
  | 'agents'
  | 'settings'
  | 'logs'
  | 'exceptions'

export interface AdminHeroConfig {
  key: AdminHeroKey
  title: string
  subtitle: string
  /** CSS color for accent wash */
  accent: string
  /** Softer wash used on the right side */
  accentSoft: string
  /** Compact bar for pages that already have dense charts */
  compact?: boolean
}

export const ADMIN_HERO_MAP: Record<AdminHeroKey, AdminHeroConfig> = {
  dashboard: {
    key: 'dashboard',
    title: '数据大盘',
    subtitle: '掌握平台活跃、学习时长与问答趋势，辅助运营决策。',
    accent: '#1d4ed8',
    accentSoft: '#dbeafe',
    compact: true,
  },
  users: {
    key: 'users',
    title: '学生用户管理',
    subtitle: '查看学员账号状态、学习概况，并支持检索与运维操作。',
    accent: '#2563eb',
    accentSoft: '#dbeafe',
  },
  admins: {
    key: 'admins',
    title: '管理员账号',
    subtitle: '维护后台权限账号与角色，保障管理端访问可控。',
    accent: '#1e3a8a',
    accentSoft: '#e0e7ff',
  },
  menus: {
    key: 'menus',
    title: '菜单配置',
    subtitle: '编排侧栏结构与权限入口，让后台导航与职责对齐。',
    accent: '#475569',
    accentSoft: '#e2e8f0',
  },
  resources: {
    key: 'resources',
    title: '学习资源管理',
    subtitle: '审核、发布与下架讲义、习题、图谱与视频等学习内容。',
    accent: '#1d4ed8',
    accentSoft: '#dbeafe',
  },
  profile: {
    key: 'profile',
    title: '画像体系配置',
    subtitle: '配置六维画像维度与采集规则，支撑个性化学习诊断。',
    accent: '#1d4ed8',
    accentSoft: '#dbeafe',
  },
  paths: {
    key: 'paths',
    title: '学习路径与知识点',
    subtitle: '维护知识图谱路径与节点，组织循序渐进的学习路线。',
    accent: '#2563eb',
    accentSoft: '#eff6ff',
  },
  generated: {
    key: 'generated',
    title: '多模态生成内容',
    subtitle: '管理智能答疑与多模态产出，追溯生成记录与质量。',
    accent: '#1e40af',
    accentSoft: '#dbeafe',
  },
  documents: {
    key: 'documents',
    title: '用户上传文档',
    subtitle: '审核学员上传材料，控制可见范围与引用合规性。',
    accent: '#3b82f6',
    accentSoft: '#eff6ff',
  },
  security: {
    key: 'security',
    title: '内容安全审核',
    subtitle: '敏感词过滤、事实校验与全链路调用追溯一体化管理。',
    accent: '#b91c1c',
    accentSoft: '#fee2e2',
  },
  agents: {
    key: 'agents',
    title: '智能体配置',
    subtitle: '查看多智能体定义与协作编排，保障生成链路可运营。',
    accent: '#1d4ed8',
    accentSoft: '#dbeafe',
  },
  settings: {
    key: 'settings',
    title: '系统设置',
    subtitle: '配置 LLM、安全策略、公告与反馈等平台运行参数。',
    accent: '#1e40af',
    accentSoft: '#dbeafe',
  },
  logs: {
    key: 'logs',
    title: '操作日志',
    subtitle: '追溯管理员关键操作，满足审计与问题定位需求。',
    accent: '#2563eb',
    accentSoft: '#eff6ff',
  },
  exceptions: {
    key: 'exceptions',
    title: '异常监控',
    subtitle: '跟踪接口异常与趋势，及时发现并清理过期故障记录。',
    accent: '#dc2626',
    accentSoft: '#fecaca',
    compact: true,
  },
}
