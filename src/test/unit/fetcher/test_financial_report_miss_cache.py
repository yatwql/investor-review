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


class TestDocumentEmptyNegativeCache:
    """单篇「确定性空正文」按 (doc_id, section) 记负缓存；传输级失败不记。

    背景（实测）：持仓里 5 只 A 股在 DataSinking 侧都无「管理层讨论与分析」章节，
    每份报告都要逐只重走链路（每只 1~2s，合 10s 左右），而结论是确定性的。
    """

    @staticmethod
    def _patch_chain(monkeypatch, reason: str, result=None):
        calls = {"n": 0}

        def _fake(data_type, provider_map, cache_key, cache_ttl, fn_kwargs=None, transform=None, diagnostics=None):
            calls["n"] += 1
            if diagnostics is not None:
                diagnostics.add("DataSinking", reason)
            return result

        monkeypatch.setattr("src.python.fetcher.chain.fetch_with_fallback", _fake)
        return calls

    def test_deterministic_empty_is_cached(self, isolated_cache, monkeypatch):
        """首次判定「该文档无该章节」后，同一 (doc_id, section) 不再走链路。"""
        calls = self._patch_chain(monkeypatch, "该文档无「管理层讨论与分析」章节")
        assert fr._fetch_document("47990", "管理层讨论与分析") is None
        assert fr._fetch_document("47990", "管理层讨论与分析") is None
        assert calls["n"] == 1, "确定性空结果应命中负缓存"

    def test_transport_failure_is_not_cached(self, isolated_cache, monkeypatch):
        """传输级失败可能是瞬时问题 → 不写负缓存，下次仍重试。"""
        calls = self._patch_chain(monkeypatch, "ConnectTimeout: timed out")
        assert fr._fetch_document("47990", "管理层讨论与分析") is None
        assert fr._fetch_document("47990", "管理层讨论与分析") is None
        assert calls["n"] == 2

    def test_other_section_not_blocked(self, isolated_cache, monkeypatch):
        """负缓存按 (doc_id, section) 隔离：别的章节照常取数。"""
        calls = self._patch_chain(monkeypatch, "该文档无「管理层讨论与分析」章节")
        fr._fetch_document("47990", "管理层讨论与分析")
        fr._fetch_document("47990", "主要会计数据和财务指标")
        assert calls["n"] == 2


class TestDocMissVisibility:
    """命中负缓存的次数必须可观测（INFO 级一行，不靠 DEBUG）。"""

    @staticmethod
    def _patch_chain(monkeypatch):
        def _fake(data_type, provider_map, cache_key, cache_ttl, fn_kwargs=None, transform=None, diagnostics=None):
            if diagnostics is not None:
                diagnostics.add("DataSinking", "该文档无「管理层讨论与分析」章节")
            return None

        monkeypatch.setattr("src.python.fetcher.chain.fetch_with_fallback", _fake)

    def test_two_provider_reasons_are_cached(self, isolated_cache, monkeypatch):
        """真实链路形态：主源「该文档无」+ 备源槽「异源候选拒服务」→ 仍属确定性空。"""
        calls = {"n": 0}

        def _fake(data_type, provider_map, cache_key, cache_ttl, fn_kwargs=None, transform=None, diagnostics=None):
            calls["n"] += 1
            if diagnostics is not None:
                diagnostics.add("DataSinking", "该文档无「管理层讨论与分析」章节")
                diagnostics.add("巨潮资讯", "异源候选拒服务(hint=datasink)")
            return None

        monkeypatch.setattr("src.python.fetcher.chain.fetch_with_fallback", _fake)
        assert fr._fetch_document("47990", "管理层讨论与分析") is None
        assert fr._fetch_document("47990", "管理层讨论与分析") is None
        assert calls["n"] == 1, "两槽都为确定性拒绝时应写负缓存"

    def test_mixed_transport_failure_not_cached(self, isolated_cache, monkeypatch):
        """任一槽为传输级失败 → 整次不缓存（可能瞬时恢复）。"""
        calls = {"n": 0}

        def _fake(data_type, provider_map, cache_key, cache_ttl, fn_kwargs=None, transform=None, diagnostics=None):
            calls["n"] += 1
            if diagnostics is not None:
                diagnostics.add("DataSinking", "该文档无「管理层讨论与分析」章节")
                diagnostics.add("巨潮资讯", "ConnectTimeout: timed out")
            return None

        monkeypatch.setattr("src.python.fetcher.chain.fetch_with_fallback", _fake)
        assert fr._fetch_document("810006", "管理层讨论与分析") is None
        assert fr._fetch_document("810006", "管理层讨论与分析") is None
        assert calls["n"] == 2

    def test_hits_are_counted_and_resettable(self, isolated_cache, monkeypatch):
        self._patch_chain(monkeypatch)
        fr.reset_doc_miss_hits()
        fr._fetch_document("47990", "管理层讨论与分析")  # 首次：写负缓存
        assert fr.doc_miss_hits() == 0
        fr._fetch_document("47990", "管理层讨论与分析")  # 第二次：命中
        fr._fetch_document("47990", "管理层讨论与分析")  # 第三次：命中
        assert fr.doc_miss_hits() == 2
        fr.reset_doc_miss_hits()
        assert fr.doc_miss_hits() == 0

    def test_digest_logs_hit_summary(self, isolated_cache, monkeypatch, caplog):
        """报告级只打一行 INFO 汇总（确定性缺失不是故障）。"""
        import logging

        from src.python.report import financial_report_digest as digest

        monkeypatch.setattr(digest, "datasink_credential_missing", lambda: None)
        monkeypatch.setattr(
            digest,
            "collect_a_share_targets",
            lambda h, p: [{"code": "47990", "symbol": "47990.SS", "name": "演示", "kind": "holding"}],
        )
        monkeypatch.setattr(
            digest,
            "fetch_symbol_report_detailed",
            lambda *a, **k: (
                {
                    "doc_id": "1",
                    "symbol": "47990.SS",
                    "report_period": "2026-09-30",
                    "doc_type": "三季报",
                    "title": "t",
                    "content": "c",
                    "summary": "c",
                    "source": "datasink",
                    "word_count": 1,
                },
                "",
            ),
        )
        monkeypatch.setattr(digest, "doc_miss_hits", lambda: 2)
        monkeypatch.setattr(digest, "reset_doc_miss_hits", lambda: None)
        with caplog.at_level(logging.INFO, logger="invest"):
            digest.build_financial_report_digest([], {})
        assert any("命中负缓存 2 次" in record.getMessage() for record in caplog.records)
