<template>
  <div>
    <div class="page-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
      <div><h2 style="font-size:24px;margin:0">结算管理</h2></div>
      <div style="display:flex;gap:12px;flex-wrap:wrap" v-if="auth.isAdmin">
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
        <div style="color:#8c6d00;font-size:14px">建议每月15号和月底各结算一次</div>
      </div>
    </el-card>

    <el-card shadow="never">
      <!-- 工具栏：年度下载 + 批量操作 -->
      <div style="display:flex;align-items:center;gap:16px;padding:0 0 14px;border-bottom:1px solid #f0f0f0;margin-bottom:12px;flex-wrap:wrap">
        <!-- 年度一键下载 -->
        <div style="display:flex;align-items:center;gap:8px">
          <el-select v-model="selectedYear" style="width:110px" size="default">
            <el-option v-for="y in availableYears" :key="y" :label="`${y}年`" :value="y" />
          </el-select>
          <el-button type="primary" plain size="default" @click="yearDownload('invoice')" :loading="yearLoading.invoice">
            <el-icon style="margin-right:4px"><Download /></el-icon>
            下载全年Invoice
          </el-button>
          <el-button type="success" plain size="default" @click="yearDownload('detail')" :loading="yearLoading.detail">
            <el-icon style="margin-right:4px"><Download /></el-icon>
            下载全年明细
          </el-button>
        </div>

        <!-- 分隔线 -->
        <div v-if="selectedIds.length > 0" style="height:28px;width:1px;background:#dcdfe6"></div>

        <!-- 批量选择操作 -->
        <div v-if="selectedIds.length > 0" style="display:flex;align-items:center;gap:8px">
          <span style="color:#606266;font-size:14px">已选 <strong style="color:#409EFF">{{ selectedIds.length }}</strong> 条</span>
          <el-button type="primary" size="default" @click="batchDownload('invoice')" :loading="batchLoading.invoice">
            <el-icon style="margin-right:4px"><Download /></el-icon>
            批量Invoice ({{ selectedIds.length }})
          </el-button>
          <el-button type="success" size="default" @click="batchDownload('detail')" :loading="batchLoading.detail">
            <el-icon style="margin-right:4px"><Download /></el-icon>
            批量明细 ({{ selectedIds.length }})
          </el-button>
          <el-button size="small" text @click="selectedIds = []">清除</el-button>
        </div>
      </div>

      <!-- 下载进度提示 -->
      <el-alert
        v-if="downloadProgress.show"
        :title="downloadProgress.text"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom:12px"
      >
        <template #default>
          <el-progress :percentage="downloadProgress.pct" :striped="true" :striped-flow="true" :duration="6" />
        </template>
      </el-alert>

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
        <el-table-column label="操作" min-width="380" fixed="right">
          <template #default="{ row }">
            <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
              <!-- Invoice 下载 -->
              <el-button
                size="default" type="primary"
                @click="downloadPdf(row, 'invoice')"
                :loading="downloadingId === `${row.id}-invoice`"
                style="font-weight:600;letter-spacing:0.3px"
              >
                <el-icon v-if="downloadingId !== `${row.id}-invoice`" style="margin-right:4px"><Document /></el-icon>
                Invoice账单
              </el-button>
              <!-- 明细 PDF -->
              <el-button
                size="default" type="success"
                @click="downloadPdf(row, 'detail')"
                :loading="downloadingId === `${row.id}-detail`"
                style="font-weight:600"
              >
                <el-icon v-if="downloadingId !== `${row.id}-detail`" style="margin-right:4px"><Tickets /></el-icon>
                明细PDF
              </el-button>
              <el-button size="default" type="warning" v-if="auth.isAdmin && row.status !== 'settled'"
                @click="openConfirm(row)">确认收款</el-button>
              <!-- 短信通知按钮 -->
              <el-button
                v-if="auth.isAdmin"
                size="default"
                type="info"
                plain
                @click="sendNotify(row.id)"
                :loading="notifyingId === row.id"
                style="border-color:#67c23a;color:#67c23a;background:#f0f9eb"
              >
                <el-icon v-if="notifyingId !== row.id" style="margin-right:4px"><Bell /></el-icon>
                发通知
              </el-button>
              <!-- 邮件通知按钮 -->
              <el-button
                v-if="auth.isAdmin"
                size="default"
                type="info"
                plain
                @click="sendEmail(row.id)"
                :loading="emailingId === row.id"
                style="border-color:#409eff;color:#409eff;background:#ecf5ff"
              >
                <el-icon v-if="emailingId !== row.id" style="margin-right:4px"><Message /></el-icon>
                发邮件
              </el-button>
              <el-button size="default" type="danger" plain v-if="auth.isAdmin && row.status !== 'settled'"
                @click="deleteSettlement(row.id)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 自定义结算 -->
    <el-dialog v-model="createDialog" title="自定义结算单" width="500px" :teleported="false">
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
    <el-dialog v-model="confirmDialog" title="确认收款" width="420px" :teleported="false">
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
import { ref, reactive, onMounted, onBeforeUnmount, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, Tickets, Download, Bell, Message } from '@element-plus/icons-vue'
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
const yearLoading = reactive({ invoice: false, detail: false })
const downloadingId = ref('')   // 单个下载时记录 `${id}-${type}`
const notifyingId = ref(null)   // 发短信时记录 id
const emailingId = ref('')       // 发邮件时记录 id

