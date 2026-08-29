# TECHNICAL_TRADEOFFS（本项目真实存在的工程权衡）

> 每条结合本项目真实代码与实验/审计发现，用于深入学习与面试深挖。

## 1. Dense vs Sparse（语义 vs 关键词）

- **为什么互补**：Dense（BGE-M3）擅长语义近似（"无法开机"↔"电源故障"）；Sparse（BM25 jieba）擅长精确术语（"PTC"、"E07"、"BAAI/bge-m3"这类 token 在向量空间可能被稀释）。
- **本项目实证**：V2（+BM25）MRR 0.76→0.84（+10.5%），说明说明书场景**术语精确匹配**是硬需求。
- **代价**：双通道都跑 → 延迟 + 索引维护。本项目 BM25 用 rank_bm25 内存索引 + pkl 持久化（bm25.py），doc_filter 在打分后过滤（规模小可接受）。

## 2. RRF vs 加权融合

- **为什么不用直接相加**：dense score（余弦 0-1）与 BM25 score（无界频率分）**量纲不同**，直接加权需要调权重且对分数分布敏感。
- **RRF**：`score = Σ 1/(k + rank)`，只看排名不看分数 → 无需归一化。k=60 使融合偏向"两路都靠前的项"。
- **本项目**：`_rrf_fusion`（hybrid_retriever.py），k 已配置化（retrieval_rrf_k）。
- **局限**：丢弃分数信息；低质量语料下排名噪声放大。

## 3. Bi-Encoder vs Cross-Encoder（召回 vs 精排）

- **Bi-Encoder**（BGE-M3）：query 与 doc 独立编码 → 可预计算向量 → 快；但**交互缺失**，query 与 doc 的细粒度匹配信息丢失。
- **Cross-Encoder**（BGE-Reranker）：query+doc 拼接一起编码 → 精确但慢（每对一次前向）。
- **本项目实证**：V3（+Reranker）Recall@5 0.88→0.91、Context Precision 0.76→0.87，但**延迟 3.3s→20.5s（6x）**——这就是"先粗筛 20 条再精排 5 条"二阶段设计的动机。
- **权衡**：candidate_top_k 越大越准越慢；本项目默认 20（可配）。

## 4. Recall vs Precision（粗筛 vs 精排）

- 粗筛（hybrid top-20）追求 **Recall**（别漏）；精排（rerank top-5）追求 **Precision**（别错）。
- 指标：Recall@K 衡量"答案在不在前 K"；Precision/Context Precision 衡量"返回的 K 条有多少真相关"。**面试必答**：V3 提升的是 Precision（排序质量），Recall@5 提升有限（召回面没变，只是排序变了）。

## 5. LLM Verify vs Deterministic Grounding（V4 vs V6）

- V4 用 LLM-as-judge 验证答案 → **不可复现、可被 prompt 影响、成本高**。
- V6 用句级拆分 + 交叉编码器/余弦打分 → **确定性、可复现、可校准**。
- **本项目诚实结论**：交叉编码器是**相关性打分器，不是蕴含判断器**——"主题相关但编造"（如"本产品由核聚变反应堆提供动力"）在投毒测试中仍有 18% 漏网（28/34 拦截 82%）。**relevance ≠ entailment** 是 grounding 的根本局限。

## 6. Coverage vs Abstention（答 vs 拒）

- Grounding 阈值越高 → 越少幻觉（高 precision）但越保守（高 abstain）。
- 校准脚本（scripts/calibrate_grounding.py）输出 threshold→precision/recall/F1/abstain/coverage 曲线，**阈值必须有数据支撑而非拍脑袋**。
- 本项目 1/100 过度拒答（"不可以用洗涤剂"短否定句未匹配）——这就是 coverage/abstain 权衡的真实代价。

## 7. Cache Hit vs False Hit

- 语义缓存（V9）以余弦相似度判命中 → **相似 ≠ 同义**，阈值 0.9 仍可能错命中（返回错误答案比慢更糟）。
- 本项目修复：cache key 加入 **corpus_version**（知识库更新自动失效）与 doc_filter（跨文档隔离）。
- 权衡：阈值调低省更多 LLM 调用但 false-hit 风险上升；需 cache 专项 benchmark（hit/false-hit 分离）。

## 8. Incremental Index vs Full Rebuild

- 增量（SHA256 manifest）省算力（V5 实测 unchanged 文档 0 次 embedding）但**一致性复杂**：
  - manifest 写入非原子 → 崩溃可能索引与清单不一致（已修复为 tmp+rename）。
  - Milvus 无事务 → 删除旧 chunk + 写入新 embedding 非原子（文档化限制）。
  - chunk_id 由 `document_id|page|seq` 派生，文档路径变化会导致全量重建（document_id 基于绝对路径）。
- 权衡：全量重建简单可靠但浪费；增量高效但需要补偿机制。

## 9. Milvus Lite vs Milvus Server

- Lite：单进程文件模式、零运维、适合本地/Demo；**不能多 worker/多副本**（本项目 docker-compose 固定单 backend）。
- Server/Zilliz：水平扩展但需部署运维。
- 权衡：本项目定位本地优先 → Lite 正确；扩展点已留（MilvusClient 抽象）。

## 10. CPU vs GPU（Embedding/Reranker）

- GPU：BGE-M3/Reranker 快但 8GB 显存受限（本项目 RTX 4060 8GB，共享 embedder 避免二次加载）。
- CPU：能跑但慢（reranker 逐对打分在 CPU 上是延迟主因）。
- 并发：GPU 内存不足时需 semaphore 限流（MAX_CONCURRENT_RERANKS，Phase 6）。

## 11. VLM Caption vs Native Visual Embedding

- 本项目：图片 → Qwen3-VL 描述 → 文本 embedding（VLM-assisted textualized retrieval）——**准确说法**，不是原生 image-text joint embedding。
- 优势：复用文本检索链路、无需视觉 embedding 模型。
- 局限：描述损失图像细节；caption 是 untrusted content（注入面）。
- 可选实验（不默认）：SigLIP/CLIP 视觉 embedding 与 caption 检索对比，需三组评测才能决定。

## 12. LLM Gateway 的复杂度

- retry/熔断/failover 带来鲁棒性（V7）但：重试放大延迟与成本；熔断误判可能降低可用性；多 provider 配置复杂。
- 本项目权衡：专家角色低重试上限（防重试风暴）、兜底文案含"无法回答"子串与拒答流程联动（字符串耦合，审计发现）。

## 13. 平均延迟 vs p50/p95

- 平均延迟掩盖长尾：V3 平均 20.5s 但 p95 可能 40s+（reranker + LLM + grounding 串行）。
- 本项目：StageTimer 分阶段计时 + p50/p95/max（eval/latency.py）——回答"V3 为什么 3s→20s"（rerank 占大头）。

## 14. 离线 eval vs 在线 eval

- 离线（fake/确定性 grader）：CI 可跑、可复现、免费；但**无法测真实模型行为**。
- 在线（RAGAS/LLM-judge）：真实但贵、慢、不可复现（模型漂移）。
- 本项目：离线优先（audit 原则），在线需 `RUN_ONLINE_EVALS=true` 显式开启。

## 15. Dataset 校准集 vs 测试集

- 在测试集上反复调参 = leakage（指标虚高）。
- 本项目：calibration/test split（20/80），阈值与参数在 calibration 上选，test 只跑一次。
- 局限：数据量有限（100 题），校准集小——诚实记录。
