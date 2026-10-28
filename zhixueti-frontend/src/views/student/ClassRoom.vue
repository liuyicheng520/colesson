<script setup lang="ts">
defineOptions({ name: 'StudentClassRoom' })

import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  classroomApi,
  type Announcement,
  type CheckinSession,
  type ClassChatMessage,
  type ClassLesson,
  type ClassMaterial,
  type ClassRoom,
  type HomeworkView,
  type MemberBrief,
  type Submission,
} from '@/api/classroom'
import {
  clearGongshengProgress,
  getGongshengProgress,
  openGongshengWorkbench,
  readGongshengProgress,
} from '@/utils/gongshengProgress'

const route = useRoute()
const router = useRouter()
const classId = computed(() => String(route.params.classId || ''))

const loading = ref(false)
const tab = ref('learn')
const room = ref<ClassRoom | null>(null)
const overview = ref<Record<string, number>>({})
const members = ref<MemberBrief[]>([])
const lessons = ref<ClassLesson[]>([])
const materials = ref<ClassMaterial[]>([])
const homeworks = ref<HomeworkView[]>([])
const announcements = ref<Announcement[]>([])
const checkins = ref<CheckinSession[]>([])
const featured = ref<Submission[]>([])
const chat = ref<ClassChatMessage[]>([])
const chatText = ref('')
const chatSending = ref(false)
const activeHwId = ref('')
const textContent = ref('')
const fileList = ref<File[]>([])
const submitting = ref(false)
const progressTick = ref(0)
let chatTimer: number | undefined

const tabs = [
  { key: 'learn', label: '课程学习' },
  { key: 'homework', label: '作业' },
  { key: 'materials', label: '学习资料' },
  { key: 'members', label: '班级成员' },
  { key: 'chat', label: '班级聊天' },
  { key: 'notice', label: '公告 · 签到' },
]

const labels = computed(() => {
  const name = (room.value?.name || '').trim()
  const m = name.match(/^(.*?)(\d+\s*班)$/)
  if (m && m[1]) {
    return { course: m[1].trim(), classLabel: m[2].replace(/\s+/g, '') }
  }
  if (room.value?.subject?.trim()) {
    return { course: room.value.subject.trim(), classLabel: name || '班级' }
  }
  return { course: name || '课程', classLabel: '班级' }
})

const activeTabLabel = computed(() => tabs.find((t) => t.key === tab.value)?.label || '')

function lessonProgress(id: string) {
  progressTick.value
  return Math.round(getGongshengProgress(id)?.percent || 0)
}

function openLesson(l: ClassLesson) {
  if (l.digitalUrl) {
    window.open(l.digitalUrl, '_blank', 'noopener')
    return
  }
  openGongshengWorkbench(l.id)
}

async function resetLesson(l: ClassLesson) {
  try {
    await ElMessageBox.confirm(
      `清除「${l.lessonTitle || l.name || '该智课'}」的本地学习进度，并重新开始听课？`,
      '重新学习',
      { type: 'warning', confirmButtonText: '清除并打开', cancelButtonText: '取消' },
    )
    clearGongshengProgress(l.id)
    progressTick.value += 1
    ElMessage.success('进度已清除')
    openLesson(l)
  } catch {
    /* cancel */
  }
}

async function loadCore() {
  if (!classId.value) return
  loading.value = true
  try {
    const [detail, hwAll, lessonAll, mats] = await Promise.all([
      classroomApi.getClass(classId.value),
      classroomApi.listMyHomeworks(),
      classroomApi.listClassLessons(),
      classroomApi.listMaterials(classId.value),
    ])
    room.value = detail.class
    overview.value = detail.overview || {}
    members.value = detail.members || []
    materials.value = mats.items || []
    homeworks.value = (hwAll.items || []).filter((h) => h.classId === classId.value)
    const publishedIds = new Set((detail.publishedProjects || []).map((p) => p.id))
    lessons.value = (lessonAll.items || []).filter((l) => publishedIds.has(l.id) || !publishedIds.size)
    if (!lessons.value.length && detail.publishedProjects?.length) {
      lessons.value = detail.publishedProjects.map((p) => ({
        id: p.id,
        name: p.name,
        lessonTitle: p.name,
        digitalUrl: p.digitalUrl,
        classOnly: true,
      }))
    }
    progressTick.value += 1
    void readGongshengProgress()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载班级失败')
  } finally {
    loading.value = false
  }
}

