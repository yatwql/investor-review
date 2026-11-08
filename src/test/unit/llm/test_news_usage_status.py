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


# ── 批次级成败回传（回归：全批失败与全缓存命中同形，被记成成功）──


def _run_batch_mode_with(returned):
    """用固定返回值跑一轮批量骨架，返回 (usage, ok_batches, failed_batches)。"""
    from src.python.llm import _batch_mode

    items = [{"id": i} for i in range(3)]
    with patch.object(_batch_mode, "call_llm", return_value=returned):
        _map, _cached, usage, _cnt = _batch_mode.run_batch_mode(
            {"cache_enabled_news_correlation": False},
            "news_correlation",
            batch_preparer=lambda: (items, "fp"),
            per_item_cache_fn=None,
            batch_prompt_fn=lambda batch, _fp: "prompt",
            response_parser=lambda batch, result: [{"t": 1} for _ in batch],
        )
    return usage


def test_batch_mode_reports_zero_ok_when_all_batches_fail():
    """全部批次无产出 → ok_batches=0、failed_batches=批数（不得用零用量冒充成功）。"""
    usage = _run_batch_mode_with((None, None, None))

    assert usage["ok_batches"] == 0
    assert usage["failed_batches"] == usage["total_batches"] >= 1


def test_batch_mode_reports_ok_batches_when_produced():
    """有产出 → ok_batches 计数上挑，failed_batches 为 0（正向上屏依据）。"""
    usage = _run_batch_mode_with(("响应正文", {"input_tokens": 10, "output_tokens": 5}, {}))

    assert usage["ok_batches"] >= 1
    assert usage["failed_batches"] == 0


def test_finalize_marks_all_batches_failed_as_no_production():
    """批次全失败时即使回到零用量，也不得落模块用量行（明细不得显示成功）。"""
    token_usage = _finalize(
        {"input": 0, "output": 0, "cache_hit": 0, "ok_batches": 0, "failed_batches": 3, "total_batches": 3},
        analysis_count=0,
    )

    assert token_usage == {}
    assert "news_correlation" not in _session_usage["per_module"]


# ── 批量用量行与逐模块费用口径（回归：用量行恒 0 token、模块费用丢精度）──


def test_batch_usage_line_reports_real_tokens(caplog):
    """批量用量行须按 usage 形状归一。

    旧实现把 provider 条目名（如 deepseek-main）当协议名传进 ``_log_token_usage``，
    落到 openai 分支读 ``prompt_tokens``（claude 形 usage 无此键）→ 行恒为
    「输入 0 + 输出 0 = 0 tokens」，与真实计费自相矛盾。
    """
    import logging

    with caplog.at_level(logging.INFO, logger="invest"):
        _finalize({"input": 1200, "output": 300, "cache_hit": 200}, analysis_count=5)

    line = next(r.getMessage() for r in caplog.records if "（批处理）" in r.getMessage())
    assert "输入 1,200" in line, f"用量行须显示真实输入量（含缓存命中口径）: {line}"
    assert "输出 300" in line, f"用量行须显示真实输出量: {line}"
    assert "缓存命中 200" in line, f"用量行须显示真实缓存命中量: {line}"


@pytest.mark.usefixtures("offline_external_sources")
def test_module_cost_uses_numeric_precision():
    """逐模块费用取数值口径，不得回读 3 位小数的展示串。

    旧实现把 ``estimate_cost`` 的格式化串（>=0.01 时只到 3 位小数）解析回 float，
    0.064563 被记成 0.065，逐模块合计与页签总计不等。
    """
    from src.python.llm.pricing import compute_cost_value

    _finalize_news_token_usage(
        {"input": 6907, "output": 14508, "cache_hit": 384},
        {"_provider_list": [{"name": "deepseek-main"}]},
        "deepseek-v4-flash",
        top_news=[{"title": "t"}] * 3,
        cached_count=0,
        news_data=[{"title": "t"}] * 3,
        analysis_count=5,
    )

    expected = compute_cost_value("deepseek-v4-flash", 6907, 14508, cache_hit_input_tokens=384)
    assert expected is not None
    recorded = sum(_session_usage["per_module"]["news_correlation"]["costs"].values())
    assert recorded == pytest.approx(expected, abs=1e-12), "逐模块费用须与数值口径一致（不得经展示串回归）"
    assert recorded != pytest.approx(round(expected, 3), abs=1e-12), "展示串回读会把费用截到 3 位小数"


def test_batch_module_duration_recorded_from_skeleton():
    """批量模块的耗时必须落账（此前恒为 0.0，用量页签无法归因该模块）。"""
    _finalize(
        {"input": 1200, "output": 300, "cache_hit": 0, "duration": 3.25},
        analysis_count=2,
    )

    assert _session_usage["per_module"]["news_correlation"]["duration"] == pytest.approx(3.25, abs=1e-9)


def test_batch_mode_reports_elapsed_duration():
    """批量骨架须回传本段墙钟（扣排队），0 只应出现在「全缓存、无真实调用」时。"""
    from src.python.llm import _batch_mode

    with patch.object(_batch_mode, "_execute_and_merge_batch", side_effect=_slow_batch):
        usage = _run_batch_mode_with((None, None, None))

    assert usage["duration"] > 0.0, f"有真实批次时必须回传耗时，实际 {usage['duration']}"


def _slow_batch(*_args, **_kwargs):
    import time as _time

    _time.sleep(0.02)
    return (10, 5, 0, 1)
