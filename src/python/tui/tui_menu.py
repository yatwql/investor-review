"""TUI 菜单定义与渲染模块。

职责：
  - MenuItem 类型定义
  - MENU_ITEMS 菜单列表
  - 菜单渲染（render_menu、print_header、print_sep）
  - 配置显示（show_config、_show_llm_config_status）
  - 快捷键查找（index_by_key）
  - 通用 UI 辅助（exit_app、press_any_key、refresh_config）
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

from src.python.core.ansi_colors import CYAN, DIM, GREEN, RED, RESET, YELLOW
from src.python.config import get_config, resolve_output_dir

# 每个菜单项：(快捷键, 显示标签, 回调函数, 是否退出项)
MenuItem = tuple[str, str, Callable[[], None] | None, bool]

MENU_ITEMS: list[MenuItem] = [
    ("E", "生成基础报告（仅 Excel）", None, False),
    ("B", "生成标准报告（Excel+HTML）", None, False),
    ("L", "生成完整报告（含 LLM 分析）", None, False),
    ("W", "调仓 What-if 模拟（独立报告）", None, False),
    ("Q", "报告对话式追问", None, False),
    ("1", "更新基础类缓存", None, False),
    ("2", "更新行情类缓存", None, False),
    ("3", "缓存管理（统计与清理）", None, False),
    ("C", "配置报告章节显隐", None, False),
    ("S", "配置报告章节内容呈现", None, False),
    ("G", "全局设置", None, False),
    ("R", "刷新配置", None, False),
    ("D", "诊断与排查", None, False),
    ("X", "退出（0 亦可）", None, True),
]

# 受功能开关约束的菜单项：{快捷键: 开关名}。
# 开关关闭时该菜单项整体不出现（在 _apply_feature_gates 中裁剪），
# 避免用户点进去只得到一句「功能未启用」。
FEATURE_GATED_ITEMS: dict[str, str] = {"Q": "report_qa"}

# 主菜单分组（按任务域编排）：组序即阅读序，组内保留 MENU_ITEMS 的原始次序。
# 未列入任何组的项（退出）渲染在分组之后——组覆盖完整性由菜单用例守护。
MENU_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("生成报告", ("E", "B", "L", "W", "Q")),
    ("数据与查看", ("1", "2", "3")),
    ("配置", ("C", "S", "G", "R")),
    ("诊断与排查", ("D",)),
]


# 菜单母本（定义时的完整清单）：门控裁剪**从母本重建**而不是就地过滤——
# 就地过滤会把关闭过的项永久删除，运行中在 [S] 重新开启后该项仍不出现（只能重启）。
_ALL_MENU_ITEMS: list[MenuItem] = list(MENU_ITEMS)


def _apply_feature_gates() -> None:
    """按功能开关重建 MENU_ITEMS（幂等、可逆；切片赋值保持列表对象不变）。

    幂等可逆是硬要求：主循环每帧调用一次（开关在 `[S]` 改完返回首页即刻生效），
    所以必须每次从 `_ALL_MENU_ITEMS` 母本重新裁剪——否则「先关后开」的项回不来。
    """
    from src.python.config.features import is_feature_enabled

    disabled = {
        key
        for key, flag in FEATURE_GATED_ITEMS.items()
        if not is_feature_enabled(flag) and any(item[0] == key for item in _ALL_MENU_ITEMS)
    }
    MENU_ITEMS[:] = [item for item in _ALL_MENU_ITEMS if item[0] not in disabled]


_config_cache: dict | None = None


def refresh_config() -> dict:
    """刷新并返回配置缓存。"""
    global _config_cache
    _config_cache = get_config()
    return _config_cache


def get_config_cache() -> dict | None:
    """返回当前配置缓存（只读访问）。"""
    return _config_cache


def filter_menu_llm_modules(module_names: dict[str, str]) -> dict[str, str]:
    """菜单 LLM 模块清单门面（恒等返回）。

    注册表不含任何面板隐藏模块，本函数保留调用面稳定（菜单 / [S] 面板 /
    强刷多选 / 手册菜单块同步均经此派发），不做过滤。
    """
    return dict(module_names)


# ── 界面输出 ──────────────────────────────────────────────


def print_sep(char: str = "=", width: int = 56) -> None:
    """横向分隔线（弱化层：不抢标题与内容的注意力）。"""
    print(f"{DIM}{char * width}{RESET}")


def print_header() -> None:
    """打印程序标题头（每次主循环迭代时重绘）。"""
    from src.python.core.constants import APP_NAME, APP_VERSION

    print_sep()
    from src.python.core.ansi_colors import BOLD, ORANGE, RESET

    print(f"        {BOLD}{ORANGE}{APP_NAME}  v{APP_VERSION}{RESET}")
    print_sep()

    # 页头常驻状态行（全本地取数、逐项降级、TTL 内记忆化）
    from src.python.tui.status_line import build_status_line

    print(f"  {build_status_line()}")
    print()

    # 首次运行引导：检测是否缺少关键资源
    config = _config_cache if _config_cache is not None else refresh_config()
    holdings = os.path.join(config.get("holdings_dir", ""), config.get("holdings_filename", ""))
    _first_run_hints = []
    if not os.path.exists(holdings):
        _first_run_hints.append("• 请先通过菜单 [D] 配置持仓目录/文件名，或放置文件到默认目录")
    from src.python.core.system_info import llm_status

    if not llm_status()["configured"]:
        _first_run_hints.append(
            "• 如需 LLM 分析，请配置 data/config/llm_key.json 或 llm_providers.json（菜单 [S] 查看状态）"
        )
    if _first_run_hints:
        print("  📋 首次使用指引：")
        for hint in _first_run_hints:
            print(f"    {hint}")
        print()


def render_menu(sel: int, filter_text: str = "") -> None:
    """打印菜单（按终端宽度折行；全档渲染选中态，窄屏导航时由主循环原地重绘）。

    按 ``MENU_GROUPS`` 分组渲染（生成 / 数据与查看 / 配置 / 诊断），未入组项
    （退出）列在末尾。``filter_text`` 非空时只渲染匹配项并顶部给筛选状态行。

    narrow（<64 列，手机竖屏）下直达主路径（按字母/数字键即执行）与方向键导航
    并存：渲染 `>` 选中指示器；页脚提示两种入口（见 tui.main 内层循环）。
    """
    from src.python.tui.switch_panel import layout_tier
    from src.python.tui.text_layout import style_heading, terminal_columns, wrap_with_prefix

    columns = terminal_columns()
    narrow = layout_tier(columns) == "narrow"
    visible = match_menu_items(filter_text)
    visible_set = set(visible)
    grouped_keys = {key for _title, keys in MENU_GROUPS for key in keys}

    def _render_item(index: int) -> None:
        key, label, _cb, _is_exit = MENU_ITEMS[index]
        # 焦点色（青）只标当前选中行：一色一职责，不与结构蓝/状态色混用
        prefix = f"  {CYAN}>{RESET}" if index == sel else "   "
        head = f"{prefix} [{key}] "
        # 长标签（如「生成标准报告（Excel+HTML，按章节配置）」）在手机窄屏上折行：
        # 前缀（光标/编号）不参与断行，续行缩进到标签起始列，视觉上仍归属同一项
        print("\n".join(wrap_with_prefix(head, label, columns)))

    print()
    if filter_text:
        print(
            "\n".join(
                wrap_with_prefix("  ", f"筛选「{filter_text}」：{len(visible)} 项（/ 改关键词 · 0 清除）", columns)
            )
        )
    for title, keys in MENU_GROUPS:
        members = [index_by_key(key) for key in keys]
        members = [i for i in members if i is not None and i in visible_set]
        if not members:
            continue
        for _line in wrap_with_prefix("  ", f"── {title} ──", columns):
            print(style_heading(_line))
        for index in members:
            _render_item(index)
    for index, (key, _label, _cb, _is_exit) in enumerate(MENU_ITEMS):
        if key in grouped_keys or index not in visible_set:
            continue
        _render_item(index)
    print()
    # 页脚按终端宽度折行：窄屏（手机）上不硬折，键位提示也不会被右边界切掉
    footer = (
        "窄屏直达 · ↑↓ 选择 · 回车执行 | / 筛选 | Esc / 0 / X 退出 | Ctrl+C 退出"
        if narrow
        else "↑↓ 移动 | 回车执行 | 字母/数字键直达 | / 筛选 | Esc / 0 / X 退出 | Ctrl+C 退出"
    )
    print("\n".join(f"{DIM}{_line}{RESET}" for _line in wrap_with_prefix("  ", footer, terminal_columns())))
    print()


def show_config() -> None:
    """显示当前配置及 LLM 配置状态。"""
    from src.python.config import resolve_holdings_path

    config = _config_cache if _config_cache is not None else refresh_config()
    holdings_path = resolve_holdings_path(config)
    print(f"  持仓目录: {config.get('holdings_dir', '未设置')}")
    print(f"  持仓文件: {config.get('holdings_filename', '未设置')}")
    print(f"  输出目录: {resolve_output_dir(config)}")
    print(f"  新闻抓取上限: {config.get('news_top_count', '300')} 条")
    if os.path.exists(holdings_path):
        print(f"  状态: {GREEN}[OK]{RESET} 文件就绪")
    else:
        print(f"  状态: {RED}[!!]{RESET} 文件未找到")
    _show_privacy_and_security_status()
    _show_llm_config_status()
    print()


def _show_privacy_and_security_status() -> None:
    """显示隐私提示和匿名化安全状态。"""
    from src.python.config.anonymizer import get_anonymization_mode
    from src.python.core.system_info import anon_mode_label

    _anon_mode = get_anonymization_mode()
    _anon_display = anon_mode_label(_anon_mode)

    # 检查隐私提示是否已显示过（机器本地状态）
    from src.python.config import get_local_flag

    _privacy_shown = get_local_flag("_privacy_notice_shown")
    _privacy_icon = f"{GREEN}✓{RESET}" if _privacy_shown else f"{YELLOW}待首次报告生成时显示{RESET}"

    print(f"  持仓匿名化: {_anon_display}")
    print(f"  隐私声明: {_privacy_icon}")
    print()


def _show_llm_config_status() -> None:
    """显示 LLM 配置状态（绿色已配置 / 红色未配置）。

    数据来自 ``core.system_info.llm_status`` 单源（三渠道共用判定树），
    本函数只做终端渲染，不自行组装状态。
    """

    from src.python.core.system_info import llm_status

    llm = llm_status()
    if not llm.get("configured"):
        print(f"  LLM: {RED}未配置{RESET}（配置 data/config/llm_key.json 或 llm_providers.json 后重启生效）")
        return
    if llm.get("mode") == "multi":
        _show_multi_chain_status(llm)
        return
    # 状态文案已由 core.system_info.circuit_display 归一为用户词（三渠道同源）
    cb_display = f" |  自动重试: {llm['circuit']}" if llm["circuit"] != "—" else ""
    print(
        f"  LLM: {GREEN}已配置{RESET}  provider={llm['provider']}  model={llm['model']}"
        f"  endpoint={llm['endpoint_display']}{cb_display}"
    )
    print(f"         模型路由: {' / '.join(llm['route'])}")


def _show_multi_chain_status(llm: dict) -> None:
    """显示多 Provider 链式服务的详细信息（消费 llm_status 单源结果）。

    展示策略、各 Provider 的后端/模型/优先级/熔断状态与模块偏好；
    单独提取为函数以保持 _show_llm_config_status 清晰。
    """
    print(f"  LLM: {GREEN}已配置{RESET}")
    print(f"  策略: {llm['strategy']}  |  多链服务 ({len(llm['providers'])} provider)")
    for i, p in enumerate(llm["providers"], 1):
        cb_status = p["circuit"]
        cb_icon = f"{GREEN}✓{RESET}" if cb_status == "正常" else f"{RED}⚠{RESET}"
        print(f"    [{i}] {p['name']}  ({p['backend']})")
        print(f"         模型: {p['model']}")
        print(f"         优先级: {p['priority']}    自动重试: {cb_icon} {cb_status}")
    if llm.get("preferred"):
        print(f"    ▶ 模块偏好: {' / '.join(llm['preferred'])}")


# ── 快捷键查找 ──────────────────────────────────────────────


def index_by_key(key: str) -> int | None:
    """返回快捷键对应的菜单索引，未找到则返回 None。"""
    for i, (k, _label, _cb, _is_exit) in enumerate(MENU_ITEMS):
        if k == key:
            return i
    return None


def match_menu_items(keyword: str) -> list[int]:
    """返回标签或按键命中关键词的菜单索引（空关键词=全部）。

    Args:
        keyword: 筛选关键词（大小写不敏感；按键精确命中优先，否则按标签子串）。

    Returns:
        按 MENU_ITEMS 次序的索引列表。
    """
    word = (keyword or "").strip().lower()
    if not word:
        return list(range(len(MENU_ITEMS)))
    # 按键精确命中优先：输入单键名（如 "T"/"1"）时不应被标签里的拉丁字母噪声干扰
    for i, (key, _label, _cb, _is_exit) in enumerate(MENU_ITEMS):
        if word == key.lower():
            return [i]
    return [i for i, (_key, label, _cb, _is_exit) in enumerate(MENU_ITEMS) if word in label.lower()]


def next_matching(matches: list[int], cursor: int, step: int) -> int | None:
    """在筛选结果内按方向移动选中项（回绕）；无匹配返回 None。

    Args:
        matches: ``match_menu_items`` 的索引列表。
        cursor: 当前选中索引。
        step: +1 向下 / -1 向上。

    Returns:
        下一个匹配索引（回绕）；无匹配项时 None。
    """
    if not matches:
        return None
    if step > 0:
        later = [i for i in matches if i > cursor]
        return later[0] if later else matches[0]
    earlier = [i for i in matches if i < cursor]
    return earlier[-1] if earlier else matches[-1]


# ── 通用 UI 辅助 ──────────────────────────────────────────────


def press_any_key() -> None:
    """等待用户按任意键继续。支持 Ctrl+C 退出。"""
    from src.python.tui.tui_keys import KEY_CTRL_C, get_key

    print("  按任意键返回菜单...")
    k = get_key()
    if k == KEY_CTRL_C:
        exit_app()


def exit_app() -> None:
    """打印退出信息并终止程序。"""
    print()
    print("  感谢使用，再见！")
    sys.exit(0)
