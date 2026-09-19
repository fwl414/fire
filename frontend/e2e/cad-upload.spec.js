// CAD 图纸上传（建筑详情页 → 上传CAD图纸 → 解析结果）
//
// 这个入口改造前是两个问题叠在一起：
//   ① 前端：el-upload 的 on-change 给的是 UploadFile 对象，页面却按 DOM 事件读
//      event.target.files，选完文件直接抛 TypeError、界面毫无反应（上传功能是坏的）；
//   ② 后端：解析失败时在 except 里返回一份固定的假平面图并标 success，
//      界面照样画出来，还能把 20 个假设备写进设备表。
// 现在：上传链路可用；DWG 明确要求先转 DXF；解析不了就如实报错，不画假图。
const { test, expect } = require('@playwright/test')
const path = require('path')
const { login, currentToken } = require('./helpers')

const DXF_FIXTURE = path.join(__dirname, 'fixtures', 'plan.dxf')

test.describe('CAD 图纸上传', () => {
  test('上传 DXF 能解析出构件，DWG 被明确挡下', async ({ page, request }) => {
    await login(page)
    const token = await currentToken(page)
    const headers = { Authorization: `Bearer ${token}` }

    // 找一个有归属建筑的设备，再确认该建筑有楼层——上传接口需要目标楼层
    const devices = await (await request.get('/api/devices?page_size=20', { headers })).json()
    const device = (devices.items || []).find(item => item.building_id)
    expect(device, '演示数据里应有归属建筑的设备').toBeTruthy()

    const buildingId = device.building_id
    const floors = await (await request.get(`/api/floors?building_id=${buildingId}`, { headers })).json()
    expect(Array.isArray(floors) && floors.length, '该建筑应有楼层').toBeTruthy()

    await page.goto(`/building-detail/${buildingId}`)
    await page.getByRole('button', { name: '上传CAD图纸' }).click()
    const dialog = page.locator('.el-dialog').filter({ hasText: '上传CAD图纸' })
    await expect(dialog).toBeVisible({ timeout: 30_000 })

    let parseCalls = 0
    page.on('request', req => {
      if (req.url().includes('/api/cad/parse')) parseCalls += 1
    })

    // ① DWG：前端直接拦下并要求先转换，不能送去解析
    await dialog.locator('input[type=file]').setInputFiles({
      name: 'plan.dwg',
      mimeType: 'application/octet-stream',
      buffer: Buffer.from('AC1015' + '\u0000'.repeat(64)),
    })
    await expect(page.locator('.el-message').filter({ hasText: 'DWG' })).toBeVisible({ timeout: 15_000 })
    expect(parseCalls, 'DWG 不该被送去解析').toBe(0)

    // ② DXF：解析出真实构件，页面展示统计与图层名
    await dialog.locator('input[type=file]').setInputFiles(DXF_FIXTURE)
    await expect(dialog).toContainText('解析结果', { timeout: 30_000 })
    await expect(dialog).toContainText('墙体')
    // 图层名是解析依据，要在页面上摊开
    await expect(dialog).toContainText('图纸图层')
    await expect(dialog).toContainText('WALL')

    const text = await dialog.innerText()
    expect(text, '不应再出现任何演示数据兜底').not.toContain('演示数据')
    expect(text, '不应再出现假数据提示').not.toContain('ezdxf未安装')
  })
})
