"""CLI argparse 解析器构建 —— 全局参数、子命令定义与 type 回调校验。

仅负责「参数如何定义与解析」；解析结果的执行（子命令处理器）在
``_handlers.py``，主流程编排在 ``cli.py`` 门面。
"""

from __future__ import annotations

import argparse

from src.python.core.constants import APP_NAME, APP_VERSION
from src.python.core.doctor import NETWORK_TIMEOUT_DEFAULT

# ── argparse 解析器 ─────────────────────────────────────


def _experiment_name(value: str) -> tuple[str, ...]:
    """argparse type 回调 —— 校验并归一化 ``--experiment`` 取值。

    取值清单取自 features 注册表的实验项（experimental 字段，与 TUI 菜单 S / Web 配置面板同源），
    支持开关名、显示名与 ``all``。命中多个（``all``）时返回全部开关名，调用方
    平铺后统一启用。

    名称解析本身容忍空白项（见 resolve_experiment_flags），但命令行取值
    为空串时属用户笔误，此处按非法取值报错，不静默忽略。
    """
    from src.python.config.features import describe_experiment_flags, resolve_experiment_flags

    flags, unknown = resolve_experiment_flags([value])
    if unknown or not flags:
        raise argparse.ArgumentTypeError(f"未知实验功能 '{value}'；可选: {describe_experiment_flags()}、all")
    return tuple(sorted(flags))


def _parse_switch_bool(value: str) -> bool:
    """``on/off`` 类布尔词表（CLI 一次性开关统一取值域）。"""
    token = value.strip().lower()
    if token in ("on", "true", "1", "yes"):
        return True
    if token in ("off", "false", "0", "no"):
        return False
    raise argparse.ArgumentTypeError(f"布尔取值须为 on/off（收到：{value}）")


def _chapter_override(value: str) -> tuple[str, bool]:
    """argparse type 回调 —— 校验 ``--chapter KEY=on|off`` 的章节键与取值。

    键取章节注册表的稳定键名（含智囊团生成子项），不存在则当场报错并列出可选值；
    该覆写**仅本次运行**（不写盘），持久化请用 ``config set``。
    """
    from src.python.config.chapter_registry import chapter_by_key, chapter_registry

    key, sep, raw = value.partition("=")
    key = key.strip()
    if not sep or not key:
        raise argparse.ArgumentTypeError("格式应为 KEY=on|off（如 enable_news=off、expert_review=off）")
    enabled = _parse_switch_bool(raw)
    if chapter_by_key(key) is None:
        valid: list[str] = []
        for entry in chapter_registry:
            valid.append(entry.key)
            valid.extend(entry.sub_items)
        raise argparse.ArgumentTypeError(f"未知章节键 '{key}'；可选: {', '.join(valid)}")
    return key, enabled


def _provider_order(value: str) -> list[str]:
    """``--llm-provider-order`` 参数校验：非空线路名列表（覆盖性校验在共享编辑层）。"""
    names = [part.strip() for part in value.split(",")]
    if not names or not all(names):
        raise argparse.ArgumentTypeError("线路名列表不能为空（如 deepseek-main,opencode-go）")
    if len(set(names)) != len(names):
        raise argparse.ArgumentTypeError("线路名重复")
    return names


