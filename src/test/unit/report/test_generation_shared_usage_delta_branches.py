"""report/_generation_shared.py 的 LLM 用量增量分支。

锁住的契约：
  - 逐模块费用按币种做差（只带出本次真实增量，非零才入表，币种码大写）；
  - 本次有模型记录时原样带出模型清单。
"""

from __future__ import annotations

import pytest

from src.python.report._generation_shared import _usage_delta

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def test_usage_delta_keeps_only_non_zero_module_cost_diff_and_models() -> None:
    baseline = {"per_module": {"summary": {"costs": {"cny": 1.0}}}, "costs": {"cny": 1.0}}
    current = {
        "per_module": {"summary": {"costs": {"cny": 2.5}, "input_tokens": 10}},
        "costs": {"cny": 2.5},
        "models": ["claude-sonnet-4"],
    }

    delta = _usage_delta(current, baseline)

    assert delta["per_module"]["summary"]["costs"] == {"CNY": pytest.approx(1.5)}
    assert delta["models"] == ["claude-sonnet-4"]
