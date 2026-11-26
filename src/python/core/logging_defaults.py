"""日志运行配置的缺省值表 — 唯一事实位（`config/_logging.py` 与 `core/logger.py` 共用）。

放 core 层而非 config 层：`core/logger.py` 在进程启动时就要读到日志缺省值，而 core
不得依赖 config 包（叶子模块边界，见 `docs/managements/technical.md`「配置读取」与
`src/test/unit/core/test_json_comments.py` 的导入边界守卫）。config 侧
`config/_logging.py` 从这里 re-export，于是「启动读取」与「面板校验/保存」看到的是
同一份默认值，不再各自维护一份同值镜像。

纯常量模块：不导入任何业务包。
"""

from __future__ import annotations

from typing import Any

#: 日志级别枚举（文件/控制台）；查看器另接受 ALL
LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
VIEWER_LEVELS: tuple[str, ...] = (*LEVELS, "ALL")

#: logger.json 的扁平缺省值（键与配置面板字段一一对应）
DEFAULTS: dict[str, Any] = {
    "path": "logs/app.log",
    "level": "INFO",
    "max_bytes": 10 * 1024 * 1024,
    "backup_count": 5,
    "console_level": "INFO",
    "console_color": True,
    "viewer_level": "INFO",
    "tail_lines": 500,
}

#: 整数项合法区间（保存拒绝与加载回落共用）
RANGES: dict[str, tuple[int, int]] = {
    "max_bytes": (1024, 1024 * 1024 * 1024),
    "backup_count": (0, 50),
    "tail_lines": (50, 10000),
}
