"""持仓变动度量与事件窗口的口径分支测试。

覆盖：
  - `detect_account_reorder`：缺代码/缺日期的脏事件不参与重排识别
  - `_align`：仅减仓意图 / 减仓意愿与减仓意图一致两态
  - `_date_in_window` / `_ymd` / `_iso_date`：无法解析的时间戳一律不出判定
  - `_contribution_breakdown`：四个市值字段缺一即计 skipped、份额 0 而市值 > 0 亦 skipped
  - `event_window_impact._is_calendar_trading_day` / `assess_direction_match` / `_closes`：
    非法日期、未知方向、脏 K 线行三种降级
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]


def test_detect_account_reorder_skips_events_without_code_or_date():
    """缺代码或缺 period_to 的事件不进清仓/新增集合，重排识别只看可归日的事件。"""
    from src.python.analysis.holding_change_metrics import detect_account_reorder

    events = [
        {"code": "", "action": "清仓", "period_to": "20260105"},
        {"code": "000001", "action": "清仓", "period_to": "未知"},
        {"code": "000001", "action": "清仓", "period_to": "20260105"},
        {"code": "000001", "action": "新增", "period_to": "20260106"},
        {"code": "000002", "action": "新增", "period_to": "20260106"},
    ]

    result = detect_account_reorder(events, min_codes=2)

    assert result is None, "脏事件不计入，仅 1 只品种联动，低于 min_codes=2"


def test_align_short_intent_and_short_action_is_aligned():
    """决策账本仅有减仓意图，且事件为减仓 → 意图「减仓意图」+ 口径一致。"""
    from src.python.analysis.holding_change_metrics import _align
    from src.python.core.decision_ledger import DIRECTION_SHORT

    intent, alignment = _align("减仓", {DIRECTION_SHORT})

    assert intent == "减仓意图"
    assert alignment == "一致"


def test_align_short_intent_with_long_action_is_divergent():
    """仅有减仓意图却发生加仓 → 口径分歧（意图标签仍为减仓意图）。"""
    from src.python.analysis.holding_change_metrics import _align
    from src.python.core.decision_ledger import DIRECTION_SHORT

    intent, alignment = _align("加仓", {DIRECTION_SHORT})

    assert intent == "减仓意图"
    assert alignment == "分歧"


@pytest.mark.parametrize("bad_report_date", ["", "not-a-date", "2026/01/05"])
def test_date_in_window_rejects_unparsable_report_date(bad_report_date):
    """无法解析的登记日不出区间判定（返回 False 而非猜）。"""
    from src.python.analysis.holding_change_metrics import _date_in_window

    assert _date_in_window(bad_report_date, "20260101", "20260131") is False


@pytest.mark.parametrize(("raw", "expected"), [("2026-01-05", "20260105"), ("20260105T150000", "20260105"), ("x", "")])
def test_ymd_normalises_three_shapes(raw, expected):
    """YYYY-MM-DD / YYYYMMDDTHHMMSS 归一到 YYYYMMDD，其余形态返回空串。"""
    from src.python.analysis.holding_change_metrics import _ymd

    assert _ymd(raw) == expected


def test_iso_date_formats_compact_and_iso_timestamps():
    """紧凑时间戳补连字符，已带连字符的截到日，其余返回空串。"""
    from src.python.analysis.holding_change_metrics import _iso_date

    assert _iso_date("20260105T150000") == "2026-01-05"
    assert _iso_date("2026-01-05 15:00:00") == "2026-01-05"
    assert _iso_date("不合法") == ""


def test_contribution_breakdown_skips_incomplete_and_unpriced_events():
    """四个市值字段缺一或「份额 0 而市值 > 0」的事件不计入分解，只累计 skipped。"""
    from src.python.analysis.holding_change_metrics import _contribution_breakdown

    result = _contribution_breakdown(
        [
            {"shares_before": 100.0, "shares_after": 0.0, "value_before": 1000.0, "value_after": 0.0},
            {"shares_before": None, "shares_after": 0.0, "value_before": 1000.0, "value_after": 0.0},
            {"shares_before": 0.0, "shares_after": 50.0, "value_before": 800.0, "value_after": 900.0},
        ]
    )

    assert result["skipped_count"] == 2
    assert result["market_value_change"] == pytest.approx(-1000.0)
    assert result["price_part"] == pytest.approx(0.0)


def test_is_calendar_trading_day_false_on_unparsable_date():
    """日期串非法时判非交易日（降级为「无交易日」而非抛错）。"""
    from src.python.analysis.event_window_impact import _is_calendar_trading_day

    assert _is_calendar_trading_day("2026-13-45") is False


def test_assess_direction_match_unknown_direction_is_indeterminate():
    """方向非上/下/持平时不可判（即使文本极性明确）。"""
    from src.python.analysis.event_window_impact import assess_direction_match

    assert assess_direction_match("震荡", "利好") == "不可判"


def test_closes_skips_non_dict_and_dateless_bars():
    """K 线序列里的非 dict 行与缺日期行静默剔除，只保留可用收盘价。"""
    from src.python.analysis.event_window_impact import _closes

    closes = _closes(["不是字典", {"close": 3.0}, {"date": "2026-01-05", "close": 1.5}])

    assert closes == {"2026-01-05": pytest.approx(1.5)}
