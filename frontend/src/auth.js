import request from './api'

const STORAGE_KEY = 'fire_agent_current_user'
const TOKEN_KEY = 'fire_agent_access_token'
const REFRESH_TOKEN_KEY = 'fire_agent_refresh_token'

export const demoAccounts = []

let useBackendAuth = true

const storage = () => window.sessionStorage

export function getCurrentUser() {
  try { return JSON.parse(storage().getItem(STORAGE_KEY) || 'null') } catch { return null }
}

export function setCurrentUser(user) {
  storage().setItem(STORAGE_KEY, JSON.stringify(user))
  window.dispatchEvent(new CustomEvent('fire-auth-change', { detail: user }))
}

export function clearCurrentUser() {
  storage().removeItem(STORAGE_KEY)
  storage().removeItem(TOKEN_KEY)
  storage().removeItem(REFRESH_TOKEN_KEY)
  window.dispatchEvent(new CustomEvent('fire-auth-change'))
}

export function getAccessToken() {
  return storage().getItem(TOKEN_KEY) || ''
}

export function setAccessToken(token) {
  storage().setItem(TOKEN_KEY, token)
}

export function getRefreshToken() {
  return storage().getItem(REFRESH_TOKEN_KEY) || ''
}

export function setRefreshToken(token) {
  storage().setItem(REFRESH_TOKEN_KEY, token)
}

export async function login(username, password) {
  if (!useBackendAuth) {
    return loginWithDemoAccount(username, password)
  }

  try {
    const params = new URLSearchParams()
    params.append('username', username)
    params.append('password', password)

    const res = await request.post('/api/auth/login', params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      silentError: true
    })

    const data = res.data
    if (data.ok) {
      setAccessToken(data.access_token)
      if (data.refresh_token) {
        setRefreshToken(data.refresh_token)
      }
      const user = {
        username: data.user.username,
        real_name: data.user.real_name,
        role: data.user.role,
        roleName: data.user.role_name,
        displayName: data.user.real_name || data.user.username,
        permissions: data.user.permissions || [],
        email: data.user.email,
        phone: data.user.phone,
        department: data.user.department,
        avatar: data.user.avatar,
        loginAt: new Date().toISOString()
      }
      setCurrentUser(user)
      return { ok: true, user }
    } else {
      return { ok: false, message: data.message || '登录失败' }
    }
  } catch (e) {
    const msg = e?.response?.data?.message || e?.message || '登录失败，请检查服务是否可用'
    return { ok: false, message: msg }
  }
}

export function loginWithDemoAccount() {
  return { ok: false, message: '演示登录已禁用，请使用系统账号登录。' }
}

export async function logout() {
  if (useBackendAuth && getAccessToken()) {
    try {
      await request.post('/api/auth/logout', null, { silentError: true })
    } catch (e) {
      // ignore
    }
  }
  clearCurrentUser()
  return { ok: true }
}

export async function fetchCurrentUser() {
  if (!useBackendAuth || !getAccessToken()) return getCurrentUser()

  try {
    const res = await request.get('/api/auth/me', { silentError: true })
    const data = res.data
    if (data.ok && data.user) {
      const current = getCurrentUser() || {}
      const user = {
        ...current,
        username: data.user.username,
        real_name: data.user.real_name,
        role: data.user.role,
        roleName: data.user.role_name,
        displayName: data.user.real_name || data.user.username,
        permissions: data.user.permissions || [],
        email: data.user.email,
        phone: data.user.phone,
        department: data.user.department,
        avatar: data.user.avatar,
      }
      setCurrentUser(user)
      return user
    }
  } catch (e) {
    clearCurrentUser()
    return null
  }
  clearCurrentUser()
  return null
}

export async function changePassword(oldPassword, newPassword) {
  if (!useBackendAuth || !getAccessToken()) {
    return { ok: false, message: '演示模式不支持修改密码' }
  }

  try {
    const params = new URLSearchParams()
    params.append('old_password', oldPassword)
    params.append('new_password', newPassword)

    const res = await request.post('/api/auth/change-password', params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      silentError: true
    })

    const data = res.data
    return { ok: data.ok, message: data.message }
  } catch (e) {
    const msg = e?.response?.data?.message || e?.message || '修改密码失败'
    return { ok: false, message: msg }
  }
}

export async function getDemoAccountsFromServer() {
  try {
    const res = await request.get('/api/auth/demo-accounts', { silentError: true })
    return res.data?.accounts || []
  } catch (e) {
    return []
  }
}

export async function getRolePermissions() {
  try {
    const res = await request.get('/api/auth/role-permissions', { silentError: true })
    return res.data
  } catch (e) {
    return { roles: [] }
  }
}

export function hasPermission(user, permission) {
  if (!permission) return true
  if (!user) return false
  const perms = user.permissions || []
  if (perms.includes('*')) return true
  if (perms.includes(permission)) return true
  const prefix = permission.split(':')[0]
  if (perms.includes(`${prefix}:*`)) return true
  // 支持 module:action 格式：路由要求 'dashboard' 时，用户有 'dashboard:view' 也允许
  for (const p of perms) {
    if (p.startsWith(permission + ':')) return true
  }
  return false
}

export function canAccessRoute(user, route) {
  const meta = route.meta || {}
  if (meta.public) return true
  if (!user) return false
  if (meta.roles?.length) return meta.roles.includes(user.role)
  if (meta.permission) return hasPermission(user, meta.permission)
  return true
}

export function setAuthMode(backend) {
  useBackendAuth = backend
}
