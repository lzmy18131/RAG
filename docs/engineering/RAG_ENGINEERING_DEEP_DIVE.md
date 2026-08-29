# RAG 工程深潜：17 个关键设计问题的代码级答案

> 本文档面向工程师，用**本仓库真实代码**回答 RAG 管线里最常见的 17 个"为什么"。
> 所有结论均可追溯到 `src/` 下的具体文件、函数与行号；引用的指标只使用
> `runs/demo_retrieval_v1/report.md`（当前可信基准）与明确标注为历史值的文档，
> 不编造任何数字。

## 管线总览

v1 查询链路在 `src/api/services/rag_service.py:RAGService.run_stages`（L121-269）中逐阶段执行：

```
cache_lookup → hybrid retrieve (dense+BM25+RRF) → rerank → relevance check
→ generate → grounding verify → citation build → cache write
```

- **Stage 1 召回**：`RerankedRetriever.search` 先调 Hybrid（top-20 候选），再 Cross-Encoder 精排取 top-5（`src/retrieval/reranked_retriever.py`，docstring L3：`Query → Hybrid top-20 → Reranker score → top-5 final`）。
- **Stage 2 验证**：`GroundingVerifier` 对答案逐句打分，不达标则拒绝回答（`src/workflow/grounding.py`）。

当前唯一可信基准：Demo 模式（合成语料 20 chunk、12 题、确定性可复现）`runs/demo_retrieval_v1/report.md`：
**Recall@5 = 0.9167 / MRR = 0.9167 / nDCG@5 = 0.8792 / Hit@5 = 1.0**；语义缓存 exact 命中 12/12、false-hit rate 0.0。
README 中的 V0–V9 历史数字（如 V3 Recall@5 0.88→0.91、V6 投毒拦截 82%）均为旧环境产物，**重构后未重跑 → NOT VERIFIED AFTER REFACTOR**（README L163、docs/history/FINAL_ENGINEERING_AUDIT.md L85）。

---

## Q1. 为什么 Dense 会漏 exact keyword？（BGE-M3 语义向量 vs BM25 token 匹配）

Dense 检索是**整句语义压缩**：`Embedder.encode`（`src/infra/embedder.py` L34-38）把 query 编码成一个归一化向量，再在 Milvus 里做向量近似搜索（`DenseRetriever.search`，`src/retrieval/retriever.py` L86/L107）。语义相近（"无法开机"↔"电源故障"）能命中，但**精确词面信号在稠密向量里被稀释**：像 "PTC"、"E07"、型号名这类只出现在极少 chunk 的 token，它们对 1024 维向量的贡献淹没在整句语义里；query 换了个说法后，这个 chunk 的余弦分可能跌出 top-K。

README L66 直接写了这个动机："精确术语（'PTC'、'E07'、型号名）在向量空间会被稀释，关键词匹配是硬需求"。Demo 的 `FakeEmbedder`（`src/infra/demo.py` L100-106，BoW 哈希向量）是这一现象的玩具模型：token 被散列进固定维度的桶，词面信息只占其中几维。

## Q2. 为什么 BM25 与 Dense 互补？

BM25 是**词面匹配**：`BM25Retriever.search`（`src/retrieval/bm25.py` L42-65）用 jieba 分词（L24）后对 query token 计算 BM25 分数。它抓得住精确术语、型号、故障码；但**对同义改写、口语化、跨语言完全无能为力**（中文 query 命中英文手册 chunk 只能靠语义，见 docs/DECISIONS.md D-008 的 Ecovacs 跨语言题）。

两者的召回盲区互补：Dense 漏字面术语（Q1），BM25 漏语义改写。`HybridRetriever.search`（`src/retrieval/hybrid_retriever.py` L138-233）正是"两路独立检索、再融合"（L157-180 分别 try dense/bm25，L205-206 交给 RRF），一路挂了就降级到另一路（L209-225，带 `degrade_reason`），两路全挂才报错（L228-231）。

## Q3. RRF 公式是什么？k=60 的含义？

`_rrf_fusion`（`src/retrieval/hybrid_retriever.py` L24-75）实现 Reciprocal Rank Fusion：

```
rrf_score(d) = Σ_路 1 / (k + rank_d)
```

代码 L49 与 L68：`combined[cid]["rrf_score"] += 1.0 / (k + rank)`。k 默认 60（L27），且配置化于 `src/config/settings.py:retrieval_rrf_k = 60`（L55）。

