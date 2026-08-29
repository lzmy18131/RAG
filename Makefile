# -RAG- 开发命令（Windows 用 git-bash/WSL；核心命令在 README 同步提供原始形式）

PYTHON ?= .venv/Scripts/python
ifeq ($(OS),Windows_NT)
PYTHON := .venv/Scripts/python
else
PYTHON := .venv/bin/python
endif
PIP := $(dir $(PYTHON))pip

.PHONY: help install dev lint format typecheck test test-unit eval-build eval-ablation \
        eval-retrieval eval-full eval-online e2e docker-up docker-down benchmark check

help: ## 显示可用命令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## 安装依赖
	$(PIP) install -r requirements.txt

dev: ## 启动后端（开发）
	PYTHONUTF8=1 $(PYTHON) -m uvicorn main:app --reload --port 8000

lint: ## ruff check
	$(PYTHON) -m ruff check src/ tests/ scripts/

format: ## ruff format --check
	$(PYTHON) -m ruff format --check src/ tests/ scripts/

typecheck: ## 类型检查（当前覆盖核心模块；渐进收紧见 docs/ENGINEERING_ROADMAP.md）
	$(PYTHON) -m mypy src --ignore-missing-imports --follow-imports=skip 2>/dev/null || echo "typecheck: 见 roadmap Phase 2（pyright/mypy 渐进接入）"

test: ## 全部测试（离线子集）
	PYTHONPATH= $(PYTHON) -m pytest tests/ -k "not test_phase3 and not test_phase4 and not test_phase5 and not test_phase7_integration and not milvus_collection" -q

test-unit: ## 纯单元测试（最快）
	PYTHONPATH= $(PYTHON) -m pytest tests/test_retrieval_metrics.py tests/test_citation.py tests/test_eval_foundation.py tests/test_ablation.py tests/test_gateway.py tests/test_grounding.py tests/test_semantic_cache.py -q

eval-build: ## 构建版本化评测数据集
	PYTHONPATH= $(PYTHON) scripts/build_evals_datasets.py

eval-ablation: ## 汇总消融表（读取 runs/* 产物）
	PYTHONPATH= $(PYTHON) scripts/ablation.py

eval-retrieval: ## 检索评估（需模型+Milvus 集合；离线时 NOT RUN）
	PYTHONPATH= $(PYTHON) scripts/final_evaluation.py --retrieval-only --dataset golden_100

eval-full: ## 完整评估（需 API key + 模型）
	PYTHONPATH= $(PYTHON) scripts/final_evaluation.py

eval-online: ## 在线评估（需 RUN_ONLINE_EVALS=true + API key）
	RUN_ONLINE_EVALS=true PYTHONPATH= $(PYTHON) scripts/final_evaluation.py

benchmark: ## 性能基准（reranker/cache/concurrency）
	$(PYTHON) scripts/benchmark_reranker.py 2>/dev/null || echo "benchmark 脚本见 benchmark/（Phase 6）"

docker-up: ## Docker 启动
	docker compose up --build

docker-down: ## Docker 停止
	docker compose down

check: lint format test ## CI 主检查
