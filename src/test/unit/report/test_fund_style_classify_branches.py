"""基金风格判定（`report/fund_style_classify.py`）降级分支契约测试。

锁住的契约：
  - 无市值数据时按代码段估算规模，且结果标记为估算值
  - 扩展数据取数异常（push2 / Tencent）降级为 None，Tencent 失败计入 provider 失败
  - 行业数据 fetcher 模块缺失时行业平均 PE 功能整体降级为空映射
  - 行业数据缺行业字段的标的既不进行业分组也不进结果映射
  - 行业平均 PE 编排内部异常降级为空映射（不冒泡）
  - 批量腾讯预取在空代码表时不发并发请求
  - 批量腾讯预取单路异常只丢该路结果，其余照常返回
  - 预取阶段已有会话缓存的代码不再探 push2
  - 占比非正的持仓不参与风格权重累加
  - 全部持仓权重为 0 时最终风格为 "--"（不产生空标签）

运行：
  .venv/bin/python -m pytest src/test/unit/report/test_fund_style_classify_branches.py -v
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from src.python.report import fund_style_classify as fsc
from src.python.fetcher import fund_style_extended as fse

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.usefixtures("offline_external_sources")]


@pytest.fixture(autouse=True)
def _clear_extended_cache():
    """扩展数据走文件缓存（extended_ 前缀），用例间必须隔离，否则命中他例写入值。"""
    from src.python.cache import clear_by_prefix
    from src.python.core.provider_registry import get_registry

    clear_by_prefix("extended_")
    get_registry().session_cache_clear("extended")
    yield
    clear_by_prefix("extended_")
    get_registry().session_cache_clear("extended")


class TestClassifyStockDegrade:
    """单只股票判定的降级口径。"""

    def test_missing_market_cap_falls_back_to_code_size(self):
        result = fsc._classify_stock("600519", None, 25.0)

        assert result["is_estimated"] is True
        assert result["style"] == "混合", "无市值即无法定风格，须落混合而非臆测"
        assert result["size"] == "大盘"

    def test_missing_pe_keeps_size_and_marks_estimate(self):
        result = fsc._classify_stock("600519", 1e11, None)

        assert result == {"size": "大盘", "style": "混合", "is_estimated": True}


class TestPush2ExtendedDegrade:
    """push2 扩展数据取数异常。"""

    def test_fetch_exception_degrades_to_none(self, monkeypatch):
        def _boom(_code):
            raise RuntimeError("industry boom")

        monkeypatch.setattr("src.python.fetcher.industry.fetch_industry_data_cached", _boom)

        assert fse.push2_extended("600519") is None


class TestTencentExtendedDegrade:
    """Tencent 扩展数据取数与失败留痕。"""

    def test_no_usable_field_returns_none(self, monkeypatch):
        monkeypatch.setattr(
            "src.python.fetcher.price.fetch_market_data",
            lambda code, name="": {"market_cap": 0, "pe": -3.0},
        )

        assert fse.tencent_extended("600519", "贵州茅台") is None

    def test_fetch_exception_records_provider_failure(self, monkeypatch):
        def _boom(_code, _name=""):
            raise RuntimeError("tencent boom")

        reg = MagicMock()
        monkeypatch.setattr("src.python.fetcher.price.fetch_market_data", _boom)
        monkeypatch.setattr("src.python.core.provider_registry.get_registry", lambda: reg)

        assert fse.tencent_extended("600519", "贵州茅台") is None
        reg.record_failure.assert_called_once_with("tencent_style", "extended:600519")


class TestIndustryAvgPeDegrade:
    """行业平均 PE 的降级与跳过口径。"""

    def test_missing_fetcher_module_degrades_to_empty(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "src.python.fetcher.industry", None)

        assert fsc._get_industry_avg_pe(["600519"]) == {}

    def test_missing_industry_field_is_skipped(self, monkeypatch):
        monkeypatch.setattr(
            "src.python.fetcher.industry.fetch_industry_data_cached",
            lambda code: {"pe": 25.0},
        )

        assert fsc._get_industry_avg_pe(["600519"]) == {}

    def test_internal_exception_degrades_to_empty(self, monkeypatch):
        def _boom(_code):
            raise RuntimeError("industry boom")

        monkeypatch.setattr("src.python.fetcher.industry.fetch_industry_data_cached", _boom)

        assert fsc._get_industry_avg_pe(["600519"]) == {}


class TestBatchTencentExtended:
    """批量腾讯预取的输入与单路异常口径。"""

    def test_empty_codes_yields_no_result(self):
        assert fse.batch_tencent_extended([]) == {}

    def test_single_route_failure_keeps_other_results(self, monkeypatch):
        payload = {"600519": {"market_cap": 1e11}, "000858": {"pe": 15.0}}

        def _fetch(code, _name=""):
            if code == "000858":
                raise RuntimeError("route boom")
            return payload[code]

        monkeypatch.setattr(fse, "tencent_extended", _fetch)

        assert fse.batch_tencent_extended(["600519", "000858"]) == {"600519": payload["600519"]}


class TestPrefetchSkipsCached:
    """预取阶段对已有会话缓存的代码不再探 push2。"""

    def test_cached_code_skips_push2_probe(self, monkeypatch):
        from src.python.core.provider_registry import get_registry

        get_registry().session_cache_set("extended", "600519", {"market_cap": 1e11})
        probe = MagicMock(return_value={"market_cap": 1e11})
        monkeypatch.setattr(fse, "push2_extended", probe)

        fse.prefetch_extended_data(
            [{"name": "贵州茅台", "code": "600519", "ratio": 10.0}],
            get_registry(),
        )

        probe.assert_not_called()


class TestStockStyleWeights:
    """逐只持仓的权重累加口径。"""

    def test_non_positive_ratio_holding_is_skipped(self, monkeypatch):
        from src.python.core.provider_registry import get_registry

        monkeypatch.setattr(fse, "push2_extended", lambda code: {"market_cap": 1e11, "pe": 25.0})

        styles, size_weights, style_weights, total_weight, has_estimated = fsc._classify_stock_styles(
            [
                {"name": "贵州茅台", "code": "600519", "ratio": 0},
                {"name": "五粮液", "code": "000858", "ratio": None},
            ],
            get_registry(),
            {},
        )

        assert styles == []
        assert total_weight == 0.0
        assert has_estimated is False
        assert sum(size_weights.values()) == 0.0
        assert sum(style_weights.values()) == 0.0


class TestFinalizeFundStyle:
    """最终风格装配的零权重口径。"""

    def test_zero_total_weight_yields_empty_label(self):
        result = fsc._finalize_fund_style(
            "110011",
            [{"name": "贵州茅台", "code": "600519"}],
            0.0,
            {"大盘": 0.0, "中盘": 0.0, "小盘": 0.0},
            {"价值": 0.0, "成长": 0.0, "混合": 0.0},
            True,
        )

        assert result == {"code": "110011", "style": "--", "is_estimated": False, "details": []}
