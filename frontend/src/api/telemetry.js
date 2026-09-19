import request from './core'

// 按设备类型取每台设备某指标的最新值 + 阈值规则（来自 DeviceTelemetry 真实时序表）
export function latestTelemetry(deviceType, metric) {
  return request.get('/api/telemetry/latest', { params: { device_type: deviceType, metric } })
}

export function telemetryAnalyzeSingle(params) {
  return request.post('/api/telemetry/analyze-single', params, { headers: { 'Content-Type': 'multipart/form-data' } })
}

export function telemetryAnalyzeHistory(params) {
  return request.post('/api/telemetry/analyze-history', params, { headers: { 'Content-Type': 'multipart/form-data' } })
}

export function telemetryAnalyzeMultiple(params) {
  return request.post('/api/telemetry/analyze-multiple', params, { headers: { 'Content-Type': 'multipart/form-data' } })
}
