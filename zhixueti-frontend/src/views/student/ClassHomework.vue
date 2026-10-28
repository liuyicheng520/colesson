<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  classroomApi,
  type Announcement,
  type CheckinSession,
  type ClassLesson,
  type ClassRoom,
  type HomeworkView,
  type Submission,
} from '@/api/classroom'

const loading = ref(false)
const joining = ref(false)
const requestingCode = ref(false)
const inviteCode = ref('')
const joinEmail = ref('')
const emailCode = ref('')
const demoHint = ref('')
const classes = ref<ClassRoom[]>([])
const homeworks = ref<HomeworkView[]>([])
const lessons = ref<ClassLesson[]>([])
const activeClassId = ref('')
const announcements = ref<Announcement[]>([])
const checkins = ref<CheckinSession[]>([])
const featured = ref<Submission[]>([])
const activeHwId = ref('')
const textContent = ref('')
const fileList = ref<File[]>([])
const submitting = ref(false)

async function refresh() {
  loading.value = true
  try {
    const [c, h, l] = await Promise.all([
      classroomApi.listMyClasses(),
      classroomApi.listMyHomeworks(),
      classroomApi.listClassLessons(),
    ])
    classes.value = c.items || []
    homeworks.value = h.items || []
    lessons.value = l.items || []
    if (!activeClassId.value && classes.value.length) {
      activeClassId.value = classes.value[0].id
    }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadClassExtras() {
  if (!activeClassId.value) {
    announcements.value = []
    checkins.value = []
    featured.value = []
    return
  }
  try {
    const [a, ck, f] = await Promise.all([
      classroomApi.listAnnouncements(activeClassId.value),
      classroomApi.listCheckins(activeClassId.value),
      classroomApi.listFeatured(activeClassId.value),
    ])
    announcements.value = a.items || []
    checkins.value = ck.items || []
    featured.value = f.items || []
  } catch {
    announcements.value = []
    checkins.value = []
    featured.value = []
  }
}

watch(activeClassId, () => {
  void loadClassExtras()
})

async function requestEmailCode() {
  const code = inviteCode.value.trim()
  const email = joinEmail.value.trim()
  if (!code) {
    ElMessage.warning('请输入班级邀请码')
    return
  }
  if (!email) {
    ElMessage.warning('请输入邮箱')
    return
  }
  requestingCode.value = true
  demoHint.value = ''
  try {
    const data = await classroomApi.requestJoinCode(code, email)
    if (data.demoCode) {
      demoHint.value = `演示验证码：${data.demoCode}（正式环境将发送到邮箱）`
      emailCode.value = data.demoCode
    } else {
      demoHint.value = data.hint || '验证码已发送，请查收邮箱'
    }
    ElMessage.success('验证码已生成')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '获取验证码失败')
  } finally {
    requestingCode.value = false
  }
}

async function joinClass() {
  const code = inviteCode.value.trim()
  const email = joinEmail.value.trim()
  const otp = emailCode.value.trim()
  if (!code) {
    ElMessage.warning('请输入邀请码')
    return
  }
  if (!email) {
    ElMessage.warning('请输入邮箱')
    return
  }
  if (!otp) {
    ElMessage.warning('请输入邮箱验证码')
    return
  }
  joining.value = true
  try {
    const data = await classroomApi.join(code, email, otp)
    ElMessage.success('已加入班级')
    inviteCode.value = ''
    joinEmail.value = ''
    emailCode.value = ''
    demoHint.value = ''
    await refresh()
    if (data.class?.id) activeClassId.value = data.class.id
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加入失败')
  } finally {
    joining.value = false
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
    await refresh()
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
    await loadClassExtras()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '签到失败')
  }
}

onMounted(() => {
  void refresh().then(() => loadClassExtras())
})
</script>

