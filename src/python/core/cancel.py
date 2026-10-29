"""协作式取消：令牌 + 阶段边界信号。

取消语义（与硬中断的区别写在设计里）：置位令牌后**不打断进行中的请求/写盘**，
而是在下一个阶段边界抛 :class:`StageCancelled` 让生成流程有序收尾——已完成阶段
的产物与缓存全部保留，未完成部分由 ``run_integrity.handle_interruption`` 清理。

为什么落在 ``core`` 层：令牌要同时被 ``core.perf``（阶段边界检查）与渠道层使用；
放在 ``report`` 下会让基础设施反向依赖报告层。
"""

from __future__ import annotations

import threading


class CancelToken:
    """协作式取消令牌（线程安全，可跨阶段轮询）。

    Attributes:
        reason: 取消原因（面向用户的短语，如「用户按 q」）。
    """

    __slots__ = ("_event", "reason")

    def __init__(self, reason: str = "用户取消") -> None:
        self._event = threading.Event()
        self.reason = reason

    @property
    def cancelled(self) -> bool:
        """是否已被置位（调用方在每个阶段边界轮询）。"""
        return self._event.is_set()

    def cancel(self, reason: str | None = None) -> None:
        """置位令牌（幂等；重复调用不覆盖首个原因）。"""
        if self._event.is_set():
            return
        if reason:
            self.reason = reason
        self._event.set()

    def reset(self) -> None:
        """复位令牌（同一会话内复用一次运行上下文时用）。"""
        self._event.clear()


class StageCancelled(Exception):
    """阶段边界上的取消信号（由 ``PerfCollector.start`` 抛出）。

    不是 ``BaseException``：渠道层的 ``except Exception`` 可以捕获它，但正常路径
    应由编排层显式捕获并走中断收口——被中途某处 ``except Exception`` 吞掉时，
    取消会推迟到下一阶段边界生效（协作式取消的可接受降级）。
    """

    def __init__(self, reason: str = "用户取消") -> None:
        super().__init__(reason)
        self.reason = reason


def token_of(reporter: object) -> CancelToken | None:
    """从进度报告器取取消令牌（非令牌对象一律视为「不可取消」）。

    渠道层把令牌挂在 reporter 上，生成路径经 ``PerfCollector`` 使用。取用点统一走
    本函数而不是裸 ``getattr``：测试里的替身（MagicMock 等）任何属性都存在且为真，
    裸取会得到一个「永远已取消」的假令牌，让生成在首个阶段边界直接中止。
    """
    token = getattr(reporter, "cancel_token", None)
    return token if isinstance(token, CancelToken) else None
