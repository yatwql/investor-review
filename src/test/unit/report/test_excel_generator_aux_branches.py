"""Excel 生成器 basic 路径辅助块装配的三条分支。

- ``_ensure_market_sentiment``：编排层未注入时就地组装；组装返回 None 时不改写 pipeline_data；
- ``_ensure_prosperity_framework``：实验性诊断装配抛异常只降级（告警 + 不写键，主报告不受影响）；
- ``_finalize_and_save``：匿名化模式非 off 时对产物做真名清扫（off 恒等跳过）。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from openpyxl import Workbook

from src.python.report.excel_generator import (
    _ensure_market_sentiment,
    _ensure_prosperity_framework,
    _finalize_and_save,
)
from src.python.report.progress import SilentProgressReporter

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]

_HOLDINGS = [{"code": "000001", "name": "甲基金", "shares": 10.0, "cost": 1.0}]


def test_market_sentiment_fills_missing_namespace():
    """编排层未注入 market_sentiment_data 时就地组装并写入（None 入参也要新建字典）。"""
    with patch(
        "src.python.report._report_aux_metrics.compute_market_sentiment_data",
        return_value={"temperature": 55.0},
    ):
        out = _ensure_market_sentiment(None, _HOLDINGS, {"top10": []}, SilentProgressReporter())

    assert out == {"market_sentiment_data": {"temperature": 55.0}}, "None 入参须新建字典承载组装结果"


def test_market_sentiment_none_result_leaves_pipeline_untouched():
    """组装返回 None（数据不足）时 pipeline_data 原样返回，不得写入空块。"""
    with patch("src.python.report._report_aux_metrics.compute_market_sentiment_data", return_value=None):
        out = _ensure_market_sentiment({"market_sentiment_data": None}, _HOLDINGS, None, SilentProgressReporter())

    assert out == {"market_sentiment_data": None}


def test_prosperity_framework_exception_degrades_without_key(caplog):
    """实验性诊断装配抛异常 → 只记 warning、不写 prosperity_framework_data。"""
    pipeline = {"market_sentiment_data": {"temperature": 1.0}}
    with (
        patch(
            "src.python.report._report_aux_metrics.compute_prosperity_framework_data",
            side_effect=RuntimeError("诊断炸了"),
        ),
        caplog.at_level("WARNING", logger="invest"),
    ):
        out = _ensure_prosperity_framework(
            pipeline, _HOLDINGS, {"details": []}, None, None, None, SilentProgressReporter()
        )

    assert out == pipeline, "装配失败不得写入半个诊断块"
    assert "诊断装配异常" in caplog.text


def test_finalize_masks_workbook_when_anonymization_enabled(tmp_path):
    """匿名化模式非 off → 保存前对字符串单元格做真名→代号清扫。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "汇总"
    ws["A1"] = "甲基金"
    save_workbook = MagicMock(return_value=str(tmp_path / "r.xlsx"))
    data = {"total_mv": 1.0, "total_cost": 1.0, "total_profit": 0.0, "today_profit": 0.0}

    with patch("src.python.config.anonymizer.get_anonymization_mode", return_value="full_anonymous"):
        _finalize_and_save(wb, {"summary": ws}, _HOLDINGS, save_workbook, data, str(tmp_path), SilentProgressReporter())

    assert ws["A1"].value != "甲基金", "非 off 模式下产物单元格的真名必须已被代号替换"
    assert ws["A1"].value.startswith("品种")
