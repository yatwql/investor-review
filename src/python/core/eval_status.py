"""决策质量回测的入口提示与可选随报告执行（零取数提示 + opt-in 子进程）。

定位：把「什么时候该跑回测、上次跑是几天前」做成**一行可读状态**，并提供一个
**显式开启**的随报告执行入口。默认不跑：回测需要长窗口行情（额外取数、可能触发
限速与重试），结论又是按月积累的慢变量，塞进报告主流程会拖累墙钟并放大失败面。

两条能力各自独立、都不阻塞报告：
  - `format_eval_hint()`：读 `docs/tmp/decision-quality/*.json` 的最新 mtime，给出
    「距上次 N 天 + 命令」；无记录时给首次运行提示。
  - `run_post_eval()`：仅在 CLI 显式传 `--post-eval` 时调用，跑零取数阶段
    （`horizon` / `valuation`，只读账本与缓存），失败只记结果不抛错。

产物仍只落 `docs/tmp/`（git 忽略），不进报告产物、不改生产状态。
"""

from __future__ import annotations

import logging
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Sequence

from src.python.core.constants import PROJECT_ROOT

logger = logging.getLogger("invest")

#: 回测产物目录（与 `scripts/eval-decision-quality.py` 默认 --out 一致）
SUMMARY_DIR = Path(PROJECT_ROOT) / "docs" / "tmp" / "decision-quality"

#: 常用命令（提示语里直接给出，避免用户翻文档）
EVAL_COMMAND = "python scripts/eval-decision-quality.py all"

#: 默认随报告执行的阶段：只选零取数项（决策视界 / 估值口径），长窗口阶段留给人工
DEFAULT_POST_EVAL_STAGES: tuple[str, ...] = ("horizon", "valuation")

#: 子进程超时（秒）：超时即放弃，不影响报告
POST_EVAL_TIMEOUT = 180


def last_eval_days(summary_dir: str | Path | None = None, *, today: date | None = None) -> int | None:
    """距最近一次回测的天数（无产物 → None）。

    Args:
        summary_dir: 产物目录（None 用默认 `docs/tmp/decision-quality`）。
        today: 基准日（测试注入；None 用当天）。
    """
    directory = Path(summary_dir) if summary_dir is not None else SUMMARY_DIR
    if not directory.is_dir():
        return None
    stamps = [path.stat().st_mtime for path in directory.glob("*.json")]
    if not stamps:
        return None
    latest = datetime.fromtimestamp(max(stamps)).date()
    base = today or date.today()
    return max((base - latest).days, 0)


def format_eval_hint(summary_dir: str | Path | None = None, *, today: date | None = None) -> str:
    """一行评测状态提示（无记录 → 首次运行提示）。"""
    days = last_eval_days(summary_dir, today=today)
    if days is None:
        return f"评测：尚无回测产物，可运行 `{EVAL_COMMAND}`"
    return f"评测：距上次回测 {days} 天，可运行 `{EVAL_COMMAND}`"


def run_post_eval(
    stages: Sequence[str] = DEFAULT_POST_EVAL_STAGES,
    *,
    timeout: int = POST_EVAL_TIMEOUT,
    python: str | None = None,
    script: Path | None = None,
) -> dict[str, Any]:
    """随报告执行回测（opt-in）：子进程跑零取数阶段，失败只回报不抛错。

    Args:
        stages: 要执行的阶段名（默认零取数的 horizon / valuation）。
        timeout: 子进程超时（秒）。
        python: 解释器路径（None 用当前解释器，保证与运行环境一致）。
        script: 回测脚本路径（None 用仓库内默认路径）。

    Returns:
        {"ok": bool, "returncode": int | None, "error": str, "tail": str}
    """
    path = script or (Path(PROJECT_ROOT) / "scripts" / "eval-decision-quality.py")
    if not path.exists():
        return {"ok": False, "returncode": None, "error": f"脚本不存在: {path}", "tail": ""}
    cmd = [python or sys.executable, str(path), *stages]
    try:
        proc = subprocess.run(  # noqa: S603 - 固定脚本路径 + 固定阶段白名单，无用户输入拼接
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.info("[评测] 随报告执行失败（不影响报告）：%s", exc)
        return {"ok": False, "returncode": None, "error": f"{type(exc).__name__}: {exc}", "tail": ""}
    tail = "\n".join((proc.stdout or "").strip().splitlines()[-6:])
    ok = proc.returncode == 0
    if not ok:
        logger.info("[评测] 阶段返回非零（%s），不影响报告", proc.returncode)
    return {"ok": ok, "returncode": proc.returncode, "error": "" if ok else (proc.stderr or "").strip(), "tail": tail}


__all__ = [
    "DEFAULT_POST_EVAL_STAGES",
    "EVAL_COMMAND",
    "POST_EVAL_TIMEOUT",
    "SUMMARY_DIR",
    "format_eval_hint",
    "last_eval_days",
    "run_post_eval",
]
