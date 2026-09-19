import request from './core'

export function multimodalAnalyze(params) {
  return request.post('/api/multimodal/analyze', params, { headers: { 'Content-Type': 'multipart/form-data' } })
}

export function multimodalInterpretAlert(params) {
  return request.post('/api/multimodal/interpret-alert', params, { headers: { 'Content-Type': 'multipart/form-data' } })
}

export function multimodalUpdateRisk(params) {
  return request.post('/api/multimodal/update-risk', params, { headers: { 'Content-Type': 'multipart/form-data' } })
}
