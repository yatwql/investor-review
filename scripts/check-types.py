#!/usr/bin/env python3
"""类型检查守护（pyright）—— 产品代码与入口脚本的类型错误门禁。

守护域与规则基线写在 `pyproject.toml` 的 `[tool.pyright]`：

  - `include`：`src/python`（产品代码；`scripts/` 入口脚本的 argparse/流替换/平台桩噪声
    另立项清理，未入本守护域）
  - `exclude`：**刻意排除 `src/test`**——单测天然大量 mock / 行内 dict，静态噪音远多于
    缺陷收益，其正确性由 pytest 运行时守卫（怪癖口径同 `technical.md` 的类型检查决策）
  - `venvPath` / `venv`：依赖解析走项目虚拟环境（否则 pandas/akshare/flask 判缺失）

「ERROR」级别即 finding；WARNING/INFORMATION 不计（pyright 默认依据即可，不自造阈值）。
单条 finding 打印为 `文件:行:列 规则 首行说明`，与其余守护脚本同构。

用法：
  python scripts/check-types.py
    检查全守护域，有 error 时按契约退出（退出码 2）。

  python scripts/check-types.py --ci
    CI 模式（只输出裸 finding 行，不打汇总行）。

  python scripts/check-types.py -v
    详细模式（打印解析器版本与受检目标）。

  python scripts/check-types.py src/python/llm
    显式指定受检路径（覆盖 include；排他规则仍生效），供改单模块时快反馈。

退出码：
  0 — 无类型错误
  1 — 环境缺失（pyright 既不在 PATH，也无 npx 可用）
  2 — 发现类型错误
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_shared）
from _shared.checklib import REPO_ROOT, add_common_args, rel, report  # noqa: E402

#: 默认受检路径（与 `[tool.pyright] include` 同域；CLI 传路径即覆盖）
DEFAULT_TARGETS: tuple[str, ...] = ("src/python",)

#: 单次输出上限（CI 日志友好；超出时末尾给「其余 N 条」一行）
MAX_REPORTED = 60


def venv_pyright_path() -> Path | None:
    """虚拟环境里安装的 pyright（未激活 venv 时 PATH 上找不到它）。

    `pip install pyright` 装进 .venv 后，`git commit` 走钩子时通常没有 activate，
    PATH 里只有解释器自己——故按解释器同目录再找一份。
    """
    candidate = Path(sys.executable).parent / ("pyright.exe" if os.name == "nt" else "pyright")
    return candidate if candidate.is_file() else None


def pyright_command() -> list[str] | None:
    """定位 pyright 可执行入口：PATH → 虚拟环境 → npx（`--no-install`，不联网）。

    Returns:
        可直接拼参数的命令前缀；三者都没有时返回 None（调用方按环境缺失退出 1）。
    """
    exe = shutil.which("pyright")
    if exe:
        return [exe]
    venv_exe = venv_pyright_path()
    if venv_exe is not None:
        return [str(venv_exe)]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--no-install", "pyright"]
    return None


def run_pyright(cmd: list[str], targets: list[str], *, timeout: float = 900.0) -> dict[str, Any] | None:
    """跑一次 pyright 并解析 JSON 报告。

    Args:
        cmd: 命令前缀（``pyright_command()`` 的返回）。
        targets: 受检路径（相对仓库根）。
        timeout: 子进程超时秒数。

    Returns:
        解析后的报告 dict；子进程无 JSON 输出（如参数错误）时返回 None。
    """
    proc = subprocess.run(
        [*cmd, "--outputjson", *targets],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,  # pyright 有 error 时退出码非 0，报告仍在 stdout
    )
    stdout = (proc.stdout or "").strip()
    if not stdout:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def collect_findings(report_data: dict[str, Any]) -> list[str]:
    """从 pyright 报告里取 ERROR 级诊断，转成 ``文件:行:列 规则 说明`` 行。

    Args:
        report_data: ``run_pyright`` 解析出的报告。

    Returns:
        finding 行列表（已按文件/行排序）；WARNING/INFORMATION 不计。
    """
    rows: list[tuple[str, int, int, str]] = []
    for diag in report_data.get("generalDiagnostics", []) or []:
        if diag.get("severity") != "error":
            continue
        path = str(diag.get("file") or "")
        start = diag.get("range", {}).get("start", {}) or {}
        line = int(start.get("line", 0)) + 1
        column = int(start.get("character", 0)) + 1
        rule = str(diag.get("rule") or "error")
        message = " ".join(str(diag.get("message") or "").split("\n")[0].split())
        rows.append((rel(Path(path)), line, column, f"{rule}: {message}"))
    rows.sort()
    return [f"{path}:{line}:{column} {detail}" for path, line, column, detail in rows]


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。

    Args:
        argv: 参数列表（默认取 ``sys.argv[1:]``；测试可注入）。

    Returns:
        退出码（0 通过 / 1 环境缺失 / 2 有 finding）。
    """
    parser = argparse.ArgumentParser(description="类型检查守护（pyright）")
    parser.add_argument("paths", nargs="*", default=[], help=f"受检路径（缺省 {', '.join(DEFAULT_TARGETS)}）")
    add_common_args(parser)
    args = parser.parse_args(argv)

    cmd = pyright_command()
    if cmd is None:
        print(
            "[ERR] 类型检查不可用：未找到 pyright（可 pip install pyright，或确保 npx 可用）",
            file=sys.stderr,
        )
        return 1

    targets = [str(p) for p in (args.paths or DEFAULT_TARGETS)]
    if args.verbose:
        print(f"[..] 解析器：{' '.join(cmd)}")
        print(f"[..] 受检目标：{', '.join(targets)}")

    report_data = run_pyright(cmd, targets)
    if report_data is None:
        print("[ERR] 类型检查未能取得 JSON 报告（pyright 调用失败）", file=sys.stderr)
        return 1

    findings = collect_findings(report_data)
    if not findings:
        if args.verbose:
            summary = report_data.get("summary", {}) or {}
            print(f"[..] 诊断统计：{summary.get('errorCount', 0)} error / {summary.get('warningCount', 0)} warning")
        return report([], "[OK] 类型检查通过（无 ERROR 级诊断）", ci=args.ci)
    shown = findings[:MAX_REPORTED]
    if len(findings) > MAX_REPORTED:
        shown = [*shown, f"[!] 其余 {len(findings) - MAX_REPORTED} 条已省略（本地全跑看全量）"]
    return report(shown, "[OK] 类型检查通过（无 ERROR 级诊断）", ci=args.ci)


if __name__ == "__main__":
    sys.exit(main())