<template>
  <div class="page" v-loading="loading">
    <header class="head">
      <div>
        <h1>我的班级 · 作业</h1>
        <p>加入班级后可交作业、看公告、签到，并学习本班专属智课。</p>
      </div>
    </header>

    <section class="card join">
      <h2>加入班级（邀请码 + 邮箱验证）</h2>
      <p class="meta join-tip">老师发布班级后，请填写邀请码与邮箱，获取验证码后再进入本班学生端。</p>
      <div class="join-grid">
        <el-input v-model="inviteCode" maxlength="12" placeholder="班级邀请码（6 位）" clearable />
        <el-input v-model="joinEmail" type="email" placeholder="接收验证码的邮箱" clearable />
        <div class="join-row">
          <el-input v-model="emailCode" maxlength="8" placeholder="邮箱验证码" clearable />
          <el-button :loading="requestingCode" @click="requestEmailCode">获取验证码</el-button>
          <el-button type="primary" :loading="joining" @click="joinClass">验证并加入</el-button>
        </div>
      </div>
      <p v-if="demoHint" class="meta demo-hint">{{ demoHint }}</p>
    </section>

    <section class="card">
      <h2>已加入班级</h2>
      <div v-if="!classes.length" class="empty">还没有班级。向任课老师索取邀请码。</div>
      <div v-else class="class-grid">
        <button
          v-for="c in classes"
          :key="c.id"
          type="button"
          class="class-item"
          :class="{ active: activeClassId === c.id }"
          @click="activeClassId = c.id"
        >
          <strong>{{ c.name }}</strong>
          <span>{{ c.subject || '未填学科' }}</span>
        </button>
      </div>
    </section>

    <section v-if="activeClassId" class="card">
      <h2>班内公告</h2>
      <div v-if="!announcements.length" class="empty">暂无公告。</div>
      <article v-for="a in announcements" :key="a.id" class="hw-item">
        <h3>{{ a.title }}</h3>
        <p class="meta">{{ a.authorUsername }} · {{ a.createdAt }}</p>
        <p class="content">{{ a.content }}</p>
      </article>
    </section>

    <section v-if="activeClassId" class="card">
      <h2>签到</h2>
      <div v-if="!checkins.length" class="empty">暂无签到。</div>
      <div v-for="ck in checkins" :key="ck.id" class="hw-item row">
        <div>
          <h3>{{ ck.title }}</h3>
          <p class="meta">{{ ck.status === 'open' ? '进行中' : '已结束' }} · {{ ck.createdAt }}</p>
        </div>
        <el-button v-if="ck.status === 'open'" type="primary" @click="sign(ck)">我要签到</el-button>
      </div>
    </section>

    <section class="card">
      <h2>本班智课</h2>
      <div v-if="!lessons.length" class="empty">老师按班发布后会出现在这里（仅本班可见）。</div>
      <div v-else class="class-grid">
        <a
          v-for="l in lessons"
          :key="l.id"
          class="class-item link"
          :href="l.digitalUrl || '#'"
          target="_blank"
          rel="noopener"
        >
          <strong>{{ l.lessonTitle || l.name || l.id }}</strong>
          <span>仅本班可见</span>
        </a>
      </div>
    </section>

    <section v-if="activeClassId" class="card">
      <h2>优秀作业展示</h2>
      <div v-if="!featured.length" class="empty">暂无优秀作业。</div>
      <article v-for="s in featured" :key="s.id" class="hw-item">
        <h3>{{ s.studentUsername || '同学' }} · {{ s.score != null ? `得分 ${s.score}` : '优秀作业' }}</h3>
        <p class="content">{{ s.textContent || '（见附件）' }}</p>
        <p class="meta">
          <a
            v-for="a in s.attachments || []"
            :key="a.id"
            :href="`/api/v1/homework-attachments/${a.id}`"
            target="_blank"
            rel="noopener"
          >{{ a.name }}</a>
        </p>
      </article>
    </section>

    <section class="card">
      <h2>作业列表</h2>
      <div v-if="!homeworks.length" class="empty">暂无作业。</div>
      <div v-else class="hw-list">
        <article v-for="item in homeworks" :key="item.homework.id" class="hw-item">
          <div class="hw-top">
            <div>
              <h3>{{ item.homework.title }}</h3>
              <p class="meta">
                {{ item.className }} · {{ item.homework.dueAt || '未设截止' }} ·
                {{
                  item.submitted
                    ? (item.late || item.submission?.status === 'late' ? '已补交' : '已提交')
                    : item.overdue
                      ? '已截止 · 未交'
                      : '未提交'
                }}
                <template v-if="item.submission?.score != null"> · 得分 {{ item.submission.score }}</template>
              </p>
            </div>
            <el-button
              v-if="canEditHomework(item)"
              type="primary"
              plain
              @click="openSubmit(item)"
            >
              {{ item.submitted ? (item.overdue ? '补交' : '重新提交') : '交作业' }}
            </el-button>
            <el-button v-else-if="item.submitted" disabled>已提交</el-button>
            <el-button v-else disabled>已截止</el-button>
          </div>
          <p class="content">{{ item.homework.content || '（无说明）' }}</p>

          <div v-if="item.submitted && item.submission" class="my-work">
            <p class="meta">
              <strong>我的提交</strong>
              · {{ item.submission.submittedAt || '' }}
              <template v-if="item.submission.late || item.submission.status === 'late'"> · 补交</template>
            </p>
            <p class="content">
              {{
                item.submission.textContent?.trim()
                  || (item.submission.attachments?.length ? '（无文字，见下方附件）' : '（无文字答案）')
              }}
            </p>
            <p v-if="item.submission.attachments?.length" class="meta att-links">
              <a
                v-for="a in item.submission.attachments"
                :key="a.id"
                :href="`/api/v1/homework-attachments/${a.id}`"
                target="_blank"
                rel="noopener"
              >{{ a.name }}</a>
            </p>
            <p v-if="item.submission.feedback" class="meta">老师评语：{{ item.submission.feedback }}</p>
          </div>

          <div v-if="activeHwId === item.homework.id" class="submit-box">
            <p class="meta">
              {{
                item.submitted
                  ? '补交：不选新文件则保留原附件；选择新文件将替换原附件'
                  : '填写文字并/或上传附件'
              }}
            </p>
            <el-input
              v-if="item.homework.allowText !== false"
              v-model="textContent"
              type="textarea"
              :rows="5"
              placeholder="在此填写文字答案…"
            />
            <div v-if="item.homework.allowFile !== false || item.homework.allowImage !== false" class="file-row">
              <input type="file" multiple @change="onFilesChange" />
              <span class="meta">已选 {{ fileList.length }} 个附件</span>
            </div>
            <div class="actions">
              <el-button @click="activeHwId = ''">取消</el-button>
              <el-button type="primary" :loading="submitting" @click="submitHomework">
                {{ item.submitted ? '确认补交' : '提交作业' }}
              </el-button>
            </div>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
