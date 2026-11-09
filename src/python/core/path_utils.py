"""路径原语 —— 「配置/环境变量给的路径按项目根绝对化」的唯一来源。

日志文件路径、缓存目录、数据源凭据路径等处的覆盖值都遵循同一条约定：绝对路径
原样使用，相对路径按项目根解析并 `normpath` 归一（`./` 段、冗余分隔符、空串）。
每处各写一份 ``isabs ? x : join(PROJECT_ROOT, x)`` 时，口径会悄悄分叉——有的归一
有的不归一（`data//cache`、`./logs` 原样落盘），空串有的落成 ``PROJECT_ROOT/`` 有
的落成 ``PROJECT_ROOT``。故收敛到本模块，只依赖 ``core.constants``（零副作用）。
"""

from __future__ import annotations

import os

from src.python.core.constants import PROJECT_ROOT


def resolve_project_path(path: str) -> str:
    """把配置/环境变量给出的路径解析为绝对路径。

    Args:
        path: 待解析路径；可为空串、含 `.` 段或冗余分隔符的相对路径，也可已是绝对路径。

    Returns:
        绝对路径。绝对路径原样返回（不做归一，保留用户写法）；相对路径按项目根拼接后
        归一；空串/纯空白解析为项目根本身。
    """
    value = (path or "").strip()
    if not value:
        return PROJECT_ROOT
    if os.path.isabs(value):
        return value
    return os.path.normpath(os.path.join(PROJECT_ROOT, value))
