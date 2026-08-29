import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QAPanel } from "../pages/QAPanel";
import type { QueryResponseV1 } from "../api/client";

vi.mock("../api/client", () => ({
  queryV1: vi.fn(),
}));

import { queryV1 } from "../api/client";

const mockedQuery = vi.mocked(queryV1);

function answeredResponse(overrides: Partial<QueryResponseV1> = {}): QueryResponseV1 {
  return {
    answer: "【DEMO】故障码 E01 表示激光雷达被遮挡，请清理雷达窗口。",
    status: "answered",
    citations: [
      {
        chunk_id: "demo-0003",
        source_file: "data/demo/x1-manual.pdf",
        page: 2,
        content_type: "text",
        content_excerpt: "故障码 E01：表示激光雷达被遮挡。处理方法：检查并清理激光雷达窗口…",
        dense_score: 0.39,
        bm25_score: 4.2,
        rrf_score: 0.033,
        rerank_score: 0.075,
      },
    ],
    sources: [{ chunk_id: "demo-0003" }],
    grounding: { status: "supported", support_ratio: 1.0, unsupported_claims: [], scorer: "reranker" },
    usage: { llm_calls: 1, input_tokens: null, output_tokens: null, total_tokens: null, model: "demo" },
    latency: { total_ms: 120, retrieve_ms: 40, generate_ms: 50 },
    cache: { hit: false, source: "none", corpus_version: "demo" },
    request_id: "req-1",
    trace: null,
    ...overrides,
  };
}

describe("QAPanel", () => {
  beforeEach(() => {
    mockedQuery.mockReset();
  });

  it("renders answer, citations, grounding badge and DEMO banner", async () => {
    mockedQuery.mockResolvedValue(answeredResponse());
    const user = userEvent.setup();
    render(<QAPanel />);

    await user.type(screen.getByPlaceholderText(/输入问题/), "故障码 E01 是什么意思");
    await user.click(screen.getByRole("button", { name: "提交问题" }));

    await waitFor(() => expect(screen.getByText(/DEMO MODE · 演示输出/)).toBeInTheDocument());
    expect(screen.getByText(/E01 表示激光雷达被遮挡/)).toBeInTheDocument();
    // 引用（系统计算）
    expect(screen.getByText(/引用（1）/)).toBeInTheDocument();
    expect(screen.getByText(/x1-manual\.pdf/)).toBeInTheDocument();
    // Grounding badge
    expect(screen.getByText(/Grounding: Supported/)).toBeInTheDocument();
  });

  it("shows cache badge on cache hit", async () => {
    mockedQuery.mockResolvedValue(
      answeredResponse({ cache: { hit: true, source: "exact", corpus_version: "demo" } })
    );
    const user = userEvent.setup();
    render(<QAPanel />);
    await user.type(screen.getByPlaceholderText(/输入问题/), "故障码 E01 是什么意思");
    await user.click(screen.getByRole("button", { name: "提交问题" }));
    await waitFor(() => expect(screen.getByText(/缓存命中 \(精确\)/)).toBeInTheDocument());
  });

  it("shows refused status and abstained grounding", async () => {
    mockedQuery.mockResolvedValue(
      answeredResponse({
        status: "refused",
        answer: "根据现有说明书内容无法回答此问题。",
        grounding: { status: "abstained", support_ratio: 0, unsupported_claims: ["证据不足"], scorer: "reranker" },
      })
    );
    const user = userEvent.setup();
    render(<QAPanel />);
    await user.type(screen.getByPlaceholderText(/输入问题/), "如何登录火星");
    await user.click(screen.getByRole("button", { name: "提交问题" }));
    await waitFor(() => expect(screen.getByText(/已拒答（证据不足）/)).toBeInTheDocument());
    expect(screen.getByText(/Grounding: Abstained/)).toBeInTheDocument();
  });

  it("shows API error box on failure", async () => {
    mockedQuery.mockRejectedValue(new Error("后端服务不可用"));
    const user = userEvent.setup();
    render(<QAPanel />);
    await user.type(screen.getByPlaceholderText(/输入问题/), "故障码");
    await user.click(screen.getByRole("button", { name: "提交问题" }));
    await waitFor(() => expect(screen.getByText(/后端服务不可用/)).toBeInTheDocument());
  });

  it("citation click expands content excerpt with scores", async () => {
    mockedQuery.mockResolvedValue(answeredResponse());
    const user = userEvent.setup();
    render(<QAPanel />);
    await user.type(screen.getByPlaceholderText(/输入问题/), "故障码 E01");
    await user.click(screen.getByRole("button", { name: "提交问题" }));
    await waitFor(() => expect(screen.getByRole("button", { name: /demo-0003/ })).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /demo-0003/ }));
    // 展开的 excerpt 与分数可见
    expect(screen.getByText(/激光雷达窗口/)).toBeInTheDocument();
    expect(screen.getByText(/dense 0.39/)).toBeInTheDocument();
  });

  it("developer mode renders Evidence Panel with hybrid scores", async () => {
    mockedQuery.mockResolvedValue(
      answeredResponse({
        trace: {
          query: "故障码 E01",
          stages: { retrieve_ms: 40 },
          candidates: [
            { chunk_id: "demo-0004", dense_rank: 1, bm25_rank: 2, rrf_score: 0.033, rerank_score: 0.075, rerank_rank: 1, ranking_changed: true },
            { chunk_id: "demo-0003", dense_rank: 3, bm25_rank: 1, rrf_score: 0.031, rerank_score: 0.06, rerank_rank: 2, ranking_changed: true },
          ],
        },
      })
    );
    const user = userEvent.setup();
    render(<QAPanel />);
    await user.type(screen.getByPlaceholderText(/输入问题/), "故障码 E01");
    await user.click(screen.getByRole("checkbox", { name: /Developer/ }));
    await user.click(screen.getByRole("button", { name: "提交问题" }));
    await waitFor(() => expect(screen.getByText(/Evidence Panel/)).toBeInTheDocument());
    expect(screen.getByText(/demo-0004/)).toBeInTheDocument();
  });

  it("stop button aborts loading state", async () => {
    let resolveFn: (v: QueryResponseV1) => void = () => {};
    mockedQuery.mockImplementation(
      () =>
        new Promise<QueryResponseV1>((resolve) => {
          resolveFn = resolve;
        })
    );
    const user = userEvent.setup();
    render(<QAPanel />);
    await user.type(screen.getByPlaceholderText(/输入问题/), "故障码");
    await user.click(screen.getByRole("button", { name: "提交问题" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "⏹ 停止" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "⏹ 停止" }));
    // 停止后不再显示 loading
    expect(screen.queryByText(/正在检索并生成答案/)).not.toBeInTheDocument();
    resolveFn(answeredResponse());
  });
});
