import request from './core'

export function analyzeAlert(data) {
  return request.post('/api/intelligence/analyze-alert', data, { hideLoading: true })
}

export function analyzeInspection(data) {
  return request.post('/api/intelligence/analyze-inspection', data)
}

export function generateRectificationPlan(data) {
  return request.post('/api/intelligence/generate-rectification-plan', data)
}

export function diagnoseDevice(data) {
  return request.post('/api/intelligence/diagnose-device', data, { hideLoading: true })
}

export function getDailyBrief(date) {
  return request.get('/api/intelligence/daily-brief', { params: { date } })
}

export function analyzeAlertCorrelation(alerts) {
  return request.post('/api/intelligence/analyze-alert-correlation', { alerts })
}

export function extractExperience(caseData) {
  return request.post('/api/intelligence/extract-experience', { case_data: caseData })
}

export function recommendKnowledge(query) {
  return request.get('/api/intelligence/recommend-knowledge', { params: { query }, hideLoading: true })
}

export function queryData(question) {
  return request.get('/api/intelligence/query-data', { params: { question }, hideLoading: true })
}
