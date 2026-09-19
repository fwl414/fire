// 数据大屏端到端：页面必须展示后端真实统计，且不再出现写死的假数据
//
// 改造前后端有 6 处常量（隐患总数 48、整改率 78、水箱水位 82、巡检完成率 92、培训合格率 96、
// 值班人员「张建国（班长）」），前端另有天气/待办/风险排名三处 mock。
// 这里把「不能再出现」也作为断言，防止以后回退。
const { test, expect } = require('@playwright/test')
const { login } = require('./helpers')

const DEMO_USER = process.env.E2E_USERNAME || 'admin'
const DEMO_PASSWORD = process.env.E2E_PASSWORD || '123456'

// 改造前写死的假数据，出现在页面上即视为回归
const LEGACY_FAKE_TEXTS = [
  '巡检完成率',
  '培训合格率',
  '晴 26°C',
  '系统运行正常',
  '张建国（班长）',
  '月度设备维保',
]

// 3D 场景/热力图改造前硬编码的演示建筑，除下表列出的种子建筑外都不应出现在页面上
// （注意：种子建筑「综合办公楼A座 / 实验楼B座 / 学生宿舍C区」是真实台账，不在禁用之列）
const FABRICATED_BUILDINGS = ['图书馆D馆', '体育馆E馆', '行政楼F座', '科研楼G座']

