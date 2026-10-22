#!/usr/bin/env python3
"""生成 GitHub Social Preview 图（1200×630 JPG）。

品牌视觉由两栏构成：左卡内嵌 `src/static/owl-mascot.svg`（猫头鹰「守望」+ 夜空底 +
净值曲线栖木），右栏为中文品牌名、英文名、定位句与能力关键词；配色与
`docs/managements/DESIGN.md` 的暗色语义色同源（背景渐变 `#0b1524→#122036→#16283f`、
强调色 `#2E75B6`）。

产物即仓库资产 `src/static/social-preview.jpg`（入库受 git 管控）：改动文案/配色后重跑脚本
即就地刷新该图，提交后由人工上传到仓库 Settings → Social preview。

依赖：`cairosvg`（SVG 栅格化，不入 requirements）与 `Pillow`（JPG 编码，运行期已依赖）。
cairosvg 在无 cairo 系统库的环境装不上，故只在本机手工运行，不进任何门禁。

用法：
  .venv/bin/python scripts/make-social-preview.py                  # 默认写入 src/static/social-preview.jpg
  .venv/bin/python scripts/make-social-preview.py -o /tmp/x.jpg    # 自定义输出路径（不碰入库资产）
  .venv/bin/python scripts/make-social-preview.py --keep-svg       # 保留中间 PNG（同名 .png）

退出码：
  0 — 生成成功
  1 — 依赖缺失（cairosvg / Pillow）或素材文件不可读
"""

from __future__ import annotations

import argparse
import base64
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OWL_SVG = REPO_ROOT / "src" / "static" / "owl-mascot.svg"
DEFAULT_OUTPUT = REPO_ROOT / "src" / "static" / "social-preview.jpg"

WIDTH = 1200
HEIGHT = 630
JPG_QUALITY = 92

#: 猫头鹰卡片在画布上的落位（与 SVG 源 viewBox 440×380 的比例接近，不留形变）
OWL_BOX = {"x": 58, "y": 126, "w": 470, "h": 406}

_INSTALL_HINT = "缺少依赖：cairosvg 用于 SVG 栅格化。安装：.venv/bin/pip install cairosvg"


class RenderDependencyError(RuntimeError):
    """渲染依赖缺失（cairosvg / Pillow）或素材不可读。"""


@dataclass(frozen=True)
class RenderDeps:
    """渲染器依赖面（cairosvg 模块 + Pillow Image 类）。"""

    cairosvg: Any
    image_module: Any


def _load_render_deps() -> RenderDeps:
    """导入渲染依赖；缺失时抛 RenderDependencyError（附安装指引）。"""
    try:
        import cairosvg
        from PIL import Image
    except ImportError as e:  # pragma: no cover - 依赖齐备的环境走不到
        raise RenderDependencyError(f"{_INSTALL_HINT}（{e}）") from e
    return RenderDeps(cairosvg=cairosvg, image_module=Image)


