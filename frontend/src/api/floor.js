import request from './core'

export function listFloors(buildingId) {
  return request.get('/api/floors', { params: { building_id: buildingId } })
}

export function getFloorDetail(floorId) {
  return request.get(`/api/floors/${floorId}`)
}

export function createFloor(data) {
  return request.post('/api/floors', data)
}

export function updateFloor(floorId, data) {
  return request.put(`/api/floors/${floorId}`, data)
}

export function deleteFloor(floorId) {
  return request.delete(`/api/floors/${floorId}`)
}

export function uploadFloorPlan(floorId, file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post(`/api/floors/${floorId}/plan`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function updateDevicePosition(deviceId, data) {
  return request.post(`/api/devices/${deviceId}/position`, data)
}