async function loadNotice() {
  if (!classId.value) return
  const [a, c, f] = await Promise.all([
    classroomApi.listAnnouncements(classId.value),
    classroomApi.listCheckins(classId.value),
    classroomApi.listFeatured(classId.value),
  ])
  announcements.value = a.items || []
  checkins.value = c.items || []
  featured.value = f.items || []
}

async function loadChat() {
  if (!classId.value) return
  const data = await classroomApi.listChat(classId.value)
  chat.value = data.items || []
}

async function sendChat() {
  const text = chatText.value.trim()
  if (!text) return
  chatSending.value = true
  try {
    await classroomApi.postChat(classId.value, text)
    chatText.value = ''
    await loadChat()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '发送失败')
  } finally {
    chatSending.value = false
  }
}

function canEditHomework(item: HomeworkView) {
  if (item.canResubmit === false || item.canSubmit === false) return false
  if (item.overdue && item.homework.allowLate === false) return false
  return true
}

function openSubmit(item: HomeworkView) {
  if (!canEditHomework(item)) {
    ElMessage.warning('已过截止时间，且本作业不允许补交')
    return
  }
  activeHwId.value = item.homework.id
  textContent.value = item.submission?.textContent || ''
  fileList.value = []
}

function onFilesChange(e: Event) {
  const input = e.target as HTMLInputElement
  fileList.value = input.files ? Array.from(input.files) : []
}

async function submitHomework() {
  if (!activeHwId.value) return
  const item = homeworks.value.find((h) => h.homework.id === activeHwId.value)
  if (item && !canEditHomework(item)) {
    ElMessage.warning('已过截止时间，且本作业不允许补交')
    return
  }
  submitting.value = true
  try {
    await classroomApi.submit(activeHwId.value, textContent.value, fileList.value)
    ElMessage.success(item?.submitted ? '补交成功' : '作业已提交')
    activeHwId.value = ''
    await loadCore()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '提交失败')
  } finally {
    submitting.value = false
  }
}

async function sign(ck: CheckinSession) {
  try {
    await classroomApi.signCheckin(ck.classId, ck.id)
    ElMessage.success('签到成功')
    await loadNotice()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '签到失败')
  }
}

const pendingHw = computed(() => homeworks.value.filter((h) => !h.submitted).length)
const openCk = computed(() => checkins.value.filter((c) => c.status === 'open').length)

watch(tab, (v) => {
  if (v === 'notice') void loadNotice()
  if (v === 'chat') void loadChat()
  if (v === 'learn') void loadNotice()
})

watch(classId, () => {
  void loadCore().then(() => {
    if (tab.value === 'notice' || tab.value === 'learn') void loadNotice()
    if (tab.value === 'chat') void loadChat()
  })
})

onMounted(() => {
  void loadCore().then(() => loadNotice())
  chatTimer = window.setInterval(() => {
    if (tab.value === 'chat') void loadChat()
  }, 8000)
})

onUnmounted(() => {
  if (chatTimer) window.clearInterval(chatTimer)
})
</script>

