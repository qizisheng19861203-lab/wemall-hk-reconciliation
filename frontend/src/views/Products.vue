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
        <el-button type="primary" @click="openAdd" :icon="Plus">新增产品</el-button>
        <el-button type="success" @click="syncRecentProducts" :loading="syncingRecent">同步最近20个产品</el-button>
        <el-button @click="syncProducts" :loading="syncing">同步全部产品</el-button>
        <el-button type="warning" @click="pushToStore" :disabled="!selectedProducts.length" :loading="pushing">
          同步到倍赛思甄选 ({{ selectedProducts.length }})
        </el-button>
      </div>
    </div>

    <el-card shadow="never">
      <div style="margin-bottom:12px;display:flex;gap:8px;align-items:center">
        <el-input v-model="keyword" placeholder="搜索产品名/SKU" clearable style="width:220px"
          @clear="load" @keydown.enter.prevent="load" />
        <el-button @click="load">搜索</el-button>
        <el-radio-group v-model="syncFilter" @change="load" style="margin-left:12px">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="synced">已同步甄选</el-radio-button>
          <el-radio-button value="unsynced">未同步</el-radio-button>
        </el-radio-group>
        <el-button size="small" @click="refreshTargetSkus" :loading="loadingSkus" style="margin-left:8px">刷新同步状态</el-button>
        <el-tag type="warning" style="margin-left:auto">⚠ 供货价仅管理员可编辑</el-tag>
      </div>
      <!-- 手动 loading 覆盖层：v-if 保证加载完成后立即从 DOM 消失，不留 pointer-events 残留 -->
      <div style="position:relative;">
      <div v-if="loading" style="position:absolute;inset:0;z-index:10;background:rgba(255,255,255,0.65);display:flex;align-items:center;justify-content:center;border-radius:4px;">
        <el-icon class="is-loading" :size="28" color="#409EFF"><Loading /></el-icon>
      </div>
      <el-table :data="filteredProducts" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" v-if="auth.isAdmin" />
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
        <el-table-column label="甄选" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="targetSkus.has(row.sku)" type="success" size="small">已同步</el-tag>
            <el-tag v-else type="info" size="small">未同步</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" v-if="auth.isAdmin">
          <template #default="{ row }">
            <el-button size="small" link @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
      </div><!-- end loading wrapper -->
    </el-card>

    <el-dialog v-model="dialog" :title="editingId ? '编辑产品' : '新增产品'" width="520px" destroy-on-close :teleported="false">
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
        <div style="display:flex;justify-content:space-between;align-items:center">
          <el-button v-if="editingId" type="danger" plain @click="deleteProduct" :loading="deleting">删除产品</el-button>
          <div v-else />
          <div>
            <el-button @click="dialog = false">取消</el-button>
            <el-button type="primary" @click="save" :loading="saving">保存</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { Loading, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { products as productsApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const products = ref([])
const loading = ref(false)
const syncing = ref(false)
const syncingRecent = ref(false)
const saving = ref(false)
const deleting = ref(false)
const pushing = ref(false)
const dialog = ref(false)
const editingId = ref(null)
const keyword = ref('')
const form = reactive({ name: '', sku: '', category: '', retail_price: null, supply_price: null, image_url: '', notes: '', is_active: true })
const selectedProducts = ref([])
const syncFilter = ref('all')
const targetSkus = ref(new Set())
const loadingSkus = ref(false)

const filteredProducts = computed(() => {
  if (syncFilter.value === 'all') return products.value
  if (syncFilter.value === 'synced') return products.value.filter(p => targetSkus.value.has(p.sku))
  return products.value.filter(p => !targetSkus.value.has(p.sku))
})

function handleSelectionChange(val) {
  selectedProducts.value = val
}

async function refreshTargetSkus() {
  loadingSkus.value = true
  try {
    const res = await productsApi.getTargetStoreSkus()
    targetSkus.value = new Set(res.skus || [])
  } catch (e) {
    console.error('获取甄选同步状态失败', e)
  } finally { loadingSkus.value = false }
}

async function pushToStore() {
  if (!selectedProducts.value.length) return ElMessage.warning('请先勾选要同步的产品')
  const names = selectedProducts.value.map(p => p.name).join('、')
  try {
    await ElMessageBox.confirm(
      `确定将以下 ${selectedProducts.value.length} 个产品同步到倍赛思甄选？\n\n${names}\n\n将以零售价创建商品，图片和详情会自动同步。`,
      '同步确认',
      { confirmButtonText: '同步', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }

  pushing.value = true
  try {
    const res = await productsApi.pushToStore({
      product_ids: selectedProducts.value.map(p => p.id),
    })
    const s = res.success?.length || 0
    const f = res.failed?.length || 0
    if (f > 0) {
      const errList = res.failed.map(x => `${x.name}: ${x.error}`).join('\n')
      ElMessageBox.alert(errList, `成功${s}个，失败${f}个`, { confirmButtonText: '知道了' })
    } else {
      ElMessage.success(`成功同步 ${s} 个产品到倍赛思甄选`)
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  } finally { pushing.value = false }
}

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

async function deleteProduct() {
  try {
    await ElMessageBox.confirm('确定要删除这个产品吗？此操作不可撤销。', '删除确认', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
      confirmButtonClass: 'el-button--danger',
    })
  } catch { return }
  deleting.value = true
  try {
    await productsApi.remove(editingId.value)
    ElMessage.success('删除成功')
    dialog.value = false
    load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '删除失败')
  } finally { deleting.value = false }
}

async function syncProducts() {
  syncing.value = true
  try {
    const res = await productsApi.syncWemall()
    ElMessage.success(`同步完成：新增${res.created}，更新${res.updated}`)
    await load()
  } catch (e) { ElMessage.error(e.message) }
  finally { syncing.value = false }
}

async function syncRecentProducts() {
  syncingRecent.value = true
  try {
    const res = await productsApi.syncWemall()
    ElMessage.success(`同步最近20个产品完成：新增${res.created}，更新${res.updated}`)
    await load()
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

onBeforeUnmount(() => { loading.value = false; dialog.value = false; deleting.value = false; pushing.value = false })
onMounted(() => { load(); refreshTargetSkus() })
</script>
