import request from './core'

// 审计日志列表
export function operationLogs(params = {}) {
  return request.get('/api/system/operation-logs', { params })
}

export function operationLogDashboard() {
  return request.get('/api/system/operation-logs/dashboard')
}

// 登录日志：逐次的登录成功与失败明细（与操作日志同属 logs:view 权限）
export function loginLogs(params = {}) {
  return request.get('/api/system/login-logs', { params })
}

// 重算哈希链，确认审计日志未被篡改
export function verifyOperationLogChain(params = {}) {
  return request.get('/api/system/operation-logs/verify', { params })
}

/**
 * 导出审计日志。
 * 导出接口需要认证头，因此先经 axios 取回二进制，再触发浏览器下载。
 * 后端会把「谁在什么时候导出了哪些日志」本身也记为一条审计日志。
 */
export async function exportOperationLogs(params = {}) {
  const res = await request.get('/api/system/operation-logs/export', {
    params,
    responseType: 'blob',
  })
  const disposition = res.headers['content-disposition'] || ''
  const match = /filename="?([^";]+)"?/.exec(disposition)
  const filename = match ? match[1] : 'operation_logs.csv'

  const url = URL.createObjectURL(res.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  // 立即 revoke 会掐断浏览器尚未接手的下载，延迟释放
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
  return filename
}
