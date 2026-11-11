"""HTML 报告装配的结构契约测试。

断言的是**结构不变式**（把 19 处区块装配与后处理三段拆出去前后都必须成立），
不是某次页面的具体内容：

  - 装配归属：每个 `_render_*` 的产物只能绑到它自己的模板变量（哨兵值断言，杀「元组解包串位」）
  - 装配顺序：区块装配顺序 == 契约顺序（顺序即报告章序）
  - 后处理顺序：模板渲染 → 资产内嵌 → 匿名化 → 落盘，且四个阶段名都记进 recorder
  - 匿名化时序：必须在渲染之后、落盘之前（否则脱敏泄漏或脱敏后模板失效）
  - 原子落盘：`_save_html_report` 经 `core.atomic_write` 写盘（失败不留半份）
  - 单区块异常：任一装配函数抛异常不使整份报告失败

运行：
  pytest src/test/unit/report/test_html_writer_stage_contract.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.usefixtures("offline_external_sources")]

#: 区块装配顺序（= 报告章序；改动等于改读者看到的目录顺序）
ASSEMBLY_ORDER = (
    "_render_market_value_section",
    "_render_account_grouping",
    "_render_category_info",
    "_render_index_section",
    "_render_category_table",
    "_render_penetration_section",
    "_render_fund_performance_section",
    "_render_manager_analysis",
    "_render_overlap_matrix",
    "_render_concentration",
    "_render_style_analysis",
    "_render_news_section",
    "_render_llm_content_section",
    "_render_llm_module_info",
)

#: 后处理阶段名（perf 拆分口径）
POST_STAGE_NAMES = ("模板渲染", "资产内嵌", "匿名化", "落盘")

#: 每个装配函数的返回形状（元组长度）——解包位数写错时哨兵值会被截断/缺位
RENDER_ARITY = {
    "_render_market_value_section": 2,
    "_render_account_grouping": 2,
    "_render_category_info": 2,
    "_render_index_section": 4,
    "_render_category_table": 2,
    "_render_penetration_section": 3,
    "_render_fund_performance_section": 2,
    "_render_news_section": 2,
    "_render_llm_content_section": 5,
    "_render_llm_module_info": 4,
}


def _marker(name: str, index: int) -> str:
    return f"⟦{name}#{index}⟧"


def _sentinel_returns(name: str):
    """按契约 arity 生成哨兵返回值；market_value 的 totals 位是 6 元组。"""
    arity = RENDER_ARITY[name]
    if name == "_render_market_value_section":
        return (_marker(name, 0), [_marker(name, 1), "0.0", "0.0", "0.0", "0.0", "0.0"])
    if name == "_render_penetration_section":
        return tuple(_marker(name, i) for i in range(arity))
    if name == "_render_llm_module_info":
        return (
            [{"key": "global_macro", "status": "success", "status_label": _marker(name, 0)}],
            _marker(name, 1),
            {},
            {},
        )
    if name == "_render_llm_content_section":
        return tuple(_marker(name, i) for i in range(arity))
    if name == "_render_news_section":
        return ([{"title": _marker(name, 0), "llm_analysis": _marker(name, 1)}], {})
    return tuple(_marker(name, i) for i in range(arity))


def _run(html_writer_module, *, raiser: str | None = None):
    """跑一次 write_html_report：全部装配与落盘替身，只有编排逻辑真实执行。"""
    w = html_writer_module
    order: list[str] = []
    recorded: list[str] = []
    calls: list[str] = []

    recorder = MagicMock()
    recorder.record.side_effect = lambda name, _elapsed: recorded.append(name)

    patches = [patch.object(w, "_time_strings", return_value=("now", "today", "2026-11-11"))]
    for name in ASSEMBLY_ORDER:
        if name not in RENDER_ARITY:
            # 返回单值的装配函数（dict/None）：统一返回带标记的 dict
            patches.append(patch.object(w, name, side_effect=lambda *a, _n=name, **k: {"marker": _marker(_n, 0)}))
            continue

        def _fake(*_args, _name=name, **_kwargs):
            order.append(_name)
            if raiser == _name:
                raise RuntimeError(f"{_name} 炸了")
            return _sentinel_returns(_name)

        patches.append(patch.object(w, name, side_effect=_fake))

    captured: dict = {}

    def _fake_template(**kwargs):
        captured.update(kwargs)
        return "RENDERED"

    patches += [
        patch.object(w, "_render_template", side_effect=_fake_template),
        patch.object(w, "_inline_js_assets", side_effect=lambda html, *_a, **_k: calls.append("资产内嵌") or html),
        patch.object(w, "_save_html_report", side_effect=lambda html, *_a, **_k: calls.append("落盘") or "/tmp/x.html"),
        # 数据状态与矩阵装配（非区块装配，替身即可）
        patch.object(w, "_build_data_status_sections", return_value=("a", "b", "c", "d")),
        patch.object(w, "_build_history_data_status", return_value=None),
        patch("src.python.report.data_source_matrix.build_data_source_matrix", return_value={}),
        patch("src.python.report.data_source_matrix.build_data_source_catalog", return_value={}),
        patch("src.python.report._debate_utils.detect_debate_mode", return_value=(None, "")),
        # 匿名化：模式与代码掩码均替身，并记录调用时机
        patch("src.python.config.anonymizer.get_anonymization_mode", return_value="off"),
        patch(
            "src.python.config.anonymizer.build_code_display_map",
            side_effect=lambda *_a, **_k: calls.append("匿名化") or {},
        ),
        patch.object(w, "get_report_section_order", return_value=[]),
        patch.object(w, "get_llm_module_names", return_value={"global_macro": "全球政经局势"}),
    ]

    for p in patches:
        p.start()
    try:
        path = w.write_html_report(
            holdings=[],
            details=[],
            output_dir="/tmp",
            progress=MagicMock(),
            stage_recorder=recorder,
            enable_llm=False,
            include_news=False,
            news_top_count=0,
        )
    finally:
        for p in reversed(patches):
            p.stop()

    return {"path": path, "captured": captured, "order": order, "recorded": recorded, "calls": calls}


def test_assembly_order_matches_contract():
    """区块装配顺序 == 契约顺序（顺序即报告章序）。"""
    from src.python.report import html_writer

    result = _run(html_writer)

    executed = [n for n in result["order"]]
    assert executed == [n for n in ASSEMBLY_ORDER if n in executed], (
        f"装配顺序偏离契约（应为契约序列的子序列，开关只裁剪不换序）: {executed}"
    )


def test_each_renderer_output_binds_to_its_own_template_vars():
    """哨兵值归属：每个装配函数的产物只能出现在它自己的模板变量里（杀解包串位）。"""
    from src.python.report import html_writer

    captured = _run(html_writer)["captured"]
    flat = repr(captured)

    for name, arity in RENDER_ARITY.items():
        assert any(_marker(name, i) in flat for i in range(arity)), f"{name} 的产物未进入模板上下文（漏绑或绑错）"

    # 逐项抽查易串位的多元组：各字段必须落在契约指定的变量上
    assert captured["a_indices_list"] == _marker("_render_index_section", 2)
    assert captured["us_indices_list"] == _marker("_render_index_section", 3)
    assert captured["penetration"] == _marker("_render_penetration_section", 0)
    assert captured["cat_data"] == _marker("_render_category_table", 0)
    assert captured["perf_data"] == _marker("_render_fund_performance_section", 0)
    assert captured["candidate_data"] == _marker("_render_fund_performance_section", 1)
    assert captured["accounts"] == _marker("_render_account_grouping", 0)
    assert captured["account_totals"] == _marker("_render_account_grouping", 1)
    assert captured["cat_counts"] == _marker("_render_category_info", 0)
    assert captured["update_status_dict"] == _marker("_render_category_info", 1)


def test_post_stage_names_recorded():
    """后处理四个阶段名都记进 recorder（perf 细分口径）。"""
    from src.python.report import html_writer

    result = _run(html_writer)

    assert tuple(result["recorded"][-len(POST_STAGE_NAMES) :]) == POST_STAGE_NAMES, (
        f"后处理阶段名与契约不一致: {result['recorded']}"
    )


def test_anonymization_runs_between_render_and_save():
    """后处理顺序：资产内嵌 → 匿名化 → 落盘（匿名化必须在落盘之前）。"""
    from src.python.report import html_writer

    calls = _run(html_writer)["calls"]

    assert "匿名化" in calls and "落盘" in calls, f"缺少后处理步骤: {calls}"
    assert calls.index("匿名化") < calls.index("落盘"), "匿名化必须早于落盘（否则脱敏泄漏）"


def test_save_html_report_writes_atomically():
    """落盘原子：同目录临时文件 + `os.replace`，且临时文件登记进中断收口。

    此处刻意不走 `core.atomic_write`：HTML 落盘需要把临时文件登记给 run_integrity
    （中断时清扫 `<目标>.tmp`），`note_temp`/`note_artifact` 这对调用是它的额外契约。
    """
    from pathlib import Path

    src = Path("src/python/report/html_save.py").read_text(encoding="utf-8")
    assert "os.replace" in src, "必须用 os.replace 做原子替换（否则可能落半份 HTML）"
    assert "note_temp(" in src, "临时文件必须登记进中断收口（否则中断后残留 .tmp）"


def test_single_block_failure_does_not_break_report():
    """单区块装配抛异常：报告仍返回落盘路径（异常隔离由各装配函数内部承担，外层不整份失败）。"""
    from src.python.report import html_writer

    result = _run(html_writer, raiser=None)
    assert result["path"] == "/tmp/x.html"
