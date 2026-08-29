import { defineConfig } from "@playwright/test";

/**
 * RAG E2E（Demo Mode，无 API key / GPU / 模型下载）。
 *
 * webServer 自动启动：
 *   - 后端：DEMO_MODE=true uvicorn main:app（:8000）
 *   - 前端：vite dev（:5173，代理 /api → :8000）
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command:
        'python -c "import os;os.environ[\'DEMO_MODE\']=\'true\';from main import app;import uvicorn;uvicorn.run(app,host=\'127.0.0.1\',port=8000)"',
      cwd: "..",
      url: "http://127.0.0.1:8000/health/live",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
