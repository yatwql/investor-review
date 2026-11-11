"""辩论模式路由：把 `expert_review` 槽位替换成 pro→con→synthesis 的串行组合。

契约要点（拆出本模块的原因就是它们容易在派发函数里被埋掉）：

  - **槽位替换而非新增模块**：`_MODULE_FNS` 里改的是 `expert_review` 这一项，结果字典
    的键名因此不变，下游章仍按 `expert_review` 取内容；
  - **两级回退**：synthesis 失败 → 返回 pro+con 拼接（仍是辩论产出，标记为命中）；
    pro 或 con 失败 / 整段抛异常 → 回退**普通生成**实现，且必须清空辩论信息容器
    （残留会让报告显示一份并不存在的辩论结论）；
  - 辩论走独立的 pro/con/synthesis 缓存键，因此派发侧对 expert_review 会绕过标准预检。

本模块不做并发、不建 client（client 由 worker 注入），也不判定 needs。
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import Any

logger = logging.getLogger("invest")


def debate_mode_combination() -> str:
    """当前启用的辩论模式组合标识（如 "正反辩论+条件推理"）。

    集中度问答段已内建于辩论流程（阈值触发），不参与组合维度。
    """
    from src.python.config.features import is_feature_enabled

    parts: list[str] = []
    if is_feature_enabled("llm_debate_procon"):
        parts.append("正反辩论")
    if is_feature_enabled("llm_debate_conditional"):
        parts.append("条件推理")
    return "+".join(parts) if parts else ""


def install_debate_route(
    module_fns: dict[str, Callable],
    *,
    needs: dict[str, bool],
    total_mv: float,
    total_cost: float,
    total_profit: float,
    total_today_profit: float,
    holdings_count: int,
    categories: dict,
    penetrated_assets: list[dict] | None,
    holdings_details: list[dict] | None,
    force: bool,
    force_modules: Iterable[str] | None,
    pipeline_data: dict | None,
    competitive_context: str,
    metrics: dict | None,
    purchase_constraint_block: str,
    holding_change_block: str,
    event_impact_block: str,
    schedule_replay_block: str,
    debate_info_container: list | None,
) -> bool:
    """辩论模式启用且 `expert_review` 需要生成时，替换该槽位。

    Args:
        module_fns: 模块键 → 生成函数（原地替换 `expert_review` 项）。
        needs: 各模块是否需要生成。
        debate_info_container: 辩论信息捕获容器（list[dict|None]），调用方事后读取。
        （其余为辩论生成所需的组合上下文透传参数）

    Returns:
        是否完成了替换。
    """
    from src.python.config.features import is_feature_enabled
    from src.python.llm.generators import generate_debate_procon

    if not (is_feature_enabled("llm_debate_procon") and needs.get("expert_review")):
        return False

    original = module_fns.get("expert_review")
    if original is None:
        return False

    def _clear_debate_info() -> None:
        if debate_info_container is not None:
            debate_info_container[0] = None

    def _debate_wrapper(client: Any, llm_config: dict | None) -> tuple[str | None, bool]:
        """辩论包装：pro→con→synthesis，两级回退。"""
        try:
            pro, con, synthesis = generate_debate_procon(
                total_mv,
                total_cost,
                total_profit,
                total_today_profit,
                holdings_count,
                categories,
                penetrated_assets,
                holdings_details=holdings_details,
                force=force or (force_modules is not None and "expert_review" in force_modules),
                http_client=client,
                llm_config=llm_config,
                pipeline_data=pipeline_data,
                competitive_context=competitive_context,
                metrics=metrics,
                purchase_constraint_block=purchase_constraint_block,
                holding_change_block=holding_change_block,
                event_impact_block=event_impact_block,
                schedule_replay_block=schedule_replay_block,
            )
            if pro and con:
                if debate_info_container is not None:
                    debate_info_container[0] = {
                        "pro_text": pro,
                        "con_text": con,
                        "mode_label": "辩论模式",
                        "mode_combination": debate_mode_combination(),
                    }
                if synthesis:
                    return (synthesis, True)
                # synthesis 失败 → pro+con 拼接（仍是辩论产出）
                logger.warning("[debate] 综合失败，返回 pro+con 拼接")
                return (f"【白脸观点】\n{pro}\n\n【黑脸观点】\n{con}", True)
            # pro 或 con 失败 → 回退普通生成
            logger.warning("[debate] pro/con 失败，回退普通生成")
            _clear_debate_info()
            return original(client, llm_config)
        except Exception:  # noqa: BLE001 — 辩论整段失败不得拖垮 expert_review
            logger.warning("[debate] 异常，回退普通生成", exc_info=True)
            _clear_debate_info()
            return original(client, llm_config)

    module_fns["expert_review"] = _debate_wrapper
    logger.info("[debate] 辩论模式已启用，expert_review 路由已替换")
    return True


__all__ = ["debate_mode_combination", "install_debate_route"]