**k 是排名深度平滑常数**：k 越大，相邻排名的分差越小（所有项的分都趋近 1/k 的倍数），结果越偏向"在两路都靠前"的 chunk；k 越小，越放大排名差异。项目注释明确 k=60 "偏向'两路都靠前'的项"（README L67）。最后按 rrf_score 降序取 top_k（L70-75）。

## Q4. 为什么不能直接加 BM25 score 与 cosine score？（量纲/分布）

`HybridRetriever` 在融合时**刻意只保留 rank、不融合分数**：dense 的 cosine 经 `normalize_embeddings=True` 后 ∈ [-1, 1]（`embedder.py` L38），而 BM25Okapi 的分数是**无界的频率加权和**（`bm25.py` L51 `get_scores`，L59 仅 round 不归一化）。两个分布的量纲、尺度、形状都不同——直接相加等于让数值大的那一路（BM25）完全主导，另一路信号被淹没。

RRF 只用排名（Q3 公式里只有 rank 没有 score），天然把两个异构排序器统一到 `[0, 2/k]` 区间，无需归一化。README L67 的措辞即此："不需要归一化 dense cosine 与 BM25 无界频率分（量纲不同不能直接相加）"。两路的原始分数仍保留在结果里供诊断（`dense_score`/`bm25_score`，L42/L59），但从不进入融合。

## Q5. 为什么 retrieve 后 rerank？（Recall→Precision 两阶段）

检索器的**质量-成本曲线不同**：Hybrid 便宜但粗（语义近似 + 词面匹配），Cross-Encoder 精确但贵（见 Q7）。两阶段是把预算花在刀刃上：

- **Stage 1（Recall）**：`RerankedRetriever.search`（`reranked_retriever.py` L63-74）用 Hybrid 取 `candidate_top_k=20`（L23，配置于 `settings.retrieval_rerank_candidate_k=20` L58）——宁可多召回，别漏。
- **Stage 2（Precision）**：对这 20 个候选用 BGE-Reranker 逐对打分（L80-105），重排后只取 `final_top_k=5`（L113，`settings.retrieval_final_top_k=5` L59）。

README L68 称之为"质量-延迟 Pareto"：rerank 只作用于 20 个候选而非全库，避免了昂贵模型扫全量。Demo 基准中 Hit@5=1.0、Recall@5=0.9167（`runs/demo_retrieval_v1/metrics.json`）说明在 demo 语料上候选池没有漏掉 golden chunk。

## Q6. Bi-Encoder 与 Cross-Encoder 区别？

- **Bi-Encoder**（`Embedder`，`src/infra/embedder.py`）：query 与 doc **各自独立编码**成向量（L34-38），二者在编码阶段完全看不到对方，交互发生在编码之后的向量空间（点积/余弦近似）。doc 向量可**预计算**（摄入时 `encode_batch`，`src/ingestion/incremental.py` L104）并建 ANN 索引，所以 query 时只需 1 次编码 + 向量检索。
- **Cross-Encoder**（`Reranker`，`src/infra/reranker.py`）：把 `[query, doc]` **拼接成一个序列联合编码**（L38 `pairs = [[query, doc] for doc in documents]`），Transformer 内部做完整 cross-attention——query 的每个 token 都能直接"看见" doc 的每个 token。

一句话：Bi-Encoder 用"预计算换速度"、牺牲交互精度；Cross-Encoder 用"逐 query 重算"换精确的 token 级交互。这正是"语义召回用 Bi-Encoder、精排用 Cross-Encoder"的分工（README L65/L68）。

## Q7. 为什么 reranker 更慢？

三层原因，都能在代码里看到：

1. **无法预计算**：Cross-Encoder 的表示依赖 (query, doc) 配对，doc 侧没有任何可复用的预计算向量，每个新 query 都要对所有候选重新前向。
2. **前向次数 = 候选数**：`reranked_retriever.py` L84-85 对 20 个候选逐个构造 pair 打分，即 20 次 transformer 前向；而 Dense 全程只有 1 次 query 编码（`retriever.py` L86）+ Milvus ANN（L107），doc 向量早在摄入时算好。
3. **显存预算**：因此项目把它当稀缺资源管理——`settings.max_concurrent_reranks = 4`（L52）限制并发重排，且 `DenseRetriever`/`RerankedRetriever` 都要求注入共享模型实例，避免第二个本地加载撑爆 8GB 显存（`retriever.py` L46-49、`reranked_retriever.py` L38-40 的注释）。

