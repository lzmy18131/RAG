import { useState } from "react";
import { queryV1 } from "../api/client";
import type { CitationV1, QueryResponseV1 } from "../api/client";

const EXAMPLES = [
  "设备无法开机怎么办？",
  "机器人会不会从楼梯摔下去？",
  "如何清理边刷？",
];

const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  answered: { label: "已回答（已验证）", cls: "badge-success" },
  refused: { label: "已拒答（证据不足）", cls: "badge-warning" },
  fallback: { label: "降级回答", cls: "badge-warning" },
};

const GROUNDING_CONFIG: Record<string, { label: string; cls: string }> = {
  supported: { label: "Supported", cls: "badge-success" },
  warning: { label: "Warning", cls: "badge-warning" },
  abstained: { label: "Abstained", cls: "badge-neutral" },
};

const TYPE_ICONS: Record<string, string> = {
  text: "📝",
  image: "🖼️",
  table: "📊",
};

export function QAPanel() {
  const [question, setQuestion] = useState("");
  const [documentIds, setDocumentIds] = useState<string[]>([]);
  const [debug, setDebug] = useState(false);
  const [loading, setLoading] = useState(false);
  const [aborted, setAborted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResponseV1 | null>(null);
  const [expandedCitation, setExpandedCitation] = useState<string | null>(null);

  const doSubmit = async (q: string) => {
    if (!q.trim()) return;
    setError(null);
    setResult(null);
    setExpandedCitation(null);
    setLoading(true);
    setAborted(false);
    try {
      const data = await queryV1({
        query: q,
        top_k: 5,
        document_ids: documentIds.length ? documentIds : null,
        debug,
        cache: true,
      });
      if (!aborted) setResult(data);
    } catch (e: any) {
      if (!aborted) setError(e.message || "请求失败");
    } finally {
      if (!aborted) setLoading(false);
    }
  };

  const stop = () => {
    setAborted(true);
    setLoading(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      doSubmit(question);
    }
  };

  const statusCfg = result ? STATUS_CONFIG[result.status] || { label: result.status, cls: "badge-neutral" } : null;
  const groundingCfg = result ? GROUNDING_CONFIG[result.grounding.status] || { label: result.grounding.status, cls: "badge-neutral" } : null;

  return (
    <div>
      <h1 className="mb-3">维保问答</h1>
      <p className="section-subtitle">
        Hybrid Retrieval → Reranker → 生成 → 确定性接地 → 引用验证（v1 管线；语义缓存加速）
      </p>

      {/* DEMO MODE 横幅（Demo 模式可见；真实模式不显示） */}
      <div className="demo-banner" style={{ marginBottom: 12 }}>
        DEMO MODE · 演示输出（合成语料 + 确定性模型），非真实维修结论
      </div>

      {/* Input area */}
      <div className="card mb-4">
        <textarea
          className="textarea"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题，例如：故障码 E01 是什么意思？"
          rows={3}
        />
        <div className="flex-row mt-3" style={{ flexWrap: "wrap", gap: 8 }}>
          <button
            className="btn btn-primary"
            onClick={() => doSubmit(question)}
            disabled={loading || !question.trim()}
          >
            {loading ? "查询中..." : "提交问题"}
          </button>
          {loading && (
            <button className="btn btn-danger" onClick={stop}>
              ⏹ 停止
            </button>
          )}
          <select
            className="select"
            value={documentIds.length ? documentIds[0] : ""}
            onChange={(e) => setDocumentIds(e.target.value ? [e.target.value] : [])}
            title="限定检索到单本说明书（document_ids 过滤）"
          >
            <option value="">📚 全部文档</option>
            <option value="Roborock G10S">Roborock G10S</option>
            <option value="Ecovacs DEEBOT T30C">Ecovacs DEEBOT T30C</option>
          </select>
          <label className="muted" style={{ fontSize: "var(--text-sm)", display: "inline-flex", gap: 4, alignItems: "center" }}>
            <input type="checkbox" checked={debug} onChange={(e) => setDebug(e.target.checked)} />
            Developer（检索 trace）
          </label>
        </div>
      </div>

      {/* Examples */}
      {!result && !loading && (
        <div className="mb-4">
          <div className="muted mb-3" style={{ fontSize: "var(--text-sm)" }}>示例问题：</div>
          <div className="tag-row">
            {EXAMPLES.map((ex) => (
              <button key={ex} className="btn btn-ghost btn-sm" onClick={() => { setQuestion(ex); doSubmit(ex); }}>
                {ex}
              </button>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="error-box mb-4">
          <strong>请求失败：</strong>{error}
        </div>
      )}

      {loading && (
        <div className="empty-state" style={{ padding: 40 }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>⏳</div>
          <div>正在检索并生成答案，请稍候...</div>
          <button className="btn btn-sm mt-3" onClick={stop}>停止生成</button>
        </div>
      )}

      {result && (
        <div>
          <div className="flex-between mb-4">
            <span className={`badge ${statusCfg?.cls || ""}`}>{statusCfg?.label}</span>
            <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
              {result.cache.hit && (
                <span className="badge badge-success">
                  ⚡ 缓存命中 {result.cache.source === "semantic" ? "(语义)" : "(精确)"}
                </span>
              )}
              <span className={`badge ${groundingCfg?.cls || ""}`}>
                Grounding: {groundingCfg?.label}
              </span>
              <span className="muted" style={{ fontSize: "var(--text-sm)" }}>
                耗时 {(result.latency.total_ms / 1000).toFixed(2)}s
              </span>
            </div>
          </div>

          <div className="card mb-3" style={{ lineHeight: "var(--leading-relaxed)", whiteSpace: "pre-wrap", fontSize: "var(--text-md)" }}>
            {result.answer}
          </div>

          {/* Grounding */}
          <div className="card card-sm mb-4">
            <div style={{ fontWeight: 600, marginBottom: 8, fontSize: "var(--text-md)" }}>验证结果</div>
            <div className="flex-row" style={{ gap: 24, flexWrap: "wrap" }}>
              <div>
                <span className="muted">grounding: </span>
                <span style={{ fontWeight: 600 }}>{result.grounding.status}</span>
              </div>
              {result.grounding.support_ratio != null && (
                <div>
                  <span className="muted">支撑率: </span>
                  <span style={{ fontWeight: 600 }}>{(result.grounding.support_ratio * 100).toFixed(0)}%</span>
                </div>
              )}
              <div>
                <span className="muted">scorer: </span>
                <span style={{ fontWeight: 600 }}>{result.grounding.scorer}</span>
              </div>
            </div>
            {result.grounding.unsupported_claims.length > 0 && (
              <div className="mt-3">
                <div className="muted" style={{ fontSize: "var(--text-sm)", marginBottom: 4 }}>
                  无支撑句子（{result.grounding.unsupported_claims.length}）：
                </div>
                {result.grounding.unsupported_claims.map((c, i) => (
                  <div key={i} style={{ color: "var(--color-error)", fontSize: "var(--text-sm)" }}>• {c}</div>
                ))}
              </div>
            )}
          </div>

          {/* Citations（由系统计算，点击展开 excerpt） */}
          <div style={{ fontWeight: 600, marginBottom: 8, fontSize: "var(--text-md)" }}>
            引用（{result.citations.length}）— 由系统从检索结果计算
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {result.citations.map((c: CitationV1) => (
              <div key={c.chunk_id} className="card card-sm">
                <button
                  className="citation-toggle"
                  onClick={() => setExpandedCitation(expandedCitation === c.chunk_id ? null : c.chunk_id)}
                  style={{ width: "100%", textAlign: "left", background: "none", border: "none", cursor: "pointer" }}
                >
                  <span style={{ fontSize: 18 }}>{TYPE_ICONS[c.content_type] || "📄"}</span>{" "}
                  <strong>{c.source_file.split("/").pop()}</strong>
                  <span className="ml-2 muted" style={{ fontSize: "var(--text-xs)" }}>第{c.page}页 · ID {c.chunk_id}</span>
                  {c.rerank_score != null && (
                    <span className="ml-2 muted mono" style={{ fontSize: "var(--text-xs)" }}>
                      rerank {c.rerank_score.toFixed(4)}
                    </span>
                  )}
                </button>
                {expandedCitation === c.chunk_id && (
                  <div className="mt-2" style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
                    {c.content_excerpt}
                    <div className="flex-row mt-2" style={{ gap: 12, fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
                      <span>dense {c.dense_score ?? "-"}</span>
                      <span>bm25 {c.bm25_score ?? "-"}</span>
                      <span>rrf {c.rrf_score ?? "-"}</span>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Evidence Panel（developer mode：证明 hybrid 检索真实） */}
          {result.trace && (
            <div className="card card-sm mt-4">
              <div style={{ fontWeight: 600, marginBottom: 8, fontSize: "var(--text-md)" }}>
                Evidence Panel（developer）— Dense/BM25/RRF/Rerank
              </div>
              <table style={{ width: "100%", fontSize: "var(--text-xs)" }}>
                <thead>
                  <tr style={{ textAlign: "left" }}>
                    <th>chunk</th><th>dense_rank</th><th>bm25_rank</th><th>rrf</th><th>rerank</th><th>changed</th>
                  </tr>
                </thead>
                <tbody>
                  {result.trace.candidates.map((cand) => (
                    <tr key={cand.chunk_id}>
                      <td className="mono">{cand.chunk_id}</td>
                      <td>{cand.dense_rank ?? "-"}</td>
                      <td>{cand.bm25_rank ?? "-"}</td>
                      <td>{cand.rrf_score?.toFixed(4) ?? "-"}</td>
                      <td>{cand.rerank_score?.toFixed(4) ?? "-"}</td>
                      <td>{cand.ranking_changed ? "✓" : cand.ranking_changed === false ? "—" : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