.page { max-width: 960px; margin: 0 auto; padding: 28px 20px 48px; display: grid; gap: 18px; }
.head h1 { margin: 0; font-size: 28px; font-weight: 800; color: #1f2a44; }
.head p { margin: 8px 0 0; color: #6b7c99; line-height: 1.6; }
.card { background: #fff; border: 1px solid #e8eef8; border-radius: 16px; padding: 18px; box-shadow: 0 8px 24px rgba(31, 64, 120, 0.04); }
.card h2 { margin: 0 0 12px; font-size: 17px; font-weight: 800; color: #243556; }
.join-tip { margin: -4px 0 12px; }
.join-grid { display: grid; gap: 10px; }
.join-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.demo-hint { margin-top: 10px; color: #b45309; }
.class-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
.class-item {
  border: 1px solid #e5edf8; border-radius: 12px; padding: 12px; display: grid; gap: 4px;
  background: #f8fbff; text-align: left; cursor: pointer; font: inherit; color: inherit;
}
.class-item.active { border-color: #3b82f6; background: #eff6ff; }
.class-item.link { text-decoration: none; }
.class-item strong { color: #1f2a44; }
.class-item span, .meta, .empty { color: #6b7c99; font-size: 13px; }
.hw-list { display: grid; gap: 12px; }
.hw-item { border: 1px solid #e8eef8; border-radius: 14px; padding: 14px; display: grid; gap: 8px; margin-bottom: 10px; }
.hw-item.row { grid-template-columns: 1fr auto; align-items: center; }
.hw-top { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.hw-item h3 { margin: 0; font-size: 16px; color: #1f2a44; }
.content { margin: 0; white-space: pre-wrap; color: #3a4a66; line-height: 1.7; }
.my-work {
  margin-top: 4px; padding: 12px; border-radius: 12px;
  background: #f0fdf4; border: 1px solid #bbf7d0; display: grid; gap: 6px;
}
.submit-box { margin-top: 8px; padding-top: 12px; border-top: 1px dashed #d7e3f5; display: grid; gap: 10px; }
.file-row, .actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.actions { justify-content: flex-end; }
.meta a { margin-right: 8px; color: #2563eb; }
</style>
