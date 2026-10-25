"""财报正文缺失的标的级负缓存 —— 同一结论不在每份报告里重走取数链路。

现象：持仓里若干标的（银行股/季度报告）在 DataSinking 侧无「管理层讨论与分析」，
章节阶 + 备源都要走一遍 404 与「异源候选拒服务」，单份报告白耗约 3s。
判定为**确定性**缺失（两阶都试过仍无正文）后记 6h 负缓存；索引为空/网络瞬时失败
不进负缓存（否则恢复期被无谓延长）。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.fetcher import financial_report as fr

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher]


@pytest.fixture()
def isolated_cache(tmp_path, monkeypatch):
    """缓存目录隔离（负缓存走真实 cache 层，不 mock）。"""
    from src.python.cache import _paths, _store

    monkeypatch.setattr(_paths, "_CACHE_DIR", str(tmp_path))
    _store.reset_debug_log_state()
    return tmp_path


class TestSymbolMissingNegativeCache:
    def test_second_call_skips_index_and_candidates(self, isolated_cache):
        """首次判定缺失后，第二次不再读索引/不试候选。"""
        with (
            patch.object(fr, "_fetch_index", return_value=[{"doc_id": "1"}]) as index,
            patch.object(fr, "_order_report_candidates", return_value=[{"doc_id": "1"}]),
            patch.object(fr, "_attempt_candidates", return_value=None) as attempt,
            patch.object(fr, "_backup_candidates", return_value=[]),
        ):
            first = fr.fetch_symbol_report_detailed("601398.SS")
            assert first[0] is None and first[1].startswith("目标章节缺失")
            assert index.call_count == 1 and attempt.call_count == 1

            second = fr.fetch_symbol_report_detailed("601398.SS")
        assert second[0] is None
        assert second[1] == first[1], "负缓存应复用同一原因文案"
        assert index.call_count == 1, "命中负缓存后不得再读索引"
        assert attempt.call_count == 1

    def test_index_empty_is_not_cached(self, isolated_cache):
        """索引为空可能是瞬时不可用 → 不写负缓存，下次仍重试。"""
        with patch.object(fr, "_fetch_index", return_value=[]) as index:
            assert fr.fetch_symbol_report_detailed("600519.SS") == (None, fr.REASON_INDEX_EMPTY)
            assert fr.fetch_symbol_report_detailed("600519.SS") == (None, fr.REASON_INDEX_EMPTY)
        assert index.call_count == 2

    def test_success_after_miss_is_not_blocked_by_cache(self, isolated_cache):
        """成功路径不受负缓存影响；且成功后不再写负缓存（不同标的互不干扰）。"""
        with patch.object(fr, "_fetch_index", return_value=[]):
            fr.fetch_symbol_report_detailed("600519.SS")
        record = {"doc_id": "9", "symbol": "000001.SZ"}
        with (
            patch.object(fr, "_fetch_index", return_value=[{"doc_id": "9"}]),
            patch.object(fr, "_order_report_candidates", return_value=[{"doc_id": "9"}]),
            patch.object(fr, "_attempt_candidates", return_value=record),
        ):
            assert fr.fetch_symbol_report_detailed("000001.SZ") == (record, "")
