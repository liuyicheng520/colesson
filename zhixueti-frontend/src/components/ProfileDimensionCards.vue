<script setup lang="ts">
import { computed, ref } from 'vue'
import type { DimensionProgressItem } from '@/types'
import { formatContributionTags } from '@/profile/fusion'
import {
  buildDimensionAnalysis,
  buildStatusTag,
  progressBarColor,
  type DimensionAnalysis,
} from '@/utils/dimensionAnalysis'

const props = defineProps<{
  items: DimensionProgressItem[]
}>()

const emit = defineEmits<{
  edit: [item: DimensionProgressItem]
  'continue-dialogue': [payload: { item: DimensionProgressItem; prompt: string }]
}>()

const completedItems = computed(() => props.items.filter((i) => i.status === 'completed'))

const detailVisible = ref(false)
const detailLoading = ref(false)
const detailItem = ref<DimensionProgressItem | null>(null)
const analysis = ref<DimensionAnalysis | null>(null)
const analysisCache = new Map<string, DimensionAnalysis>()

function isIncomplete(item: DimensionProgressItem) {
  return Number(item.display_score ?? 0) < 0.3
}

function fusionText(item: DimensionProgressItem) {
  const tags = formatContributionTags(item)
  if (!tags) return ''
  const conf = Math.round(Number(item.fusion_confidence ?? item.confidence ?? 0) * 100)
  return `融合来源：${tags} · 置信 ${conf}%`
}

async function openDetail(item: DimensionProgressItem) {
  if (item.status === 'pending' && !item.dimension_value) {
    return
  }
  detailItem.value = item
  detailVisible.value = true
  analysis.value = null
  detailLoading.value = true
  const cacheKey = `v2-${item.dimension_code}-${item.updated_at || ''}-${JSON.stringify(item.dimension_value || {})}`
  try {
    // 基于现有画像接口数据生成学情分析（模拟 AI 加载，便于答辩演示）
    await new Promise((r) => setTimeout(r, 280))
    if (analysisCache.has(cacheKey)) {
      analysis.value = analysisCache.get(cacheKey)!
    } else {
      const built = buildDimensionAnalysis(item)
      analysisCache.set(cacheKey, built)
      analysis.value = built
    }
  } finally {
    detailLoading.value = false
  }
}

function onCardClick(item: DimensionProgressItem, e: MouseEvent) {
  const target = e.target as HTMLElement
  if (target.closest('.card-actions')) return
  openDetail(item)
}

function onViewDetail(item: DimensionProgressItem, e: MouseEvent) {
  e.stopPropagation()
  openDetail(item)
}

function onEdit(item: DimensionProgressItem, e: MouseEvent) {
  e.stopPropagation()
  emit('edit', item)
}

function goAdjustFromDialog() {
  if (!detailItem.value || !analysis.value) return
  const item = detailItem.value
  const prompt = analysis.value.continuePrompt
  detailVisible.value = false
  emit('continue-dialogue', { item, prompt })
}

function continueInDialogue() {
  goAdjustFromDialog()
}
</script>

<template>
  <div class="dimension-cards">
    <h4 v-if="items.length">画像维度卡片</h4>
    <div v-if="!completedItems.length && !items.length" class="empty-hint">
      完成问卷或对话后，将在此展示融合后的 6 维画像
    </div>
    <div v-else class="card-grid">
      <div
        v-for="item in items"
        :key="item.dimension_code"
        class="dim-card"
        :class="[item.status, { clickable: item.status !== 'pending' || !!item.dimension_value }]"
        @click="onCardClick(item, $event)"
      >
        <div class="card-head">
          <span class="code">{{ item.dimension_code }}</span>
          <span class="name">{{ item.dimension_name }}</span>
          <div class="card-actions">
            <button
              v-if="item.status === 'completed' || item.dimension_value"
              type="button"
              class="link-detail"
              @click="onViewDetail(item, $event)"
            >
              查看详情
            </button>
            <el-button
              v-if="item.status === 'completed'"
              link
              type="primary"
              size="small"
              @click="onEdit(item, $event)"
            >
              调整
            </el-button>
          </div>
        </div>

        <!-- 已删除 description 底层释义文案 -->

        <div v-if="item.status !== 'pending'" class="score-bar">
          <el-progress
            :percentage="Math.round(item.display_score * 100)"
            :stroke-width="8"
            :color="progressBarColor(item.dimension_code)"
            :show-text="false"
          />
          <span class="score-text">{{ Math.round(item.display_score * 100) }}%</span>
        </div>

        <p v-if="item.dimension_value || item.status === 'completed'" class="card-value">
          {{ buildStatusTag(item) }}
        </p>
        <p v-else-if="item.status === 'active'" class="card-value muted">对话采集中…</p>
        <p v-else class="card-value muted">待采集</p>

        <p v-if="isIncomplete(item) && item.status !== 'pending'" class="incomplete-tip">
          维度信息不完善，建议查看 AI 分析补充细节
        </p>

        <p v-if="fusionText(item)" class="fusion-tags">{{ fusionText(item) }}</p>
      </div>
    </div>

    <el-dialog
      v-model="detailVisible"
      :title="detailItem ? `${detailItem.dimension_code} ${detailItem.dimension_name} - AI学情深度分析` : 'AI学情深度分析'"
      width="760px"
      class="dim-analysis-dialog"
      destroy-on-close
      align-center
      :modal="true"
      @closed="analysis = null"
    >
      <el-skeleton v-if="detailLoading" animated :rows="6" />
      <template v-else-if="analysis && detailItem">
        <div class="portrait-banner">
          <p class="portrait-lead">{{ analysis.portrait }}</p>
          <p v-if="analysis.portraitDetail" class="portrait-detail">{{ analysis.portraitDetail }}</p>
        </div>

        <div class="section">
          <h5>关于你的几句画像</h5>
          <ul>
            <li v-for="(f, i) in analysis.facts" :key="'f' + i">{{ f }}</li>
          </ul>
          <p class="for-you">{{ analysis.forYou }}</p>
        </div>

        <div class="trust-grid">
          <div class="trust-cell">
            <div class="trust-label">数据来源</div>
            <div class="trust-body">{{ analysis.fusionWeights }}</div>
          </div>
          <div class="trust-cell">
            <div class="trust-label">判断把握</div>
            <div class="trust-body">{{ analysis.confidenceText }}</div>
          </div>
        </div>

        <div class="section suggest">
          <h5>若想让评价更贴你</h5>
          <p>{{ analysis.suggestion }}</p>
          <el-button type="primary" size="small" @click="continueInDialogue">
            继续对话完善维度
          </el-button>
        </div>
      </template>

      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="primary" :disabled="!analysis" @click="goAdjustFromDialog">
          前往调整该维度
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.dimension-cards {
  h4 { margin-bottom: 12px; font-size: 15px; }
}

