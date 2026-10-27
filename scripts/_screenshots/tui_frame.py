"""把「一帧 TUI 屏幕」渲染成 PNG（演示截图用）。

取帧走生产渲染函数（`print_header` + `show_config` + `render_menu`），不经过真实 TTY——
拿到的文本与配色与终端同源，且不含光标控制序列。渲染端解析生产代码实际用到的 SGR 子集
（30-37 / 90-97 / 1 粗体 / 2 淡色 / 0 复位），在深色底上用等宽 CJK 字体逐行绘制。

宽行按终端语义折成多行（真终端会硬折）；折行保留颜色：跨行的配色在续行开头重新打开，
否则第二行会掉回默认前景色。演示工作区与仓库根的绝对路径前缀整体抹掉，上屏读作
`data/holdings` / `reports` 这类相对路径。

依赖：Pillow + 等宽 CJK 字体（Noto Sans Mono CJK）。缺失时以环境缺失退出，不进任何门禁。
"""

from __future__ import annotations

import io
import os
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO_ROOT / "docs" / "tmp" / "screenshots"

FONT_CANDIDATES: tuple[str, ...] = (
    "/usr/share/fonts/opentype/noto/NotoSansMonoCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansMonoCJKsc-Regular.otf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)
FONT_SIZE = 15
LINE_HEIGHT = 24
PADDING = 18
BACKGROUND = (12, 12, 12)
TARGET_COLUMNS = 100

#: 生产代码用到的 SGR 码 → RGB（16 色档位取深色主题常见配色）
PALETTE: dict[int, tuple[int, int, int]] = {
    30: (90, 90, 90),
    31: (231, 76, 60),
    32: (46, 204, 113),
    33: (241, 196, 15),
    34: (52, 152, 219),
    35: (155, 89, 182),
    36: (26, 188, 156),
    37: (224, 224, 224),
    90: (128, 128, 128),
    91: (255, 107, 107),
    92: (80, 250, 123),
    93: (255, 235, 59),
    94: (97, 175, 239),
    95: (255, 121, 198),
    96: (139, 233, 253),
    97: (255, 255, 255),
}
DEFAULT_FG = (224, 224, 224)
SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")


class RenderDependencyError(RuntimeError):
    """渲染依赖缺失（Pillow / 等宽 CJK 字体）。"""


class _TtyStdout:
    """伪 TTY：`ansi_colors` 在 import 期按 `isatty()` 决定颜色常量是否为空串，
    截图必须拿到真实 ANSI 才能渲染出配色（仅取帧期间生效）。"""

    def __init__(self, wrapped: object) -> None:
        self._wrapped = wrapped

    def isatty(self) -> bool:
        return True

    def __getattr__(self, name: str) -> object:
        return getattr(self._wrapped, name)


def display_width(text: str) -> int:
    """文本的终端显示列数（生产实现；延迟导入避免包加载副作用）。"""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from src.python.tui.text_layout import display_width as production_width

    return production_width(text)


def strip_ansi(text: str) -> str:
    """剥离 SGR 序列（仅取可见文本）。"""
    return SGR_RE.sub("", text)


def wrap_line(line: str, columns: int = TARGET_COLUMNS) -> list[str]:
    """按显示宽度折行，保留配色（跨行时在续行开头重新打开当前 SGR）。"""
    if display_width(line) <= columns:
        return [line]
    rows: list[str] = []
    active: list[str] = []
    buffer = ""
    width = 0
    position = 0
    for match in SGR_RE.finditer(line):
        for char in line[position : match.start()]:
            char_width = display_width(char)
            if width + char_width > columns:
                rows.append(buffer)
                buffer = "".join(active)
                width = 0
            buffer += char
            width += char_width
        sequence = match.group(0)
        codes = [int(code) for code in match.group(1).split(";") if code != ""] or [0]
        if 0 in codes:
            active.clear()
        else:
            active.append(sequence)
        buffer += sequence
        position = match.end()
    for char in line[position:]:
        char_width = display_width(char)
        if width + char_width > columns:
            rows.append(buffer)
            buffer = "".join(active)
            width = 0
        buffer += char
        width += char_width
    if buffer:
        rows.append(buffer)
    return rows


def resolve_font() -> str:
    """等宽 CJK 字体路径（缺失即环境缺失）。"""
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    raise RenderDependencyError("未找到等宽 CJK 字体（Noto Sans Mono CJK）。Debian/Ubuntu 可装 fonts-noto-cjk")


def render(text: str, out: Path) -> Path:
    """把一帧文本（含 SGR）绘制成 PNG，返回输出路径。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # pragma: no cover - 环境缺失分支
        raise RenderDependencyError("缺少 Pillow（requirements.txt 已声明）") from exc

    font = ImageFont.truetype(resolve_font(), FONT_SIZE)
    lines: list[str] = []
    for raw in text.expandtabs(4).splitlines():
        lines.extend(wrap_line(raw))
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    # 画布宽度按**字体实测**取（与逐段绘制同一口径）：等宽 CJK 字体里拉丁与全角的
    # 实际步进不同，用「字号 × 固定系数」估算会让长行（如页头状态行）的每个配色段
    # 起点逐段偏移，肉眼看到的是段间一大段空白。
    measured = max((int(probe.textlength(strip_ansi(line), font=font)) for line in lines), default=0)
    image = Image.new(
        "RGB",
        (max(measured + PADDING * 2, 320), LINE_HEIGHT * len(lines) + PADDING * 2),
        BACKGROUND,
    )
    draw = ImageDraw.Draw(image)
    for row, line in enumerate(lines):
        x = PADDING
        y = PADDING + row * LINE_HEIGHT
        foreground = DEFAULT_FG
        position = 0
        for match in SGR_RE.finditer(line):
            chunk = line[position : match.start()]
            if chunk:
                draw.text((x, y), chunk, font=font, fill=foreground)
                x += draw.textlength(chunk, font=font)
            codes = [int(code) for code in match.group(1).split(";") if code != ""] or [0]
            for code in codes:
                if code == 0:
                    foreground = DEFAULT_FG
                elif code == 2:
                    foreground = PALETTE[90]
                elif code in PALETTE:
                    foreground = PALETTE[code]
            position = match.end()
        rest = line[position:]
        if rest:
            draw.text((x, y), rest, font=font, fill=foreground)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    return out


def scrub_paths(text: str, prefixes: tuple[Path, ...]) -> str:
    """抹掉绝对路径前缀（长的先抹，避免仓库根前缀把演示目录截半）。"""
    ordered = sorted({str(prefix.resolve()) for prefix in prefixes}, key=len, reverse=True)
    for prefix in ordered:
        text = text.replace(prefix + os.sep, "").replace(prefix, "")
    return text


def capture_frame(config_path: Path) -> str:
    """采集一帧首页文本（生产渲染函数，非真实 TTY）。"""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    saved_stdout = sys.stdout
    sys.stdout = _TtyStdout(saved_stdout)  # type: ignore[assignment]
    try:
        from src.python.config import set_config_path_override
        from src.python.config._core import _clear_config_cache

        set_config_path_override(str(config_path))
        _clear_config_cache()

        # 页头状态行会显示「上次报告 / 新鲜度 / 数据源失败」——这些读的是本机真实运行状态。
        # 演示帧必须只用演示工作区的状态：把 perf/健康历史路径指向演示目录（演示目录里没有
        # 这些文件 → 显示占位），事后再还原模块属性，不触碰真实 data/state。
        demo_root = config_path.parents[2]
        state_dir = demo_root / "data" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        from src.python.core import perf as _perf

        _orig_perf = _perf._PERF_HISTORY_FILE
        _orig_health = _perf._HEALTH_CHECK_FILE
        _perf._PERF_HISTORY_FILE = str(state_dir / "perf_history.jsonl")
        _perf._HEALTH_CHECK_FILE = str(state_dir / "datasource_health.jsonl")

        from src.python.tui import tui_menu

        tui_menu.refresh_config()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            tui_menu.print_header()
            tui_menu.show_config()
            # 游标落在配置的缺省项：真机首页即此状态，截图须一致
            cached_config = tui_menu.get_config_cache() or {}
            default_key = str(cached_config.get("default_menu_key") or "L")
            selected = tui_menu.index_by_key(default_key)
            tui_menu.render_menu(selected if selected is not None else 0)
        return buffer.getvalue()
    finally:
        sys.stdout = saved_stdout
        try:  # 还原真实状态路径（Demo 帧不得改变本机读取来源）
            _perf._PERF_HISTORY_FILE = _orig_perf
            _perf._HEALTH_CHECK_FILE = _orig_health
        except (NameError, UnboundLocalError):
            pass


def main(argv: list[str] | None = None) -> int:
    """`tui <out.png> [--config PATH] [--text FILE]` 子命令实现。"""
    import argparse

    parser = argparse.ArgumentParser(prog="make-screenshots.py tui", description="把一帧 TUI 首页渲染成 PNG")
    parser.add_argument("output", type=Path, help="输出 PNG 路径")
    parser.add_argument("--config", type=Path, help="配置路径（缺省用演示工作区的配置）")
    parser.add_argument("--text", type=Path, help="改用已有的帧文本文件（跳过取帧）")
    args = parser.parse_args(argv)

    config_path = args.config or (
        REPO_ROOT / "docs" / "tmp" / "screenshots" / "demo" / "data" / "config" / "config.json"
    )
    if args.text is not None:
        text = args.text.read_text(encoding="utf-8")
    else:
        text = capture_frame(config_path.resolve())
    text = scrub_paths(text, (config_path.resolve().parent.parent.parent, REPO_ROOT))
    try:
        rendered = render(text, args.output.resolve())
    except RenderDependencyError as exc:
        print(f"  [ERR] {exc}")
        return 1
    print(f"  [OK] {rendered}")
    return 0
