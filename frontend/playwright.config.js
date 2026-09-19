// 前端端到端测试配置（Playwright）
//
// 运行前置：
//   1) yarn install          # 安装 @playwright/test（本项目统一用 yarn，勿用 npm install，否则会生成第二套锁文件）
//   2) npx playwright install chromium   # 或使用本机浏览器：E2E_CHANNEL=msedge
//   3) npm run test:e2e
//
//   若 .bin/playwright 未生成（安装中断），可直接执行：
//     node node_modules/@playwright/test/cli.js test
//   无网络下载浏览器时，可复用本机浏览器：E2E_CHANNEL=msedge
//
// 配置会自动拉起后端（独立端口 + 独立 SQLite 库 + DEMO_MODE=true）与前端开发服务器，
// 不会干扰本机正在运行的实例；二者均已运行时直接复用。
const { defineConfig, devices } = require('@playwright/test')
const path = require('path')

const FRONTEND_PORT = Number(process.env.E2E_FRONTEND_PORT || 5273)
const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT || 8010)
const BACKEND_DIR = path.resolve(__dirname, '..', 'backend')
const CHANNEL = process.env.E2E_CHANNEL || undefined
const E2E_DATABASE_URL = process.env.E2E_DATABASE_URL || 'sqlite:///./e2e_test.db'

module.exports = defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://127.0.0.1:${FRONTEND_PORT}`,
    headless: true,
    actionTimeout: 20_000,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    channel: CHANNEL,
  },
  projects: [
    {
      name: 'e2e',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: `python -m uvicorn main:app --host 127.0.0.1 --port ${BACKEND_PORT}`,
      cwd: BACKEND_DIR,
      url: `http://127.0.0.1:${BACKEND_PORT}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
      env: {
        ENV: 'development',
        DEMO_MODE: 'true',
        DEBUG: 'false',
        DATABASE_URL: E2E_DATABASE_URL,
        JWT_SECRET_KEY: 'e2e-test-secret-key-0123456789abcdef',
      },
    },
    {
      command: `npm run dev -- --port ${FRONTEND_PORT} --strictPort`,
      cwd: __dirname,
      url: `http://127.0.0.1:${FRONTEND_PORT}/login`,
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
      env: {
        VITE_API_TARGET: `http://127.0.0.1:${BACKEND_PORT}`,
      },
    },
  ],
})