.empty-hint {
  text-align: center;
  color: $text-secondary;
  font-size: 13px;
  padding: 24px 0;
}

.card-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.dim-card {
  padding: 14px 14px 12px;
  border-radius: 12px;
  border: 1px solid #d9f0e3;
  background: #F0FBF4;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.04);
  transition: box-shadow 0.2s ease, transform 0.2s ease;
  min-height: 118px;

  &.clickable { cursor: pointer; }
  &:hover {
    box-shadow: 0 6px 16px rgba(64, 158, 255, 0.14);
    transform: translateY(-2px);
  }

  &.active {
    border-color: #bfdbfe;
    background: #eff6ff;
  }
  &.pending {
    background: #F5F7FA;
    border-color: #e4e7ed;
  }

  .card-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
    .code {
      font-size: 11px;
      font-weight: 700;
      color: #409EFF;
      background: rgba(64, 158, 255, 0.12);
      padding: 2px 8px;
      border-radius: 6px;
      flex-shrink: 0;
    }
    .name {
      font-weight: 700;
      font-size: 14px;
      flex: 1;
      color: #303133;
    }
  }

  .card-actions {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }

  .link-detail {
    border: none;
    background: none;
    color: #409EFF;
    font-size: 12px;
    cursor: pointer;
    padding: 0 4px;
    line-height: 1.4;
    &:hover { text-decoration: underline; }
  }

  .score-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
    :deep(.el-progress-bar__outer) { border-radius: 999px; }
    :deep(.el-progress-bar__inner) { border-radius: 999px; }
    .el-progress { flex: 1; }
    .score-text {
      font-size: 14px;
      font-weight: 700;
      color: #303133;
      min-width: 42px;
      text-align: right;
    }
  }

  .card-value {
    font-size: 13px;
    line-height: 1.4;
    margin: 0 0 4px;
    color: #303133;
    &.muted { color: $text-secondary; font-style: italic; }
  }

  .incomplete-tip {
    margin: 0 0 4px;
    font-size: 11px;
    color: #E6A23C;
    line-height: 1.4;
  }

  .fusion-tags {
    margin: 6px 0 0;
    font-size: 11px;
    color: #909399;
    line-height: 1.4;
  }
}

.portrait-banner {
  background: linear-gradient(135deg, #f0f9eb 0%, #ecf5ff 100%);
  border-radius: 12px;
  padding: 18px 18px 16px;
  margin-bottom: 16px;
  .portrait-lead {
    margin: 0 0 8px;
    font-size: 16px;
    font-weight: 700;
    line-height: 1.55;
    color: #303133;
  }
  .portrait-detail {
    margin: 0;
    font-size: 13px;
    line-height: 1.7;
    color: #606266;
  }
}

.trust-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}
.trust-cell {
  background: #F5F7FA;
  border-radius: 10px;
  padding: 12px 14px;
}
.trust-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}
.trust-body {
  font-size: 13px;
  color: #303133;
  line-height: 1.5;
  font-weight: 500;
}

.section {
  margin-bottom: 14px;
  h5 { margin: 0 0 8px; font-size: 14px; color: #303133; }
  ul {
    margin: 0 0 8px;
    padding-left: 18px;
    li { font-size: 13px; color: #606266; line-height: 1.65; margin-bottom: 4px; }
  }
  p { margin: 0 0 10px; font-size: 13px; color: #606266; line-height: 1.65; }
  .for-you {
    margin: 0;
    padding: 10px 12px;
    background: #fafafa;
    border-radius: 8px;
    font-size: 13px;
    color: #606266;
    line-height: 1.65;
  }
  &.suggest {
    background: #ecf5ff;
    border-radius: 10px;
    padding: 14px 16px;
  }
}

@media (max-width: 640px) {
  .trust-grid { grid-template-columns: 1fr; }
}
</style>
