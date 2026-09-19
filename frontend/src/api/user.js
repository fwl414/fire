import request from './core'

export function userList(params) {
  return request.get('/api/system/users', { params })
}

export function userDetail(userId) {
  return request.get(`/api/system/users/${userId}`)
}

export function userCreate(data) {
  const form = new FormData()
  Object.entries(data).forEach(([k, v]) => { if (v !== undefined && v !== null) form.append(k, v) })
  return request.post('/api/system/users', form)
}

export function userUpdate(userId, data) {
  const form = new FormData()
  Object.entries(data).forEach(([k, v]) => { if (v !== undefined && v !== null) form.append(k, v) })
  return request.put(`/api/system/users/${userId}`, form)
}

export function userDelete(userId) {
  return request.delete(`/api/system/users/${userId}`)
}

export function userResetPassword(userId, newPassword) {
  const form = new FormData()
  form.append('new_password', newPassword)
  return request.post(`/api/system/users/${userId}/reset-password`, form)
}

export function userToggleStatus(userId) {
  return request.post(`/api/system/users/${userId}/toggle-status`)
}

export function roleList(params) {
  return request.get('/api/system/roles', { params })
}

export function roleAll() {
  return request.get('/api/system/roles/all')
}

export function roleDetail(roleId) {
  return request.get(`/api/system/roles/${roleId}`)
}

export function roleCreate(data) {
  const form = new FormData()
  Object.entries(data).forEach(([k, v]) => {
    if (v !== undefined && v !== null) {
      form.append(k, Array.isArray(v) ? JSON.stringify(v) : v)
    }
  })
  return request.post('/api/system/roles', form)
}

export function roleUpdate(roleId, data) {
  const form = new FormData()
  Object.entries(data).forEach(([k, v]) => {
    if (v !== undefined && v !== null) {
      form.append(k, Array.isArray(v) ? JSON.stringify(v) : v)
    }
  })
  return request.put(`/api/system/roles/${roleId}`, form)
}

export function roleDelete(roleId) {
  return request.delete(`/api/system/roles/${roleId}`)
}

export function permissionList() {
  return request.get('/api/system/permissions')
}
