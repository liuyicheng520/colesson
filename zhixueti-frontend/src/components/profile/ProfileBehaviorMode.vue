<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { profileApi } from '@/api/profile'

const emit = defineEmits<{ generated: [] }>()

const generating = ref(false)
const progress = ref(0)
const features = ref<Record<string, unknown> | null>(null)
const done = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

async function requestGenerate() {
  try {
    await ElMessageBox.confirm(
      '将读取您的学习行为数据（学习时长、资源交互、答题记录、路径进度等），仅在本地计算画像，不上传额外隐私数据。是否授权？',
      '行为画像授权确认',
      { confirmButtonText: '授权并生成', cancelButtonText: '取消', type: 'info' },
    )
  } catch {
    return
  }

  generating.value = true
  progress.value = 0
  timer = setInterval(() => {
    if (progress.value < 90) progress.value += Math.random() * 15
  }, 400)

  try {
    const res = await profileApi.generateBehaviorProfile()
    progress.value = 100
    features.value = res.features_used
    done.value = true
    ElMessage.success('行为画像生成完成！')
    emit('generated')
  } catch {
    ElMessage.error('生成失败，请确认已有学习数据')
  } finally {
    if (timer) clearInterval(timer)
    generating.value = false
  }
}
</script>

<template>
  <div class="behavior-mode">
    <div v-if="!done" class="behavior-card">
      <h3>基于学习记录自动生成</h3>
      <p>系统将分析您在平台上的学习行为，无感化推断 6 维画像，避免自评偏差。</p>
      <ul>
        <li>学习行为：登录频次、学习时长、时段分布</li>
        <li>内容交互：资源完播率、停留时长、收藏偏好</li>
        <li>答题数据：正确率、错题分布</li>
        <li>交互行为：答疑频次、功能使用偏好</li>
      </ul>

      <div v-if="generating" class="progress-area">
        <el-progress :percentage="Math.round(progress)" :stroke-width="10" striped striped-flow />
        <p>正在分析学习行为特征…</p>
      </div>
      <el-button v-else type="primary" size="large" @click="requestGenerate">授权并一键生成</el-button>
    </div>

    <div v-else class="result-card">
      <el-result icon="success" title="行为画像已生成">
        <template #sub-title>真实反映您的学习习惯，可在右侧卡片手动修正标签</template>
      </el-result>
      <div v-if="features" class="features">
        <div v-for="(val, key) in features" :key="key" class="feat-item">
          <span class="key">{{ key }}</span>
          <span class="val">{{ val }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.behavior-mode { height: 100%; }
.behavior-card, .result-card {
  padding: 28px;
  background: #fff;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  h3 { margin: 0 0 12px; }
  p { color: $text-secondary; line-height: 1.6; margin-bottom: 12px; }
  ul { margin: 0 0 24px; padding-left: 20px; font-size: 14px; color: #475569; li { margin: 6px 0; } }
}
.progress-area { text-align: center; p { margin-top: 12px; font-size: 13px; color: $text-secondary; } }
.features {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-top: 16px;
  font-size: 12px;
}
.feat-item {
  padding: 8px 12px;
  background: #f8fafc;
  border-radius: 8px;
  .key { color: $text-secondary; margin-right: 8px; }
  .val { font-weight: 600; color: #334155; }
}
</style>
