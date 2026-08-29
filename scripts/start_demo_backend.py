"""Playwright E2E demo backend launcher (cross-platform).

启动 DEMO_MODE 后端供 Playwright webServer 使用，并自动选择正确的解释器：

- 若当前解释器缺少项目依赖（如 hermes 等全局 venv 的 `python` 在 PATH 最前），
  则重新 exec 到仓库 `.venv` 内的解释器（Windows: .venv/Scripts/python.exe，
  POSIX: .venv/bin/python）。
- CI（GitHub Actions）依赖装在系统 python 中，无 .venv → 直接使用当前解释器。

用法（由 playwright.config.ts webServer 调用，cwd=仓库根目录）:
    python scripts/start_demo_backend.py
"""

from __future__ import annotations

import importlib.util
import os
import sys


def _repo_root() -> str:
    # scripts/start_demo_backend.py → 仓库根目录
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _venv_python() -> str | None:
    root = _repo_root()
    candidates = (
        os.path.join(root, ".venv", "Scripts", "python.exe"),  # Windows
        os.path.join(root, ".venv", "bin", "python"),  # POSIX
    )
    for cand in candidates:
        if os.path.isfile(cand):
            return cand
    return None


def _has_deps() -> bool:
    # langgraph/uvicorn 是后端起服务的硬依赖；缺失 → 说明解释器环境不对
    for name in ("langgraph", "uvicorn"):
        if importlib.util.find_spec(name) is None:
            return False
    return True


def main() -> int:
    # 宿主 shell 可能把全局 venv 的 site-packages 注入 PYTHONPATH（如 hermes-agent），
    # 会让重 exec 后的解释器 import 到错误版本 → 启动前清掉
    os.environ.pop("PYTHONPATH", None)
    if not _has_deps():
        vp = _venv_python()
        if vp is not None:
            # 用仓库 venv 的解释器重新执行本脚本
            os.execv(vp, [vp, os.path.abspath(__file__)])
        # 无 venv：信任当前解释器（CI 场景），继续往下走，让 import 报错可见
    os.chdir(_repo_root())
    # 脚本方式执行时 sys.path[0]=scripts/，需显式把仓库根加入（main.py 在根目录）
    sys.path.insert(0, _repo_root())
    os.environ.setdefault("DEMO_MODE", "true")
    import uvicorn  # noqa: PLC0415

    from main import app  # noqa: PLC0415  (chdir + env 就绪后再 import)

    uvicorn.run(app, host="127.0.0.1", port=8000)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
