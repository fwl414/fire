import request from './core'

// 平台能力与接入表单元数据
export function videoPlatforms() {
  return request.get('/api/video/platforms')
}

// 通道台账
export function videoChannels(params = {}) {
  return request.get('/api/video/channels', { params })
}

export function createVideoChannel(payload) {
  return request.post('/api/video/channels', payload)
}

export function updateVideoChannel(channelId, payload) {
  return request.put(`/api/video/channels/${channelId}`, payload)
}

export function deleteVideoChannel(channelId) {
  return request.delete(`/api/video/channels/${channelId}`)
}

// 真实连通性探测（会实际连接设备）
export function probeVideoChannel(channelId) {
  return request.post(`/api/video/channels/${channelId}/probe`)
}

// 抓拍图需要短时令牌：<img> 无法携带请求头
export function videoSnapshotToken(channelId) {
  return request.post(`/api/video/channels/${channelId}/snapshot-token`)
}

export function controlVideoPtz(channelId, action, speed = 5) {
  return request.post(`/api/video/channels/${channelId}/ptz`, { action, speed })
}

export function videoStreamInfo(channelId, reveal = false) {
  return request.get(`/api/video/channels/${channelId}/stream-info`, { params: { reveal } })
}

// 抓拍一帧做视觉识别，必要时生成告警/工单或转人工复核
export function analyzeVideoChannel(channelId, createAlert = true) {
  return request.post(`/api/video/channels/${channelId}/analyze`, { create_alert: createAlert })
}

// 按时间段检索录像片段（海康 ISAPI 已实现）；平台不支持时返回 supported=false
export function searchVideoRecordings(channelId, payload) {
  return request.post(`/api/video/channels/${channelId}/recordings/search`, payload)
}

// ---------------- GB28181 国标视频接入 ----------------

// 已注册的国标设备（含注册运行态：远端地址、最后心跳、通道数）
export function listGB28181Devices() {
  return request.get('/api/gb28181/devices')
}

export function listGB28181Channels(deviceId) {
  return request.get(`/api/gb28181/devices/${deviceId}/channels`)
}

// 下发目录查询；设备回传后通道列表会被刷新
export function refreshGB28181Catalog(deviceId) {
  return request.post(`/api/gb28181/devices/${deviceId}/refresh-catalog`)
}

// 发起点播（INVITE → 设备推 RTP 到 ZLMediaKit），返回 hls/flv/webrtc 播放地址
export function playGB28181Channel(channelId, prefer = 'flv') {
  return request.post(`/api/gb28181/channels/${channelId}/play`, { prefer })
}

export function stopGB28181Channel(channelId) {
  return request.post(`/api/gb28181/channels/${channelId}/stop`)
}

// action 取 up/down/left/right/zoom_in/zoom_out/stop；也可传 ptz_cmd 原始指令码
export function gb28181Ptz(channelId, action, speed = 5) {
  return request.post(`/api/gb28181/channels/${channelId}/ptz`, { action, speed })
}

export function gb28181ChannelStreamInfo(channelId) {
  return request.get(`/api/gb28181/channels/${channelId}/stream-info`)
}

export function gb28181Status() {
  return request.get('/api/gb28181/status')
}
