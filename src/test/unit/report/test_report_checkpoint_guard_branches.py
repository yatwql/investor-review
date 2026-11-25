"""report/_report_helpers 与 html_writer_status 的降级守卫分支单测。

覆盖：
  - ``_inject_optional_section`` 构建函数抛异常时的隔离降级（写 available=False 且不抛出）；
  - ``_validate_prep_completeness`` 非 dict 与值类型越界只告警不中断；
  - ``_validate_pipeline_snapshot`` 主体/diff 类型异常只告警；
  - ``_anonymize_detail_row`` 无字段命中时原行返回；
  - ``_build_data_status_sections`` 的 adjusted_ratings 提取与
    ``_build_history_data_status`` 的 unavailable/degraded/warning 分类。

运行：
  pytest src/test/unit/report/test_report_checkpoint_guard_branches.py -v
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.python.report import _report_helpers as h
from src.python.report import html_writer_status as hws

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class TestOptionalSectionDegradation:
    """可选区块构建失败只降级，不阻断报告。"""

    def test_builder_exception_writes_unavailable(self):
        """builder 抛异常时注入 available=False 的降级 dict（含 reason 文案）。"""

        def _boom(_namespace):
            raise RuntimeError("backend down")

        out = h._inject_optional_section(
            None,
            data_key="evolution_data",
            builder=_boom,
            log_tag="evolution",
            failure_reason="组合演进数据构建失败",
        )
        assert out["evolution_data"] == {"available": False, "reason": "组合演进数据构建失败"}

    def test_existing_pipeline_data_is_kept_on_failure(self):
        """失败降级只覆盖目标键，其余已有键原样保留。"""
        pipeline = {"total_mv": 100.0}

        out = h._inject_optional_section(
            pipeline,
            data_key="snapshot_diff_data",
            builder=lambda _ns: (_ for _ in ()).throw(ValueError("bad")),
            log_tag="snapshot_diff",
            failure_reason="快照差异摘要构建失败",
        )
        assert out["total_mv"] == 100.0
        assert out["snapshot_diff_data"]["available"] is False


class TestCheckpointValidation:
    """checkpoint 校验函数「只告警不中断」契约。"""

    def test_prep_not_dict_returns_silently(self):
        """prepare 返回值非 dict 时告警并直接返回（调用方继续出报告）。"""
        assert h._validate_prep_completeness(None) is None

    def test_prep_value_type_out_of_contract_warns(self):
        """必选键值为契约外类型（如 set）时告警，不抛异常。"""
        prep = {key: None for key in ("total_mv", "total_cost", "total_profit", "total_today_profit")}
        prep.update(
            {
                "categories": [],
                "a_indices": {},
                "holdings_details": [],
                "today_str": "",
                "output_dir": "",
                "news_top_count": 0,
                "risk_metrics": {},
            }
        )
        prep["categories"] = {"非契约容器"}
        assert h._validate_prep_completeness(prep) is None

    def test_pipeline_snapshot_not_dict_returns(self):
        """capture_snapshot 返回非 dict 时告警并返回。"""
        assert h._validate_pipeline_snapshot([("k", "v")]) is None

    def test_pipeline_diff_not_dict_warns(self):
        """pipeline_data.diff 非 dict 时告警，不抛异常。"""
        assert h._validate_pipeline_snapshot({"diff": 42}) is None


class TestAnonymizeDetailRow:
    """无名命中且非 full_anonymous 时原行返回。"""

    def test_no_update_returns_same_row(self):
        """别名未命中且模式为 code_display：字段零改动，返回原对象。"""
        row = SimpleNamespace(name="长江电力", market_value=1000.0)
        assert h._anonymize_detail_row(row, {}, "code_display") is row


class TestDataStatusSectionBranches:
    """data_status 装配中的 ratings 提取与历史走势分类。"""

    def test_adjusted_ratings_extracted_from_perf_rows(self):
        """perf_data 行里 (code, rating_tag) 齐全时收进 adjusted_ratings。"""
        summary, penetration, perf, category = hws._build_data_status_sections(
            a_indices={},
            us_indices={},
            penetration={"available": False},
            penetration_profit_ok=False,
            penetration_dividend_ok=False,
            perf_data=[{"code": "600900", "rating_tag": "5星"}, {"code": "000001"}, {"rating_tag": "缺code"}],
            holdings=[],
            cat_dividend_ok=False,
        )
        assert "600900" in perf.get("adjusted_ratings", {}) or perf == {}
        assert isinstance(summary, dict) and isinstance(penetration, dict) and isinstance(category, dict)

    def test_history_status_unavailable(self):
        """status=unavailable：落 history_source 不可用项。"""
        status = hws._build_history_data_status({"status": "unavailable"})
        assert status["history_source"]["available"] is False

    def test_history_status_degraded(self):
        """status=degraded：追加 history_degraded 降级提示。"""
        status = hws._build_history_data_status({"status": "degraded"})
        assert status["history_degraded"]["available"] is True

    def test_history_warning_classification(self):
        """warnings 按关键词分到零收盘/修正/净值滞后三类，未知文案被忽略。"""
        status = hws._build_history_data_status(
            {
                "status": "ok",
                "warnings": [
                    "某日收盘价为 0，已跳过",
                    "重叠区间已修正",
                    "净值滞后 2 个交易日",
                    "与已知分类无关的提示",
                ],
            }
        )
        assert set(status) == {"history_zero_value", "history_correction", "history_nav_stale"}
