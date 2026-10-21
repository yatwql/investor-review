"""发布编排耗时埋点 —— 分步计时与 `logs/release.jsonl` 追加记录。

为什么单独成模块：发布墙钟（prepare / refresh / evolution / gate / publish 各步耗时）
此前只在终端打印、不落盘，整改（结论缓存 / 门禁并行 / bench 并行采集）的效果无法跨
版本对拍——每次都要现场重测。本模块把每步耗时写成一行 JSON：

    {"ts": "2026-01-01T10:00:00+08:00", "command": "gate", "ok": true,
     "elapsed_s": 13.6, "version": "x.y.z-dev",
     "steps": [{"step": "P2 场景回归", "elapsed_s": 13.1}]}

`logs/` 属 git 忽略域（不入仓库、不进 `folders.md` 目录树、无门禁依赖），记录失败一律
降级为 `[!]` 提示，绝不阻断发布——埋点是**观测面**，不是门禁面。

拆分纪律同 `_release/_common.py`：只收显式参数（路径/文本由调用方传入），不读入口
模块的路径常量，保证测试对入口模块属性的重定向始终生效。
"""

from __future__ import annotations

import datetime as _dt
import json
import time
from contextlib import contextmanager
from pathlib import Path


def now_iso() -> str:
    """本地时区 ISO 时间戳（秒精度，含偏移）——便于跨机/跨时区对拍。"""
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


class StepTimer:
    """分步计时器：收集命令内各步耗时，并提供总墙钟。"""

    def __init__(self) -> None:
        self._t0 = time.perf_counter()
        self.steps: list[dict] = []

    @contextmanager
    def step(self, label: str, **extra):
        """`with timer.step("标签"):` —— 退出时记录该步耗时（异常路径同样记录）。"""
        started = time.perf_counter()
        try:
            yield
        finally:
            self.mark_elapsed(label, started, **extra)

    def mark_elapsed(self, label: str, started_at: float, **extra) -> dict:
        """按起点时刻补记一步（用于不便包 `with` 的多分支/早退代码块）。"""
        entry = {"step": label, "elapsed_s": round(time.perf_counter() - started_at, 2), **extra}
        self.steps.append(entry)
        return entry

    def step_seconds(self, label: str) -> float | None:
        """取某步耗时（同名多步取首次）；未记录返回 None。"""
        for entry in self.steps:
            if entry["step"] == label:
                return entry["elapsed_s"]
        return None

    @property
    def total(self) -> float:
        """自计时器创建至今的总墙钟（秒，两位小数）。"""
        return round(time.perf_counter() - self._t0, 2)

    @property
    def steps_total(self) -> float:
        """各步耗时之和（用于直观确认「步内已覆盖大头」）。"""
        return round(sum(entry["elapsed_s"] for entry in self.steps), 2)

    def summary(self) -> str:
        """`步名 1.2s · 步名 0.3s` 形式的一行摘要（无步时为空串）。"""
        return " · ".join(f"{entry['step']} {entry['elapsed_s']:.1f}s" for entry in self.steps)


def build_record(command: str, elapsed_s: float, ok: bool, steps: list[dict] | None = None, version: str = "") -> dict:
    """构造一条耗时记录（字段顺序固定，便于人工扫读与 jq 取值）。"""
    return {
        "ts": now_iso(),
        "command": command,
        "ok": bool(ok),
        "elapsed_s": round(float(elapsed_s), 2),
        "version": version,
        "steps": list(steps or ()),
    }


def append_record(path: Path, record: dict) -> Path:
    """追加一行 JSON 记录（自动建父目录）；返回实际写入路径。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path
