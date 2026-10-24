"""JSON 注释剥离 — 再导出 ``core/json_comments``（配置包既有导入面）。

实现位于叶子模块 ``core/json_comments.py``：``core/logger.py`` 与计价等 core 级
读取方无需导入 ``config`` 包，避免向上依赖成环。配置包内部继续使用
``_comments._strip_json_comments`` / ``strip_json_comments`` 两个名字。
"""

from __future__ import annotations

from src.python.core.json_comments import loads, strip_json_comments

#: 配置包内部沿用的私有别名（与 ``strip_json_comments`` 同一函数）
_strip_json_comments = strip_json_comments

__all__ = ["strip_json_comments", "_strip_json_comments", "loads"]
