import request from './core'

export function batchInspectionList(params) {
  return request.get('/api/batch-inspection/list', { params })
}

export function batchInspectionCreate(data) {
  return request.post('/api/batch-inspection/create', data)
}

export function batchInspectionDetail(taskId) {
  return request.get(`/api/batch-inspection/${taskId}`)
}

export function batchInspectionProgress(taskId) {
  return request.get(`/api/batch-inspection/${taskId}/progress`)
}
