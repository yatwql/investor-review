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

**去抖与脱敏**：采集结果统一过 `_sanitize` —— 日志正文替换为同形态示例行、计数/体积/
日期/本地路径/真实线路名归一为固定值。因此图样**可重复生成**（同代码状态两次采集逐字节
一致），且不含用户真实数据（持仓品种、缓存清单、端点名、机器路径）。新增屏若回显随运行
时刻变化的内容，在此补规则而不是让图样抖动。

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


#: 每屏的入口路径（current, proposed）——图样顶部面包屑与层级导航图共用
NAV_PATH: dict[str, tuple[str, str]] = {
    "main": ("主菜单", ""),
    "main_proposed": ("", "主菜单"),
    "switches": ("主菜单 › 配置 › [S]", ""),
    "switches_proposed": ("", "主菜单 › 配置 › [S]"),
    "switch_detail": ("主菜单 › 配置 › [S] › ?10（面板内查询）", ""),
    "switch_detail_proposed": ("", "主菜单 › 配置 › [S] › ?3（面板内查询）"),
    "dmenu": ("主菜单 › 配置 › [G]", ""),
    "g_menu_proposed": ("", "主菜单 › 配置 › [G]"),
    "d_tuning": ("主菜单 › 配置 › [D] › [L]", ""),
    "d_llm_proposed": ("", "主菜单 › 配置 › [G] › [L]"),
    "d_map": ("主菜单 › 配置 › [G] › [M]", "主菜单 › 配置 › [G] › [M]"),
    "d_dir": ("主菜单 › 配置 › [G] › [H]", "主菜单 › 配置 › [G] › [H]"),
    "d_file": ("主菜单 › 配置 › [G] › [F]", "主菜单 › 配置 › [G] › [F]"),
    "d_out": ("主菜单 › 配置 › [D] › [O]", "主菜单 › 配置 › [G] › [O]"),
    "boards": ("主菜单 › 配置 › [C]", ""),
    "boards_proposed": ("", "主菜单 › 配置 › [C]"),
    "indices": ("主菜单 › 配置 › [G] › [I]", "主菜单 › 配置 › [G] › [I]"),
    "anon": ("主菜单 › 配置 › [G] › [A]", "主菜单 › 配置 › [G] › [A]"),
    "providers": ("主菜单 › 配置 › [G] › [L] › 7", ""),
    "providers_proposed": ("", "主菜单 › 配置 › [G] › [L] › 7"),
    "cache": ("主菜单 › 数据与查看 › [3]", "主菜单 › 数据与查看 › [3]"),
    "logs": ("主菜单 › 诊断与排查 › [V]", "主菜单 › 诊断与排查 › [D] › [V]"),
    "health": ("主菜单 › 诊断与排查 › [H]", "主菜单 › 诊断与排查 › [D] › [H]"),
    "doctor": ("主菜单 › 诊断与排查 › [T]", "主菜单 › 诊断与排查 › [D] › [T]"),
    "d_diag_proposed": ("", "主菜单 › 诊断与排查 › [D]"),
    "d_log_proposed": ("", "主菜单 › 诊断与排查 › [D] › [L]"),
    "generate": ("主菜单 › 生成报告 › [E]/[B]/[L]", "主菜单 › 生成报告 › [E]/[B]/[L]"),
    "qa": ("主菜单 › 生成报告 › [Q]", "主菜单 › 生成报告 › [Q]"),
    "whatif": ("主菜单 › 生成报告 › [W]", "主菜单 › 生成报告 › [W]"),
    "refresh": ("主菜单 › 配置 › [R]", "主菜单 › 配置 › [R]"),
}

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
        "主菜单（14 项，配置组四项 + 诊断组一项）",
        "main_proposed",
        "",
        "配置组 P/S/G/R；线路、运行参数、指数池、匿名化归于 [G]；日志/健康/自检收进 [D]",
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
        "[S] 报告章节内容呈现（六组，20 项）",
        "switches_proposed",
        "0\r",
        "按报告位置六组：持仓与交易 1-4 / 市场与估值 5-8 / 基金与风格 9-11 / 事件与摘要 12-15 / 呈现与交互 16-17 / 机制与质量 18-20",
    ),
    (
        "switch_detail",
        "面板内",
        "current",
        "功能开关 · 单项详情（`?10`，四组编号）",
        "",
        "switches",
        "?10\r\x03",
        "面板内只读查询：回车后仍停在同一面板，不进入新层级；此处第 10 项＝辩论-条件推理",
    ),
    (
        "switch_detail_proposed",
        "面板内",
        "proposed",
        "",
        "[S] 单项详情（`?3`，五组编号）",
        "switches_proposed",
        "?3\r\x03",
        "面板内只读查询：回车后仍停在同一面板；第 3 项＝数据质量仪表盘",
    ),
    # ── 配置分组二级 ──
    (
        "dmenu",
        "二级",
        "current",
        "[G] 全局设置（二级，7 项·数字主入口）",
        "",
        "dmenu",
        "0\r",
        "[H] 目录 / [F] 文件名 / [O] 输出目录 / [L] LLM 调优 / [M] 入口地图",
    ),
    (
        "g_menu_proposed",
        "二级",
        "proposed",
        "",
        "[G] 全局设置（二级，7 项·数字主入口）",
        "g_menu_proposed",
        "0\r",
        "按 G 进入本层：1-7 为主入口、H/F/O/L/I/A/M 为字母别名；按 4 或 L 才进入 LLM 设置（下一层）",
    ),
    (
        "d_diag_proposed",
        "二级",
        "proposed",
        "",
        "[D] 诊断与排查（4 项·数字主入口）",
        "d_diag_proposed",
        "0\r",
        "入口聚合：1-4 主入口、L/V/H/T 字母别名；缺省项为 T（系统自检）；自检恒上屏",
    ),
    (
        "d_log_proposed",
        "三级",
        "proposed",
        "",
        "[D]→[L] 日志设置（6 项）",
        "d_log_proposed",
        "0\r",
        "写盘/控制台级别、轮转上限与备份数、查看器默认级别与行数；级别与轮转下次启动生效",
    ),
    # ── LLM 设置三级 ──
    (
        "d_tuning",
        "三级",
        "current",
        "[D]→[L] LLM 调优参数（三级，6 个数字项）",
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
        "[G]→[L] LLM 设置（三级，7 个数字项）",
        "d_llm_proposed",
        "0\r",
        "1-6 输入新值修改运行参数；第 7 项为「多链线路优先级」入口（再进线路面板）；数字编号从属本层",
    ),
    # ── 目录与索引（版面一致，入口键不同）──
    (
        "d_map",
        "三级",
        "both",
        "配置入口地图（[G]→[M]）",
        "配置入口地图（[G]→[M]）",
        "entrymap",
        "",
        "只读索引：各配置项在哪个菜单键下",
    ),
    (
        "d_dir",
        "三级",
        "both",
        "持仓信息目录（[G]→[H]）",
        "持仓信息目录（[G]→[H]）",
        "dir",
        "\x03",
        "目录列表选择，取到首屏即中止",
    ),
    (
        "d_file",
        "三级",
        "both",
        "持仓信息文件名（[G]→[F]）",
        "持仓信息文件名（[G]→[F]）",
        "filename",
        "\x03",
        "目录内 .xlsx 列表选择",
    ),
    (
        "d_out",
        "三级",
        "both",
        "报告输出目录（[G]→[O]）",
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
        "报告章节取舍（[C]，含指路牌项）",
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
        "[C] 报告章节（17 项三块 + 7.1/7.2）",
        "boards_proposed",
        "0\r",
        "顶层 5 / LLM 7（智囊团下 7.1 正反辩论、7.2 条件推理）/ 默认关闭的整章 3 / 关联产物 1；底部提示章节内内容见 [S]",
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
        "current",
        "LLM 多链线路优先级（[M]）",
        "",
        "providers",
        "0\r",
        "按 priority 排序的线路清单与调序操作；返回项「0. 返回主菜单」",
    ),
    (
        "providers_proposed",
        "四级",
        "proposed",
        "",
        "多链线路优先级（[G]→[L] 第 7 项）",
        "providers",
        "0\r",
        "按 priority 排序的线路清单与调序操作；返回项「0. 返回 LLM 设置」",
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

#: 目标态需要按"上一层"改写的返回项文案（真实实现会同步改字面量）
REWRITES: dict[str, list[tuple[str, str]]] = {
    "providers_proposed": [("0. 返回主菜单", "0. 返回 LLM 设置")],
}

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# ── 图样去抖与脱敏（确定性 + 无真实数据）─────────────────────────────
#
# 图样是**设计产物**：必须可重复生成（同代码 → 同字节）且不含用户真实数据。
# 三张「内容随运行时刻变化」的屏（`logs` 日志查看器、`doctor` 系统自检、
# `health` 健康历史）天然带时间戳、真实日志正文（含持仓品种名）、计数与本地
# 绝对路径，直接采集会让每次重拍都产生噪声 diff，并把私有数据带进仓库。
#
# 因此采集结果统一过一遍 `_sanitize`：先把日志正文替换为同形态示例行，再把
# 计数/体积/日期/路径归一为固定值。规则顺序固定、每条幂等，保证两次采集逐字节
# 一致（本文件末尾的 `--stable` 自检即验证这一点）。

_LOG_LINE_RE = re.compile(
    r"^(?P<indent>\s*)(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) \[(?P<level>[A-Z]+)\] (?P<msg>.*)$"
)

#: 各日志级别的示例正文（按出现序轮转，保留信息密度与长短差异，便于看图样观感）
_LOG_EXAMPLES: dict[str, tuple[str, ...]] = {
    "DEBUG": (
        "[示例模块] 缓存命中：示例键 …",
        "[示例模块] 预检跳过：无变更",
    ),
    "INFO": (
        "基金业绩 [2/5]: 示例基金B (000002)",
        "基金风格表 [3/5]: 示例基金C (000003)",
        "[示例模块] 已加载 12 项功能开关覆写",
        "缓存清理预览: 共 0 个文件",
        "复用预取的示例数据，共 20 条",
    ),
    "WARNING": (
        "[示例数据源] 响应超时，已切换备用源",
        "[示例模块] 字段缺失，已静默降级",
    ),
    "ERROR": ("[示例模块] 请求失败：端点不可达（已重试 2 次）",),
}

#: 顺序敏感的归一规则：(正则, 替换)。数值/日期/路径一律落到固定示例值
_NORMALIZE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    # 本地绝对路径（项目根 / 虚拟环境）——去掉机器与用户名信息
    (re.compile(re.escape(str(REPO)) + r"/\.venv"), "<虚拟环境>"),
    (re.compile(re.escape(str(REPO))), "<项目根>"),
    # 日志体积与采样行数（doctor「日志与缓存」组）
    (re.compile(r"app\.log [\d.]+ MB"), "app.log 8.0 MB"),
    (re.compile(r"轮转 \d+ 份"), "轮转 3 份"),
    (re.compile(r"DEBUG 占比 \d+%"), "DEBUG 占比 85%"),
    (re.compile(r"采样 \d+ 行"), "采样 120000 行"),
    # 去重锚点体积 / 行数
    (re.compile(r"([\d.]+ MB) / \d+ 行（维护压缩阈值"), r"37.0 MB / 110000 行（维护压缩阈值"),
    # 运行台账与账本统计
    (re.compile(r"告警中位 \d+、累计错误 \d+、中断 \d+"), "告警中位 12、累计错误 0、中断 0"),
    (re.compile(r"事实校验自动修正中位 \d+ 处"), "事实校验自动修正中位 3 处"),
    (re.compile(r"已结算 \d+ 条 / 待结算 \d+ 条"), "已结算 16 条 / 待结算 40 条"),
    (re.compile(r"累计 \d+ 条（实时 \d+ / 非实时 \d+）"), "累计 240 条（实时 236 / 非实时 4）"),
    (re.compile(r"启用 \d+ 次（最近 \d{4}-\d{2}-\d{2}）"), "启用 60 次（最近 2026-01-05）"),
    (re.compile(r"统计窗口 \d{4}-\d{2}-\d{2} ~ \d{4}-\d{2}-\d{2}"), "统计窗口 2025-12-01 ~ 2026-01-05"),
    # LLM 行尾费用摘要（近 N 日滚动窗口：跨日即变）
    (re.compile(r"· \d+次 ¥[\d.]+ 均¥[\d.]+"), "· 18次 ¥1.2345 均¥0.0686"),
    # 缓存管理统计（真实缓存清单：文件数 / 体积 / 前缀分布 / 最大文件）
    (re.compile(r"缓存文件: \d+ 个 \| 大小: \d+ KB"), "缓存文件: 100 个 | 大小: 1024 KB"),
    (re.compile(r"^(\s*)文件: \d+ 个 \| 大小: [\d.]+ (?:KB|MB)$", re.M), r"\1文件: 100 个 | 大小: 1.0 MB"),
    (re.compile(r"过期文件: \d+ 个"), "过期文件: 0 个"),
    (re.compile(r"(\w+_\*): \d+ 个文件"), r"\1: 12 个文件"),
    (re.compile(r"最新: \d{4}-\d{2}-\d{2} \d{2}:\d{2}"), "最新: 2026-01-01 00:00"),
    (re.compile(r"^(\s{4})(?!\S+_\*)(.+?)  \([\d.]+ (?:KB|MB)\)$", re.M), r"\1示例缓存键.json  (1.0 MB)"),
    # 健康历史日期列：按出现序映射为固定日期序列（保证顺序可读、取值稳定）
    (re.compile(r"\b20\d{2}-\d{2}-\d{2}\b"), "2026-01-01"),
)


