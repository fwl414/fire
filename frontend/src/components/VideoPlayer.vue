<template>
  <div class="video-player">
    <video
      ref="videoEl"
      class="player-video"
      controls
      muted
      autoplay
      playsinline
      :poster="poster"
      @error="onNativeError"
    ></video>

    <div v-if="!url" class="player-mask">未选择国标通道</div>
    <div v-else-if="errorMessage" class="player-mask error">{{ errorMessage }}</div>
    <div v-else-if="loading" class="player-mask">正在拉流…</div>

    <div v-if="title" class="player-title">{{ title }}</div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'

// 通用播放器：按地址后缀自动选择 HLS / HTTP-FLV 播放方式，
// 两种库都按需动态加载，不进主包（前端体积影响可控）。
const props = defineProps({
  url: { type: String, default: '' },
  // auto | hls | flv | native
  mode: { type: String, default: 'auto' },
  title: { type: String, default: '' },
  poster: { type: String, default: '' },
})

const emit = defineEmits(['playing', 'failed'])

const videoEl = ref(null)
const loading = ref(false)
const errorMessage = ref('')

let hlsInstance = null
let flvPlayer = null

function destroy() {
  if (flvPlayer) {
    try {
      flvPlayer.pause()
      flvPlayer.unload()
      flvPlayer.detachMediaElement()
      flvPlayer.destroy()
    } catch (error) {
      // 销毁失败不影响后续重新加载
    }
    flvPlayer = null
  }
  if (hlsInstance) {
    try {
      hlsInstance.destroy()
    } catch (error) {
      // 同上
    }
    hlsInstance = null
  }
  const video = videoEl.value
  if (video) {
    try {
      video.removeAttribute('src')
      video.load()
    } catch (error) {
      // 忽略
    }
  }
}

function detectMode(url) {
  if (props.mode && props.mode !== 'auto') return props.mode
  const path = String(url).split('?')[0].toLowerCase()
  if (path.endsWith('.m3u8')) return 'hls'
  if (path.endsWith('.flv')) return 'flv'
  return 'native'
}

function fail(message) {
  errorMessage.value = message
  loading.value = false
  emit('failed', message)
}

function onNativeError() {
  if (!props.url) return
  fail('无法播放该地址（设备可能未上流，或流媒体服务器不可达）')
}

async function loadStream() {
  destroy()
  errorMessage.value = ''
  if (!props.url) return

  const mode = detectMode(props.url)
  const video = videoEl.value
  if (!video) return

  loading.value = true
  try {
    if (mode === 'flv') {
      const module = await import('flv.js')
      const flvjs = module.default || module
      if (!flvjs.isSupported()) throw new Error('当前浏览器不支持 HTTP-FLV，请改用 HLS 播放')
      flvPlayer = flvjs.createPlayer({ type: 'flv', url: props.url, isLive: true, hasAudio: true })
      flvPlayer.attachMediaElement(video)
      flvPlayer.on(flvjs.Events.ERROR, (type, detail) => fail(`FLV 拉流失败：${detail || type}`))
      flvPlayer.load()
      flvPlayer.play()
    } else if (mode === 'hls') {
      if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = props.url
        await video.play().catch(() => {})
      } else {
        const module = await import('hls.js')
        const Hls = module.default || module
        if (!Hls.isSupported()) throw new Error('当前浏览器不支持 HLS 播放')
        hlsInstance = new Hls({ liveDurationInfinity: true, lowLatencyMode: true })
        hlsInstance.on(Hls.Events.ERROR, (event, data) => {
          if (data?.fatal) fail(`HLS 拉流失败：${data.details}`)
        })
        hlsInstance.loadSource(props.url)
        hlsInstance.attachMedia(video)
        hlsInstance.on(Hls.Events.MANIFEST_PARSED, () => {
          video.play().catch(() => {})
        })
      }
    } else {
      video.src = props.url
      await video.play().catch(() => {})
    }
    loading.value = false
    emit('playing')
  } catch (error) {
    fail(error?.message || '拉流失败')
  }
}

watch(() => [props.url, props.mode], loadStream)

onBeforeUnmount(destroy)
</script>

<style scoped>
.video-player {
  position: relative;
  width: 100%;
  height: 100%;
  background: #0f172a;
  border-radius: 8px;
  overflow: hidden;
}

.player-video {
  width: 100%;
  height: 100%;
  display: block;
  background: #000;
}

.player-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 13px;
  background: rgba(15, 23, 42, 0.72);
  text-align: center;
  padding: 12px;
}

.player-mask.error {
  color: #fecaca;
  background: rgba(127, 29, 29, 0.72);
}

.player-title {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 6px 10px;
  font-size: 12px;
  color: #e2e8f0;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.65) 0%, transparent 100%);
  pointer-events: none;
}
</style>
