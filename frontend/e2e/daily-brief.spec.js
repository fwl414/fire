// 每日安全简报（/daily-brief）
//
// 改造前：后端简报里的告警数、各级数量、处置数、巡检数、隐患数、7 日趋势全是 `random.randint`，
// 「今日重点关注区域」写死了「1号办公楼 / 地下车库 / 消防水泵房」；前端在接口失败时还会塞一份
// 「今日系统运行正常」的假简报。现在页面上的数字必须等于接口返回的真实统计。
const { test, expect } = require('@playwright/test')
const { login, currentToken } = require('./helpers')

test.describe('每日安全简报', () => {
  test('页面数字等于接口返回的真实统计，重点区域由数据推导', async ({ page }) => {
    await login(page)
    const token = await currentToken(page)
    const headers = { Authorization: `Bearer ${token}` }

    const resp = await page.request.get('/api/intelligence/daily-brief', { headers })
    expect(resp.ok(), await resp.text()).toBeTruthy()
    const brief = (await resp.json()).data
    const stats = brief.alert_stats

    await page.goto('/daily-brief')
    await expect(page.locator('.brief-date')).toHaveText(brief.date, { timeout: 30_000 })
    await expect(page.locator('.stat-num.total')).toHaveText(String(stats.total))
    await expect(page.locator('.stat-num.critical')).toHaveText(String(stats.critical))
    await expect(page.locator('.stat-num.high')).toHaveText(String(stats.high))
    await expect(page.locator('.stat-num.medium')).toHaveText(String(stats.medium))
    await expect(page.locator('.summary-text')).toContainText(`共发生各类告警${stats.total}起`)
    await expect(page.locator('.inspection-num').first()).toHaveText(
      String(brief.inspection_stats.inspection_count)
    )

    // 趋势与重点区域都来自接口：条数一致，且不再出现写死的区域名
    const trendBars = page.locator('.trend-bar-item')
    await expect(trendBars).toHaveCount(brief.alarm_trend.length)
    await expect(trendBars.last()).toContainText(String(brief.alarm_trend[brief.alarm_trend.length - 1].count))

    const body = await page.locator('.daily-brief-page').innerText()
    for (const fake of ['1号办公楼', '地下车库', '消防水泵房']) {
      expect(body, `重点区域不应出现写死的「${fake}」`).not.toContain(fake)
    }
  })
})
