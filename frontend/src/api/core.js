import axios from "axios"
import { ElMessage, ElNotification } from "element-plus"
import { ref } from "vue"

export const globalLoading = ref(false)
let loadingCount = 0
let loadingTimer = null

function showLoading() {
  loadingCount++
  if (loadingCount === 1) {
    if (loadingTimer) clearTimeout(loadingTimer)
    loadingTimer = setTimeout(() => {
      globalLoading.value = true
    }, 300)
  }
}

function hideLoading() {
  loadingCount = Math.max(0, loadingCount - 1)
  if (loadingCount === 0) {
    if (loadingTimer) {
      clearTimeout(loadingTimer)
      loadingTimer = null
    }
    globalLoading.value = false
  }
}

const request = axios.create({
  baseURL: "",
  timeout: 120000,
})

function getToken() {
  try {
    return sessionStorage.getItem('fire_agent_access_token') || ''
  } catch {
    return ''
  }
}

request.interceptors.request.use(
  config => {
    if (!config.hideLoading) {
      showLoading()
    }

    const token = getToken()
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }

    return config
  },
  error => {
    hideLoading()
    return Promise.reject(error)
  }
)

function normalizeErrorMessage(error) {
  const data = error?.response?.data
  const candidates = [
    data?.message,
    data?.error,
    data?.detail,
    error?.message,
  ]
  let msg = candidates.find(v => v !== undefined && v !== null && String(v).trim() !== "")
  if (Array.isArray(msg)) {
    msg = msg.map(item => item?.msg || item?.message || JSON.stringify(item)).join("；")
  } else if (typeof msg === "object") {
    msg = msg?.msg || msg?.message || JSON.stringify(msg)
  }
  msg = String(msg || "服务暂时不可用，请稍后重试。").trim()
  return msg || "服务暂时不可用，请稍后重试。"
}

request.interceptors.response.use(
  response => {
    if (!response.config.hideLoading) {
      hideLoading()
    }
    return response
  },
  error => {
    hideLoading()

    const status = error?.response?.status
    const msg = normalizeErrorMessage(error)
    
    if (status === 401) {
      try {
        sessionStorage.removeItem('fire_agent_current_user')
        sessionStorage.removeItem('fire_agent_access_token')
        sessionStorage.removeItem('fire_agent_refresh_token')
      } catch {}
      // 触发认证状态变更事件，通知 App.vue 等组件更新登录态
      window.dispatchEvent(new CustomEvent('fire-auth-change'))
      // 避免在登录页或公开页面重复跳转
      const currentPath = window.location.pathname
      if (currentPath !== '/login') {
        ElNotification({
          title: '登录已过期',
          message: '请重新登录',
          type: 'warning',
          duration: 3000,
        })
        // 延迟跳转，让通知先显示
        setTimeout(() => {
          window.location.href = '/login'
        }, 300)
      }
    } else if (status === 403) {
      if (!error?.config?.silentError) {
        ElNotification({
          title: '权限不足',
          message: msg || '您没有权限执行此操作',
          type: 'warning',
          duration: 3000,
        })
      }
    } else if (status === 404) {
      if (!error?.config?.silentError) {
        ElMessage.warning(msg || '请求的资源不存在')
      }
    } else if (status >= 500) {
      if (!error?.config?.silentError) {
        ElNotification({
          title: '服务器错误',
          message: msg || '服务器暂时不可用，请稍后重试',
          type: 'error',
          duration: 4000,
        })
      }
    } else if (error?.code === 'ERR_CANCELED') {
      return Promise.reject(error)
    } else if (error?.code === 'ECONNABORTED' || error?.message?.includes('timeout')) {
      if (!error?.config?.silentError) {
        ElNotification({
          title: '请求超时',
          message: '网络连接超时，请检查网络后重试',
          type: 'error',
          duration: 4000,
        })
      }
    } else if (error?.code === 'ERR_NETWORK' || !error?.response) {
      if (!error?.config?.silentError) {
        ElNotification({
          title: '网络错误',
          message: '网络连接失败，请检查网络设置',
          type: 'error',
          duration: 4000,
        })
      }
    } else {
      if (!error?.config?.silentError) {
        ElMessage.error(msg)
      }
    }
    return Promise.reject(error)
  }
)

export default request
export { request, getToken, normalizeErrorMessage }

/**
 * 受控文件下载：后端上传内容必须携带认证头访问，而 <img> 无法自定义请求头，
 * 因此先经 axios（自动附加 Token）取回二进制，再转换为 objectURL。
 * 调用方负责在合适时机 URL.revokeObjectURL 释放。
 */
export async function fetchObjectUrl(url) {
  if (!url) return ''
  if (typeof url !== 'string' || !url.startsWith('/api/files/')) return url
  const res = await request.get(url, { responseType: 'blob', hideLoading: true })
  return URL.createObjectURL(res.data)
}
