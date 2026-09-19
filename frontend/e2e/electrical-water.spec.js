// 电气火灾监测 + 消防水源监测：接真实遥测
//
// 改造前这两个页面各有一批 2024-01-15 的写死数据（LD-001 照明回路 / XHS-001 /
// 1号喷淋泵 / 0.35 - 0.65 MPa 等），页面没有 onMounted、没有任何接口调用。
// 现在：
//   - 电气：漏电(remaining_current)/温度(temperature)/电流(current)/电压(voltage) 来自
//     /api/telemetry/latest?device_type=配电箱，值为空则显示「--」，不编数字
//   - 水系统：消火栓压力(pressure) 来自 /api/telemetry/latest?device_type=消火栓
//   - 水箱水位、水泵工况后端确实没有对应指标列，如实显示「暂未接入」空态
const { test, expect } = require('@playwright/test')
const { login, currentToken } = require('./helpers')

const ELECTRICAL_ALERT_TYPES = ['remaining_current', 'temperature_high', 'current_high', 'voltage_high']
const WATER_ALERT_TYPES = ['pressure_low', 'pressure_high']

async function fetchLatest(page, headers, deviceType, metric) {
  const resp = await page.request.get('/api/telemetry/latest', {
    headers,
    params: { device_type: deviceType, metric },
  })
  expect(resp.ok(), await resp.text()).toBeTruthy()
  return resp.json()
}

