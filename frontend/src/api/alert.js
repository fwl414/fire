import request from './core'

export function alertProcess(params) {
  return request.post('/api/alert/process', params, { headers: { 'Content-Type': 'multipart/form-data' } })
}

export function alertList(params) {
  return request.get('/api/alert/list', { params })
}

export function alertStatistics() {
  return request.get('/api/alert/statistics')
}

export function decisionLogs(params) {
  return request.get('/api/decision-logs', { params })
}

export function decisionLogDetail(logId) {
  return request.get(`/api/decision-logs/${logId}`)
}
