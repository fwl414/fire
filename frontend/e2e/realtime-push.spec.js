// 实时推送端到端
//
// 改造前 `/ws/notifications/{user_id}` 有三个问题：URL 里自报 user_id、握手不校验令牌、
// 推送全量广播。这里固化两条可观察的行为：
//   1) 令牌无效的连接必须被服务端以 4401 关闭；带有效令牌连接后，服务端用令牌里的租户回话；
//   2) 新告警推送到达后，大屏立即刷新（不必干等 30 秒轮询）。
const { test, expect } = require('@playwright/test')
const { login, currentToken, apiPost } = require('./helpers')

const WS_PATH = '/ws/notifications'
// 页面里的 WebSocket 走 Vite dev server 的 /ws 代理（前端 5273 → 后端 8010）。
// 代理这条路失败时直连后端再试一次，用来区分「代理坏了」还是「后端/环境坏了」。
const BACKEND_WS = process.env.E2E_BACKEND_WS || `ws://127.0.0.1:${process.env.E2E_BACKEND_PORT || 8010}${WS_PATH}`
const POLL_INTERVAL_MS = 30_000
// 只给轮询周期的三分之一：在这个窗口里刷新，只可能来自推送
const PUSH_WINDOW_MS = Math.floor(POLL_INTERVAL_MS / 3)

/** 在浏览器里建一条 WebSocket，按 auth 帧握手，返回 { ok, code, reason, wasClean, readyState } */
async function probeSocket(page, { token, url, timeout = 10_000 }) {
  return page.evaluate(({ path, url, token, timeout }) => {
    return new Promise((resolve) => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const target = url || `${protocol}//${window.location.host}${path}`
      const socket = new WebSocket(target)
      let settled = false
      let sawError = false
      const finish = (result) => {
        if (settled) return
        settled = true
        clearTimeout(timer)
        try { socket.close() } catch { /* 已经关闭 */ }
        resolve({ url: target, ...result })
      }
      const timer = setTimeout(() => finish({ ok: false, timeout: true, readyState: socket.readyState }), timeout)

      socket.onopen = () => socket.send(JSON.stringify({ action: 'auth', token }))
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data)
        if (message.type === 'auth_ok') {
          finish({ ok: true, tenantId: message.data.tenant_id, userId: message.data.user_id })
        }
      }
      // 1006 = 异常关闭（没拿到关闭帧就断了），通常意味着断在中间的代理上而不是后端主动关
      socket.onerror = () => { sawError = true }
      socket.onclose = (event) => finish({
        ok: false,
        code: event.code,
        reason: event.reason,
        wasClean: event.wasClean,
        readyState: socket.readyState,
        sawError,
      })
    })
  }, { path: WS_PATH, url, token, timeout })
}

/** 经代理探测；失败时补一次直连后端的探测，并把两次结果一起带进断言消息 */
async function probeWithDiagnosis(page, { token }) {
  const viaProxy = await probeSocket(page, { token })
  if (viaProxy.ok) return { viaProxy, detail: '' }
  const viaBackend = await probeSocket(page, { token, url: BACKEND_WS })
  return {
    viaProxy,
    viaBackend,
    detail: `｜经代理：${JSON.stringify(viaProxy)}｜直连后端：${JSON.stringify(viaBackend)}`,
  }
}

test.describe('实时推送', () => {
  test('令牌无效的连接被服务端拒绝（4401）', async ({ page }) => {
    await login(page)

    const { viaProxy, detail } = await probeWithDiagnosis(page, { token: 'not-a-real-token' })

    expect(viaProxy.ok, `无效令牌不该连上${detail}`).toBeFalsy()
    expect(viaProxy.code, `令牌无效必须以 4401 关闭${detail}`).toBe(4401)
  })

  test('带令牌连接后服务端按令牌里的身份回话', async ({ page }) => {
    await login(page)
    const token = await currentToken(page)
    expect(token, '登录后应拿到访问令牌').toBeTruthy()

    const { viaProxy, detail } = await probeWithDiagnosis(page, { token })

    expect(viaProxy.ok, `应认证成功${detail}`).toBeTruthy()
    expect(viaProxy.tenantId, '必须带租户，否则收不到任何推送').toBeGreaterThan(0)
  })

  test('新告警推送后大屏立即刷新，不必等 30 秒轮询', async ({ page }) => {
    await login(page)
    const token = await currentToken(page)

    let screenRequests = 0
    page.on('request', (req) => {
      if (req.url().includes('/api/dashboard/screen-data')) screenRequests += 1
    })

    await page.goto('/dashboard')
    await expect(page.getByText('智慧消防综合指挥平台')).toBeVisible({ timeout: 30_000 })
    // 等首次加载完成，再记下基线
    await expect.poll(() => screenRequests, { timeout: 20_000 }).toBeGreaterThan(0)
    const before = screenRequests

    const resp = await apiPost(page, '/api/business/alerts', {
      alert_code: `E2E-WS-${Date.now()}`,
      alert_type: 'E2E实时推送用例',
      severity: 'high',
      description: '验证大屏收到推送后立即刷新',
    }, token)
    expect(resp.ok(), await resp.text()).toBeTruthy()

    // 轮询周期是 30 秒，这里只等一小段：能刷新就只可能来自推送
    try {
      await expect.poll(() => screenRequests, { timeout: PUSH_WINDOW_MS }).toBeGreaterThan(before)
    } catch (error) {
      // 推送没到：把此刻的 WS 状态一起带进失败信息，便于区分「没连上」和「连上了但没推」
      const probe = await probeSocket(page, { token })
      throw new Error(`${error.message}｜同刻 WS 探测：${JSON.stringify(probe)}`)
    }
  })
})
