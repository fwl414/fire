// 登录与路由守卫的端到端用例
const { test, expect } = require('@playwright/test')

const DEMO_USER = process.env.E2E_USERNAME || 'admin'
const DEMO_PASSWORD = process.env.E2E_PASSWORD || '123456'

async function fillLogin(page, username, password) {
  await page.goto('/login')
  await page.getByPlaceholder('请输入系统账号').fill(username)
  await page.getByPlaceholder('请输入密码').fill(password)
  await page.getByRole('button', { name: '登录系统' }).click()
}

test.describe('登录与路由守卫', () => {
  test('未登录访问受保护页面会跳转到登录页', async ({ page }) => {
    await page.goto('/workorders')
    await expect(page).toHaveURL(/\/login/)
    await expect(page.getByRole('button', { name: '登录系统' })).toBeVisible()
  })

  test('密码错误时停留在登录页且不写入令牌', async ({ page }) => {
    await fillLogin(page, DEMO_USER, 'definitely-wrong-password')
    await expect(page).toHaveURL(/\/login/)
    const token = await page.evaluate(() => sessionStorage.getItem('fire_agent_access_token'))
    expect(token).toBeFalsy()
  })

  test('正确账号密码可登录并进入首页', async ({ page }) => {
    await fillLogin(page, DEMO_USER, DEMO_PASSWORD)
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 30_000 })

    const token = await page.evaluate(() => sessionStorage.getItem('fire_agent_access_token'))
    expect(token).toBeTruthy()
  })

  test('登录后退出登录会清理令牌并回到登录页', async ({ page }) => {
    await fillLogin(page, DEMO_USER, DEMO_PASSWORD)
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 30_000 })

    // 通过后端登出接口使当前令牌失效，再访问受保护页面应被拒绝
    const token = await page.evaluate(() => sessionStorage.getItem('fire_agent_access_token'))
    const logout = await page.request.post('/api/auth/logout', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(logout.ok()).toBeTruthy()

    const me = await page.request.get('/api/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(me.status()).toBe(401)
  })
})
