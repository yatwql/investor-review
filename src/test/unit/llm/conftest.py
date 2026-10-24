"""LLM 单元测试共用 fixture（缓存目录隔离）。

放在目录级 `conftest.py` 而非各测试文件：缓存测试文件有四个，隔离逻辑（重定向
`_paths._CACHE_DIR` + 复位「每 key 首见一次」的日志去重）此前各抄一份，漏抄一处
就会出现「用例互相遮蔽命中日志」这类顺序依赖。
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def llm_cache_dir(tmp_path, monkeypatch):
    """把缓存目录隔离到 tmp，并复位缓存层模块级日志去重状态。"""
    from src.python.cache import _paths, _store

    monkeypatch.setattr(_paths, "_CACHE_DIR", str(tmp_path / "cache"))
    _store.reset_debug_log_state()
    yield tmp_path / "cache"
    _store.reset_debug_log_state()
