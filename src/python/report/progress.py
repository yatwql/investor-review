"""进度报告及耗时记录 — 解耦报告模块与 TUI 显示。

报告模块通过 ProgressReporter 接口输出进度消息和错误，
不直接依赖 TUI 或 print()，方便在无终端环境下运行。
"""

from __future__ import annotations

import logging
import time as _time_module
from collections.abc import Callable
from typing import Any

from src.python.core.ansi_colors import CYAN, GREEN, RED, RESET, YELLOW

#: 行情获取进度提示（Excel / HTML / 编排三条路径共用同一句话）
MSG_FETCHING_MARKET = "正在获取行情数据..."
MSG_FETCHING_MARKET_FIRST = "正在获取行情数据（首次耗时较长，后续使用缓存）..."

logger = logging.getLogger("invest")

# ── 模块耗时记录（跨模块共享，供直接使用 Timer() 的场景） ──
timing_records: list[tuple[str, float]] = []


class Timer:
    """简单计时器上下文管理器，记录各模块耗时。

    默认写入模块级 ``timing_records``（供直接使用 Timer() 的调用方）。
    ProgressReporter 子类应通过 ``reporter.timer()`` 获取绑定了实例级
    记录列表的 Timer，避免跨报告生成的数据串扰。
    """

    def __init__(self, label: str, records: list | None = None) -> None:
        self.label = label
        self.records = records if records is not None else timing_records
        self.start: float = 0.0

    def __enter__(self) -> Timer:
        self.start = _time_module.time()
        return self

    def __exit__(self, *args) -> None:
        elapsed = _time_module.time() - self.start
        self.records.append((self.label, elapsed))


# ── 进度报告接口 ─────────────────────────────────────────────


class ProgressReporter:
    """报告进度回调接口。报告模块通过此接口输出进度和错误，不依赖 TUI。

    子类可覆盖各方法自定义输出格式（终端、日志、静默等）。
    """

    def __init__(self) -> None:
        self._errors: list[str] = []
        self._timing_records: list[tuple[str, float]] = []

    def info(self, msg: str) -> None:
        """进行中消息（对应 [..] 前缀）。"""

    def ok(self, msg: str) -> None:
        """成功消息（对应 [OK] 前缀）。"""

    def warn(self, msg: str) -> None:
        """警告消息（对应 [!] 前缀）。"""

    def error(self, msg: str) -> None:
        """错误消息（对应 [ERR] 前缀）。"""

    def add_error(self, msg: str) -> None:
        """记录非致命错误，不影响继续执行。"""
        self._errors.append(msg)
        logger.warning("生成异常: %s", msg)

    def get_errors(self) -> list[str]:
        """返回已记录的错误列表。"""
        return list(self._errors)

    def call_sheet(self, label: str, fn: Callable | None, *args: Any, **kwargs: Any) -> bool:
        """安全调用单页写入函数，记录耗时，失败时记录错误并继续。

        Args:
            label: 页面名称（中文，用于日志/输出）
            fn: 要调用的写入函数（为 None 时视为模块缺失）
            args, kwargs: 传递给 fn 的参数

        Returns:
            True 表示成功，False 表示失败/未调用
        """
        if fn is None:
            self.add_error(f"{label}模块缺失，跳过")
            return False
        with self.timer(label):
            try:
                fn(*args, **kwargs)
                return True
            except Exception:
                self.add_error(f"{label}生成失败（详情请查看日志）")
                logger.exception("%s写入异常", label)
                return False

    def print_timing_summary(self) -> None:
        """输出耗时汇总。默认空实现，子类可覆盖。"""

    def stage_progress(self, perf: Any) -> None:
        """阶段状态行：当前阶段 + 已耗时 + 预计剩余（perf 历史同阶段中位数）。

        所有进度通道（CLI verbose / Web / TUI）继承本单一实现，保证同源文案：
        - ETA 可得且阶段非瞬时 → 输出「阶段」· 已耗时 · 预计剩余
        - 历史不足（ETA 不可得）且已耗时 ≥1s → 仅显示已耗时
        - 无活跃阶段、瞬时阶段（预估剩余 <1s）、预估计算失败 → 静默不输出
        """
        from src.python.core.perf import estimate_stage_eta, format_stage_status

        try:
            status = perf.stage_status()
            if not status:
                return
            eta = estimate_stage_eta(status["phase"], status["elapsed"], report_type=perf.report_type)
            if eta is None and status["elapsed"] < 1.0:
                return
            if eta is not None and eta < 1.0:
                return
            self.info(format_stage_status(status, eta))
        except Exception:
            logger.debug("阶段状态行生成失败，静默降级", exc_info=True)

    def timer(self, label: str) -> Timer:
        """返回绑定了实例级记录的计时器上下文管理器。"""
        return Timer(label, records=self._timing_records)


class SilentProgressReporter(ProgressReporter):
    """静默进度报告器 — 所有消息不输出（默认），适合库调用场景。"""

    pass


class AnnouncingProgressReporter(ProgressReporter):
    """带「开始/完成」播报的进度报告器 — TUI 与 Web 两渠道共用的页签滑轨语义。

    与基类实现的区别仅在文案：调用前 ``info("正在生成…")``、成功后
    ``ok("…生成完成")``、失败走 ``add_error``。文案逐字同源，避免两个
    渠道各写一份后漂移（原先 TUI / Web 各持一份逐字相同的实现）。
    """

    def call_sheet(self, label: str, fn: Callable | None, *args: Any, **kwargs: Any) -> bool:
        if fn is None:
            self.add_error(f"{label}模块缺失，跳过")
            return False
        self.info(f"正在生成{label}...")
        try:
            with self.timer(label):
                fn(*args, **kwargs)
        except Exception:
            self.add_error(f"{label}生成失败（详情请查看日志）")
            logger.exception("%s写入异常", label)
            return False
        self.ok(f"{label}生成完成")
        return True


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
        except Exception:
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
