"""生成后自检 — 对本次 LLM 分析产出做一次模型层复核。

**分层定位（与确定性校验不重叠）**：

  ① ``llm/fact_checker``：确定性校验（数值/代码/排名是否有据，可自动修正、追加摘要），
     **始终生效**，不依赖本模块；
  ② 本模块：模型层自检（结论与数据是否矛盾、是否存在未标注的推测性表述、模块间结论
     是否互斥）——由 ``llm_settings.json → enabled_llm.self_review`` 控制，**出厂默认关**（实验能力）：
     它是单份报告里输入最大的一遍（全部模块正文），产物只是尾部的复核清单；要衡量
     它是否值得开，用离线抽样 ``scripts/eval-llm-hallucination.py --self-review``。

**产物交付方式**：自检产出的「自检清单」区块由本模块的**运行作用域载体**承载，报告层
（Excel 用量页签 / HTML 自检区块）以**零参 pull** 方式取用——与
``report/experimental_notice`` 同源模式。**刻意不扩宽 4 元组 ``llm_content`` 契约**：
该契约在报告层多处按位置解包（Excel 页签、HTML 渲染、决策登记、质量分级），扩宽属
高风险改动而收益仅为一个附加区块。

**注册纪律（LLM 模块注册）**：本模块在 ``core/registry.py`` 登记（显示名/缓存前缀/TTL/用量统计/
失败原因载体随之自动获得），但**故意不出现在 ``_llm_dispatch._MODULE_FNS``**：
其输入是其余模块的产出，天然必须在它们之后串行执行，不属线程池并行调度模块——
模块注册纪律明文允许该形态（「无人调用或无独立调度语义的注册分支属注册漂移」不适用于本项，
本项有真实调用方：编排层的生成后一遍）。

**失败隔离**：自检失败只登记失败原因并保留原内容，绝不影响主内容（报告照常产出）。
"""

from __future__ import annotations

import logging
import re
import threading

logger = logging.getLogger("invest")

SELF_REVIEW_MODULE_KEY = "self_review"
"""模块语义名（config 键后缀 / 注册表 settings_suffix / 缓存前缀共用）。"""

NON_GUARANTEE_NOTE = "注：自检由模型自我复核产生，为辅助信号，不构成质量保证；投资决策与后果由使用者自行承担。"
"""固定尾注：防止把「自检通过」误读为质量背书（虚假信心）。"""

_block: str | None = None
_lock = threading.Lock()


def reset_self_review() -> None:
    """清空本轮自检载体（报告开始时调用；测试隔离亦用）。"""
    global _block
    with _lock:
        _block = None


def set_self_review_block(html: str | None) -> None:
    """写入本轮自检区块 HTML（``None`` 视为无内容）。"""
    global _block
    with _lock:
        _block = html or None


def get_self_review_block() -> str | None:
    """取本轮自检区块 HTML（无则 ``None``）——报告层零参 pull 入口。"""
    with _lock:
        return _block


def ensure_non_guarantee_note(html: str) -> str:
    """确保自检区块含固定尾注（模型未输出时由本函数确定性补上）。"""
    if not html:
        return html
    if NON_GUARANTEE_NOTE in html:
        return html
    return f"{html.rstrip()}\n<p>{NON_GUARANTEE_NOTE}</p>"


_PCT_RE = re.compile(r"[-+]?\d+(?:\.\d+)?%")

_UNVERIFIED_PCT_NOTE = (
    "注：下列百分比未能在本次数据（模块产出与持仓/穿透摘要）中逐字定位，"
    "应按「无法核实」处理，不得作为判断依据：{items}。"
)


def module_dual_form(text: str) -> str:
    """把裸模块键补成「中文名（内部键）」双写（**离线产物**用：人读中文、程序读键）。"""
    from src.python.core.registry import get_llm_module_names

    names = get_llm_module_names()
    for key in sorted(names, key=len, reverse=True):
        dual = f"{names[key]}（{key}）"
        text = text.replace(f"`{key}`", dual)
        # 已在双写括号内的键不再二次套娃（`(?<![（\w-])`）
        text = re.sub(rf"(?<![（\w-]){re.escape(key)}(?![）\w-])", dual, text)
    return text


def localize_for_display(text: str) -> str:
    """把双写形态与裸键统一成**只留中文名**（报告上屏用：读者不是开发者）。

    双写里的「（内部键）」在屏幕上只是噪声——离线评测（``scripts/eval-llm-hallucination.py``
    的自检抽样）保留双写供程序解析，两条展示口径各取所需。
    """
    from src.python.core.registry import get_llm_module_names

    names = get_llm_module_names()
    for key in sorted(names, key=len, reverse=True):
        name = names[key]
        text = text.replace(f"{name}（{key}）", name).replace(f"{name}({key})", name)
        text = text.replace(f"`{key}`", name)
        text = re.sub(rf"(?<![\w-]){re.escape(key)}(?![\w-])", name, text)
    return text


def _localize_module_keys(text: str) -> str:
    """报告上屏口径（历史名保留：调用点语义即「上屏前本地化」）。"""
    return localize_for_display(text)


