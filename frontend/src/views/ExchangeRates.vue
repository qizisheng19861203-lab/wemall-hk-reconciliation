<template>
  <div>
    <div class="page-header" style="display:flex;justify-content:space-between;align-items:center">
      <div><h2>汇率管理</h2><p>港币/人民币汇率，每日更新</p></div>
      <div style="display:flex;gap:8px" v-if="auth.isAdmin">
        <el-button @click="fetchToday" :loading="fetching">获取今日汇率</el-button>
        <el-button type="primary" @click="dialog = true">手动录入</el-button>
      </div>
    </div>
    <el-card shadow="never">
      <el-table :data="rates" v-loading="loading" stripe>
        <el-table-column prop="date" label="日期" width="130" />
        <el-table-column label="1 HKD → CNY" width="160" align="center">
          <template #default="{ row }"><strong>{{ row.hkd_to_cny }}</strong></template>
        </el-table-column>
        <el-table-column label="1 CNY → HKD" width="160" align="center">
          <template #default="{ row }">{{ row.cny_to_hkd }}</template>
        </el-table-column>
        <el-table-column label="来源" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.source === 'api' ? 'success' : 'info'">{{ row.source }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialog" title="手动录入汇率" width="380px" destroy-on-close>
      <el-form :model="form" label-width="140px">
        <el-form-item label="日期"><el-date-picker v-model="form.date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="1 HKD = ? CNY"><el-input-number v-model="form.hkd_to_cny" :precision="4" :min="0" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="save" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { rates as ratesApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import dayjs from 'dayjs'

const auth = useAuthStore()
const rates = ref([])
const loading = ref(false)
const fetching = ref(false)
const saving = ref(false)
const dialog = ref(false)
const form = reactive({ date: dayjs().format('YYYY-MM-DD'), hkd_to_cny: 0.9 })

async function load() {
  loading.value = true
  try { rates.value = await ratesApi.list() }
  finally { loading.value = false }
}

async function fetchToday() {
  fetching.value = true
  try {
    const r = await ratesApi.fetchToday()
    ElMessage.success(`今日汇率已更新：1 HKD = ${r.hkd_to_cny} CNY`)
    load()
  } catch (e) { ElMessage.error(e.message) }
  finally { fetching.value = false }
}

async function save() {
  saving.value = true
  try {
    await ratesApi.create(form)
    ElMessage.success('保存成功')
    dialog.value = false
    load()
  } catch (e) { ElMessage.error(e.message) }
  finally { saving.value = false }
}

onBeforeUnmount(() => { loading.value = false; saving.value = false; dialog.value = false })
onMounted(load)
</script>
