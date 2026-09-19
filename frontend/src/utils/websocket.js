// 实时推送客户端
//
// 握手：连上后首帧发 `{action: "auth", token}`，服务端校验令牌后回 `{type: "auth_ok"}`。
// 身份完全由令牌决定（URL 里不再带 user_id），令牌无效或账号未关联租户时，
// 服务端以 4401/4403 关闭连接。
//
// 这是全局单例：由 App.vue 负责建立与销毁连接，页面只订阅事件（`wsService.on('alert', fn)`）。
import { getToken } from '@/api/core'

const RECONNECT_BASE_DELAY = 1000
const RECONNECT_MAX_DELAY = 30000
// 心跳间隔：nginx 默认 60 秒没有数据就掐断连接，所以要小于它
const HEARTBEAT_INTERVAL = 25000

// 服务端主动拒绝（令牌无效 / 无租户）：重连也不会成功，直接放弃，避免无谓打请求
function isRejected(code) {
  return code >= 4400 && code < 4500
}

class WebSocketService {
  constructor() {
    this.ws = null
    this.callbacks = new Map()
    this.isConnected = false
    this.reconnectAttempts = 0
    this.reconnectTimer = null
    this.heartbeatTimer = null
    this.connectPromise = null
    this.closedByUser = false
  }

  connect() {
    if (this.isConnected) return Promise.resolve(this)
    if (this.connectPromise) return this.connectPromise

    const token = getToken()
    if (!token) return Promise.reject(new Error('未登录，不建立实时连接'))

    this.closedByUser = false
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/notifications`

    this.connectPromise = new Promise((resolve, reject) => {
      let socket
      try {
        socket = new WebSocket(url)
      } catch (error) {
        this.connectPromise = null
        reject(error)
        return
      }
      this.ws = socket

      socket.onopen = () => {
        socket.send(JSON.stringify({ action: 'auth', token }))
      }

      socket.onmessage = (event) => {
        let message
        try {
          message = JSON.parse(event.data)
        } catch (error) {
          console.error('[ws] 消息解析失败:', error)
          return
        }
        if (message.type === 'auth_ok') {
          this.isConnected = true
          this.reconnectAttempts = 0
          this.connectPromise = null
          this.startHeartbeat()
          resolve(this)
          return
        }
        if (message.type === 'pong') return
        this.handleMessage(message)
      }

      // 出错之后一定会触发 onclose，断线处理统一放在 onclose 里
      socket.onerror = () => {}

      socket.onclose = (event) => {
        const rejected = isRejected(event.code)
        const authenticated = this.isConnected
        this.isConnected = false
        this.ws = null
        this.connectPromise = null
        this.stopHeartbeat()

        if (!authenticated && !this.closedByUser) {
          reject(new Error(rejected ? `实时连接被拒绝(${event.code}): ${event.reason}` : '实时连接建立失败'))
        }
        if (this.closedByUser) return
        if (rejected) {
          console.warn(`[ws] 服务端拒绝连接(${event.code}): ${event.reason}，不再重连`)
          return
        }
        this.scheduleReconnect()
      }
    })

    return this.connectPromise
  }

  scheduleReconnect() {
    if (this.reconnectTimer) return
    this.reconnectAttempts += 1
    const delay = Math.min(RECONNECT_BASE_DELAY * 2 ** (this.reconnectAttempts - 1), RECONNECT_MAX_DELAY)
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connect().catch(() => {})
    }, delay)
  }

  startHeartbeat() {
    this.stopHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.isConnected) {
        this.ws.send(JSON.stringify({ action: 'ping' }))
      }
    }, HEARTBEAT_INTERVAL)
  }

  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  on(type, callback) {
    if (!this.callbacks.has(type)) {
      this.callbacks.set(type, [])
    }
    this.callbacks.get(type).push(callback)
  }

  off(type, callback) {
    const callbacks = this.callbacks.get(type)
    if (!callbacks) return
    const index = callbacks.indexOf(callback)
    if (index > -1) callbacks.splice(index, 1)
  }

  handleMessage(message) {
    const callbacks = this.callbacks.get(message.type)
    if (!callbacks || !callbacks.length) return
    callbacks.forEach((callback) => {
      try {
        callback(message.data, message)
      } catch (error) {
        console.error(`[ws] 处理 ${message.type} 事件出错:`, error)
      }
    })
  }

  disconnect() {
    this.closedByUser = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.stopHeartbeat()
    const socket = this.ws
    this.ws = null
    this.isConnected = false
    this.connectPromise = null
    if (socket) socket.close()
  }
}

const wsService = new WebSocketService()

export { wsService, WebSocketService }