// 年度下载
const currentYear = new Date().getFullYear()
const selectedYear = ref(currentYear)
const availableYears = computed(() => {
  const years = new Set()
  settlements.value.forEach(s => {
    if (s.period_end) years.add(parseInt(s.period_end.slice(0, 4)))
  })
  // 确保当年和前两年都在列表中
  for (let y = currentYear - 2; y <= currentYear; y++) years.add(y)
  return [...years].sort((a, b) => b - a)
})

// 下载进度
const downloadProgress = reactive({ show: false, text: '', pct: 0 })

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
    start = new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 0)
    end = new Date(now.getFullYear(), now.getMonth(), 15, 23, 59, 59)
    periodName = `${now.getFullYear()}年${now.getMonth() + 1}月1-15号`
  } else {
    start = new Date(now.getFullYear(), now.getMonth(), 16, 0, 0, 0)
    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()
    end = new Date(now.getFullYear(), now.getMonth(), lastDay, 23, 59, 59)
    periodName = `${now.getFullYear()}年${now.getMonth() + 1}月16-${lastDay}号`
  }

  try {
    await ElMessageBox.confirm(`确认结算 ${periodName}？`, '提示', { type: 'warning' })
    const rate = await ratesApi.today()
    const formatLocalDateTime = (date) => {
      const pad = n => String(n).padStart(2, '0')
      return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
    }
    const orders = await ordersApi.list({
      unsettled_only: true, is_refunded: false,
      start_date: formatLocalDateTime(start), end_date: formatLocalDateTime(end), limit: 500,
    })
    if (!orders.length) return ElMessage.warning('该周期没有未结算订单')
    creating.value = true
    await settlementsApi.create({
      period_start: formatLocalDateTime(start), period_end: formatLocalDateTime(end),
      hkd_rate: Number(rate.hkd_to_cny), order_ids: orders.map(o => o.id),
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
  if (!createForm.period_start || !createForm.period_end) return ElMessage.warning('请选择账期')
  creating.value = true
  try {
    const rate = await ratesApi.today()
    const startDateTime = `${createForm.period_start} 00:00:00`
    const endDateTime = `${createForm.period_end} 23:59:59`
    const orders = await ordersApi.list({
      unsettled_only: true, is_refunded: false,
      start_date: startDateTime, end_date: endDateTime, limit: 500,
    })
    if (!orders.length) return ElMessage.warning('该周期没有未结算订单')
    await settlementsApi.create({
      period_start: startDateTime, period_end: endDateTime,
      hkd_rate: Number(rate.hkd_to_cny), order_ids: orders.map(o => o.id),
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
      type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消',
    })
    await settlementsApi.delete(id)
    ElMessage.success('删除成功')
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

function fmtDate(dateStr) {
  return dateStr ? dateStr.slice(0, 10).replace(/-/g, '') : ''
}

function triggerDownload(blob, filename) {
  const objectUrl = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.style.display = 'none'
  a.href = objectUrl
  a.setAttribute('download', filename)
  document.body.appendChild(a)
  // Use a tick delay so browser processes the click before we clean up
  setTimeout(() => {
    a.click()
    setTimeout(() => {
      document.body.removeChild(a)
      window.URL.revokeObjectURL(objectUrl)
    }, 200)
  }, 10)
}

// 显示下载进度条
function showProgress(text) {
  downloadProgress.show = true
  downloadProgress.text = text
  downloadProgress.pct = 30
  // 模拟进度
  setTimeout(() => { if (downloadProgress.show) downloadProgress.pct = 60 }, 600)
  setTimeout(() => { if (downloadProgress.show) downloadProgress.pct = 85 }, 1500)
}
function hideProgress() {
  downloadProgress.pct = 100
  setTimeout(() => { downloadProgress.show = false; downloadProgress.pct = 0 }, 500)
}

async function downloadPdf(row, type) {
  const key = `${row.id}-${type}`
  if (downloadingId.value === key) return
  downloadingId.value = key
  showProgress(`正在生成 ${type === 'invoice' ? 'Invoice账单' : '明细PDF'}（约8-15秒）...`)
  const token = localStorage.getItem('token')
  const url = type === 'invoice' ? settlementsApi.invoiceUrl(row.id) : settlementsApi.detailUrl(row.id)
  const date = fmtDate(row.period_end)
  const filename = type === 'invoice'
    ? `Invoice#${row.invoice_number}+香港蔚蓝+${date}.pdf`
    : `OrderDetail+香港蔚蓝+${date}.pdf`
  try {
    const response = await fetch(url, { headers: { 'Authorization': `Bearer ${token}` } })
    if (response.status === 401) { ElMessage.error('登录已过期，请重新登录'); return }
    if (!response.ok) throw new Error(`服务器错误 ${response.status}`)
    const blob = await response.blob()
    triggerDownload(blob, filename)
    hideProgress()
  } catch (e) {
    hideProgress()
    if (e.name === 'TypeError' && e.message === 'Failed to fetch') {
      ElMessage.error('网络连接中断，PDF生成需要约10秒，请稍候重试')
    } else {
      ElMessage.error(e.message || 'PDF下载失败')
    }
  } finally {
    downloadingId.value = ''
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
  showProgress(`正在打包 ${selectedIds.value.length} 个PDF（每个约8-15秒）...`)
  try {
    const response = await fetch(url, { headers: { 'Authorization': `Bearer ${token}` } })
    if (response.status === 401) { ElMessage.error('登录已过期，请重新登录'); return }
    if (!response.ok) throw new Error(`服务器错误 ${response.status}`)
    const blob = await response.blob()
    triggerDownload(blob, filename)
    hideProgress()
    ElMessage.success(`已下载 ${selectedIds.value.length} 个PDF`)
  } catch (e) {
    hideProgress()
    if (e.name === 'TypeError' && e.message === 'Failed to fetch') {
      ElMessage.error('网络中断，请勿切换页面，稍候重试')
    } else {
      ElMessage.error(e.message || '批量下载失败')
    }
  } finally {
    batchLoading[type] = false
  }
}

async function yearDownload(type) {
  const year = selectedYear.value
  const token = localStorage.getItem('token')
  const url = type === 'invoice'
    ? settlementsApi.yearInvoiceUrl(year)
    : settlementsApi.yearDetailUrl(year)
  const filename = type === 'invoice'
    ? `Invoices+香港蔚蓝+${year}年.zip`
    : `OrderDetails+香港蔚蓝+${year}年.zip`
  yearLoading[type] = true
  showProgress(`正在打包 ${year} 年全部${type === 'invoice' ? 'Invoice' : '明细'}...`)
  try {
    const response = await fetch(url, { headers: { 'Authorization': `Bearer ${token}` } })
    if (response.status === 401) { ElMessage.error('登录已过期，请重新登录'); return }
    if (!response.ok) throw new Error(`服务器错误 ${response.status}`)
    const blob = await response.blob()
    triggerDownload(blob, filename)
    hideProgress()
    ElMessage.success(`${year} 年全部PDF已下载`)
  } catch (e) {
    hideProgress()
    if (e.name === 'TypeError' && e.message === 'Failed to fetch') {
      ElMessage.error(`全年打包耗时较长，请勿切换页面，稍候重试（${year}年约需${year === new Date().getFullYear() ? '1-2' : '2-5'}分钟）`)
    } else {
      ElMessage.error(e.message || '年度下载失败')
    }
  } finally {
    yearLoading[type] = false
  }
}

async function sendNotify(id) {
  try {
    await ElMessageBox.confirm('确认发送结算通知短信？', '提示', { type: 'warning' })
    notifyingId.value = id
    const res = await settlementsApi.notify(id)
    ElMessage.success(`通知发送成功：${res.success}/${res.total}`)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '发送失败')
  } finally {
    notifyingId.value = null
  }
}

async function sendEmail(id) {
  if (emailingId.value === id) return
  emailingId.value = id
  const loadingMsg = ElMessage({
    message: '正在生成账单并发送邮件，请稍候（约10-20秒）…',
    type: 'info',
    duration: 0,
    showClose: false,
  })
  try {
    const res = await settlementsApi.sendEmail(id)
    loadingMsg.close()
    if (res.sent > 0) {
      ElMessage.success(`✅ 邮件已成功发送给 ${res.sent} 位联系人`)
    } else {
      ElMessage.warning(res.error || '没有可用的邮件联系人，请在通知号码管理中填写邮箱')
    }
  } catch (e) {
    loadingMsg.close()
    ElMessage.error(e.message || '邮件发送失败')
  } finally {
    emailingId.value = ''
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

// 离开页面时重置所有状态，防止 loading mask / overlay 残留拦截点击
onBeforeUnmount(() => {
  loading.value = false
  creating.value = false
  confirming.value = false
  createDialog.value = false
  confirmDialog.value = false
  batchLoading.invoice = false
  batchLoading.detail = false
  yearLoading.invoice = false
  yearLoading.detail = false
  downloadingId.value = ''
  notifyingId.value = null
  emailingId.value = ''
  downloadProgress.show = false
})

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
