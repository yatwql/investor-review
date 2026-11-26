"""LLM 侧残余守卫/诊断分支：逐行收口用例。

覆盖目标（每例对应一条真实可达路径，不是「跑到该行」）：
  - `_apply_llm_news_correlation`：``` 围栏内**直接**以 ``[`` / ``{`` 起始的 JSON 块
    （LLM 常在代码围栏里裸放数组，不带 ``json`` 语言标注）
  - `enhance_news_correlation`：部分批次失败时的「部分失败 N/M」告警
  - `_valuation_signal`：估值数据可用但档位全部落在已知三档之外 → 无信号行
  - `_self_review_penetration_digest`：穿透列表混入非 dict 元素 → 跳过该行
  - `_log_dispatch_tail`：预算跳过清单非空 → 告警回显模块中文名
  - `_filter_hallucinated_codes`：原空行（段落分隔）原样保留
  - `save_baseline`：快照写盘异常 → 返回 False（只影响归因，不影响生成）
  - `extract_stable_categories`：非 dict 元素按属性取 code/name
  - `extract_stable_penetration`：``full`` 与 ``include_sector`` 同时为真 → ValueError
  - `fingerprint_components` / `expert_review_fingerprint`：决策台账启用时纳入教训后缀
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from src.python.llm import fingerprint_baseline
from src.python.llm._hallucination_filter import _filter_hallucinated_codes
from src.python.llm._llm_dispatch import _log_dispatch_tail
from src.python.llm.fingerprint import extract_stable_categories, extract_stable_penetration
from src.python.llm.generators_news import _apply_llm_news_correlation, enhance_news_correlation
from src.python.llm.prompts_review import _self_review_penetration_digest
from src.python.llm.prompts_signals import _valuation_signal

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]

_BATCH = [{"title": f"新闻{i}", "matched_keywords": ["茅台"]} for i in range(3)]


# ── 新闻关联解析 / 失败汇总 ───────────────────────────────────


def test_fenced_array_without_json_language_tag_is_parsed():
    """围栏块以 ``[`` 起始（无 ``json`` 标注）→ 取该块解析，而非整串解析失败。

    LLM 常见产出形态：`` ```\\n[{"idx": 0, ...}]\\n``` ``。整串 json.loads 必失败，
    若不剥围栏，本批会被误判为「响应不可解析」而整批作废。
    """
    response = '```\n[{"idx": 0, "relevance": "高", "sentiment": "利好", "analysis": "原因0"}]\n```'

    result = _apply_llm_news_correlation(_BATCH, response)

    assert result is not None, "围栏内的裸数组须被剥出来解析"
    assert result[0] == ("高", "利好", "原因0")


def test_fenced_object_block_is_extracted_before_parse():
    """围栏块以 ``{`` 起始 → 同样先剥围栏（非数组随后按格式异常收口）。"""
    assert _apply_llm_news_correlation(_BATCH, '```\n{"error": "wrong"}\n```') is None


def test_partial_batch_failure_warns_with_ratio(monkeypatch, caplog):
    """有成功批次也有失败批次 → 告警「部分批次失败 failed/total」并给出缺分析条数。"""

    def _fake_dispatch(_cfg, _module_key, **_kwargs):
        return (
            {0: ("高", "利好", "原因0")},
            False,
            {"input": 100, "output": 20, "ok_batches": 1, "failed_batches": 1, "duration": 1.0},
            0,
        )

    monkeypatch.setattr("src.python.llm.generators_news.generate_llm_module", _fake_dispatch)

    with caplog.at_level(logging.WARNING):
        enriched, _cached, _usage = enhance_news_correlation([dict(item) for item in _BATCH], [])

    assert enriched[0]["llm_analysis"] == "[高][利好] 原因0", "成功批次的分析须合并回原新闻"
    assert any("部分批次失败 1/2" in record.getMessage() for record in caplog.records), caplog.text


# ── 提示词取数守卫 ──────────────────────────────────────────


def test_valuation_signal_returns_none_when_no_known_tier():
    """估值可用但 by_code 里没有已知档位 → 不出信号行（不硬造方向）。"""
    pipeline_data = {"valuation_data": {"available": True, "by_code": {"600519": {"tier": "未知档"}}}}

    assert _valuation_signal(pipeline_data) is None


def test_penetration_digest_skips_non_dict_entries():
    """穿透列表混入非 dict 元素 → 跳过，其余照常出行（不因脏元素整段丢失）。"""
    digest = _self_review_penetration_digest([{"name": "白酒", "ratio_pct": 5.0}, "脏元素"])

    assert digest == "- 白酒 占比 5.0%"


# ── 派发收尾 ───────────────────────────────────────────────


def test_dispatch_tail_warns_skipped_modules_by_label(caplog):
    """预算跳过清单非空 → 告警回显模块**中文名**（没有映射时退回模块键）。"""
    with caplog.at_level(logging.WARNING):
        _log_dispatch_tail(["qa", "unknown_key"], {"qa": "问答模块"}, thinking_limit=1)

    message = next(record.getMessage() for record in caplog.records if "总时间预算跳过" in record.getMessage())
    assert "问答模块" in message
    assert "unknown_key" in message


# ── 虚构代码过滤 ───────────────────────────────────────────


def test_hallucinated_filter_preserves_blank_separator_lines():
    """整行为空（段落分隔）→ 原样保留；含虚构代码的行照旧整行丢弃。"""
    text = "开头段落\n\n提到 XYZWQ 的虚构品种"

    result = _filter_hallucinated_codes(text, valid_codes=set())

    assert result == "开头段落\n", "空行须作为段落分隔保留，虚构品种所在行丢弃"


# ── 指纹基线 / 分类与穿透提取 ──────────────────────────────


def test_save_baseline_returns_false_when_write_raises(monkeypatch):
    """快照写盘异常 → False（诊断输入写不进去不影响本轮生成）。"""

    def _boom(*_args, **_kwargs):
        raise OSError("磁盘满")

    monkeypatch.setattr(fingerprint_baseline, "write_json_atomic", _boom)

    assert fingerprint_baseline.save_baseline({"holdings": "h1"}, {"expert_review": "k1"}) is False


def test_stable_categories_reads_attributes_from_non_dict_items():
    """分类品种为对象（非 dict）时按 ``code``/``name`` 属性取值。"""
    result = extract_stable_categories({"股票": [SimpleNamespace(code="600519", name="示例")]})

    assert result == {"股票": [("600519", "示例")]}


def test_stable_penetration_rejects_full_with_sector():
    """``full`` 与 ``include_sector`` 互斥（诊断口径 vs 入键口径）→ ValueError。"""
    with pytest.raises(ValueError, match="互斥"):
        extract_stable_penetration([], full=True, include_sector=True)


def test_fingerprint_components_include_ledger_lessons_when_active(monkeypatch):
    """决策台账启用 → 组件级诊断纳入「决策教训」块（关闭时该块不含它）。"""
    from src.python.llm.module_fingerprint import ModuleFingerprintInputs, fingerprint_components

    def _active(flag: bool) -> None:
        monkeypatch.setattr("src.python.core.decision_ledger.is_active", lambda: flag)

    _active(False)
    inactive = fingerprint_components(ModuleFingerprintInputs(categories={}))["ledger_blocks"]

    _active(True)
    monkeypatch.setattr("src.python.core.decision_ledger.lessons_cache_suffix", lambda: "_LEDGER")

    assert fingerprint_components(ModuleFingerprintInputs(categories={}))["ledger_blocks"] != inactive, (
        "台账启用后教训块须进入组件哈希（否则排障时看不到它变没变）"
    )


def test_expert_review_fingerprint_tracks_ledger_lessons(monkeypatch):
    """决策台账启用 → 专家复盘指纹叠加教训后缀（关闭时与未启用一致）。"""
    from src.python.llm import module_fingerprint

    inputs = module_fingerprint.ModuleFingerprintInputs(
        categories={"股票": [{"code": "600519", "name": "示例"}]},
    )
    monkeypatch.setattr("src.python.core.decision_ledger.is_active", lambda: False)
    baseline = module_fingerprint.expert_review_fingerprint(inputs)

    monkeypatch.setattr("src.python.core.decision_ledger.is_active", lambda: True)
    monkeypatch.setattr("src.python.core.decision_ledger.lessons_cache_suffix", lambda: "_LESSONS")

    assert module_fingerprint.expert_review_fingerprint(inputs) != baseline