def _feature_override(value: str) -> tuple[str, bool]:
    """argparse type 回调 —— 校验 ``--feature NAME=VALUE`` 取值。

    与 ``--experiment`` 的区别见各自 help：本参数作用于**全部**功能开关（含常规
    组）且**双向**（可关）。取值域与合法性在解析期即校验——错误的开关名或取值
    当场报错并列出可选项，不留给运行时静默失效。
    """
    from src.python.config.features import parse_switch_override

    try:
        return parse_switch_override(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _effective_date_arg(value: str) -> str:
    """argparse 类型钩子：生效日归一化校验（委托共享层，与 Web/TUI 同一规则）。"""
    from src.python.report.whatif_operations import normalize_effective_date

    try:
        return normalize_effective_date(value) or ""
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from e


def _build_parser() -> argparse.ArgumentParser:
    """构建 argparse 参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="investor-review",
        description=f"{APP_NAME} — 命令行模式",
        epilog="示例: python -m src.python.cli report --type full --history auto",
    )

    # 全局参数
    parser.add_argument("--config", metavar="PATH", help="备用配置文件路径（默认: data/config/config.json）")
    parser.add_argument("--output", metavar="DIR", help="报告输出目录（覆盖 config.json 的 output_dir）")
    parser.add_argument("--verbose", action="store_true", help="将进度消息同步到 stderr（默认仅写入 logs/app.log）")
    parser.add_argument("--non-interactive", action="store_true", help="跳过首次运行交互式引导（定时任务/脚本使用）")
    parser.add_argument(
        "--experiment",
        metavar="NAME",
        action="append",
        type=_experiment_name,
        help="启用实验性功能，仅本次运行生效（不写入 features.json）。可重复指定；"
        "NAME 取开关名或显示名，all=全部启用。等价于 --feature 只开全部实验项的简写。",
    )
    parser.add_argument(
        "--feature",
        metavar="NAME=VALUE",
        action="append",
        type=_feature_override,
        help="覆写任意功能开关（含常规开关），仅本次运行生效（不写入 features.json）。可重复指定；"
        "NAME 取开关名，VALUE ∈ on/off/true/false/1/0（大小写不敏感）。"
        "与 --experiment 的区别：本参数是全开关双向覆写，后者只开实验项。",
    )
    parser.add_argument(
        "--chapter",
        metavar="KEY=on|off",
        action="append",
        type=_chapter_override,
        help="一次性覆盖报告章节显隐（仅本次运行，不写盘；键取章节注册表稳定名，含智囊团子项）。"
        "可重复指定；与 --feature 作用于同一子项时本参数后应用（优先生效）。"
        "持久化请用 config set / TUI [C] / Web 配置面。",
    )
    parser.add_argument(
        "--anonymize",
        choices=["off", "code_display", "full_anonymous", "summary"],
        default=None,
        help="一次性覆盖持仓匿名化模式（仅本次运行，不写盘）；持久化请用 config set anonymization.mode。",
    )
    parser.add_argument(
        "--llm-provider-order",
        metavar="NAME[,NAME...]",
        type=_provider_order,
        help="重排 LLM 多链线路优先级并**写入** llm_providers.json（靠前优先），随后退出。"
        "NAME 须恰好覆盖全部现有线路（如 deepseek-main,opencode-go）。"
        "与 --feature（仅本次运行、不写盘）不同：本参数持久化；亦可在 TUI [G] → [L] LLM 设置 / Web 配置面调序。",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s v{APP_VERSION}")

    sub = parser.add_subparsers(dest="command", required=True)

    # ── report 子命令 ──
    report_p = sub.add_parser("report", help="生成投资分析报告")
    report_p.add_argument(
        "--type",
        choices=["basic", "both", "full"],
        default="basic",
        help="报告类型: basic=仅Excel(≈1min, 默认), both=HTML+Excel(不含LLM,≈2min), "
        "full=全量含LLM(≈5min, 定时任务按需开启)",
    )
    report_p.add_argument(
        "--history",
        choices=["auto", "off"],
        default=None,
        help="获取组合历史走势数据: auto=获取, off=跳过（未指定时按配置 history.fetch_mode，默认 auto；"
        "仅 --type both/full 时有效）",
    )
    report_p.add_argument("--force-llm", action="store_true", help="强制重新生成 LLM 内容（跳过缓存）")
    from src.python.llm.force_scope import FORCEABLE_LLM_MODULES

    report_p.add_argument(
        "--llm-module",
        action="append",
        default=None,
        metavar="KEY",
        choices=list(FORCEABLE_LLM_MODULES),
        help=f"仅强制重新生成指定 LLM 模块（可重复传参，粒度优先于 --force-llm 全量；"
        f"可选: {', '.join(FORCEABLE_LLM_MODULES)}）",
    )
    report_p.add_argument(
        "--yes",
        action="store_true",
        help="跳过生成前 LLM 费用预估确认（脚本/自动化常用；日预算超限仍直接中止）",
    )
    report_p.add_argument(
        "--prefer-source",
        action="append",
        default=None,
        metavar="NAME",
        help="本次运行优先使用的数据源（可重复；不写配置，仅排到链首，不绕过熔断）",
    )
    report_p.add_argument(
        "--exclude-source",
        action="append",
        default=None,
        metavar="NAME",
        help="本次运行排除的数据源（可重复；用于排障复现，不写配置）",
    )

    # ── cache 子命令 ──
    cache_p = sub.add_parser("cache", help="缓存管理")
    cache_action = cache_p.add_mutually_exclusive_group(required=True)
    cache_action.add_argument(
        "--update", choices=["basic", "position", "all"], help="更新缓存: basic=基础类, position=持仓类, all=全部"
    )
    cache_action.add_argument("--clean", action="store_true", help="清理过期缓存文件")
    cache_action.add_argument("--stats", action="store_true", help="查看缓存文件统计/状态")
    cache_p.epilog = (
        "示例:\n"
        "  cache --update all             更新全部缓存\n"
        "  cache --update basic           仅更新基础类缓存\n"
        "  cache --clean                  清理过期缓存\n"
        "  cache --stats                  查看缓存统计"
    )

    # ── whatif 子命令 ──
    whatif_p = sub.add_parser("whatif", help="调仓 What-if 模拟：对比两份持仓生成 diff 报告")
    whatif_p.add_argument("--candidate", metavar="PATH", required=True, help="目标持仓文件（调仓后/假设，必填）")
    whatif_p.add_argument("--base", metavar="PATH", help="基准持仓文件（调仓前）；缺省用 config 配置的持仓文件")
    whatif_p.add_argument(
        "--effective-date",
        metavar="YYYY-MM-DD",
        type=_effective_date_arg,
        help="调仓生效日（可选）：指定后 opt-in 联网取生效日后行情，追加时序回测页（区间/年化收益、波动率、夏普、最大回撤）",
    )
    whatif_p.epilog = (
        "示例:\n"
        "  whatif --candidate 调仓后.xlsx              对比当前持仓 vs 目标持仓（成本口径截面比较）\n"
        "  whatif --base 调仓前.xlsx --candidate 调仓后.xlsx   显式指定两份持仓\n"
        "  whatif --candidate 调仓后.xlsx --effective-date 2026-07-01   指定生效日，追加时序回测\n"
        "输出: 调仓模拟.xlsx / .html（最新版固定名，历史归档至日期子目录；默认零网络请求，指定生效日时联网取历史做假设推演，不构成收益承诺）"
    )

    # ── cassettes 子命令（只读维护，无需 config）──
    cassettes_p = sub.add_parser(
        "cassettes",
        help="数据源记录-回放：列出已录制响应 / 离线校验能否被当前解析器解析（无需 config）",
    )
    cassettes_p.add_argument(
        "--verify",
        action="store_true",
        help="逐条离线回放并交给当前解析器解析（不联网）；有解析失败则退出码 2",
    )
    cassettes_p.epilog = (
        "示例:\n"
        "  cassettes           列出已录制 cassette（来源/录制时间/交互数）\n"
        "  cassettes --verify  离线校验每份录制的解析路径\n"
        "\n"
        "刷新录制需联网且为显式动作：\n"
        "  python scripts/test-runner.py --mode live --record-cassettes"
    )

    # ── check-sources 子命令 ──
    check_p = sub.add_parser("check-sources", help="数据源健康检查（无需 config）")
    check_p.epilog = "示例:\n  check-sources    测试各数据源联通性"

    # ── health-history 子命令 ──
    health_p = sub.add_parser("health-history", help="数据源健康历史（最近 N 次采集，无需 config）")
    health_p.add_argument(
        "--limit",
        type=int,
        default=10,
        help="显示最近多少次采集记录（默认 10）",
    )
    health_p.add_argument("--json", action="store_true", help="以 JSON 输出（供脚本消费）")
    health_p.epilog = (
        "示例:\n"
        "  health-history             查看最近 10 次数据源健康历史\n"
        "  health-history --limit 30  查看最近 30 次\n"
        "  health-history --json      输出 JSON（与 Web /api/health/history 同字段）"
    )

    # ── view-logs 子命令 ──
    logs_p = sub.add_parser("view-logs", help="查看结构化运行日志（无需 config）")
    logs_p.add_argument(
        "--level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="最小级别阈值（ERROR 含 ERROR+CRITICAL；默认全部）",
    )
    logs_p.add_argument(
        "--lines",
        type=int,
        default=5000,
        help="读取日志末尾物理行数上限（默认 5000，防止大日志卡顿）",
    )
    logs_p.add_argument("--since", metavar="YYYY-MM-DD[ HH:MM:SS]", help="起始时间前缀过滤")
    logs_p.add_argument("--until", metavar="YYYY-MM-DD[ HH:MM:SS]", help="结束时间前缀过滤（含边界）")
    logs_p.epilog = (
        "示例:\n"
        "  view-logs                     查看最近日志\n"
        "  view-logs --level ERROR      只看 ERROR+CRITICAL\n"
        "  view-logs --since 2026-08-16 只看指定日期之后\n"
        "  view-logs --lines 200        只读末尾 200 行"
    )

    # ── doctor 子命令（只读诊断，不依赖 config 初始化）──
    doctor_p = sub.add_parser("doctor", help="系统自检：环境/配置/目录/数据源一键体检（无需 config）")
    doctor_p.add_argument(
        "--offline",
        action="store_true",
        help="跳过数据源网络检查（仅查本地环境/配置/目录，瞬时返回）",
    )
    doctor_p.add_argument(
        "--timeout",
        type=float,
        default=NETWORK_TIMEOUT_DEFAULT,
        help=f"网络检查整体耗时预算秒数（默认 {NETWORK_TIMEOUT_DEFAULT:g}，防止慢速数据源拖住自检）",
    )
    doctor_p.epilog = (
        "示例:\n"
        "  doctor              完整自检（含数据源联通性）\n"
        "  doctor --offline    仅本地自检，不联网\n"
        "  doctor --timeout 15 放宽网络检查耗时预算"
    )

    # ── config 子命令（共享配置的查看与持久化编辑）──
    config_p = sub.add_parser(
        "config",
        help="查看/修改共享配置（白名单键；写盘前 .bak 备份，值校验与 TUI/Web 同源）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    config_sub = config_p.add_subparsers(dest="config_action", required=True)
    cfg_list = config_sub.add_parser("list", help="列出可编辑键与当前生效值（含 scheduler.*）")
    cfg_list.add_argument("--json", action="store_true", help="以 JSON 输出（供脚本消费）")
    cfg_get = config_sub.add_parser("get", help="读取单个键的当前生效值（JSON 输出）")
    cfg_get.add_argument(
        "key", metavar="KEY", help="点分键，如 holdings_dir / enabled_llm.health_check / scheduler.time"
    )
    cfg_set = config_sub.add_parser("set", help="写入单个键（持久化；动作型键请用专用参数）")
    cfg_set.add_argument("key", metavar="KEY", help="点分键（config list 查看全部）")
    cfg_set.add_argument("value", metavar="VALUE", help="目标值（bool 用 on/off；周几用 0,1,2 逗号分隔）")
    cfg_set.add_argument("--dry-run", action="store_true", help="只校验并输出归一化值，不写盘")
    config_p.epilog = (
        "示例:\n"
        "  config list                              列出全部可编辑键与当前值\n"
        "  config get holdings_dir                  读取单个键\n"
        "  config set enable_news off               关闭「市场新闻」章节（持久化）\n"
        "  config set anonymization.mode summary    设置匿名化模式（持久化）\n"
        "  config set scheduler.enabled on          启用 Web 内置定时生成\n"
        "  config set scheduler.weekdays 0,1,2,3,4  设置执行日（0=周一）\n"
        "  config set holdings_filename a.xlsx --dry-run  只校验不写盘\n"
        "\n"
        "一次性（不改盘）请用全局参数 --chapter / --anonymize / --feature。"
    )

    return parser
