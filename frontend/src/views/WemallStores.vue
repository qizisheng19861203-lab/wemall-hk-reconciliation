<template>
  <div>
    <!-- 页头 -->
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
      <div>
        <h2 style="margin:0 0 4px 0; font-size:18px; font-weight:600;">微盟店铺配置</h2>
        <p style="margin:0; color:#909399; font-size:13px;">管理多个微盟开放平台凭证，切换后系统将使用该店铺的订单和商品数据</p>
      </div>
      <el-button type="primary" @click="openAdd" :icon="Plus">新增店铺</el-button>
    </div>

    <!-- 当前激活提示 -->
    <el-alert v-if="activeStore" type="success" :closable="false" style="margin-bottom:16px;">
      <template #title>
        <span>当前激活店铺：<strong>{{ activeStore.name }}</strong></span>
        <span v-if="activeStore.shop_id" style="margin-left:12px; color:#606266; font-size:13px;">
          Shop ID: {{ activeStore.shop_id }}
        </span>
      </template>
    </el-alert>

    <!-- 店铺列表 -->
    <el-table :data="stores" border stripe>
      <el-table-column label="店铺名称" prop="name" min-width="160">
        <template #default="{ row }">
          <div style="display:flex; align-items:center; gap:8px;">
            <el-tag v-if="row.is_active" type="success" size="small">激活</el-tag>
            <span :style="row.is_active ? 'font-weight:600' : ''">{{ row.name }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="Client ID" prop="client_id" min-width="200">
        <template #default="{ row }">
          <code style="font-size:12px; background:#f5f7fa; padding:2px 6px; border-radius:3px;">
            {{ row.client_id }}
          </code>
        </template>
      </el-table-column>
      <el-table-column label="Client Secret" prop="client_secret_masked" width="160">
        <template #default="{ row }">
          <code style="font-size:12px; color:#909399;">{{ row.client_secret_masked }}</code>
        </template>
      </el-table-column>
      <el-table-column label="Shop ID" prop="shop_id" width="140" />
      <el-table-column label="备注" prop="notes" min-width="140" show-overflow-tooltip />
      <el-table-column label="上线打印" width="100" align="center">
        <template #default="{ row }">
          <el-switch v-model="row.print_enabled" @change="togglePrint(row)" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="info" @click="testStore(row)" :loading="testingId === row.id">测试</el-button>
          <el-button
            size="small"
            type="success"
            :disabled="row.is_active"
            @click="activateStore(row)"
            :loading="activatingId === row.id"
          >
            {{ row.is_active ? '已激活' : '切换到此' }}
          </el-button>
          <el-button size="small" type="danger" :disabled="row.is_active" @click="deleteStore(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="formDialog"
      :title="editingId ? '编辑店铺配置' : '新增店铺配置'"
      width="520px"
      destroy-on-close
    >
      <el-form :model="form" label-width="110px" :rules="rules" ref="formRef">
        <el-form-item label="店铺名称" prop="name">
          <el-input v-model="form.name" placeholder="如：倍赛思甄选" />
        </el-form-item>
        <el-form-item label="Client ID" prop="client_id">
          <el-input v-model="form.client_id" placeholder="微盟开放平台 client_id" />
        </el-form-item>
        <el-form-item label="Client Secret" prop="client_secret">
          <el-input
            v-model="form.client_secret"
            :placeholder="editingId ? '留空则不修改' : '微盟开放平台 client_secret'"
            show-password
          />
        </el-form-item>
        <el-form-item label="Shop ID">
          <el-input v-model="form.shop_id" placeholder="可选，店铺 ID（部分接口需要）" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="可选，描述这个店铺" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formDialog = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>

    <!-- 测试结果弹窗 -->
    <el-dialog v-model="testDialog" title="连接测试结果" width="420px" destroy-on-close>
      <div v-if="testResult">
        <el-result
          :icon="testResult.ok ? 'success' : 'error'"
          :title="testResult.ok ? '连接成功' : '连接失败'"
        >
          <template #sub-title>
            <template v-if="testResult.ok">
              <p>Token：<code>{{ testResult.token_prefix }}</code></p>
              <p>组织 VID：<strong>{{ testResult.vid }}</strong></p>
              <p>组织名称：<strong>{{ testResult.org_name }}</strong></p>
            </template>
            <template v-else>
              <p style="color:#f56c6c;">{{ testResult.error }}</p>
            </template>
          </template>
        </el-result>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '@/api/http'

const stores = ref([])
const loading = ref(false)
const formDialog = ref(false)
const testDialog = ref(false)
const submitting = ref(false)
const testingId = ref(null)
const activatingId = ref(null)
const editingId = ref(null)
const testResult = ref(null)
const formRef = ref()

const form = reactive({
  name: '',
  client_id: '',
  client_secret: '',
  shop_id: '',
  notes: '',
})

const rules = {
  name: [{ required: true, message: '请输入店铺名称', trigger: 'blur' }],
  client_id: [{ required: true, message: '请输入 Client ID', trigger: 'blur' }],
  client_secret: [
    {
      validator: (rule, value, callback) => {
        if (!editingId.value && !value) callback(new Error('请输入 Client Secret'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

const activeStore = computed(() => stores.value.find(s => s.is_active))

async function loadStores() {
  loading.value = true
  try {
    const data = await http.get('/admin/wemall-stores')
    stores.value = data
  } catch (e) {
    ElMessage.error('加载失败：' + e.message)
  } finally {
    loading.value = false
  }
}

function openAdd() {
  editingId.value = null
  Object.assign(form, { name: '', client_id: '', client_secret: '', shop_id: '', notes: '' })
  formDialog.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    client_id: row.client_id,
    client_secret: '',  // 不回显 secret，留空则不修改
    shop_id: row.shop_id || '',
    notes: row.notes || '',
  })
  formDialog.value = true
}

async function submitForm() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload = {
      name: form.name,
      client_id: form.client_id,
      shop_id: form.shop_id || null,
      notes: form.notes || null,
    }
    // 编辑时 secret 留空则不传（后端 Optional）
    if (form.client_secret) payload.client_secret = form.client_secret
    else if (!editingId.value) payload.client_secret = ''

    if (editingId.value) {
      await http.put(`/admin/wemall-stores/${editingId.value}`, payload)
      ElMessage.success('已保存')
    } else {
      payload.client_secret = form.client_secret
      await http.post('/admin/wemall-stores', payload)
      ElMessage.success('新增成功')
    }
    formDialog.value = false
    await loadStores()
  } catch (e) {
    ElMessage.error('操作失败：' + e.message)
  } finally {
    submitting.value = false
  }
}

async function testStore(row) {
  testingId.value = row.id
  testResult.value = null
  try {
    const data = await http.post(`/admin/wemall-stores/${row.id}/test`)
    testResult.value = data
    testDialog.value = true
  } catch (e) {
    ElMessage.error('测试请求失败：' + e.message)
  } finally {
    testingId.value = null
  }
}

async function activateStore(row) {
  try {
    await ElMessageBox.confirm(
      `确认将系统切换到「${row.name}」的订单数据？\n系统将立即使用新店铺的凭证进行订单同步。`,
      '切换确认',
      { type: 'warning', confirmButtonText: '确认切换', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  activatingId.value = row.id
  try {
    const data = await http.post(`/admin/wemall-stores/${row.id}/activate`)
    ElMessage.success(`已切换到「${data.active_store.name}」`)
    await loadStores()
  } catch (e) {
    ElMessage.error('切换失败：' + e.message)
  } finally {
    activatingId.value = null
  }
}

async function togglePrint(row) {
  try {
    const data = await http.post(`/admin/wemall-stores/${row.id}/toggle-print`)
    ElMessage.success(`${row.name} 打印已${data.print_enabled ? '开启' : '关闭'}`)
  } catch (e) {
    row.print_enabled = !row.print_enabled
    ElMessage.error('操作失败：' + e.message)
  }
}

async function deleteStore(row) {
  try {
    await ElMessageBox.confirm(`确认删除「${row.name}」？`, '删除确认', {
      type: 'danger',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  try {
    await http.delete(`/admin/wemall-stores/${row.id}`)
    ElMessage.success('已删除')
    await loadStores()
  } catch (e) {
    ElMessage.error('删除失败：' + e.message)
  }
}

onMounted(loadStores)
onBeforeUnmount(() => {
  formDialog.value = false
  testDialog.value = false
})
</script>
