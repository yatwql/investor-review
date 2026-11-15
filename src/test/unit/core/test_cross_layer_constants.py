"""跨层/跨渠道常量的单源守卫 — 同一事实只允许一处定义。

为什么需要这道守卫：同一个事实在多处各写一份时，改动只落到其中一处就会让两条路径
口径分叉——退出码让 CI/脚本判错成败、年化交易日数让夏普/波动率与超额收益各按不同
分母、份额容差让交易事件推断与成本模型对同一笔持仓变动得出不同结论。

守卫方式：断言各处「名字」对应的值**等于单源值**（不断言字面量），单源改变时守卫自动跟随。
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestExitCodesSingleSource:
    """退出码：CLI 与 Web worker 共用 core 协议常量。"""

    def test_cli_uses_core_exit_codes(self):
        from src.python.cli import _handlers
        from src.python.core import constants

        assert _handlers._EXIT_SUCCESS == constants.EXIT_SUCCESS
        assert _handlers._EXIT_PARTIAL == constants.EXIT_PARTIAL
        assert _handlers._EXIT_SEVERE == constants.EXIT_SEVERE

    def test_web_uses_core_exit_codes(self):
        from src.python.core import constants
        from src.python.web import run_generation

        assert run_generation._EXIT_SUCCESS == constants.EXIT_SUCCESS
        assert run_generation._EXIT_PARTIAL == constants.EXIT_PARTIAL
        assert run_generation._EXIT_SEVERE == constants.EXIT_SEVERE

    def test_exit_codes_are_distinct(self):
        from src.python.core import constants

        assert len({constants.EXIT_SUCCESS, constants.EXIT_PARTIAL, constants.EXIT_SEVERE}) == 3


class TestPush2EndpointSingleSource:
    """push2 快照接口：交易状态判定与行业取数共用同一 URL。"""

    def test_all_callers_share_one_url(self):
        from src.python.core import constants, market_hours
        from src.python.providers import eastmoney_industry

        assert market_hours._PUSH2_BASE == constants.EASTMONEY_PUSH2_BASE
        assert eastmoney_industry._PUSH2_BASE == constants.EASTMONEY_PUSH2_BASE


class TestAnalysisConstantsSingleSource:
    """analysis 层统计/容差常量：年化交易日数与份额容差单源在 `_math_utils`。"""

    def test_trading_days_per_year_shared(self):
        from src.python.analysis import (
            _math_utils,
            alignment_correction,
            benchmark_excess,
            metrics_returns,
        )

        for mod in (alignment_correction, benchmark_excess, metrics_returns):
            assert mod._TRADING_DAYS_PER_YEAR == _math_utils.TRADING_DAYS_PER_YEAR

    def test_min_sample_days_shared(self):
        from src.python.analysis import _math_utils, metrics_returns

        assert metrics_returns._MIN_SAMPLE_DAYS == _math_utils._MIN_SAMPLE_DAYS

    def test_shares_eps_shared(self):
        from src.python.analysis import _math_utils, holding_change_events, trade_cost_model

        assert holding_change_events._SHARES_EPS == _math_utils.SHARES_EPS
        assert trade_cost_model._SHARES_EPS == _math_utils.SHARES_EPS
