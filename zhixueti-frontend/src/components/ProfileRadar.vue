<script setup lang="ts">
import { onMounted, onActivated, onDeactivated, onBeforeUnmount, ref, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

export type RadarDim = {
  name: string
  value: number
  summary?: string
  weak?: boolean
}

const props = defineProps<{
  dimensions: RadarDim[]
}>()

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

function dispose() {
  chart?.dispose()
  chart = null
}

function tipHtml(d: RadarDim) {
  const score = Math.round(Number(d.value) * 100)
  const extra = d.summary ? `<br/>${d.summary}` : ''
  const tag = d.weak || d.value < 0.45
    ? '<span style="color:#E6A23C">薄弱维度</span>'
    : d.value >= 0.75
      ? '<span style="color:#67C23A">优势维度</span>'
      : '<span style="color:#409EFF">均衡维度</span>'
  return `<strong>${d.name}</strong><br/>分值 ${score}｜${tag}${extra}`
}

function render() {
  if (!chartRef.value || props.dimensions.length < 2) return
  if (!chart) chart = echarts.init(chartRef.value)
  const dims = props.dimensions

  chart.setOption({
    tooltip: {
      trigger: 'item',
      appendToBody: true,
      formatter: () => dims.map(tipHtml).join('<br/><br/>'),
    },
    radar: {
      indicator: dims.map((d) => ({
        name: d.name,
        max: 1,
        color: d.weak || d.value < 0.45 ? '#E6A23C' : d.value >= 0.75 ? '#67C23A' : '#64748b',
      })),
      shape: 'polygon',
      splitArea: { areaStyle: { color: ['#F5F7FA', '#fff'] } },
      axisName: { fontSize: 12 },
      triggerEvent: true,
    },
    series: [{
      type: 'radar',
      data: [{
        value: dims.map((d) => d.value),
        name: '学习画像',
        areaStyle: { color: 'rgba(64, 158, 255, 0.18)' },
        lineStyle: { color: '#409EFF', width: 2 },
        itemStyle: { color: '#409EFF' },
        symbolSize: 10,
      }],
    }],
  }, true)

  chart.off('mouseover')
  chart.on('mouseover', (params: { componentType?: string; name?: string }) => {
    if (params.componentType !== 'radar' || !params.name || !chart) return
    const d = dims.find((x) => x.name === params.name)
    if (!d) return
    chart.setOption({ tooltip: { formatter: () => tipHtml(d) } })
  })
}

function refresh() {
  render()
  chart?.resize()
}

watch(() => props.dimensions, () => nextTick(refresh), { deep: true })

function onResize() {
  chart?.resize()
}

onMounted(() => {
  refresh()
  window.addEventListener('resize', onResize)
})

onActivated(() => {
  nextTick(() => {
    requestAnimationFrame(() => {
      dispose()
      refresh()
    })
  })
})

onDeactivated(() => dispose())

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  dispose()
})
</script>

<template>
  <div ref="chartRef" class="radar-chart" />
</template>

<style scoped>
.radar-chart { width: 100%; height: 320px; }
</style>
