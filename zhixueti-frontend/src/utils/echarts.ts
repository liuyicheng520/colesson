/**
 * ECharts 按需注册（全站唯一入口）。
 *
 * 原先各页面 `import * as echarts from 'echarts'` 会把全部图表与组件打进主包；
 * 此处只注册实际用到的 4 类图表与 6 个组件，配合 vite manualChunks 单独成块。
 *
 * 新增图表类型时，在此处补充 `echarts.use([...])` 即可，页面不需要改动引入方式。
 */
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart, RadarChart } from 'echarts/charts'
import {
  GraphicComponent,
  GridComponent,
  LegendComponent,
  RadarComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  RadarChart,
  GraphicComponent,
  GridComponent,
  LegendComponent,
  RadarComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
])

export type { ECharts } from 'echarts/core'
export default echarts
