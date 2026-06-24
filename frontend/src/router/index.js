import { createRouter, createWebHistory } from 'vue-router'
import { nextTick } from 'vue'

const routes = [
  { path: '/login', component: () => import('@/views/Login.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: () => {
      const user = JSON.parse(localStorage.getItem('user') || 'null')
      return user?.role === 'distributor' ? '/orders' : '/dashboard'
    }},
      { path: 'dashboard', component: () => import('@/views/Dashboard.vue') },
      { path: 'orders', component: () => import('@/views/Orders.vue') },
      { path: 'products', component: () => import('@/views/Products.vue'), meta: { adminOnly: true } },
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
  const isDistributor = user?.role === 'distributor'
  // 运营(对账人员)与分销商一样，只能访问订单+结算（仅查看/下载，不做编辑同步等管理操作）
  const isLimited = isDistributor || user?.role === 'operator'
  if (to.meta.requiresAuth && !isLoggedIn) return '/login'
  if (to.meta.adminOnly && !isAdmin) return isLimited ? '/orders' : '/dashboard'
  // 分销商/运营只能访问 /orders 和 /settlements
  if (isLimited && !['/orders', '/settlements'].includes(to.path)) return '/orders'
  if (to.path === '/login' && isLoggedIn) return isLimited ? '/orders' : '/dashboard'

  // 导航前立即清理 body 上的残留遮罩，防止切换时遮罩仍在拦截点击
  cleanupOverlays()
})

// 清理 El Plus 遗留的浮层（teleport 到 body 的 overlay/popper）
// dialog 已改为 teleported=false，body 下只剩 ElMessageBox 及偶发残影
function cleanupOverlays() {
  document.querySelectorAll('body > .el-overlay').forEach(el => el.remove())
  // 卡住的 loading 遮罩（全屏式 或 挂到 body 的）会拦截所有点击 → 导航时一并清掉
  document.querySelectorAll('.el-loading-mask.is-fullscreen, body > .el-loading-mask').forEach(el => el.remove())
  document.querySelectorAll('.el-select__popper, .el-picker__popper, .el-dropdown__popper').forEach(el => {
    if (el.parentNode === document.body) el.remove()
  })
}

router.afterEach(() => {
  // afterEach 再清理一次（nextTick 等 Vue 完成 DOM 更新后）
  nextTick(cleanupOverlays)
})

export default router
