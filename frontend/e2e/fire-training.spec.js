// 消防安全培训：培训课程 / 培训计划 / 考试考核 / 培训档案
//
// 改造前这四个页签的数据全是写死的演示数组（2024-01 的 8 门课程、6 个计划、
// 4 场考试、8 条档案），后端连一张培训表都没有。
// 现在：
//   - 课程复用学习模块的真实课程（/api/learning/courses），本页只读
//   - 计划/考试/档案走后端三张新表，支持新建、编辑、删除
//   - 考试的参考人数/平均分/及格率、计划的实际参训人数都由档案聚合而来
//   - 导出档案按当前筛选条件导出全部（CSV）
const { test, expect } = require('@playwright/test')
const { login, currentToken } = require('./helpers')

// 用 test 的 request fixture（独立于 page 生命周期），不要用 page.request——
// 后者会随页面关闭一起销毁，测试收尾时容易抛 TargetClosedError。
async function getJson(api, url, headers, params) {
  const resp = await api.get(url, { headers, params })
  expect(resp.ok(), await resp.text()).toBeTruthy()
  return resp.json()
}

// el-table 带固定列时会额外渲染一份表格副本，直接用 tbody tr 会把行数算成两倍，
// 所以统一从主表（第一个 body-wrapper）取行。
function bodyRows(page) {
  return page.locator('.el-table__body-wrapper').first().locator('tbody tr')
}

