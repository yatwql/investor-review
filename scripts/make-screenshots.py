#!/usr/bin/env python3
"""演示截图生成器（README / 手册配图）：隔离演示工作区 + TUI 帧渲染 + Web CDP 截图。

一条流水线五个子命令，产物全部落在 `docs/tmp/screenshots/`（git 忽略域），
真实 `data/`（持仓、配置、密钥）零接触：

  demo                              建隔离演示工作区：自造持仓 + 占位凭据 + 相对路径上屏配置
  report                            在演示工作区生成 Excel + HTML 报告
  tui <out.png> [--config P] [--text F]
                                    把一帧 TUI 首页渲染成 PNG（取帧走生产渲染函数）
  cli <out.png> [--text F]            把一次 CLI 生成输出渲染成 PNG（伪终端采集，含进度与耗时排行）
  web <url> <out.png> [--scroll-y N] [--width W] [--height H] [--replace from=>to] [--chrome P]
                                    无头 Chromium CDP 截图（滚动后截视口，固定侧栏不丢；
                                    省略 --scroll-y 时保留 URL 锚点定位，适合报告章节截图）
  xlsx <in.xlsx> <out.png> [--sheet NAME] [--rows N] [--cols N]
                                    把一个 Excel 页签按真实内容排成表格图（列标/行号/页签条）

典型用法（README 配图刷新）：

  .venv/bin/python scripts/make-screenshots.py demo
  .venv/bin/python scripts/make-screenshots.py report
  .venv/bin/python scripts/make-screenshots.py tui docs/tmp/screenshots/demo/tui-menu.png
  .venv/bin/python scripts/make-screenshots.py web http://127.0.0.1:8000/workbench \\
      docs/tmp/screenshots/demo/web-workbench.png --scroll-y 0
  .venv/bin/python scripts/make-screenshots.py xlsx \\
      docs/tmp/screenshots/demo/reports/个人投资分析报告.xlsx src/static/excel-report.png

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

from _screenshots import demo_workspace, tui_frame, web_shot, xlsx_frame  # noqa: E402


def _demo(_: argparse.Namespace) -> int:
    print(f"  [OK] 演示工作区：{demo_workspace.build()}")
    return 0


def _report(_: argparse.Namespace) -> int:
    demo_workspace.assert_demo_holdings()
    return demo_workspace.run_report()


def _tui(args: argparse.Namespace) -> int:
    demo_workspace.assert_demo_holdings()
    argv = [str(args.output)]
    if args.config is not None:
        argv += ["--config", str(args.config)]
    if args.text is not None:
        argv += ["--text", str(args.text)]
    return tui_frame.main(argv)


def _cli(args: argparse.Namespace) -> int:
    """把一帧 CLI 生成输出渲染成 PNG（伪终端采集 + 状态护栏）。"""
    from _screenshots import tui_frame

    demo_workspace.assert_demo_holdings()
    text = demo_workspace.capture_report_text()
    if args.text is not None:
        text = Path(args.text).read_text(encoding="utf-8")
    output = tui_frame.render(text + "\n", args.output)
    print(f"  [OK] {output}")
    return 0


def _web(args: argparse.Namespace) -> int:
    """无头截图；``--serve-demo`` 时自起演示服务（环境与工作区由本脚本统一注入）。"""
    demo_workspace.assert_demo_holdings()
    server = None
    url = args.url
    if args.serve_demo:
        server, url = _start_demo_server(args.url)
    try:
        return web_shot.run(
            url,
            args.output,
            scroll_y=args.scroll_y,
            width=args.width,
            height=args.height,
            replace=args.replace,
            chrome=args.chrome,
        )
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except Exception:  # 收尾失败不影响截图结果
                server.kill()


def _xlsx(args: argparse.Namespace) -> int:
    """把一个 Excel 页签按内容排成表格图（数字全部取自该工作簿）。"""
    demo_workspace.assert_demo_holdings()
    return xlsx_frame.render(
        args.workbook,
        args.output,
        sheet_name=args.sheet,
        width=args.width,
        height=args.height,
        max_rows=args.rows,
        max_cols=args.cols,
        chrome=args.chrome,
    )


def _start_demo_server(url: str) -> tuple:
    """按演示工作区环境起 Web 服务，返回 (进程, 换成实际端口的 URL)。

    环境统一走 ``demo_workspace.isolation_env``（含 ``INVEST_PROJECT_ROOT``），
    避免手工拼 env 时漏项导致服务读到真实持仓。
    """
    import os as _os
    import socket
    import subprocess
    import sys as _sys
    import time
    import urllib.request
    from urllib.parse import urlparse, urlunparse

    demo = demo_workspace.demo_dir()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {
        **_os.environ,
        "PYTHONPATH": str(demo_workspace.REPO_ROOT),
        **demo_workspace.isolation_env(demo),
    }
    server = subprocess.Popen(
        [_sys.executable, "-m", "src.python.web", "--port", str(port)],
        cwd=str(demo),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    parsed = urlparse(url)
    target = urlunparse(parsed._replace(netloc=f"127.0.0.1:{port}"))
    for _ in range(60):
        try:
            urllib.request.urlopen(target, timeout=1).read(64)
            break
        except Exception:
            time.sleep(0.5)
    return server, target


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

    cli = subparsers.add_parser("cli", help="把一帧 CLI 生成输出渲染成 PNG（伪终端采集）")
    cli.add_argument("output", type=Path, help="输出 PNG 路径")
    cli.add_argument("--text", type=Path, help="改用已有的输出文本文件（跳过采集）")
    cli.set_defaults(handler=_cli)

    web = subparsers.add_parser("web", help="无头 Chromium CDP 截图")
    web.add_argument("url", help="目标页面 URL")
    web.add_argument("output", type=Path, help="输出 PNG 路径")
    web.add_argument(
        "--scroll-y",
        type=int,
        default=None,
        help="滚动到该纵向位置再截图（省略时保留 URL 锚点定位，适合 #sec-xxx 章节图）",
    )
    web.add_argument("--width", type=int, default=1440, help="视口宽（默认 1440）")
    web.add_argument("--height", type=int, default=940, help="视口高（默认 940）")
    web.add_argument("--replace", default="", help="截图前替换文本，写法 `原文=>替换`（用于抹除临时数据）")
    web.add_argument("--chrome", default=None, help="Chromium/Chrome 可执行文件（缺省按 CHROME_BIN 等次序解析）")
    web.add_argument(
        "--serve-demo",
        action="store_true",
        help="先按演示工作区环境自起 Web 服务再截图（URL 的 host:port 被替换为本机临时端口）",
    )
    web.set_defaults(handler=_web)

    xlsx = subparsers.add_parser("xlsx", help="把 Excel 页签按内容排成表格图（列标/行号/页签条）")
    xlsx.add_argument("workbook", type=Path, help="报告工作簿（.xlsx）路径")
    xlsx.add_argument("output", type=Path, help="输出 PNG 路径")
    xlsx.add_argument("--sheet", default=None, help="页签名（缺省取第一个页签）")
    xlsx.add_argument("--rows", type=int, default=xlsx_frame.DEFAULT_MAX_ROWS, help="最多渲染行数（默认 26）")
    xlsx.add_argument("--cols", type=int, default=None, help="最多渲染列数（缺省取该页全部列）")
    xlsx.add_argument("--width", type=int, default=1440, help="视口宽（默认 1440）")
    xlsx.add_argument("--height", type=int, default=940, help="视口高（默认 940）")
    xlsx.add_argument("--chrome", default=None, help="Chromium/Chrome 可执行文件（缺省按 CHROME_BIN 等次序解析）")
    xlsx.set_defaults(handler=_xlsx)
    return parser


def main(argv: list[str] | None = None) -> int:
    """按子命令分发，返回退出码。"""
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
