<template>
  <div>
    <div class="page-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
      <div><h2 style="font-size:24px;margin:0">结算管理</h2></div>
      <div style="display:flex;gap:12px" v-if="auth.isAdmin">
        <el-button type="success" size="large" @click="quickSettle('first-half')">
          <span style="font-size:15px">结算本月1-15号</span>
        </el-button>
        <el-button type="success" size="large" @click="quickSettle('second-half')">
          <span style="font-size:15px">结算本月16-月底</span>
        </el-button>
        <el-button type="primary" size="large" @click="openCreate">
          <span style="font-size:15px">自定义结算</span>
        </el-button>
        <el-button type="warning" size="large" @click="triggerAutoSettle">
          <span style="font-size:15px">手动触发自动结算</span>
        </el-button>
      </div>
    </div>

    <!-- 未结算金额提示 -->
    <el-card shadow="never" style="margin-bottom:20px;background:#fff7e6;border-color:#ffd591" v-if="unsettledAmount > 0">
      <div style="display:flex;align-items:center;gap:16px">
        <div>
          <div style="font-size:14px;color:#8c6d00;margin-bottom:6px">当前未结算金额</div>
          <div style="font-size:32px;font-weight:700;color:#d46b08">¥{{ unsettledAmount.toFixed(2) }}</div>
        </div>
        <div style="color:#8c6d00;font-size:14px">
          建议每月15号和月底各结算一次
        </div>
      </div>
    </el-card>

    <el-card shadow="never">
      <!-- 批量下载工具栏 -->
      <div v-if="selectedIds.length > 0" style="display:flex;align-items:center;gap:12px;padding:10px 0 14px;border-bottom:1px solid #f0f0f0;margin-bottom:12px">
        <span style="color:#606266;font-size:14px">已选 <strong style="color:#409EFF">{{ selectedIds.length }}</strong> 条</span>
        <el-button type="primary" size="default" @click="batchDownload('invoice')" :loading="batchLoading.invoice">
          <el-icon style="margin-right:5px"><Download /></el-icon>
          批量下载 Invoice ({{ selectedIds.length }})
        </el-button>
        <el-button type="success" size="default" @click="batchDownload('detail')" :loading="batchLoading.detail">
          <el-icon style="margin-right:5px"><Download /></el-icon>
          批量下载明细 ({{ selectedIds.length }})
        </el-button>
        <el-button size="small" text @click="selectedIds = []">清除选择</el-button>
      </div>

      <el-table
        :data="settlements"
        v-loading="loading"
        stripe
        :row-class-name="tableRowClassName"
        style="font-size:14px"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="46" />
        <el-table-column prop="invoice_number" label="Invoice号" width="180" />
        <el-table-column label="账期" width="240">
          <template #default="{ row }">
            <span style="font-size:14px">{{ row.period_start?.slice(0,10) }} ~ {{ row.period_end?.slice(0,10) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="净供货额(RMB)" width="150" align="right">
          <template #default="{ row }">
            <span style="font-size:15px;font-weight:600">¥{{ Number(row.net_supply_rmb).toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="汇率" width="100" align="center">
          <template #default="{ row }">
            <span style="font-size:14px">{{ row.hkd_rate }}</span>
          </template>
        </el-table-column>
        <el-table-column label="应付(HKD)" width="150" align="right">
          <template #default="{ row }">
            <strong style="font-size:16px;color:#409EFF">HK${{ Number(row.payment_amount_hkd).toFixed(2) }}</strong>
          </template>
        </el-table-column>
        <el-table-column prop="order_count" label="订单数" width="90" align="center">
          <template #default="{ row }">
            <span style="font-size:14px">{{ row.order_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType[row.status]" size="large">{{ statusLabel[row.status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="320" fixed="right">
          <template #default="{ row }">
            <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
              <!-- Invoice 下载按钮 - 醒目蓝色 + PDF图标 -->
              <el-button
                size="default" type="primary"
                @click="downloadPdf(row, 'invoice')"
                style="font-weight:600;letter-spacing:0.3px"
              >
                <el-icon style="margin-right:4px"><Document /></el-icon>
                Invoice账单
              </el-button>
              <!-- 明细下载按钮 - 绿色 + PDF图标 -->
              <el-button
                size="default" type="success"
                @click="downloadPdf(row, 'detail')"
                style="font-weight:600"
              >
                <el-icon style="margin-right:4px"><Tickets /></el-icon>
                明细PDF
              </el-button>
              <el-button size="default" type="warning" v-if="auth.isAdmin && row.status !== 'settled'"
                @click="openConfirm(row)">确认收款</el-button>
              <el-button size="default" type="danger" v-if="auth.isAdmin && row.status !== 'settled'"
                @click="deleteSettlement(row.id)">删除</el-button>
              <el-button size="default" v-if="auth.isAdmin" @click="sendNotify(row.id)">发通知</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 自定义结算 -->
    <el-dialog v-model="createDialog" title="自定义结算单" width="500px">
      <el-alert type="info" :closable="false" style="margin-bottom:12px">
        选择日期范围，系统会自动计算该周期内的未结算订单并获取今日汇率
      </el-alert>
      <el-form :model="createForm" label-width="90px">
        <el-form-item label="账期开始">
          <el-date-picker v-model="createForm.period_start" type="date" value-format="YYYY-MM-DD" placeholder="选择开始日期" />
        </el-form-item>
        <el-form-item label="账期结束">
          <el-date-picker v-model="createForm.period_end" type="date" value-format="YYYY-MM-DD" placeholder="选择结束日期" />
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="createForm.notes" type="textarea" rows="2" /></el-form-item>
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
          <strong style="font-size:18px">HK${{ confirmingSettlement?.payment_amount_hkd }}</strong>
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
import { Document, Tickets, Download } from '@element-plus/icons-vue'
import { settlements as settlementsApi, orders as ordersApi, rates as ratesApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const settlements = ref([])
const loading = ref(false)
const creating = ref(false)
const confirming = ref(false)
const createDialog = ref(false)
const confirmDialog = ref(false)
const confirmingSettlement = ref(null)
const unsettledAmount = ref(0)
const selectedIds = ref([])
const batchLoading = reactive({ invoice: false, detail: false })

const createForm = reactive({ period_start: '', period_end: '', notes: '' })
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

async function quickSettle(period) {
  const now = new Date()
  let start, end, periodName

  if (period === 'first-half') {
    // 本月1-15号（北京时间）
    start = new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 0)
    end = new Date(now.getFullYear(), now.getMonth(), 15, 23, 59, 59)
    periodName = `${now.getFullYear()}年${now.getMonth() + 1}月1-15号`
  } else {
    // 本月16-月底（北京时间）
    start = new Date(now.getFullYear(), now.getMonth(), 16, 0, 0, 0)
    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()
    end = new Date(now.getFullYear(), now.getMonth(), lastDay, 23, 59, 59)
    periodName = `${now.getFullYear()}年${now.getMonth() + 1}月16-${lastDay}号`
  }

  try {
    await ElMessageBox.confirm(`确认结算 ${periodName}？`, '提示', { type: 'warning' })

    // 获取今日汇率
    const rate = await ratesApi.today()

    // 转换为本地时间字符串（YYYY-MM-DD HH:mm:ss）
    const formatLocalDateTime = (date) => {
      const pad = n => String(n).padStart(2, '0')
      return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
    }

    // 获取该周期订单
    const orders = await ordersApi.list({
      unsettled_only: true,
      is_refunded: false,
      start_date: formatLocalDateTime(start),
      end_date: formatLocalDateTime(end),
      limit: 500,
    })

    if (!orders.length) {
      return ElMessage.warning('该周期没有未结算订单')
    }

    const orderIds = orders.map(o => o.id)

    creating.value = true
    await settlementsApi.create({
      period_start: formatLocalDateTime(start),
      period_end: formatLocalDateTime(end),
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
    // 获取今日汇率
    const rate = await ratesApi.today()

    // 构造完整的日期时间（开始日期 00:00:00，结束日期 23:59:59）
    const startDateTime = `${createForm.period_start} 00:00:00`
    const endDateTime = `${createForm.period_end} 23:59:59`

    // 获取该周期订单
    const orders = await ordersApi.list({
      unsettled_only: true,
      is_refunded: false,
      start_date: startDateTime,
      end_date: endDateTime,
      limit: 500,
    })

    if (!orders.length) {
      return ElMessage.warning('该周期没有未结算订单')
    }

    const orderIds = orders.map(o => o.id)

    await settlementsApi.create({
      period_start: startDateTime,
      period_end: endDateTime,
      hkd_rate: Number(rate.hkd_to_cny),
      order_ids: orderIds,
      notes: createForm.notes || `自定义结算 ${createForm.period_start} ~ ${createForm.period_end}`,
    })

    ElMessage.success('结算单创建成功')
    createDialog.value = false
    load()
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  } finally {
    creating.value = false
  }
}

function openCreate() {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), 1)
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0)
  Object.assign(createForm, {
    period_start: start.toISOString().slice(0, 10),
    period_end: end.toISOString().slice(0, 10),
    notes: '',
  })
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

async function deleteSettlement(id) {
  try {
    await ElMessageBox.confirm('确认删除此结算单？删除后订单将恢复为未结算状态。', '警告', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
    })
    await settlementsApi.delete(id)
    ElMessage.success('删除成功')
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

// 格式化文件名日期：取账期结束日 YYYYMMDD
function fmtDate(dateStr) {
  return dateStr ? dateStr.slice(0, 10).replace(/-/g, '') : ''
}

async function downloadPdf(row, type) {
  const token = localStorage.getItem('token')
  const url = type === 'invoice' ? settlementsApi.invoiceUrl(row.id) : settlementsApi.detailUrl(row.id)
  const date = fmtDate(row.period_end)
  const filename = type === 'invoice'
    ? `Invoice#${row.invoice_number}+香港蔚蓝+${date}.pdf`
    : `OrderDetail+香港蔚蓝+${date}.pdf`

  try {
    const response = await fetch(url, { headers: { 'Authorization': `Bearer ${token}` } })
    if (!response.ok) throw new Error('下载失败')
    const blob = await response.blob()
    const a = document.createElement('a')
    a.href = window.URL.createObjectURL(blob)
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(a.href)
  } catch (e) {
    ElMessage.error(e.message || 'PDF下载失败')
  }
}

function handleSelectionChange(rows) {
  selectedIds.value = rows.map(r => r.id)
}

async function batchDownload(type) {
  if (!selectedIds.value.length) return
  const token = localStorage.getItem('token')
  const url = type === 'invoice'
    ? settlementsApi.batchInvoiceUrl(selectedIds.value)
    : settlementsApi.batchDetailUrl(selectedIds.value)
  const filename = type === 'invoice' ? 'Invoices+香港蔚蓝.zip' : 'OrderDetails+香港蔚蓝.zip'

  batchLoading[type] = true
  try {
    const response = await fetch(url, { headers: { 'Authorization': `Bearer ${token}` } })
    if (!response.ok) throw new Error('批量下载失败')
    const blob = await response.blob()
    const a = document.createElement('a')
    a.href = window.URL.createObjectURL(blob)
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(a.href)
    ElMessage.success(`已下载 ${selectedIds.value.length} 个PDF`)
  } catch (e) {
    ElMessage.error(e.message || '批量下载失败')
  } finally {
    batchLoading[type] = false
  }
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
    const res = await settlementsApi.autoSettle({ force: true })
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
