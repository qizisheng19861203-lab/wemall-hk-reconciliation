<template>
  <el-container class="layout">
    <el-aside width="220px" class="sidebar">
      <div class="sidebar-logo">
        <el-icon size="22" color="#fff"><Shop /></el-icon>
        <span>HK对账</span>
      </div>
      <el-menu router :default-active="$route.path" background-color="#1a2035"
        text-color="#adb5bd" active-text-color="#ffffff">
        <el-menu-item index="/dashboard"><el-icon><DataLine /></el-icon>总览</el-menu-item>
        <el-menu-item index="/orders"><el-icon><List /></el-icon>订单管理</el-menu-item>
        <el-menu-item index="/products"><el-icon><Goods /></el-icon>产品库</el-menu-item>
        <el-menu-item index="/settlements"><el-icon><Money /></el-icon>结算管理</el-menu-item>
        <el-menu-item index="/rates"><el-icon><Coin /></el-icon>汇率管理</el-menu-item>
        <el-menu-item index="/reports"><el-icon><TrendCharts /></el-icon>统计报表</el-menu-item>
        <el-menu-item v-if="auth.isAdmin" index="/users"><el-icon><User /></el-icon>用户管理</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-breadcrumb>
            <el-breadcrumb-item>{{ pageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-avatar size="small" :style="{ background: '#409EFF' }">{{ auth.user?.display_name?.[0] }}</el-avatar>
              <span>{{ auth.user?.display_name }}</span>
              <el-tag size="small" :type="roleTag">{{ roleLabel }}</el-tag>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="changePassword">修改密码</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <!-- 修改密码弹窗 -->
          <el-dialog v-model="pwdDialog" title="修改密码" width="400px">
            <el-form :model="pwdForm" label-width="90px">
              <el-form-item label="原密码">
                <el-input v-model="pwdForm.old_password" type="password" show-password />
              </el-form-item>
              <el-form-item label="新密码">
                <el-input v-model="pwdForm.new_password" type="password" show-password />
              </el-form-item>
              <el-form-item label="确认新密码">
                <el-input v-model="pwdForm.confirm_password" type="password" show-password />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="pwdDialog = false">取消</el-button>
              <el-button type="primary" @click="submitChangePassword" :loading="pwdLoading">确认修改</el-button>
            </template>
          </el-dialog>
        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import http from '@/api/http'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const titleMap = {
  '/dashboard': '总览',
  '/orders': '订单管理',
  '/products': '产品库',
  '/settlements': '结算管理',
  '/rates': '汇率管理',
  '/reports': '统计报表',
  '/users': '用户管理',
}
const pageTitle = computed(() => titleMap[route.path] || '微盟香港对账')
const roleLabel = computed(() => ({ admin: '管理员', operator: '运营', distributor: '分销商' })[auth.user?.role] || '')
const roleTag = computed(() => ({ admin: '', operator: 'success', distributor: 'info' })[auth.user?.role] || 'info')

const pwdDialog = ref(false)
const pwdLoading = ref(false)
const pwdForm = reactive({ old_password: '', new_password: '', confirm_password: '' })

function handleCommand(cmd) {
  if (cmd === 'logout') { auth.logout(); router.push('/login') }
  if (cmd === 'changePassword') {
    Object.assign(pwdForm, { old_password: '', new_password: '', confirm_password: '' })
    pwdDialog.value = true
  }
}

async function submitChangePassword() {
  if (!pwdForm.old_password || !pwdForm.new_password) return ElMessage.warning('请填写完整')
  if (pwdForm.new_password !== pwdForm.confirm_password) return ElMessage.warning('两次新密码不一致')
  pwdLoading.value = true
  try {
    await http.post('/auth/change-password', { old_password: pwdForm.old_password, new_password: pwdForm.new_password })
    ElMessage.success('密码修改成功，请重新登录')
    pwdDialog.value = false
    setTimeout(() => { auth.logout(); router.push('/login') }, 1500)
  } catch (e) { ElMessage.error(e.message) }
  finally { pwdLoading.value = false }
}
</script>

<style scoped>
.layout { height: 100vh; }
.sidebar { background: #1a2035; overflow: hidden; display: flex; flex-direction: column; }
.sidebar-logo { padding: 18px 20px; display: flex; align-items: center; gap: 10px; color: #fff; font-size: 16px; font-weight: 600; border-bottom: 1px solid rgba(255,255,255,0.1); }
.header { background: #fff; border-bottom: 1px solid #ebeef5; display: flex; align-items: center; justify-content: space-between; padding: 0 24px; }
.user-info { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.main { background: #f4f6fa; padding: 24px; overflow-y: auto; }
</style>
