#!/usr/bin/env python3
"""类型检查守护（pyright）—— 产品代码与入口脚本的类型错误门禁。

守护域与规则基线写在 `pyproject.toml` 的 `[tool.pyright]`：

  - `include`：`src/python` + `scripts`（产品代码与入口/守护脚本——两者的类型错误
    同样是缺陷，`scripts/` 停顿的历史噪声已清零）
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

  python scripts/check-types.py --changed
    只查「相对 HEAD 变更（含未跟踪）且落在守护域内」的 .py——pre-commit 快车道：
    全量 pyright 约 14s/次，按变更文件查约 2s；变更文件过多或拿不到 git 清单时
    自动回落全量（宁可慢，不漏检）。**CI 与发布门禁始终跑全量**。

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
DEFAULT_TARGETS: tuple[str, ...] = ("src/python", "scripts")

#: 单次输出上限（CI 日志友好；超出时末尾给「其余 N 条」一行）
MAX_REPORTED = 60

#: 守护域前缀（`--changed` 按此过滤变更文件；由 `DEFAULT_TARGETS` 派生，不另写一份域）
GUARDED_PREFIXES: tuple[str, ...] = tuple(f"{target}/" for target in DEFAULT_TARGETS)

#: `--changed` 的变更文件上限：超过即回落全量（pyright 起停固定开销 > 逐文件收益）
MAX_CHANGED_FILES = 25


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


def changed_guarded_files() -> list[str] | None:
    """取「相对 HEAD 变更（含未跟踪）且落在守护域内」的 `.py` 清单。

    Returns:
        变更文件相对路径（升序去重）；无变更返回空列表；git 不可用/命令失败
        返回 None（调用方据此回落全量扫描，宁可慢不漏检）。
    """
    commands = (
        ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD", "--"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    )
    found: set[str] = set()
    for command in commands:
        try:
            proc = subprocess.run(
                command,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None  # 无 git / 无 HEAD：不猜，回落全量
        for line in (proc.stdout or "").splitlines():
            path = line.strip()
            if path.endswith(".py") and path.startswith(GUARDED_PREFIXES):
                found.add(path)
    return sorted(found)


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
    parser.add_argument(
        "--changed",
        action="store_true",
        help="只查相对 HEAD 变更且落在守护域内的 .py（pre-commit 快车道；过多或取不到清单时回落全量）",
    )
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
    if args.changed and not args.paths:
        changed = changed_guarded_files()
        if changed is None:
            targets = list(DEFAULT_TARGETS)  # git 不可用：回落全量
        elif not changed:
            if args.verbose:
                print("[..] 无落在守护域内的变更文件，跳过类型检查")
            return report([], "[OK] 类型检查通过（无 ERROR 级诊断；本次无变更文件）", ci=args.ci)
        elif len(changed) > MAX_CHANGED_FILES:
            targets = list(DEFAULT_TARGETS)  # 变更面过大：全量更划算
        else:
            targets = changed
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
