"""report/_report_helpers.py 的类型校验与匿名行不变分支。

锁住的契约：
  - 可选区块构建函数抛异常时写 available=False 降级 dict，不向上抛；
  - prepare/snapshot 的类型异常只告警，不中断编排；
  - 明细行既无别名替换、也非 full_anonymous 时原样返回（不改对象）。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.python.report import _report_helpers as rh

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def test_optional_section_builder_failure_degrades_in_place() -> None:
    def _boom(_namespace: str | None) -> dict:
        raise RuntimeError("快照目录不可读")

    pipeline_data = rh._inject_optional_section(
        None,
        data_key="snapshot_diff_data",
        builder=_boom,
        log_tag="snapshot_diff",
        failure_reason="快照差异摘要构建失败",
    )
    assert pipeline_data["snapshot_diff_data"]["available"] is False
    assert pipeline_data["snapshot_diff_data"]["reason"] == "快照差异摘要构建失败"


def _capture_warnings(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    messages: list[str] = []
    monkeypatch.setattr(rh.logger, "warning", lambda msg, *args, **kwargs: messages.append(msg % args if args else msg))
    return messages


def test_prepare_completeness_tolerates_non_dict_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = _capture_warnings(monkeypatch)
    rh._validate_prep_completeness(["非 dict"])
    assert any("prepare_report_data 返回类型异常: list" in msg for msg in messages)


def test_prepare_completeness_warns_on_unexpected_value_type(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = _capture_warnings(monkeypatch)
    prep = {key: None for key in ("total_mv", "total_cost", "total_profit", "total_today_profit", "categories")}
    prep.update(
        {
            "a_indices": None,
            "holdings_details": None,
            "today_str": None,
            "output_dir": None,
            "news_top_count": None,
            "risk_metrics": object(),
        }
    )
    rh._validate_prep_completeness(prep)
    assert any("prep.risk_metrics 类型异常: object" in msg for msg in messages)


def test_snapshot_validation_tolerates_non_dict_payload_and_bad_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = _capture_warnings(monkeypatch)
    rh._validate_pipeline_snapshot(["非 dict"])
    rh._validate_pipeline_snapshot({"diff": "非 dict"})
    assert any("pipeline_data 类型异常: list" in msg for msg in messages)
    assert any("pipeline_data.diff 类型异常: str" in msg for msg in messages)


def test_anonymize_detail_row_returns_row_when_nothing_changes() -> None:
    row = SimpleNamespace(name="贵州茅台", market_value=1000.0, cost=900.0)
    assert rh._anonymize_detail_row(row, {"其它标的": "代号A"}, "code_display") is row