def _provider_name_rules() -> tuple[tuple[re.Pattern[str], str], ...]:
    """把本机 `llm_providers.json` 的真实线路名/凭据名脱敏为「示例线路X」。

    线路面板与 `[G]→[L]` 第 7 项摘要会回显真实线路名（链首名等），属用户配置，
    不得进入仓库图样。名字从配置只读取、按长度降序替换（避免 `deepseek` 先吃掉
    `deepseek-main` 的前缀）。配置缺失或读取失败时返回空规则，图样照常生成。
    """
    try:
        import sys as _sys

        _sys.path.insert(0, str(REPO))
        from src.python.config import get_llm_providers

        providers = [item for item in (get_llm_providers().get("providers") or []) if isinstance(item, dict)]
    except Exception:
        return ()
    names: list[str] = []
    for item in providers:
        for key in ("name", "credentials_ref"):
            value = item.get(key)
            if isinstance(value, str) and value and value not in names:
                names.append(value)
    names.sort(key=len, reverse=True)
    return tuple(
        (re.compile(re.escape(name)), f"示例线路{chr(ord('A') + index % 26)}") for index, name in enumerate(names)
    )


def _sanitize(raw: str) -> str:
    """图样去抖 + 脱敏：日志正文替换为示例行，计数/体积/日期/路径归一。

    Args:
        raw: 采集到的原始上屏文本（含 ANSI）。

    Returns:
        归一后的文本；同一代码状态重复采集逐字节一致。
    """
    counters: dict[str, int] = {level: 0 for level in _LOG_EXAMPLES}
    stamps: dict[str, int] = {}
    out: list[str] = []
    for line in raw.split("\n"):
        match = _LOG_LINE_RE.match(line)
        if match:
            level = match.group("level")
            examples = _LOG_EXAMPLES.get(level, ("[示例模块] 示例日志行",))
            index = counters.get(level, 0)
            counters[level] = index + 1
            # 时间戳按「同秒递增 1 毫秒」伪造：稳定、可比，不泄漏真实运行时刻
            seq = stamps.get("n", 0)
            stamps["n"] = seq + 1
            fake_ts = f"2026-01-01 00:00:{seq % 60:02d},{(seq * 137) % 1000:03d}"
            out.append(f"{match.group('indent')}{fake_ts} [{level}] {examples[index % len(examples)]}")
            continue
        out.append(line)
    text = "\n".join(out)
    for pattern, replacement in (*_NORMALIZE_RULES, *_provider_name_rules()):
        text = pattern.sub(replacement, text)
    return text


