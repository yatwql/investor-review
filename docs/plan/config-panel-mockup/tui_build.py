#!/usr/bin/env python3
"""TUI 图样构建器 —— 按样式分别产出两份 HTML，互不混排。

输入：`docs/tmp/tui-frames/tui_frames.json`（由 `tui_capture.py` 采集，git 忽略）
输出：
  `tui.html`          —— 目标设计（variant = proposed / both）
  `tui-current.html`  —— 现有实现（variant = current / both）

ANSI SGR → HTML span 的映射与终端实际配色一致。单帧超过 `MAX_LINES` 行时截断并
给出「共 N 行」提示（完整输出可由重跑采集得到）。

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

MAX_LINES = 52

#: 输出文件 → (标题, 副标题, 收录的变体)
OUTPUTS = {
    "tui.html": (
        "TUI 面板图样 · 目标设计",
        "本文件只含目标设计（[C] 报告章节显隐 / [S] 报告章节内容呈现 / [G] 全局设置 / [G]→[L] LLM 设置），"
        "专项详情为面板内 `?编号` 查询；现有实现见 tui-current.html。",
        ("proposed", "both"),
    ),
    "tui-current.html": (
        "TUI 面板图样 · 现有实现",
        "本文件只含现有实现（四组开关 / 一级直达的指数池与匿名化 / [D] 目录信息 / [D]→[L] 调优参数）；"
        "目标设计见 tui.html。",
        ("current", "both"),
    ),
}

#: 层级导航图（每份图样只放自己那一套）
NAV_TREE = {
    "proposed": """主菜单（一级 · 14 项）
├─ 生成报告      [E] [B] [L] [W]
├─ 数据与查看    [Q] [1] [2] [3]
├─ 配置
│   ├─ [C] 报告章节显隐    二级 · 数字 1-16（顶层章节 5 / LLM 章节 7 / 默认关闭的整章 3 / 关联产物 1）+ 7.1/7.2 子项
│   ├─ [S] 报告章节内容呈现  二级 · 数字 1-20（持仓与交易 4 / 市场与估值 4 / 基金与风格 3 / 事件与摘要 4 / 呈现与交互 2 / 机制与质量 3）
│   ├─ [G] 全局设置        二级 · 数字 1-7 主入口，字母 D/F/O/L/I/A/M 别名
│   │   ├─ [L] LLM 设置         三级 · 数字 1-7 · 0 返回
│   │   │     ├─ 1-6 运行参数        输入新值（范围校验）
│   │   │     └─ 7 多链线路优先级    四级 · 输入两个编号交换
│   │   ├─ [D]/[F]/[O]          持仓信息目录 / 文件名 / 输出目录
│   │   ├─ [I] 对比基准指数     增删 / 重置
│   │   ├─ [A] 持仓匿名化       数字 1-4 选档
│   │   └─ [M] 配置入口地图     只读打印
│   └─ [R] 刷新配置
└─ 诊断与排查    [D]      二级 · 数字 1-4 主入口，字母 L/V/H/T 别名，缺省 T
                ├─ [L] 日志设置（三级 · 数字 1-6）
                ├─ [V] 运行日志
                ├─ [H] 数据源健康历史
                └─ [T] 系统自检（恒上屏；本层缺省项）

键语义：一级＝功能入口；二级＝菜单键（数字主入口 + 字母别名）；三级＝可编辑项编号；?编号＝面板内只读查询（不换层级、不写配置）""",
    "current": """主菜单（一级 · 19 项）
├─ 生成报告      [E] [B] [L] [W]
├─ 数据与查看    [Q] [1] [2] [3]
├─ 配置
│   ├─ [C] 配置报告可选章节    二级 · 数字 1-6（第 6 项为跳转提示）
│   ├─ [S] 配置功能开关        二级 · 数字 1-34 切换；?编号 为面板内只读查询
│   ├─ [I] 管理对比指数池      一级直达 · 增删 / 重置
│   ├─ [A] 配置持仓匿名化      一级直达 · 数字 1-4 选档
│   ├─ [D] 查看配置与目录信息  二级 · 字母键 C/F/O/L/M · 0 返回
│   │   ├─ [H] 持仓信息目录     输入路径
│   │   ├─ [F] 持仓信息文件名   输入名称
│   │   ├─ [O] 报告输出目录     输入路径
│   │   ├─ [L] LLM 调优参数     三级 · 数字 1-6 · 0 返回
│   │   └─ [M] 配置入口地图     只读打印
│   ├─ [M] 配置 LLM 多链线路优先级   一级直达 · 输入两个编号交换
│   └─ [R] 刷新配置
└─ 诊断与排查    [V] [H] [T]

