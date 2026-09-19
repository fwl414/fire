// 设备智能诊断（建筑详情页 → 选中设备 → 智能诊断）
//
// 改造前这个弹窗有两处问题：① 接口返回的是 { ok, data } 信封，页面只取了信封 →
// 状态/原因全是空、置信度显示 NaN；② 「可能故障原因」的百分比是写死的模板值，
// 却当作本次诊断的概率展示，判断依据还断言「设备已使用超过5年」「安装环境通风不良」
// 这类我们并不知道的事实。现在权重按设备台账数据推导并标明来源。
const { test, expect } = require('@playwright/test')
const { login, currentToken } = require('./helpers')

test.describe('设备智能诊断', () => {
  test('诊断弹窗展示真实内容，权重标明来源', async ({ page }) => {
    await login(page)
    const token = await currentToken(page)
    const headers = { Authorization: `Bearer ${token}` }

    const devices = await (await page.request.get('/api/devices?page_size=10', { headers })).json()
    const device = (devices.items || []).find(item => item.building_id)
    expect(device, '演示数据里应有归属建筑的设备').toBeTruthy()

    await page.goto(`/building-detail/${device.building_id}`)
    const firstDevice = page.locator('.device-item').first()
    await expect(firstDevice).toBeVisible({ timeout: 30_000 })
    await firstDevice.click()

    await page.getByRole('button', { name: '智能诊断' }).click()
    const dialog = page.locator('.el-dialog').filter({ hasText: '设备诊断' })
    await expect(dialog).toBeVisible({ timeout: 15_000 })

    // 信封取对了才有内容：状态、权重、依据都要在
    await expect(dialog).toContainText('设备状态')
    await expect(dialog).toContainText('参考权重')
    await expect(dialog).toContainText(/按设备数据|知识库经验/)

    const text = await dialog.innerText()
    expect(text, '置信度不应是 NaN（以前只取到信封时的表现）').not.toContain('NaN')
    expect(text, '不应再凭空断言设备年限').not.toContain('设备已使用超过5年')
    expect(text, '不应再凭空断言安装环境').not.toContain('安装环境通风不良')
    // 判断依据要么是设备真实数字，要么明确标注为知识库经验
    expect(text).toMatch(/已投用|距上次维保|知识库经验/)
  })
})
