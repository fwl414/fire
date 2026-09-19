import request from './core'

export function getGisBuildings() {
  return request.get('/api/gis/buildings')
}

export function getGisDevices() {
  return request.get('/api/gis/devices')
}

export function getGisHeatmap() {
  return request.get('/api/gis/heatmap')
}

export function getGisDashboard() {
  return request.get('/api/gis/dashboard')
}
