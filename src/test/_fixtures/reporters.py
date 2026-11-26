"""报告进度通道（`report.progress.ProgressReporter`）的共享测试替身。

报告链路对进度通道的依赖是「只播报、不回流数据」，因此各测试只需要两种替身：
**记录型**（断言播报口径）与**静默型**（用例不关心播报内容）。此前每个测试文件
各写一份，接口随用随加导致同一概念多个拼写（`warnings` / `warns()` / `calls`），
本模块按现有实现的并集收敛为一份。

接口约定：
  - ``messages``：按 ``(级别, 文案)`` 录制全部渠道调用，顺序即真实播报顺序；
  - ``infos`` / ``oks`` / ``warns`` / ``errors``：同一批记录的按级视图（只断言
    某一级时用，避免在用例里手写过滤）；
  - ``levels(level)``：按级别过滤的通用入口（非四渠道级别也可查）；
  - ``raise_on_info`` / ``raise_on_warn``：让对应渠道抛错，用于验证「播报失败
    不得中断主链路」这类降级契约（其余渠道照常记录）；
  - ``call_sheet`` / ``add_error`` / ``stage_progress`` / ``print_timing_summary``
    继承基类实现，``add_error`` 额外落一条 ``error`` 记录（错误摘要可从 ``errors`` 读）。
"""

from __future__ import annotations

from src.python.report.progress import ProgressReporter


class RecordingReporter(ProgressReporter):
    """记录各级播报内容的进度通道替身。"""

    def __init__(self, *, raise_on_info: bool = False, raise_on_warn: bool = False) -> None:
        super().__init__()
        self.messages: list[tuple[str, str]] = []
        self._raise_on_info = raise_on_info
        self._raise_on_warn = raise_on_warn

    def info(self, msg: str) -> int | None:
        if self._raise_on_info:
            raise RuntimeError("reporter.info 故障")
        self.messages.append(("info", msg))
        return None

    def ok(self, msg: str) -> int | None:
        self.messages.append(("ok", msg))
        return None

    def warn(self, msg: str) -> int | None:
        if self._raise_on_warn:
            raise RuntimeError("reporter.warn 故障")
        self.messages.append(("warn", msg))
        return None

    def error(self, msg: str) -> int | None:
        self.messages.append(("error", msg))
        return None

    def add_error(self, msg: str) -> None:
        """记录错误：既有 ``error`` 播报记录，也进基类的错误摘要（`get_errors`）。"""
        self.messages.append(("error", msg))
        self._errors.append(msg)

    def levels(self, level: str) -> list[str]:
        """按级别取文案（``level`` 为 ``info`` / ``ok`` / ``warn`` / ``error``）。"""
        return [msg for lvl, msg in self.messages if lvl == level]

    @property
    def infos(self) -> list[str]:
        return self.levels("info")

    @property
    def oks(self) -> list[str]:
        return self.levels("ok")

    @property
    def warns(self) -> list[str]:
        return self.levels("warn")

    @property
    def errors(self) -> list[str]:
        return self.levels("error")


class SilentReporter(ProgressReporter):
    """全空操作的进度通道替身（用例不关心播报内容时用，不记录、不输出）。"""
