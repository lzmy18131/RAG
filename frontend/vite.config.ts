import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      // 开发代理到后端（与 Playwright webServer 对齐）
      "/api": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/version": "http://127.0.0.1:8000",
      "/metrics": "http://127.0.0.1:8000",
    },
  },
})