def _clean(raw: bytes) -> str:
    text = raw.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\x1b\[[0-9;]*[HJKlh]", "", text)
    text = re.sub(r"\x1b\[[0-9;]*[ABCDG]", "", text)
    lines = [ln.rstrip() for ln in text.split("\n")]
    lines = [
        ln for ln in lines if not re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+ \[(INFO|DEBUG|WARNING)\]", ln)
    ]
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
        for old_text, new_text in REWRITES.get(sid, ()):
            raw = raw.replace(old_text, new_text)
        raw = _sanitize(raw)
        lines = [ln for ln in ANSI_RE.sub("", raw).split("\n") if ln.strip()]
        path_current, path_proposed = NAV_PATH.get(sid, ("", ""))
        frames.append(
            {
                "id": sid,
                "level": level,
                "variant": variant,
                "path_current": path_current,
                "path_proposed": path_proposed,
                "title_current": title_current,
                "title_proposed": title_proposed,
                "note": note,
                "ansi": raw,
                "lines": len(lines),
            }
        )
        print(
            f"[{'OK' if lines else 'EMPTY'}] {variant:<9} {level} {title_current or title_proposed}（{len(lines)} 行）"
        )
    out_dir = REPO / "docs" / "tmp" / "tui-frames"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "tui_frames.json"
    out.write_text(json.dumps(frames, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n写出 {out}（{len(frames)} 屏）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
