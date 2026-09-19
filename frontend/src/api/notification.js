import request from './core'

// 告警外部通知通道（后端整组接口要求 admin 角色）
// 密钥字段（群机器人 Webhook、SMTP 口令）后端只回掩码，更新时留空或传掩码表示「保持不变」。

export function listNotificationChannels() {
  return request.get('/api/settings/notification-channels')
}

export function createNotificationChannel(payload) {
  return request.post('/api/settings/notification-channels', payload)
}

export function updateNotificationChannel(channelId, payload) {
  return request.put(`/api/settings/notification-channels/${channelId}`, payload)
}

export function toggleNotificationChannel(channelId, enabled) {
  return request.post(`/api/settings/notification-channels/${channelId}/toggle`, { enabled })
}

// 立即发一条测试消息，验证通道配置是否真的可达
export function testNotificationChannel(channelId) {
  return request.post(`/api/settings/notification-channels/${channelId}/test`)
}

export function deleteNotificationChannel(channelId) {
  return request.delete(`/api/settings/notification-channels/${channelId}`)
}

// 投递记录：排查「告警产生了但没收到通知」
export function listNotificationDeliveries(params = {}) {
  return request.get('/api/settings/notification-deliveries', { params })
}
