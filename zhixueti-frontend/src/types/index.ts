/** Shared TypeScript types aligned with backend API */

export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
  timestamp: string
}

export interface PageData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface UserInfo {
  id: number
  username: string
  email: string | null
  phone: string | null
  student_no: string | null
  nickname: string
  real_name: string | null
  avatar_url: string | null
  user_type: number
  major: string | null
  bio: string | null
  grade: number | null
  status: number
  roles: string[]
  created_at: string
  last_login_at?: string | null
}

export interface TokenData {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface DimensionValue {
  dimension_code: string
  dimension_name: string
  dimension_value: Record<string, unknown>
  confidence: number
  source_type: string
  updated_at: string
  display_score?: number
}

export interface DimensionProgressItem {
  dimension_code: string
  dimension_name: string
  description: string
  status: 'pending' | 'active' | 'completed'
  confidence: number
  fusion_confidence?: number
  display_score: number
  dimension_value: Record<string, unknown> | null
  source_contributions?: Array<{ source: string; weight: number }>
  updated_at: string | null
  questions_answered?: number
  questions_total?: number
}

export interface ProfileData {
  id: number
  user_id: number
  profile_version: number
  completeness: number
  avg_confidence: number
  learning_goal: string | null
  status: number
  confirmed_at: string | null
  dimensions: DimensionValue[]
  dimension_progress: DimensionProgressItem[]
  core_dimension_count: number
  completed_dimension_count: number
  total_question_count: number
  completed_question_count: number
  is_profile_built: boolean
  created_at: string
  updated_at: string
}

export interface DialogueHistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface DialogueStartData {
  session_no: string
  profile_id: number
  task_no: string
  message: string
  messages?: DialogueHistoryMessage[]
  current_dimension_code: string
  current_dimension_name: string
  completeness: number
  dimension_progress: DimensionProgressItem[]
  completed_question_count?: number
  total_question_count?: number
  current_question_index?: number
}

export interface DialogueMessageData {
  session_no: string
  round_no: number
  assistant_message: string
  extracted_dims: Record<string, unknown> | null
  updated_dimensions: string[]
  completeness: number
  is_completed: boolean
  current_dimension_code: string | null
  current_dimension_name: string | null
  dimension_progress: DimensionProgressItem[]
  completed_count: number
  total_count: number
  completed_question_count?: number
  total_question_count?: number
  current_question_index?: number
}

export interface QuestionnaireItem {
  dimension_code: string
  question: string
  options: { id: string; label: string }[]
}

export interface AssessmentQuestionItem {
  id: string
  topic: string
  stem: string
  options: string[]
  difficulty: number
  discrimination: number
}

export interface BehaviorGenerateData {
  profile: ProfileData
  features_used: Record<string, unknown>
  updated_dimensions: string[]
}

export interface ProfileModesMeta {
  behavior_available: boolean
  has_profile_data: boolean
  preferred_mode: string | null
}

export interface LearningStats {
  total_study_hours: number
  resources_learned: number
  knowledge_points_completed: number
  avg_accuracy: number
  study_hours_change_pct: number
  resources_change_pct: number
  knowledge_change_pct: number
  accuracy_change_pct: number
  trend_7d: Array<{ date: string; minutes: number }>
  trend_30d: Array<{ date: string; minutes: number }>
  mastery_items: Array<{ name: string; value: number }>
  path_progress_rate: number
  path_completed_nodes: number
  path_total_nodes: number
  path_title: string | null
  recent_records: Array<{
    resource_name: string
    study_time: string
    duration_minutes: number
    node_name?: string | null
  }>
  has_data: boolean
}

export interface ResourceItem {
  id: number
  resource_no: string
  type_code: string
  type_name: string
  title: string
  summary: string | null
  topic: string
  difficulty: number
  status: number
  audit_status: number
  fact_check_status: number
  citation_count: number
  agent_task_id: number | null
  created_at: string
  published_at: string | null
  author_name?: string | null
  detail?: Record<string, unknown> | null
}

export interface NodeResourceItem {
  resource_id: number
  title: string
  type_code: string
  type_name: string
  resource_role: string
  is_learned?: boolean
}

export interface PathNode {
  id: number
  node_code: string
  node_name: string
  node_type: string
  phase: string
  phase_name: string
  description: string | null
  sort_order: number
  difficulty: number
  estimated_min: number
  status: number
  mastery_score: number | null
  resources: number[]
  resource_items: NodeResourceItem[]
  expected_resource_types: string[]
  is_weak?: boolean
  is_adaptive?: boolean
  prereq_names?: string[]
  learned_resource_count?: number
  total_resource_count?: number
}

export interface PathPhase {
  phase: string
  phase_name: string
  description: string
  node_ids: number[]
  completed_count: number
  total_count: number
}

export interface PathEdge {
  from_node_id: number
  to_node_id: number
  edge_type: string
}

export interface PathData {
  id: number
  path_no: string
  title: string
  goal: string
  path_version: number
  total_nodes: number
  estimated_hours: number
  status: number
  progress_rate: number
  path_mode?: 'profile' | 'standard'
  nodes: PathNode[]
  phases: PathPhase[]
  edges: PathEdge[]
  profile_snapshot: Record<string, unknown> | null
  weak_focus?: string[]
  adaptive_node_count?: number
  created_at: string
}

export interface TaskStage {
  stage_code: string
  stage_name: string
  stage_order: number
  status: number
  progress: number
  message: string | null
}

export interface AgentRunInfo {
  id: number
  agent_code: string
  agent_name: string
  status: number
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  output_preview: string | null
}

export interface PartialPreview {
  agent_code: string
  agent_name?: string
  type?: string
  preview?: string
  resource_id?: number
  title?: string
  data?: unknown
}

export interface TaskData {
  id: number
  task_no: string
  task_type: string
  task_name: string
  status: number
  progress: number
  current_stage: string | null
  output_result: Record<string, unknown> | null
  error_message: string | null
  stages: TaskStage[]
  agent_runs: AgentRunInfo[]
  partial_previews: PartialPreview[]
  learning_diagnosis: Record<string, unknown> | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface AgentDefinition {
  id: number
  agent_code: string
  agent_name: string
  agent_type: string
  description: string | null
  default_model: string
  status: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  streaming?: boolean
}

export interface TutorKnowledgePoint {
  point_code: string
  point_name: string
  domain: string
  difficulty: number
}

export interface TutorRelatedResource {
  resource_id: number
  title: string
  type_code: string
  type_name: string
  topic: string
}

export interface TutorMessageMeta {
  knowledge_points: TutorKnowledgePoint[]
  related_resources: TutorRelatedResource[]
  message_type: string
  strategy_used: string | null
  hint_level: number
  is_exercise: boolean
  web_sources?: Array<{ title: string; url: string; snippet?: string }>
  doc_citations?: Array<{ doc_id: string; filename: string; page: number; snippet?: string }>
  slides?: TutorSlide[]
  multimodal?: Record<string, unknown> | null
  disclaimer?: string | null
  web_search_timeout?: boolean
  /** 沉浸式视频讲解 ID，用于对话内重新进入 */
  lecture_id?: string
  lecture_topic?: string
  lecture_slide_count?: number
}

export interface TutorLectureSlide {
  id: number
  type: 'content' | 'quiz'
  title?: string
  bullets?: string[]
  highlight?: string
  mermaid?: string | null
  narration?: string
  question?: string
  options?: string[]
  answer?: string
  multi?: boolean
  analysis?: string
}

export interface TutorLectureData {
  lecture_id: string
  topic: string
  slides: TutorLectureSlide[]
  content_slide_count?: number
  quiz_count?: number
  recommendations?: string[]
  created_at?: string
  resource_id?: number
}

export interface TutorLectureSummary {
  topic: string
  knowledge_point_count: number
  quiz_count: number
  correct_count: number
  total_quizzes: number
  accuracy: number
  mastery: string
  recommendations: string[]
}

export interface TutorSlide {
  title: string
  bullets?: string[]
  highlight?: string
  mermaid?: string | null
}

export interface TutorOutlineItem {
  title: string
  objectives?: string[]
  duration_min?: number
}

export interface TutorDocumentItem {
  doc_id: string
  filename: string
  page_count: number
  preview?: string
}

export interface TutorVideoStep {
  label: string
  content: string
  duration_sec?: number
}

export interface TutorMessageItem {
  id: number
  round_no: number
  role: string
  content: string
  message_type: string
  strategy_used: string | null
  meta?: TutorMessageMeta | null
  created_at: string
}

export interface TutorSessionData {
  session_no: string
  topic: string
  tutor_mode: string
  zpd_level: number
  status: number
  total_rounds: number
  profile_summary: string
  messages: TutorMessageItem[]
  created_at: string
  updated_at: string
  profile_adapt_enabled?: boolean
  answer_detail?: string
  show_steps?: boolean
  deep_mode?: boolean
  web_search_enabled?: boolean
  document_ids?: string[]
}

export type ResourceTypeCode = 'document' | 'mindmap' | 'reading' | 'video' | 'code' | 'question'

export const PHASE_STYLE: Record<string, { color: string; bg: string; icon: string }> = {
  intro: { color: '#2563eb', bg: '#eff6ff', icon: '🌱' },
  intermediate: { color: '#f59e0b', bg: '#fffbeb', icon: '🚀' },
  advanced: { color: '#10b981', bg: '#ecfdf5', icon: '🏆' },
}

export const NODE_STATUS_MAP: Record<number, { label: string; type: string }> = {
  0: { label: '锁定', type: 'info' },
  1: { label: '可学习', type: 'primary' },
  2: { label: '学习中', type: 'warning' },
  3: { label: '已完成', type: 'success' },
  4: { label: '已跳过', type: 'info' },
}

export const RESOURCE_TYPE_ICON: Record<string, string> = {
  document: 'Document',
  mindmap: 'Share',
  reading: 'Reading',
  video: 'VideoCamera',
  code: 'Monitor',
  question: 'QuestionFilled',
}
