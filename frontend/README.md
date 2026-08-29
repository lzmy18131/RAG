# Frontend — RAG Web Console

React 19 + TypeScript + Vite 的单页应用：多模态可信 RAG 智能硬件维保知识助手的交互界面。

> 本文件只描述前端本身的角色/结构/开发方式；完整项目说明见仓库根 [README.md](../README.md)。

## Role

前端是 RAG 系统的交互层，覆盖完整应用链路：

- **维保问答**：v1 契约查询（answer / citations / grounding / usage / latency / cache / request_id）+ SSE 流式 + 停止生成。
- **Evidence Panel（developer）**：展示 Dense rank / BM25 rank / RRF score / Rerank score / chunk_id / page，证明 Hybrid Retrieval 真实实现。
- **Citation UI**：点击引用展开 source / page / excerpt + 各检索通道分数。
- **知识库管理**：文档列表与上传（真实模式；Demo Mode 内置合成语料）。
- **实验评估**：从 Experiment Registry（`runs/`）真实读取；无 run 时显示 "no verified run"。
- **系统状态**：embedding / reranker / vector store / gateway / cache / corpus version（不含 secret）。
- **DEMO 标记**：Demo Mode 下显示明确横幅与输出标记，不伪装真实维修结论。

## Stack

- React 19 + TypeScript（`tsc -b` 严格构建）+ Vite 8
- 无路由库：5 个页面用 state 导航（`App.tsx`）
- Vitest + React Testing Library（单元测试）；Playwright（E2E）
- oxlint（lint 门禁）

## API Integration

- API 客户端：`src/api/client.ts`（`fetch` 封装，类型化响应）
- 默认后端地址：`VITE_API_BASE`（未设置时回退 `http://127.0.0.1:8000`，跨域由后端 CORS 放行）
- 开发代理（`vite.config.ts`）：`/api`、`/health`、`/version`、`/metrics` → `http://127.0.0.1:8000`
- 查询走 **v1 契约**：`POST /api/v1/query`（`query / top_k / document_ids / debug / cache`）
- 流式走 **SSE**：`POST /api/v1/query/stream`（stage 事件 + demo token 流）；停止生成取消请求，后端 `CancelledError` 不包装 500

## Routes

state 导航页面（`src/pages/`）：

| 页面 | 组件 | 说明 |
|---|---|---|
| 仪表盘 | `Dashboard.tsx` | 入口/概览 |
| 维保问答 | `QAPanel.tsx` | 核心 Q&A（v1 + SSE + 引用 + Grounding 徽章 + 缓存徽章 + 停止按钮） |
| 知识库管理 | `KnowledgeBase.tsx` | 文档列表/上传（demo 内置语料） |
| 实验评估 | `Experiments.tsx` | 读取 `runs/` Experiment Registry |
| 系统状态 | `SystemStatus.tsx` | 组件/网关/缓存状态（不含 secret） |

## Development

```bash
npm ci
npm run dev            # http://127.0.0.1:5173（代理 /api → :8000）
```

后端（Demo Mode，无需 API key / GPU / 模型下载）：

```bash
cd .. && DEMO_MODE=true .venv/Scripts/python -m uvicorn main:app --port 8000
```

## Testing

```bash
npm run lint           # oxlint
npm run typecheck      # tsc -b --noEmit
npm test               # Vitest + RTL（QAPanel 等 7 用例）
npm run test:e2e       # Playwright（需后端 + 前端 dev server，见 playwright.config.ts webServer）
```

Playwright E2E 通过 `playwright.config.ts` 的 webServer 自动启动：后端（`python scripts/start_demo_backend.py`，自动选择解释器并清除 PYTHONPATH 污染）与前端（直接 `node node_modules/vite/bin/vite.js`），无需手工起服务。

## Build

```bash
npm run build          # tsc -b && vite build → dist/
```

CI（`.github/workflows/ci.yml` frontend job）：lint → typecheck → vitest → build → npm audit；E2E job 另跑 Playwright（Demo Mode）。
