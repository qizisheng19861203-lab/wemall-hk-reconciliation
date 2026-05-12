import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isLoggedIn) return '/login'
  if (to.meta.adminOnly && !auth.isAdmin) return '/dashboard'
  if (to.path === '/login' && auth.isLoggedIn) return '/dashboard'
})

export default router
