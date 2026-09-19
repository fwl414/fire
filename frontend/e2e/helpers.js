// 端到端测试公共工具
const DEMO_USER = process.env.E2E_USERNAME || 'admin'
const DEMO_PASSWORD = process.env.E2E_PASSWORD || '123456'

/** 通过登录页完成登录（真实走前端表单与后端接口） */
async function login(page, username = DEMO_USER, password = DEMO_PASSWORD) {
  await page.goto('/login')
  await page.getByPlaceholder('请输入系统账号').fill(username)
  await page.getByPlaceholder('请输入密码').fill(password)
  await page.getByRole('button', { name: '登录系统' }).click()
  await page.waitForURL(/\/dashboard/, { timeout: 30_000 })
}

/** 取当前会话令牌 */
async function currentToken(page) {
  return page.evaluate(() => sessionStorage.getItem('fire_agent_access_token'))
}

/** 以已登录身份调用后端接口 */
async function apiPost(page, url, data, token) {
  return page.request.post(url, {
    headers: { Authorization: `Bearer ${token}` },
    data,
  })
}

module.exports = { DEMO_USER, DEMO_PASSWORD, login, currentToken, apiPost }
