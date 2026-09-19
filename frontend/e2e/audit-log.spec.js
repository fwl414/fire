// 审计日志端到端：真实数据加载 → 哈希链完整性校验 → 审计导出下载
//
// 关键点是验证「页面展示的就是后端审计日志」，而不是前端 mock：
// 用例先经接口取一次 total，再断言页面显示的条数与之一致。
//
// 说明：全程使用 page.request（与页面同一上下文），不引入独立的 request fixture——
// 浏览器下载会使该 fixture 的回收挂起，与用例本身无关。
const { test, expect } = require('@playwright/test')
const { login } = require('./helpers')

const DEMO_USER = process.env.E2E_USERNAME || 'admin'
const DEMO_PASSWORD = process.env.E2E_PASSWORD || '123456'

test.describe('审计日志', () => {
  test('页面展示真实日志，可校验完整性并导出', async ({ page }) => {
    // 1) 先登录拿到会话（后续经 page.request 调用接口会自动带上 Cookie/Token 由用例显式携带）
    await login(page)
    const token = await page.evaluate(() => sessionStorage.getItem('fire_agent_access_token'))
    expect(token).toBeTruthy()
    const headers = { Authorization: `Bearer ${token}` }

    // 2) 制造一次写操作：确保库中存在已接入哈希链的新记录
    //    （历史遗留记录没有 seq，不计入链校验，这是预期行为）
    const created = await page.request.post('/api/video/channels', {
      headers,
      data: {
        channel_code: `AUDIT-CAM-${Date.now().toString().slice(-8)}`,
        channel_name: '审计用例通道',
        platform: 'mock',
        host: '127.0.0.1',
        port: 80,
      },
    })
    expect(created.ok(), await created.text()).toBeTruthy()
    const channelId = (await created.json()).id
    const removed = await page.request.delete(`/api/video/channels/${channelId}`, { headers })
    expect(removed.ok(), await removed.text()).toBeTruthy()

    // 3) 经接口取基准数据
    const listResp = await page.request.get('/api/system/operation-logs?page=1&page_size=20', { headers })
    expect(listResp.ok(), await listResp.text()).toBeTruthy()
    const list = await listResp.json()
    expect(list.total, '端到端库中应已有操作日志').toBeGreaterThan(0)

    const verifyResp = await page.request.get('/api/system/operation-logs/verify', { headers })
    expect(verifyResp.ok(), await verifyResp.text()).toBeTruthy()
    const verify = await verifyResp.json()
    expect(verify.ok, `审计链应完整：${JSON.stringify(verify.first_broken)}`).toBeTruthy()
    expect(verify.checked, '新写入的记录必须接入哈希链').toBeGreaterThan(0)

    // 4) 页面必须展示与接口一致的条数与真实记录
    await page.goto('/operation-logs')
    await expect(page.getByText(`共 ${list.total} 条`)).toBeVisible({ timeout: 30_000 })

    const firstSeq = list.items[0].seq
    expect(firstSeq, '最新一条应已接入哈希链').toBeTruthy()
    await expect(page.getByRole('cell', { name: String(firstSeq), exact: true }).first()).toBeVisible()

    // 4.1) 顶部指标卡来自后端汇总，而不是写死的 1,268 / 342 / 87 / 36
    const dashResp = await page.request.get('/api/system/operation-logs/dashboard', { headers })
    expect(dashResp.ok(), await dashResp.text()).toBeTruthy()
    const dashboard = await dashResp.json()
    for (const label of ['日志总数', '业务状态变更', '异常与预警', '今日登录用户']) {
      await expect(page.getByText(label, { exact: true })).toBeVisible()
    }
    // 千分位分隔与前端一致，这里统一剥掉非数字再比
    const cardNumbers = (await page.locator('.metric-card strong').allInnerTexts())
      .map(text => Number(text.replace(/[^\d]/g, '')))
    expect(cardNumbers[0], '日志总数应等于接口 total').toBe(dashboard.total)
    expect(cardNumbers[1], '业务状态变更应等于接口 status_changed_count')
      .toBe(dashboard.status_changed_count)
    expect(cardNumbers[2], '异常与预警应等于 warning + error')
      .toBe(dashboard.warning_count + dashboard.error_count)
    expect(cardNumbers[3], '今日登录用户应等于接口 today_login_users')
      .toBe(dashboard.today_login_users)

    // 5) 完整性校验按钮
    await page.getByRole('button', { name: '校验完整性' }).click()
    await expect(page.getByText('审计日志完整性校验通过')).toBeVisible({ timeout: 30_000 })

    // 6) 导出按钮已挂载；导出契约在浏览器会话内直接校验
    //    （不触发真实下载：blob 下载会让 Playwright 的 worker 收尾出现竞态，
    //     与产品行为无关；导出内容/文件名/留痕已由后端用例逐一断言）
    const exportBtn = page.getByRole('button', { name: '导出 CSV' })
    await expect(exportBtn).toBeVisible()
    await expect(exportBtn).toBeEnabled()

    const exportResp = await page.request.get(
      '/api/system/operation-logs/export?format=csv', { headers }
    )
    expect(exportResp.status()).toBe(200)
    const disposition = exportResp.headers()['content-disposition'] || ''
    expect(disposition, '导出响应应带附件文件名').toContain('attachment')
    expect(disposition).toMatch(/operation_logs_\d{14}\.csv/)
    expect((await exportResp.body()).subarray(0, 3), 'CSV 应带 BOM').toEqual(
      Buffer.from([0xef, 0xbb, 0xbf])
    )

    // 7) 导出动作本身要被记入审计日志
    const auditResp = await page.request.get(
      '/api/system/operation-logs?module=操作日志&action=export', { headers }
    )
    expect(auditResp.ok(), await auditResp.text()).toBeTruthy()
    expect((await auditResp.json()).total, '导出行为应留下审计记录').toBeGreaterThan(0)
  })

  test('登录日志页展示真实登录记录而非演示数据', async ({ page }) => {
    // 改造前该标签页是一组写死的 2024-01 演示数据，且「查询」按钮没有绑定任何事件
    await login(page)
    const token = await page.evaluate(() => sessionStorage.getItem('fire_agent_access_token'))
    expect(token).toBeTruthy()
    const headers = { Authorization: `Bearer ${token}` }

    // 登录本身就会写一条成功记录
    const successResp = await page.request.get('/api/system/login-logs?page=1&page_size=20', { headers })
    expect(successResp.ok(), await successResp.text()).toBeTruthy()
    const successList = await successResp.json()
    expect(successList.total, '登录后应至少有一条登录日志').toBeGreaterThan(0)
    expect(successList.items[0].username).toBe(DEMO_USER)
    expect(successList.items[0].status).toBe('success')

    // 一次失败登录也要留痕。
    // 账号名每次唯一：固定名会被反复失败后锁定，之后返回的失败原因变成「账号已锁定」，
    // 断言就不再验证「失败登录逐次留痕」这件事了。
    const probeUser = `e2e-probe-${Date.now()}`
    const failed = await page.request.post('/api/auth/login', {
      form: { username: probeUser, password: 'not-a-password' },
    })
    expect(failed.status()).toBe(401)

    const failedResp = await page.request.get(
      '/api/system/login-logs?status=failed&page=1&page_size=200', { headers }
    )
    const failedList = await failedResp.json()
    const probe = failedList.items.find(i => i.username === probeUser)
    expect(probe, '失败登录必须逐次留痕').toBeTruthy()
    expect(probe.fail_reason).toBe('用户不存在')
    // 未接入 IP 库，只对可判定的内网/回环地址下结论（本地请求即属此类），不编造城市
    expect(['本机', '内网'], '只在能判定时才给出归属地').toContain(probe.location)

    // 页面展示的是不带筛选的完整列表（含上面那条失败记录）
    const allResp = await page.request.get('/api/system/login-logs?page=1&page_size=20', { headers })
    const allList = await allResp.json()
    expect(allList.total).toBeGreaterThan(successList.total)

    // 页面接的是同一份数据
    await page.goto('/operation-logs')
    await page.locator('.tab-item', { hasText: '登录日志' }).click()
    await expect(page.getByText(`共 ${allList.total} 条`)).toBeVisible({ timeout: 30_000 })
    await expect(page.getByRole('cell', { name: DEMO_USER, exact: true }).first()).toBeVisible()

    // 演示数据必须消失
    const body = await page.locator('body').innerText()
    for (const faked of [
      '2024-01-15 14:32:18',
      '192.168.1.100',
      '114.88.120.56',
      '内网-办公楼',
      'zhangjg',
      'test01',
    ]) {
      expect(body, `登录日志不应再出现写死的演示数据「${faked}」`).not.toContain(faked)
    }
  })
})
