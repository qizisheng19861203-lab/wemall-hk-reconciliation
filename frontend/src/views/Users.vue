<template>
  <div>
    <div class="page-header" style="display:flex;justify-content:space-between;align-items:center">
      <div><h2>用户管理</h2></div>
      <el-button type="primary" @click="openAdd">新增用户</el-button>
    </div>
    <el-card shadow="never">
      <el-table :data="users" v-loading="loading" stripe>
        <el-table-column prop="username" label="用户名" width="130" />
        <el-table-column prop="display_name" label="姓名" width="130" />
        <el-table-column prop="phone" label="手机" width="130" />
        <el-table-column label="角色" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="roleType[row.role]" size="small">{{ roleLabel[row.role] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" link @click="openEdit(row)">编辑</el-button>
            <el-button size="small" link type="danger" @click="toggleActive(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialog" :title="editingId ? '编辑用户' : '新增用户'" width="440px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名" v-if="!editingId" required><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="密码" v-if="!editingId" required><el-input v-model="form.password" type="password" /></el-form-item>
        <el-form-item label="姓名" required><el-input v-model="form.display_name" /></el-form-item>
        <el-form-item label="手机"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role">
            <el-option label="管理员（完整权限）" value="admin" />
            <el-option label="运营（查看+下载）" value="operator" />
            <el-option label="分销商员工（仅查看）" value="distributor" />
          </el-select>
        </el-form-item>
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
import { ElMessage } from 'element-plus'
import { users as usersApi } from '@/api'

const users = ref([])
const loading = ref(false)
const saving = ref(false)
const dialog = ref(false)
const editingId = ref(null)
const form = reactive({ username: '', password: '', display_name: '', phone: '', email: '', role: 'distributor' })

const roleLabel = { admin: '管理员', operator: '运营', distributor: '分销商' }
const roleType = { admin: 'danger', operator: 'success', distributor: 'info' }

async function load() {
  loading.value = true
  try { users.value = await usersApi.list() }
  finally { loading.value = false }
}

function openAdd() {
  editingId.value = null
  Object.assign(form, { username: '', password: '', display_name: '', phone: '', email: '', role: 'distributor' })
  dialog.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, { display_name: row.display_name, phone: row.phone || '', email: row.email || '', role: row.role })
  dialog.value = true
}

async function save() {
  if (!form.display_name) return ElMessage.warning('姓名不能为空')
  saving.value = true
  try {
    if (editingId.value) await usersApi.update(editingId.value, { display_name: form.display_name, phone: form.phone, email: form.email })
    else await usersApi.create(form)
    ElMessage.success('保存成功')
    dialog.value = false
    load()
  } catch (e) { ElMessage.error(e.message) }
  finally { saving.value = false }
}

async function toggleActive(row) {
  try {
    await usersApi.update(row.id, { is_active: !row.is_active })
    row.is_active = !row.is_active
  } catch (e) { ElMessage.error(e.message) }
}

onMounted(load)
</script>
