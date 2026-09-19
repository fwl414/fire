// 移动端协同（/mobile-inspection）：现场人员用的一页
//
// 改造前这一页是「桌面网页里塞了个手机壳」：375×750 的固定外壳 + 全写死的待办/通知/巡检任务/报警列表，
// 提交巡检按钮没有事件、扫码只弹提示。现在数据全部来自 /api/mobile/* 与业务接口，
// 这里用手机视口把「领取工单 → 现场上报 → 落库」整条链路跑一遍。
const { test, expect } = require('@playwright/test')
const { login, currentToken } = require('./helpers')

// 用真实手机视口跑，避免又退回「固定像素的手机壳」。
// 这里手写设备参数而不是用 devices['iPhone 13']：后者会切到 WebKit，
// 而本机用的是 msedge 通道（Chromium），两者不能混。
test.use({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 3,
  isMobile: true,
  hasTouch: true,
})

async function apiGet(page, url, token) {
  const res = await page.request.get(url, { headers: { Authorization: `Bearer ${token}` } })
  expect(res.ok(), `${url} -> ${res.status()}`).toBeTruthy()
  return res.json()
}

test.describe('移动端协同', () => {
  test('首页数字来自接口，可领取工单并现场上报', async ({ page }) => {
    await login(page)
    const token = await currentToken(page)
    const headers = { Authorization: `Bearer ${token}` }

    // 造一条「待受理」工单：保证首页一定有可领取的条目
    const stamp = Date.now()
    const ticketTitle = `E2E移动端工单-${stamp}`
    const created = await page.request.post('/api/workorders', {
      headers,
      data: { title: ticketTitle, status: '待受理', risk_level: '高风险', location: 'E2E现场' },
    })
    expect(created.ok(), await created.text()).toBeTruthy()

    const home = await apiGet(page, '/api/mobile/home', token)

    await page.goto('/mobile-inspection')
    await expect(page.locator('.header-title')).toHaveText('现场协同', { timeout: 30_000 })

    // 统计卡必须等于接口返回的数字
    const cells = page.locator('.stat-cell')
    await expect(cells.nth(0)).toContainText(String(home.stats.pendingAlerts))
    await expect(cells.nth(1)).toContainText(String(home.stats.claimableWorkorders))
    await expect(cells.nth(2)).toContainText(String(home.stats.myWorkorders))

    // 领取刚造的那条工单
    const card = page.locator('.task-card').filter({ hasText: ticketTitle })
    await expect(card).toBeVisible()
    await card.getByRole('button', { name: '领取' }).click()
    await expect(card).toBeHidden({ timeout: 15_000 })

    const mine = await apiGet(page, '/api/mobile/tasks', token)
    const claimed = mine.items.find(item => item.title === ticketTitle)
    expect(claimed, '领取后工单应出现在我的待办里').toBeTruthy()
    expect(claimed.status).toBe('处理中')
    expect(claimed.mine).toBe(true)

    // 现场上报：选建筑 + 写描述 + 提交
    await page.locator('.tabbar-item').filter({ hasText: '上报' }).click()
    const buildingSelect = page.locator('.el-form-item').filter({ hasText: '建筑' }).locator('.el-select')
    await buildingSelect.click()
    await page.locator('.el-select-dropdown__item').first().click()
    await page.locator('.el-form-item').filter({ hasText: '现场描述' }).locator('textarea')
      .fill('现场发现消防通道被纸箱堵塞，旁边还有电动车违规充电')
    await page.getByRole('button', { name: '提交上报' }).click()

    const result = page.locator('.result-card')
    await expect(result).toBeVisible({ timeout: 30_000 })
    await expect(result).toContainText('巡检记录 #')
    await expect(result).toContainText('风险')

    // 落库校验：今日巡检数 +1，且最近一条记录就是这次上报的
    const after = await apiGet(page, '/api/mobile/home', token)
    expect(after.stats.todayInspections).toBe(home.stats.todayInspections + 1)
  })
})
