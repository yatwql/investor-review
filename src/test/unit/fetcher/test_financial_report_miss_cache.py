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
        # 计数是进程级，先全清再按类注入，避免其它用例的命中串进本次断言
        fr.reset_doc_miss_hits()
        monkeypatch.setattr(digest, "reset_doc_miss_hits", lambda: None)
        # 汇总按 `cache.NegativeCache` 统一清单逐类打一行：把实例计数换成 2 即可
        monkeypatch.setattr(fr.DOC_MISS, "hits", lambda: 2)
        with caplog.at_level(logging.INFO, logger="invest"):
            digest.build_financial_report_digest([], {})
        assert any("空正文（该文档无该章节）命中负缓存 2 次" in record.getMessage() for record in caplog.records)


class TestSectionsUnavailableNegativeCache:
    """章节清单不可得 → 负缓存，`/sections` 不再每份报告重探。

    判定口径：源侧成功应答但无可用章节清单（404 探测未命中 / 200 空列表）时，
    清单结论只取决于源侧解析状态、跨报告稳定——不缓存就会每份报告为同一篇文档
    重发一次 `/sections`（实测 5 篇 × 0.3~1.4s ≈ 5s/份，全缓存运行的数据准备
    主要残差）。传输级失败另走 30min **短退避**（不进 6h 确定性缺失缓存）——避免
    每份报告都为同一篇文档白等一次超时预算（实测单篇 20.7s），又不长时间堵住恢复。
    """

    def test_second_call_skips_sections_probe(self, isolated_cache, monkeypatch):
        calls = {"n": 0}

        def _sections(doc_id):
            calls["n"] += 1
            return None

        monkeypatch.setattr(fr.datasink, "fetch_report_sections", _sections)
        assert fr._fetch_sections("47990") is None
        assert fr._fetch_sections("47990") is None
        assert calls["n"] == 1, "确认不可得后不得再发 /sections 请求"

    def test_transport_failure_opens_backoff_not_deterministic_miss(self, isolated_cache, monkeypatch):
        """传输级失败 → 短退避（30min），**不**进「确定性缺失 6h」负缓存。

        两者语义必须分开：这条只是这次探测挂起了（源侧可能马上恢复，短暂避让即可），
        那条是源侧确认没有清单（结论稳定，6h 不用再问）。
        """
        calls = {"n": 0}

        def _sections(doc_id):
            calls["n"] += 1
            raise RuntimeError("connection reset")

        monkeypatch.setattr(fr.datasink, "fetch_report_sections", _sections)
        assert fr._fetch_sections("47990") is None
        assert fr._fetch_sections("47990") is None
        assert calls["n"] == 1, "退避窗口内不得重探（每轮白等满一个超时预算）"
        assert fr.SECTIONS_BACKOFF.is_missing(fr.SECTIONS_BACKOFF.key("47990")) is True
        assert fr.SECTIONS_MISS.is_missing(fr.SECTIONS_MISS.key("47990")) is False, "传输失败不得当成确定性缺失"

    def test_available_sections_still_cached_positive(self, isolated_cache, monkeypatch):
        calls = {"n": 0}

        def _sections(doc_id):
            calls["n"] += 1
            return ["第三节管理层讨论与分析"]

        monkeypatch.setattr(fr.datasink, "fetch_report_sections", _sections)
        assert fr._fetch_sections("47990") == ["第三节管理层讨论与分析"]
        assert fr._fetch_sections("47990") == ["第三节管理层讨论与分析"]
        assert calls["n"] == 1

    def test_invalidate_clears_negative_cache(self, isolated_cache, monkeypatch):
        """全空正文时清一次清单缓存：负缓存也要清，否则恢复期被无谓延长。"""
        calls = {"n": 0}

        def _sections(doc_id):
            calls["n"] += 1
            return None

        monkeypatch.setattr(fr.datasink, "fetch_report_sections", _sections)
        fr._fetch_sections("47990")
        fr._invalidate_sections_cache("47990")
        fr._fetch_sections("47990")
        assert calls["n"] == 2, "失效后应重新探测（清单可能已被源侧补齐）"

    def test_hits_are_counted_and_resettable(self, isolated_cache, monkeypatch):
        monkeypatch.setattr(fr.datasink, "fetch_report_sections", lambda doc_id: None)
        fr.reset_doc_miss_hits()
        fr._fetch_sections("47990")  # 首次：写负缓存（未命中）→ 不计
        assert fr.sections_miss_hits() == 0
        fr._fetch_sections("47990")
        fr._fetch_sections("47990")
        assert fr.sections_miss_hits() == 2
        fr.reset_doc_miss_hits()
        assert fr.sections_miss_hits() == 0

    def test_transport_failure_opens_short_backoff(self, isolated_cache, monkeypatch):
        """传输级失败（挂起/断连）→ 30min 短退避，下一轮不再白等同一篇的超时预算。

        与「确定性缺失 6h 负缓存」语义不同：那条是源侧确认没有清单，这条只是这次探测
        挂起了；探测只是取数优选路径，短退避止住「每份报告都再撞一次」，又不长时间堵住恢复。
        """
        calls = {"n": 0}

        def _sections(doc_id):
            calls["n"] += 1
            raise RuntimeError("handshake operation timed out")

        monkeypatch.setattr(fr.datasink, "fetch_report_sections", _sections)
        assert fr._fetch_sections("817432") is None
        assert fr._fetch_sections("817432") is None
        assert calls["n"] == 1, "退避窗口内不得再探测 /sections"

    def test_success_clears_backoff(self, isolated_cache, monkeypatch):
        """探测成功即解除退避（源侧恢复后立刻重新用上清单）。"""
        monkeypatch.setattr(
            fr.datasink, "fetch_report_sections", lambda doc_id: (_ for _ in ()).throw(RuntimeError("t"))
        )
        fr._fetch_sections("817432")
        monkeypatch.setattr(fr.datasink, "fetch_report_sections", lambda doc_id: None)
        # 退避窗口内仍跳过（返回 None 且不再请求）
        assert fr._fetch_sections("817432") is None
        fr._invalidate_sections_cache("817432")  # 显式失效不清退避，另用 clear
        fr.SECTIONS_BACKOFF.clear(fr.SECTIONS_BACKOFF.key("817432"))
        mark = {"n": 0}

        def _ok(doc_id):
            mark["n"] += 1
            return ["第三节管理层讨论与分析"]

        monkeypatch.setattr(fr.datasink, "fetch_report_sections", _ok)
        assert fr._fetch_sections("817432") == ["第三节管理层讨论与分析"]
        assert mark["n"] == 1
        # 成功后再探一次：正向缓存命中，不再请求
        assert fr._fetch_sections("817432") == ["第三节管理层讨论与分析"]
        assert mark["n"] == 1

    def test_unusable_sections_list_is_negative_cached(self, isolated_cache, monkeypatch):
        """源侧返回**非空但不可用**的清单（只有封面/目录几项）→ 失效同时记负缓存。

        实测形态：`/sections` 返回 3 项「公司名 / 年度报告 / 重要提示」，匹配不到任何
        偏好章节 → 回退偏好名直取仍全空 → 该清单每次都会走到失效分支。只失效不记负缓存，
        等于每份报告都为同一篇文档重探 `/sections` 并重试同一批死章节名（1~3s/篇）。
        """
        calls = {"n": 0}

        def _sections(doc_id):
            calls["n"] += 1
            return ["某公司", "2025 年年度报告", "重要提示"]

        monkeypatch.setattr(fr.datasink, "fetch_report_sections", _sections)
        monkeypatch.setattr(fr, "_fetch_document", lambda *a, **k: None)
        fr.reset_doc_miss_hits()
        assert fr._collect_doc_sections(817432, ["管理层讨论与分析"])[1] == []
        assert fr._collect_doc_sections(817432, ["管理层讨论与分析"])[1] == []
        assert calls["n"] == 1, "不可用清单确认一次后，下一轮不得再探 /sections"
        assert fr.sections_miss_hits() == 1

    def test_unusable_sections_miss_can_be_invalidated(self, isolated_cache, monkeypatch):
        """负缓存可被显式失效（源侧补齐时不必干等 TTL）。"""
        monkeypatch.setattr(fr.datasink, "fetch_report_sections", lambda doc_id: None)
        fr._fetch_sections("817432")
        assert fr._fetch_sections("817432") is None  # 命中负缓存
        fr._invalidate_sections_cache("817432")
        mark_calls = {"n": 0}
        monkeypatch.setattr(
            fr.datasink, "fetch_report_sections", lambda doc_id: (mark_calls.__setitem__("n", 1), None)[1]
        )
        fr._fetch_sections("817432")
        assert mark_calls["n"] == 1, "失效后必须重新探测"

    def test_digest_logs_sections_miss_summary(self, isolated_cache, monkeypatch, caplog):
        """报告级一行 INFO：让「这轮省了几次 /sections 探测」可直接读日志确认。"""
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
        fr.reset_doc_miss_hits()
        monkeypatch.setattr(digest, "reset_doc_miss_hits", lambda: None)
        monkeypatch.setattr(fr.SECTIONS_MISS, "hits", lambda: 3)
        with caplog.at_level(logging.INFO, logger="invest"):
            digest.build_financial_report_digest([], {})
        assert any("章节清单不可得命中负缓存 3 次" in record.getMessage() for record in caplog.records)
