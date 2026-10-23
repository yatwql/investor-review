#!/usr/bin/env python3
"""TUI 图样构建器 —— 把采集到的 ANSI 帧转成自包含 HTML 图样。

输入：`docs/tmp/tui-frames/tui_frames.json`（由 `tui_capture.py` 采集，git 忽略）
输出：`docs/plan/config-panel-mockup/tui.html`（自包含，无外部依赖）

ANSI SGR → HTML span 的映射与终端实际配色一致（tui/ansi_colors + switch_panel 取值）。
单帧超过 `MAX_LINES` 行时截断并给出「共 N 行」提示（完整输出仍可由重跑采集得到）。

用法::

    .venv/bin/python docs/plan/config-panel-mockup/tui_build.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FRAMES = REPO / "docs" / "tmp" / "tui-frames" / "tui_frames.json"
OUT = HERE / "tui.html"

MAX_LINES = 52

#: SGR 码 → CSS 类（颜色取真实终端语义：绿=开、红=关、黄=告警、蓝=结构、橙=品牌、暗=次要）
SGR_CLASS = {
    "92": "g",
    "91": "r",
    "93": "y",
    "96": "c",
    "94": "b",
    "38;5;208": "o",
    "2": "d",
    "1": "bold",
    "0": "",
}

SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")


def ansi_to_html(text: str) -> str:
    """把一行里的 SGR 序列转成 `<span class=…>`（转义其余字符）。"""
    out: list[str] = []
    stack: list[str] = []
    pos = 0
    for match in SGR_RE.finditer(text):
        out.append(_esc(text[pos : match.start()]))
        pos = match.end()
        code = match.group(1)
        cls = SGR_CLASS.get(code)
        if code in ("0", ""):
            while stack:
                out.append("</span>")
                stack.pop()
        elif cls:
            out.append(f'<span class="{cls}">')
            stack.append(cls)
    out.append(_esc(text[pos:]))
    while stack:
        out.append("</span>")
        stack.pop()
    return "".join(out)


def _esc(raw: str) -> str:
    return raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_frame(frame: dict) -> str:
    lines = [ln for ln in frame["ansi"].split("\n")]
    total = len([ln for ln in lines if SGR_RE.sub("", ln).strip()])
    kept = lines[:MAX_LINES]
    body = "\n".join(ansi_to_html(ln) for ln in kept)
    more = (
        f'<p class="more">… 共 {total} 行，此处展示前 {MAX_LINES} 行</p>' if total > MAX_LINES else ""
    )
    return (
        f'<section class="screen" id="s-{frame["id"]}" data-level="{frame["level"]}">'
        f'<div class="screen-head"><span class="lvl lvl-{frame["level"]}">{frame["level"]}</span>'
        f'<h2>{_esc(frame["title"])}</h2></div>'
        f'<p class="note">{_esc(frame["note"])}</p>'
        f'<pre class="term">{body}</pre>{more}</section>'
    )


def build_nav(frames: list[dict]) -> str:
    items = []
    for f in frames:
        items.append(
            f'<a href="#s-{f["id"]}" class="nav-item" data-level="{f["level"]}">'
            f'<span class="lvl lvl-{f["level"]}">{f["level"]}</span>{_esc(f["title"])}</a>'
        )
    return "\n".join(items)


def main() -> int:
    frames = json.loads(FRAMES.read_text(encoding="utf-8"))
    body = "\n".join(build_frame(f) for f in frames)
    html = TEMPLATE.replace("{{NAV}}", build_nav(frames)).replace("{{BODY}}", body)
    html = html.replace("{{COUNT}}", str(len(frames)))
    OUT.write_text(html, encoding="utf-8")
    print(f"写出 {OUT}（{len(frames)} 屏，{len(html)} 字符）")
    return 0


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TUI 面板图样 · 全层级（真实渲染取样）</title>
<style>
:root {
  --bg: #0d1117;
  --panel: #161b22;
  --border: #30363d;
  --text: #c9d1d9;
  --text-dim: #8b949e;
  --brand: #f0883e;
  --blue: #79c0ff;
  --green: #7ee787;
  --red: #ff7b72;
  --yellow: #ffd479;
  --cyan: #76e3ea;
  --font: ui-monospace, "SF Mono", Menlo, Consolas, "Noto Sans Mono CJK SC", monospace;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  font-size: 14px; line-height: 1.7;
}
header.top {
  position: sticky; top: 0; z-index: 5; background: var(--panel);
  border-bottom: 1px solid var(--border); padding: 12px 20px;
  display: flex; gap: 14px; align-items: baseline; flex-wrap: wrap;
}
header.top h1 { font-size: 15px; font-weight: 600; margin: 0; }
header.top .hint { color: var(--text-dim); font-size: 12px; }
.wrap { display: grid; grid-template-columns: 240px 1fr; gap: 0; }
nav {
  position: sticky; top: 52px; align-self: start; height: calc(100vh - 52px);
  overflow-y: auto; padding: 14px 10px 40px; border-right: 1px solid var(--border);
  background: var(--panel);
}
nav .nav-title { font-size: 11px; color: var(--text-dim); margin: 12px 6px 6px; letter-spacing: .04em; }
.nav-item {
  display: flex; gap: 8px; align-items: baseline; padding: 4px 8px; border-radius: 6px;
  color: var(--text); text-decoration: none; font-size: 12.5px;
}
.nav-item:hover { background: #21262d; }
main { padding: 20px 24px 80px; max-width: 1100px; }
.screen { margin: 0 0 34px; scroll-margin-top: 64px; }
.screen-head { display: flex; gap: 10px; align-items: center; }
.screen-head h2 { font-size: 16px; font-weight: 600; margin: 0; }
.lvl {
  font-size: 10.5px; padding: 0 5px; border-radius: 4px; white-space: nowrap;
  border: 1px solid var(--border); color: var(--text-dim);
}
.lvl-一级 { color: var(--brand); border-color: #6b3f18; }
.lvl-二级 { color: var(--blue); border-color: #1f4a75; }
.lvl-三级 { color: var(--cyan); border-color: #1d5a63; }
.note { margin: 2px 0 10px; color: var(--text-dim); font-size: 12px; }
pre.term {
  margin: 0; padding: 14px 16px; background: #0b0f14;
  border: 1px solid var(--border); border-radius: 8px; overflow-x: auto;
  font-family: var(--font); font-size: 12.5px; line-height: 1.55; color: var(--text);
}
.more { margin: 6px 0 0; font-size: 11.5px; color: var(--text-dim); }
.g { color: var(--green); }
.r { color: var(--red); }
.y { color: var(--yellow); }
.c { color: var(--cyan); }
.b { color: var(--blue); }
.o { color: var(--brand); }
.d { color: var(--text-dim); }
.bold { font-weight: 600; }
@media (max-width: 900px) {
  .wrap { grid-template-columns: 1fr; }
  nav { position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--border); }
  main { padding: 16px 12px 60px; }
}
</style>
</head>
<body>
<header class="top">
  <h1>TUI 面板图样 · 全层级</h1>
  <span class="hint">{{COUNT}} 屏，均为真实处理器渲染取样（等宽字体 + 真实 ANSI 配色）；文件选择类屏幕取到列表即中止，不生成报告、不写配置。</span>
</header>
<div class="wrap">
<nav>
  <div class="nav-title">屏幕清单（一级 → 二级 → 三级）</div>
  {{NAV}}
</nav>
<main>
{{BODY}}
</main>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