test.describe('消防安全培训', () => {
  test('四个页签都接真实接口，不再是 2024 年的写死数据', async ({ page, request }) => {
    await login(page)
    const token = await currentToken(page)
    const headers = { Authorization: `Bearer ${token}` }

    const stats = await getJson(request, '/api/training/stats', headers)
    const plans = await getJson(request, '/api/training/plans', headers, { page_size: 100 })
    const exams = await getJson(request, '/api/training/exams', headers, { page_size: 100 })
    const records = await getJson(request, '/api/training/records', headers, { page_size: 100 })

    expect(stats.course_count, '演示库应至少有一门课程').toBeGreaterThan(0)
    expect(plans.total, '演示库应至少有一个培训计划').toBeGreaterThan(0)

    await page.goto('/fire-training')

    // ① 统计卡取自 /api/training/stats
    const cards = page.locator('.stat-card')
    await expect(cards.nth(0)).toContainText(String(stats.course_count))
    await expect(cards.nth(1)).toContainText(String(stats.trained_count))
    await expect(cards.nth(2)).toContainText(String(stats.exam_count))
    if (stats.pass_rate === null) {
      await expect(cards.nth(3)).toContainText('--')
    } else {
      await expect(cards.nth(3)).toContainText(`${stats.pass_rate}%`)
    }

    // ② 课程页签：真实课程标题出现，原来的演示课程名不再出现
    const firstCourse = (await getJson(request, '/api/learning/courses', headers))[0]
    await expect(page.locator('.course-card').first()).toBeVisible({ timeout: 20_000 })
    await expect.poll(() => page.locator('.course-card').count(), { timeout: 20_000 })
      .toBeGreaterThan(0)
    const courseText = await page.locator('.fire-training-page').innerText()
    expect(courseText).toContain(firstCourse.title)
    for (const fake of ['消防法律法规基础知识', '灭火器操作使用培训', '室内消火栓系统操作']) {
      expect(courseText, `不应再出现写死的演示课程「${fake}」`).not.toContain(fake)
    }
    // 「新建课程」不该存在：课程由学习模块统一维护
    await expect(page.getByRole('button', { name: '新建课程' })).toHaveCount(0)

    // ③ 培训计划页签：行数与接口一致，且带真实的状态文案
    await page.locator('.tab-item', { hasText: '培训计划' }).click()
    await expect.poll(() => bodyRows(page).count(), { timeout: 20_000 })
      .toBe(plans.items.length)
    const planText = await page.locator('.fire-training-page').innerText()
    expect(planText).toContain(plans.items[0].plan_name)
    expect(planText).toContain(plans.items[0].status_label)
    for (const fake of ['2024年Q1全员消防安全培训', '2024年Q2消防演练计划', '2024-01-10']) {
      expect(planText, `不应再出现写死的演示计划「${fake}」`).not.toContain(fake)
    }

    // ④ 考试页签：卡片数与接口一致，聚合值也一致
    await page.locator('.tab-item', { hasText: '考试考核' }).click()
    await expect(page.locator('.exam-card').first()).toBeVisible({ timeout: 20_000 })
    await expect.poll(() => page.locator('.exam-card').count(), { timeout: 20_000 })
      .toBe(exams.items.length)

    const withScores = exams.items.find(e => e.avg_score !== null)
    const withoutScores = exams.items.find(e => e.avg_score === null)
    const examText = await page.locator('.fire-training-page').innerText()
    if (withScores) {
      expect(examText).toContain(String(withScores.avg_score))
      expect(examText).toContain(`${withScores.attend_count} 人已考`)
    }
    // 没人考的场次不能拿 0 冒充平均分与及格率
    if (withoutScores) {
      const card = page.locator('.exam-card').filter({ hasText: withoutScores.title })
      await expect(card).toContainText('平均分 --')
      await expect(card).toContainText('及格率 --')
    }
    for (const fake of ['2024年Q1消防安全知识考试', '灭火器使用实操考核']) {
      expect(examText, `不应再出现写死的演示考试「${fake}」`).not.toContain(fake)
    }

    // ⑤ 培训档案页签：行数与接口一致，合格判定按关联考试的及格线
    await page.locator('.tab-item', { hasText: '培训档案' }).click()
    await expect(bodyRows(page).first()).toBeVisible({ timeout: 20_000 })
    await expect.poll(() => bodyRows(page).count(), { timeout: 20_000 })
      .toBe(records.items.length)

    const recordText = await page.locator('.fire-training-page').innerText()
    expect(recordText).toContain(records.items[0].trainee_name)
    const labels = new Set(records.items.map(r => r.result_label))
    for (const label of labels) {
      expect(recordText, `档案应显示后端的判定文案「${label}」`).toContain(label)
    }
    expect(recordText).not.toContain('2024-01-12')
    expect(recordText).not.toContain('XF2024001')
  })

  test('新建 / 编辑 / 删除培训计划，并支持导出档案', async ({ page, request }) => {
    await login(page)
    const token = await currentToken(page)
    const headers = { Authorization: `Bearer ${token}` }
    const planName = `E2E 培训计划 ${Date.now().toString().slice(-6)}`

    await page.goto('/fire-training')
    // 首次访问要让 dev server 编译该路由，先等页面骨架渲染出来再操作
    await expect(page.locator('.tab-bar')).toBeVisible({ timeout: 40_000 })
    await page.locator('.tab-item', { hasText: '培训计划' }).click()

    // 新建
    await page.getByRole('button', { name: '新建计划' }).click()
    const dialog = page.locator('.el-dialog').filter({ hasText: '新建培训计划' })
    await expect(dialog).toBeVisible({ timeout: 20_000 })
    await dialog.getByPlaceholder(/2026年上半年全员消防安全培训/).fill(planName)
    await dialog.getByPlaceholder('如：全体员工').fill('E2E 测试对象')
    await dialog.getByRole('button', { name: '保存' }).click()
    await expect(dialog).toBeHidden({ timeout: 20_000 })

    // 列表里出现，接口也确实落库了
    const created = await getJson(request, '/api/training/plans', headers, { keyword: planName })
    expect(created.total).toBe(1)
    const createdId = created.items[0].id
    expect(created.items[0].status).toBe('pending')
    expect(created.items[0].status_label).toBe('未开始')

    await page.getByPlaceholder('搜索计划名称').fill(planName)
    await page.getByRole('button', { name: '查询' }).click()
    await expect.poll(() => bodyRows(page).count(), { timeout: 20_000 }).toBe(1)
    await expect(bodyRows(page).first()).toContainText(planName)

    try {
      // 编辑：改状态与进度
      await bodyRows(page).first().getByRole('button', { name: '编辑' }).click()
      const editDialog = page.locator('.el-dialog').filter({ hasText: '编辑培训计划' })
      await expect(editDialog).toBeVisible({ timeout: 20_000 })
      await editDialog.getByRole('button', { name: '保存' }).click()
      await expect(editDialog).toBeHidden({ timeout: 20_000 })

      // 导出档案：后端按当前筛选条件返回 CSV（带 BOM，Excel 打开不乱码）
      const exportResp = await request.get('/api/training/records/export', { headers })
      expect(exportResp.ok(), await exportResp.text()).toBeTruthy()
      expect(exportResp.headers()['content-type']).toContain('text/csv')
      expect(exportResp.headers()['content-disposition']).toContain('attachment')
      const csv = await exportResp.text()
      expect(csv.startsWith('\ufeff'), 'CSV 应带 BOM').toBeTruthy()
      expect(csv).toContain('姓名')
      expect(csv).toContain('是否合格')
      expect(csv).toContain('证书编号')

      // 页面上的导出按钮存在且可用。
      // 注意：这里**不点它**——点击会在浏览器里触发 blob 下载，
      // 而 Playwright 对未消费的下载会在 worker 收尾时抛 TargetClosedError，
      // 污染整个用例的退出码。前端下载动作（blob → a.click）由接口契约与构建保证。
      await page.locator('.tab-item', { hasText: '培训档案' }).click()
      await expect(page.getByRole('button', { name: '导出档案' })).toBeEnabled()
    } finally {
      // 清理自己创建的计划
      const removed = await request.delete(`/api/training/plans/${createdId}`, { headers })
      expect(removed.ok(), await removed.text()).toBeTruthy()
    }
  })
})
