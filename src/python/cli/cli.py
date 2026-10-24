#!/usr/bin/env python3
"""CLI 命令行模式 — 主入口门面。

模块职责拆分（守住单文件 800 行红线）：

- ``_parser.py``：argparse 解析器构建与 type 回调；
- ``_handlers.py``：子命令处理器、持仓读入辅助与 ``_EXIT_*`` 退出码契约；
- 本模块：主流程 ``main()`` / ``run_cli()``、命令行功能开关应用（仅本次运行、
  不写盘），并 re-export 上述模块的对外符号——``src.python.cli`` 包门面与
  测试 patch 点（``src.python.cli.cli._handle_*`` 等）依赖本模块属性名稳定，
  删除任何 re-export 前须先迁移消费方。

"""

from __future__ import annotations

import os
import sys
from typing import NoReturn

# 确保项目根目录在 sys.path 中（支持直接执行 python src/python/cli/cli.py）
_src_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_src_dir)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.python.cli._handlers import (
    _EXIT_PARTIAL,
    _EXIT_SEVERE,
    _EXIT_SUCCESS,
    _cli_read_holdings,
    _cli_read_holdings_with_flows,
    _cli_resolve_holdings_file,
    _confirm_cost_forecast,
    _handle_cache,
    _handle_cache_update,
    _handle_cassettes,
    _handle_config,
    _handle_check_sources,
    _handle_doctor,
    _handle_health_history,
    _handle_report,
    _handle_view_logs,
    _handle_whatif,
    _resolve_source_overrides,
    _show_llm_config_status_cli,
    _use_ansi_color,
)
from src.python.cli._parser import (
    _build_parser,
    _effective_date_arg,
    _experiment_name,
    _feature_override,
)

__all__ = [
    "_EXIT_PARTIAL",
    "_EXIT_SEVERE",
    "_EXIT_SUCCESS",
    "_apply_cli_anonymize",
    "_apply_cli_chapters",
    "_apply_cli_experiments",
    "_apply_cli_switches",
    "_build_parser",
    "_cli_read_holdings",
    "_cli_read_holdings_with_flows",
    "_cli_resolve_holdings_file",
    "_effective_date_arg",
    "_experiment_name",
    "_feature_override",
    "_confirm_cost_forecast",
    "_handle_cache",
    "_handle_cache_update",
    "_handle_cassettes",
    "_handle_check_sources",
    "_handle_config",
    "_handle_doctor",
    "_handle_health_history",
    "_handle_report",
    "_handle_view_logs",
    "_handle_whatif",
    "_resolve_source_overrides",
    "_show_llm_config_status_cli",
    "_use_ansi_color",
    "main",
    "run_cli",
]

# ── 主入口 ───────────────────────────────────────────────


def _apply_cli_experiments(groups: list[tuple[str, ...]] | None) -> None:
    """启用命令行指定的实验功能（仅当前进程运行时，不写盘）。

    ``--experiment`` 已在 argparse type 回调中完成取值校验，
    此处只负责平铺与启用。持久化开关请走 TUI 菜单 S / Web 配置面板。
    """
    if not groups:
        return

    import logging

    from src.python.config.features import set_feature_enabled

    flags = sorted({flag for group in groups for flag in group})
    for flag in flags:
        set_feature_enabled(flag, True)
    logging.getLogger("invest").info("[features] 命令行启用实验功能 %d 项: %s", len(flags), "、".join(flags))


def _apply_cli_switches(pairs: list[tuple[str, bool]] | None) -> None:
    """应用命令行指定的功能开关覆写（仅当前进程运行时，不写盘）。

    与 ``_apply_cli_experiments`` 的差别是**双向**：``--feature report_qa=off``
    可关闭常规开关，用于临时复现「关掉这一项会怎样」而无须改盘上配置（实验开关
    的关闭路径仍走 features.json / 面板）。同名重复以最后一次为准（见
    ``resolve_switch_values``）。取值已在 argparse type 回调中校验。
    """
    from src.python.config.features import resolve_switch_values, set_feature_enabled

    overrides = resolve_switch_values(pairs)
    if not overrides:
        return

    import logging

    for flag, value in overrides:
        set_feature_enabled(flag, value)
    logging.getLogger("invest").info(
        "[features] 命令行覆写功能开关 %d 项: %s",
        len(overrides),
        "、".join(f"{flag}={'on' if value else 'off'}" for flag, value in overrides),
    )


def _apply_cli_chapters(pairs: list[tuple[str, bool]] | None) -> None:
    """应用命令行章节显隐覆写（仅当前进程运行时，不写盘）。"""
    if not pairs:
        return

    import logging

    from src.python.config.chapter_registry import set_chapter_runtime_override

    for key, enabled in pairs:
        set_chapter_runtime_override(key, enabled)
    logging.getLogger("invest").info(
        "[chapters] 命令行覆写报告章节 %d 项: %s",
        len(pairs),
        "、".join(f"{key}={'on' if enabled else 'off'}" for key, enabled in pairs),
    )


def _apply_cli_anonymize(mode: str | None) -> None:
    """应用命令行匿名化模式覆写（仅当前进程运行时，不写盘）。"""
    if not mode:
        return

    import logging

    from src.python.config import set_config_override

    set_config_override("anonymization.mode", mode)
    logging.getLogger("invest").info("[anonymizer] 命令行覆盖匿名化模式: %s（仅本次运行）", mode)


