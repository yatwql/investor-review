"""穿透计算分支契约测试。

锁住的契约：
  - 行业关键词表读盘失败（缺文件 / 损坏 JSON）时降级为空表，不抛出
  - 空名称 → 板块判定返回 "--"
  - 基金层合并跳过无名称的成分项（不产生空键标的）
  - 直接持股合并进已有标的时复用同一标的并追加来源与市值
  - 行业分类数据按代码写入 sector_api / sector / concepts

运行：
  .venv/bin/python -m pytest src/test/unit/report/test_penetration_branches.py -v
"""

from __future__ import annotations

from datetime import date

import pytest

from src.python.core.models import Holding
from src.python.report import penetration
from src.python.report.market_value import DetailRow

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _holding(name: str, code: str, *, account: str = "证券") -> Holding:
    return Holding(account=account, name=name, code=code, shares=100, cost_price=10.0)


def _detail(code: str, name: str = "贵州茅台", market_value: float = 1000.0) -> DetailRow:
    return DetailRow(account="证券", name=name, code=code, market_value=market_value, cost=market_value)


class TestSectorKeywordTable:
    """行业关键词表的加载降级。"""

    def test_missing_file_yields_empty_table(self, tmp_path, monkeypatch):
        monkeypatch.setattr(penetration, "_SECTOR_KEYWORDS_FILE", str(tmp_path / "absent.json"))
        assert penetration._load_sector_keywords() == {}

    def test_corrupt_file_yields_empty_table(self, tmp_path, monkeypatch):
        broken = tmp_path / "sector_keywords.json"
        broken.write_text("{not-json", encoding="utf-8")
        monkeypatch.setattr(penetration, "_SECTOR_KEYWORDS_FILE", str(broken))
        assert penetration._load_sector_keywords() == {}

    def test_blank_name_classified_as_unknown_sector(self):
        assert penetration.classify_sector("") == "--"


class TestFundLayerMerge:
    """基金层穿透合并的分支口径。"""

    def test_unnamed_component_items_are_skipped(self, monkeypatch):
        payload = {
            "110011": {
                "holdings": [
                    {"name": "   ", "code": "600519", "ratio": 40.0},
                    {"name": "贵州茅台", "code": "600519", "ratio": 10.0},
                ],
                "date": date.today().isoformat(),
            }
        }
        monkeypatch.setattr(penetration, "fetch_fund_holdings_batch", lambda codes: payload)
        monkeypatch.setattr(penetration, "_prefetch_manager_data", lambda code: None)

        result = penetration._merge_fund_layer(
            [_holding("易方达优质精选混合", "110011", account="支付宝")],
            {"110011": 1000.0},
        )

        assert set(result.merged) == {"贵州茅台"}
        assert result.merged["贵州茅台"]["mv"] == pytest.approx(100.0)


class TestStockLayerMerge:
    """直接持股合并进已有标的的分支。"""

    def test_existing_target_is_reused(self):
        merged = {
            "贵州茅台": {
                "name": "贵州茅台",
                "codes": set(),
                "mv": 0.0,
                "funds": [],
                "sector": "消费",
            }
        }

        penetration._merge_stock_layer([_holding("贵州茅台", "600519")], {"600519": 1000.0}, merged)

        assert merged["贵州茅台"]["codes"] == {"600519"}
        assert merged["贵州茅台"]["mv"] == pytest.approx(1000.0)
        assert merged["贵州茅台"]["funds"] == ["直接持有"]


class TestApplyIndustryData:
    """行业分类数据写入穿透结果的分支。"""

    def test_industry_and_concepts_are_applied(self):
        merged = {"贵州茅台": {"name": "贵州茅台", "codes": {"600519"}, "mv": 0.0, "funds": [], "sector": "--"}}

        reasons = penetration._apply_industry_data(merged, {"600519": {"industry": "白酒", "concepts": ["高端消费"]}})

        assert reasons == ""
        assert merged["贵州茅台"]["sector"] == "白酒"
        assert merged["贵州茅台"]["sector_api"] == "白酒"
        assert merged["贵州茅台"]["concepts"] == ["高端消费"]

    def test_unknown_code_leaves_entry_untouched(self):
        merged = {"平安银行": {"name": "平安银行", "codes": {"000001"}, "mv": 0.0, "funds": [], "sector": "--"}}

        assert penetration._apply_industry_data(merged, {"600519": {"industry": "白酒"}}) == ""
        assert "sector_api" not in merged["平安银行"]
        assert "concepts" not in merged["平安银行"]


class TestIndustryPrefetch:
    """行业预取与补取的两段口径。"""

    def _fund_layer(self, merged_entry: dict):
        from types import SimpleNamespace

        return SimpleNamespace(
            merged={merged_entry["name"]: merged_entry},
            unknown_mv=0.0,
            failed_count=0,
            failed_details=[],
            stale_count=0,
            stale_details=[],
            period_details={},
        )

    def test_prefetch_exception_falls_back_to_on_demand_fetch(self, monkeypatch):
        calls: list[list[str]] = []

        def _batch(codes):
            calls.append(list(codes))
            if len(calls) == 1:
                raise RuntimeError("prefetch boom")
            return {}

        monkeypatch.setattr("src.python.fetcher.industry.batch_fetch_industry_data", _batch)

        result = penetration._compute_penetration_top10_uncached(
            [_holding("贵州茅台", "600519")],
            [_detail("600519")],
        )

        assert calls == [["600519"], ["600519"]], "预取异常后须按需补取（不得直接放弃行业分类）"
        assert result["top10"]

    def test_prefetched_and_remaining_codes_are_both_applied(self, monkeypatch):
        calls: list[list[str]] = []

        def _batch(codes):
            calls.append(list(codes))
            if len(calls) == 1:
                return {"600519": {"industry": "白酒"}}
            return {"000858": {"industry": "食品饮料"}}

        monkeypatch.setattr(
            penetration,
            "_merge_fund_layer",
            lambda funds, detail_map: self._fund_layer(
                {"name": "五粮液", "codes": {"000858"}, "mv": 500.0, "funds": ["易方达"], "sector": "--"}
            ),
        )
        monkeypatch.setattr("src.python.fetcher.industry.batch_fetch_industry_data", _batch)

        result = penetration._compute_penetration_top10_uncached(
            [_holding("贵州茅台", "600519")],
            [_detail("600519")],
        )

        assert calls == [["600519"], ["000858"]], "只补取预取未覆盖的代码"
        sectors = {item["name"]: item["sector"] for item in result["top10"]}
        assert sectors["贵州茅台"] == "白酒", "预取命中的代码须写入分类结果"
        assert sectors["五粮液"] == "食品饮料", "预取未覆盖的代码补取后也须写入"
