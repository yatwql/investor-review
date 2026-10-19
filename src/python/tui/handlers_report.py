"""TUI 报告生成命令处理器。

仅保留 TUI 专属交互外壳，业务编排逻辑全部委托 orchestrator。
"""

from __future__ import annotations

from src.python.core.logger import setup_logger
from src.python.core.registry import get_llm_module_names
from src.python.llm.cost_forecast import budget_status, forecast_run_cost, forecast_summary_lines
from src.python.report import orchestrator
from src.python.report.progress import TuiProgressReporter
from src.python.tui.tui_handlers import (
    finish_report,
    prepare_holdings,
    print_error_with_hint,
    print_llm_session_usage,
)
from src.python.tui.text_layout import terminal_columns, wrap_hanging, wrap_prompt
from src.python.tui.tui_keys import PromptCancelledError, input_choice
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
            resp = input_choice(wrap_prompt("  [..] 是否获取组合历史走势数据（as-if 模拟）？(y/N): "))
        except (EOFError, KeyboardInterrupt):
            return False
        if resp is None:  # Esc：中止生成返回主菜单（Esc ≠ 答 N 继续）
            raise PromptCancelledError
        return resp.strip().lower() == "y"

    return resolve_fetch_history(config, ask=_ask_history)


def _select_force_modules(reporter: TuiProgressReporter) -> tuple[bool, list[str] | None]:
    """模块级重新生成选择（合并单屏按 ``f`` 后触发）：列可选模块、输入子集、回车=全量。

    Returns:
        (force_llm, force_llm_modules)——回车全量 (True, None)；指定子集 (False, [keys])，
        让模块级粒度优先生效（共享层 resolve_force_scope 同源合并）。
    """
    from src.python.llm.force_scope import FORCEABLE_LLM_MODULES, resolve_force_scope

    # 模块级粒度：列出可选模块，输入编号/键名子集（逗号或空格分隔），回车=全量
    try:
        _names = get_llm_module_names()
        print("  [..] 指定要重新生成的模块（可选）：")
        for i, key in enumerate(FORCEABLE_LLM_MODULES, 1):
            print(f"      {i}. {key}（{_names.get(key, key)}）")
        _resp2 = input_choice(wrap_prompt("  [..] 输入编号或键名（逗号分隔，回车=全部模块）: "))
    except (EOFError, KeyboardInterrupt):
        _resp2 = ""
    if _resp2 is None:  # Esc：中止流程返回主菜单
        raise PromptCancelledError
    _resp2 = _resp2.strip()
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
        reporter.warn(f"无法识别的模块: {', '.join(_bad)}，本次按全部模块重新生成")
        return (True, None)
    _keys = list(dict.fromkeys(_keys))  # 去重保序
    resolve_force_scope(False, _keys)  # 校验（非法键抛 ValueError，此处已过滤）
    reporter.ok(f"仅重新生成: {', '.join(_keys)}")
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
        force_llm: 是否重新生成 LLM 内容（跳过已有结果），None 表示不传入
        force_llm_modules: 模块级强制重新生成键列表，None 表示不传入

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


def _prompt_generate_confirm(reporter: TuiProgressReporter, config: dict) -> tuple[bool, list[str] | None, bool] | None:
    """问句式单屏一次确认：费用预估上屏 + 问句（讲清 Y/N 各自代价）+ 键位行（回车/Y / N / [h] / q）。

    替代原先「①是否重新生成 y/N → ③费用预估 y/N」两问（默认路径从 2~3 问降为 1 问）；历史走势以
    ``h`` 选项并入本屏（仅 fetch_mode=prompt 时展示，其余模式由共享层 resolve 单源解析）。
    按键按**词**精确匹配（空格/逗号分隔，支持 ``n h`` 组合；``f`` 为 ``N`` 同义键，
    ``of``/``faq`` 这类子串不误触发）。

    Returns:
        (force_llm, force_llm_modules, fetch_history)；None=中止（不进入生成）。
    日预算超限走独立安全网确认（用已有结果继续 / 中止），不并入单屏——费用保护不受合并影响。
    该路径不追加历史询问（prompt 模式回落为不获取），但输出一行「本次不获取历史走势」
    提示保证可感知（告知后覆盖，不追加提问）。
    """
    from src.python.config import is_enable_history
    from src.python.report.history_policy import resolve_fetch_history

    forecast = forecast_run_cost()
    budget = budget_status()
    for line in forecast_summary_lines(forecast, budget):
        print(f"  [..] {line}")

    # 安全网：日预算超限 → 独立确认（用已有结果继续 / 中止），不给重新生成入口
    mode = ((config.get("history") or {}).get("fetch_mode")) or "auto"
    if budget.get("exceeded"):
        try:
            resp = input_choice(
                wrap_prompt("  [!] 今日 LLM 费用已达日预算上限：y=继续（用已有结果，本次不重新生成） / N=中止 (y/N): ")
            )
        except (EOFError, KeyboardInterrupt):
            return None
        if resp is None:  # Esc
            print("  [!] 已取消本次生成")
            return None
        if resp.strip().lower() != "y":
            print("  [!] 已中止本次生成（日预算超限）")
            return None
        fetch_history = resolve_fetch_history(config, ask=lambda: False) if is_enable_history(config) else False
        if mode == "prompt" and is_enable_history(config):
            print("  [..] 本次用已有结果，不获取历史走势")
        return (False, None, fetch_history)

    # 问句式：问句行先答「为什么/代价是什么」，键位行只作答——不要求用户记暗语
    hist_opt = " / h=含历史走势" if (mode == "prompt" and is_enable_history(config)) else ""
    _question = "  [?] 是否用已有的 AI 分析结果生成？（Y=用已有结果，免费但可能不是最新；N=重新生成，会产生费用）"
    for _line in wrap_hanging(_question, terminal_columns(), indent="      "):
        print(_line)
    try:
        resp = input_choice(wrap_prompt(f"  回车/Y=用已有结果生成 / N=重新生成（可选模块）{hist_opt} / q=中止: "))
    except (EOFError, KeyboardInterrupt):
        return None
    if resp is None:  # Esc
        print("  [!] 已取消本次生成")
        return None
    tokens = set(resp.strip().lower().replace(",", " ").split())  # 词级匹配，子串不误触发
    if "q" in tokens:
        print("  [!] 已中止本次生成")
        return None
    force_llm, force_modules = (False, None)
    if tokens & {"n", "f"}:  # N=重新生成（默认 Y 侧不进此分支）；f 与 N 同义
        reporter.ok("将忽略已有结果，重新调用 AI 生成")
        force_llm, force_modules = _select_force_modules(reporter)
    # 历史：复用共享层 resolve（ask 回调返回本屏 h 选择），不再单独询问
    fetch_history = resolve_fetch_history(config, ask=lambda: "h" in tokens) if is_enable_history(config) else False
    return (force_llm, force_modules, fetch_history)


def _cmd_generate_full() -> None:
    """生成包含所有内容的全系列报告（Excel + HTML + 新闻 + LLM 分析章节）。"""
    reporter = TuiProgressReporter()
    config = get_config_cache() or {}
    confirm = _prompt_generate_confirm(reporter, config)
    if confirm is None:  # 中止（Esc / q / 预算超限中止）
        return
    _force, _force_modules, _fetch_history = confirm
    _run_generate(
        "full",
        fetch_history=_fetch_history,
        force_llm=_force,
        force_llm_modules=_force_modules,
    )
    print_llm_session_usage()
