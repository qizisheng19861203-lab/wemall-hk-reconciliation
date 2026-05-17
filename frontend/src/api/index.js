import http from './http'

export const auth = {
  login: (data) => http.post('/auth/login', data),
  me: () => http.get('/auth/me'),
}

export const users = {
  list: () => http.get('/users'),
  create: (data) => http.post('/users', data),
  update: (id, data) => http.put(`/users/${id}`, data),
  remove: (id) => http.delete(`/users/${id}`),
}

export const products = {
  list: (params) => http.get('/products', { params }),
  create: (data) => http.post('/products', data),
  update: (id, data) => http.put(`/products/${id}`, data),
  syncWemall: () => http.post('/products/sync-wemall'),
}

export const orders = {
  list: (params) => http.get('/orders', { params }),
  get: (id) => http.get(`/orders/${id}`),
  update: (id, data) => http.put(`/orders/${id}`, data),
  stats: (params) => http.get('/orders/stats', { params }),
  syncWemall: (params) => http.post('/orders/sync-wemall', null, { params }),
}

export const settlements = {
  list: (params) => http.get('/settlements', { params }),
  create: (data) => http.post('/settlements', data),
  confirm: (id, data) => http.post(`/settlements/${id}/confirm`, data),
  delete: (id) => http.delete(`/settlements/${id}`),
  notify: (id) => http.post(`/settlements/${id}/notify`),
  autoSettle: (params) => http.post('/settlements/auto-settle', null, { params }),
  invoiceUrl: (id) => `/api/settlements/${id}/invoice.pdf`,
  detailUrl: (id) => `/api/settlements/${id}/detail.pdf`,
  batchInvoiceUrl: (ids) => `/api/settlements/batch-invoice.zip?ids=${ids.join(',')}`,
  batchDetailUrl: (ids) => `/api/settlements/batch-detail.zip?ids=${ids.join(',')}`,
}

export const rates = {
  list: () => http.get('/exchange-rates'),
  today: () => http.get('/exchange-rates/today'),
  create: (data) => http.post('/exchange-rates', data),
  fetchToday: () => http.post('/exchange-rates/fetch-today'),
}

export const reports = {
  dashboard: () => http.get('/reports/dashboard'),
  monthly: (year) => http.get('/reports/monthly', { params: { year } }),
  yearly: () => http.get('/reports/yearly'),
}
