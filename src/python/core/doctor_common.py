"""自检结果的分组常量与构造器 —— `doctor` 与 `doctor_logs` 共用的基座。

定位：这两个模块此前互相 import（`doctor` 末尾导入探针实现、`doctor_logs` 反向 import
`GROUP_*` 与 `_item`），靠「先定义后延迟导入」勉强可用，属脆弱结构。本模块只收两侧都要
用的最小面（分组名字 + 结果构造器），依赖方向因此单向：`doctor_common` ← `doctor_logs` ← `doctor`。

分组名是**用户可见词**（自检输出按组渲染），改动即改观感；顺序由 `doctor.GROUP_ORDER` 持有。
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "GROUP_ENV",
    "GROUP_CONFIG",
    "GROUP_DIRS",
    "GROUP_FEATURES",
    "GROUP_ADAPTER",
    "GROUP_CREDENTIAL",
    "GROUP_NETWORK",
    "GROUP_LOG_CACHE",
]

#: 自检分组名（渲染顺序见 `doctor.GROUP_ORDER`）
GROUP_ENV = "环境"
GROUP_CONFIG = "配置"
GROUP_DIRS = "目录"
GROUP_FEATURES = "功能开关"
GROUP_ADAPTER = "数据源适配"
GROUP_CREDENTIAL = "数据源凭据"
GROUP_NETWORK = "数据源"
GROUP_LOG_CACHE = "日志与缓存"

def _item(group: str, label: str, ok: bool, message: str, *, hint: str = "") -> dict[str, Any]:
    """构造一条自检结果。

    Args:
        hint: 可选的可执行修复建议（「错误即 UX」——不只报错，还告诉用户怎么办）
    """
    return {"group": group, "label": label, "ok": ok, "message": message, "hint": hint}
