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
  remove: (id) => http.delete(`/products/${id}`),
  syncWemall: () => http.post('/products/sync-wemall'),
  getTargetStoreConfig: () => http.get('/products/target-store-config'),
  getTargetStoreSkus: () => http.get('/products/target-store-skus'),
  getBeisiStock: () => http.get('/products/beisi-stock'),
  pushToStore: (data) => http.post('/products/push-to-store', data),
}

export const orders = {
  list: (params) => http.get('/orders', { params }),
  get: (id) => http.get(`/orders/${id}`),
  update: (id, data) => http.put(`/orders/${id}`, data),
  stats: (params) => http.get('/orders/stats', { params }),
  syncWemall: (params) => http.post('/orders/sync-wemall', null, { params }),
  bulkMarkTest: () => http.post('/orders/bulk-mark-test'),
}

export const settlements = {
  list: (params) => http.get('/settlements', { params }),
  create: (data) => http.post('/settlements', data),
  confirm: (id, data) => http.post(`/settlements/${id}/confirm`, data),
  delete: (id) => http.delete(`/settlements/${id}`),
  notify: (id) => http.post(`/settlements/${id}/notify`),
  sendEmail: (id, includeDetail = false) => http.post(`/settlements/${id}/send-email?include_detail=${includeDetail}`),
  autoSettle: (params) => http.post('/settlements/auto-settle', null, { params }),
  invoiceUrl: (id) => `/api/settlements/${id}/invoice.pdf`,
  detailUrl: (id) => `/api/settlements/${id}/detail.pdf`,
  batchInvoiceUrl: (ids) => `/api/settlements/batch-invoice.zip?ids=${ids.join(',')}`,
  batchDetailUrl: (ids) => `/api/settlements/batch-detail.zip?ids=${ids.join(',')}`,
  yearInvoiceUrl: (year) => `/api/settlements/year-invoice.zip?year=${year}`,
  yearDetailUrl: (year) => `/api/settlements/year-detail.zip?year=${year}`,
}

export const notificationContacts = {
  list: () => http.get('/notification-contacts'),
  create: (data) => http.post('/notification-contacts', data),
  update: (id, data) => http.put(`/notification-contacts/${id}`, data),
  remove: (id) => http.delete(`/notification-contacts/${id}`),
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
  monthlyDaily: (year, month) => http.get('/reports/monthly-daily', { params: { year, month } }),
  yearly: () => http.get('/reports/yearly'),
}
