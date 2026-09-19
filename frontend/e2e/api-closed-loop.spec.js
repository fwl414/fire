// 系统级端到端：跨越「前端代理 → 后端 → 数据库 → 文件存储」的完整链路
//
// 注意：用例会在演示库中留下闭环样例数据（告警/工单/报表），可用于演示与验收。
const { test, expect } = require('@playwright/test')

const DEMO_USER = process.env.E2E_USERNAME || 'admin'
const DEMO_PASSWORD = process.env.E2E_PASSWORD || '123456'

async function loginByApi(request) {
  const resp = await request.post('/api/auth/login', {
    form: { username: DEMO_USER, password: DEMO_PASSWORD },
  })
  expect(resp.ok(), `登录失败: ${await resp.text()}`).toBeTruthy()
  const body = await resp.json()
  return { token: body.access_token, headers: { Authorization: `Bearer ${body.access_token}` } }
}

test.describe('系统级闭环（经前端代理调用后端）', () => {
  test('告警 → 工单 → 整改 → 复查 全程闭环', async ({ request }) => {
    const { headers } = await loginByApi(request)
    const deviceId = `E2E-DEV-${Date.now()}`

    // 1) 设备告警上报（自动去重、自动建单）
    const alertResp = await request.post('/api/alert/process', {
      headers,
      form: {
        device_id: deviceId,
        alert_type: 'smoke_high',
        alert_value: '1.6',
        alert_unit: 'mg/m³',
        device_info: JSON.stringify({ code: deviceId, name: 'E2E烟感', location: 'E2E测试区' }),
        building_name: 'E2E测试楼',
      },
    })
    expect(alertResp.ok(), await alertResp.text()).toBeTruthy()
    const alertBody = await alertResp.json()
    const alertId = alertBody.alert_id
    const ticketId = alertBody.workorder.ticket_id
    expect(alertId).toBeTruthy()
    expect(ticketId, '告警必须生成并落库整改工单').toBeTruthy()
    expect(alertBody.dedup.action).toBe('created')

    // 2) 未提交整改前不允许复查
    const earlyVerify = await request.post(`/api/workorders/${ticketId}/verify`, {
      headers,
      data: { result: '通过' },
    })
    expect(earlyVerify.status()).toBe(400)

    // 3) 整改完成提交复查
    const rectify = await request.post(`/api/workorders/${ticketId}/rectify`, {
      headers,
      data: { handle_result: '已现场处置并复测正常' },
    })
    expect(rectify.ok(), await rectify.text()).toBeTruthy()
    expect((await rectify.json()).status).toBe('待复查')

    // 4) 复查通过 → 工单完成且来源告警自动关闭
    const verify = await request.post(`/api/workorders/${ticketId}/verify`, {
      headers,
      data: { result: '通过', note: '复查合格' },
    })
    expect(verify.ok(), await verify.text()).toBeTruthy()
    const verifyBody = await verify.json()
    expect(verifyBody.status).toBe('已完成')
    expect(verifyBody.review_result).toBe('通过')
    expect(verifyBody.closed_alert?.status).toBe('resolved')

    // 5) 回查告警与工单详情，状态应一致
    const alertDetail = await request.get(`/api/alerts/${alertId}`, { headers })
    expect(alertDetail.ok()).toBeTruthy()
    const alertDetailBody = await alertDetail.json()
    expect(alertDetailBody.status).toBe('resolved')
    expect(alertDetailBody.workorder_id).toBe(ticketId)

    const ticketDetail = await request.get(`/api/workorders/${ticketId}`, { headers })
    expect(ticketDetail.ok()).toBeTruthy()
    const ticketBody = await ticketDetail.json()
    expect(ticketBody.status).toBe('已完成')
    expect(ticketBody.source_alert?.id).toBe(alertId)
  })

  test('报表由后端生成、落盘并可受控下载', async ({ request }) => {
    const { headers } = await loginByApi(request)

    const exportResp = await request.post('/api/reports/export', {
      headers,
      data: { report_type: 'inspection', format: 'csv', period: 'month' },
    })
    expect(exportResp.ok(), await exportResp.text()).toBeTruthy()
    const reportId = exportResp.headers()['x-report-id']
    expect(reportId, '导出应返回报表ID').toBeTruthy()
    const exported = await exportResp.body()

    const listResp = await request.get('/api/reports/artifacts', { headers })
    expect(listResp.ok()).toBeTruthy()
    const ids = (await listResp.json()).items.map((item) => item.id)
    expect(ids).toContain(Number(reportId))

    const download = await request.get(`/api/reports/artifacts/${reportId}/download`, { headers })
    expect(download.ok()).toBeTruthy()
    expect(Buffer.compare(await download.body(), exported)).toBe(0)
  })

  test('上传内容与报表不得匿名下载', async ({ request }) => {
    const fileResp = await request.get('/api/files/1')
    expect(fileResp.status()).toBe(401)

    const reportResp = await request.get('/api/reports/artifacts/1/download')
    expect(reportResp.status()).toBe(401)

    // 直连后端校验静态目录已关闭（经前端开发服务器会被 SPA 兜底路由返回 index.html）
    const backendBase = process.env.E2E_BACKEND_URL || `http://127.0.0.1:${process.env.E2E_BACKEND_PORT || 8010}`
    const staticResp = await request.get(`${backendBase}/static/floor_plans/anything.png`)
    expect(staticResp.status()).toBe(404)
  })
})
