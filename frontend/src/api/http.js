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
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      router.push('/login')
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