def build_svg(owl_b64: str) -> str:
    """按画布参数拼出整张预览图的 SVG 源（`owl_b64` 为猫头鹰 SVG 的 base64 载荷）。"""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}"
     role="img" aria-label="投资复盘助手 Investor Review">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0b1524"/>
      <stop offset="0.55" stop-color="#122036"/>
      <stop offset="1" stop-color="#16283f"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.30" cy="0.44" r="0.52">
      <stop offset="0" stop-color="#2E75B6" stop-opacity="0.28"/>
      <stop offset="1" stop-color="#2E75B6" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <!-- 背景 -->
  <rect width="{WIDTH}" height="{HEIGHT}" fill="url(#bg)"/>
  <rect width="{WIDTH}" height="{HEIGHT}" fill="url(#glow)"/>

  <!-- 星点（夜空意象，克制分布，避开文字区） -->
  <g fill="#e8f1fb" opacity="0.45">
    <circle cx="96" cy="72" r="2.2"/><circle cx="188" cy="44" r="1.6"/>
    <circle cx="302" cy="90" r="1.8"/><circle cx="420" cy="52" r="2.0"/>
    <circle cx="520" cy="104" r="1.5"/><circle cx="742" cy="66" r="2.2"/>
    <circle cx="866" cy="40" r="1.6"/><circle cx="980" cy="96" r="1.9"/>
    <circle cx="1090" cy="58" r="2.1"/><circle cx="1150" cy="132" r="1.5"/>
    <circle cx="64" cy="248" r="1.6"/><circle cx="1174" cy="300" r="1.8"/>
    <circle cx="700" cy="592" r="1.6"/><circle cx="360" cy="600" r="1.5"/>
    <circle cx="1010" cy="596" r="1.7"/>
  </g>

  <!-- 吉祥物卡片：复用 owl-mascot.svg（夜空底 + 猫头鹰 + 净值曲线栖木） -->
  <image x="{OWL_BOX["x"]}" y="{OWL_BOX["y"]}" width="{OWL_BOX["w"]}" height="{OWL_BOX["h"]}"
         xlink:href="data:image/svg+xml;base64,{owl_b64}"/>

  <!-- 品牌文字块（右栏；右边界 1120，避开收口条） -->
  <g font-family="Noto Sans CJK SC, Noto Sans CJK JP, sans-serif">
    <text x="596" y="232" font-size="76" font-weight="700" fill="#f4f8fc"
          letter-spacing="2">投资复盘助手</text>

    <text x="600" y="292" font-size="32" font-weight="600" fill="#6fa8dc"
          letter-spacing="6">INVESTOR REVIEW</text>

    <!-- 分隔线 -->
    <rect x="600" y="326" width="92" height="4" rx="2" fill="#2E75B6"/>
    <rect x="704" y="326" width="168" height="4" rx="2" fill="#2E75B6" opacity="0.32"/>

    <!-- 一句话定位 -->
    <text x="600" y="392" font-size="29" fill="#cfe0f2">本地优先的投资分析引擎</text>

    <!-- 能力关键词（两行，避免溢出） -->
    <text x="600" y="452" font-size="24" fill="#8fa9c4" letter-spacing="1">行情 · 穿透 · 基金评级</text>
    <text x="600" y="492" font-size="24" fill="#8fa9c4" letter-spacing="1">量化风控 · LLM 智囊团</text>
  </g>

  <!-- 右侧单一强调色收口条 -->
  <rect x="1156" y="126" width="8" height="406" rx="4" fill="#2E75B6" opacity="0.5"/>
</svg>
'''


def compose_preview(owl_bytes: bytes) -> str:
    """把猫头鹰素材编码进画布模板，返回完整 SVG 源文本。"""
    return build_svg(base64.b64encode(owl_bytes).decode("ascii"))


def render_jpeg(svg_text: str, output: Path, deps: RenderDeps, *, keep_png: bool = False) -> tuple[int, int]:
    """栅格化 SVG 并编码为 JPG，返回成品像素尺寸。"""
    output.parent.mkdir(parents=True, exist_ok=True)
    png_path = output.with_suffix(".png")
    deps.cairosvg.svg2png(
        bytestring=svg_text.encode("utf-8"),
        write_to=str(png_path),
        output_width=WIDTH,
        output_height=HEIGHT,
    )
    image = deps.image_module.open(png_path).convert("RGB")
    image.save(output, "JPEG", quality=JPG_QUALITY, optimize=True, progressive=True)
    size = image.size
    image.close()
    if not keep_png:
        png_path.unlink(missing_ok=True)
    return size


def main(argv: list[str] | None = None) -> int:
    """命令行入口：读素材 → 拼画布 → 栅格化 → 落 JPG。"""
    parser = argparse.ArgumentParser(description="生成 GitHub Social Preview（1200×630 JPG）")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT, help="输出 JPG 路径")
    parser.add_argument("--keep-svg", action="store_true", help="保留中间 PNG（与输出同名）")
    args = parser.parse_args(argv)

    try:
        deps = _load_render_deps()
    except RenderDependencyError as e:
        print(f"  [ERR] {e}")
        return 1

    try:
        owl_bytes = OWL_SVG.read_bytes()
    except OSError as e:
        print(f"  [ERR] 素材不可读：{OWL_SVG}（{e}）")
        return 1

    output = args.output if args.output.is_absolute() else (Path.cwd() / args.output)
    width, height = render_jpeg(compose_preview(owl_bytes), output, deps, keep_png=args.keep_svg)
    print(f"  [OK] 已生成 {output}（{width}×{height}，{output.stat().st_size / 1024:.1f} KB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
