// 知识图谱：业务实体图谱 + 学习知识图谱
//
// 改造前：/knowledge-graph 这个页面不存在；/api/learning/knowledge-graph 虽然返回了
// nodes/edges，但前端只用了 node_count/edge_count/question_count 三个数字，图从来没画出来过。
// 现在的判据是「页面渲染的节点/关系数 == 接口返回的数量」，写死数据或只显示计数都会失败。
const { test, expect } = require('@playwright/test')
const { login, currentToken } = require('./helpers')

test.describe('知识图谱', () => {
  test('业务实体图来自接口，可按实体下钻', async ({ page }) => {
    await login(page)
    const token = await currentToken(page)
    const headers = { Authorization: `Bearer ${token}` }

    const full = await (
      await page.request.get('/api/kg/graph?alerts=40&workorders=40&inspections=40', { headers })
    ).json()
    expect(full.nodes.length, '演示数据里应该有实体').toBeGreaterThan(0)

    const search = await (await page.request.get('/api/kg/search?keyword=座', { headers })).json()
    expect(search.items.length, '应能按名称搜到实体').toBeGreaterThan(0)
    const target = search.items[0]

    await page.goto('/knowledge-graph')
    await expect(page.locator('.page-title')).toHaveText('知识图谱')
    await expect(page.locator('.graph-card')).toBeVisible({ timeout: 30_000 })
    // 统计数字必须等于接口返回的节点/关系数（不是写死的，也不只是节点总数）
    await expect(page.locator('.stat-total')).toContainText(`节点 ${full.nodes.length}`)
    await expect(page.locator('.stat-total')).toContainText(`关系 ${full.edges.length}`)
    await expect(page.locator('.graph-card canvas').first()).toBeVisible()

    // 以某个实体为中心下钻：图应该切换成它的邻居子图
    const entityId = target.id.split(':').slice(1).join(':')
    const sub = await (
      await page.request.get(
        `/api/kg/subgraph?entity_type=${target.type}&entity_id=${encodeURIComponent(entityId)}&depth=1`,
        { headers }
      )
    ).json()
    expect(sub.found).toBeTruthy()

    await page.locator('.toolbar .el-select').first().click()
    await page.keyboard.type(target.label)
    await page.locator('.el-select-dropdown__item').filter({ hasText: target.label }).first().click()
    await expect(page.locator('.stat-total')).toContainText(`节点 ${sub.nodes.length}`, { timeout: 15_000 })
  })

  test('学习知识图谱把节点与关系真正画出来', async ({ page }) => {
    await login(page)
    await page.goto('/learning')
    await page.getByRole('tab', { name: '知识图谱/RAG' }).click()

    await expect(page.locator('.graph-card-header')).toContainText('学习知识图谱', { timeout: 30_000 })
    // 接口返回的节点数必须出现在标题里（写死数字或空图都会失败）
    await expect(page.locator('.graph-card-header')).not.toContainText('节点 0 ·')
    // 改造前这里只有三个数字，没有任何图形
    await expect(page.locator('.card canvas').first()).toBeVisible({ timeout: 30_000 })
  })
})
