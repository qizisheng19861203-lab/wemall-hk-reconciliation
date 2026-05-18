<template>
  <div>
    <div class="page-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
      <div>
        <h2 style="font-size:24px;margin:0">短信通知号码管理</h2>
        <p style="margin:6px 0 0;color:#909399;font-size:13px">管理结算通知短信的接收手机号，启用状态的号码会收到结算通知</p>
      </div>
      <el-button v-if="auth.isAdmin" type="primary" size="large" @click="openAdd">
        <el-icon style="margin-right:6px"><Plus /></el-icon>
        添加号码
      </el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="contacts" v-loading="loading" stripe style="font-size:14px">
        <el-table-column label="联系人名称" prop="name" min-width="150">
          <template #default="{ row }">
            <span style="font-weight:600;font-size:15px">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="手机号" prop="phone" width="180">
          <template #default="{ row }">
            <span style="font-family:monospace;font-size:14px;color:#303133">{{ row.phone }}</span>
          </template>
        </el-table-column>
        <el-table-column label="邮箱" prop="email" min-width="200">
          <template #default="{ row }">
            <span v-if="row.email" style="font-size:13px;color:#303133">{{ row.email }}</span>
            <span v-else style="font-size:13px;color:#c0c4cc">未设置</span>
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
        <el-table-column label="添加时间" width="180" align="center">
          <template #default="{ row }">
            <span style="color:#909399;font-size:13px">{{ row.created_at?.slice(0, 16) }}</span>
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

      <el-empty v-if="!loading && contacts.length === 0" description="暂无通知号码，点击右上角添加" style="padding:40px 0" />
    </el-card>

    <!-- 说明区 -->
    <el-card shadow="never" style="margin-top:16px;background:#f8f9fa">
      <div style="font-size:13px;color:#606266;line-height:2">
        <strong style="color:#303133">使用说明：</strong><br>
        · 在结算管理页点击「发通知」按钮时，所有<strong>启用</strong>状态的号码都会收到短信<br>
        · 在结算管理页点击「发邮件」按钮时，所有<strong>启用</strong>且填写了邮箱的联系人都会收到账单邮件<br>
        · 手机号格式支持：<code>13812345678</code>（自动加 +86）或 <code>+85213812345</code>（含国际区号）<br>
        · 关闭开关可临时禁用某个号码，不会删除记录
      </div>
    </el-card>

    <!-- 添加/编辑弹窗 -->
    <el-dialog v-model="formDialog" :title="editingId ? '编辑联系人' : '添加通知号码'" width="420px">
      <el-form :model="form" label-width="90px" style="margin-top:8px">
        <el-form-item label="联系人名称" required>
          <el-input v-model="form.name" placeholder="如：张总、运营小王" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="手机号" required>
          <el-input v-model="form.phone" placeholder="如：13812345678 或 +85212345678" />
          <div style="font-size:12px;color:#909399;margin-top:4px">大陆号码直接填11位，港澳号码填 +852/+853 开头</div>
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="如：contact@example.com（可选）" />
          <div style="font-size:12px;color:#909399;margin-top:4px">填写后可在结算管理页发送PDF账单邮件</div>
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
import { ref, reactive, onMounted } from 'vue'
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
const form = reactive({ name: '', phone: '', email: '', is_active: true })

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
  Object.assign(form, { name: '', phone: '', email: '', is_active: true })
  formDialog.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, { name: row.name, phone: row.phone, email: row.email || '', is_active: row.is_active })
  formDialog.value = true
}

async function submitForm() {
  if (!form.name.trim()) return ElMessage.warning('请填写联系人名称')
  if (!form.phone.trim()) return ElMessage.warning('请填写手机号')
  submitting.value = true
  try {
    if (editingId.value) {
      await contactsApi.update(editingId.value, { name: form.name, phone: form.phone, email: form.email || null, is_active: form.is_active })
      ElMessage.success('修改成功')
    } else {
      await contactsApi.create({ name: form.name, phone: form.phone, email: form.email || null })
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
    await ElMessageBox.confirm('确认删除此通知号码？', '警告', {
      type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消',
    })
    await contactsApi.remove(id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

onMounted(load)
</script>