这也是 Q5 两阶段设计的直接动因：把 20 次昂贵前向限制在候选池内。

## Q8. Recall / MRR / nDCG 区别？

统一实现在 `src/eval/retrieval_metrics.py:evaluate_query`（L30-69）：

- **Recall@K**（L57）：top-K 里命中的相关 chunk 数 / 总相关数——**只看召回了多少，不看顺序**。
- **MRR**（L65）：第一个相关项的倒数排名，未命中记 0——**只关心"第一个对的排多前"**。
- **nDCG@K**（L62 + `_dcg` L20-22 / `_idcg` L25-27）：按排名位置加权（`1/log2(r+1)`），并除以理想排序的 DCG 归一化——**既看相关项数量，又惩罚排在后面的相关项**。

三者回答不同问题：Recall 回答"证据找全了吗"，MRR 回答"第一个证据有多靠前"，nDCG 回答"整体排序质量好不好"。Demo 基准正好展示了三者差异：Recall@1=0.5417 但 Recall@3=0.9167、MRR=0.9167、nDCG@5=0.8792（`runs/demo_retrieval_v1/metrics.json`）——多数 query 的第一个相关项就在第 1-2 位，但并非全部。

## Q9. Retrieval Recall 与 Faithfulness 区别？

- **Retrieval Recall**：衡量**检索阶段**——golden 相关 chunk 是否进入候选（Q8，`retrieval_metrics.py`）。
- **Faithfulness**：衡量**生成阶段**——答案是否忠于**检索到的**上下文（README L82 的 generation 指标族：Faithfulness / Answer Relevancy / Context Precision 等）。

两者正交且分属不同环节：**召回失败 → 生成器无证据可用，Faithfulness 不可能高**；但**召回全对也不保证 Faithfulness**——LLM 仍可能脱离上下文编造。项目因此把验证放在生成之后（`rag_service.run_stages` 中 grounding 在 generate 之后，L213-243），用证据去核对答案（Q10），而不是默认"检索对了就安全了"。

## Q10. Grounding 与 Retrieval 的区别？

- **Retrieval（找证据）**：query → chunk，发生在生成**之前**，输出"可能是证据的候选"。
- **Grounding（验答案）**：answer → chunk，发生在生成**之后**，验证"答案的每一句是否真的被某 chunk 支撑"。

`GroundingVerifier.verify`（`src/workflow/grounding.py` L264-415）的流程：`split_sentences` 拆句（L56-110，只在括号深度为 0 的 `。！？!?；;` 处分句）→ 每句与 chunks 打分（cross-encoder `CrossEncoderScorer` L193-212 或 cosine 路径 L327-328）→ 逐句判定支撑 → `support_ratio`（L376）≥ `min_support_ratio=0.7`（L233/L389）才算整体 supported，否则拒答或列 `unsupported_claims`（L390-397）。`rag_service.py` L227-243 把它接到管线里：不通过 → `status="refused"` 并返回 REFUSE_ANSWER（L56/L251）。

## Q11. 为什么 relevance != entailment？（项目文档的 honest 声明）

交叉编码器打分高 = **主题相关**，不等于**逻辑上被蕴含**。项目在 README L74 明示："这是 deterministic relevance-based grounding，`relevance ≠ entailment`——交叉编码器拦不住'主题相关但编造'（Frankenstein 边界），不是'彻底解决幻觉'"。

证据在 `docs/history/V0_V9_EXPERIMENTS.md` L107-110 的投毒实验（历史数字）：对真实答案追加编造句，BGE-M3 余弦拦截 **0/34**（相似度被主题词抬高），BGE-Reranker 拦截 **28/34（82%）**，残余 6/34 漏网均为"主题相关编造"——例如"核聚变反应堆提供动力"能匹配到手机连接 chunk 里的功率内容。`CrossEncoderScorer` 的 docstring（`grounding.py` L196-198）自己也承认它只是"far more discriminative than bi-encoder cosine for detecting topical-but-fabricated claims"，是判别力更强的**相关性**打分器，不是蕴含判别器。

