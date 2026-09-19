// 端到端测试公共工具
const DEMO_USER = process.env.E2E_USERNAME || 'admin'
const DEMO_PASSWORD = process.env.E2E_PASSWORD || '123456'

/** 通过登录页完成登录（真实走前端表单与后端接口） */
async function login(page, username = DEMO_USER, password = DEMO_PASSWORD) {
  await page.goto('/login')
  await page.getByPlaceholder('请输入系统账号').fill(username)
  await page.getByPlaceholder('请输入密码').fill(password)
  await page.getByRole('button', { name: '登录系统' }).click()
  // CI 上首次访问要等 Vite dev server 现场转译整个应用（本地有缓存，几秒就够），
  // 30s 会不够用，所以给到 60s
  await page.waitForURL(/\/dashboard/, { timeout: 60_000 })
}

/** 取当前会话令牌 */
async function currentToken(page) {
  // 登录后应用可能还在跳转，直接 evaluate 会撞上导航报 "Execution context was destroyed"；
  // waitForFunction 会在新上下文里重试，等 token 真正出现再取
  await page.waitForFunction(
    () => !!sessionStorage.getItem('fire_agent_access_token'),
    null,
    { timeout: 15_000 }
  )
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
