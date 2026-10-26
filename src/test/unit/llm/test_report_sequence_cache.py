"""连续报告的 LLM 缓存命中契约（同进程、同输入、真实 generate_all_llm）。

为什么需要文件级契约测试：缓存是否生效过去只能靠用户手动跑两份报告看日志，
定位成本极高且结论依赖现场。这里把「同输入第二份必须全命中」变成可自动验证的
事实，同时用反例锁住「不得为了命中而忽略真实数据变化」。

覆盖三条契约：
1. 同输入连续两份 → 第二份**预检层**即命中四个基础模块（不只是 worker 层命中）；
2. 数据质量失败事件的条数/累计次数变化（重试轮次、跨会话累计）→ 仍然命中；
3. 行情变化 → 对应模块必须未命中（不为命中而忽略真实变化）。
"""

from __future__ import annotations

import logging

import pytest

from src.test.unit.llm._cache_fixtures import degradation_events, make_inputs, run_generate_all_llm

# `unit_core` 横切标记：缓存命中契约属核心基础设施行为，需随 P0 `dev-verify` 跑
# （该档选择面不含 `unit_llm`，只标 llm 域会让这批回归只在 P1 才执行）。
pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_llm,
    pytest.mark.unit_core,
    pytest.mark.usefixtures("offline_external_sources"),
]


def _run(inputs, degradation=None):
    return run_generate_all_llm(inputs, degradation=degradation)


def _precheck_summary_lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if "[LLM 预检]" in r.getMessage()]


class TestConsecutiveReportCache:
    def test_second_report_precheck_hits_all_four_modules(self, llm_cache_dir, caplog):
        """同输入的第二份报告：**预检层**就要命中四模块，而不是靠 worker 再查一次。

        只断言返回的 cached 标志不够——预检键拼错时 worker 仍能命中并返回 True，
        表面上「缓存正常」，实际上预检优化与命中统计全部失效（历史缺陷即如此）。
        """
        inputs = make_inputs()
        events = degradation_events("industry")

        with caplog.at_level(logging.INFO, logger="invest"):
            first = _run(inputs, events)
            assert not any(first), "首份报告不应命中（无缓存）"
            second = _run(inputs, events)

        assert all(second), f"第二份报告应全部命中，实际 {second}"
        assert any("基础模块命中 4/4" in line for line in _precheck_summary_lines(caplog))

    def test_failure_multiplicity_drift_does_not_break_hit(self, llm_cache_dir):
        """失败事件**条数**与累计次数变化不得影响命中。

        回归：数据质量文本曾按事件条数渲染「连接失败: x(2次)」、按跨会话累计渲染
        「累计N次」——两者每轮随重试轮次/历史累计变化，使 health_check 与
        expert_review 的缓存键持续翻新。修复后按源去重、不输出次数。
        """
        inputs = make_inputs()
        _run(inputs, degradation_events("industry", times=1, count=3))
        flags = _run(inputs, degradation_events("industry", times=3, count=9))
        assert all(flags), f"仅失败条数/累计次数变化时第二份应全部命中，实际 {flags}"

    def test_market_change_misses_macro(self, llm_cache_dir):
        """行情变化必须使对应模块未命中——命中不得以忽略真实数据变化为代价。"""
        inputs = make_inputs()
        _run(inputs)
        changed = dict(inputs)
        changed["a_indices"] = {"sh000300": {"name": "沪深300", "close": 4100.0, "change_pct": 3.0}}
        flags = _run(changed)
        assert flags[0] is False, "指数变化时 global_macro 必须重算"
