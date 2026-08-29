# 数据与许可（audit D7 / 任务书 §60-61）

## 数据来源分类

| 数据 | 类别 | 是否随仓库分发 | 说明 |
|---|---|---|---|
| `data/eval_dataset/golden_100.json` | 项目自建（QA 标注） | ✅ | 基于公开说明书内容人工/半自动标注的问答对，schema 见 docs/DATA_CONTRACTS.md |
| `data/eval_dataset/golden_extended.json` | 项目自建（QA 标注） | ✅ | 同上（多文档扩展集） |
| `data/eval_dataset/v0_questions.json` | 项目自建 | ✅ | V0 阶段 20 题 |
| `evals/datasets/*.jsonl` | 派生（规范化+哈希） | ✅ | 由上述文件构建（`scripts/build_evals_datasets.py`） |
| `data/raw_docs/Roborock*.pdf` | 第三方（厂商公开说明书） | ⚠️ 见下 | **版权归厂商所有，不随 git 分发**（本地开发用） |
| `data/raw_docs/Ecovacs*.pdf` | 第三方（厂商公开说明书） | ⚠️ 见下 | 同上 |

## 第三方文档的再分发声明

`data/raw_docs/` 下的商业说明书（Roborock / Ecovacs）**版权归各自厂商所有**，
仅用于本项目本地开发与评测，**不随仓库重新分发**（.gitignore 已排除；仓库中仅保留占位）。

如需公开演示数据：
1. 使用你自己编写的合成硬件说明书（建议）。
2. 或提供官方下载链接（不复制文件本身）。

## 许可

本项目代码部分无 LICENSE 声明（由项目所有者决定，见 ENGINEERING_AUDIT §P1-14）；
**不代表**包含第三方文档的许可。使用本仓库数据前请自行核对版权。