test.describe('电气火灾监测与水系统监测', () => {
  test('电气火灾监测三个页签接真实遥测，不再是 2024-01-15 的演示数据', async ({ page }) => {
    await login(page)
    const token = await currentToken(page)
    const headers = { Authorization: `Bearer ${token}` }

    const leakage = await fetchLatest(page, headers, '配电箱', 'remaining_current')
    const temperature = await fetchLatest(page, headers, '配电箱', 'temperature')
    const current = await fetchLatest(page, headers, '配电箱', 'current')
    expect(leakage.items.length, '演示库应至少有一台配电箱').toBeGreaterThan(0)

    await page.goto('/electrical-fire')

    // ① 漏电页签卡片数与接口返回一致
    await expect(page.locator('.device-card').first()).toBeVisible({ timeout: 20_000 })
    await expect
      .poll(() => page.locator('.device-card').count(), { timeout: 20_000 })
      .toBe(leakage.items.length)

    // ② 值取自接口，没上报的设备显示「--」而不是编一个数
    const firstItem = leakage.items[0]
    if (firstItem.value === null) {
      await expect(page.locator('.device-card').first()).toContainText('--')
    } else {
      await expect(page.locator('.device-card').first()).toContainText(String(firstItem.value))
    }

    // ③ 写死的演示回路名与日期都不该再出现
    const leakageText = await page.locator('.electrical-fire-page').innerText()
    for (const fake of ['2024-01-15', 'LD-001', 'LD-008 排风回路', '1号配电箱', '正常阈值']) {
      expect(leakageText, `不应再出现写死的演示数据「${fake}」`).not.toContain(fake)
    }

    // ④ 温度页签：卡片数与接口一致，刻度不再是写死的 80/60/40/20/0
    await page.locator('.tab-item', { hasText: '温度监测' }).click()
    await expect
      .poll(() => page.locator('.temp-card').count(), { timeout: 20_000 })
      .toBe(temperature.items.length)
    const tempText = await page.locator('.electrical-fire-page').innerText()
    expect(tempText).not.toContain('WD-001')
    expect(tempText).not.toContain('线缆')

    // ⑤ 电流页签：行数与接口一致，且不再有 A/B/C 三相与负载率（硬件只上报单相电流）
    await page.locator('.tab-item', { hasText: '电流监测' }).click()
    await expect
      .poll(() => page.locator('tbody tr').count(), { timeout: 20_000 })
      .toBe(current.items.length)
    const currentText = await page.locator('.electrical-fire-page').innerText()
    for (const fake of ['A相电流', 'B相电流', 'C相电流', '负载率', 'DL-001 总进线']) {
      expect(currentText, `不应再出现写死的演示数据「${fake}」`).not.toContain(fake)
    }

    // ⑥ 告警页签：只列电气类真实告警，行数与接口一致
    const alerts = await (await page.request.get('/api/alert/list', { headers, params: { limit: 200 } })).json()
    const expectedElectrical = alerts.items.filter(a => ELECTRICAL_ALERT_TYPES.includes(a.alert_type)).length
    await page.locator('.tab-item', { hasText: '告警记录' }).click()
    await expect
      .poll(() => page.locator('tbody tr').count(), { timeout: 20_000 })
      .toBe(expectedElectrical)
    const alarmText = await page.locator('.electrical-fire-page').innerText()
    expect(alarmText).not.toContain('漏电超限')
    expect(alarmText).not.toContain('未处理')
  })

  test('水系统监测消火栓接真实压力，水箱与水泵如实显示未接入', async ({ page }) => {
    await login(page)
    const token = await currentToken(page)
    const headers = { Authorization: `Bearer ${token}` }

    const pressure = await fetchLatest(page, headers, '消火栓', 'pressure')
    expect(pressure.items.length, '演示库应至少有一台消火栓').toBeGreaterThan(0)

    await page.goto('/water-monitor')

    // ① 消火栓卡片数与接口返回一致
    await expect(page.locator('.device-card').first()).toBeVisible({ timeout: 20_000 })
    await expect
      .poll(() => page.locator('.device-card').count(), { timeout: 20_000 })
      .toBe(pressure.items.length)

    // ② 正常范围来自后端阈值（0.3 - 0.6），不再是写死的 0.35 - 0.65
    const hydrantText = await page.locator('.water-monitor-page').innerText()
    expect(hydrantText).not.toContain('0.35 - 0.65')
    expect(hydrantText).not.toContain('2024-01-15')
    expect(hydrantText).not.toContain('XHS-001')
    expect(hydrantText).toContain(`${pressure.thresholds.normal_range[0]} - ${pressure.thresholds.normal_range[1]}`)

    // ③ 水箱水位：后端没有水位指标列，必须如实空态而不是 4 条假水箱
    await page.locator('.tab-item', { hasText: '消防水箱' }).click()
    await expect(page.getByText('水箱水位暂未接入遥测上报通道')).toBeVisible({ timeout: 20_000 })
    await expect(page.locator('.tank-card')).toHaveCount(0)
    const tankText = await page.locator('.water-monitor-page').innerText()
    expect(tankText).not.toContain('1号消防水箱')
    expect(tankText).not.toContain('消防水池B')

    // ④ 水泵工况：同样如实空态，不再是 6 台假水泵
    await page.locator('.tab-item', { hasText: '消防水泵' }).click()
    await expect(page.getByText('消防水泵工况暂未接入遥测上报通道')).toBeVisible({ timeout: 20_000 })
    await expect(page.locator('.pump-card')).toHaveCount(0)
    const pumpText = await page.locator('.water-monitor-page').innerText()
    for (const fake of ['1号喷淋泵', '稳压泵1组', '2号消火栓泵', '远程控制']) {
      expect(pumpText, `不应再出现写死的演示数据「${fake}」`).not.toContain(fake)
    }

    // ⑤ 告警页签：只列水系统真实告警
    const alerts = await (await page.request.get('/api/alert/list', { headers, params: { limit: 200 } })).json()
    const expectedWater = alerts.items.filter(a => WATER_ALERT_TYPES.includes(a.alert_type)).length
    await page.locator('.tab-item', { hasText: '告警记录' }).click()
    await expect
      .poll(() => page.locator('tbody tr').count(), { timeout: 20_000 })
      .toBe(expectedWater)
    const alarmText = await page.locator('.water-monitor-page').innerText()
    expect(alarmText).not.toContain('水位过低')
    expect(alarmText).not.toContain('水泵故障')
  })
})
