<template>
  <div>
    <div class="page-header" style="display:flex;justify-content:space-between;align-items:center">
      <div><h2>结算管理</h2></div>
      <div style="display:flex;gap:8px" v-if="auth.isAdmin">
        <el-button type="success" @click="quickSettle('first-half')">结算本月1-15号</el-button>
        <el-button type="success" @click="quickSettle('second-half')">结算本月16-月底</el-button>
        <el-button type="primary" @click="openCreate">自定义结算</el-button>
        <el-button type="warning" @click="triggerAutoSettle">手动触发自动结算</el-button>
      </div>
    </div>

    <!-- 未结算金额提示 -->
    <el-card shadow="never" style="margin-bottom:16px;background:#fff7e6;border-color:#ffd591" v-if="unsettledAmount > 0">
      <div style="display:flex;align-items:center;gap:16px">
        <div>
          <div style="font-size:13px;color:#8c6d00;margin-bottom:4px">当前未结算金额</div>
          <div style="font-size:28px;font-weight:700;color:#d46b08">¥{{ unsettledAmount.toFixed(2) }}</div>
        </div>
        <div style="color:#8c6d00;font-size:13px">
          建议每月15号和月底各结算一次
        </div>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table :data="settlements" v-loading="loading" stripe :row-class-name="tableRowClassName">
        <el-table-column prop="invoice_number" label="Invoice号" width="160" />
        <el-table-column label="账期" width="200">
          <template #default="{ row }">{{ row.period_start?.slice(0,10) }} ~ {{ row.period_end?.slice(0,10) }}</template>
        </el-table-column>
        <el-table-column label="净供货额(RMB)" width="130" align="right">
          <template #default="{ row }">¥{{ Number(row.net_supply_rmb).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="汇率" width="100" align="center">
          <template #default="{ row }">{{ row.hkd_rate }}</template>
        </el-table-column>
        <el-table-column label="应付(HKD)" width="120" align="right">
          <template #default="{ row }"><strong>HK${{ Number(row.payment_amount_hkd).toFixed(2) }}</strong></template>
        </el-table-column>
        <el-table-column prop="order_count" label="订单数" width="80" align="center" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType[row.status]" size="small">{{ statusLabel[row.status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link @click="downloadPdf(row.id, 'invoice')">Invoice</el-button>
            <el-button size="small" link @click="downloadPdf(row.id, 'detail')">明细</el-button>
            <el-button size="small" link type="warning" v-if="auth.isAdmin && row.status !== 'settled'"
              @click="openConfirm(row)">确认收款</el-button>
            <el-button size="small" link v-if="auth.isAdmin" @click="sendNotify(row.id)">发通知</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 自定义结算 -->
    <el-dialog v-model="createDialog" title="自定义结算单" width="600px">
      <el-alert type="info" :closable="false" style="margin-bottom:12px">
        手动选择时间范围创建结算单，系统会自动计算该周期内的未结算订单
      </el-alert>
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="账期开始">
          <el-date-picker v-model="createForm.period_start" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" />
        </el-form-item>
        <el-form-item label="账期结束">
          <el-date-picker v-model="createForm.period_end" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" />
        </el-form-item>
        <el-form-item label="汇率(HKD→RMB)">
          <el-input-number v-model="createForm.hkd_rate" :precision="4" :min="0.01" style="width:160px" />
          <el-button link @click="fetchTodayRate" style="margin-left:8px">获取今日汇率</el-button>
        </el-form-item>
        <el-form-item label="预览">
          <el-button @click="previewOrders" :loading="previewing">查看该周期订单</el-button>
          <span style="margin-left:8px;color:#909399" v-if="previewData">
            共 {{ previewData.order_count }} 笔订单，合计 ¥{{ previewData.total_rmb.toFixed(2) }}
          </span>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="createForm.notes" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" @click="createSettlement" :loading="creating">创建结算单</el-button>
      </template>
    </el-dialog>

    <!-- 确认收款 -->
    <el-dialog v-model="confirmDialog" title="确认收款" width="420px">
      <el-form :model="confirmForm" label-width="110px">
        <el-form-item label="应付金额(HKD)">
          <strong>HK${{ confirmingSettlement?.payment_amount_hkd }}</strong>
        </el-form-item>
        <el-form-item label="实付金额(HKD)">
          <el-input-number v-model="confirmForm.actual_payment_hkd" :precision="2" :min="0" />
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="confirmForm.notes" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="confirmDialog = false">取消</el-button>
        <el-button type="success" @click="confirmSettlement" :loading="confirming">确认结清</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { settlements as settlementsApi, orders as ordersApi, rates as ratesApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const settlements = ref([])
const loading = ref(false)
const creating = ref(false)
const confirming = ref(false)
const previewing = ref(false)
const createDialog = ref(false)
const confirmDialog = ref(false)
const confirmingSettlement = ref(null)
const unsettledAmount = ref(0)
const previewData = ref(null)

const createForm = reactive({ period_start: '', period_end: '', hkd_rate: 0.9, notes: '' })
const confirmForm = reactive({ actual_payment_hkd: 0, notes: '' })

const statusLabel = { pending: '待结算', notified: '已通知', settled: '已结清' }
const statusType = { pending: 'warning', notified: 'primary', settled: 'success' }

function tableRowClassName({ row }) {
  return row.status === 'settled' ? 'settled-row' : ''
}

async function load() {
  loading.value = true
  try {
    settlements.value = await settlementsApi.list()
    await loadUnsettledAmount()
  } finally {
    loading.value = false
  }
}

async function loadUnsettledAmount() {
  try {
    const stats = await ordersApi.stats({ unsettled_only: true })
    unsettledAmount.value = stats.unsettled_rmb || 0
  } catch (e) {
    console.error('Failed to load unsettled amount:', e)
  }
}

async function fetchTodayRate() {
  try {
    const rate = await ratesApi.today()
    createForm.hkd_rate = Number(rate.hkd_to_cny)
    ElMessage.success(`已填入今日汇率：1 HKD = ${rate.hkd_to_cny} CNY`)
  } catch {
    ElMessage.warning('今日汇率未录入，请手动输入')
  }
}

async function previewOrders() {
  if (!createForm.period_start || !createForm.period_end) {
    return ElMessage.warning('请先选择账期')
  }
  previewing.value = true
  try {
    const orders = await ordersApi.list({
      unsettled_only: true,
      is_refunded: false,
      start_date: createForm.period_start,
      end_date: createForm.period_end,
      limit: 500,
    })
    let total = 0
    orders.forEach(o => {
      o.items?.forEach(item => {
        total += item.supply_subtotal || 0
      })
    })
    previewData.value = { order_count: orders.length, total_rmb: total }
    ElMessage.success(`找到 ${orders.length} 笔未结算订单`)
  } finally {
    previewing.value = false
  }
}

async function quickSettle(period) {
  const now = new Date()
  let start, end, periodName

  if (period === 'first-half') {
    // 本月1-15号
    start = new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 0)
    end = new Date(now.getFullYear(), now.getMonth(), 15, 23, 59, 59)
    periodName = `${now.getFullYear()}年${now.getMonth() + 1}月1-15号`
  } else {
    // 本月16-月底
    start = new Date(now.getFullYear(), now.getMonth(), 16, 0, 0, 0)
    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()
    end = new Date(now.getFullYear(), now.getMonth(), lastDay, 23, 59, 59)
    periodName = `${now.getFullYear()}年${now.getMonth() + 1}月16-${lastDay}号`
  }

  try {
    await ElMessageBox.confirm(`确认结算 ${periodName}？`, '提示', { type: 'warning' })

    // 获取今日汇率
    const rate = await ratesApi.today()

    // 获取该周期订单
    const orders = await ordersApi.list({
      unsettled_only: true,
      is_refunded: false,
      start_date: start.toISOString(),
      end_date: end.toISOString(),
      limit: 500,
    })

    if (!orders.length) {
      return ElMessage.warning('该周期没有未结算订单')
    }

    const orderIds = orders.map(o => o.id)

    creating.value = true
    await settlementsApi.create({
      period_start: start.toISOString(),
      period_end: end.toISOString(),
      hkd_rate: Number(rate.hkd_to_cny),
      order_ids: orderIds,
      notes: `快速结算 ${periodName}`,
    })

    ElMessage.success('结算单创建成功')
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '操作失败')
  } finally {
    creating.value = false
  }
}

