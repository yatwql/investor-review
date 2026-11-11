"""`_dispatch_llm_workers` 派发结构契约测试。

断言的是结构不变式（拆分 `_worker_runner` / `_debate_router` 前后都必须成立），
不是某次生成的文本：

  - 结果键集合：返回字典的键集合 == 实际提交的模块键集合（needs=False 的不提交）
  - worker 返回形状：`(content, from_cache)` → `{"result", "cached"}`
  - 失败只登记一次：线程异常不外抛、不污染其它模块的结果，且留 WARNING
  - 并发闸门：thinking 模块由 `thinking_enabled_{label}` 认定，上限非法值回落 1
  - 预算闸：超预算的模块返回 `(None, False)` 并计入跳过汇总
  - 辩论槽位替换：`expert_review` 键名不变，pro/con 失败时回退普通生成
  - client 降级：`make_http_client` 因缺 h2 抛 ImportError 时去掉 http2 重试一次

运行：
  pytest src/test/unit/llm/test_llm_dispatch_contract.py -v
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from src.python.llm import _llm_dispatch as dispatch
from src.python.llm import _worker_runner as _worker_runner_mod

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]

_CFG = {"llm_max_concurrency": 2, "llm_max_thinking_concurrency": 2}


def _call(needs: dict[str, bool], *, llm_config: dict | None = None, client=None, **kwargs):
    """以最小参数调派发入口（外部依赖全 patch，线程池为真但只跑纯 Python 闭包）。

    `client` 为 None 时用 MagicMock；需要验证装配降级时由调用方传自己的工厂。
    """
    params = {
        "needs": needs,
        "llm_config": llm_config if llm_config is not None else _CFG,
        "force": False,
        "a_indices": {},
        "us_indices": {},
        "total_mv": 0.0,
        "total_cost": 0.0,
        "total_profit": 0.0,
        "total_today_profit": 0.0,
        "holdings_count": 0,
        "categories": {},
        "penetrated_assets": None,
        "holdings_details": None,
        "sector_flow": None,
    }
    params.update(kwargs)
    factory = client if client is not None else (lambda **_kwargs: MagicMock())
    with patch.object(_worker_runner_mod, "make_http_client", side_effect=factory):
        return dispatch._dispatch_llm_workers(**params)


def test_result_keys_equal_submitted_keys():
    """结果键集合 == 提交集合：needs=False 的模块既不提交也不出现在结果里。"""
    fns = {
        "global_macro": lambda _c, _lc: ("<p>宏</p>", False),
        "health_check": lambda _c, _lc: ("<p>体检</p>", False),
        "penetration_deep": lambda _c, _lc: (None, False),
    }
    needs = {"global_macro": True, "health_check": True, "penetration_deep": True, "expert_review": False}

    with patch.object(dispatch, "_build_module_fns", return_value=dict(fns)):
        result = _call(needs)

    assert set(result) == {key for key, need in needs.items() if need}
    assert "expert_review" not in result, "needs=False 的模块不得出现在结果字典里"


def test_worker_result_shape_is_content_and_flag():
    """worker 的 `(content, from_cache)` 落成 `{"result", "cached"}`。"""
    fns = {"global_macro": lambda _c, _lc: ("<p>宏</p>", True)}

    with patch.object(dispatch, "_build_module_fns", return_value=dict(fns)):
        result = _call({"global_macro": True})

    assert result["global_macro"] == {"result": "<p>宏</p>", "cached": True}


def test_empty_needs_short_circuits_without_building_fns():
    """全部 needs 为假：不装配生成函数、不入线程池，直接返回空字典。"""
    with patch.object(dispatch, "_build_module_fns") as mock_build:
        result = _call({"global_macro": False, "health_check": False})

    assert result == {}
    assert not mock_build.called


def test_thread_exception_does_not_escape_or_pollute_other_modules(caplog):
    """单模块线程异常：不外抛、不写该键、其余模块照常返回，且留 WARNING。"""

    def _boom(_c, _lc):
        raise RuntimeError("线程炸了")

    fns = {"global_macro": _boom, "health_check": lambda _c, _lc: ("<p>体检</p>", False)}

    with patch.object(dispatch, "_build_module_fns", return_value=dict(fns)):
        result = _call({"global_macro": True, "health_check": True})

    assert "health_check" in result and "global_macro" not in result
    assert any("LLM 生成线程异常" in record.getMessage() for record in caplog.records), (
        "线程异常必须留痕（否则模块静默缺失）"
    )


@pytest.mark.parametrize("configured,expected", [(0, 1), (-3, 1), ("abc", 1), (2, 2)])
def test_thinking_concurrency_limit_falls_back_to_one(configured, expected):
    """thinking 并发上限：非法值（<=0/非数值）回落 1，合法值原样生效。"""
    seen: list[int] = []
    semaphore_factory = threading.BoundedSemaphore

    def _spy(limit):
        seen.append(limit)
        return semaphore_factory(max(1, limit))

    with (
        patch.object(dispatch, "_build_module_fns", return_value={"global_macro": lambda _c, _lc: ("<p>x</p>", False)}),
        patch.object(dispatch.threading, "BoundedSemaphore", side_effect=_spy),
    ):
        _call({"global_macro": True}, llm_config={"llm_max_thinking_concurrency": configured})

    assert seen and seen[0] == expected, f"上限取值异常: {seen}"


def test_budget_guard_skips_overrun_modules_without_killing_running_ones():
    """预算闸：超预算模块返回 (None, False) 并计入跳过汇总（不打断已提交的模块）。"""
    fns = {"global_macro": lambda _c, _lc: ("<p>宏</p>", False)}

    with (
        patch.object(dispatch, "_build_module_fns", return_value=dict(fns)),
        # 起点拨到很久以前 → 首次检查即超预算
        patch.object(dispatch.time, "monotonic", return_value=10_000.0),
    ):
        result = _call({"global_macro": True}, llm_config={**_CFG, "llm_total_time_budget_sec": 1})

    assert result["global_macro"] == {"result": None, "cached": False}, "预算跳过必须给出 (None, False)"


def test_debate_route_keeps_expert_review_key_and_falls_back():
    """辩论槽位替换：键名仍是 expert_review；pro/con 失败时回退普通生成。"""
    called: list[str] = []
    container: list = [None]

    def _original(_c, _lc):
        called.append("original")
        return ("<p>原始智囊团</p>", False)

    fns = {"expert_review": _original}

    with (
        patch.object(dispatch, "_build_module_fns", return_value=dict(fns)),
        # 辩论生成函数在路由模块内**延迟导入**（避免与 generators 的导入环）→
        # 按「patch 源模块」纪律指向定义处
        patch("src.python.llm.generators.generate_debate_procon", return_value=("", "", "")),
        patch("src.python.config.features.is_feature_enabled", side_effect=lambda name: name == "llm_debate_procon"),
    ):
        result = _call({"expert_review": True}, _debate_info_container=container)

    assert set(result) == {"expert_review"}, "辩论模式不得改变结果键名"
    assert called == ["original"], "pro/con 失败必须回退普通生成"
    assert container[0] is None, "回退时不得残留辩论信息"


def test_client_falls_back_to_http1_when_h2_missing():
    """client 降级单点：缺 h2 包时去掉 http2 设置重试一次，能力判定只在装配处。"""
    attempts: list[dict] = []

    def _fake_client(**kwargs):
        attempts.append(kwargs)
        if "http2" in kwargs:
            raise ImportError("h2 未安装")
        return MagicMock()

    fns = {"global_macro": lambda _c, _lc: ("<p>宏</p>", False)}

    with patch.object(dispatch, "_build_module_fns", return_value=dict(fns)):
        result = _call({"global_macro": True}, client=_fake_client)

    assert result["global_macro"]["result"] == "<p>宏</p>"
    assert len(attempts) == 2, f"应「带 http2 失败 → 去掉 http2 重试」共两次，实际 {attempts}"
    assert "http2" not in attempts[1]
