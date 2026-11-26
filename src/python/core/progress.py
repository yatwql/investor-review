"""进度上报协议：跨层消费的只读接口面。

为什么落在 ``core`` 层：需要进度回调的下层模块（如 ``cache``）若为标注参数而引用
``report.progress.ProgressReporter``，就形成「下层依赖上层」的类型边（`TYPE_CHECKING`
块同样计入分层）。协议定义在最底层后，消费方向一律指向 ``core``；报告层的实现
（``report/progress.py`` 的 ``ProgressReporter`` 及其子类）结构化满足本协议，调用方
直接传入实现即可，无需适配。
"""

from __future__ import annotations

from typing import Protocol


class ProgressReporterProtocol(Protocol):
    """进度上报的最小使用面（只描述下层真正调用的四个渠道方法）。

    返回值与 ``report.progress.ProgressReporter`` 一致：事件序号，无事件通道时为
    ``None``（Web 渠道写 run 缓冲并回传序号，供轮询增量对账）。
    """

    def info(self, msg: str) -> int | None: ...

    def ok(self, msg: str) -> int | None: ...

    def warn(self, msg: str) -> int | None: ...

    def error(self, msg: str) -> int | None: ...
