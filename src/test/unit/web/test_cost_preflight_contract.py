"""前端 cost-preflight 与本端费用载荷的字段契约 —— 防"后端改字段、前端静默崩"。

费用一律由后端格式化成展示串（`cost_display` / `forced_cost_display` / `display`），
前端只拼文本、不自拼符号与数值。若前端读了后端不提供的字段，`.toFixed()` 对
`undefined` 抛错——表现为「点生成没反应」（无日志、无提示）。本文件把
"前端读的字段必须由后端提供"钉成可执行断言。

覆盖：
- `forecast_run_cost` 必须给出前端渲染所需字段（含空状态）；
- `budget_status` 必须给出 `display`（一行摘要，前端整行直出）；
- 静态 JS 不得再读取已移除的字段名。
"""

from __future__ import annotations

import pathlib
import re

import pytest

from src.python.llm.cost_forecast import budget_status, forecast_run_cost

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]

_MAIN_JS = pathlib.Path("src/static/web/main.js")

#: 前端弹层渲染所需的 forecast 字段（缺一即 `.toFixed`/字符串拼接出现 `undefined`）
_FORECAST_FIELDS = ("ok", "module_count", "cost_display", "forced_count", "forced_cost_display")

#: 已移除的字段名：前端一旦回读，后端无法提供 → 弹层崩溃
_REMOVED_FORECAST_FIELDS = ("low", "high", "symbol", "forced_low", "forced_high")


@pytest.fixture()
def empty_forecast():
    return forecast_run_cost({}, {}, history=[])


@pytest.mark.parametrize("field", _FORECAST_FIELDS)
def test_forecast_provides_frontend_fields(empty_forecast, field):
    """空计划（无模块）分支也要给全字段：前端不区分空/非空都应该能渲染。"""
    assert field in empty_forecast, f"前端需要 forecast.{field}"


@pytest.mark.parametrize("field", _REMOVED_FORECAST_FIELDS)
def test_forecast_no_longer_exposes_removed_fields(empty_forecast, field):
    """旧字段不再返回：保留它们只会让前端继续按老格式渲染（跨币种拼不出正确串）。"""
    assert field not in empty_forecast


def test_forced_breakdown_uses_same_formatter(empty_forecast):
    """重算区间与总区间同源格式化（避免两处各拼一套符号/精度规则）。"""
    assert empty_forecast["forced_cost_display"] == ""
    assert isinstance(empty_forecast["cost_display"], str)


def test_budget_provides_display_line():
    """预算给出一行可直接上屏的摘要（前端整行直出，不再自拼金额与符号）。"""
    status = budget_status({}, [])
    assert isinstance(status["display"], str)
    assert status["display"], "display 不应为空（无支出时也要说明当前状态）"


def test_frontend_reads_only_backend_provided_fields():
    """静态 JS 不得读取已移除的字段（`f.low` / `f.symbol` / `b.spent` 等）。"""
    source = _MAIN_JS.read_text(encoding="utf-8")
    forbidden = [
        r"\bf\.low\b",
        r"\bf\.high\b",
        r"\bf\.symbol\b",
        r"\bf\.forced_low\b",
        r"\bf\.forced_high\b",
        r"\bb\.spent\b",
        r"\bb\.limit\b",
    ]
    hits = [pattern for pattern in forbidden if re.search(pattern, source)]
    assert not hits, f"前端仍在读已移除字段：{hits}"


def test_frontend_uses_display_strings():
    """前端应消费 `cost_display` / `forced_cost_display` / `display` 这三个展示串。"""
    source = _MAIN_JS.read_text(encoding="utf-8")
    for token in ("cost_display", "forced_cost_display", "b.display"):
        assert token in source, f"前端未使用 {token}"
