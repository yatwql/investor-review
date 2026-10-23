#!/usr/bin/env python3
"""TUI 图样采集器 —— 两套样式分别采集：`现有实现` 与 `目标设计`，互不混排。

每屏在独立进程与独立伪终端里跑真实处理器（108 列、真实 ANSI 配色），
按脚本送键后整屏取回。产出 `docs/tmp/tui-frames/tui_frames.json`（git 忽略），
由 `tui_build.py` 分别生成 `tui.html`（目标设计）与 `tui-current.html`（现有实现）。

变体归属：
  ``current``  —— 仅现有实现（如 `[D]` 二级、四组开关面板）
  ``proposed`` —— 仅目标设计（如 `[G]` 二级、五组开关面板）
  ``both``     —— 版面两套一致，仅入口键不同（标题按变体切换）

只读纪律：文件选择类屏幕取到列表后即 Ctrl+C 中止；不清缓存、不生成报告、不写配置。

用法::

    .venv/bin/python docs/plan/config-panel-mockup/tui_capture.py
"""

from __future__ import annotations

import fcntl
import json
import os
import pty
import re
import select
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
COLS = 108
LINES = 60

#: (id, 层级, 变体, 现有标题, 目标标题, 取数模式, 送键, 说明)
SCREENS: list[tuple[str, str, str, str, str, str, str, str]] = [
    # ── 一级主菜单 ──
    (
        "main",
        "一级",
        "current",
        "主菜单（19 项，配置组七项）",
        "",
        "main",
        "",
        "配置组含 [M] LLM 多链线路、[I] 对比指数池、[A] 匿名化、[D] 目录信息",
    ),
    (
        "main_proposed",
        "一级",
        "proposed",
        "",
        "主菜单（16 项，配置组四项）",
        "main_proposed",
        "",
        "配置组 P/S/G/R；线路、运行参数、指数池、匿名化归于 [G] 二级",
    ),
    # ── 功能开关面板 ──
    (
        "switches",
        "二级",
        "current",
        "功能开关面板（四组）",
        "",
        "switches",
        "0\r",
        "1-7 标准 LLM 模块 + 8-34 功能开关：呈现 / 分析 / 独立 / 机制",
    ),
    (
        "switches_proposed",
        "二级",
        "proposed",
        "",
        "功能开关面板（五组）",
        "switches_proposed",
        "0\r",
        "分析增强 8-21 / 独立章节 22-26 / 呈现 27 / 机制 28-32 / LLM 增强 33-34",
    ),
    (
        "switch_detail",
        "三级",
        "both",
        "功能开关 · 单项详情（`?编号`）",
        "功能开关 · 单项详情（`?编号`）",
        "switches",
        "?10\r\x03",
        "只读信息面：说明 / 分组 / 存储位置 / 当前值 vs 出厂默认",
    ),
    # ── 配置分组二级 ──
    (
        "dmenu",
        "二级",
        "current",
        "配置与目录信息子菜单（[D] 二级，5 项）",
        "",
        "dmenu",
        "0\r",
        "[C] 目录 / [F] 文件名 / [O] 输出目录 / [L] LLM 调优 / [M] 入口地图",
    ),
    (
        "g_menu_proposed",
        "二级",
        "proposed",
        "",
        "全局设置子菜单（[G] 二级，7 项）",
        "g_menu_proposed",
        "0\r",
        "增 [I] 对比基准指数、[A] 持仓匿名化；提示覆盖 C/F/O/L/I/A/M",
    ),
    # ── LLM 设置三级 ──
    (
        "d_tuning",
        "三级",
        "current",
        "LLM 调优参数（[D]→[L]，6 项）",
        "",
        "tuning",
        "0\r0\r",
        "6 个运行参数，取值范围与说明由共享白名单下发",
    ),
    (
        "d_llm_proposed",
        "三级",
        "proposed",
        "",
        "LLM 设置（[G]→[L]，7 项）",
        "d_llm_proposed",
        "0\r",
        "6 个运行参数 + 第 7 项「多链线路优先级」入口；行尾给线路条数与链首",
    ),
    # ── 目录与索引（版面一致，入口键不同）──
    (
        "d_map",
        "三级",
        "both",
        "配置入口地图（[D]→[M]）",
        "配置入口地图（[G]→[M]）",
        "dmenu",
        "M\r0\r",
        "只读索引：各配置项在哪个菜单键下",
    ),
    (
        "d_dir",
        "三级",
        "both",
        "持仓信息目录（[D]→[C]）",
        "持仓信息目录（[G]→[C]）",
        "dir",
        "\x03",
        "目录列表选择，取到首屏即中止",
    ),
    (
        "d_file",
        "三级",
        "both",
        "持仓信息文件名（[D]→[F]）",
        "持仓信息文件名（[G]→[F]）",
        "filename",
        "\x03",
        "目录内 .xlsx 列表选择",
    ),
    (
        "d_out",
        "三级",
        "both",
        "报告输出目录（[D]→[O]）",
        "报告输出目录（[G]→[O]）",
        "outdir",
        "\x03",
        "输出目录切换（含恢复默认项）",
    ),
    # ── 报告章节 ──
    (
        "boards",
        "二级",
        "current",
        "报告章节取舍（[P]，含指路牌项）",
        "",
        "boards",
        "0\r",
        "5 个顶层章节 + 第 6 项跳转提示 + 底部一行提示",
    ),
    (
        "boards_proposed",
        "二级",
        "proposed",
        "",
        "报告章节取舍（[P]，仅 5 章）",
        "boards_proposed",
        "0\r",
        "5 个顶层章节；面板底部一行提示指向 [S]",
    ),
    # ── 指数池 / 匿名化（版面一致，入口层级不同）──
    (
        "indices",
        "二级",
        "both",
        "对比指数池（[I]）",
        "对比基准指数（[G]→[I]）",
        "indices",
        "0\r",
        "增删基准指数、恢复默认预设",
    ),
    (
        "anon",
        "二级",
        "both",
        "持仓匿名化（[A]）",
        "持仓匿名化（[G]→[A]）",
        "anon",
        "0\r",
        "off / code_display / full_anonymous / summary 四档",
    ),
    (
        "providers",
        "二级",
        "both",
        "LLM 多链线路优先级（[M]）",
        "多链线路优先级（[G]→[L] 第 7 项）",
        "providers",
        "0\r",
        "按 priority 排序的线路清单与调序操作",
    ),
    # ── 其余面板（两套一致）──
    ("cache", "二级", "both", "缓存管理（[3]）", "缓存管理（[3]）", "cache", "B\r", "统计首屏 + 子项 3 清理过期缓存"),
    ("logs", "二级", "both", "运行日志（[V]）", "运行日志（[V]）", "logs", "0\r", "按级别筛选的结构化日志视图"),
    (
        "health",
        "二级",
        "both",
        "数据源健康历史（[H]）",
        "数据源健康历史（[H]）",
        "health",
        "0\r",
        "最近若干次采集的成功/失败源与降级原因",
    ),
    (
        "doctor",
        "二级",
        "both",
        "系统自检（[T]）",
        "系统自检（[T]）",
        "doctor",
        "\r\x03",
        "环境/配置/目录/数据源一键体检；首屏含联网检查询问",
    ),
    (
        "generate",
        "二级",
        "both",
        "生成报告 · 费用确认（[E]/[B]/[L]）",
        "生成报告 · 费用确认（[E]/[B]/[L]）",
        "generate",
        "\x03",
        "生成前的费用预估与「用已有结果 / 重新生成」确认",
    ),
    (
        "qa",
        "二级",
        "both",
        "报告追问 · 报告选择（[Q]）",
        "报告追问 · 报告选择（[Q]）",
        "qa",
        "\x03",
        "选择已生成 HTML 报告进入多轮追问",
    ),
    (
        "whatif",
        "二级",
        "both",
        "调仓 What-if · 基准文件选择（[W]）",
        "调仓 What-if · 基准文件选择（[W]）",
        "whatif",
        "\x03",
        "基准持仓选择，下一步为候选持仓",
    ),
    (
        "refresh",
        "二级",
        "both",
        "刷新配置（[R]）",
        "刷新配置（[R]）",
        "refresh",
        "",
        "重读 config / llm_settings / llm_key / llm_providers",
    ),
]

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _clean(raw: bytes) -> str:
    text = raw.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\x1b\[[0-9;]*[HJKlh]", "", text)
    text = re.sub(r"\x1b\[[0-9;]*[ABCDG]", "", text)
    lines = [ln.rstrip() for ln in text.split("\n")]
    lines = [ln for ln in lines if not re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+ \[(INFO|DEBUG|WARNING)\]", ln)]
    while lines and not ANSI_RE.sub("", lines[0]).strip():
        lines.pop(0)
    while lines and not ANSI_RE.sub("", lines[-1]).strip():
        lines.pop()
    return "\n".join(lines)


def capture(mode: str, keys: str, timeout: float = 20.0) -> str:
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", LINES, COLS, 0, 0))
    env = {**os.environ, "COLUMNS": str(COLS), "LINES": str(LINES), "TERM": "xterm-256color", "PYTHONPATH": str(REPO)}
    env.pop("NO_COLOR", None)
    proc = subprocess.Popen(
        [sys.executable, str(HERE / "tui_render.py"), "--mode", mode],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        cwd=str(REPO),
        env=env,
        close_fds=True,
    )
    os.close(slave)
    chunks: list[bytes] = []
    started = time.time()
    sent_at: float | None = None
    try:
        while time.time() - started < timeout:
            ready, _, _ = select.select([master], [], [], 0.1)
            if ready:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    break
                if not data:
                    break
                chunks.append(data)
            elapsed = time.time() - started
            if sent_at is None and elapsed >= 1.2:
                os.write(master, keys.encode())
                sent_at = elapsed
            elif sent_at is not None and elapsed - sent_at > 2.5 and proc.poll() is None:
                proc.terminate()
                break
            if proc.poll() is not None:
                time.sleep(0.3)
                while True:
                    try:
                        data = os.read(master, 65536)
                    except OSError:
                        break
                    if not data:
                        break
                    chunks.append(data)
                break
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        os.close(master)
    return _clean(b"".join(chunks))


def main() -> int:
    frames = []
    for sid, level, variant, title_current, title_proposed, mode, keys, note in SCREENS:
        raw = capture(mode, keys)
        lines = [ln for ln in ANSI_RE.sub("", raw).split("\n") if ln.strip()]
        frames.append(
            {
                "id": sid,
                "level": level,
                "variant": variant,
                "title_current": title_current,
                "title_proposed": title_proposed,
                "note": note,
                "ansi": raw,
                "lines": len(lines),
            }
        )
        print(f"[{'OK' if lines else 'EMPTY'}] {variant:<9} {level} {title_current or title_proposed}（{len(lines)} 行）")
    out_dir = REPO / "docs" / "tmp" / "tui-frames"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "tui_frames.json"
    out.write_text(json.dumps(frames, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n写出 {out}（{len(frames)} 屏）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
