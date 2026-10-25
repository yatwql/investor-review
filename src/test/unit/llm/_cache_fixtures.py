"""LLM 缓存测试共用构造器（输入 / 编排调用 / 常量；命名遵循 `_<模块>_fixtures.py`）。

四个缓存测试文件（`test_report_sequence_cache` / `test_cache_matrix` /
`test_cache_real_config` / `test_cache_cost_accounting`）此前各自复制了一份
`_inputs()`、`cache_dir` fixture、`_run()` 与常量——同一份「最小自洽输入」改一处
要改四遍，且容易漂移出只在一个文件里存在的差异。集中在此，各文件只保留自己的
关注点（断言）。

目录内的共享 fixture 在 `conftest.py`（`llm_cache_dir`）；本模块只放纯函数与常量。
"""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any

HOLDING_CODE = "600900"

#: 多链配置（首选 probe-main；备链 probe-backup 仅故障转移用例用）
CHAIN_CONFIG: dict[str, Any] = {
    "_provider_list": [
        {"name": "probe-main", "provider": "claude", "api_key": "sk-x"},
        {"name": "probe-backup", "provider": "claude", "api_key": "sk-y"},
    ],
    "_strategy": "priority",
    "_preferred_providers": {},
    "llm_max_concurrency": 2,
}

#: 基础四模块在 `generate_all_llm` 返回元组（后四位缓存标志）中的下标
MODULE_INDEX = {"global_macro": 0, "expert_review": 1, "health_check": 2, "penetration_deep": 3}

#: 默认 mock 回复（模型名取真实定价表内的条目，保证费用估算非零）
LLM_REPLY_DEFAULT = (
    "<p>生成内容</p>",
    {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 0},
    {"name": "probe-main", "model": "deepseek-v4-flash", "endpoint": "e"},
)

#: 高 token 回复（成本用例：单次调用即可产生可见费用）
LLM_REPLY_PAID = (
    "<p>生成内容</p>",
    {"input_tokens": 1000, "output_tokens": 500, "cache_read_input_tokens": 0},
    {"name": "probe-main", "model": "deepseek-v4-flash", "endpoint": "e"},
)


def make_inputs() -> dict[str, Any]:
    """一套自洽的最小输入（指数/持仓/穿透/历史/管线/量化指标）。"""
    return {
        "a_indices": {"sh000300": {"name": "沪深300", "close": 4000.0, "change_pct": 0.5}},
        "us_indices": {"^IXIC": {"name": "纳斯达克", "close": 18000.0, "change_pct": -0.2}},
        "categories": {"股票": {"market_value": 10000.0, "cost": 9000.0, "count": 1}},
        "holdings_details": [
            {"name": "测试A", "code": HOLDING_CODE, "cost": 1.0, "shares": 100, "market_value": 120.0}
        ],
        "penetrated_assets": [{"name": "测试A", "code": HOLDING_CODE, "weight": 100.0}],
        "history_data": {
            "max_drawdown_pct": -15.0,
            "annualized_volatility": 0.17,
            "total_return_pct": -10.0,
            "status": "ok",
        },
        "pipeline_data": {"diff": {"added": [], "removed": []}, "data_degradation": []},
        "metrics": {"sharpe": 1.2, "hhi": 0.3},
    }


def degradation_events(*sources: str, times: int = 1, count: int = 1) -> list[dict[str, Any]]:
    """同一批源各产生 `times` 条失败事件（`count` 为跨会话累计次数）。"""
    return [
        {
            "source_key": src,
            "tier": "T3",
            "success": False,
            "failure_type": "unreachable",
            "degraded": True,
            "count": count,
        }
        for src in sources
        for _ in range(times)
    ]


def run_generate_all_llm(
    inputs: dict[str, Any],
    *,
    llm_config: dict[str, Any] | None = None,
    reply: tuple | None = None,
    error: BaseException | None = None,
    force: bool = False,
    force_modules: frozenset[str] | None = None,
    degradation: list[dict[str, Any]] | None = None,
    patch_call: bool = True,
    patch_config: bool = True,
) -> tuple[bool, bool, bool, bool]:
    """调用真实 `generate_all_llm`（仅网络层被 mock），返回四模块缓存标志。

    Args:
        inputs: `make_inputs()` 形状的输入。
        llm_config: 注入的配置；None 用 `CHAIN_CONFIG`。
        patch_config: 是否 patch 两处 `get_llm_config`（编排层 + `config` 模块——
            后者由 `generation_params_suffix` 直接读）。真实配置文件链路的用例传
            False，让配置从磁盘加载。
        reply: mock 的 LLM 返回；None 用 `LLM_REPLY_DEFAULT`。
        error: 若给则让调用抛该异常（模拟全链路失败）。
        force / force_modules: 强制重算范围。
        degradation: 数据质量失败事件。
        patch_call: False 供并发用例在外部单点 patch（多线程各自 patch 同一
            目标会让 mock 的保存/恢复交错，`call_llm` 会永久留在 Mock 上）。

    Returns:
        (global_macro, expert_review, health_check, penetration_deep) 命中标志。
    """
    from unittest.mock import patch

    from src.python.llm import generators_orchestrator as go

    conf = dict(llm_config) if llm_config is not None else dict(CHAIN_CONFIG)

    with ExitStack() as stack:
        if patch_config:
            from src.python import config as cfg_mod

            stack.enter_context(patch.object(go, "get_llm_config", return_value=dict(conf)))
            stack.enter_context(patch.object(cfg_mod, "get_llm_config", return_value=dict(conf)))
        if patch_call:
            if error is not None:
                stack.enter_context(patch("src.python.llm.skeleton.call_llm", side_effect=error))
            else:
                stack.enter_context(patch("src.python.llm.skeleton.call_llm", return_value=reply or LLM_REPLY_DEFAULT))

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
            metrics=inputs.get("metrics"),
            degradation_events=degradation or [],
            force=force,
            force_modules=force_modules,
        )
    return out[4:8]  # type: ignore[return-value]
