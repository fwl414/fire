// 系统监控（真实主机指标）
//
// 改造前这个页面用 `Math.random()` 每 3 秒改写 CPU / 内存 / 网络，趋势曲线也是随机数滚出来的；
// 峰值/均值、数据库连接数（42/200）、QPS/TPS、接口调用量、进程列表全是写死的常量。
// 现在所有数字都来自后端真实采集（backend/services/system_metrics_service.py）。
const { test, expect } = require('@playwright/test')
const { login, currentToken } = require('./helpers')

test.describe('系统监控', () => {
  test('页面数字来自真实采集，不是随机数或写死的演示数据', async ({ page }) => {
    await login(page)
    const token = await currentToken(page)
    const headers = { Authorization: `Bearer ${token}` }

    // 后端指标：CPU 与网络速率靠两次采样差值，首次没有基准
    const first = await (await page.request.get('/api/system/host', { headers })).json()
    expect(first.cpu === null || typeof first.cpu === 'number').toBeTruthy()
    const second = await (await page.request.get('/api/system/host', { headers })).json()
    expect(typeof second.memory).toBe('number')
    expect(typeof second.disk).toBe('number')

    await page.goto('/system-monitor')

    // 统计卡：磁盘使用率要和接口返回的一致
    await expect(page.locator('.stat-card').nth(2)).toContainText(`${second.disk}%`)

    // 原来那批写死的服务名与运行时长不该再出现
    const body = await page.locator('.system-monitor-page').innerText()
    for (const fake of ['32天15小时', 'MinIO', 'RabbitMQ', 'Nginx', 'MySQL']) {
      expect(body, `不应再出现写死的演示数据「${fake}」`).not.toContain(fake)
    }

    // 服务状态页签：来自 /api/system/health 的真实检查项
    await expect(page.locator('.service-card').first()).toBeVisible({ timeout: 20_000 })

    // 性能监控：真实进程列表（不再是 python3 - FastAPI / mysqld / redis-server 这五条）
    await page.locator('.tab-item', { hasText: '性能监控' }).click()
    const processCard = page.locator('.content-card').filter({ hasText: '资源占用排行' })
    await expect(processCard.locator('tbody tr').first()).toBeVisible({ timeout: 20_000 })
    await expect(processCard).not.toContainText('python3 - FastAPI')

    // 数据库状态：真实表名，且不再有 InnoDB / 碎片率这类编出来的列
    await page.locator('.tab-item', { hasText: '数据库状态' }).click()
    const dbCard = page.locator('.content-card').filter({ hasText: '数据表记录数' })
    await expect(dbCard).toContainText('devices', { timeout: 20_000 })
    await expect(dbCard).not.toContainText('InnoDB')

    // 接口监控：真实请求计数，本页面刚请求过的接口应在排行里
    await page.locator('.tab-item', { hasText: '接口监控' }).click()
    const apiCard = page.locator('.content-card').filter({ hasText: '接口调用排行' })
    await expect(apiCard.locator('tbody tr').first()).toBeVisible({ timeout: 20_000 })
    await expect(apiCard).toContainText('/api/')
    // 原来是写死的「总请求数 128,650」「最近24小时统计」
    await expect(apiCard).not.toContainText('128,650')
  })
})
