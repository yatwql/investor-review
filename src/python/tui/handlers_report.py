"""TUI 报告生成命令处理器。

仅保留 TUI 专属交互外壳，业务编排逻辑全部委托 orchestrator。
"""

from __future__ import annotations

from src.python.core.logger import setup_logger
from src.python.core.registry import get_llm_module_names
from src.python.report import orchestrator
from src.python.report.progress import TuiProgressReporter
from src.python.tui.tui_handlers import (
    finish_report,
    prepare_holdings,
    print_error_with_hint,
    print_llm_session_usage,
)
from src.python.tui.tui_menu import get_config_cache

logger = setup_logger()


def _prompt_history() -> bool:
    """TUI 交互外壳：是否获取历史走势（fetch_mode 解析委托共享层）。

    - ``enable_history=False``（整章关闭）→ False；
    - fetch_mode 三态由 ``report.history_policy.resolve_fetch_history`` 单源解析，
      ``prompt`` 时注入本函数的 y/N 询问回调——渠道层不再自行分支三态。
    """
    from src.python.config import is_enable_history
    from src.python.report.history_policy import resolve_fetch_history

    config = get_config_cache() or {}
    if not is_enable_history(config):
        return False

    def _ask_history() -> bool:
        try:
            resp = input("  [..] 是否获取组合历史走势数据（as-if 模拟）？(y/N): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return resp == "y"

    return resolve_fetch_history(config, ask=_ask_history)


def _prompt_force_llm(reporter: TuiProgressReporter) -> tuple[bool, list[str] | None]:
    """TUI 专属：询问用户是否强制刷新 LLM 缓存，可选模块级粒度。

    Returns:
        (force_llm, force_llm_modules)——均未指定时 (False, None)；
        强制且未选模块时 (True, None)（全量）；指定模块时 (False, [keys])，
        让模块级粒度优先生效（共享层 resolve_force_scope 同源合并）。
    """
    from src.python.llm.force_scope import FORCEABLE_LLM_MODULES, resolve_force_scope

    try:
        _resp = input("  [..] 是否强制重新生成 LLM 内容（跳过缓存）？(y/N): ").strip().lower()
        _force = _resp == "y"
    except (EOFError, KeyboardInterrupt):
        _force = False
    if not _force:
        return (False, None)
    reporter.ok("将跳过 LLM 缓存强制重新生成")
    # 模块级粒度：列出可选模块，输入编号/键名子集（逗号或空格分隔），回车=全量
    try:
        _names = get_llm_module_names()
        print("  [..] 指定强制模块（可选）：")
        for i, key in enumerate(FORCEABLE_LLM_MODULES, 1):
            print(f"      {i}. {key}（{_names.get(key, key)}）")
        _resp2 = input("  [..] 输入编号或键名（逗号分隔，回车=全部模块）: ").strip()
    except (EOFError, KeyboardInterrupt):
        _resp2 = ""
    if not _resp2:
        return (True, None)
    _tokens = [t for t in _resp2.replace(",", " ").split() if t]
    _keys: list[str] = []
    _bad: list[str] = []
    for t in _tokens:
        if t.isdigit() and 1 <= int(t) <= len(FORCEABLE_LLM_MODULES):
            _keys.append(FORCEABLE_LLM_MODULES[int(t) - 1])
        elif t in FORCEABLE_LLM_MODULES:
            _keys.append(t)
        else:
            _bad.append(t)
    if _bad:
        reporter.warn(f"无法识别的模块: {', '.join(_bad)}，本次按全量强制")
        return (True, None)
    _keys = list(dict.fromkeys(_keys))  # 去重保序
    resolve_force_scope(False, _keys)  # 校验（非法键抛 ValueError，此处已过滤）
    reporter.ok(f"仅强制重新生成: {', '.join(_keys)}")
    return (False, _keys)


def _run_generate(
    report_type: str,
    *,
    fetch_history: bool | None = None,
    force_llm: bool | None = None,
    force_llm_modules: list[str] | None = None,
) -> TuiProgressReporter | None:
    """通用报告生成命令骨架。

    Args:
        report_type: 报告类型（"basic" / "both" / "full"）
        fetch_history: 是否获取历史走势，None 表示不传入（使用 orchestrator 默认）
        force_llm: 是否强制刷新 LLM 缓存，None 表示不传入
        force_llm_modules: 模块级强刷键列表，None 表示不传入

    Returns:
        TuiProgressReporter 实例（成功时）或 None（持仓未就绪时）
    """
    reporter = TuiProgressReporter()
    config = get_config_cache() or {}
    prepared = prepare_holdings()
    if not prepared:
        return None
    holdings, transactions, dividends = prepared
    kwargs: dict = {
        "holdings": holdings,
        "config": config,
        "reporter": reporter,
        "report_type": report_type,
        "transactions": transactions,
        "dividends": dividends,
    }
    if fetch_history is not None:
        kwargs["fetch_history"] = fetch_history
    if force_llm is not None:
        kwargs["force_llm"] = force_llm
    if force_llm_modules is not None:
        kwargs["force_llm_modules"] = force_llm_modules
    try:
        orchestrator.generate_report(**kwargs)
    except Exception as e:
        logger.exception("生成 %s 报告失败", report_type)
        print_error_with_hint(e, "生成失败")
    finish_report(reporter)
    return reporter


def _cmd_generate_excel() -> None:
    """生成 Excel 分析报告（必选内容）。"""
    _run_generate("basic")


def _cmd_generate_both() -> None:
    """生成全系列包含新闻的报告（Excel+HTML，不含 LLM 分析章节）。"""
    _run_generate("both", fetch_history=_prompt_history())


def _cmd_generate_full() -> None:
    """生成包含所有内容的全系列报告（Excel + HTML + 新闻 + LLM 分析章节）。"""
    reporter = TuiProgressReporter()
    _force, _force_modules = _prompt_force_llm(reporter)
    _run_generate(
        "full",
        fetch_history=_prompt_history(),
        force_llm=_force,
        force_llm_modules=_force_modules,
    )
    print_llm_session_usage()
