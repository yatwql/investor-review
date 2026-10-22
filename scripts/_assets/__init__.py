"""视觉资产维护工具内部实现包（入口 `scripts/make-assets.py`）。

子命令实现分两处：`social_preview.py`（社交预览图绘制/栅格化）与 `svg_check.py`
（README 架构图的几何/像素/文字越界体检）。两者都只在本机手工运行，不进任何门禁。
"""

from __future__ import annotations

import sys
from pathlib import Path

# scripts/ 加入 sys.path：内部模块需 `from _checklib import ...` 等兄弟设施
_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
