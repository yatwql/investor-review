"""发布预检的本地门禁前置断言 —— 把「进 gate 才发现」前移到 check。

背景（真实事故）：一次发布里 `refresh` 失败 1 次、`gate` 失败 3 次，累计白跑
≈150s 门禁墙钟——根因只有一个：**改完代码只跑了局部测试**（`pytest src/test/scenario`）
就进 gate，未跑全量 `dev-verify`；连带统计快照（`folders.md` 行数）也未同步，
`check-doc-drift` 跟着红。

`release.py check` 的定位是「动手前把所有能便宜查的都查掉」。本模块补两条：

1. **统计快照已同步**：`check-doc-drift --ci` 的统计表核对（纯本地、秒级）——
   测试文件增删后未跑 `test-collect-coverage --update-docs` / `--sync` 会立刻红；
2. **本地全量测试已绿**：`test-runner --mode dev-verify`（≈30s）——它比 gate 的
   verify+regression（≈37s×并行）便宜得多，且失败用例名直接可见。

两条都只在 `--strict-local` 或默认开启时执行；`--no-local-gate` 可跳过
（适合「只检查文档派生」的快速场景）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], root: Path) -> tuple[int, str]:
    """执行子命令，返回 (退出码, 合并输出尾部)。"""
    try:
        proc = subprocess.run(  # noqa: S603 — 固定脚本路径，无 shell
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return (1, f"{cmd[0]} 执行失败：{exc}")
    out = (proc.stdout or "") + (proc.stderr or "")
    return (proc.returncode, out)


def check_doc_snapshot(root: Path) -> tuple[bool, str]:
    """统计快照（folders.md 行数/用例数等）与实测一致。"""
    rc, out = _run([sys.executable, "scripts/check-doc-drift.py", "--ci"], root)
    if rc == 0:
        return (True, "")
    tail = "\n".join(line for line in out.strip().splitlines()[-6:])
    return (
        False,
        "文档统计快照与实测不一致（测试文件增删/计数变更后未同步）\n"
        f"{tail}\n"
        "修法：.venv/bin/python scripts/test-collect-coverage.py --update-docs && "
        ".venv/bin/python scripts/check-doc-drift.py --sync --with-test-count",
    )


def check_local_tests(root: Path) -> tuple[bool, str]:
    """本地 P0 测试门禁（dev-verify）全绿。"""
    rc, out = _run([sys.executable, "scripts/test-runner.py", "--mode", "dev-verify"], root)
    if rc == 0:
        return (True, "")
    failures = [line.strip() for line in out.splitlines() if line.strip().startswith("[ERR]")]
    tail = "\n".join(failures[-8:]) or "\n".join(out.strip().splitlines()[-8:])
    return (
        False,
        "本地测试门禁未通过（gate 必然失败，先在此处修掉）\n"
        f"{tail}\n"
        "修法：.venv/bin/python scripts/test-extract-failures.py 取失败用例名，改完重跑 dev-verify",
    )


__all__ = ["check_doc_snapshot", "check_local_tests"]
