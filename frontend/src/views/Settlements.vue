<template>
  <div>
    <div class="page-header" style="display:flex;justify-content:space-between;align-items:center">
      <div><h2>结算管理</h2></div>
      <el-button type="primary" @click="openCreate" v-if="auth.isAdmin">新建结算单</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="settlements" v-loading="loading" stripe>
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

    <!-- 新建结算 -->
    <el-dialog v-model="createDialog" title="新建结算单" width="600px">
      <el-alert type="info" :closable="false" style="margin-bottom:12px">
        将选中的未结算订单生成一张结算单，请先在订单页面筛选确认范围
      </el-alert>
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="账期开始"><el-date-picker v-model="createForm.period_start" type="datetime" /></el-form-item>
        <el-form-item label="账期结束"><el-date-picker v-model="createForm.period_end" type="datetime" /></el-form-item>
        <el-form-item label="汇率(HKD→RMB)">
          <el-input-number v-model="createForm.hkd_rate" :precision="4" :min="0.01" style="width:160px" />
          <el-button link @click="fetchTodayRate" style="margin-left:8px">获取今日汇率</el-button>
        </el-form-item>
        <el-form-item label="选择订单">
          <el-button @click="loadUnsettledOrders" :loading="loadingOrders">加载未结算订单</el-button>
          <span style="margin-left:8px;color:#909399">已选 {{ createForm.order_ids.length }} 笔</span>
        </el-form-item>
        <el-table v-if="unsettledOrders.length" :data="unsettledOrders" max-height="240"
          @selection-change="(rows) => createForm.order_ids = rows.map(r => r.id)">
          <el-table-column type="selection" width="44" />
          <el-table-column prop="wemall_order_id" label="订单号" width="150" />
          <el-table-column prop="order_date" label="日期" width="100" :formatter="r => r.order_date?.slice(0,10)" />
          <el-table-column label="供货小计" align="right">
            <template #default="{ row }">¥{{ row.items.reduce((s,i) => s+(i.supply_subtotal||0), 0).toFixed(2) }}</template>
          </el-table-column>
        </el-table>
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
const loadingOrders = ref(false)
const createDialog = ref(false)
const confirmDialog = ref(false)
const confirmingSettlement = ref(null)
const unsettledOrders = ref([])

const createForm = reactive({ period_start: null, period_end: null, hkd_rate: 0.9, order_ids: [], notes: '' })
const confirmForm = reactive({ actual_payment_hkd: 0, notes: '' })

const statusLabel = { pending: '待结算', notified: '已通知', settled: '已结清' }
const statusType = { pending: 'warning', notified: 'primary', settled: 'success' }

async function load() {
  loading.value = true
  try { settlements.value = await settlementsApi.list() }
  finally { loading.value = false }
}

async function fetchTodayRate() {
  try {
    const rate = await ratesApi.today()
    createForm.hkd_rate = Number(rate.hkd_to_cny)
    ElMessage.success(`已填入今日汇率：1 HKD = ${rate.hkd_to_cny} CNY`)
  } catch { ElMessage.warning('今日汇率未录入，请手动输入') }
}

async function loadUnsettledOrders() {
  loadingOrders.value = true
  try {
    unsettledOrders.value = await ordersApi.list({ unsettled_only: true, limit: 200 })
  } finally { loadingOrders.value = false }
}

async function createSettlement() {
  if (!createForm.period_start || !createForm.period_end) return ElMessage.warning('请选择账期')
  if (!createForm.order_ids.length) return ElMessage.warning('请选择订单')
  creating.value = true
  try {
    await settlementsApi.create({ ...createForm, period_start: new Date(createForm.period_start).toISOString(), period_end: new Date(createForm.period_end).toISOString() })
    ElMessage.success('结算单创建成功')
    createDialog.value = false
    load()
  } catch (e) { ElMessage.error(e.message) }
  finally { creating.value = false }
}

function openCreate() {
  unsettledOrders.value = []
  Object.assign(createForm, { period_start: null, period_end: null, hkd_rate: 0.9, order_ids: [], notes: '' })
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
  } catch (e) { ElMessage.error(e.message) }
  finally { confirming.value = false }
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
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message) }
}

onMounted(load)
</script>
