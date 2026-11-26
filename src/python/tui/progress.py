"""TUI 进度报告器与长任务状态条接线（TUI 层专有，报告层不得反向依赖）。

从 `report/progress.py` 迁出：`TuiProgressReporter` 依赖 `tui/live_status` 的状态条，
若继续留在 report 层会形成「报告层 → 交互层」的反向依赖。报告层只保留渠道无关的
`ProgressReporter` / `AnnouncingProgressReporter`，TUI 专属格式化与状态条在此实现。
"""

from __future__ import annotations

import logging
from typing import Any

from src.python.core.ansi_colors import CYAN, GREEN, RED, RESET, YELLOW
from src.python.report.progress import AnnouncingProgressReporter

logger = logging.getLogger("invest")


class TuiProgressReporter(AnnouncingProgressReporter):
    """终端进度报告器 — 将进度消息格式化为 [..]/[OK]/[ERR]/[!] 前缀输出。

    ``live=True`` 时额外启用长任务状态条（单行原地刷新）：阶段状态改由状态条承载，
    不再逐行追加；落地行（``[OK]/[!]/[ERR]``）打印前后自动挂起/恢复状态条，两者
    不会互相覆盖。仅 TTY 生效，非 TTY / ``TUI_PLAIN`` 下行为与未启用时逐字节一致。

    状态条只在阶段切换时刷新一帧，写明当前阶段与中断方式（``Ctrl+C``）；不启后台线程、
    不读 stdin。
    """

    def __init__(self, *, live: bool = False) -> None:
        super().__init__()
        self._errors: list[str] = []
        self._bar: Any = None
        self._last_perf: Any = None
        if live:
            self._start_live_status()

    # ── 状态条生命周期 ──

    def _start_live_status(self) -> None:
        """启用状态条（仅 TTY）。"""
        from src.python.tui.live_status import LiveStatusBar

        # 刻意不启后台线程、不切 terminal 模式、不读 stdin：后台读键会与生成前的
        # 交互提示抢输入，cbreak 泄漏会让终端失去回显——与该行的收益不成比例。
        if LiveStatusBar.supported():
            self._bar = LiveStatusBar()

    def _draw(self) -> None:
        """按当前阶段刷新状态条（只报阶段，不猜剩余时间）。"""
        if self._bar is None or self._last_perf is None:
            return
        from src.python.tui.live_status import status_bar_text

        try:
            status = self._last_perf.stage_status()
            if not status:
                return
            self._bar.update(status_bar_text(str(status["phase"]), hint=self._bar.cancel_hint))
        except Exception:  # noqa: BLE001 — [tui] 状态条绘制失败，已忽略
            logger.debug("[tui] 状态条绘制失败，已忽略", exc_info=True)

    def close(self) -> None:
        """收尾：清掉状态条（幂等；生成结束与异常路径都可调用）。"""
        if self._bar is not None:
            self._bar.close()
            self._bar = None

    def stage_progress(self, perf: Any) -> None:
        """阶段状态：状态条启用时改由状态条承载，否则透传基类逐行输出。"""
        if self._bar is None:
            super().stage_progress(perf)
            return
        self._last_perf = perf
        self._draw()

    def _emit(self, line: str) -> None:
        """落地行输出（打印前后挂起/恢复状态条，避免鬼影行）。"""
        if self._bar is not None:
            self._bar.suspend()
        print(line)
        if self._bar is not None:
            self._bar.resume()

    def info(self, msg: str) -> None:
        self._emit(f"  {CYAN}[..]{RESET} {msg}")

    def ok(self, msg: str) -> None:
        self._emit(f"  {GREEN}[OK]{RESET} {msg}")

    def warn(self, msg: str) -> None:
        self._emit(f"  {YELLOW}[!]{RESET} {msg}")

    def error(self, msg: str) -> None:
        self._emit(f"  {RED}[ERR]{RESET} {msg}")

    def add_error(self, msg: str) -> None:
        self._errors.append(msg)
        logger.warning("生成异常: %s", msg)

    def get_errors(self) -> list[str]:
        return list(self._errors)

    def print_timing_summary(self) -> None:
        """输出本次运行时各模块耗时排行。"""
        records = self._timing_records
        if not records:
            return
        # 合并同名 label
        merged: dict[str, float] = {}
        for label, t in records:
            merged[label] = merged.get(label, 0.0) + t
        total = sum(merged.values())
        print()
        print(f"  ┌{'─' * 48}┐")
        print(f"  │  ⏱ 模块耗时排行（总计 {total:.1f}s）{' ' * 17}│")
        print(f"  ├{'─' * 48}┤")
        sorted_records = sorted(merged.items(), key=lambda x: -x[1])
        for label, t in sorted_records:
            pct = t / total * 100 if total > 0 else 0
            bar_len = int(pct / 100 * 24)
            bar = "█" * bar_len + "░" * (24 - bar_len)
            print(f"  │ {label:<18s} {t:>6.1f}s {pct:>5.1f}% {bar} │")
        print(f"  └{'─' * 48}┘")
        records.clear()

    def print_error_summary(self) -> None:
        """如果存在错误，在终端输出汇总。"""
        if not self._errors:
            return
        print("\n  [!] 以下模块遇到问题（不影响已有结果）:")
        for e in self._errors:
            print(f"    - {e}")
        self._errors.clear()
