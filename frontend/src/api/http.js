import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

const http = axios.create({ baseURL: '/api', timeout: 30000 })

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const status = err.response?.status
    const detail = err.response?.data?.detail
    // 未认证 = 401，或 403 且是 HTTPBearer 的"Not authenticated"(令牌丢失/未带) → 清令牌跳登录。
    // 注意：403 且带有效令牌但权限不足(如运营点管理员接口)不算未认证，只提示不跳转。
    const notAuthed = status === 401 || (status === 403 && /not authenticated/i.test(String(detail || '')))
    if (notAuthed) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (router.currentRoute.value.path !== '/login') router.push('/login')
    }

    // 显示详细错误信息（内部系统，方便调试）
    let msg = err.response?.data?.detail || err.message || '请求失败'

    // 如果是对象，转成 JSON 字符串
    if (typeof msg === 'object') {
      msg = JSON.stringify(msg, null, 2)
    }

    // 添加 HTTP 状态码和 URL 信息
    const status = err.response?.status
    const url = err.config?.url
    if (status || url) {
      msg = `${msg}\n\n[${status || 'Network Error'}] ${url || ''}`
    }

    return Promise.reject(new Error(msg))
  }
)

export default http
