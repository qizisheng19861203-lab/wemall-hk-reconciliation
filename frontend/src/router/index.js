import { createRouter, createWebHistory } from 'vue-router'
import { nextTick } from 'vue'

const routes = [
  { path: '/login', component: () => import('@/views/Login.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', component: () => import('@/views/Dashboard.vue') },
      { path: 'orders', component: () => import('@/views/Orders.vue') },
      { path: 'products', component: () => import('@/views/Products.vue') },
      { path: 'settlements', component: () => import('@/views/Settlements.vue') },
      { path: 'rates', component: () => import('@/views/ExchangeRates.vue') },
      { path: 'reports', component: () => import('@/views/Reports.vue') },
      { path: 'users', component: () => import('@/views/Users.vue'), meta: { adminOnly: true } },
      { path: 'notification-contacts', component: () => import('@/views/NotificationContacts.vue'), meta: { adminOnly: true } },
      { path: 'wemall-stores', component: () => import('@/views/WemallStores.vue'), meta: { adminOnly: true } },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  const user = JSON.parse(localStorage.getItem('user') || 'null')
  const isLoggedIn = !!token
  const isAdmin = user?.role === 'admin'
  if (to.meta.requiresAuth && !isLoggedIn) return '/login'
  if (to.meta.adminOnly && !isAdmin) return '/dashboard'
  if (to.path === '/login' && isLoggedIn) return '/dashboard'

  // 导航前立即清理 body 上的残留遮罩，防止切换时遮罩仍在拦截点击
  cleanupOverlays()
})

// 清理 El Plus 遗留的浮层（teleport 到 body 的 overlay/popper）
// dialog 已改为 teleported=false，body 下只剩 ElMessageBox 及偶发残影
function cleanupOverlays() {
  document.querySelectorAll('body > .el-overlay').forEach(el => el.remove())
  document.querySelectorAll('.el-select__popper, .el-picker__popper, .el-dropdown__popper').forEach(el => {
    if (el.parentNode === document.body) el.remove()
  })
}

router.afterEach(() => {
  // afterEach 再清理一次（nextTick 等 Vue 完成 DOM 更新后）
  nextTick(cleanupOverlays)
})

export default router
