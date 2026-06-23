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
          <div v-if="stats.total_refund_rmb > 0" style="border-left:1px solid #ffd591;padding-left:24px">
            <div style="font-size:13px;color:#8c6d00;margin-bottom:4px">已退款</div>
            <div style="font-size:20px;font-weight:600;color:#F56C6C">¥{{ stats.total_refund_rmb.toFixed(2) }}</div>
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
          style="width:140px" @change="onMonthPick" :teleported="true" />
        <el-date-picker v-model="filter.dateRange" type="daterange" range-separator="~"
          start-placeholder="自定义开始" end-placeholder="自定义结束"
          value-format="YYYY-MM-DDTHH:mm:ss" style="width:280px" @change="onDateRangeChange"
          :teleported="true" />
      </div>

      <!-- 区间结算概览 -->
      <div v-if="periodStats.loaded" style="margin-top:12px;padding:10px 14px;background:#f5f7fa;border-radius:6px;display:flex;align-items:center;gap:20px;flex-wrap:wrap">
        <span style="font-size:12px;color:#909399;font-weight:500">{{ periodRangeLabel }} 区间：</span>
        <div style="display:flex;align-items:center;gap:6px">
          <span style="font-size:12px;color:#606266">供货总额</span>
          <span style="font-size:15px;font-weight:700;color:#303133">¥{{ periodStats.total_supply_rmb.toFixed(2) }}</span>
        </div>
        <div style="width:1px;height:20px;background:#dcdfe6"></div>
        <div style="display:flex;align-items:center;gap:6px">
          <el-tag type="success" size="small">已收款</el-tag>
          <span style="font-size:14px;font-weight:600;color:#67c23a">¥{{ periodStats.confirmed_settled_rmb.toFixed(2) }}</span>
        </div>
        <div v-if="periodStats.pending_settlement_rmb > 0" style="display:flex;align-items:center;gap:6px">
          <el-tag type="primary" size="small">结算中</el-tag>
          <span style="font-size:14px;font-weight:600;color:#409EFF">¥{{ periodStats.pending_settlement_rmb.toFixed(2) }}</span>
        </div>
        <div style="display:flex;align-items:center;gap:6px">
          <el-tag type="warning" size="small">未结算</el-tag>
          <span style="font-size:14px;font-weight:600;color:#e6a23c">¥{{ periodStats.unsettled_rmb.toFixed(2) }}</span>
        </div>
        <div style="width:1px;height:20px;background:#dcdfe6"></div>
        <div style="display:flex;align-items:center;gap:6px">
          <span style="font-size:12px;color:#909399">订单数</span>
          <span style="font-size:14px;font-weight:600;color:#606266">{{ periodStats.total_orders }}</span>
        </div>
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
            <el-tooltip content="隐藏所有订单条目都是「非供货」的订单（分销商独有商品，不在我们供货范围内）" placement="top">
              <el-checkbox v-model="filter.supply_only">只看我方供货</el-checkbox>
            </el-tooltip>
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
      <!-- 手动 loading 层：v-if 确保加载完成后立刻从 DOM 消失，不留透明遮罩残留 -->
      <div style="position:relative; min-height:80px;">
      <div v-if="loading" style="position:absolute;inset:0;z-index:10;background:rgba(255,255,255,0.65);display:flex;align-items:center;justify-content:center;border-radius:4px;">
        <el-icon class="is-loading" :size="28" color="#409EFF"><Loading /></el-icon>
      </div>
      <el-table :data="flatRows" stripe :span-method="spanMethod" border size="small" style="font-size:13px">
        <el-table-column label="订单号 / 下单时间" width="150">
          <template #default="{ row }">
            <div style="font-size:12px;line-height:1.35;color:#475569;font-variant-numeric:tabular-nums;word-break:break-all">{{ row.wemall_order_id }}</div>
            <div style="font-size:11px;color:#94a3b8;margin-top:1px">{{ fmtBJ(row.order_date) }}</div>
            <el-tag v-if="row.is_test" type="info" size="small" style="margin-top:2px">测试</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="收件人" width="100">
          <template #default="{ row }">
            <div style="line-height:1.3">
              <div style="font-size:13px;color:#1e293b">{{ row.buyer_name || '-' }}</div>
              <div style="font-size:11px;color:#94a3b8">{{ row.buyer_phone || '' }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="收货地址" width="155">
          <template #default="{ row }">
            <span style="font-size:12px;color:#64748b;line-height:1.4;white-space:normal;word-break:break-all">{{ row.shipping_address || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="商品" min-width="300">
          <template #default="{ row }">
            <div style="display:flex;align-items:center;gap:6px">
              <el-image v-if="row._item.image_url" :src="row._item.image_url" lazy
                :preview-src-list="[row._item.image_url]" preview-teleported fit="cover"
                style="width:28px;height:28px;border-radius:4px;flex-shrink:0" />
              <div v-else style="width:28px;height:28px;border-radius:4px;background:#f0f2f5;flex-shrink:0" />
              <span style="font-size:12px;line-height:1.25">{{ row._item.product_name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="数量" width="48" align="center">
          <template #default="{ row }"><span style="font-size:13px;color:#475569">{{ row._item.quantity }}</span></template>
        </el-table-column>
        <el-table-column label="供货单价" width="96" align="right">
          <template #default="{ row }">
            <span v-if="row._item.supply_price" style="font-size:12px;color:#94a3b8">¥{{ Number(row._item.supply_price).toFixed(2) }}</span>
            <!-- product_id=null → 非供货（灰）；≠null 但无供货价 → 待录价（红）-->
            <el-tag v-else-if="row._item.product_id == null" type="info" size="small">非供货</el-tag>
            <el-tag v-else type="danger" size="small">待录价</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="供货小计" width="128" align="right">
          <template #default="{ row }">
            <span v-if="row._item.supply_subtotal"
              :style="{ fontSize:'15.5px', fontWeight:700, color: row.is_refunded ? '#ef4444' : '#1f6feb', fontVariantNumeric:'tabular-nums', textDecoration: row.is_refunded ? 'line-through' : 'none' }">
              <span style="font-size:11px;font-weight:500;opacity:0.65">¥</span>{{ Number(row._item.supply_subtotal).toFixed(2) }}
            </span>
            <span v-if="row.is_refunded && row._item.supply_subtotal" style="font-size:10px;color:#ef4444;margin-left:3px">退款</span>
            <span v-else-if="!row._item.supply_subtotal" style="color:#C0C4CC">-</span>
          </template>
        </el-table-column>
        <el-table-column label="客户支付" width="96" align="right">
          <template #default="{ row }">
            <span v-if="row._item.retail_price != null && Number(row._item.retail_price) > 0" style="font-size:12px;color:#94a3b8">
              ¥{{ (Number(row._item.retail_price) * row._item.quantity).toFixed(2) }}
            </span>
            <span v-else style="color:#C0C4CC">-</span>
          </template>
        </el-table-column>
        <el-table-column label="退款" width="72" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_refunded" type="danger" size="small" effect="light">¥{{ row.refund_amount }}</el-tag>
            <span v-else style="color:#C0C4CC">-</span>
          </template>
        </el-table-column>
        <el-table-column label="结算" width="78" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.settlement_id" type="success" size="small" effect="light" round>已结算</el-tag>
            <el-tag v-else type="warning" size="small" effect="light" round>未结算</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="58" align="center" v-if="auth.isAdminOrOperator">
          <template #default="{ row }">
            <el-button size="small" link @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
      </div><!-- end loading wrapper -->
      <div style="margin-top:16px;text-align:right">
        <el-pagination v-model:current-page="page" :page-size="pageSize"
          :total="total" layout="total, prev, pager, next" @current-change="loadOrders" />
      </div>
    </el-card>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editDialog" title="编辑订单" width="600px" destroy-on-close :teleported="false">
      <el-form :model="editForm" label-width="90px">
        <el-form-item label="订单号">
          <span style="font-weight:600">{{ editForm._order_id }}</span>
        </el-form-item>
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
        <el-form-item label="订单商品">
          <div style="width:100%;border:1px solid #ebeef5;border-radius:4px;overflow:hidden">
            <div v-for="item in editForm._items" :key="item.id"
              style="padding:8px 12px;border-bottom:1px solid #f0f0f0;display:flex;align-items:center;gap:8px;justify-content:space-between">
              <div style="flex:1;min-width:0">
                <div style="font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ item.product_name }}</div>
                <div style="font-size:11px;color:#909399">x{{ item.quantity }} | 供货价: {{ item.supply_price ? `¥${item.supply_price}` : '无' }}</div>
              </div>
              <el-tag v-if="item.product_id == null" type="info" size="small">非供货</el-tag>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="退款">
          <el-switch v-model="editForm.is_refunded" />
          <span v-if="editForm.is_refunded" style="margin-left:8px;font-size:12px;color:#F56C6C">已退款</span>
        </el-form-item>
        <el-form-item label="退款金额" v-if="editForm.is_refunded">
          <el-input-number v-model="editForm.refund_amount" :precision="2" :min="0" />
          <el-button size="small" style="margin-left:8px" @click="setFullRefund">全额退款</el-button>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.notes" type="textarea" />
        </el-form-item>
        <el-form-item label="测试订单">
          <el-switch v-model="editForm.is_test" />
          <span style="font-size:12px;color:#909399;margin-left:8px">标记后不计入结算金额</span>
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
import { Loading } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { orders as ordersApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

// order_date 是 UTC 朴素时间，转北京(Asia/Shanghai)显示「MM-DD HH:mm」
function fmtBJ(s) {
  if (!s) return '-'
  const d = new Date(/[Z+]/.test(s) ? s : s + 'Z')
  if (isNaN(d)) return String(s).slice(0, 16).replace('T', ' ')
  const p = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(d).reduce((a, x) => (a[x.type] = x.value, a), {})
  return `${p.month}-${p.day} ${p.hour}:${p.minute}`
}

const orders = ref([])
const loading = ref(false)
const syncing = ref(false)
const markingTest = ref(false)
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

const stats = reactive({ unsettled_rmb: 0, total_supply_rmb: 0, total_orders: 0, total_refund_rmb: 0 })
const periodStats = reactive({ loaded: false, total_supply_rmb: 0, confirmed_settled_rmb: 0, pending_settlement_rmb: 0, unsettled_rmb: 0, total_orders: 0 })

const periodRangeLabel = computed(() => {
  const r = filter.dateRange
  if (!r?.[0] || !r?.[1]) return ''
  const s = r[0].slice(0, 10)
  const e = r[1].slice(0, 10)
  return s === e ? s : `${s} ~ ${e}`
})

const filter = reactive({
  dateRange: null,
  monthPicker: null,
  shipping_status: null,
  is_refunded: null,
  unsettled_only: false,
  supply_only: true,    // 只看有我方供货商品的订单（默认开启）
  keyword: '',
})

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
  loadPeriodStats()
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
  loadPeriodStats()
}

function onDateRangeChange() {
  quickMode.value = ''
  filter.monthPicker = null
  page.value = 1
  loadOrders()
  loadStats()
  loadPeriodStats()
}

const flatRows = computed(() => {
  const rows = []
  for (const order of orders.value) {
    const items = order.items?.length ? order.items : [{ product_name: '(无商品)', quantity: 0, supply_price: null, supply_subtotal: null, product_id: null, id: 0 }]

    // 「只看我方供货」过滤：过滤非供货条目，整单无供货时跳过
    const displayItems = filter.supply_only
      ? items.filter(it => it.supply_price != null || it.product_id != null)
      : items
    if (displayItems.length === 0) continue

    displayItems.forEach((item, idx) => {
      rows.push({ ...order, _item: item, _itemIndex: idx, _itemCount: displayItems.length })
    })
  }
  return rows
})

// 列索引(订单号与时间已合并为一列): 订单号/时间[0] 收件人[1] 地址[2] 商品[3] 数量[4] 供货单价[5] 供货小计[6] 客户支付[7] 退款[8] 结算[9] 操作[10]
// 合并整订单行的列（跨商品条目合并）：订单号/时间、收件人、地址、退款、结算、操作
const MERGE_COLS = [0, 1, 2, 8, 9, 10]
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
    stats.total_refund_rmb = res.total_refund_rmb ?? 0
    lastRefreshTime.value = new Date()
  } finally {
    statsLoading.value = false
  }
}

async function loadPeriodStats() {
  if (!filter.dateRange?.[0] || !filter.dateRange?.[1]) {
    periodStats.loaded = false
    return
  }
  try {
    const res = await ordersApi.stats({ start_date: filter.dateRange[0], end_date: filter.dateRange[1] })
    periodStats.total_supply_rmb = res.total_supply_rmb ?? 0
    periodStats.unsettled_rmb = res.unsettled_rmb ?? 0
    periodStats.confirmed_settled_rmb = res.confirmed_settled_rmb ?? 0
    periodStats.pending_settlement_rmb = Math.max(0, res.pending_settlement_rmb ?? 0)
    periodStats.total_orders = res.total_orders ?? 0
    periodStats.loaded = true
  } catch (e) {
    periodStats.loaded = false
  }
}

async function refreshStats() {
  // 并行加载，别串行等（原来串行 ~3 倍耗时）
  await Promise.all([loadStats(), loadOrders(), loadPeriodStats()])
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
    supply_only: false,
    keyword: '',
  })
  quickMode.value = 'month'
  page.value = 1
  loadOrders()
  loadStats()
  loadPeriodStats()
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(editForm, {
    _order_id: row.wemall_order_id,
    _items: row.items || [],
    shipping_status: row.shipping_status,
    tracking_number: row.tracking_number || '',
    is_refunded: row.is_refunded,
    refund_amount: row.refund_amount,
    is_test: row.is_test || false,
    notes: row.notes || '',
  })
  editDialog.value = true
}

function setFullRefund() {
  const items = editForm._items || []
  const total = items.reduce((sum, item) => sum + (Number(item.supply_subtotal) || 0), 0)
  editForm.refund_amount = Number(total.toFixed(2))
}

async function saveEdit() {
  saving.value = true
  try {
    await ordersApi.update(editingId.value, editForm)
    ElMessage.success('保存成功')
    editDialog.value = false
    loadOrders()
    loadStats()
    loadPeriodStats()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

async function bulkMarkTest() {
  try {
    await ElMessageBox.confirm('将当前店铺所有未结算订单全部标为「测试」，不计入结算统计。确定继续？', '批量标记测试', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch { return }
  markingTest.value = true
  try {
    const res = await ordersApi.bulkMarkTest()
    ElMessage.success(`已将 ${res.updated} 条订单标记为测试`)
    loadOrders()
    loadStats()
    loadPeriodStats()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    markingTest.value = false
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
    loadPeriodStats()
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
  loadPeriodStats()
  autoRefreshTimer = setInterval(() => {
    loadStats()
    loadOrders()
    loadPeriodStats()
  }, 10 * 60 * 1000)
})

onUnmounted(() => {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer)
  // 重置 loading 状态，防止 v-loading mask 残留
  loading.value = false
  editDialog.value = false
})
</script>

<style scoped>
.text-red { color: #F56C6C; }
</style>
