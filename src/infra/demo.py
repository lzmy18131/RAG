"""Demo Mode — 无 API key / 无 GPU / 无模型下载的确定性演示链路。

设计原则：
- **复用真实管线代码路径**：FakeEmbedder / FakeReranker / FakeMilvusClient 实现与
  真实适配器相同的接口，DenseRetriever → HybridRetriever(RRF) → RerankedRetriever →
  GroundingVerifier → SemanticCache 全部走真实代码，只是替换了底层模型/存储。
- 语料为**公开可合法分发的合成硬件说明书**（自造内容，非真实品牌手册）。
- 所有输出带 DEMO 标记，绝不伪装真实 AI 结果。
- 确定性：同一输入 → 同一输出（可复现、可测试、可 E2E）。
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from src.retrieval.bm25 import BM25Retriever
from src.retrieval.contracts import RetrievedChunk
from src.retrieval.retriever import DenseRetriever

DEMO_MARK = "【DEMO 演示模式 · 非真实诊断/维修结论】"
DEMO_COLLECTION = "demo_corpus"

# ==================== 合成语料（公开可分发） ====================
# 自造的「智能清洁机器人 X1 使用与维护手册（DEMO 版）」节选：
# 覆盖故障码 / 维护流程 / 参数 / 按钮组件 / 图片示意图 caption。

_DEMO_ROWS: list[tuple[str, int, str, str]] = [
    # (chunk_id, page, type, text)
    (
        "demo-0001",
        1,
        "text",
        "X1 智能清洁机器人支持自动回充：电量低于 20% 时自动返回充电座，充电 3 小时后可恢复满电状态。",
    ),
    (
        "demo-0002",
        1,
        "image",
        "正面示意图：机身顶部为电源键与回充键，前方为激光雷达传感器，底部为边刷与主滚刷。",
    ),
    (
        "demo-0003",
        2,
        "text",
        "故障码 E01：表示激光雷达被遮挡。处理方法：检查并清理激光雷达窗口，重启机器人后若仍报错请联系售后。",
    ),
    (
        "demo-0004",
        2,
        "table",
        "故障码对照表：E01=激光雷达遮挡；E02=边刷缠绕；E07=尘盒未安装或安装不到位；PTC=电机过热保护。",
    ),
    (
        "demo-0005",
        3,
        "text",
        "故障码 E02：边刷缠绕异物。处理方法：关闭电源，取出边刷并清理缠绕的线缆或毛发后重新安装。",
    ),
    (
        "demo-0006",
        3,
        "text",
        "故障码 E07：尘盒未安装。处理方法：确认尘盒已推入到位并听到卡扣声；若尘盒已满请先清空。",
    ),
    (
        "demo-0007",
        4,
        "text",
        "PTC 过热保护：长时间高负载运行导致电机过热时，机器人自动停机降温，约 15 分钟后可重新启动。",
    ),
    (
        "demo-0008",
        4,
        "text",
        "日常维护：建议每周清理一次主滚刷与边刷，每月更换一次 HEPA 滤网，每季度清洁一次传感器窗口。",
    ),
    (
        "demo-0009",
        5,
        "text",
        "参数规格：额定功率 45W，电池容量 5200mAh，续航约 180 分钟，尘盒容量 400ml，水箱容量 350ml。",
    ),
    (
        "demo-0010",
        5,
        "text",
        "充电说明：使用随附的 24V 电源适配器为充电座供电；充电时指示灯为橙色，充满后变为绿色。",
    ),
    (
        "demo-0011",
        6,
        "text",
        "按键说明：电源键短按开机/关机，长按 3 秒进入配网模式；回充键可随时触发返回充电座。",
    ),
    (
        "demo-0012",
        6,
        "image",
        "底部示意图：主滚刷位于中部，两侧为边刷，前部为悬崖传感器，用于检测台阶防止跌落。",
    ),
    (
        "demo-0013",
        7,
        "text",
        "防跌落功能：机器人配备悬崖传感器，可检测楼梯等高度差并自动转向，避免从楼梯跌落。",
    ),
    (
        "demo-0014",
        7,
        "text",
        "首次使用：安装边刷与尘盒，接通充电座电源，将机器人放上充电座充满电后即可开始清扫。",
    ),
    (
        "demo-0015",
        8,
        "text",
        "清扫模式：支持标准、强力、静音三种模式；强力模式吸力最大但续航缩短至约 120 分钟。",
    ),
    (
        "demo-0016",
        8,
        "text",
        "水箱组件：安装水箱后进入拖地模式；水箱缺水时机器人暂停拖地并语音提示加水。",
    ),
    (
        "demo-0017",
        9,
        "text",
        "清理边刷：将机器人翻转，按下边刷卡扣即可取出；清理后按原方向装回并确认卡紧。",
    ),
    ("demo-0018", 9, "text", "滤网更换：打开尘盒，取出 HEPA 滤网，装入新的滤网并确保密封圈贴合。"),
    (
        "demo-0019",
        10,
        "text",
        "Wi-Fi 配网：长按电源键 3 秒进入配网模式，指示灯闪烁；在 App 中选择 2.4GHz 网络并输入密码。",
    ),
    (
        "demo-0020",
        10,
        "text",
        "常见问题：机器人找不到充电座时，请确认充电座前方 1.5 米无障碍物，并检查回充信号发射窗清洁。",
    ),
]

DEMO_CORPUS: list[dict[str, Any]] = []
for _cid, _page, _ctype, _content in _DEMO_ROWS:
    DEMO_CORPUS.append(
        {
            "chunk_id": _cid,
            "document_id": "demo-manual",
            "source_file": "data/demo/x1-manual.pdf",
            "page_number": _page,
            "chunk_index": int(_cid.split("-")[1]),
            "content_type": _ctype,
            "content": _content,
            "language": "zh",
        }
    )


def _tokenize(text: str) -> list[str]:
    """确定性分词：中文字符按 2-gram + ASCII 词。不依赖 jieba 词典变体。"""
    ascii_words = re.findall(r"[A-Za-z0-9]+", text.lower())
    cn_chars = re.findall(r"[\u4e00-\u9fff]", text)
    grams: list[str] = []
    for i in range(len(cn_chars) - 1):
        grams.append(cn_chars[i] + cn_chars[i + 1])
    return ascii_words + grams


# ==================== Fake 模型/存储（真实管线复用） ====================


class FakeEmbedder:
    """确定性哈希 Bag-of-words 向量（余弦相似度有语义可复现）。"""

    def __init__(self, dim: int = 64):
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def is_loaded(self) -> bool:
        return True

    def load(self) -> None:
        pass

    def encode(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for tok in _tokenize(text):
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest()[:8], 16)
            vec[h % self._dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [round(v / norm, 6) for v in vec]

    def encode_batch(self, texts: list[str], batch_size: int = 8) -> list[list[float]]:
        return [self.encode(t) for t in texts]


class FakeReranker:
    """词元重叠 [0,1] 打分的确定性 reranker（够让 grounding/排序有意义）。

    语义对齐真实 Cross-Encoder：完全无关的 (query, doc) 对返回低但非零的分数
    （真实 BGE-reranker sigmoid 输出 ~0.01-0.05），使 VerifiedQA 的相关性阈值
    （MIN_RELEVANCE_SCORE=0.05）能正确拒答越界问题。
    """

    # 无关对的基础分（低于相关性阈值 0.05，高于绝对 0，避免 `or` 回退到 dense）
    UNRELATED_FLOOR = 0.01

    @property
    def is_loaded(self) -> bool:
        return True

    def load(self) -> None:
        pass

    def score(self, query: str, documents: list[str]) -> list[float]:
        q = set(_tokenize(query))
        out: list[float] = []
        for doc in documents:
            d = set(_tokenize(doc))
            if not q or not d:
                out.append(self.UNRELATED_FLOOR)
            else:
                overlap = len(q & d) / max(1, len(q | d))
                out.append(round(overlap, 4) if overlap > 0 else self.UNRELATED_FLOOR)
        return out


class FakeMilvusClient:
    """内存向量存储，实现 DenseRetriever/IncrementalIndexer 使用的子集接口。"""

    def __init__(self) -> None:
        self._collections: dict[str, list[dict[str, Any]]] = {}
        self._vectors: dict[str, list[list[float]]] = {}
        self._embedder: FakeEmbedder | None = None

    # ── seeding（demo 启动时灌入合成语料） ──
    def seed(self, collection: str, chunks: list[dict], embedder: FakeEmbedder) -> None:
        self._embedder = embedder
        self._collections[collection] = [dict(c) for c in chunks]
        self._vectors[collection] = [embedder.encode(c["content"]) for c in chunks]

    # ── Milvus 兼容接口 ──
    def list_collections(self) -> list[str]:
        return list(self._collections)

    def load_collection(self, name: str) -> None:
        if name not in self._collections:
            self._collections[name] = []
            self._vectors[name] = []

    def search(self, **kwargs: Any) -> list[list[dict]]:
        collection = kwargs.get("collection_name", DEMO_COLLECTION)
        data = (kwargs.get("data") or [[]])[0]
        limit = int(kwargs.get("limit", 5))
        filter_expr = kwargs.get("filter")
        output_fields = kwargs.get("output_fields", [])
        chunks = self._collections.get(collection, [])
        vecs = self._vectors.get(collection, [])
        scored: list[tuple[float, int]] = []
        for i, chunk in enumerate(chunks):
            if filter_expr:
                sf = _parse_source_file_filter(filter_expr)
                if sf is not None and chunk.get("source_file", "") != sf:
                    continue
            sim = _cosine(data, vecs[i]) if i < len(vecs) else 0.0
            scored.append((sim, i))
        scored.sort(key=lambda x: x[0], reverse=True)
        hits: list[dict] = []
        for sim, i in scored[:limit]:
            chunk = chunks[i]
            entity = {k: chunk.get(k) for k in output_fields}
            hits.append({"entity": entity, "distance": round(sim, 4)})
        return [hits]

    def insert(self, collection_name: str, data: list[dict]) -> dict:
        chunks = self._collections.setdefault(collection_name, [])
        vecs = self._vectors.setdefault(collection_name, [])
        for row in data:
            chunks.append(dict(row))
            vecs.append(self._embedder.encode(row.get("content", "")) if self._embedder else [])
        return {"insert_count": len(data)}

    def delete(self, collection_name: str, filter: str = "") -> dict:  # noqa: A002
        return {"delete_count": 0}

    def close(self) -> None:
        pass


def _parse_source_file_filter(expr: str) -> str | None:
    m = re.search(r'source_file == "([^"]*)"', expr)
    return m.group(1) if m else None


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))


# ==================== Demo 组件装配 ====================


def build_demo_dense_retriever(embedder: FakeEmbedder, milvus: FakeMilvusClient) -> DenseRetriever:
    """用 Fake 存储构建 DenseRetriever（真实检索代码路径）。"""
    return DenseRetriever(
        collection_name=DEMO_COLLECTION,
        uri="demo-in-memory",
        embedder=embedder,
        client=milvus,  # type: ignore[arg-type]  # 接口子集
    )


def build_demo_bm25() -> BM25Retriever:
    """从合成语料构建 BM25 索引（真实 rank_bm25 代码路径）。"""
    bm = BM25Retriever()
    bm.build(DEMO_CORPUS)
    return bm


def demo_to_retrieved_chunks(results: list[dict]) -> list[RetrievedChunk]:
    """将检索 dict 归一化为统一契约（src/retrieval/contracts.py）。"""
    return [RetrievedChunk.from_dict(r) for r in results]