<template>
  <div class="space" v-loading="loading">
    <div class="atmosphere" aria-hidden="true" />

    <header class="hero">
      <div class="hero-row">
        <button type="button" class="back" @click="router.push('/student/course-center')">
          <span>←</span> 课程中心
        </button>
        <div class="hero-meta">
          <span>{{ room?.subject || '课程' }}</span>
          <span>教师 {{ room?.teacherUsername || '-' }}</span>
          <span>{{ members.length }} 名同学</span>
        </div>
      </div>

      <div class="hero-main">
        <div class="hero-copy">
          <p class="kicker">智课共生 · 班级空间</p>
          <h1>{{ labels.course }}</h1>
          <p class="subline">
            <em>{{ labels.classLabel }}</em>
            {{ room?.description || '在这里听课、交作业、查资料，并与同学老师交流。' }}
          </p>
        </div>

        <dl class="pulse">
          <div>
            <dt>智课</dt>
            <dd>{{ lessons.length }}</dd>
          </div>
          <div>
            <dt>作业</dt>
            <dd>{{ homeworks.length }}</dd>
          </div>
          <div>
            <dt>资料</dt>
            <dd>{{ materials.length }}</dd>
          </div>
          <div class="accent">
            <dt>待交</dt>
            <dd>{{ pendingHw }}</dd>
          </div>
        </dl>
      </div>

      <nav class="rail" aria-label="班级功能">
        <button
          v-for="t in tabs"
          :key="t.key"
          type="button"
          :class="{ on: tab === t.key }"
          @click="tab = t.key"
        >
          {{ t.label }}
          <i v-if="t.key === 'homework' && pendingHw">{{ pendingHw }}</i>
          <i v-if="t.key === 'notice' && openCk">{{ openCk }}</i>
        </button>
      </nav>
    </header>

    <main class="stage">
      <div class="stage-head">
        <h2>{{ activeTabLabel }}</h2>
        <p v-if="tab === 'learn'">老师按班发布的智课会出现在这里；可继续听课，或清除进度后重学。</p>
        <p v-else-if="tab === 'homework'">支持文字与文件提交，题目附件可直接下载。</p>
        <p v-else-if="tab === 'materials'">课件、讲义与实验指导，由老师上传。</p>
        <p v-else-if="tab === 'members'">查看本班同学与提交活跃度。</p>
        <p v-else-if="tab === 'chat'">本班聊天，约 8 秒自动刷新。</p>
        <p v-else>公告与签到集中在此。</p>
      </div>

      <!-- 课程学习 -->
      <section v-if="tab === 'learn'" class="block">
        <div v-if="!lessons.length" class="void">
          <strong>还没有本班智课</strong>
          <span>请等待老师在「按班发布」中发布课程。</span>
        </div>
        <ul v-else class="lesson-rows">
          <li v-for="(l, idx) in lessons" :key="l.id">
            <div class="idx">{{ String(idx + 1).padStart(2, '0') }}</div>
            <div class="body">
              <h3>{{ l.lessonTitle || l.name || l.id }}</h3>
              <div class="progress">
                <div class="track"><i :style="{ width: `${lessonProgress(l.id)}%` }" /></div>
                <span>{{ lessonProgress(l.id) }}%</span>
              </div>
            </div>
            <div class="ops">
              <button type="button" class="btn primary" @click="openLesson(l)">
                {{ lessonProgress(l.id) > 0 ? '继续听课' : '开始学习' }}
              </button>
              <button
                v-if="lessonProgress(l.id) > 0"
                type="button"
                class="btn ghost"
                @click="resetLesson(l)"
              >
                重学
              </button>
            </div>
          </li>
        </ul>

        <div class="split">
          <div>
            <h3 class="sec">快捷入口</h3>
            <div class="jump">
              <button type="button" @click="tab = 'homework'">
                <b>{{ homeworks.length }}</b>
                <span>作业 · {{ pendingHw }} 待交</span>
              </button>
              <button type="button" @click="tab = 'materials'">
                <b>{{ materials.length }}</b>
                <span>学习资料</span>
              </button>
              <button type="button" @click="tab = 'members'">
                <b>{{ members.length }}</b>
                <span>班级成员</span>
              </button>
              <button type="button" @click="tab = 'chat'">
                <b>聊</b>
                <span>班级聊天</span>
              </button>
            </div>
          </div>
          <div>
            <h3 class="sec">优秀作业</h3>
            <div v-if="!featured.length" class="void slim">暂无优秀作业展示</div>
            <article v-for="s in featured" :key="s.id" class="feat">
              <header>
                <strong>{{ s.studentUsername || '同学' }}</strong>
                <span>{{ s.score != null ? `${s.score} 分` : '优秀' }}</span>
              </header>
              <p>{{ s.textContent || '（见附件）' }}</p>
            </article>
          </div>
        </div>
      </section>

      <!-- 作业 -->
      <section v-else-if="tab === 'homework'" class="block">
        <div v-if="!homeworks.length" class="void">
          <strong>暂无作业</strong>
          <span>老师发布后会出现在这里。</span>
        </div>
        <article v-for="item in homeworks" :key="item.homework.id" class="hw">
          <div class="hw-top">
            <div>
              <h3>{{ item.homework.title }}</h3>
              <p class="meta">
                {{ item.homework.dueAt || '未设截止' }}
                ·
                <b :class="item.submitted ? 'ok' : 'warn'">
                  {{
                    item.submitted
                      ? (item.late || item.submission?.status === 'late' ? '已补交' : '已提交')
                      : item.overdue
                        ? '已截止 · 未交'
                        : '未提交'
                  }}
                </b>
                <template v-if="item.overdue && item.submitted === false && canEditHomework(item)"> · 可补交</template>
                <template v-if="item.submission?.score != null"> · 得分 {{ item.submission.score }}</template>
              </p>
            </div>
            <button
              v-if="canEditHomework(item)"
              type="button"
              class="btn primary"
              @click="openSubmit(item)"
            >
              {{ item.submitted ? (item.overdue ? '补交' : '重新提交') : '交作业' }}
            </button>
            <button v-else-if="item.submitted" type="button" class="btn ghost" disabled>
              已提交
            </button>
            <button v-else type="button" class="btn ghost" disabled title="已过截止且不允许补交">
              已截止
            </button>
          </div>
          <p class="content">{{ item.homework.content || '（无说明）' }}</p>
          <p v-if="item.homework.attachments?.length" class="meta">
            题目附件：
            <a
              v-for="a in item.homework.attachments"
              :key="a.id"
              :href="`/api/v1/homework-attachments/${a.id}`"
              target="_blank"
              rel="noopener"
            >{{ a.name }}</a>
          </p>

          <!-- 已交内容始终可见（不随补交表单折叠） -->
          <div v-if="item.submitted && item.submission" class="my-work">
            <header>
              <strong>我的提交</strong>
              <span>
                {{ item.submission.submittedAt || '' }}
                <template v-if="item.late || item.submission.status === 'late' || item.submission.late"> · 补交</template>
              </span>
            </header>
            <p class="content">
              {{
                item.submission.textContent?.trim()
                  || (item.submission.attachments?.length ? '（无文字，见下方附件）' : '（无文字答案）')
              }}
            </p>
            <ul v-if="item.submission.attachments?.length" class="att-list">
              <li v-for="a in item.submission.attachments" :key="a.id">
                <a
                  :href="`/api/v1/homework-attachments/${a.id}`"
                  target="_blank"
                  rel="noopener"
                >{{ a.name }}</a>
              </li>
            </ul>
            <p v-if="item.submission.feedback" class="meta">老师评语：{{ item.submission.feedback }}</p>
            <p v-if="item.submission.score != null" class="meta">得分：{{ item.submission.score }}</p>
          </div>

          <div v-if="activeHwId === item.homework.id" class="submit">
            <p class="meta">
              {{
                item.submitted
                  ? '补交：可改文字；不选新文件则保留原附件，选择新文件将替换原附件'
                  : '填写文字并/或上传附件后提交'
              }}
            </p>
            <el-input
              v-if="item.homework.allowText !== false"
              v-model="textContent"
              type="textarea"
              :rows="4"
              placeholder="填写文字答案…"
            />
            <div v-if="item.homework.allowFile !== false || item.homework.allowImage !== false" class="file-row">
              <input type="file" multiple @change="onFilesChange" />
              <span class="meta">已选 {{ fileList.length }} 个</span>
            </div>
            <div class="ops end">
              <button type="button" class="btn ghost" @click="activeHwId = ''">取消</button>
              <button type="button" class="btn primary" :disabled="submitting" @click="submitHomework">
                {{ submitting ? '提交中…' : (item.submitted ? '确认补交' : '提交') }}
              </button>
            </div>
          </div>
        </article>
      </section>

      <!-- 资料 -->
      <section v-else-if="tab === 'materials'" class="block">
        <div v-if="!materials.length" class="void">
          <strong>暂无资料</strong>
          <span>老师上传后可在此下载。</span>
        </div>
        <ul v-else class="file-grid">
          <li v-for="m in materials" :key="m.id">
            <a
              :href="m.attachment ? `/api/v1/homework-attachments/${m.attachment.id}` : '#'"
              target="_blank"
              rel="noopener"
            >
              <strong>{{ m.title }}</strong>
              <span>{{ m.description || m.attachment?.name || '下载' }}</span>
            </a>
          </li>
        </ul>
      </section>

      <!-- 成员 -->
      <section v-else-if="tab === 'members'" class="block">
        <div v-if="!members.length" class="void">暂无成员信息</div>
        <ul v-else class="people">
          <li v-for="m in members" :key="m.username">
            <div class="avatar">{{ (m.displayName || m.username || '?').slice(0, 1) }}</div>
            <div>
              <strong>{{ m.displayName || m.username }}</strong>
              <span>{{ m.status || '学生' }} · 提交 {{ m.submissionCount || 0 }} 次</span>
            </div>
          </li>
        </ul>
      </section>

      <!-- 聊天 -->
      <section v-else-if="tab === 'chat'" class="block chat">
        <div class="chat-box">
          <div v-if="!chat.length" class="void slim">还没有消息，打个招呼吧。</div>
          <div v-for="m in chat" :key="m.id" class="bubble">
            <div class="who">{{ m.username }} · {{ m.createdAt }}</div>
            <div class="txt">{{ m.content }}</div>
          </div>
        </div>
        <div class="chat-input">
          <el-input v-model="chatText" placeholder="输入消息，Enter 发送" @keyup.enter="sendChat" />
          <button type="button" class="btn primary" :disabled="chatSending" @click="sendChat">发送</button>
        </div>
      </section>

      <!-- 公告签到 -->
      <section v-else class="block notice">
        <div class="notice-col">
          <h3 class="sec">班内公告</h3>
          <div v-if="!announcements.length" class="void slim">暂无公告</div>
          <article v-for="a in announcements" :key="a.id" class="feat">
            <header>
              <strong>{{ a.title }}</strong>
              <span>{{ a.createdAt }}</span>
            </header>
            <p class="meta">{{ a.authorUsername }}</p>
            <p>{{ a.content }}</p>
          </article>
        </div>
        <div class="notice-col">
          <h3 class="sec">课堂签到 <small v-if="openCk">进行中 {{ openCk }}</small></h3>
          <div v-if="!checkins.length" class="void slim">暂无签到</div>
          <div v-for="ck in checkins" :key="ck.id" class="ck">
            <div>
              <strong>{{ ck.title }}</strong>
              <span>{{ ck.status === 'open' ? '进行中' : '已结束' }} · {{ ck.createdAt }}</span>
            </div>
            <button
              v-if="ck.status === 'open'"
              type="button"
              class="btn primary"
              @click="sign(ck)"
            >
              签到
            </button>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped lang="scss">
