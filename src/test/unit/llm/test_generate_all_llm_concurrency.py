"""generate_all_llm 并发治理与派发测试（thinking 并发上限 / 等待量化 / 模块跨度 / 新闻不并入编排）。

从 `test_generate_all_llm.py` 分出（按被测职责分片）：本文件覆盖并发与调度面，
编排主路径与缓存预检留在主分片。
"""

from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import pytest


pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]


class TestThinkingConcurrencyLimit(unittest.TestCase):
    """_dispatch_llm_workers — thinking 模块并发信号量限制。

    health_check / expert_review 等开启 Extended Thinking 的模块并发涌向
    DeepSeek 时偶发返回空 content（HTTP 200 + 空响应），整章降级占位。
    约束：thinking 请求（thinking_enabled_{label}=true）受 BoundedSemaphore
    限制，同时最多 llm_max_thinking_concurrency 个（默认 2）；非 thinking
    模块不受限。
    """

    def test_thinking_modules_serialized_under_limit(self) -> None:
        """两个 thinking 模块 → 信号量串行（时间不重叠）；非 thinking 不受限并发。"""
        from src.python.llm.generators_orchestrator import _dispatch_llm_workers

        _lock = threading.Lock()
        _tracking = {"active": 0, "max_active": 0, "thinking_enter": []}

        def _make_tracked_fn(name: str, is_thinking: bool):
            def _fn(_client, _cfg):
                with _lock:
                    _tracking["active"] += 1
                    _tracking["max_active"] = max(_tracking["max_active"], _tracking["active"])
                    if is_thinking:
                        _tracking["thinking_enter"].append(time.monotonic())
                time.sleep(0.05)
                with _lock:
                    _tracking["active"] -= 1
                return f"<p>{name}</p>", False

            return _fn

        fns = {
            "health_check": _make_tracked_fn("health", True),
            "expert_review": _make_tracked_fn("expert", True),
            "global_macro": _make_tracked_fn("macro", False),
        }
        needs = {"health_check": True, "expert_review": True, "global_macro": True}
        llm_config = {
            "llm_max_concurrency": 3,
            "llm_max_thinking_concurrency": 1,
            "thinking_enabled_health_check": True,
            "thinking_enabled_expert_review": True,
            "thinking_enabled_global_macro": False,
        }

        with (
            patch("src.python.llm._llm_dispatch._build_module_fns", return_value=fns),
            patch("src.python.llm.generators_orchestrator._build_competitive_context_block", return_value=""),
            patch("src.python.llm._llm_dispatch.make_http_client", return_value=MagicMock()),
        ):
            result = _dispatch_llm_workers(needs, llm_config, False, {}, {}, 0, 0, 0, 0, 0, {}, None, None, None)

        # 三个模块全部完成
        self.assertEqual(len(result), 3)
        # thinking 两个模块进入时间不重叠（信号量串行，间隔 ≥ sleep 时长）
        self.assertEqual(len(_tracking["thinking_enter"]), 2)
        gap = abs(_tracking["thinking_enter"][0] - _tracking["thinking_enter"][1])
        self.assertGreaterEqual(gap, 0.04, "thinking 模块应串行执行（并发限制未生效）")
        # 总并发不超 llm_max_concurrency
        self.assertLessEqual(_tracking["max_active"], 3)

    def test_thinking_wait_over_threshold_logged(self) -> None:
        """thinking 槽等待超阈值必须留下日志线索。

        判定口径：`llm_max_thinking_concurrency=1` 时第二个 thinking 模块的等待时间
        等于第一个的执行时长（实测两个模块 51s / 37s 完全串行），若等待静默，日志里
        只有时间轴能看出「被信号量排队」与「端点慢」的区别。
        """
        from src.python.llm.generators_orchestrator import _dispatch_llm_workers

        def _slow_fn(_client, _cfg):
            time.sleep(0.06)
            return "<p>x</p>", False

        fns = {"health_check": _slow_fn, "expert_review": _slow_fn}
        needs = {"health_check": True, "expert_review": True}
        llm_config = {
            "llm_max_concurrency": 2,
            "llm_max_thinking_concurrency": 1,
            "thinking_enabled_health_check": True,
            "thinking_enabled_expert_review": True,
        }

        with (
            patch("src.python.llm._llm_dispatch._build_module_fns", return_value=fns),
            patch("src.python.llm.generators_orchestrator._build_competitive_context_block", return_value=""),
            patch("src.python.llm._llm_dispatch.make_http_client", return_value=MagicMock()),
            patch("src.python.llm._llm_dispatch._THINKING_WAIT_LOG_SECONDS", 0.02),
            self.assertLogs("invest", level="INFO") as logs,
        ):
            _dispatch_llm_workers(needs, llm_config, False, {}, {}, 0, 0, 0, 0, 0, {}, None, None, None)

        wait_lines = [line for line in logs.output if "等待 thinking 并发槽" in line]
        self.assertEqual(len(wait_lines), 1, f"应恰有一条等待日志（实际 {logs.output}）")
        self.assertIn("上限 1", wait_lines[0])


