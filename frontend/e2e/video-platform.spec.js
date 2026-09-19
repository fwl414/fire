// 视频平台接入端到端：通道台账 → 真实探测 → 抓拍图受控下发 → 前端轮询展示
//
// 使用 mock 平台（本地合成画面），因此不依赖真实摄像头也能验证完整链路；
// 用例结束会清理自己创建的通道。
const { test, expect } = require('@playwright/test')
const { login } = require('./helpers')

const DEMO_USER = process.env.E2E_USERNAME || 'admin'
const DEMO_PASSWORD = process.env.E2E_PASSWORD || '123456'

async function loginByApi(request) {
  const resp = await request.post('/api/auth/login', {
    form: { username: DEMO_USER, password: DEMO_PASSWORD },
  })
  expect(resp.ok(), `登录失败: ${await resp.text()}`).toBeTruthy()
  const body = await resp.json()
  return { headers: { Authorization: `Bearer ${body.access_token}` } }
}

test.describe('视频平台接入', () => {
  test('通道台账 → 探测 → 抓拍图 → 页面轮询展示', async ({ request, page }) => {
    const { headers } = await loginByApi(request)
    const code = `E2E-CAM-${Date.now().toString().slice(-8)}`

    // 1) 新增通道：密码必须只进不出
    const created = await request.post('/api/video/channels', {
      headers,
      data: {
        channel_code: code,
        channel_name: 'E2E 模拟摄像头',
        location: 'E2E 测试区域',
        platform: 'mock',
        host: '127.0.0.1',
        port: 80,
        username: 'admin',
        password: 'Camera@123',
      },
    })
    expect(created.ok(), await created.text()).toBeTruthy()
    const channel = await created.json()
    expect(channel.has_password).toBeTruthy()
    expect(channel.password).toBeUndefined()
    expect(channel.password_cipher).toBeUndefined()

    try {
      // 2) 真实探测
      const probe = await request.post(`/api/video/channels/${channel.id}/probe`, { headers })
      expect(probe.ok(), await probe.text()).toBeTruthy()
      expect((await probe.json()).online).toBeTruthy()

      // 3) 抓拍令牌 + 抓拍图（走前端代理，等价于浏览器请求路径）
      const tokenResp = await request.post(`/api/video/channels/${channel.id}/snapshot-token`, {
        headers,
      })
      expect(tokenResp.ok(), await tokenResp.text()).toBeTruthy()
      const { token, snapshot_url } = await tokenResp.json()
      expect(token).toBeTruthy()

      const snapshot = await request.get(snapshot_url)
      expect(snapshot.ok(), await snapshot.text()).toBeTruthy()
      expect(snapshot.headers()['content-type']).toContain('image/jpeg')

      // 无令牌访问必须被拒绝
      const anonymous = await request.get(`/api/video/channels/${channel.id}/snapshot?token=bogus`)
      expect(anonymous.status()).toBe(401)

      // 4) 页面真实展示抓拍画面
      await login(page)
      await page.goto('/video-monitor')
      await expect(page.getByText('视频监控').first()).toBeVisible()

      await page.getByPlaceholder('搜索摄像头').fill(code)
      const frame = page.locator('img.video-frame').first()
      await expect(frame).toBeVisible({ timeout: 30_000 })
      await expect(frame).toHaveAttribute('src', /\/api\/video\/channels\/\d+\/snapshot\?token=/)
      // 图片确实解码成功（naturalWidth > 0 才算真的显示了画面）
      await expect
        .poll(() => frame.evaluate(img => img.naturalWidth), { timeout: 30_000 })
        .toBeGreaterThan(0)

      await expect(page.getByText('抓拍画面轮询中')).toBeVisible()
      await expect(page.getByText('尚未接入视频通道')).toHaveCount(0)
    } finally {
      const removed = await request.delete(`/api/video/channels/${channel.id}`, { headers })
      expect(removed.ok(), await removed.text()).toBeTruthy()
    }
  })

  test('告警联动与录像回放接真实数据，不再是写死的演示片段', async ({ request, page }) => {
    const { headers } = await loginByApi(request)
    const code = `E2E-REC-${Date.now().toString().slice(-8)}`

    const created = await request.post('/api/video/channels', {
      headers,
      data: {
        channel_code: code,
        channel_name: 'E2E 录像检索通道',
        location: 'E2E 测试区域',
        platform: 'mock',
        host: '127.0.0.1',
        port: 80,
        username: 'admin',
        password: 'Camera@123',
      },
    })
    expect(created.ok(), await created.text()).toBeTruthy()
    const channel = await created.json()

    try {
      await login(page)
      await page.goto('/video-monitor')

      // ① 告警联动：行数与本租户真实告警一致
      const alarms = await (await request.get('/api/alert/list?limit=50', { headers })).json()
      await page.locator('.tab-item', { hasText: '告警联动' }).click()
      const alarmPanel = page.locator('.tab-content').filter({ hasText: '告警时间' })
      await expect(alarmPanel).toBeVisible({ timeout: 20_000 })
      await expect
        .poll(() => alarmPanel.locator('tbody tr').count(), { timeout: 20_000 })
        .toBe(alarms.items.length)

      // 写死的演示告警（摄像头名 / 处置状态 / 告警类型）都不该再出现
      const pageText = await page.locator('.video-monitor-page').innerText()
      for (const fake of ['SP-005 研发大厅', 'SP-009 车库入口', '人员入侵', '已误报']) {
        expect(pageText, `不应再出现写死的演示数据「${fake}」`).not.toContain(fake)
      }

      // ② 录像回放：模拟平台没有录像检索能力，必须如实告知而不是给一份片段清单
      await page.locator('.tab-item', { hasText: '录像回放' }).click()
      await page.locator('.tab-content').getByRole('button', { name: '检索' }).click()
      await expect(page.getByText('未实现录像检索')).toBeVisible({ timeout: 20_000 })

      const playbackText = await page.locator('.video-monitor-page').innerText()
      expect(playbackText).not.toContain('2024-01-15')
      expect(playbackText).not.toContain('常规录像')
      expect(playbackText).toContain('共 0 个片段')
    } finally {
      const removed = await request.delete(`/api/video/channels/${channel.id}`, { headers })
      expect(removed.ok(), await removed.text()).toBeTruthy()
    }
  })
})
