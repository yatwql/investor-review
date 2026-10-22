"""HTML 报告结构测试共享夹具 — 模板路径、章节常量与最小渲染数据构造。

供 `test_html_report_structure*.py` 各分片共用（避免同一套构造器在各分片
复制一份、改模板契约时漏改）。本文件不含 `test_*` 用例，故不被收集。
"""

from __future__ import annotations

import os

from bs4 import BeautifulSoup

from src.python.core.registry import _REPORT_SECTION_DEFAULT as _REGISTRY_SECTION_DEFAULT


# ── 常量 ──────────────────────────────────────────────────────

_TEMPLATE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "static", "tmpl", "report_template.html"),
)
_WHATIF_TEMPLATE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "static", "tmpl", "whatif_template.html"),
)

# 默认注册表 key（按默认顺序，与 registry.py 对齐）
_ALL_KEYS_DEFAULT = [
    "summary",
    "holdings_detail",
    "penetration",
    "fund_performance",
    "position_structure",
    "style_factor",
    "news_correlation",
    "global_macro",
    "expert_review",
    "health_check",
    "penetration_deep",
    "portfolio_history_drawdown",
    "llm_usage",
]

_ALWAYS_KEYS = {"summary", "holdings_detail", "penetration", "fund_performance"}
_FUND_DEEP_ANALYSIS_KEYS = {"position_structure", "style_factor"}
_NEWS_KEYS = {"news_correlation"}
_LLM_KEYS = {"global_macro", "expert_review", "health_check", "penetration_deep", "llm_usage"}
_HISTORY_KEYS = {"portfolio_history_drawdown"}

# LLM 支持章节（目录/导航橙色+🧠 标记）：与「LLM」导航组全部章节一致
# （news_correlation 注册表 type 为 news，但仍属 LLM 支持章；_LLM_SUPPORTED_SECTIONS 派生一致性测试防漂移）
_LLM_SUPPORTED_KEYS = {
    "news_correlation",
    "global_macro",
    "expert_review",
    "health_check",
    "penetration_deep",
    "llm_usage",
}

# 场景章节序（真值取自 core/registry.py 章节注册表，nav_group/llm_supported/显示名
# 等字段同源）：裁剪到 _ALL_KEYS_DEFAULT 并重排号为可见连续序 1..N——模拟生产端
# 可见重编号；不再自持第二份字段字面量（注册表改名/改分组测试自动跟随）。
_REGISTRY_SECTION_BY_KEY = {sec["key"]: sec for sec in _REGISTRY_SECTION_DEFAULT}

_REPORT_SECTION_DEFAULT: list[dict] = [
    {**_REGISTRY_SECTION_BY_KEY[key], "number": idx} for idx, key in enumerate(_ALL_KEYS_DEFAULT, start=1)
]


def _build_minimal_render_data(
    section_order: list[dict],
    section_numbers: dict[str, int],
    section_visible_dict: dict[str, bool],
) -> dict:
    """构建最小化模板渲染数据。

    根据 visible_set 自动填充基金深度分析/新闻模块所需的 mock 数据结构，
    避免模板内 .get() 或 [] 操作因 None 值崩溃。

    Args:
        visible_set: 当前可见的模块 key 集合，用于决定哪些 mock 数据需要填充
    """
    visible_keys = {k for k, v in section_visible_dict.items() if v}

    data = {
        "now": "2026-07-05 12:00:00",
        "today": "2026-07-05",
        "trading_day": "2026-07-03",
        "total_mv": 0,
        "total_cost": 0,
        "total_profit": 0,
        "total_profit_rate": 0,
        "total_today_profit": 0,
        "today_profit_rate": 0,
        "categories": {},
        "update_status": None,
        "a_indices": [],
        "us_indices": [],
        "accounts": {},
        "account_totals": {},
        "cat_data": [],
        "penetration": None,
        "perf_data": [],
        "news_data": None,
        "news_llm_meta": None,
        "has_llm_analysis": False,
        "manager_analysis": None,
        "overlap_matrix": None,
        # 持仓关系矩阵：相关性区块数据契约（空 dict 触发模板内 .get() 默认值降级）
        "position_relationship_data": {},
        "concentration_analysis": None,
        "style_analysis": None,
        "llm_enabled": True,
        "global_macro": None,
        "expert_review": None,
        "health_check": None,
        "penetration_deep": None,
        "llm_session_usage": None,
        "module_labels": {},
        "module_disabled": {},
        "llm_module_info": [],
        "llm_endpoint": "",
        "cache_stats": None,
        "section_order": section_order,
        "section_numbers": section_numbers,
        "section_visible_dict": section_visible_dict,
        # Chart.js 数据集空 → 图表容器显示占位文案
        "chart_datasets": {},
    }

    # 基金深度分析模块可见时，填充 mock 数据结构（模板内部 .get() 要求 dict 非 None）
    if visible_keys & _FUND_DEEP_ANALYSIS_KEYS:
        data["manager_analysis"] = {"first_check_summary": None, "results": []}
        data["overlap_matrix"] = {"fund_names": {}, "funds": [], "matrix": [], "pairs": []}
        data["concentration_analysis"] = {"results": []}
        data["style_analysis"] = {"results": []}

    # 新闻模块可见时，news_data 需为非 None list（模板隐式调用 |length）
    if visible_keys & _NEWS_KEYS:
        data["news_data"] = []

    return data


def _render_template(render_data: dict) -> BeautifulSoup:
    """用 html_writer._ENV 渲染模板并返回 BeautifulSoup 对象。"""
    from src.python.report.html_jinja_env import _ENV
    from src.python.report.html_writer import _LLM_SUPPORTED_SECTIONS, _build_section_nav_groups

    # 注入 section_visible 闭包 + section_groups 分组导航（与生产代码相同的 context 变量方式，不写入 _ENV.globals）
    _sv_dict = render_data.get("section_visible_dict", {})

    def _sv_fn(key: str, _d: dict = _sv_dict) -> bool:
        return bool(_d.get(key, False))

    section_groups = _build_section_nav_groups(
        render_data.get("section_order", []),
        _sv_fn,
        render_data.get("section_numbers", {}),
    )
    html = _ENV.get_template("report_template.html").render(
        **render_data,
        section_visible=_sv_fn,
        section_groups=section_groups,
        llm_supported_sections=_LLM_SUPPORTED_SECTIONS,
    )
    return BeautifulSoup(html, "html.parser")


def _get_section_id_from_href(href: str) -> str:
    """从 href="#sec-xxx" 提取 sec-xxx。"""
    if href.startswith("#"):
        return href[1:]
    return href