class TestThinkingWaitQuantified(unittest.TestCase):
    """thinking 串行等待要能跨期量化（本轮累计 + 可执行提示）。

    判定口径：两个 thinking 模块在上限 1 下串行时，等待总量≈较短那段时长；
    该数字进 perf counters（`llm_thinking_wait_ms`）并给出「提到 2 约可省该时长」提示，
    否则「默认值该不该改」只能靠翻时间轴猜。
    """

    def _run(self, sleep_s: float, hint_threshold: float):
        from src.python.llm import _llm_dispatch as disp
        from src.python.llm.generators_orchestrator import _dispatch_llm_workers

        def _slow_fn(_client, _cfg):
            time.sleep(sleep_s)
            return "<p>x</p>", False

        fns = {"health_check": _slow_fn, "expert_review": _slow_fn}
        needs = {"health_check": True, "expert_review": True}
        llm_config = {
            "llm_max_concurrency": 2,
            "llm_max_thinking_concurrency": 1,
            "thinking_enabled_health_check": True,
            "thinking_enabled_expert_review": True,
        }
        disp.reset_thinking_wait_total()
        with (
            patch("src.python.llm._llm_dispatch._build_module_fns", return_value=fns),
            patch("src.python.llm.generators_orchestrator._build_competitive_context_block", return_value=""),
            patch("src.python.llm._llm_dispatch.make_http_client", return_value=MagicMock()),
            patch("src.python.llm._llm_dispatch._THINKING_WAIT_HINT_SECONDS", hint_threshold),
            self.assertLogs("invest", level="INFO") as logs,
        ):
            _dispatch_llm_workers(needs, llm_config, False, {}, {}, 0, 0, 0, 0, 0, {}, None, None, None)
        return disp.thinking_wait_total_seconds(), logs.output

    def test_wait_total_accumulated_and_hint_logged(self):
        total, output = self._run(0.06, 0.02)
        self.assertGreater(total, 0.0, "串行等待必须被累计（否则无法跨期量化）")
        hints = [line for line in output if "串行等待合计" in line]
        self.assertEqual(len(hints), 1, f"应恰有一条量化提示（实际 {output}）")
        self.assertIn("提到 2", hints[0])

    def test_no_hint_when_wait_below_threshold(self):
        """等待很小时不打扰（阈值内属正常抖动）。"""
        _total, output = self._run(0.02, 999.0)
        self.assertFalse([line for line in output if "串行等待合计" in line])


