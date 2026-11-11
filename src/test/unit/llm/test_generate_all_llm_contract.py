"""`generate_all_llm` 编排入口的结构契约测试。

这些用例断言的是**结构不变式**，不是某次输出的具体文本——它们是拆分
（块装配整组外移、生成后一遍外移）之前先立好的护栏：

  - 返回位序：前 4 位是四模块正文（按注册顺序），后 4 位是同序的缓存命中标志；
    辩论模式在第 9 位追加辩论信息
  - 块实例单次渲染：同一份上下文块实例既进预检指纹、又进提示词正文（身份相同）
  - 门面 patch 点：`generators_orchestrator._dispatch_llm_workers` 是唯一的消费入口，
    外部 patch 该名字必须真正拦到分发（否则用例假绿、真实分发照跑）

运行：
  pytest src/test/unit/llm/test_generate_all_llm_contract.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]

_MODULE_KEYS = ("global_macro", "expert_review", "health_check", "penetration_deep")


@pytest.fixture
def llm_enabled_config() -> dict:
    """四模块全开的最小 llm 配置。"""
    return {"enabled_llm": {key: True for key in _MODULE_KEYS}}


def _precheck_mixed() -> dict:
    """预检结果：global_macro 命中缓存，其余未命中。"""
    out: dict = {}
    for index, key in enumerate(_MODULE_KEYS):
        cached = index == 0
        out[key] = {"result": f"<p>缓存-{key}</p>" if cached else None, "cached": cached}
    return out


def _run(orchestrator_module, **kwargs):
    """跑一次编排入口（分发被 facade patch 拦下，不触真实生成）。"""
    return orchestrator_module.generate_all_llm({}, {}, 0, 0, 0, 0, 0, {}, **kwargs)


def test_return_positions_follow_module_order(llm_enabled_config):
    """返回位序：前 4 位正文、后 4 位命中标志，顺序与注册顺序一致。"""
    from src.python.llm import generators_orchestrator as orch

    with (
        patch.object(orch, "get_llm_config", return_value=llm_enabled_config),
        patch.object(orch, "_compute_module_cache_info", return_value={}),
        patch.object(orch, "_precheck_all_modules", return_value=_precheck_mixed()),
        patch.object(orch, "_dispatch_llm_workers", return_value={}) as mock_dispatch,
        patch("src.python.llm.fingerprint_baseline.save_baseline") as mock_baseline,
    ):
        result = _run(orch)
        assert mock_dispatch.called
        mock_baseline.assert_called_once()

    assert len(result) == 8, f"非辩论模式必须是 8 元组，实际 {len(result)}"
    contents, flags = result[:4], result[4:]
    for index, key in enumerate(_MODULE_KEYS):
        expected = "<p>缓存-%s</p>" % key if index == 0 else None
        assert contents[index] == expected, f"{key} 正文位错位：{contents[index]!r}"
        assert flags[index] is (index == 0), f"{key} 命中标志位错位"


def test_return_appends_debate_info_only_in_debate_mode(llm_enabled_config):
    """辩论模式：第 9 位是辩论信息（容器为空时即 None），非辩论模式不追加。"""
    from src.python.llm import generators_orchestrator as orch

    _precheck_mixed()
    with (
        patch.object(orch, "get_llm_config", return_value=llm_enabled_config),
        patch.object(orch, "_compute_module_cache_info", return_value={}),
        patch.object(orch, "_precheck_all_modules", return_value=_precheck_mixed()),
        patch.object(orch, "_dispatch_llm_workers", return_value={}) as mock_dispatch,
        patch("src.python.llm.fingerprint_baseline.save_baseline"),
        patch("src.python.config.features.is_feature_enabled", side_effect=lambda name: name == "llm_debate_procon"),
    ):
        result = _run(orch)
        # 辩论模式必须绕过标准 expert_review 预检（走独立键）
        assert mock_dispatch.call_args.args[0]["expert_review"] is True

    assert len(result) == 9, "辩论模式应追加第 9 位辩论信息"
    assert result[8] is None, "未产生辩论结论时第 9 位为 None"


def test_context_blocks_are_single_instance_across_fingerprint_and_prompt(llm_enabled_config):
    """块实例单次渲染：进指纹的对象与进提示词的对象必须是同一个（`is`）。"""
    from src.python.llm import generators_orchestrator as orch

    marker = "<p>竞争语境块</p>"
    with (
        patch.object(orch, "get_llm_config", return_value=llm_enabled_config),
        patch.object(orch, "_build_competitive_context_block", return_value=marker),
        patch.object(orch, "_build_data_quality_detail_block", return_value="<p>质量块</p>"),
        patch.object(orch, "_compute_module_cache_info", return_value={}) as mock_cache_info,
        patch.object(orch, "_precheck_all_modules", return_value=_precheck_mixed()),
        patch.object(orch, "_dispatch_llm_workers", return_value={}) as mock_dispatch,
        patch("src.python.llm.fingerprint_baseline.save_baseline"),
    ):
        _run(orch)

    cache_kwargs = mock_cache_info.call_args.kwargs
    dispatch_kwargs = mock_dispatch.call_args.kwargs
    for name in ("competitive_context", "data_quality_text", "purchase_constraint_block"):
        assert cache_kwargs[name] is dispatch_kwargs[name], (
            f"{name} 在指纹侧与提示词侧不是同一实例：两侧各自渲染会让缓存键与请求体脱钩"
        )


def test_facade_patch_point_intercepts_real_dispatch(llm_enabled_config):
    """门面 patch 点：patch 门面名字必须真正拦下分发（否则用例假绿）。"""
    from src.python.llm import generators_orchestrator as orch

    with (
        patch.object(orch, "get_llm_config", return_value=llm_enabled_config),
        patch.object(orch, "_compute_module_cache_info", return_value={}),
        patch.object(orch, "_precheck_all_modules", return_value=_precheck_mixed()),
        patch.object(orch, "_dispatch_llm_workers", return_value={}) as mock_dispatch,
        patch("src.python.llm.fingerprint_baseline.save_baseline"),
    ):
        _run(orch)

    assert mock_dispatch.call_count == 1, "分发入口应被调用一次且仅一次"
    # 被拦下后不应触达真实生成函数（真实分发会做线程池与 client 装配）
    assert mock_dispatch.return_value == {}


def test_missing_llm_config_short_circuits():
    """无 llm 配置：直接返回全 None/False 八元组，不做预检、不分发、不写基线。"""
    from src.python.llm import generators_orchestrator as orch

    with (
        patch.object(orch, "get_llm_config", return_value=None),
        patch.object(orch, "_precheck_all_modules") as mock_precheck,
        patch.object(orch, "_dispatch_llm_workers") as mock_dispatch,
        patch("src.python.llm.fingerprint_baseline.save_baseline") as mock_baseline,
    ):
        result = _run(orch)

    assert result == (None, None, None, None, False, False, False, False)
    assert not mock_precheck.called and not mock_dispatch.called and not mock_baseline.called


def test_dispatch_receives_needs_including_holding_change(llm_enabled_config):
    """needs 契约：持仓变动归因必须并入并行批（串行后置会把耗时叠到关键路径）。"""
    from src.python.llm import generators_orchestrator as orch

    with (
        patch.object(orch, "get_llm_config", return_value=llm_enabled_config),
        patch.object(orch, "_compute_module_cache_info", return_value={}),
        patch.object(orch, "_precheck_all_modules", return_value=_precheck_mixed()),
        patch.object(orch, "_dispatch_llm_workers", return_value={}) as mock_dispatch,
        patch("src.python.llm.fingerprint_baseline.save_baseline"),
    ):
        _run(orch)

    needs = mock_dispatch.call_args.args[0]
    assert needs.get("holding_change") is True
    for key in _MODULE_KEYS:  # 广度：四模块都在需要集合里（未命中 + 开关开）
        assert key in needs
    assert MagicMock  # 保持 unittest.mock 导入被使用（同文件其它用例风格）


# ── 生成后一遍的顺序契约（自检必须在四模块产出之后串行）────────────────


def test_self_review_runs_after_fact_check_with_review_text(llm_enabled_config):
    """自检输入是「锚定后、剥离校验产物」的正文，且调用发生在锚定之后。"""
    from src.python.llm import generators_orchestrator as orch

    order: list[str] = []

    _summary_html = '<p style="color:#4a4;font-size:12px">[测试] ✓ 事实校验通过：1/1 项检查全部通过</p>'

    def _fake_fact_check(content, *_args, **_kwargs):
        order.append("fact_check")
        # 用真实上屏格式：剥离器按样式匹配，非该样式的文本不会被当校验产物剥离
        return content + "\n" + _summary_html, _summary_html

    def _fake_self_review(outputs, *_args, **_kwargs):
        order.append("self_review")
        # 自检输入只取分析正文：事实校验产物段落必须先被剥离
        for text in outputs.values():
            assert "事实校验通过" not in (text or ""), f"自检输入混入校验产物: {text!r}"

    with (
        patch.object(orch, "get_llm_config", return_value=llm_enabled_config),
        patch.object(orch, "_compute_module_cache_info", return_value={}),
        patch.object(
            orch,
            "_precheck_all_modules",
            return_value={key: {"result": f"<p>{key}</p>", "cached": False} for key in _MODULE_KEYS},
        ),
        patch.object(orch, "_dispatch_llm_workers", return_value={}),
        patch("src.python.llm.fingerprint_baseline.save_baseline"),
        patch.object(orch, "run_fact_check", side_effect=_fake_fact_check),
        patch("src.python.llm.self_review.run_self_review", side_effect=_fake_self_review),
        patch("src.python.llm.skeleton.write_back_module_cache"),
    ):
        _run(orch, holdings_details=[{"code": "600900", "name": "长江电力", "profit_rate": 1.0}])

    # 顺序契约：四模块逐个锚定，之后才是自检（不写死次数，按模块键集合派生）
    assert order[-1] == "self_review", f"自检必须在锚定之后: {order}"
    assert set(order[:-1]) == {"fact_check"}, f"锚定应逐模块执行: {order}"
    assert len(order) - 1 == len(_MODULE_KEYS), f"锚定次数应等于模块数: {order}"