.space {
  --ink: #122033;
  --muted: #5a6b80;
  --line: rgba(18, 32, 51, 0.1);
  --paper: rgba(248, 251, 253, 0.88);
  --teal: #0f766e;
  --teal-deep: #0e5f59;
  --warn: #b45309;
  --ok: #047857;
  --display: 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  min-height: 100vh;
  position: relative;
  color: var(--ink);
  font-family: 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
}

.atmosphere {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    radial-gradient(ellipse 70% 50% at 8% -10%, rgba(15, 118, 110, 0.16), transparent 55%),
    radial-gradient(ellipse 55% 45% at 96% 8%, rgba(14, 116, 144, 0.1), transparent 50%),
    linear-gradient(165deg, #f3f7f8 0%, #e7eef3 45%, #dce8e7 100%);
}

.atmosphere::after {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0.35;
  background-image:
    linear-gradient(rgba(20, 32, 46, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(20, 32, 46, 0.03) 1px, transparent 1px);
  background-size: 28px 28px;
  mask-image: radial-gradient(ellipse 80% 70% at 50% 20%, #000 20%, transparent 75%);
}

.hero,
.stage {
  position: relative;
  z-index: 1;
  max-width: 1080px;
  margin: 0 auto;
  padding-left: 24px;
  padding-right: 24px;
}

.hero {
  padding-top: 22px;
  padding-bottom: 0;
  animation: rise 0.55s ease both;
}

.hero-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.back {
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.7);
  color: var(--ink);
  font: inherit;
  font-weight: 700;
  font-size: 13px;
  border-radius: 10px;
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease;
}

.back:hover {
  background: #fff;
  transform: translateX(-2px);
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 600;
}

.hero-main {
  display: grid;
  grid-template-columns: 1.4fr 0.8fr;
  gap: 28px;
  align-items: end;
  margin-top: 22px;
  padding-bottom: 8px;
}

.kicker {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--teal);
}

.hero-copy h1 {
  margin: 0;
  font-family: var(--display);
  font-size: clamp(38px, 5.5vw, 52px);
  font-weight: 800;
  line-height: 1.08;
  letter-spacing: -0.03em;
  color: var(--ink);
}

.subline {
  margin: 14px 0 0;
  max-width: 36em;
  color: var(--muted);
  font-size: 15px;
  line-height: 1.7;
}

.subline em {
  display: inline-block;
  margin-right: 10px;
  padding: 2px 10px;
  border-radius: 6px;
  background: rgba(15, 118, 110, 0.12);
  color: var(--teal-deep);
  font-style: normal;
  font-weight: 800;
  font-size: 13px;
}

.pulse {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.pulse > div {
  padding: 14px 16px;
  border-radius: 14px;
  background: var(--paper);
  border: 1px solid var(--line);
  backdrop-filter: blur(8px);
}

.pulse dt {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted);
  letter-spacing: 0.06em;
}

.pulse dd {
  margin: 4px 0 0;
  font-family: var(--display);
  font-size: 28px;
  font-weight: 800;
  line-height: 1;
  color: var(--ink);
}

.pulse .accent {
  background: linear-gradient(145deg, rgba(15, 118, 110, 0.12), rgba(255, 252, 247, 0.9));
  border-color: rgba(15, 118, 110, 0.22);
}

.pulse .accent dd {
  color: var(--teal-deep);
}

.rail {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 18px;
  margin-top: 26px;
  border-bottom: 1px solid var(--line);
}

.rail button {
  position: relative;
  border: 0;
  background: transparent;
  padding: 12px 2px 14px;
  font: inherit;
  font-size: 14px;
  font-weight: 700;
  color: var(--muted);
  cursor: pointer;
  transition: color 0.2s ease;
}

.rail button:hover {
  color: var(--ink);
}

.rail button.on {
  color: var(--teal-deep);
}

.rail button.on::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 2px;
  background: var(--teal);
  border-radius: 2px 2px 0 0;
  animation: draw 0.35s ease both;
}

