#!/usr/bin/env python3
"""视觉资产维护工具（`src/static/`）：社交预览图生成 + README 架构图渲染体检。

两个子工具共用同一入口，因为它们同属「仓库视觉资产的造与检」且依赖同类（可选 Pillow /
cairosvg），都不参与门禁、只在本机手工运行：

  social-preview                         生成 GitHub 社交预览图（1200×630 JPG）
  svg-geom <svg…>                        几何审查：文本越界/贴边/重叠（纯标准库）
  svg-pixel <png> <scale> <card_r> <y0> <y1> <margin>
                                         像素审查：副标题区域亮像素越出卡片右缘（需 Pillow）
  svg-text-overflow <png> <scale> <card_r> <y0> <y1> <margin>
                                         像素审查：文字色像素越出卡片右缘（需 Pillow）

用法：
  .venv/bin/python scripts/make-assets.py social-preview              # 就地刷新 src/static/social-preview.jpg
  .venv/bin/python scripts/make-assets.py svg-geom src/static/*.svg   # 架构图几何审查
  .venv/bin/python scripts/make-assets.py --ci svg-geom src/static/*.svg  # CI 模式：仅输出 文件:描述

退出码：
  0 — 通过 / 生成成功
  1 — 环境缺失（svg-pixel / svg-text-overflow 需 Pillow；social-preview 需 cairosvg）
  2 — 发现越界/重叠/对齐问题
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/ 与内部包导入面

from _assets import social_preview, svg_check  # noqa: E402

#: 子命令 → svg 体检内部子命令名（入口前缀 `svg-` 仅作分组）
_SVG_SUBCOMMANDS = {
    "svg-geom": "geom",
    "svg-pixel": "pixel",
    "svg-text-overflow": "text-overflow",
}

_HELP = __doc__ or ""


def main(argv: list[str] | None = None) -> int:
    """按子命令分发；未知子命令打印用法并返回 2。"""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(_HELP)
        return 0
    command = next((a for a in args if not a.startswith("-")), "")
    if command == "social-preview":
        return social_preview.main([a for a in args if a != command])
    if command in _SVG_SUBCOMMANDS:
        return svg_check.main([_SVG_SUBCOMMANDS[command] if a == command else a for a in args])
    print(f"  [ERR] 未知子命令：{command or '(空)'}")
    print(_HELP)
    return 2


if __name__ == "__main__":
    sys.exit(main())
