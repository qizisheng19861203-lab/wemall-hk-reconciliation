<template>
  <div>
    <div class="page-header"><h2>统计报表</h2></div>
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>月度供货统计</span>
              <el-select v-model="year" style="width:100px" @change="loadMonthly">
                <el-option v-for="y in years" :key="y" :label="`${y}年`" :value="y" />
              </el-select>
            </div>
          </template>
          <v-chart :option="monthlyOption" style="height:300px" autoresize />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" header="年度供货对比">
          <v-chart :option="yearlyOption" style="height:300px" autoresize />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { reports as reportsApi } from '@/api'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

const year = ref(new Date().getFullYear())
const years = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i)
const monthly = ref([])
const yearly = ref([])

const monthlyOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['供货额', '退款额', '净供货额'] },
  xAxis: { type: 'category', data: monthly.value.map(m => `${m.month}月`) },
  yAxis: { type: 'value' },
  series: [
    { name: '供货额', type: 'bar', data: monthly.value.map(m => m.supply_rmb), color: '#409EFF' },
    { name: '退款额', type: 'bar', data: monthly.value.map(m => -m.refund_rmb), color: '#F56C6C' },
    { name: '净供货额', type: 'bar', data: monthly.value.map(m => m.net_rmb), color: '#67C23A' },
  ],
}))

const yearlyOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['净供货额', '订单数'] },
  xAxis: { type: 'category', data: yearly.value.map(y => `${y.year}年`) },
  yAxis: [{ type: 'value', name: 'RMB' }, { type: 'value', name: '订单数', position: 'right' }],
  series: [
    { name: '净供货额', type: 'bar', data: yearly.value.map(y => y.net_rmb), color: '#409EFF' },
    { name: '订单数', type: 'bar', yAxisIndex: 1, data: yearly.value.map(y => y.order_count), color: '#E6A23C' },
  ],
}))

async function loadMonthly() {
  monthly.value = await reportsApi.monthly(year.value)
}

onMounted(async () => {
  await Promise.all([loadMonthly(), reportsApi.yearly().then(d => yearly.value = d)])
})
</script>