## Q12. Citation validation 为什么必须程序控制？

因为 LLM 声称的引用会幻觉。`rag_service.py:_build_citations`（L291-308）的注释直说："由系统计算引用：只引用真实检索返回的 chunk（任务书 §36/§37）"——引用（chunk_id / source_file / page）从**实际检索结果**构造，LLM 只负责生成文本，无权写页码。README L77 的承诺："不存在'引用第 37 页但第 37 页不存在'"。

程序侧还有第二道闸：`GroundingVerifier._audit`（`grounding.py` L433-463）解析答案里的 `[来源: X, 第Y页]` 标记，与真实 chunk 逐条核对，输出三态 `confirmed / unconfirmed / unmatched`——**unmatched 即幻觉引用**（没有任何 chunk 对得上）。若允许 LLM 自报页码，用户点击引用就打不开真实证据，"可验证性"这个 RAG 的立身之本就不成立。

## Q13. Semantic Cache 为什么带 corpus_version（+ schema_version）？

缓存命中的是**历史响应**，两个版本问题必须防：

1. **知识库更新**：同一问题在文档修改后应得到新答案。`RAGService._corpus_version`（`rag_service.py` L85-98）取 `storage/manifests/manifests.json` 的 SHA256 前 12 位——任一文档增/删/改 → manifest 变化 → corpus_version 变化。`cache_salt = f"{doc_filter or ''}|corpus:{corpus_version}|schema:v1"`（L141）把版本号混入缓存 key（`semantic_cache.py:_normalize_query_plus_salt` L26-30 用 NUL 分隔、`_hash` L73-74 SHA256），于是知识库一变，旧 key 自动 miss。doc_filter 也进 salt，跨文档 scope 永不串用。
2. **响应契约（schema）变化**：旧缓存反序列化会失败。`rag_service.py` L161-162 已有兜底（schema 不兼容 → 视为未命中），但显式加 `schema:v1` 是提前隔离（L140 注释：与 legacy /query 缓存不串用，任务书 §26）。

Demo 基准中 exact 命中 12/12、false-hit rate 0.0（`runs/demo_retrieval_v1/report.md`）——false-hit 是"相似 ≠ 同义"的近似代价，README L186 也把它列为 Known Limitation（有 corpus_version/schema 失效缓解）。

## Q14. Incremental Index 为什么需要 atomic manifest？（tmp+rename；Milvus 无事务限制）

`ManifestStore.save`（`src/ingestion/manifest.py` L78-100）是教科书式原子写：`tempfile.mkstemp` 在**同目录**建 `.tmp`（L85）→ 写 JSON + `flush` + `os.fsync`（L94-95）→ `os.replace(tmp_path, path)`（L96）原子替换；异常时清理 tmp 并重抛（L97-100）。`os.replace` 是同一文件系统上的原子 rename——任何时刻磁盘上的 `manifests.json` 要么是完整旧版、要么是完整新版，**崩溃不会留下半截 JSON**。

为什么 manifest 必须原子：它是增量索引的**唯一事实来源**——`ManifestStore.classify`（L114-141）依据它把文件分成 added/unchanged/modified/deleted，决定下一轮要重做多少工作。manifest 写坏 = 状态错乱 = 全量重索引或丢更新。

而 Milvus 侧**没有这个保证**：`IncrementalIndexer._modify_document`（`src/ingestion/incremental.py` L148-154）是"先 delete 旧文档、再 insert 新文档"两步，中间崩溃会留下不一致（README L101 文档化限制："Milvus Lite 无事务 → 删除旧+写新非原子"）。所以 manifest 必须由原子写兜底，作为可恢复的锚点。另外 `chunk_id` 是稳定派生的：`_make_chunk_id`（`src/ingestion/document.py` L11-14）`sha256(f"{document_id}|p{page}|s{seq}")[:16]`——同一文档重摄入生成相同 chunk_id，删除/重建幂等。

## Q15. LLM Gateway 为什么需要 circuit breaker？

