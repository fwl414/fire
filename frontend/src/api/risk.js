import request from './core'

export function riskEnhancedCalculate(params) {
  return request.post('/api/risk/enhanced/calculate', params, { headers: { 'Content-Type': 'multipart/form-data' } })
}

export function riskEnhancedFactors() {
  return request.get('/api/risk/enhanced/factors')
}

// ---------- 风险预测模型（scikit-learn）----------
//
// 这里原先挂的是 /api/buildings/risk、/api/buildings/{id}/risk、/api/buildings/{id}/risk-history
// 三个后端并不存在的路径（调用即 404），且没有任何页面在用。现在换成预测模型的真实接口。

export function riskModelInfo() {
  return request.get('/api/risk/model')
}

export function trainRiskModel(observations) {
  return request.post('/api/risk/model/train', null, { params: { observations } })
}

export function riskPredictions(params) {
  return request.get('/api/risk/predictions', { params })
}

export function riskPrediction(buildingId) {
  return request.get(`/api/risk/prediction/${buildingId}`)
}

export function riskHistory(params) {
  return request.get('/api/risk/history', { params })
}