.rail i {
  position: absolute;
  top: 4px;
  right: -10px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: #c2410c;
  color: #fff;
  font-size: 10px;
  font-style: normal;
  display: grid;
  place-items: center;
}

.stage {
  padding-top: 22px;
  padding-bottom: 56px;
  animation: rise 0.65s ease 0.06s both;
}

.stage-head {
  margin-bottom: 16px;
}

.stage-head h2 {
  margin: 0;
  font-family: var(--display);
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.stage-head p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.6;
}

.block {
  padding: 22px;
  border-radius: 20px;
  background: var(--paper);
  border: 1px solid var(--line);
  backdrop-filter: blur(10px);
  display: grid;
  gap: 18px;
}

.void {
  display: grid;
  gap: 6px;
  place-items: start;
  padding: 28px 8px;
  color: var(--muted);
}

.void strong {
  color: var(--ink);
  font-size: 16px;
}

.void.slim {
  padding: 12px 0;
  font-size: 13px;
}

.lesson-rows {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 10px;
}

.lesson-rows li {
  display: grid;
  grid-template-columns: 48px 1fr auto;
  gap: 14px;
  align-items: center;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.72);
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.lesson-rows li:hover {
  transform: translateY(-2px);
  border-color: rgba(15, 118, 110, 0.28);
}

