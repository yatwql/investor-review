"""连续报告的 LLM 缓存命中契约（同进程、同输入、真实 generate_all_llm）。

为什么需要文件级契约测试：缓存是否生效过去只能靠用户手动跑两份报告看日志，
定位成本极高且结论依赖现场。这里把「同输入第二份必须全命中」变成可自动验证的
事实，同时用反例锁住「不得为了命中而忽略真实数据变化」。

覆盖四条契约：
1. 同输入连续两份 → 第二份**预检层**即命中四个基础模块（不只是 worker 层命中）；
2. 数据质量失败事件的条数/累计次数变化（重试轮次、跨会话累计）→ 仍然命中；
3. 行情变化 → 对应模块必须未命中（不为命中而忽略真实变化）；
4. 多链配置下键含 provider 后缀（预检与写侧同源的前提）。
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

# `unit_core` 横切标记：缓存命中契约属核心基础设施行为，需随 P0 `dev-verify` 跑
# （该档选择面不含 `unit_llm`，只标 llm 域会让这批回归只在 P1 才执行）。
pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.unit_core]

_HOLDING_CODE = "600900"

_LLM_CONFIG = {
    "_provider_list": [{"name": "probe-main", "provider": "claude", "api_key": "sk-x"}],
    "_strategy": "priority",
    "_preferred_providers": {},
    "llm_max_concurrency": 2,
}


def _inputs() -> dict:
    """一套自洽的最小输入（指数/持仓/穿透/历史/管线）。"""
    return {
        "a_indices": {"sh000300": {"name": "沪深300", "close": 4000.0, "change_pct": 0.5}},
        "us_indices": {"^IXIC": {"name": "纳斯达克", "close": 18000.0, "change_pct": -0.2}},
        "categories": {"股票": {"market_value": 10000.0, "cost": 9000.0, "count": 1}},
        "holdings_details": [
            {"name": "测试A", "code": _HOLDING_CODE, "cost": 1.0, "shares": 100, "market_value": 120.0}
        ],
        "penetrated_assets": [{"name": "测试A", "code": _HOLDING_CODE, "weight": 100.0}],
        "history_data": {
            "max_drawdown_pct": -15.0,
            "annualized_volatility": 0.17,
            "total_return_pct": -10.0,
            "status": "ok",
        },
        "pipeline_data": {"diff": {"added": [], "removed": []}, "data_degradation": []},
    }


def _degradation(times: int = 1, count: int = 1) -> list[dict]:
    """同一源失败 `times` 次事件，每条自带跨会话累计 `count`。"""
    return [
        {
            "source_key": "industry",
            "tier": "T3",
            "success": False,
            "failure_type": "unreachable",
            "degraded": True,
            "count": count,
        }
        for _ in range(times)
    ]


def _run(inputs: dict, degradation: list[dict]) -> tuple[bool, bool, bool, bool]:
    """跑一次 generate_all_llm（LLM 全 mock），返回四模块命中标志。"""
    from src.python.llm import generators_orchestrator as go

    with (
        patch.object(go, "get_llm_config", return_value=dict(_LLM_CONFIG)),
        patch(
            "src.python.llm.skeleton.call_llm",
            return_value=(
                "<p>生成内容</p>",
                {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 0},
                {"name": "probe-main", "model": "m", "endpoint": "e"},
            ),
        ),
    ):
        out = go.generate_all_llm(
            inputs["a_indices"],
            inputs["us_indices"],
            120.0,
            100.0,
            20.0,
            1.0,
            1,
            inputs["categories"],
            penetrated_assets=inputs["penetrated_assets"],
            holdings_details=inputs["holdings_details"],
            pipeline_data=inputs["pipeline_data"],
            history_data=inputs["history_data"],
            degradation_events=degradation,
        )
    return out[4:8]  # type: ignore[return-value]


@pytest.fixture()
def cache_dir(tmp_path, monkeypatch):
    """把缓存目录重定向到临时目录（不污染真实 data/cache）。"""
    from src.python.cache import _paths

    monkeypatch.setattr(_paths, "_CACHE_DIR", str(tmp_path))
    return tmp_path


def _precheck_summary_lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if "[LLM 预检]" in r.getMessage()]


class TestConsecutiveReportCache:
    def test_second_report_precheck_hits_all_four_modules(self, cache_dir, caplog):
        """同输入的第二份报告：**预检层**就要命中四模块，而不是靠 worker 再查一次。

        只断言返回的 cached 标志不够——预检键拼错时 worker 仍能命中并返回 True，
        表面上「缓存正常」，实际上预检优化与命中统计全部失效（历史缺陷即如此）。
        """
        inputs = _inputs()
        events = _degradation()

        with caplog.at_level(logging.INFO, logger="invest"):
            first = _run(inputs, events)
            assert not any(first), "首份报告不应命中（无缓存）"
            second = _run(inputs, events)

        assert all(second), f"第二份报告应全部命中，实际 {second}"
        summaries = _precheck_summary_lines(caplog)
        assert any("命中 4/4" in line for line in summaries), summaries

    def test_failure_multiplicity_drift_does_not_break_hit(self, cache_dir):
        """失败事件**条数**与累计次数变化不得影响命中。

        回归：数据质量文本曾按事件条数渲染「连接失败: x(2次)」、按跨会话累计渲染
        「累计N次」——两者每轮随重试轮次/历史累计变化，使 health_check 与
        expert_review 的缓存键持续翻新。修复后按源去重、不输出次数。
        """
        inputs = _inputs()
        _run(inputs, _degradation(times=1, count=3))
        flags = _run(inputs, _degradation(times=3, count=9))
        assert all(flags), f"仅失败条数/累计次数变化时第二份应全部命中，实际 {flags}"

    def test_market_change_misses_macro(self, cache_dir):
        """行情变化必须使对应模块未命中——命中不得以忽略真实数据变化为代价。"""
        inputs = _inputs()
        _run(inputs, [])
        changed = dict(inputs)
        changed["a_indices"] = {"sh000300": {"name": "沪深300", "close": 4100.0, "change_pct": 3.0}}
        flags = _run(changed, [])
        assert flags[0] is False, "指数变化时 global_macro 必须重算"

    def test_chain_provider_suffix_present_in_key(self, cache_dir):
        """多链配置下键必须含 provider 后缀（预检与写侧同源的前提）。"""
        _run(_inputs(), [])
        names = [p.name for p in cache_dir.glob("*.json")]
        assert any("_probe-main" in n for n in names), names
