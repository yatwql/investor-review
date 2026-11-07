"""新闻关联批量「响应不可解析」的收口契约。

现场：一次 full 运行 3 批中 2 批响应 JSON 不可解析，解析器按旧契约给整批填
("低", "中性", "") 占位，于是 ①批次被判成功（无「部分批次失败」告警）、
②占位写进逐条缓存（后续轮次把解析失败当命中结果复用）、③报告把 20 条占位算成
「含 LLM 分析」（[低] 空分析），连带事件窗极性缺失、91% 事件不可判。

锁定：整批不可解析 = 本批失败（解析器返回 None → 不写结果、不写缓存、不计分析条数、
计 failed_batches），LLM 部分作答仍按正常产出处理（缺失项填默认值）。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.llm.generators_news import _apply_llm_news_correlation, _merge_llm_analysis

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]

_BATCH = [{"title": f"新闻{i}", "matched_keywords": ["茅台"]} for i in range(3)]
_PARTIAL_OK = '[{"idx": 0, "relevance": "高", "sentiment": "利好", "analysis": "原因0"}]'


def test_malformed_json_is_whole_batch_failure():
    """非 JSON 响应 → None（不是「全默认值列表」）。"""
    assert _apply_llm_news_correlation(_BATCH, "不是json") is None


def test_non_list_json_is_whole_batch_failure():
    """JSON 合法但不是数组 → None。"""
    assert _apply_llm_news_correlation(_BATCH, '{"error": "wrong"}') is None


def test_partial_answer_keeps_default_fill():
    """LLM 部分作答属正常产出：命中项取分析、缺失项仍填空默认值。"""
    result = _apply_llm_news_correlation(_BATCH, _PARTIAL_OK)

    assert result is not None
    assert result[0] == ("高", "利好", "原因0")
    assert result[1:] == [("低", "中性", "")] * 2


def test_parse_failure_batch_is_failed_not_cached(monkeypatch):
    """解析失败批次：结果为空、计 failed_batches、不写逐条缓存、token 仍计费。"""
    from src.python.llm import _batch_mode

    items = [{"id": i} for i in range(3)]
    cache_writes: list[str] = []
    monkeypatch.setattr(_batch_mode, "cache_set", lambda key, value: cache_writes.append(key))

    with patch.object(
        _batch_mode,
        "call_llm",
        return_value=("坏响应", {"input_tokens": 100, "output_tokens": 20}, {}),
    ):
        results_map, _all_cached, usage, _cached_count = _batch_mode.run_batch_mode(
            {"cache_enabled_news_correlation": False},
            "news_correlation",
            batch_preparer=lambda: (items, "fp"),
            per_item_cache_fn=lambda idx, item, _fp: f"k{idx}",
            batch_prompt_fn=lambda batch, _fp: "prompt",
            response_parser=lambda batch, result: None,
        )

    assert results_map == {}, "不可解析的批次不得产出结果（占位会冒充 LLM 分析）"
    assert cache_writes == [], "占位入缓存会让后续轮次把解析失败当命中复用"
    assert usage["ok_batches"] == 0
    assert usage["failed_batches"] == usage["total_batches"] >= 1
    assert usage["input"] == 100, "响应不可解析不等于没花钱：已消耗 token 仍须计入用量"


def test_failed_batch_items_get_no_analysis_text():
    """无 LLM 结果的新闻不写 llm_analysis、不计入分析条数（报告不得凭空出现 [低]）。"""
    news = [{"title": f"新闻{i}"} for i in range(3)]

    enriched, analysis_count = _merge_llm_analysis(news, {})

    assert analysis_count == 0
    assert all("llm_analysis" not in item for item in enriched)