def _review_corpus(
    module_outputs: dict[str, str | None],
    holdings_details: list[dict] | None,
    penetrated_assets: list[dict] | None,
    extra_blocks: tuple[str, ...],
) -> str:
    """自检可引用的原文语料（模块全文 + 摘要 + 附加事实块），用于核对引用的百分比。"""
    from src.python.llm.prompts_review import _self_review_holdings_digest, _self_review_penetration_digest

    parts = [text for text in (module_outputs or {}).values() if isinstance(text, str)]
    parts.extend(block for block in extra_blocks if block)
    parts.append(_self_review_holdings_digest(holdings_details))
    parts.append(_self_review_penetration_digest(penetrated_assets))
    return "\n".join(parts)


def _unverified_percentages(text: str, corpus: str) -> list[str]:
    """自检引用了但语料里找不到原值的百分比（模型即兴换算/编造的高发点）。"""
    found: list[str] = []
    for match in _PCT_RE.finditer(text):
        raw = match.group(0)
        digits = raw.rstrip("%").lstrip("+-")
        if digits in corpus:
            continue
        if raw not in found:
            found.append(raw)
    return found


def prepend_review_block(html: str) -> None:
    """把**确定性**核对段插到复核区块最前（事实在观点之前）。

    模型层自检默认关，区块仍要有内容——确定性的跨模块核对零 token、可门禁，
    属「先摆事实」；模型层复核（若开启）跟在后面作辅助意见。
    """
    if not html:
        return
    set_self_review_block(html + (get_self_review_block() or ""))


def _has_any_output(module_outputs: dict[str, str | None]) -> bool:
    """其余模块是否存在可复核的有效产出。"""
    return any(isinstance(v, str) and v.strip() for v in module_outputs.values())


def run_self_review(
    module_outputs: dict[str, str | None],
    holdings_details: list[dict] | None,
    penetrated_assets: list[dict] | None,
    llm_config: dict | None,
    force: bool = False,
    purchase_constraint_block: str = "",
    holding_change_block: str = "",
    event_impact_block: str = "",
    schedule_replay_block: str = "",
) -> bool:
    """生成后一遍：按开关执行自检，产出写入运行作用域载体。

    Args:
        module_outputs: 其余 LLM 模块的产出（模块名 → HTML 文本，可为 None）。
        holdings_details: 持仓明细（自检比对基准）。
        penetrated_assets: 穿透资产列表（自检比对基准）。
        llm_config: llm_settings 配置字典。
        force: 强制重算（跳过缓存）。

    Returns:
        是否产出了自检内容（开关关闭、无有效产出、调用失败均返回 ``False``）。
    """
    from src.python.llm.skeleton import is_llm_module_enabled

    if not is_llm_module_enabled(llm_config or {}, SELF_REVIEW_MODULE_KEY):
        logger.debug("生成后自检已禁用（enabled_llm.%s = false），跳过", SELF_REVIEW_MODULE_KEY)
        return False

    if not _has_any_output(module_outputs):
        # 上游全失败/占位 → 无可复核内容。登记失败原因（可观测），不视为错误。
        _register_skip_reason("无有效内容可自检")
        logger.info("生成后自检跳过：其余 LLM 模块无有效产出")
        return False

    from src.python.llm.generators import generate_self_review

    try:
        content, _from_cache = generate_self_review(
            module_outputs,
            holdings_details,
            penetrated_assets,
            force=force,
            llm_config=llm_config,
            purchase_constraint_block=purchase_constraint_block,
            holding_change_block=holding_change_block,
            event_impact_block=event_impact_block,
            schedule_replay_block=schedule_replay_block,
        )
    except Exception as e:  # noqa: BLE001 — 自检失败不得影响主内容（报告照常产出）
        logger.warning("生成后自检调用异常（不影响主内容）: %s", e)
        _register_skip_reason(f"自检调用异常：{e}")
        return False

    if not content:
        _register_skip_reason("自检未产出有效清单")
        logger.warning("生成后自检未产出有效内容（不影响主内容）")
        return False

    content = _localize_module_keys(content)
    unverified = _unverified_percentages(
        content,
        _review_corpus(
            module_outputs,
            holdings_details,
            penetrated_assets,
            (
                purchase_constraint_block,
                holding_change_block,
                event_impact_block,
                schedule_replay_block,
            ),
        ),
    )
    if unverified:
        logger.warning("[self_review] 自检引用了语料中查不到的百分比：%s", ", ".join(unverified))
        content = f"{content}\n<p>{_UNVERIFIED_PCT_NOTE.format(items='、'.join(unverified[:5]))}</p>"
    set_self_review_block(ensure_non_guarantee_note(content))
    return True


def _register_skip_reason(reason: str) -> None:
    """把「未产出」原因登记到失败原因载体（与其余模块同源，供报告层展示）。"""
    try:
        from src.python.llm.prompts import LLM_MODULE_FAILURE

        LLM_MODULE_FAILURE[SELF_REVIEW_MODULE_KEY] = reason
    except Exception:  # noqa: BLE001 — 登记失败不影响主流程
        logger.debug("[self_review] 失败原因登记失败", exc_info=True)


__all__ = [
    "NON_GUARANTEE_NOTE",
    "SELF_REVIEW_MODULE_KEY",
    "ensure_non_guarantee_note",
    "get_self_review_block",
    "localize_for_display",
    "module_dual_form",
    "prepend_review_block",
    "reset_self_review",
    "run_self_review",
    "set_self_review_block",
]
