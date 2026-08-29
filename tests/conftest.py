"""Test configuration — ensures pymilvus can import cleanly and repo root on sys.path."""

import os
import sys
from pathlib import Path

# 保证 `from scripts.xxx import ...` 在 Linux CI 也可用（pytest 不会自动把仓库根加入 sys.path）
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# pymilvus ORM module reads MILVUS_URI at import time and only accepts
# http:// or https:// URIs. Our .env sets "milvus.db" for app use,
# so we must set a valid dummy URI before any pymilvus import.
os.environ.setdefault("MILVUS_URI", "http://localhost:19530")