键语义：一级＝功能入口；二级＝菜单键（字母）或开关编号（数字）；三级＝可编辑项编号；?编号＝面板内只读查询（不换层级、不写配置）""",
}

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


def _esc(raw: str) -> str:
    return raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def ansi_to_html(text: str) -> str:
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


def build_frame(frame: dict, variant: str) -> str:
    title = frame["title_proposed"] if variant == "proposed" else frame["title_current"]
    title = title or frame["title_proposed"] or frame["title_current"]
    lines = frame["ansi"].split("\n")
    total = len([ln for ln in lines if SGR_RE.sub("", ln).strip()])
    body = "\n".join(ansi_to_html(ln) for ln in lines[:MAX_LINES])
    more = f'<p class="more">… 共 {total} 行，此处展示前 {MAX_LINES} 行</p>' if total > MAX_LINES else ""
    path = (frame["path_proposed"] if variant == "proposed" else frame["path_current"]) or frame[
        "path_proposed"
    ]
    crumb = f'<p class="crumb">{_esc(path)}</p>' if path else ""
    return (
        f'<section class="screen" id="s-{frame["id"]}">'
        f'<div class="screen-head"><span class="lvl lvl-{frame["level"]}">{frame["level"]}</span>'
        f"<h2>{_esc(title)}</h2></div>"
        f"{crumb}"
        f'<p class="note">{_esc(frame["note"])}</p>'
        f'<pre class="term">{body}</pre>{more}</section>'
    )


def build_nav(frames: list[dict], variant: str) -> str:
    return "\n".join(
        f'<a href="#s-{f["id"]}" class="nav-item"><span class="lvl lvl-{f["level"]}">{f["level"]}</span>'
        f'{_esc((f["title_proposed"] if variant == "proposed" else f["title_current"]) or f["title_proposed"] or f["title_current"])}</a>'
        for f in frames
    )


def main() -> int:
    frames = json.loads(FRAMES.read_text(encoding="utf-8"))
    for filename, (title, subtitle, variants) in OUTPUTS.items():
        variant = "proposed" if "proposed" in variants and filename == "tui.html" else "current"
        selected = [f for f in frames if f["variant"] in variants]
        body = "\n".join(build_frame(f, variant) for f in selected)
        html = (
            TEMPLATE.replace("{{TITLE}}", title)
            .replace("{{SUBTITLE}}", subtitle)
            .replace("{{COUNT}}", str(len(selected)))
            .replace("{{TREE}}", f'<pre class="tree">{NAV_TREE[variant]}</pre>')
            .replace("{{NAV}}", build_nav(selected, variant))
            .replace("{{BODY}}", body)
        )
        out = HERE / filename
        out.write_text(html, encoding="utf-8")
        print(f"写出 {out}（{len(selected)} 屏）")
    return 0


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}}</title>
<style>
:root {
  --bg: #0d1117; --panel: #161b22; --border: #30363d; --text: #c9d1d9; --text-dim: #8b949e;
  --brand: #f0883e; --blue: #79c0ff; --green: #7ee787; --red: #ff7b72; --yellow: #ffd479; --cyan: #76e3ea;
  --font: ui-monospace, "SF Mono", Menlo, Consolas, "Noto Sans Mono CJK SC", monospace;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; font-size: 14px; line-height: 1.7; }
header.top { position: sticky; top: 0; z-index: 5; background: var(--panel);
  border-bottom: 1px solid var(--border); padding: 12px 20px; display: flex; gap: 14px; align-items: baseline; flex-wrap: wrap; }
header.top h1 { font-size: 15px; font-weight: 600; margin: 0; }
header.top .hint { color: var(--text-dim); font-size: 12px; }
.wrap { display: grid; grid-template-columns: 240px 1fr; }
nav { position: sticky; top: 52px; align-self: start; height: calc(100vh - 52px); overflow-y: auto;
  padding: 14px 10px 40px; border-right: 1px solid var(--border); background: var(--panel); }
nav .nav-title { font-size: 11px; color: var(--text-dim); margin: 12px 6px 6px; letter-spacing: .04em; }
.nav-item { display: flex; gap: 8px; align-items: baseline; padding: 4px 8px; border-radius: 6px;
  color: var(--text); text-decoration: none; font-size: 12.5px; }
.nav-item:hover { background: #21262d; }
main { padding: 20px 24px 80px; max-width: 1100px; }
.screen { margin: 0 0 34px; scroll-margin-top: 64px; }
.screen-head { display: flex; gap: 10px; align-items: center; }
.screen-head h2 { font-size: 16px; font-weight: 600; margin: 0; }
.lvl { font-size: 10.5px; padding: 0 5px; border-radius: 4px; white-space: nowrap; border: 1px solid var(--border); color: var(--text-dim); }
.lvl-一级 { color: var(--brand); border-color: #6b3f18; }
.lvl-二级 { color: var(--blue); border-color: #1f4a75; }
.lvl-三级 { color: var(--cyan); border-color: #1d5a63; }
.lvl-面板内 { color: var(--text-dim); border-color: var(--border); }
.lvl-四级 { color: var(--gold, #d2a8ff); border-color: #4a3a6b; }
.note { margin: 2px 0 10px; color: var(--text-dim); font-size: 12px; }
pre.term { margin: 0; padding: 14px 16px; background: #0b0f14; border: 1px solid var(--border); border-radius: 8px;
  overflow-x: auto; font-family: var(--font); font-size: 12.5px; line-height: 1.55; color: var(--text); }
.more { margin: 6px 0 0; font-size: 11.5px; color: var(--text-dim); }
.crumb { margin: 2px 0 2px; font-size: 12px; color: var(--blue); letter-spacing: .01em; }
pre.tree { margin: 0 0 24px; padding: 14px 16px; background: #0f141b; border: 1px solid var(--border);
  border-radius: 8px; font-family: var(--font); font-size: 12.5px; line-height: 1.6; color: var(--text); overflow-x: auto; }
.g { color: var(--green); } .r { color: var(--red); } .y { color: var(--yellow); }
.c { color: var(--cyan); } .b { color: var(--blue); } .o { color: var(--brand); }
.d { color: var(--text-dim); } .bold { font-weight: 600; }
@media (max-width: 900px) {
  .wrap { grid-template-columns: 1fr; }
  nav { position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--border); }
  main { padding: 16px 12px 60px; }
}
</style>
</head>
<body>
<header class="top">
  <h1>{{TITLE}}</h1>
  <span class="hint">{{COUNT}} 屏 · {{SUBTITLE}}</span>
</header>
<div class="wrap">
<nav>
  <div class="nav-title">屏幕清单（按层级）</div>
  {{NAV}}
</nav>
<main>
{{TREE}}
{{BODY}}
</main>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
