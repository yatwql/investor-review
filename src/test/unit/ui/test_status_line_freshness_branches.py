# -*- coding: utf-8 -*-
"""页头状态行的降级分支（`tui/status_line.py`）：本地读数的空态与整行兜底。

锁住的契约：
  - 新鲜度只认价格缓存（其余缓存文件与读不到 stat 的文件跳过，不影响结果）
  - 缓存内容形态异常（非 dict / 无数据日期 / 新鲜度判定不可得）→ 新鲜度 —
  - 数据偏旧 → 黄色段 + 动作提示
  - 任一段取数抛异常 → 整行降级为 `状态 │ —`，不向调用方抛出
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import pytest

from src.python.core.ansi_colors import RESET, YELLOW
from src.python.tui import status_line

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


def _cache_dir_with(tmp_path, name: str, payload: object) -> str:
    """写一个缓存文件到临时目录，返回目录路径。"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(exist_ok=True)
    (cache_dir / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(cache_dir)


class TestFreshnessSkipAndDegrade:
    def test_non_price_cache_files_are_skipped(self, tmp_path, monkeypatch):
        """目录里只有非价格缓存：新鲜度 —（不把别的缓存日期当行情日期）。"""
        cache_dir = _cache_dir_with(tmp_path, "holdings_abc_v1.json", {"_data": {"price_date": "2026-10-07"}})
        monkeypatch.setattr("src.python.cache.get_cache_dir", lambda: cache_dir)

        assert status_line._freshness_part() == "新鲜度 —"

    def test_unreadable_stat_is_skipped(self, tmp_path, monkeypatch):
        """文件 stat 失败：跳过该文件，不中断整段读数。"""
        cache_dir = _cache_dir_with(tmp_path, "price_demo_v1.json", {"_data": {"price_date": "2026-10-07"}})
        monkeypatch.setattr("src.python.cache.get_cache_dir", lambda: cache_dir)

        def _boom(_path):
            raise OSError("stat failed")

        monkeypatch.setattr(os.path, "getmtime", _boom)

        assert status_line._freshness_part() == "新鲜度 —"

    def test_non_dict_payload_degrades(self, tmp_path, monkeypatch):
        """缓存内容不是 dict：无法取日期 → 新鲜度 —。"""
        cache_dir = _cache_dir_with(tmp_path, "price_demo_v1.json", {"_data": {"price_date": "2026-10-07"}})
        monkeypatch.setattr("src.python.cache.get_cache_dir", lambda: cache_dir)
        monkeypatch.setattr("src.python.cache.get", lambda *_a, **_k: "corrupted")

        assert status_line._freshness_part() == "新鲜度 —"

    def test_missing_price_date_degrades(self, tmp_path, monkeypatch):
        """缓存里没有价格日期 → 新鲜度 —。"""
        cache_dir = _cache_dir_with(tmp_path, "price_demo_v1.json", {"_data": {"price_date": "2026-10-07"}})
        monkeypatch.setattr("src.python.cache.get_cache_dir", lambda: cache_dir)
        monkeypatch.setattr("src.python.cache.get", lambda *_a, **_k: {"_data": {"price": 1.23}})

        assert status_line._freshness_part() == "新鲜度 —"

    def test_freshness_summary_unavailable_degrades(self, tmp_path, monkeypatch):
        """新鲜度判定不可得（无交易日基准等）→ 新鲜度 —。"""
        cache_dir = _cache_dir_with(tmp_path, "price_demo_v1.json", {"_data": {"price_date": "2026-10-07"}})
        monkeypatch.setattr("src.python.cache.get_cache_dir", lambda: cache_dir)
        monkeypatch.setattr("src.python.cache.get", lambda *_a, **_k: {"_data": {"price_date": "2026-10-07"}})
        monkeypatch.setattr(
            "src.python.core.data_freshness.header_freshness",
            lambda _raw: None,
        )

        assert status_line._freshness_part() == "新鲜度 —"


class TestFreshnessStale:
    def test_stale_data_is_highlighted_with_action(self, tmp_path, monkeypatch):
        """数据偏旧：黄色段 + 动作提示（提示行据此出现）。"""
        cache_dir = _cache_dir_with(tmp_path, "price_demo_v1.json", {"_data": {"price_date": "2026-10-07"}})
        monkeypatch.setattr("src.python.cache.get_cache_dir", lambda: cache_dir)
        monkeypatch.setattr("src.python.cache.get", lambda *_a, **_k: {"_data": {"price_date": "2026-10-07"}})
        monkeypatch.setattr(
            "src.python.core.data_freshness.header_freshness",
            lambda _raw: {"date": "2026-10-07", "age_days": 30, "stale": True},
        )

        part = status_line._freshness_part()

        expected = f"{YELLOW}新鲜度 {datetime.strptime('2026-10-07', '%Y-%m-%d').date():%m-%d}（30天）{RESET}"
        assert part == expected
        assert part.action, "偏旧须带动作提示（否则用户不知道要更新行情缓存）"


class TestStatusLineTotalFallback:
    def test_segment_exception_degrades_whole_line(self, monkeypatch):
        """任一段抛异常：整行降级为 `状态 │ —`，不向调用方抛出。"""
        status_line.reset_status_memo()

        def _boom():
            raise RuntimeError("segment boom")

        monkeypatch.setattr(status_line, "_last_report_part", _boom)

        assert status_line.build_status_line(now=1.0) == "状态 │ —"
