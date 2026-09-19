// 后台任务队列端到端：真实服务进程里 worker 是否在跑、任务能否真正执行完
//
// 关键点：TestClient 不会触发 lifespan，只有真实 uvicorn 进程才会启动 worker，
// 因此这里验证的是"上线后真的能跑"，而不是单元测试里的模拟。
const { test, expect } = require('@playwright/test')
const { login } = require('./helpers')

const DEMO_USER = process.env.E2E_USERNAME || 'admin'
const DEMO_PASSWORD = process.env.E2E_PASSWORD || '123456'

async function loginByApi(page) {
  await login(page)
  const token = await page.evaluate(() => sessionStorage.getItem('fire_agent_access_token'))
  expect(token).toBeTruthy()
  return { Authorization: `Bearer ${token}` }
}

async function waitForTask(page, taskId, headers, expectStatus, timeoutMs = 45_000) {
  const deadline = Date.now() + timeoutMs
  let last = null
  while (Date.now() < deadline) {
    const resp = await page.request.get(`/api/tasks/${taskId}`, { headers })
    expect(resp.ok(), await resp.text()).toBeTruthy()
    last = await resp.json()
    if (last.status === expectStatus) return last
    await page.waitForTimeout(500)
  }
  throw new Error(`任务 ${taskId} 未在 ${timeoutMs}ms 内变为 ${expectStatus}，最后状态：${JSON.stringify(last)}`)
}

test.describe('后台任务队列', () => {
  test('批量巡检任务可入队并被执行完成', async ({ page }) => {
    const headers = await loginByApi(page)
    const taskName = `E2E批量巡检-${Date.now().toString().slice(-8)}`

    // 1) 创建任务（修复前这里必然 500：同步上下文里调用 asyncio.create_task）
    const created = await page.request.post('/api/batch-inspection/create', {
      headers,
      data: {
        task_name: taskName,
        building_name: 'E2E测试楼',
        inspection_items: [
          { id: 'I1', location: '1层消防通道', description: '消防通道堵塞，堆放纸箱' },
          { id: 'I2', location: '3层配电室', description: '配电箱周围堆物，电线杂乱' },
          { id: 'I3', location: '屋顶水箱', description: '屋顶水箱巡检正常' },
        ],
      },
    })
    expect(created.ok(), await created.text()).toBeTruthy()
    const createdBody = await created.json()
    expect(createdBody.success).toBeTruthy()
    const taskId = createdBody.task_id
    expect(taskId).toBeTruthy()

    // 2) 后台 worker 应把它执行完
    const finished = await waitForTask(page, taskId, headers, 'success')
    expect(finished.progress).toBe(100)
    expect(finished.task_type).toBe('batch_inspection')

    // 3) 结果来自规则引擎的真实抽取，而不是随机数
    const result = finished.result || {}
    expect(result.completed_count).toBe(3)
    expect(result.results).toHaveLength(3)
    expect(result.results[0].hazards).toContain('消防通道堵塞')

    // 4) 批量巡检页面能看到这条已完成任务
    await page.goto('/batch-inspection')
    await expect(page.getByText(taskName)).toBeVisible({ timeout: 30_000 })
    const row = page.getByRole('row', { name: new RegExp(taskName) })
    await expect(row.getByText('已完成')).toBeVisible()
  })

  test('报表可异步导出并产出可下载产物', async ({ page }) => {
    const headers = await loginByApi(page)

    const created = await page.request.post('/api/reports/export/tasks', {
      headers,
      data: { report_type: 'inspection', period: 'month', format: 'csv' },
    })
    expect(created.ok(), await created.text()).toBeTruthy()
    const taskId = (await created.json()).task_id

    const finished = await waitForTask(page, taskId, headers, 'success')
    const artifactId = finished.result.artifact_id
    expect(artifactId, '异步导出应产出报表产物').toBeTruthy()

    // 5) 产物可受控下载
    const download = await page.request.get(`/api/reports/artifacts/${artifactId}/download`, { headers })
    expect(download.ok(), await download.text()).toBeTruthy()
    const body = await download.body()
    expect(body.length).toBeGreaterThan(0)
  })

  test('任务中心暴露 worker 运行状态', async ({ page }) => {
    const headers = await loginByApi(page)

    const stats = await page.request.get('/api/tasks/stats', { headers })
    expect(stats.ok(), await stats.text()).toBeTruthy()
    const body = await stats.json()
    expect(body.worker.running, '真实服务进程里 worker 应当处于运行中').toBeTruthy()
    expect(body.worker.worker_id).toBeTruthy()
    expect(body.tasks.by_status).toBeTruthy()

    const types = await page.request.get('/api/tasks/types', { headers })
    expect(types.ok(), await types.text()).toBeTruthy()
    expect((await types.json()).items).toContain('batch_inspection')
  })
})
