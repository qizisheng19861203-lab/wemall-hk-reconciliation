<template>
  <div>
    <!-- 顶部未结算金额 -->
    <el-card shadow="never" style="margin-bottom:16px;background:#fff7e6;border-color:#ffd591">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">
        <div style="display:flex;align-items:center;gap:24px">
          <div>
            <div style="font-size:13px;color:#8c6d00;margin-bottom:4px">本月未结算金额</div>
            <div style="font-size:28px;font-weight:700;color:#d46b08">
              ¥{{ stats.unsettled_rmb.toFixed(2) }}
            </div>
          </div>
          <div style="border-left:1px solid #ffd591;padding-left:24px">
            <div style="font-size:13px;color:#8c6d00;margin-bottom:4px">本月订单总额</div>
            <div style="font-size:20px;font-weight:600;color:#595959">¥{{ stats.total_supply_rmb.toFixed(2) }}</div>
          </div>
          <div style="border-left:1px solid #ffd591;padding-left:24px">
            <div style="font-size:13px;color:#8c6d00;margin-bottom:4px">订单数</div>
            <div style="font-size:20px;font-weight:600;color:#595959">{{ stats.total_orders }}</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-size:12px;color:#aaa">{{ lastRefreshText }}</span>
          <el-button size="small" @click="refreshStats" :loading="statsLoading">刷新</el-button>
        </div>
      </div>
    </el-card>

    <!-- 快速结算区间选择 -->
    <el-card shadow="never" style="margin-bottom:16px">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <span style="font-size:13px;color:#606266;font-weight:500">快速选择：</span>
        <el-button-group>
          <el-button size="small" :type="quickMode==='month' ? 'primary' : ''" @click="setQuickRange('month')">本月</el-button>
          <el-button size="small" :type="quickMode==='lastMonth' ? 'primary' : ''" @click="setQuickRange('lastMonth')">上月</el-button>
          <el-button size="small" :type="quickMode==='firstHalf' ? 'primary' : ''" @click="setQuickRange('firstHalf')">本月1-15号</el-button>
          <el-button size="small" :type="quickMode==='secondHalf' ? 'primary' : ''" @click="setQuickRange('secondHalf')">本月16-月底</el-button>
          <el-button size="small" :type="quickMode==='lastFirstHalf' ? 'primary' : ''" @click="setQuickRange('lastFirstHalf')">上月1-15号</el-button>
          <el-button size="small" :type="quickMode==='lastSecondHalf' ? 'primary' : ''" @click="setQuickRange('lastSecondHalf')">上月16-月底</el-button>
        </el-button-group>
        <el-date-picker v-model="filter.monthPicker" type="month" placeholder="按月选择"
          style="width:140px" @change="onMonthPick" />
        <el-date-picker v-model="filter.dateRange" type="daterange" range-separator="~"
          start-placeholder="自定义开始" end-placeholder="自定义结束"
          value-format="YYYY-MM-DDTHH:mm:ss" style="width:280px" @change="onDateRangeChange" />
      </div>
    </el-card>

    <!-- 筛选 -->
    <el-card shadow="never" style="margin-bottom:16px">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
        <el-form inline :model="filter" style="margin:0">
          <el-form-item label="发货状态" style="margin-bottom:0">
            <el-select v-model="filter.shipping_status" clearable placeholder="全部" style="width:120px">
              <el-option label="待发货" value="pending" />
              <el-option label="已发货" value="shipped" />
              <el-option label="已签收" value="delivered" />
              <el-option label="已退货" value="returned" />
            </el-select>
          </el-form-item>
          <el-form-item label="是否退款" style="margin-bottom:0">
            <el-select v-model="filter.is_refunded" clearable placeholder="全部" style="width:100px">
              <el-option label="正常" :value="false" />
              <el-option label="已退款" :value="true" />
            </el-select>
          </el-form-item>
          <el-form-item style="margin-bottom:0">
            <el-checkbox v-model="filter.unsettled_only">仅未结算</el-checkbox>
          </el-form-item>
          <el-form-item style="margin-bottom:0">
            <el-input v-model="filter.keyword" placeholder="订单号/买家" clearable style="width:160px" />
          </el-form-item>
          <el-form-item style="margin-bottom:0">
            <el-button type="primary" @click="doSearch">搜索</el-button>
            <el-button @click="resetFilter">重置</el-button>
          </el-form-item>
        </el-form>
        <div style="display:flex;gap:8px" v-if="auth.isAdminOrOperator">
          <el-select v-model="syncDays" style="width:110px">
            <el-option label="最近7天" :value="7" />
            <el-option label="最近15天" :value="15" />
            <el-option label="最近30天" :value="30" />
            <el-option label="最近60天" :value="60" />
            <el-option label="最近90天" :value="90" />
          </el-select>
          <el-button @click="syncOrders" :loading="syncing">同步微盟订单</el-button>
        </div>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table :data="flatRows" v-loading="loading" stripe :span-method="spanMethod" border>
        <el-table-column prop="wemall_order_id" label="订单号" width="165" />
        <el-table-column label="下单日期" width="100">
          <template #default="{ row }">{{ row.order_date?.slice(0,10) }}</template>
        </el-table-column>
        <el-table-column label="商品名称" min-width="220">
          <template #default="{ row }">
            <span style="font-size:12px">{{ row._item.product_name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="数量" width="55" align="center">
          <template #default="{ row }">{{ row._item.quantity }}</template>
        </el-table-column>
        <el-table-column label="供货单价(RMB)" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row._item.supply_price" style="color:#409EFF">¥{{ Number(row._item.supply_price).toFixed(2) }}</span>
            <el-tag v-else type="danger" size="small">待录价</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="供货小计(RMB)" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row._item.supply_subtotal" :class="{ 'text-red': row.is_refunded }">
              ¥{{ Number(row._item.supply_subtotal).toFixed(2) }}
            </span>
            <span v-else style="color:#C0C4CC">-</span>
          </template>
        </el-table-column>
        <el-table-column label="发货状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType[row.shipping_status]" size="small">{{ statusLabel[row.shipping_status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="退款" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_refunded" type="danger" size="small">¥{{ row.refund_amount }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="结算" width="75" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.settlement_id" type="success" size="small">已结算</el-tag>
            <el-tag v-else type="info" size="small">未结算</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="70" fixed="right" v-if="auth.isAdminOrOperator">
          <template #default="{ row }">
            <el-button size="small" link @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top:16px;text-align:right">
        <el-pagination v-model:current-page="page" :page-size="pageSize"
          :total="total" layout="total, prev, pager, next" @current-change="loadOrders" />
      </div>
    </el-card>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editDialog" title="编辑订单" width="500px">
      <el-form :model="editForm" label-width="90px">
        <el-form-item label="发货状态">
          <el-select v-model="editForm.shipping_status">
            <el-option label="待发货" value="pending" />
            <el-option label="已发货" value="shipped" />
            <el-option label="已签收" value="delivered" />
            <el-option label="已退货" value="returned" />
          </el-select>
        </el-form-item>
        <el-form-item label="快递单号">
          <el-input v-model="editForm.tracking_number" />
        </el-form-item>
        <el-form-item label="是否退款">
          <el-switch v-model="editForm.is_refunded" />
        </el-form-item>
        <el-form-item label="退款金额" v-if="editForm.is_refunded">
          <el-input-number v-model="editForm.refund_amount" :precision="2" :min="0" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.notes" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" @click="saveEdit" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { orders as ordersApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const orders = ref([])
const loading = ref(false)
const syncing = ref(false)
const syncDays = ref(7)
const saving = ref(false)
const page = ref(1)
const pageSize = 50
const total = ref(0)
const editDialog = ref(false)
const editForm = reactive({})
const editingId = ref(null)
const statsLoading = ref(false)
const lastRefreshTime = ref(null)
const quickMode = ref('month')

const stats = reactive({ unsettled_rmb: 0, total_supply_rmb: 0, total_orders: 0 })

const filter = reactive({
  dateRange: null,
  monthPicker: null,
  shipping_status: null,
  is_refunded: null,
  unsettled_only: false,
  keyword: '',
})

const statusLabel = { pending: '待发货', shipped: '已发货', delivered: '已签收', returned: '已退货' }
const statusType = { pending: 'warning', shipped: 'primary', delivered: 'success', returned: 'danger' }

const lastRefreshText = computed(() => {
  if (!lastRefreshTime.value) return ''
  const d = lastRefreshTime.value
  return `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')} 更新`
})

function toLocalISO(d) {
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function currentMonthRange() {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), 1)
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59)
  return [toLocalISO(start), toLocalISO(end)]
}

function setQuickRange(mode) {
  quickMode.value = mode
  const now = new Date()
  let start, end

  if (mode === 'month') {
    start = new Date(now.getFullYear(), now.getMonth(), 1)
    end = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59)
  } else if (mode === 'lastMonth') {
    start = new Date(now.getFullYear(), now.getMonth() - 1, 1)
    end = new Date(now.getFullYear(), now.getMonth(), 0, 23, 59, 59)
  } else if (mode === 'firstHalf') {
    // 本月1-15号
    start = new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 0)
    end = new Date(now.getFullYear(), now.getMonth(), 15, 23, 59, 59)
  } else if (mode === 'secondHalf') {
    // 本月16-月底
    start = new Date(now.getFullYear(), now.getMonth(), 16, 0, 0, 0)
    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()
    end = new Date(now.getFullYear(), now.getMonth(), lastDay, 23, 59, 59)
  } else if (mode === 'lastFirstHalf') {
    // 上月1-15号
    const lastMonth = now.getMonth() - 1
    const lastYear = lastMonth < 0 ? now.getFullYear() - 1 : now.getFullYear()
    const month = lastMonth < 0 ? 11 : lastMonth
    start = new Date(lastYear, month, 1, 0, 0, 0)
    end = new Date(lastYear, month, 15, 23, 59, 59)
  } else if (mode === 'lastSecondHalf') {
    // 上月16-月底
    const lastMonth = now.getMonth() - 1
    const lastYear = lastMonth < 0 ? now.getFullYear() - 1 : now.getFullYear()
    const month = lastMonth < 0 ? 11 : lastMonth
    const lastDay = new Date(lastYear, month + 1, 0).getDate()
    start = new Date(lastYear, month, 16, 0, 0, 0)
    end = new Date(lastYear, month, lastDay, 23, 59, 59)
  }

  filter.dateRange = [toLocalISO(start), toLocalISO(end)]
  filter.monthPicker = null
  page.value = 1
  loadOrders()
  loadStats()
}

function onMonthPick(val) {
  if (!val) return
  quickMode.value = ''
  const d = new Date(val)
  const start = new Date(d.getFullYear(), d.getMonth(), 1)
  const end = new Date(d.getFullYear(), d.getMonth() + 1, 0, 23, 59, 59)
  filter.dateRange = [toLocalISO(start), toLocalISO(end)]
  page.value = 1
  loadOrders()
  loadStats()
}

function onDateRangeChange() {
  quickMode.value = ''
  filter.monthPicker = null
  page.value = 1
  loadOrders()
  loadStats()
}

const flatRows = computed(() => {
  const rows = []
  for (const order of orders.value) {
    const items = order.items?.length ? order.items : [{ product_name: '(无商品)', quantity: 0, supply_price: null, supply_subtotal: null, id: 0 }]
    items.forEach((item, idx) => {
      rows.push({ ...order, _item: item, _itemIndex: idx, _itemCount: items.length })
    })
  }
  return rows
})

const MERGE_COLS = [0, 1, 6, 7, 8, 9]
function spanMethod({ rowIndex, columnIndex }) {
  if (!MERGE_COLS.includes(columnIndex)) return [1, 1]
  const row = flatRows.value[rowIndex]
  if (row._itemIndex === 0) return [row._itemCount, 1]
  return [0, 0]
}

async function loadOrders() {
  loading.value = true
  try {
    const params = {
      skip: (page.value - 1) * pageSize,
      limit: pageSize,
      shipping_status: filter.shipping_status || undefined,
      is_refunded: filter.is_refunded ?? undefined,
      unsettled_only: filter.unsettled_only || undefined,
      keyword: filter.keyword || undefined,
    }
    if (filter.dateRange?.[0]) params.start_date = filter.dateRange[0]
    if (filter.dateRange?.[1]) params.end_date = filter.dateRange[1]
    const res = await ordersApi.list(params)
    orders.value = res
    total.value = res.length < pageSize ? (page.value - 1) * pageSize + res.length : page.value * pageSize + 1
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  statsLoading.value = true
  try {
    const range = currentMonthRange()
    const res = await ordersApi.stats({ start_date: range[0], end_date: range[1] })
    stats.unsettled_rmb = res.unsettled_rmb ?? 0
    stats.total_supply_rmb = res.total_supply_rmb ?? 0
    stats.total_orders = res.total_orders ?? 0
    lastRefreshTime.value = new Date()
  } finally {
    statsLoading.value = false
  }
}

async function refreshStats() {
  await loadStats()
  await loadOrders()
}

function doSearch() {
  page.value = 1
  loadOrders()
}

function resetFilter() {
  const range = currentMonthRange()
  Object.assign(filter, {
    dateRange: range,
    monthPicker: null,
    shipping_status: null,
    is_refunded: null,
    unsettled_only: false,
    keyword: '',
  })
  quickMode.value = 'month'
  page.value = 1
  loadOrders()
  loadStats()
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(editForm, {
    shipping_status: row.shipping_status,
    tracking_number: row.tracking_number || '',
    is_refunded: row.is_refunded,
    refund_amount: row.refund_amount,
    notes: row.notes || '',
  })
  editDialog.value = true
}

async function saveEdit() {
  saving.value = true
  try {
    await ordersApi.update(editingId.value, editForm)
    ElMessage.success('保存成功')
    editDialog.value = false
    loadOrders()
    loadStats()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

async function syncOrders() {
  syncing.value = true
  try {
    const endDate = new Date()
    const startDate = new Date(endDate - syncDays.value * 86400 * 1000)
    const res = await ordersApi.syncWemall({
      start_date: startDate.toISOString(),
      end_date: endDate.toISOString(),
    })
    ElMessage.success(`同步完成：新增${res.created}，更新${res.updated}，跳过${res.skipped}`)
    loadOrders()
    loadStats()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    syncing.value = false
  }
}

let autoRefreshTimer = null

onMounted(() => {
  const range = currentMonthRange()
  filter.dateRange = range
  loadOrders()
  loadStats()
  autoRefreshTimer = setInterval(() => {
    loadStats()
    loadOrders()
  }, 10 * 60 * 1000)
})

onUnmounted(() => {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer)
})
</script>

<style scoped>
.text-red { color: #F56C6C; }
</style>
