// 建筑风险页（/building-risk）：接真实预测模型接口
//
// 改造前这一页整页是前端常量：6 条写死的建筑（综合办公楼A座 87 分、实验楼B座 72 分……）、
// 写死的预警表与 30 天趋势，`import request` 导入了却一次都没用。
// 现在页面只消费 /api/risk/model 与 /api/risk/predictions：没训练就明确说没训练、不展示分数。
//
// 注意：演示种子里的建筑名恰好和当年写死的那几条同名（综合办公楼A座等），
// 所以判据不能用「名字出现与否」，而要用「卡片数量是否等于接口返回数量」——
// 旧实现不管接口返回什么，永远渲染 6 条。
const { test, expect } = require('@playwright/test')
const { login, currentToken } = require('./helpers')

test.describe('建筑风险预测', () => {
  test('页面展示真实的模型状态，没训练就不给任何分数', async ({ page }) => {
    await login(page)
    const token = await currentToken(page)
    const headers = { Authorization: `Bearer ${token}` }

    const modelResp = await page.request.get('/api/risk/model', { headers })
    expect(modelResp.ok(), await modelResp.text()).toBeTruthy()
    const model = await modelResp.json()

    await page.goto('/building-risk')
    await expect(page.locator('.page-title')).toHaveText('建筑火灾风险预测')
    await expect(page.locator('.model-card')).toBeVisible({ timeout: 30_000 })

    const predictions = await (await page.request.get('/api/risk/predictions', { headers })).json()
    expect(predictions.trained).toBe(model.trained)

    if (model.trained) {
      // 已训练：卡片数必须与接口返回的建筑数一致（页面不再自己编数据）
      await expect(page.locator('.model-card')).toContainText('已训练')
      await expect(page.locator('.building-card')).toHaveCount(predictions.items.length)
      if (predictions.items.length) {
        const first = page.locator('.building-card').first()
        await expect(first).toContainText(predictions.items[0].buildingName)
        await expect(first).toContainText(`${Math.round(predictions.items[0].probability * 100)}%`)
      }
    } else {
      // 未训练：明确说明，且一条建筑卡片、一个统计卡都不该有
      await expect(page.locator('.model-card')).toContainText('尚未训练')
      await expect(page.locator('.building-card')).toHaveCount(0)
      await expect(page.locator('.stat-row')).toHaveCount(0)
    }
  })
})
