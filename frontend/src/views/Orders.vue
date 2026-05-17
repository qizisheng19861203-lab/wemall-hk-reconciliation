<template>
  <div>
    <div class="page-header" style="display:flex;justify-content:space-between;align-items:center">
      <div><h2>订单管理</h2></div>
      <div style="display:flex;gap:8px">
        <el-select v-model="syncDays" style="width:110px" v-if="auth.isAdminOrOperator">
          <el-option label="最近7天" :value="7" />
          <el-option label="最近15天" :value="15" />
          <el-option label="最近30天" :value="30" />
          <el-option label="最近60天" :value="60" />
          <el-option label="最近90天" :value="90" />
        </el-select>
        <el-button @click="syncOrders" :loading="syncing" v-if="auth.isAdminOrOperator">同步微盟订单</el-button>
      </div>
    </div>

    <!-- 筛选 -->
    <el-card shadow="never" style="margin-bottom:16px">
      <el-form inline :model="filter">
        <el-form-item label="日期范围">
          <el-date-picker v-model="filter.dateRange" type="daterange" range-separator="~"
            start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DDTHH:mm:ss" />
        </el-form-item>
        <el-form-item label="发货状态">
          <el-select v-model="filter.shipping_status" clearable placeholder="全部" style="width:120px">
            <el-option label="待发货" value="pending" />
            <el-option label="已发货" value="shipped" />
            <el-option label="已签收" value="delivered" />
            <el-option label="已退货" value="returned" />
          </el-select>
        </el-form-item>
        <el-form-item label="是否退款">
          <el-select v-model="filter.is_refunded" clearable placeholder="全部" style="width:100px">
            <el-option label="正常" :value="false" />
            <el-option label="已退款" :value="true" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="filter.unsettled_only">仅未结算</el-checkbox>
        </el-form-item>
        <el-form-item>
          <el-input v-model="filter.keyword" placeholder="订单号/买家" clearable style="width:160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadOrders">搜索</el-button>
          <el-button @click="resetFilter">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table :data="orders" v-loading="loading" stripe>
        <el-table-column prop="wemall_order_id" label="订单号" width="170" />
        <el-table-column prop="order_date" label="下单日期" width="120"
          :formatter="(r) => r.order_date?.slice(0,10)" />
        <el-table-column label="商品" min-width="200">
          <template #default="{ row }">
            <div v-for="item in row.items" :key="item.id" style="font-size:12px;line-height:1.6">
              {{ item.product_name }} × {{ item.quantity }}
              <span v-if="item.supply_price" style="color:#409EFF"> ¥{{ item.supply_price }}</span>
              <el-tag v-else size="small" type="warning">待录价</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="供货小计" width="110" align="right">
          <template #default="{ row }">
            <span :class="{ 'text-red': row.is_refunded }">
              ¥{{ row.items.reduce((s, i) => s + (i.supply_subtotal || 0), 0).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="发货状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType[row.shipping_status]" size="small">{{ statusLabel[row.shipping_status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="退款" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_refunded" type="danger" size="small">¥{{ row.refund_amount }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="结算" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.settlement_id" type="success" size="small">已结算</el-tag>
            <el-tag v-else type="info" size="small">未结算</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right" v-if="auth.isAdminOrOperator">
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
import { ref, reactive, onMounted } from 'vue'
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

const filter = reactive({ dateRange: null, shipping_status: null, is_refunded: null, unsettled_only: false, keyword: '' })

const statusLabel = { pending: '待发货', shipped: '已发货', delivered: '已签收', returned: '已退货' }
const statusType = { pending: 'warning', shipped: 'primary', delivered: 'success', returned: 'danger' }

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

function resetFilter() {
  Object.assign(filter, { dateRange: null, shipping_status: null, is_refunded: null, unsettled_only: false, keyword: '' })
  loadOrders()
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
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    syncing.value = false
  }
}

onMounted(loadOrders)
</script>

<style scoped>
.text-red { color: #F56C6C; }
</style>
