"""cache 域残余分支：启动敏感缓存清理的两条故障路径 + 新闻条数配置读取 + 基金经理零结果。

``cache/__init__.py`` 的启动清理只在**导入期**执行，「清理到东西」与「清理抛异常」
两个分支正常链路跑不到，故按模块重载触达（重载后立刻卸载补丁再重载一次，避免把
桩函数留在模块属性上污染后续用例）。
"""

from __future__ import annotations

import importlib
import logging

import pytest

import src.python.cache as cache_pkg
from src.python.cache import _cache_refresh
from src.python.cache import _cleanup
from src.python.cache.operations import CacheUpdateResult

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _reload_with_cleaner(monkeypatch, cleaner) -> None:
    monkeypatch.setattr(_cleanup, "clean_sensitive", cleaner)
    importlib.reload(cache_pkg)
    monkeypatch.undo()
    importlib.reload(cache_pkg)


class TestStartupSensitiveCleanup:
    def test_removed_files_are_reported_at_startup(self, monkeypatch, caplog):
        caplog.set_level(logging.INFO, logger="invest")

        _reload_with_cleaner(monkeypatch, lambda **_kw: 3)

        assert "启动清理" in caplog.text

    def test_cleaner_failure_does_not_break_import(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG, logger="invest")

        def _boom(**_kwargs):
            raise OSError("目录不可读")

        _reload_with_cleaner(monkeypatch, _boom)

        assert "启动敏感缓存清理失败" in caplog.text
        assert cache_pkg.get_cache_path("probe")  # 包仍然可用


class TestNewsTopCountConfig:
    def test_configured_value_is_used(self, monkeypatch):
        monkeypatch.setattr("src.python.config.get_config", lambda: {"news_top_count": 42})

        assert _cache_refresh._get_news_top_count() == 42


class _ZeroFuture:
    def result(self) -> int:
        return 0


class _ZeroPool:
    def submit(self, _fn, _arg) -> _ZeroFuture:
        return _ZeroFuture()


class _RecordingReporter:
    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.okays: list[str] = []

    def ok(self, message: str) -> None:
        self.okays.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


class TestExtendedCacheZeroCounts:
    def test_zero_manager_count_warns(self, monkeypatch, tmp_path):
        class _Holding:
            code = "005827"
            name = "易方达蓝筹精选"

        monkeypatch.setattr(_cache_refresh, "_get_pool", _ZeroPool)
        result = CacheUpdateResult()
        reporter = _RecordingReporter()

        _cache_refresh._refresh_extended_caches([_Holding()], [_Holding()], result, reporter)

        assert result.manager_ok == 0
        assert "基金经理 获取失败" in reporter.warnings
