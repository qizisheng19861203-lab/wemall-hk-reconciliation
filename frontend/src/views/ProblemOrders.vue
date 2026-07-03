<template>
  <div>
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:16px">
      <div>
        <h2 style="margin:0;font-size:20px;font-weight:700;color:#b91c1c">⚠️ 问题订单（已发货但退款）</h2>
        <div style="font-size:12px;color:#94a3b8;margin-top:4px">
          <b>真有物流单号（确实发货了）</b>、客户却退了款的订单。仅供留意/追回参考，<b>不计入结算供货款</b>。
          （判断以打印系统的物流单号为准；"货没真发就退款"的不在此列，退了无损失。）
        </div>
        <div v-if="loaded && !data.waybill_source_ok" style="font-size:12px;color:#dc2626;margin-top:4px">
          ⚠️ 暂时连不上打印系统的物流单号数据，当前列表可能不完整，请稍后刷新。
        </div>
      </div>
      <el-button size="small" @click="load" :loading="loading">刷新</el-button>
    </div>

    <el-card shadow="never" style="margin-bottom:16px;background:#fef2f2;border-color:#fecaca">
      <div style="display:flex;align-items:center;gap:32px;flex-wrap:wrap">
        <div>
          <div style="font-size:12px;color:#dc2626;margin-bottom:2px">问题订单数</div>
          <div style="font-size:24px;font-weight:700;color:#991b1b">{{ data.total }}</div>
        </div>
        <div style="border-left:1px solid #fecaca;padding-left:32px">
          <div style="font-size:12px;color:#dc2626;margin-bottom:2px">涉及我方供货值（参考）</div>
          <div style="font-size:24px;font-weight:700;color:#991b1b">¥{{ data.total_supply_rmb.toLocaleString() }}</div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table :data="data.orders" size="small" border v-loading="loading"
        :expand-row-keys="[]" row-key="wemall_order_id" style="width:100%">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div style="padding:8px 24px">
              <div v-for="(it, i) in row.items" :key="i" style="font-size:13px;padding:2px 0;color:#475569">
                • {{ it.name }} ×{{ it.qty }}
                <span v-if="it.supply_subtotal" style="color:#0f766e">（供货 ¥{{ it.supply_subtotal.toFixed(0) }}）</span>
                <span v-else style="color:#f59e0b">（非我方供货/待录价）</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="wemall_order_id" label="订单号" width="180" />
        <el-table-column prop="buyer_name" label="收件人" min-width="120" show-overflow-tooltip />
        <el-table-column prop="order_date" label="下单时间(北京)" width="150" />
        <el-table-column label="物流单号" width="180">
          <template #default="{ row }">
            <span style="font-family:monospace;font-size:12.5px;color:#0369a1">{{ row.waybill }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="item_count" label="商品项" width="70" align="center" />
        <el-table-column label="我方供货值" width="120" align="right">
          <template #default="{ row }">
            <span style="font-weight:600;color:#991b1b">¥{{ row.supply_rmb.toLocaleString() }}</span>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!loading && data.total === 0" style="text-align:center;color:#94a3b8;padding:24px">
        暂无问题订单 🎉
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { orders as ordersApi } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const loaded = ref(false)
const data = reactive({ total: 0, total_supply_rmb: 0, waybill_source_ok: true, orders: [] })

async function load() {
  loading.value = true
  try {
    const res = await ordersApi.problemRefunds()
    data.total = res.total ?? 0
    data.total_supply_rmb = res.total_supply_rmb ?? 0
    data.waybill_source_ok = res.waybill_source_ok !== false
    data.orders = res.orders || []
    loaded.value = true
  } catch (e) { ElMessage.error(e.message) }
  finally { loading.value = false }
}

onMounted(load)
onBeforeUnmount(() => { loading.value = false })
</script>