async function createSettlement() {
  if (!createForm.period_start || !createForm.period_end) {
    return ElMessage.warning('请选择账期')
  }

  creating.value = true
  try {
    // 获取该周期订单
    const orders = await ordersApi.list({
      unsettled_only: true,
      is_refunded: false,
      start_date: createForm.period_start,
      end_date: createForm.period_end,
      limit: 500,
    })

    if (!orders.length) {
      return ElMessage.warning('该周期没有未结算订单')
    }

    const orderIds = orders.map(o => o.id)

    await settlementsApi.create({
      ...createForm,
      order_ids: orderIds,
    })

    ElMessage.success('结算单创建成功')
    createDialog.value = false
    load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    creating.value = false
  }
}

function openCreate() {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 0)
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59)
  Object.assign(createForm, {
    period_start: start.toISOString().slice(0, 19).replace('T', ' '),
    period_end: end.toISOString().slice(0, 19).replace('T', ' '),
    hkd_rate: 0.9,
    notes: '',
  })
  previewData.value = null
  createDialog.value = true
}

function openConfirm(s) {
  confirmingSettlement.value = s
  confirmForm.actual_payment_hkd = Number(s.payment_amount_hkd)
  confirmForm.notes = ''
  confirmDialog.value = true
}

async function confirmSettlement() {
  confirming.value = true
  try {
    await settlementsApi.confirm(confirmingSettlement.value.id, confirmForm)
    ElMessage.success('已确认结清')
    confirmDialog.value = false
    load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    confirming.value = false
  }
}

function downloadPdf(id, type) {
  const token = localStorage.getItem('token')
  const url = type === 'invoice' ? settlementsApi.invoiceUrl(id) : settlementsApi.detailUrl(id)
  const a = document.createElement('a')
  a.href = url + `?token=${token}`
  a.target = '_blank'
  a.click()
}

async function sendNotify(id) {
  try {
    await ElMessageBox.confirm('确认发送结算通知短信？', '提示', { type: 'warning' })
    const res = await settlementsApi.notify(id)
    ElMessage.success(`通知发送成功：${res.success}/${res.total}`)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message)
  }
}

async function triggerAutoSettle() {
  try {
    await ElMessageBox.confirm('手动触发自动结算任务？系统会根据今天的日期判断应该结算哪个周期。', '提示', { type: 'warning' })
    const res = await settlementsApi.autoSettle()
    ElMessage.success(res.message || '自动结算完成')
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '操作失败')
  }
}

onMounted(load)
</script>

<style scoped>
:deep(.settled-row) {
  background-color: #f0f9ff !important;
}
:deep(.settled-row:hover > td) {
  background-color: #e6f4ff !important;
}
</style>
