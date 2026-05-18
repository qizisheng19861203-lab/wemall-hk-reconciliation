<template>
  <div>
    <div class="page-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
      <div>
        <h2 style="font-size:24px;margin:0">通知联系人管理</h2>
        <p style="margin:6px 0 0;color:#909399;font-size:13px">管理结算通知邮件的接收联系人，启用状态的联系人会收到结算通知</p>
      </div>
      <el-button v-if="auth.isAdmin" type="primary" size="large" @click="openAdd">
        <el-icon style="margin-right:6px"><Plus /></el-icon>
        添加联系人
      </el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="contacts" v-loading="loading" stripe style="font-size:14px">
        <el-table-column label="姓名" prop="name" min-width="130">
          <template #default="{ row }">
            <span style="font-weight:600;font-size:15px">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="手机号（可选）" prop="phone" width="180">
          <template #default="{ row }">
            <span v-if="row.phone" style="font-family:monospace;font-size:14px;color:#303133">{{ row.phone }}</span>
            <span v-else style="font-size:13px;color:#c0c4cc">未设置</span>
          </template>
        </el-table-column>
        <el-table-column label="邮箱（必填）" prop="email" min-width="220">
          <template #default="{ row }">
            <span v-if="row.email" style="font-size:13px;color:#303133">{{ row.email }}</span>
            <span v-else style="font-size:13px;color:#f56c6c">未设置</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-switch
              v-if="auth.isAdmin"
              v-model="row.is_active"
              @change="toggleActive(row)"
              active-text="启用"
              inactive-text="禁用"
              style="--el-switch-on-color:#67c23a"
            />
            <el-tag v-else :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="center" v-if="auth.isAdmin">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="openEdit(row)">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            <el-button size="small" type="danger" plain @click="removeContact(row.id)">
              <el-icon><Delete /></el-icon> 删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && contacts.length === 0" description="暂无通知联系人，点击右上角添加" style="padding:40px 0" />
    </el-card>

    <!-- 说明区 -->
    <el-card shadow="never" style="margin-top:16px;background:#f8f9fa">
      <div style="font-size:13px;color:#606266;line-height:2">
        <strong style="color:#303133">使用说明：</strong><br>
        · 每次生成结算单后，系统会自动向所有<strong>启用</strong>且填写了邮箱的联系人发送账单邮件<br>
        · 在结算管理页也可手动点击「发邮件」按钮重新发送<br>
        · 邮件正文包含账单预览，附件为PDF文件<br>
        · 关闭开关可临时禁用某个联系人，不会删除记录
      </div>
    </el-card>

    <!-- 添加/编辑弹窗 -->
    <el-dialog v-model="formDialog" :title="editingId ? '编辑联系人' : '添加通知联系人'" width="460px" :teleported="false">
      <el-form :model="form" label-width="100px" style="margin-top:8px">
        <el-form-item label="姓名" required>
          <el-input v-model="form.name" placeholder="如：张总、运营小王" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="邮箱" required>
          <el-autocomplete
            v-model="form.email"
            :fetch-suggestions="queryEmailSuggestions"
            placeholder="请输入邮箱地址（必填）"
            style="width:100%"
            clearable
          />
          <div style="font-size:12px;color:#909399;margin-top:4px">结算账单将发送到此邮箱，输入@后自动提示常用域名</div>
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="form.phone" placeholder="11位手机号，选填" maxlength="11" />
          <div style="font-size:12px;color:#909399;margin-top:4px">大陆11位手机号，选填</div>
        </el-form-item>
        <el-form-item label="状态" v-if="editingId">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formDialog = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">
          {{ editingId ? '保存修改' : '确认添加' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import { notificationContacts as contactsApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const contacts = ref([])
const loading = ref(false)
const formDialog = ref(false)
const submitting = ref(false)
const editingId = ref(null)
const form = reactive({ name: '', email: '', phone: '', is_active: true })

const EMAIL_DOMAINS = ['@qq.com', '@163.com', '@126.com', '@gmail.com', '@outlook.com', '@hotmail.com', '@sina.com', '@139.com']

function queryEmailSuggestions(queryString, cb) {
  if (!queryString || !queryString.includes('@')) {
    cb([])
    return
  }
  const atIndex = queryString.indexOf('@')
  const prefix = queryString.substring(0, atIndex)
  const domainPart = queryString.substring(atIndex)
  const results = EMAIL_DOMAINS
    .filter(d => d.startsWith(domainPart) || domainPart === '@')
    .map(d => ({ value: prefix + d }))
  cb(results)
}

async function load() {
  loading.value = true
  try {
    contacts.value = await contactsApi.list()
  } catch (e) {
    ElMessage.error('加载失败：' + (e.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

function openAdd() {
  editingId.value = null
  Object.assign(form, { name: '', email: '', phone: '', is_active: true })
  formDialog.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    email: row.email || '',
    phone: row.phone || '',
    is_active: row.is_active,
  })
  formDialog.value = true
}

function validateForm() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写联系人姓名')
    return false
  }
  if (!form.email.trim()) {
    ElMessage.warning('请填写邮箱地址（必填）')
    return false
  }
  if (!form.email.includes('@') || !form.email.split('@')[1]?.includes('.')) {
    ElMessage.warning('请输入有效的邮箱地址')
    return false
  }
  if (form.phone && form.phone.trim()) {
    if (!/^1[3-9]\d{9}$/.test(form.phone.trim())) {
      ElMessage.warning('手机号格式不正确，需为11位且以1[3-9]开头的大陆手机号')
      return false
    }
  }
  return true
}

async function submitForm() {
  if (!validateForm()) return
  submitting.value = true
  try {
    const payload = {
      name: form.name.trim(),
      email: form.email.trim(),
      phone: form.phone.trim() || null,
    }
    if (editingId.value) {
      await contactsApi.update(editingId.value, { ...payload, is_active: form.is_active })
      ElMessage.success('修改成功')
    } else {
      await contactsApi.create(payload)
      ElMessage.success('添加成功')
    }
    formDialog.value = false
    load()
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function toggleActive(row) {
  try {
    await contactsApi.update(row.id, { is_active: row.is_active })
    ElMessage.success(row.is_active ? '已启用' : '已禁用')
  } catch (e) {
    row.is_active = !row.is_active  // 回滚
    ElMessage.error(e.message || '操作失败')
  }
}

async function removeContact(id) {
  try {
    await ElMessageBox.confirm('确认删除此联系人？', '警告', {
      type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消',
    })
    await contactsApi.remove(id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

onBeforeUnmount(() => { loading.value = false; formDialog.value = false })
onMounted(load)
</script>
