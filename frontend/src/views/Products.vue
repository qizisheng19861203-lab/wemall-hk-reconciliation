<template>
  <div>
    <div class="page-header" style="display:flex;justify-content:space-between;align-items:center">
      <div><h2>产品库</h2></div>
      <div style="display:flex;gap:8px" v-if="auth.isAdmin">
        <el-upload
          action="/api/products/import-supply-price"
          :headers="{ Authorization: `Bearer ${auth.token}` }"
          :show-file-list="false"
          :on-success="handleImportSuccess"
          :on-error="handleImportError"
          :before-upload="beforeUpload"
          accept=".xlsx,.xls"
        >
          <el-button type="success">导入供货价</el-button>
        </el-upload>
        <el-button type="success" @click="syncRecentProducts" :loading="syncingRecent">同步最近20个产品</el-button>
        <el-button @click="syncProducts" :loading="syncing">同步全部产品</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <div style="margin-bottom:12px;display:flex;gap:8px">
        <el-input v-model="keyword" placeholder="搜索产品名/SKU" clearable style="width:220px" @clear="load" @keyup.enter="load" />
        <el-button @click="load">搜索</el-button>
        <el-tag type="warning" style="margin-left:auto">⚠ 供货价仅管理员可编辑</el-tag>
      </div>
      <el-table :data="products" v-loading="loading" stripe>
        <el-table-column label="图片" width="70">
          <template #default="{ row }">
            <el-image :src="row.image_url" style="width:44px;height:44px;border-radius:4px" fit="cover">
              <template #error><div style="width:44px;height:44px;background:#f5f5f5;border-radius:4px" /></template>
            </el-image>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="产品名称" min-width="200" />
        <el-table-column prop="sku" label="SKU" width="120" />
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column prop="retail_price" label="零售价(RMB)" width="110" align="right">
          <template #default="{ row }">{{ row.retail_price ? `¥${row.retail_price}` : '-' }}</template>
        </el-table-column>
        <el-table-column label="供货价(RMB)" width="130" align="right">
          <template #default="{ row }">
            <span v-if="row.supply_price" style="color:#409EFF;font-weight:600">¥{{ row.supply_price }}</span>
            <el-tag v-else type="danger" size="small">未设置</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right" v-if="auth.isAdmin">
          <template #default="{ row }">
            <el-button size="small" link @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialog" :title="editingId ? '编辑产品' : '新增产品'" width="520px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="产品名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="SKU"><el-input v-model="form.sku" /></el-form-item>
        <el-form-item label="分类"><el-input v-model="form.category" /></el-form-item>
        <el-form-item label="零售价(RMB)"><el-input-number v-model="form.retail_price" :precision="2" :min="0" /></el-form-item>
        <el-form-item label="供货价(RMB)">
          <el-input-number v-model="form.supply_price" :precision="2" :min="0" />
          <span style="font-size:12px;color:#F56C6C;margin-left:8px">仅管理员可改</span>
        </el-form-item>
        <el-form-item label="图片URL"><el-input v-model="form.image_url" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.is_active" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="save" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { products as productsApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const products = ref([])
const loading = ref(false)
const syncing = ref(false)
const syncingRecent = ref(false)
const saving = ref(false)
const dialog = ref(false)
const editingId = ref(null)
const keyword = ref('')
const form = reactive({ name: '', sku: '', category: '', retail_price: null, supply_price: null, image_url: '', notes: '', is_active: true })

async function load() {
  loading.value = true
  try {
    products.value = await productsApi.list({ keyword: keyword.value || undefined })
  } finally { loading.value = false }
}

function openAdd() {
  editingId.value = null
  Object.assign(form, { name: '', sku: '', category: '', retail_price: null, supply_price: null, image_url: '', notes: '', is_active: true })
  dialog.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, { name: row.name, sku: row.sku || '', category: row.category || '', retail_price: row.retail_price, supply_price: row.supply_price, image_url: row.image_url || '', notes: row.notes || '', is_active: row.is_active })
  dialog.value = true
}

async function save() {
  if (!form.name) return ElMessage.warning('产品名称不能为空')
  saving.value = true
  try {
    if (editingId.value) {
      const res = await productsApi.update(editingId.value, form)
      const backfilled = res?.backfilled_count ?? 0
      if (backfilled > 0) {
        ElMessage.success(`保存成功，已自动补录 ${backfilled} 条历史订单供货价`)
      } else {
        ElMessage.success('保存成功')
      }
    } else {
      await productsApi.create(form)
      ElMessage.success('保存成功')
    }
    dialog.value = false
    load()
  } catch (e) { ElMessage.error(e.message) }
  finally { saving.value = false }
}

async function syncProducts() {
  syncing.value = true
  try {
    const res = await productsApi.syncWemall()
    ElMessage.success(`同步完成：新增${res.created}，更新${res.updated}`)
    load()
  } catch (e) { ElMessage.error(e.message) }
  finally { syncing.value = false }
}

async function syncRecentProducts() {
  syncingRecent.value = true
  try {
    const res = await productsApi.syncWemall()
    ElMessage.success(`同步最近20个产品完成：新增${res.created}，更新${res.updated}`)
    load()
  } catch (e) { ElMessage.error(e.message) }
  finally { syncingRecent.value = false }
}

function beforeUpload(file) {
  const isExcel = file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
                  file.type === 'application/vnd.ms-excel'
  if (!isExcel) {
    ElMessage.error('只能上传Excel文件(.xlsx, .xls)')
    return false
  }
  const isLt5M = file.size / 1024 / 1024 < 5
  if (!isLt5M) {
    ElMessage.error('文件大小不能超过5MB')
    return false
  }
  return true
}

function handleImportSuccess(response) {
  const { updated, not_found, not_found_list } = response
  let msg = `导入成功：更新了${updated}个产品的供货价`
  if (not_found > 0) {
    msg += `，${not_found}个产品未找到`
    if (not_found_list && not_found_list.length > 0) {
      const list = not_found_list.map(item => `${item.goods_id} - ${item.title}`).join('\n')
      ElMessageBox.alert(list, '以下产品未找到', { confirmButtonText: '知道了' })
    }
  }
  ElMessage.success(msg)
  load()
}

function handleImportError(error) {
  const msg = error.message || '导入失败'
  ElMessage.error(msg)
}

onMounted(load)
</script>
