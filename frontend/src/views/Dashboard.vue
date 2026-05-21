<template>
  <div>
    <div class="page-header"><h2>总览</h2></div>

    <el-row :gutter="16" style="margin-bottom:20px">
      <el-col :span="6" v-for="card in statCards" :key="card.label">
        <el-card shadow="never" :class="['stat-card', card.color]">
          <div class="stat-icon"><el-icon :size="28"><component :is="card.icon" /></el-icon></div>
          <div class="stat-val">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 月度每日供货图 -->
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="24">
        <el-card shadow="never">
          <template #header>
            <div style="display:flex;align-items:center;justify-content:space-between">
              <span>本月每日供货额(RMB) — {{ currentMonthLabel }}</span>
              <div style="display:flex;gap:8px;align-items:center">
                <el-button-group>
                  <el-button size="small" @click="prevMonth">‹ 上月</el-button>
                  <el-button size="small" @click="goCurrentMonth">本月</el-button>
                  <el-button size="small" @click="nextMonth" :disabled="isCurrentMonth">下月 ›</el-button>
                </el-button-group>
              </div>
            </div>
          </template>
          <v-chart :option="dailyChartOption" style="height:260px" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <!-- 年度月度图 -->
    <el-row :gutter="16">
      <el-col :span="24">
        <el-card shadow="never" :header="`${currentYear}年 月度供货额(RMB)`">
          <v-chart :option="monthlyChartOption" style="height:240px" autoresize />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { reports as reportsApi } from '@/api'
import dayjs from 'dayjs'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

const stats = ref({})
const monthly = ref([])
const daily = ref([])
const currentYear = new Date().getFullYear()

const viewYear = ref(new Date().getFullYear())
const viewMonth = ref(new Date().getMonth() + 1)

const isCurrentMonth = computed(() => {
  const now = new Date()
  return viewYear.value === now.getFullYear() && viewMonth.value === (now.getMonth() + 1)
})

const currentMonthLabel = computed(() => `${viewYear.value}年${viewMonth.value}月`)

function prevMonth() {
  if (viewMonth.value === 1) { viewYear.value--; viewMonth.value = 12 }
  else viewMonth.value--
  loadDaily()
}
function nextMonth() {
  if (isCurrentMonth.value) return
  if (viewMonth.value === 12) { viewYear.value++; viewMonth.value = 1 }
  else viewMonth.value++
  loadDaily()
}
function goCurrentMonth() {
  viewYear.value = new Date().getFullYear()
  viewMonth.value = new Date().getMonth() + 1
  loadDaily()
}

const statCards = computed(() => [
  { label: '未结算供货额(RMB)', value: `¥${(stats.value.unsettled_rmb || 0).toFixed(2)}`, icon: 'Money', color: 'red' },
  { label: '今日供货额(RMB)', value: `¥${(stats.value.today_supply_rmb || 0).toFixed(2)}`, icon: 'TrendCharts', color: 'blue' },
  { label: '本月供货额(RMB)', value: `¥${(stats.value.month_supply_rmb || 0).toFixed(2)}`, icon: 'DataLine', color: 'green' },
  { label: '待结算单数', value: stats.value.pending_settlements || 0, icon: 'Document', color: 'orange' },
])

const dailyChartOption = computed(() => {
  const hasData = daily.value.some(d => d.supply_rmb > 0)
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const d = params[0]
        return `${viewMonth.value}月${d.name}日<br/>供货额：¥${d.value.toFixed(2)}`
      }
    },
    xAxis: {
      type: 'category',
      data: daily.value.map(d => d.day),
      axisLabel: { fontSize: 11 },
    },
    yAxis: { type: 'value', name: 'RMB', axisLabel: { fontSize: 11 } },
    series: [{
      name: '供货额',
      type: 'bar',
      data: daily.value.map(d => d.supply_rmb),
      color: '#409EFF',
      label: {
        show: false,
      },
      emphasis: { focus: 'series' },
    }],
    graphic: hasData ? [] : [{
      type: 'text',
      left: 'center',
      top: 'middle',
      style: { text: '暂无数据', fill: '#C0C4CC', fontSize: 14 }
    }],
  }
})

const monthlyChartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: monthly.value.map(m => `${m.month}月`) },
  yAxis: { type: 'value', name: 'RMB' },
  series: [
    { name: '供货额', type: 'bar', data: monthly.value.map(m => m.supply_rmb), color: '#409EFF' },
    { name: '净额', type: 'bar', data: monthly.value.map(m => m.net_rmb), color: '#67C23A' },
  ],
}))

async function loadDaily() {
  daily.value = await reportsApi.monthlyDaily(viewYear.value, viewMonth.value)
}

onMounted(async () => {
  const year = new Date().getFullYear()
  const [s, m] = await Promise.all([
    reportsApi.dashboard(),
    reportsApi.monthly(year),
  ])
  stats.value = s
  monthly.value = m
  await loadDaily()
})
</script>

<style scoped>
.stat-card { position: relative; overflow: hidden; }
.stat-val { font-size: 24px; font-weight: 700; margin: 8px 0 4px; }
.stat-label { font-size: 13px; color: #909399; }
.stat-icon { position: absolute; right: 16px; top: 16px; opacity: 0.15; }
.red .stat-val { color: #F56C6C; }
.blue .stat-val { color: #409EFF; }
.green .stat-val { color: #67C23A; }
.orange .stat-val { color: #E6A23C; }
</style>
