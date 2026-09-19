// 关键页面冒烟：登录后各核心路由可正常打开，且不产生失败的接口请求
const { test, expect } = require('@playwright/test')
const { login } = require('./helpers')

const CORE_ROUTES = [
  '/dashboard',
  '/inspection',
  '/records',
  '/workorders',
  '/alert-center',
  '/report-center',
  '/devices',
  '/floor-plan',
]

test.describe('关键页面冒烟', () => {
  test('登录后核心页面均可打开且无失败接口请求', async ({ page }) => {
    await login(page)

    const failedRequests = []
    page.on('response', (response) => {
      const url = response.url()
      if (url.includes('/api/') && response.status() >= 400) {
        failedRequests.push(`${response.status()} ${url}`)
      }
    })

    for (const route of CORE_ROUTES) {
      await page.goto(route)
      await page.waitForLoadState('domcontentloaded')
      await page.waitForTimeout(1200)
      await expect(page).toHaveURL(new RegExp(route.replace('/', '\\/')))
      // 页面应已挂载（未回落到登录页或空白）
      await expect(page.locator('#app')).toBeVisible()
    }

    expect(failedRequests, `存在失败接口请求:\n${failedRequests.join('\n')}`).toEqual([])
  })

  test('楼层平面图使用受控地址加载（不再走 /static）', async ({ page }) => {
    await login(page)

    const requests = []
    page.on('request', (request) => {
      if (request.url().includes('floor_plans') || request.url().includes('/api/files/')) {
        requests.push(request.url())
      }
    })

    await page.goto('/floor-plan')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    const staticRequests = requests.filter((url) => url.includes('/static/'))
    expect(staticRequests, `不应再请求静态目录: ${staticRequests.join(', ')}`).toEqual([])
  })
})
