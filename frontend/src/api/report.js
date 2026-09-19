import request from './core'

export function reportStatistics(params) {
  return request.get('/api/reports/statistics', { params })
}

export function reportExport(params) {
  return request.post('/api/reports/export', params, { responseType: 'blob' })
}