LLM 调用是**又慢又容易挂的外部依赖**：单次尝试超时 60s（`settings.llm_timeout`，L71），而 SDK 默认是 600s——一个挂掉的 API 能拖住查询几分钟。熔断（`CircuitBreaker`，`src/infra/gateway.py` L112-174）解决"**已知故障的 provider 不该再被反复试探**"：连续失败 ≥ `failure_threshold=3`（`CircuitConfig` L53）→ 从 CLOSED 转 OPEN，`allow_request`（L126-140）在冷却期（`cooldown_seconds=30`，L54）内直接放行请求（即跳过错），冷却后转 HALF_OPEN 放一个探测请求，成功则回 CLOSED（`record_success` L142-147）、失败则回 OPEN（`record_failure` L149-162）。

配合链是完整的（`LLMGateway.chat` L266-292）：每个 provider 先查熔断器（L270），再指数退避重试（`_backoff` L258-264，`RetryPolicy` max_retries=2 / base=1 / multiplier=2 / cap=8 / jitter，L58-64），重试耗尽或 4xx 立即 failover 到下一个 provider（L281/L285，providers 链 L318-329：primary → backup_2 → backup_3）。全挂时返回 `DEFAULT_FALLBACK_ANSWER`（L26："模型服务暂时不可用，无法回答此问题，请稍后重试。"），该文案在 `VerifiedQA` 的 `refusal_phrases` 里（`src/workflow/verified_qa.py` L119），会被当作**生成器自拒**处理——优雅降级，而不是 500。

## Q16. 平均 latency 与 p95 的区别？

`src/eval/latency.py` 同时提供了两种视角：`StageTimer`（L37-66）给**各阶段平均耗时**；`LatencyRecorder.record` + `percentiles`（L73-83、L22-34，nearest-rank、NaN 安全）给 **p50/p90/p95/max 分位数**。

差别在于**长尾**：平均值被少数慢请求拉爆——10 个请求里 9 个 0.1s、1 个 1.9s，平均值是 0.28s，看起来"挺快"，但 p95 是 1.9s，最差的 5% 用户体验差 19 倍。对 SLO（"99% 请求 < 2s"）而言，p95/p99 才是承诺；平均值会掩盖一次 60s 超时对系统整体延迟的污染（Q15 正是为了缩短这种长尾）。`rag_service.py:_stage_timer`（L39-50）逐阶段计时，README L86 的 ablation 也约定同时报告 p50/p95，就是这个原因。

## Q17. 为什么不增加 Multi-Agent / Query Rewrite / Native Multimodal？（诚实：无 benchmark 证明收益）

这些是流行技术，但项目明确把它们列为 **P2 可选实验，默认不加**（`docs/history/FINAL_ENGINEERING_AUDIT.md` L117-124）：

- "Query Rewrite（**必须 benchmark 证明收益，默认不加**）"（L119）
- "Native multimodal embedding（**对比 caption pipeline**：Image Recall/MRR/VRAM/Index size）"（L121）
- 复杂解析器（MinerU/Docling）"需 complex-PDF benchmark 证明收益"（L123）

README L189 的 Known Limitations 也写死："未接入 Query Rewrite / Adaptive Retrieval / Native Multimodal（无 benchmark 证明收益前不加）"。

诚实的理由分三层：

1. **收益未证**：在本仓库语料（智能硬件说明书）和规模上，没有任何 benchmark 证明这些模块能提升 Recall/Faithfulness；加进去只增加延迟、配置面和维护面。
2. **现状已够且已如实标注**：多模态走 **VLM caption → text → BGE-M3** 统一向量空间（README L184 明示"不是 native image-text unified embedding"）；图片题的历史基准（8 题 Hit@5/Recall@5/MRR 全 1.000，`EXPERIMENT_LOG.md` L164）是 caption-based 的证据，且属于**重构后未重跑**的历史数字。
3. **Integrity 优先**：项目宁可少一个"听起来高级"的模块，也不展示未经复跑的指标（`FINAL_ENGINEERING_AUDIT.md` L136："历史 benchmark 当最新指标展示 → 违反 Integrity"）。当前可信数字只有 demo 基准（`runs/demo_retrieval_v1/metadata.json` 注明"CI 离线回归；非真实模型 benchmark"），文档如实如此。

---

## 结语

这套系统的设计主线可以压缩成一句话：**用便宜的检索器扩大召回（Hybrid+RRF），用昂贵的编码器收紧精度（Cross-Encoder rerank 与 grounding），用确定性程序取代不可信的 LLM 声明（引用计算、接地验证），再用版本化缓存与熔断网关把成本和故障控制住**——每一步取舍都在代码里有迹可循，也都有对应的诚实边界声明。
