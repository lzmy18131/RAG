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
      // 启动脚本自动选择解释器：本地 .venv（Windows/POSIX）优先，CI 用系统 python
      command: "python scripts/start_demo_backend.py",
      cwd: "..",
      url: "http://127.0.0.1:8000/health/live",
      reuseExistingServer: true,
      timeout: 90_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      // 直接 node 调用 vite bin：绕过 npm 脚本层（CI 冷启动最稳）；host/port 与 vite.config 严格对齐
      command:
        "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173 --strictPort",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: true,
      timeout: 180_000,
      stdout: "pipe",
      stderr: "pipe",
    },
  ],
});