.idx {
  font-family: var(--display);
  font-size: 20px;
  font-weight: 800;
  color: rgba(15, 118, 110, 0.55);
  letter-spacing: -0.02em;
}

.body h3 {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 800;
}

.progress {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  align-items: center;
}

.track {
  height: 6px;
  border-radius: 999px;
  background: rgba(20, 32, 46, 0.08);
  overflow: hidden;
}

.track i {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #14b8a6, var(--teal-deep));
  transition: width 0.4s ease;
}

.progress span {
  font-size: 12px;
  font-weight: 800;
  color: var(--muted);
}

.ops {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ops.end {
  justify-content: flex-end;
}

.btn {
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  font: inherit;
  font-size: 13px;
  font-weight: 750;
  border-radius: 10px;
  padding: 9px 14px;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease, border-color 0.2s ease;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn.primary {
  background: var(--teal-deep);
  border-color: var(--teal-deep);
  color: #fff;
}

.btn.primary:hover:not(:disabled) {
  background: #0f766e;
}

.btn.ghost:hover {
  border-color: rgba(15, 118, 110, 0.35);
  color: var(--teal-deep);
}

.split {
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 22px;
  padding-top: 8px;
  border-top: 1px solid var(--line);
}

.sec {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: var(--ink);
}

.sec small {
  margin-left: 8px;
  color: var(--teal);
  font-weight: 700;
}

.jump {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.jump button {
  text-align: left;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.75);
  border-radius: 12px;
  padding: 14px;
  cursor: pointer;
  font: inherit;
  transition: border-color 0.2s ease, transform 0.2s ease;
}

.jump button:hover {
  border-color: rgba(15, 118, 110, 0.3);
  transform: translateY(-1px);
}

.jump b {
  display: block;
  font-family: var(--display);
  font-size: 24px;
  font-weight: 800;
  color: var(--teal-deep);
  margin-bottom: 4px;
}

.jump span {
  font-size: 12px;
  color: var(--muted);
  font-weight: 600;
}

.feat {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.7);
  display: grid;
  gap: 6px;
  margin-bottom: 10px;
}

.feat header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: baseline;
}

