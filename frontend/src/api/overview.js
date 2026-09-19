import request from './core'

export function getOverviewStats() {
  return request.get('/api/overview/stats')
}

export function getAlertList(params) {
  return request.get('/api/alerts/list', { params })
}

export function getDataScreenData() {
  // 大屏 30 秒轮询一次，依赖请求真实发出（core.js 不做 GET 缓存）
  return request.get('/api/dashboard/screen-data')
}
