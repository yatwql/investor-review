"""发布编排 CLI 面 — argparse 装配与命令分派（入口 `scripts/release.py` 保留命令实现）。

下沉动机：`release.py` 逼近 1000 行红线，而 argparse 装配与具体命令实现无关；
本模块不导入入口模块（命令处理表由入口注入），避免与 `release.py` 成环。
"""

from __future__ import annotations

import argparse
from collections.abc import Callable

#: refresh 的 bench 模式子集——只测**门禁口径**关心的四档：P0 `dev-verify`、
#: P1 `verify` 的 unit 总量面、P2 `regression`、CI 恒跑的 `integration`。全量 14 档
#: 串行约 5.5 min（2 路采集 3.2 min），占单次发布机器时间约 75%，而其余模式与这四档
#: 高度重叠（standard / scenario / edge / data / smoke / report / all_no_unit /
#: scenario_extreme / all）；未实测模式的耗时与计数按 `--update-docs` 既有口径
#: 「保留上次实测值」，不会写脏。需要全量复测时用 `--full-bench`。
RELEASE_BENCH_MODES: tuple[str, ...] = ("unit", "dev-verify", "regression", "integration")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="release.py",
        description="发布流程分步编排（每步独立可审阅、失败即停；详见模块文档字符串与 developer-guide）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="预检：分支/工作树/版本形态/tag/版本一致性")

    p_prepare = sub.add_parser("prepare", help="版本全链 + changelog 发布段归档 + 一致性 --fix + 台账/设计文件归档迁移")
    p_prepare.add_argument("--version", help="目标发布版（默认按 APP_VERSION 推导）")
    p_prepare.add_argument("--date", help="发布日期 YYYY-MM-DD（默认今天）")
    p_prepare.add_argument("--no-archive", action="store_true", help="跳过自动归档迁移（需单独跑 archive）")

    p_archive = sub.add_parser(
        "archive", help="台账归档迁移：rf 已解决表原表搬入归档 + plan 已完成节 + docs/plan 已完成设计文件"
    )
    p_archive.add_argument("--date", help="发布日（缺省今天）")
    p_archive.add_argument("--dry-run", action="store_true", help="只报告动作，不写任何文件")
    p_archive.add_argument("--skip-design-docs", action="store_true", help="跳过 docs/plan 设计文件迁档（只做台账）")

    p_archive_init = sub.add_parser(
        "archive-init", help="新小版本归档骨架初始化（三份归档 + 目录树块 + 三处索引行，幂等）"
    )
    p_archive_init.add_argument("--version", default=None, help="目标发布版（默认按 APP_VERSION 推导）")
    p_archive_init.add_argument("--date", default=None, help="发布日期 YYYY-MM-DD（默认今天）")
    p_archive_init.add_argument("--dry", action="store_true", help="只报告将做的改动，不落盘")

    p_refresh = sub.add_parser(
        "refresh",
        help="数据刷新：bench（发布子集）--update-docs + collect + doc-drift --sync（纯文档变更自动跳过前两者）",
    )
    p_refresh.add_argument("--force-refresh", action="store_true", help="忽略纯文档变更判定，强制刷新 bench 与 collect")
    p_refresh.add_argument(
        "--bench-jobs",
        type=int,
        default=None,
        help="bench 采集并行度（透传 test-runner --jobs；改变并行度会改变实测耗时口径，"
        "环境表「采集并行度」行需同口径才可比）",
    )
    p_refresh.add_argument(
        "--full-bench",
        action="store_true",
        help=f"bench 跑全量模式（默认只测发布子集 {', '.join(RELEASE_BENCH_MODES)}，未测模式耗时沿用上次实测）",
    )

    p_evolution = sub.add_parser("evolution", help="版本演进对照快照（默认只滚当前开发版列）")
    p_evolution.add_argument("--release", action="store_true", help="发布期使用：发布列与增长比一并写入")

    p_gate = sub.add_parser("gate", help="P2 门禁：演进新鲜度 + verify + regression + 十守护 --ci + 设计护栏")
    p_gate.add_argument(
        "--with-portability",
        action="store_true",
        help="追加 CI portability 等价探针（隐式编码 + 需求文件 locale 解码，约 +110s）",
    )

    p_publish = sub.add_parser("publish", help="release 提交 + P1 verify + --no-ff 合并 + tag")
    p_publish.add_argument("--title", required=True, help="release 提交主题（changelog 摘要式短描述）")
    p_publish.add_argument("--push", action="store_true", help="完成后推送 dev/master/tags（默认只打印命令）")

    p_devbump = sub.add_parser("devbump", help="切下一开发版并提交")
    p_devbump.add_argument(
        "--no-push",
        dest="push",
        action="store_false",
        default=True,
        help="切版后不推送 dev（默认推送 origin dev）",
    )
    p_devbump.add_argument(
        "--push",
        dest="push",
        action="store_true",
        help="兼容保留：默认已推送（显式写与省略等效）",
    )
    return parser


def run_cli(
    argv: list[str] | None,
    handlers: dict[str, Callable[[argparse.Namespace], int]],
    *,
    reset_timer: Callable[[], object],
    finish_timing: Callable[[str, int], None],
    release_error: type[Exception],
) -> int:
    """解析参数并分派到入口注入的命令表。

    Args:
        argv: 命令行参数（None 取 `sys.argv[1:]`）。
        handlers: 子命令名 → 处理函数。
        reset_timer: 每命令重建耗时计时器（入口的实现）。
        finish_timing: 命令尾写耗时台账（入口的实现）。
        release_error: 命令异常类型；命中时打印可读原因并返回 2。
    """
    args = build_parser().parse_args(argv)
    reset_timer()
    try:
        rc = handlers[args.command](args)
    except release_error as exc:
        print(f"[ERR] {exc}")
        rc = 2
    finish_timing(args.command, rc)
    return rc