.feat header span {
  color: var(--teal-deep);
  font-weight: 800;
  font-size: 13px;
}

.feat p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.hw {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.72);
  display: grid;
  gap: 10px;
}

.hw-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.hw h3 {
  margin: 0;
  font-size: 16px;
}

.meta {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 12px;
}

.meta .ok {
  color: var(--ok);
}

.meta .warn {
  color: var(--warn);
}

.meta a {
  margin-right: 8px;
  color: var(--teal-deep);
}

.content {
  margin: 0;
  white-space: pre-wrap;
  color: #334155;
  line-height: 1.7;
  font-size: 14px;
}

.my-work {
  margin-top: 4px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(34, 197, 94, 0.06);
  border: 1px solid rgba(34, 197, 94, 0.22);
  display: grid;
  gap: 8px;
}

.my-work header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: baseline;
  font-size: 13px;
  color: var(--muted);
}

.my-work header strong {
  color: var(--ok, #16a34a);
  font-size: 14px;
}

.att-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 6px;
}

.att-list a {
  color: var(--teal-deep, #0f766e);
  text-decoration: underline;
  word-break: break-all;
  font-size: 13px;
}

.submit {
  padding-top: 12px;
  border-top: 1px dashed rgba(20, 32, 46, 0.14);
  display: grid;
  gap: 10px;
}

.file-row {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.file-grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.file-grid a {
  display: grid;
  gap: 6px;
  padding: 16px;
  border-radius: 14px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.75);
  text-decoration: none;
  color: inherit;
  min-height: 96px;
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.file-grid a:hover {
  transform: translateY(-2px);
  border-color: rgba(15, 118, 110, 0.3);
}

.file-grid strong {
  font-size: 15px;
}

.file-grid span {
  font-size: 12px;
  color: var(--muted);
}

.people {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.people li {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.75);
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: linear-gradient(145deg, #99f6e4, #0f766e);
  color: #fff;
  font-weight: 800;
}

.people strong {
  display: block;
  font-size: 14px;
}

.people span {
  font-size: 12px;
  color: var(--muted);
}

.chat-box {
  min-height: 280px;
  max-height: 440px;
  overflow: auto;
  padding: 14px;
  border-radius: 14px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.55);
  display: grid;
  gap: 12px;
}

.bubble .who {
  font-size: 11px;
  color: var(--muted);
  margin-bottom: 4px;
  font-weight: 700;
}

.bubble .txt {
  display: inline-block;
  max-width: 85%;
  padding: 10px 12px;
  border-radius: 12px 12px 12px 4px;
  background: #fff;
  border: 1px solid var(--line);
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 1.55;
}

.chat-input {
  display: flex;
  gap: 10px;
  align-items: center;
}

.chat-input .el-input {
  flex: 1;
}

.notice {
  grid-template-columns: 1fr 1fr;
  display: grid;
  gap: 22px;
}

.notice-col {
  display: grid;
  gap: 10px;
  align-content: start;
}

.ck {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.72);
}

.ck strong {
  display: block;
  font-size: 14px;
}

.ck span {
  font-size: 12px;
  color: var(--muted);
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

@keyframes draw {
  from {
    transform: scaleX(0.3);
    opacity: 0;
  }
  to {
    transform: scaleX(1);
    opacity: 1;
  }
}

@media (max-width: 900px) {
  .hero-main,
  .split,
  .notice {
    grid-template-columns: 1fr;
  }

  .lesson-rows li {
    grid-template-columns: 40px 1fr;
  }

  .lesson-rows .ops {
    grid-column: 1 / -1;
  }

  .hero-copy h1 {
    font-size: 36px;
  }
}
</style>
