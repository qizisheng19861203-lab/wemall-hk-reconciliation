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

    <el-row :gutter="16">
      <el-col :span="14">
        <el-card shadow="never" header="本年月度供货额(RMB)">
          <v-chart :option="monthlyChartOption" style="height:280px" autoresize />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never" header="汇率走势(近30日)">
          <v-chart :option="rateChartOption" style="height:280px" autoresize />
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
import { reports as reportsApi, rates as ratesApi } from '@/api'
import dayjs from 'dayjs'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

const stats = ref({})
const monthly = ref([])
const rateData = ref([])

const statCards = computed(() => [
  { label: '未结算供货额(RMB)', value: `¥${(stats.value.unsettled_rmb || 0).toFixed(2)}`, icon: 'Money', color: 'red' },
  { label: '今日供货额(RMB)', value: `¥${(stats.value.today_supply_rmb || 0).toFixed(2)}`, icon: 'TrendCharts', color: 'blue' },
  { label: '本月供货额(RMB)', value: `¥${(stats.value.month_supply_rmb || 0).toFixed(2)}`, icon: 'DataLine', color: 'green' },
  { label: '待结算单数', value: stats.value.pending_settlements || 0, icon: 'Document', color: 'orange' },
])

const monthlyChartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: monthly.value.map(m => `${m.month}月`) },
  yAxis: { type: 'value', name: 'RMB' },
  series: [
    { name: '供货额', type: 'bar', data: monthly.value.map(m => m.supply_rmb), color: '#409EFF' },
    { name: '净额', type: 'bar', data: monthly.value.map(m => m.net_rmb), color: '#67C23A' },
  ],
}))

const rateChartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: rateData.value.map(r => r.date) },
  yAxis: { type: 'value', name: 'HKD→CNY', scale: true },
  series: [{ name: '汇率', type: 'line', data: rateData.value.map(r => r.hkd_to_cny), smooth: true, color: '#E6A23C' }],
}))

onMounted(async () => {
  const year = new Date().getFullYear()
  const [s, m, r] = await Promise.all([
    reportsApi.dashboard(),
    reportsApi.monthly(year),
    ratesApi.list(),
  ])
  stats.value = s
  monthly.value = m
  rateData.value = r.slice(0, 30).reverse()
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