test.describe('数据大屏', () => {
  test('展示后端真实统计且不含写死的假数据', async ({ page }) => {
    await login(page)
    const token = await page.evaluate(() => sessionStorage.getItem('fire_agent_access_token'))
    expect(token).toBeTruthy()
    const headers = { Authorization: `Bearer ${token}` }

    const resp = await page.request.get('/api/dashboard/screen-data', { headers })
    expect(resp.ok(), await resp.text()).toBeTruthy()
    const data = await resp.json()

    await page.goto('/dashboard')
    await expect(page.getByText('智慧消防综合指挥平台')).toBeVisible({ timeout: 30_000 })

    // 全屏模式：大屏页不应出现侧边栏
    await expect(page.locator('.aside')).toHaveCount(0)

    // 顶部状态改为真实指标绑定
    const onlineIndicator = data.indicators.find(i => i.name === '设备在线率')
    expect(onlineIndicator, '后端必须返回设备在线率').toBeTruthy()
    await expect(page.getByText(`设备在线率 ${onlineIndicator.value}%`)).toBeVisible()
    await expect(page.getByText(`今日告警 ${data.alarms.stats.today} 起`)).toBeVisible()

    // 四个运行指标名来自后端
    for (const indicator of data.indicators) {
      await expect(page.getByText(indicator.name, { exact: true }).first()).toBeVisible()
    }

    // 假数据必须消失
    const body = await page.locator('body').innerText()
    for (const fake of LEGACY_FAKE_TEXTS) {
      expect(body, `大屏上不应再出现写死的「${fake}」`).not.toContain(fake)
    }

    // 任何位置都不应漏出 undefined（未加载字段直接渲染的典型症状）
    expect(body, '大屏上不应出现 undefined').not.toContain('undefined')

    // 水源/电气小卡：要么是真实数字，要么是 --，不能是空值
    const miniValues = await page.locator('.water-val, .electric-val').allInnerTexts()
    expect(miniValues.length).toBeGreaterThan(0)
    for (const text of miniValues) {
      expect(text.trim(), `小卡数值不应为空：「${text}」`).toMatch(/^(\d+(\.\d+)?|--)/)
    }

    // 隐患数统计的是全量巡检记录（无时间过滤），文案不能说成「本月」
    expect(body, '隐患口径应为累计而非本月').not.toContain('本月共')
    await expect(page.getByText(/累计共 \d+ 项隐患/)).toBeVisible()

    // GIS 图例必须与 3D/Canvas 的实际渲染色一致，且不列永不出现的「离线」
    const legend = page.locator('.gis-legend span')
    await expect(legend).toHaveCount(3)
    const legendColors = await page.locator('.gis-legend .legend-dot').evaluateAll(
      nodes => nodes.map(node => getComputedStyle(node).backgroundColor)
    )
    expect(legendColors).toEqual([
      'rgb(0, 136, 204)',   // 正常
      'rgb(204, 119, 0)',   // 预警
      'rgb(204, 51, 51)',   // 告警
    ])
    await expect(page.locator('.gis-legend')).not.toContainText('离线')

    // 3D 场景/热力图改造前写死的演示建筑必须消失（建筑名称一律来自后端建筑台账）
    for (const fabricated of FABRICATED_BUILDINGS) {
      expect(body, `3D 场景不应再出现写死的演示建筑「${fabricated}」`).not.toContain(fabricated)
    }

    // 反向守卫：后端返回的建筑名必须真实渲染出来（3D/热力图/建筑分布共用同一份台账）
    for (const building of data.buildings.list) {
      await expect(page.getByText(building.name, { exact: true }).first()).toBeVisible()
    }

    // 隐患治理区块用的是后端 aggregation 结果
    await expect(page.getByText('隐患治理', { exact: false }).first()).toBeVisible()
    if (data.hazards.types.length > 0) {
      await expect(page.getByText(data.hazards.types[0].name, { exact: true }).first()).toBeVisible()
    }
  })

  test('接口不可用时提示失败，而不是伪造数字兜底', async ({ page }) => {
    await login(page)

    // 让大屏接口直接失败：改造前这里会填上 156 台设备 / 91.0% 完好率等编造数字
    await page.route('**/api/dashboard/screen-data**', route => route.abort('failed'))
    await page.goto('/dashboard')
    await expect(page.getByText('智慧消防综合指挥平台')).toBeVisible({ timeout: 30_000 })

    // 必须明确提示加载失败
    await expect(page.getByText(/数据加载失败/)).toBeVisible({ timeout: 30_000 })

    // 并且不得出现任何编造的数字/指标
    const body = await page.locator('body').innerText()
    for (const fabricated of ['156', '142', '设备完好率', '培训完成率', '响应时间', '张队长']) {
      expect(body, `接口失败时不应出现编造值「${fabricated}」`).not.toContain(fabricated)
    }

    // 未加载到数据的小卡必须显示 --：改造前初始 ref 缺字段，会渲染成空白（"/ 台"、" 台"）
    const miniValues = await page.locator('.water-val, .electric-val').allInnerTexts()
    expect(miniValues.length).toBeGreaterThan(0)
    for (const text of miniValues) {
      expect(text.trim(), `未加载数据时应显示 --，而不是空值：「${text}」`).toMatch(/^--/)
    }
  })

  test('首次加载显示遮罩，取到数据后消失', async ({ page }) => {
    await login(page)

    // 拖慢首个请求，让遮罩有足够长的可观察窗口
    await page.route('**/api/dashboard/screen-data**', async route => {
      await new Promise(resolve => setTimeout(resolve, 5000))
      await route.continue()
    })
    await page.goto('/dashboard')

    const mask = page.locator('.el-loading-mask')
    await expect(mask).toBeVisible()
    await expect(mask).toContainText('正在加载实时数据')

    // 页脚「数据更新时间」只在真正取到数据后才有值，且不跟着秒针跳
    const footer = page.locator('.footer-info')
    await expect(footer).toContainText(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/, { timeout: 30_000 })
    const stamp = (await footer.innerText()).match(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/)[0]
    await page.waitForTimeout(3000)
    expect(await footer.innerText(), '页脚写的「数据更新时间」不该每秒变化').toContain(stamp)

    await expect(mask).toHaveCount(0)
  })

  test('接口返回空数据时各面板给出占位文案，而不是留白', async ({ page }) => {
    await login(page)

    // 空租户：各区块都没有内容，此时面板不能只剩一个标题
    await page.route('**/api/dashboard/screen-data**', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({}),
    }))
    await page.goto('/dashboard')
    await expect(page.getByText('智慧消防综合指挥平台')).toBeVisible({ timeout: 30_000 })

    const placeholders = [
      '暂无设备数据',
      '暂无告警趋势数据',
      '暂无实时告警',
      '暂无视频通道',
      '今日暂无事件',
      '暂无运行指标',
    ]
    for (const placeholder of placeholders) {
      await expect(page.getByText(placeholder, { exact: true }), `「${placeholder}」占位文案必须出现`).toBeVisible()
    }
  })

  test('右侧列表可下钻到对应页面', async ({ page }) => {
    await login(page)

    // 用固定数据桩，避免用例依赖当前库里恰好有哪些告警/工单
    await page.route('**/api/dashboard/screen-data**', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        alarms: {
          stats: { critical: 0, high: 0, medium: 0, low: 0, today: 0 },
          trend: [],
          realtime: [{ id: 4247, title: 'E2E实时告警', location: '1层', time: '刚刚', level: 'critical', levelText: '严重' }],
        },
        todos: [{ id: 4242, title: 'E2E待办工单', status: '待受理', level: 'high', location: '1层', deadline: '' }],
        riskRank: [{ id: 4243, name: 'E2E风险楼', value: 88, color: '#cc3333' }],
        todayEvents: [
          { id: 'inspection-4245', title: 'E2E巡检事件', time: '09:10', type: 'inspection' },
          { id: 'ticket-4246', title: 'E2E工单事件', time: '09:20', type: 'maintenance' },
        ],
        videoList: [],
      }),
    }))

    const openScreen = async () => {
      await page.goto('/dashboard')
      await expect(page.getByText('智慧消防综合指挥平台')).toBeVisible({ timeout: 30_000 })
    }

    // 下钻是 SPA 路由跳转，且目标页是懒加载 chunk（首次进入要等 vite 现场编译），
    // 因此用 waitForURL 给足时间，再断言最终地址
    const expectUrl = async (pattern, label) => {
      await page.waitForURL(pattern, { timeout: 30_000 })
      await expect(page, label).toHaveURL(pattern)
    }

    await openScreen()
    await page.locator('.todo-item').first().click()
    await expectUrl(/\/workorders\?order_id=4242/, '待办应下钻到工单详情')

    await openScreen()
    await page.locator('.rank-item').first().click()
    await expectUrl(/\/building-detail\/4243/, '风险排名应下钻到建筑档案')

    await openScreen()
    await page.locator('.alarm-scroll-item').first().click()
    await expectUrl(/\/alert-center/, '实时告警应下钻到告警中心')

    await openScreen()
    await page.locator('.event-item.inspection').first().click()
    await expectUrl(/\/records\?record_id=4245/, '巡检事件应带上记录 id 下钻')
  })

  test('3D 场景里的建筑可悬停可点击下钻', async ({ page }) => {
    await login(page)

    // 固定三栋楼（含经纬度，会按真实坐标铺在场景中），保证场景里一定有可点的建筑
    const buildings = [
      { id: 9001, name: 'E2E北楼', floors: 4, area: 900, status: 'normal', deviceCount: 3, alarmCount: 0, riskScore: 20, latitude: 30.0020, longitude: 120.0020 },
      { id: 9002, name: 'E2E南楼', floors: 6, area: 1600, status: 'alarm', deviceCount: 5, alarmCount: 2, riskScore: 80, latitude: 29.9980, longitude: 120.0020 },
      { id: 9003, name: 'E2E东楼', floors: 3, area: 400, status: 'warning', deviceCount: 2, alarmCount: 1, riskScore: 55, latitude: 30.0020, longitude: 119.9980 },
    ]
    await page.route('**/api/dashboard/screen-data**', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ buildings: { total: buildings.length, list: buildings } }),
    }))

    await page.goto('/dashboard')
    const canvas = page.locator('canvas.webgl-layer')
    await canvas.waitFor({ timeout: 30_000 })
    await page.waitForTimeout(3000)

    // 悬停到建筑上时 canvas 的 cursor 会变成 pointer（同时也是可点提示）。
    // 这里不能「先扫完整张画布、再回头点第一个命中点」，原因有两个：
    //   1) 63 次 move + 读样式在 CI 上要几十秒，会把本用例 90s 的预算耗光（本地没这么慢）；
    //   2) 场景每帧都在渲染，早先记下的坐标会漂移，回头点很可能已经落空。
    // 所以改成「找到就立刻点」，整体给一个有限预算；画布尺寸也可能在面板渲染完才稳定，每轮重量一次。
    const buildingIds = buildings.map(b => b.id).join('|')
    const reached = () => /\/building-detail\/\d+/.test(page.url())
    const deadline = Date.now() + 45_000
    let hovered = 0

    while (!reached() && Date.now() < deadline) {
      const box = await canvas.boundingBox()
      for (let ix = 1; ix <= 9 && !reached(); ix += 1) {
        for (let iy = 1; iy <= 7 && !reached(); iy += 1) {
          const x = box.x + (box.width * ix) / 10
          const y = box.y + (box.height * iy) / 8
          await page.mouse.move(x, y)
          // 画布可能因为上一次点击已跳转而从 DOM 消失，读不到就当这次没命中（别让它把用例炸掉）
          const cursor = await canvas.evaluate(el => el.style.cursor).catch(() => '')
          if (cursor !== 'pointer') continue
          hovered += 1
          await page.mouse.click(x, y)
          // 点击可能触发路由跳转：等一小段让导航落地，跳了就结束，没跳就继续扫
          await page.waitForURL(/\/building-detail\/\d+/, { timeout: 1500 }).catch(() => {})
        }
      }
    }

    expect(hovered, '场景里应能悬停到建筑上（cursor 变 pointer）').toBeGreaterThan(0)
    await expect(page, '点建筑应下钻到该建筑档案').toHaveURL(new RegExp(`/building-detail/(${buildingIds})`))
  })

  test('视频卡拉真实抓拍画面（不是只有图标）', async ({ page }) => {
    await login(page)

    // 1x1 透明 PNG：只要不是坏图，<img> 就会保持加载成功
    const png = Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
      'base64'
    )
    await page.route('**/api/dashboard/screen-data**', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ videoList: [{ id: 4242, name: 'E2E测试通道', online: true }] }),
    }))
    // 只匹配真正的抓拍图请求（token 请求走下面那条）
    let snapshotCalls = 0
    await page.route(/\/api\/video\/channels\/4242\/snapshot\?/, route => {
      snapshotCalls += 1
      return route.fulfill({ status: 200, contentType: 'image/png', body: png })
    })
    await page.route('**/api/video/channels/4242/snapshot-token', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ token: 'e2e-token' }),
    }))

    await page.goto('/dashboard')

    const frame = page.locator('.video-mini-item img.video-frame')
    await expect(frame, '在线通道应显示抓拍画面').toBeVisible({ timeout: 30_000 })
    await expect(frame).toHaveAttribute('src', /\/api\/video\/channels\/4242\/snapshot\?token=e2e-token/)
    await expect.poll(() => snapshotCalls, { timeout: 10_000 }).toBeGreaterThan(0)
    await expect(page.locator('.video-name')).toHaveText('E2E测试通道')
  })

  test('抓拍失败时降级为占位并标离线，而不是显示坏图', async ({ page }) => {
    await login(page)

    await page.route('**/api/dashboard/screen-data**', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ videoList: [{ id: 4243, name: 'E2E故障通道', online: true }] }),
    }))
    await page.route('**/api/video/channels/4243/snapshot-token', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ token: 'e2e-token' }),
    }))
    await page.route(/\/api\/video\/channels\/4243\/snapshot\?/, route => route.fulfill({
      status: 502,
      contentType: 'text/plain',
      body: 'device unreachable',
    }))

    await page.goto('/dashboard')

    const tile = page.locator('.video-mini-item')
    await expect(tile, '抓拍失败应退回占位图标').toHaveClass(/offline/, { timeout: 30_000 })
    await expect(tile.locator('img.video-frame')).toHaveCount(0, { timeout: 30_000 })
    await expect(tile.locator('.video-offline-tip')).toHaveText('离线')
  })
})
