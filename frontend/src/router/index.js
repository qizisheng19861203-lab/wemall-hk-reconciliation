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
})

// 每次路由切换后，清理 Element Plus 遗留的浮层（dialog/select/datepicker overlay）
// 这些浮层 teleport 到 <body>，导航离开时若未关闭会残留并拦截所有点击
router.afterEach(() => {
  nextTick(() => {
    // 移除孤立的遮罩层
    document.querySelectorAll('.el-overlay').forEach(el => {
      // 只移除没有可见内容的遮罩（dialog 关闭动画已结束但未清理）
      const hasVisibleDialog = el.querySelector('.el-dialog, .el-message-box')
      if (!hasVisibleDialog) el.remove()
    })
    // 移除孤立的下拉浮层
    document.querySelectorAll('.el-select__popper, .el-picker__popper, .el-dropdown__popper').forEach(el => {
      if (!el.closest('[data-v]') && el.parentNode === document.body) el.remove()
    })
  })
})

export default router
