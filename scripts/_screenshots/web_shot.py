"""无头 Chromium CDP 截图封装（实现在 `cdp_shot.mjs`，需 Node ≥22 内置 WebSocket）。

按「导航 → 可选的文本替换 → 滚动到目标位置 → 截取视口」的次序取图。滚动后再截而不是
截整页，是为让固定侧栏停在视口里（整页截图会把 sticky 元素留在文档顶部）。

浏览器解析次序：`--chrome` 参数 → `CHROME_BIN` 环境变量 → Playwright 下载的 Chromium →
常见系统路径。找不到即环境缺失退出。
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
from pathlib import Path

CDP_SCRIPT = Path(__file__).with_name("cdp_shot.mjs")

#: Playwright 下载的 Chromium（无 playwright 依赖时直接跑二进制）
_PLAYWRIGHT_GLOB = str(Path.home() / ".cache" / "ms-playwright" / "chromium-*" / "chrome-linux64" / "chrome")

#: 常见系统安装位置
_SYSTEM_CANDIDATES: tuple[str, ...] = (
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
)


def resolve_chrome(explicit: str | None = None) -> Path | None:
    """可执行的 Chromium/Chrome 路径；找不到返回 None。"""
    for candidate in (explicit, os.environ.get("CHROME_BIN")):
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    for hit in sorted(glob.glob(_PLAYWRIGHT_GLOB), reverse=True):
        if Path(hit).is_file():
            return Path(hit)
    for candidate in _SYSTEM_CANDIDATES:
        if Path(candidate).is_file():
            return Path(candidate)
    return None


def resolve_node() -> str | None:
    """Node 可执行文件（`cdp_shot.mjs` 需要内置 WebSocket，即 Node ≥22）。"""
    return shutil.which("node")


def build_command(
    url: str,
    output: Path,
    *,
    scroll_y: int | None = None,
    width: int = 1440,
    height: int = 940,
    replace: str = "",
    node: str = "node",
) -> list[str]:
    """`cdp_shot.mjs` 的命令行（位置参数与脚本签名一一对应）。"""
    return [
        node,
        str(CDP_SCRIPT),
        url,
        str(output),
        "-" if scroll_y is None else str(scroll_y),
        str(width),
        str(height),
        replace,
    ]


def run(
    url: str,
    output: Path,
    *,
    scroll_y: int | None = None,
    width: int = 1440,
    height: int = 940,
    replace: str = "",
    chrome: str | None = None,
) -> int:
    """截一张图，返回退出码（0 成功 / 1 环境缺失或截图失败）。"""
    node = resolve_node()
    if node is None:
        print("  [ERR] 未找到 node（需 Node ≥22 内置 WebSocket）")
        return 1
    resolved_chrome = resolve_chrome(chrome)
    if resolved_chrome is None:
        print("  [ERR] 未找到 Chromium/Chrome（用 --chrome 或 CHROME_BIN 指定）")
        return 1
    if not CDP_SCRIPT.is_file():  # pragma: no cover - 打包缺失
        print(f"  [ERR] 缺少 CDP 脚本：{CDP_SCRIPT}")
        return 1
    command = build_command(
        url, output.resolve(), scroll_y=scroll_y, width=width, height=height, replace=replace, node=node
    )
    completed = subprocess.run(
        command,
        env={**os.environ, "CHROME_BIN": str(resolved_chrome)},
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode
