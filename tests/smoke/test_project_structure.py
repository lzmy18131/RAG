from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_governance_documents_exist() -> None:
    # 文档结构（docs/README.md 为导航索引）：
    #   当前事实源 + 协作协议在 docs/ 根；工程/指标/求职/历史分别归入子目录。
    required_root = [
        "README.md",  # 文档导航索引
        "PROJECT_CHARTER.md",
        "ARCHITECTURE.md",
        "DATA_CONTRACTS.md",
        "ACCEPTANCE_MATRIX.md",
        "EXPERIMENT_PROTOCOL.md",
        "DECISIONS.md",
    ]
    required_sub = {
        "engineering/FINAL_ENGINEERING_REPORT.md",
        "engineering/RAG_ENGINEERING_DEEP_DIVE.md",
        "engineering/TECHNICAL_TRADEOFFS.md",
        "evaluation/CURRENT_RESUME_METRICS.md",
        "career/INTERVIEW_GUIDE.md",
        "history/V0_V9_EXPERIMENTS.md",
        "history/PROGRESS.md",
        "history/ROADMAP.md",
        "history/SESSION_LOG.md",
    }
    assert all((ROOT / "docs" / name).exists() for name in required_root)
    assert all((ROOT / "docs" / name).exists() for name in required_sub)


def test_experiment_profiles_exist() -> None:
    profiles = [
        "v0_naive.yaml",
        "v1_multimodal.yaml",
        "v2_hybrid.yaml",
        "v3_rerank.yaml",
        "v4_verified.yaml",
    ]
    assert all((ROOT / "configs" / "experiments" / name).exists() for name in profiles)