def _apply_cli_llm_provider_order(order: list[str]) -> int:
    """``--llm-provider-order``：经共享编辑层持久化重排多链线路，打印生效链序后退出。

    Args:
        order: 目标顺序（靠前优先），须恰好覆盖全部现有线路。

    Returns:
        int 退出码（0=成功, 2=校验/写入失败）。
    """
    from src.python.config.edit_ops import ConfigEditError, apply_config_edit

    try:
        result = apply_config_edit({"key": "llm_providers.priority", "action": "reorder", "order": order})
    except ConfigEditError as e:
        print(f"[!] {e}")
        return _EXIT_SEVERE
    names = (result.get("value") or {}).get("order") or order
    print(f"[OK] 多链线路优先级已写入 llm_providers.json：{' → '.join(names)}")
    return _EXIT_SUCCESS


def _prepare_early_exit_switches(groups: list[tuple[str, ...]] | None, pairs: list[tuple[str, bool]] | None) -> None:
    """为不初始化 config 的早返回命令应用命令行开关（--experiment / --feature）。

    ``doctor``/``check-sources``/``view-logs``/``cassettes`` 先于 ``init_config()``
    分派（配置损坏时这些命令仍须可用），故命令行开关需单独应用，否则它们会被
    静默忽略、用户据 doctor 结论误判开关状态。

    顺序与 ``init_config()`` 一致：features.json 覆写先于命令行增量——反过来
    会被随后的覆写值回冲。此处显式加载而非依赖 ``config.features`` 的导入时
    自动加载：直接依赖它会让「两个参数都没传」的情况一项覆写都不加载
    （重置为内置默认值）。重复加载不会重复打印日志——``load_feature_overrides``
    仅在取值真变化时报 INFO。

    ``--experiment`` 先于 ``--feature`` 应用：后者是显式取值，同名时应覆盖前者的
    隐式「只开」。
    """
    from src.python.config.features import load_feature_overrides

    load_feature_overrides()
    _apply_cli_experiments(groups)
    _apply_cli_switches(pairs)


def main() -> int:
    """CLI 主入口。

    Returns:
        int 退出码（0=成功, 1=部分失败, 2=严重错误）
    """
    from src.python.core.logger import log_app_boundary, setup_logger

    setup_logger()
    log_app_boundary("启动", "CLI模式")

    parser = _build_parser()
    args = parser.parse_args()

    from src.python.config import get_config, init_config

    # 以下命令不初始化 config（配置损坏时仍须可用），命令行开关需单独应用
    if args.command in ("check-sources", "view-logs", "doctor", "cassettes", "health-history"):
        _prepare_early_exit_switches(args.experiment, args.feature)

    # cassettes 同样无需 config 且只读离线：维护已录制响应，不碰用户配置
    if args.command == "cassettes":
        return _handle_cassettes(args)

    if args.command == "check-sources":
        return _handle_check_sources()

    # health-history 无需 config：只读 data/state 下的健康历史快照
    if args.command == "health-history":
        return _handle_health_history(args)

    # view-logs 无需 config：配置损坏时仍可查看日志诊断
    if args.command == "view-logs":
        return _handle_view_logs(args)

    # doctor 同样无需 config：配置损坏正是它要定位的场景，此时不能因配置读不出而拒绝自检
    if args.command == "doctor":
        return _handle_doctor(args)

    init_config(config_path=args.config)
    config = get_config()

    # 命令行开关（需在配置初始化之后：覆写加载已完成，此处为本次运行增量）
    _apply_cli_experiments(args.experiment)
    _apply_cli_switches(args.feature)
    _apply_cli_chapters(args.chapter)
    _apply_cli_anonymize(args.anonymize)

    # 多链线路优先级调整：持久化写盘后退出（调整类命令，不触发报告生成）
    if args.llm_provider_order:
        return _apply_cli_llm_provider_order(args.llm_provider_order)

    # 首次运行引导（非交互/CI/脚本环境自动跳过，不阻塞命令执行）
    try:
        from src.python.startup_wizard import show_startup_wizard_if_needed

        show_startup_wizard_if_needed(non_interactive=args.non_interactive)
    except Exception:
        import logging

        logging.getLogger("invest").debug("首次运行引导显示失败（非关键）", exc_info=True)

    if args.command == "report":
        return _handle_report(args, config)
    elif args.command == "cache":
        return _handle_cache(args, config)
    elif args.command == "whatif":
        return _handle_whatif(args, config)
    elif args.command == "config":
        return _handle_config(args, config)
    return _EXIT_SEVERE


def run_cli() -> NoReturn:
    """CLI 进程入口：执行 ``main()`` 并以退出码结束进程。

    ``python -m src.python.cli``（``__main__.py``）与 ``python src/python/cli/cli.py``
    两条入口共用本函数，保证退出码与边界日志一致。**退出码是命令对外契约的一部分**
    （``doctor`` / ``cassettes --verify`` 等都靠它表达「有失败项」），入口若丢弃
    ``main()`` 的返回值，脚本化调用（cron/CI/包装脚本）就永远只看到成功。
    """
    from src.python.core.logger import log_app_boundary

    try:
        sys.exit(main())
    except SystemExit:
        # 正常退出路径（含 argparse 的 --help/参数错误）
        log_app_boundary("关闭", "CLI模式")
        raise
    except KeyboardInterrupt:
        import logging

        logging.getLogger("invest").info("CLI 操作被用户中断")
        log_app_boundary("关闭", "CLI模式")
        sys.exit(130)
    except Exception as exc:
        import logging

        from src.python.core.error_hints import hint_for

        logging.getLogger("invest").exception("CLI 未处理异常")
        # 与 TUI 同一句用户提示（映射单源 core.error_hints）；堆栈只进日志
        print(f"[ERR] {hint_for(exc).message}", file=sys.stderr)
        log_app_boundary("关闭", "CLI模式")
        sys.exit(2)


if __name__ == "__main__":
    run_cli()