class TestDispatchModuleSpans(unittest.TestCase):
    """逐模块耗时记录：模块自身耗时入 recorder，None 时零行为变化。"""

    def _run_dispatch(self, span_recorder):
        from src.python.llm.generators_orchestrator import _dispatch_llm_workers

        keys = ("health_check", "expert_review", "global_macro", "penetration_deep")
        fns = {key: (lambda _c, _lc, _k=key: (f"<p>{_k}</p>", False)) for key in keys}
        needs = dict.fromkeys(keys, True)
        with (
            patch("src.python.llm._llm_dispatch._build_module_fns", return_value=fns),
            patch("src.python.llm.generators_orchestrator._build_competitive_context_block", return_value=""),
            patch("src.python.llm._llm_dispatch.make_http_client", return_value=MagicMock()),
        ):
            return _dispatch_llm_workers(
                needs, {}, False, {}, {}, 0, 0, 0, 0, 0, {}, None, None, None, span_recorder=span_recorder
            )

    def test_each_module_recorded_under_semantic_label(self) -> None:
        """四个模块各记一条子项，键为语义模块名（非模块 key）。"""
        from src.python.core.perf import PhaseBreakdownRecorder
        from src.python.core.registry import get_llm_module_name

        recorder = PhaseBreakdownRecorder("LLM+新闻")
        self._run_dispatch(recorder)
        spans = recorder.spans()
        expected = {
            get_llm_module_name(k) for k in ("health_check", "expert_review", "global_macro", "penetration_deep")
        }
        self.assertEqual(set(spans), expected)
        self.assertTrue(all(sec >= 0 for sec in spans.values()))

    def test_none_recorder_keeps_dispatch_working(self) -> None:
        """recorder 为 None（旧调用方）时分发照常返回结果。"""
        result = self._run_dispatch(None)
        self.assertEqual(len(result), 4)


class TestNewsCorrelationNotOrchestrated(unittest.TestCase):
    """新闻关联不经编排层线程池（模块注册须与真实运行路径一致）。

    新闻关联的返回类型是 ``(list[dict], bool, dict)``（富化后的新闻列表），
    与其余 HTML 生成模块的 ``(str, bool)`` 不同，由 `report/news_correlation.py`
    直调 ``run_news_correlation_safe``。编排层曾另设一条「预计算 + 模块级变量
    传递」路径（闭包包装成 JSON 字符串、结果经 ``_news_correlation_result``
    传回），但该分支的入参 ``news_data`` / ``holdings_data`` 在任何调用方都
    未传入，**永不执行**——注册表里有、运行时从不跑，正是「注册须与真实运行路径
    一致」要防的注册漂移。
    """

    def test_dispatch_has_no_news_correlation_params(self) -> None:
        """分发入口不再接受新闻/持仓入参（回归：旧签名含这三个永不使用的参数）。"""
        import inspect

        from src.python.llm.generators_orchestrator import _dispatch_llm_workers

        params = set(inspect.signature(_dispatch_llm_workers).parameters)
        for dead in ("news_data", "holdings_data", "penetrated_assets_for_news"):
            self.assertNotIn(dead, params, f"编排层不应再接受 {dead}——该注册分支无调用方")

    def test_dispatch_never_returns_news_correlation(self) -> None:
        """实跑一次分发：结果键即传入的模块键，不含注入的 news_correlation。"""
        from src.python.llm.generators_orchestrator import _dispatch_llm_workers

        keys = ("health_check", "expert_review", "global_macro", "penetration_deep")
        fns = {key: (lambda _c, _lc, _k=key: (f"<p>{_k}</p>", False)) for key in keys}
        needs = dict.fromkeys(keys, True)

        with (
            patch("src.python.llm._llm_dispatch._build_module_fns", return_value=fns),
            patch("src.python.llm.generators_orchestrator._build_competitive_context_block", return_value=""),
            patch("src.python.llm._llm_dispatch.make_http_client", return_value=MagicMock()),
        ):
            result = _dispatch_llm_workers(needs, {}, False, {}, {}, 0, 0, 0, 0, 0, {}, None, None, None)

        self.assertEqual(set(result), set(keys))

    def test_precompute_result_api_removed(self) -> None:
        """不再暴露「预计算结果」读取接口（路径移除后该 API 已无来源）。"""
        import src.python.llm as llm_pkg

        self.assertFalse(
            hasattr(llm_pkg, "get_news_correlation_result"),
            "编排层预计算路径已移除，不应再暴露其结果读取接口",
        )
