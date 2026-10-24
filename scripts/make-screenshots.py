#!/usr/bin/env python3
"""演示截图生成器（README / 手册配图）：隔离演示工作区 + TUI 帧渲染 + Web CDP 截图。

一条流水线四个子命令，产物全部落在 `docs/tmp/screenshots/`（git 忽略域），
真实 `data/`（持仓、配置、密钥）零接触：

  demo                              建隔离演示工作区：自造持仓 + 占位凭据 + 相对路径上屏配置
  report                            在演示工作区生成 Excel + HTML 报告
  tui <out.png> [--config P] [--text F]
                                    把一帧 TUI 首页渲染成 PNG（取帧走生产渲染函数）
  web <url> <out.png> [--scroll-y N] [--width W] [--height H] [--replace from=>to] [--chrome P]
                                    无头 Chromium CDP 截图（滚动后截视口，固定侧栏不丢）

典型用法（README 配图刷新）：

  .venv/bin/python scripts/make-screenshots.py demo
  .venv/bin/python scripts/make-screenshots.py report
  .venv/bin/python scripts/make-screenshots.py tui docs/tmp/screenshots/demo/tui-menu.png
  .venv/bin/python scripts/make-screenshots.py web http://127.0.0.1:8000/workbench \\
      docs/tmp/screenshots/demo/web-workbench.png --scroll-y 0

TUI 渲染需 Pillow + 等宽 CJK 字体（Noto Sans Mono CJK）；Web 截图需 Node ≥22 与本机
Chromium（`--chrome` / `CHROME_BIN`）。两者都只在本机手工运行，不进提交与发布门禁。

退出码：
  0 — 成功
  1 — 环境缺失（Pillow / CJK 字体 / Node / Chromium）或运行失败
  2 — 参数或子命令错误
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/ 与内部包导入面

from _screenshots import demo_workspace, tui_frame, web_shot  # noqa: E402


def _demo(_: argparse.Namespace) -> int:
    print(f"  [OK] 演示工作区：{demo_workspace.build()}")
    return 0


def _report(_: argparse.Namespace) -> int:
    return demo_workspace.run_report()


def _tui(args: argparse.Namespace) -> int:
    argv = [str(args.output)]
    if args.config is not None:
        argv += ["--config", str(args.config)]
    if args.text is not None:
        argv += ["--text", str(args.text)]
    return tui_frame.main(argv)


def _web(args: argparse.Namespace) -> int:
    return web_shot.run(
        args.url,
        args.output,
        scroll_y=args.scroll_y,
        width=args.width,
        height=args.height,
        replace=args.replace,
        chrome=args.chrome,
    )


def build_parser() -> argparse.ArgumentParser:
    """子命令解析表（`-h` 打印本模块 docstring）。"""
    parser = argparse.ArgumentParser(
        prog="make-screenshots.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("demo", help="建隔离演示工作区（自造持仓 + 占位凭据）")
    demo.set_defaults(handler=_demo)

    report = subparsers.add_parser("report", help="在演示工作区生成 Excel + HTML 报告")
    report.set_defaults(handler=_report)

    tui = subparsers.add_parser("tui", help="把一帧 TUI 首页渲染成 PNG")
    tui.add_argument("output", type=Path, help="输出 PNG 路径")
    tui.add_argument("--config", type=Path, help="配置路径（缺省用演示工作区配置）")
    tui.add_argument("--text", type=Path, help="改用已有的帧文本文件（跳过取帧）")
    tui.set_defaults(handler=_tui)

    web = subparsers.add_parser("web", help="无头 Chromium CDP 截图")
    web.add_argument("url", help="目标页面 URL")
    web.add_argument("output", type=Path, help="输出 PNG 路径")
    web.add_argument("--scroll-y", type=int, default=0, help="滚动到该纵向位置再截图（默认 0）")
    web.add_argument("--width", type=int, default=1440, help="视口宽（默认 1440）")
    web.add_argument("--height", type=int, default=940, help="视口高（默认 940）")
    web.add_argument("--replace", default="", help="截图前替换文本，写法 `原文=>替换`（用于抹除临时数据）")
    web.add_argument("--chrome", default=None, help="Chromium/Chrome 可执行文件（缺省按 CHROME_BIN 等次序解析）")
    web.set_defaults(handler=_web)
    return parser


def main(argv: list[str] | None = None) -> int:
    """按子命令分发，返回退出码。"""
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
