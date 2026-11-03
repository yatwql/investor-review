"""新闻关联模块的「用量台账 ↔ 模块状态」一致性（回归：汇总 0 调用却显示成功）。

现场：一次 full 运行里 4 个基础模块全失败、新闻关联批量调用也逐条失败（0 条分析、
0 token），但《LLM API 用量》页签汇总写「调用次数 0 次」，模块明细却把新闻关联标成
「成功」——因为批量路径无条件写了模块用量记录，状态列凭「有记录」判成功。

锁定三条：
① 零产出 + 零用量 → 不写 per_module（明细不会再有「成功」假象）；
② 全缓存命中（有产出、无用量）→ 仍写 per_module 并标 cached，明细显示「缓存」；
③ 批量路径无产出时落失败原因，真有产出/缓存时才清除。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.llm.failure_reasons import LLM_MODULE_FAILURE
from src.python.llm.generators_news import _finalize_news_token_usage
from src.python.llm.session import _session_usage, reset_session_usage

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]


@pytest.fixture(autouse=True)
def _clean_state():
    reset_session_usage()
    LLM_MODULE_FAILURE.clear()
    yield
    reset_session_usage()
    LLM_MODULE_FAILURE.clear()


_LLM_CONFIG = {"_provider_list": [{"name": "claude-main"}], "model": "claude-sonnet-5"}


def _finalize(usage: dict, analysis_count: int, all_cached: bool = False) -> dict:
    return _finalize_news_token_usage(
        usage,
        _LLM_CONFIG,
        "claude-sonnet-5",
        top_news=[{"title": "t"}] * 3,
        cached_count=0,
        news_data=[{"title": "t"}] * 3,
        analysis_count=analysis_count,
        all_cached=all_cached,
    )


def test_zero_output_zero_usage_records_no_module_row():
    """零产出 + 零用量（逐条调用均失败）→ 不写模块记录，明细不会显示「成功」。"""
    _finalize({}, analysis_count=0)

    assert "news_correlation" not in _session_usage["per_module"], (
        "无产出时写 per_module 会让用量页签凭「有记录」显示成功，与汇总调用次数 0 矛盾"
    )
    assert _session_usage["call_count"] == 0


def test_all_cached_output_still_records_module_row():
    """全缓存命中：有产出、无新增用量 → 仍写模块记录并标 cached（明细显示「缓存」）。"""
    _finalize({}, analysis_count=5, all_cached=True)

    row = _session_usage["per_module"].get("news_correlation")
    assert row is not None, "有产出（缓存命中）时必须留记录，否则明细看不到该模块"
    assert row["cached"] is True
    assert row["input_tokens"] == 0 and row["output_tokens"] == 0


def test_real_usage_records_tokens_and_cost():
    """真实调用：用量与费用按批记入模块行（汇总与明细同源）。"""
    _finalize({"input": 1200, "output": 300, "cache_hit": 200}, analysis_count=5)

    row = _session_usage["per_module"]["news_correlation"]
    assert row["input_tokens"] == 1200
    assert row["output_tokens"] == 300
    assert row["cache_hit_tokens"] == 200
    assert row["cached"] is False


def test_no_output_marks_failure_reason():
    """批量路径无产出（不抛异常）→ 落失败原因，明细状态显示真实原因而非「成功」。"""
    from src.python.llm._llm_news_correlation import run_news_correlation_safe

    with (
        patch(
            "src.python.llm._llm_news_correlation.get_llm_config",
            return_value={"enabled_llm": {"news_correlation": True}},
        ),
        patch("src.python.llm.generators_news.enhance_news_correlation", return_value=([{"t": 1}], False, {})),
    ):
        run_news_correlation_safe([{"title": "t"}], [])

    assert "news_correlation" in LLM_MODULE_FAILURE, "无产出必须留失败原因（否则显示成功）"


def test_output_clears_previous_failure_reason():
    """真有产出 → 清除既有失败原因（避免上一轮失败痕迹污染本轮状态）。"""
    from src.python.llm._llm_news_correlation import run_news_correlation_safe

    LLM_MODULE_FAILURE["news_correlation"] = "circuit_open"
    with (
        patch(
            "src.python.llm._llm_news_correlation.get_llm_config",
            return_value={"enabled_llm": {"news_correlation": True}},
        ),
        patch(
            "src.python.llm.generators_news.enhance_news_correlation",
            return_value=([{"t": 1}], False, {"input_tokens": 10, "output_tokens": 5}),
        ),
    ):
        run_news_correlation_safe([{"title": "t"}], [])

    assert "news_correlation" not in LLM_MODULE_FAILURE
