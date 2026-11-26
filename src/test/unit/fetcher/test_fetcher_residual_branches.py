"""fetcher 域残余分支：适配器契约空返回 / 行业批量失败计数 / 观测失败不中断 / 缓存年龄异常。

补齐的都是「调用方契约错误」「上游观测链路坏掉」「缓存读取异常」这类异常输入下的
对外行为（返回 None/{}、只降级不抛），正常链路用例覆盖不到。
"""

from __future__ import annotations

import logging

import pytest

from src.python.fetcher import chain_diagnostics, fund, industry, price, report_adapters
from src.python.fetcher import quote_adapters
from src.python.fetcher import financial_indicator_adapters as fin_adapters
from src.python.fetcher import index as index_fetcher
from src.python.fetcher.report_locate import locate_keyword_excerpt

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher]


class TestReportAdapterContractGuards:
    def test_datasink_adapter_rejects_non_scalar_doc_id(self):
        adapter = report_adapters.DataSinkReportAdapter()

        assert adapter.extract_data({"source_hint": "datasink", "doc_id": None}) is None

    def test_cninfo_adapter_rejects_blank_announcement_id(self):
        adapter = report_adapters.CninfoReportAdapter()

        assert adapter.extract_data({"source_hint": "cninfo", "doc_id": "  "}) is None


class TestHithinkQuoteAdapterGuard:
    def test_missing_code_returns_none(self):
        assert quote_adapters.HithinkQuoteAdapter().extract_data({"code": None}) is None


class TestFinancialIndicatorAdapterGuard:
    def test_missing_code_returns_none(self):
        adapter = fin_adapters.AkshareFinancialAdapter()
        assert adapter.extract_data({"code": ""}) is None


class TestSinaIndexFallbackWithoutMappableCodes:
    def test_unmappable_codes_short_circuit_to_empty(self):
        assert index_fetcher._fetch_indices_from_sina(["no_such_internal_code"]) == {}


class TestReportLocateBlankPreference:
    def test_blank_preference_is_skipped(self):
        excerpt = locate_keyword_excerpt("正文里有关键词，不在目录行", ["  ", "关键词"], 20)
        assert excerpt == ("关键词，不在目录行", "关键词")


class TestProviderAttributionFailureIsNonFatal:
    def test_mark_provider_used_exception_is_swallowed(self, monkeypatch, caplog):
        from src.python.core import degradation

        caplog.set_level(logging.DEBUG, logger="invest")

        def _boom(*_args, **_kwargs):
            raise RuntimeError("观测链路故障")

        monkeypatch.setattr(degradation, "mark_provider_used", _boom)

        chain_diagnostics._mark_provider_used("history", "sina", "新浪财经")

        assert "provider 归属登记失败" in caplog.text


class _FailedResult:
    """BatchDispatcher 结果的最小替身：明确的失败项（既非成功也未跳过）。"""

    success = False
    skipped = False
    result = None


class _FakeDispatcher:
    """行业批量调度器替身：整批失败，用于验证失败计数告警分支。"""

    def __init__(self, **_kwargs) -> None:
        pass

    def execute_with_cache_check(self, items, **_kwargs):
        return [_FailedResult() for _ in items]

    def retry_failed(self, results, **_kwargs):
        return results

    def shutdown(self, wait: bool = True) -> None:
        pass


class TestIndustryBatchFailureCounting:
    def test_all_failed_batch_still_returns_empty_map(self, monkeypatch):
        from src.python.fetcher import batch

        monkeypatch.setattr(batch, "BatchDispatcher", _FakeDispatcher)
        monkeypatch.setattr(industry, "is_provider_chain_broken", lambda _dt: False)

        assert industry.batch_fetch_industry_data(["600519"]) == {}


class TestPriceCacheCapturedAtFault:
    def test_cache_age_exception_returns_none(self, monkeypatch):
        import src.python.cache as cache_mod

        def _boom(_key):
            raise RuntimeError("缓存层故障")

        monkeypatch.setattr(cache_mod, "get_cache_age", _boom)

        assert price._cache_captured_at("price_600519") is None


class TestFundBenchmarkDoubleCheckedLock:
    def test_second_cache_read_inside_lock_is_used(self, monkeypatch):
        calls = {"n": 0}

        def _cache_get(_key, _ttl):
            calls["n"] += 1
            return None if calls["n"] == 1 else {"000001": "沪深300指数"}

        monkeypatch.setattr(fund, "cache_get", _cache_get)

        assert fund.fetch_fund_benchmark("000001") == "沪深300指数"
