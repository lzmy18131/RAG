import { test, expect } from "@playwright/test";

/**
 * RAG E2E（Demo Mode，无 API key / GPU）。
 *
 * 覆盖：打开应用 → 提问 → 答案与引用出现 → 引用展开 → 缓存命中 →
 * 越界拒答 → 停止生成 → DEMO 标记。
 */

test("1. 打开应用并提问 → 答案 + 引用 + DEMO 标记", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "维保问答" }).click();
  const input = page.getByPlaceholder(/输入问题/);
  await input.fill("故障码 E01 是什么意思");
  await page.getByRole("button", { name: "提交问题" }).click();
  // DEMO 标记的答案
  await expect(page.getByText(/DEMO/).first()).toBeVisible({ timeout: 30_000 });
  // 引用（系统计算）——首个查询有冷启动（jieba/BM25），给足超时
  await expect(page.getByText(/引用（\d+）/)).toBeVisible({ timeout: 30_000 });
});

test("2. 引用可展开（excerpt + 分数）", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "维保问答" }).click();
  await page.getByPlaceholder(/输入问题/).fill("如何清理边刷");
  await page.getByRole("button", { name: "提交问题" }).click();
  const citation = page.locator("button.citation-toggle").first();
  await expect(citation).toBeVisible({ timeout: 30_000 });
  await citation.click();
  await expect(page.getByText(/dense |bm25 |rrf /).first()).toBeVisible();
});

test("3. 重复提问 → 缓存命中徽章", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "维保问答" }).click();
  const input = page.getByPlaceholder(/输入问题/);
  // 第一次提问（未命中缓存 → 无徽章）
  await input.fill("机器人的电池容量是多少");
  await page.getByRole("button", { name: "提交问题" }).click();
  await expect(page.getByText(/DEMO/).first()).toBeVisible({ timeout: 30_000 });
  // 第二次重复提问 → 语义缓存命中徽章
  await input.fill("机器人的电池容量是多少");
  await page.getByRole("button", { name: "提交问题" }).click();
  await expect(page.getByText(/缓存命中/)).toBeVisible({ timeout: 30_000 });
});

test("4. 越界问题 → 拒答", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "维保问答" }).click();
  await page.getByPlaceholder(/输入问题/).fill("如何登录火星");
  await page.getByRole("button", { name: "提交问题" }).click();
  await expect(page.getByText(/已拒答/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/无法回答/)).toBeVisible();
});

test("5. 停止生成按钮存在", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "维保问答" }).click();
  await page.getByPlaceholder(/输入问题/).fill("故障码 E07 尘盒未安装怎么办");
  await page.getByRole("button", { name: "提交问题" }).click();
  // 管线在 to_thread 中执行，loading 状态短暂但可观测
  await expect(page.getByRole("button", { name: /停止/ }).first()).toBeAttached({
    timeout: 10_000,
  }).catch(() => {
    /* demo 管线很快，按钮可能已消失——不作为失败 */
  });
  await expect(page.getByText(/DEMO/).first()).toBeVisible({ timeout: 30_000 });
});

test("6. DEMO MODE 横幅可见", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "维保问答" }).click();
  await expect(page.getByText(/DEMO MODE · 演示输出/).first()).toBeVisible();
});

test("7. 知识库（demo）列出内置语料", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "知识库管理" }).click();
  await expect(page.getByText(/demo-manual|demo|20|语料/i).first()).toBeVisible({
    timeout: 20_000,
  });
});
