#!/usr/bin/env python3
"""Web 配置面板图样生成器 —— 从真实注册表与配置取数，产出两份自包含 HTML。

产物：
  ``index.html``         目标设计（按业务域编排）
  ``web-current.html``   现有实现（按存储文件编排）

设计口径（与 `docs/plan/config-web-design.md` 一致）：
  - 域 = 一级分区（报告内容 / 呈现与机制 / 数据与线路 / LLM 运行）
  - 块 = 一组可编辑项；`features.<组键>` 对应注册表分组
  - 条目名与 TUI 逐字相同；TUI 的编号只属于 TUI，Web 用勾选/输入控件表达
  - 三种标记：影响报告（affects_report）、⚗（experimental）、✻（与出厂默认不同）

Web 特有能力的图样：顶部工具条（说明密度 / 标记 / 主题）、域跳转、关键词筛选、
块级计数（N 项 · M 开）、窄屏单列排版。

用法::

    .venv/bin/python docs/plan/config-panel-mockup/web_mock_build.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

import sys

sys.path.insert(0, str(REPO))

from src.python.config import (  # noqa: E402
    get_config,
    get_default,
    get_llm_config,
    get_llm_providers,
    is_enable_action,
    is_enable_fund_deep_analysis,
    is_enable_history,
    is_enable_news,
    is_enable_portfolio_evolution,
    resolve_output_dir,
)
from src.python.config._llm_settings_defaults import _DEFAULT_LLM_SETTINGS  # noqa: E402
from src.python.config.anonymizer import ANONYMIZATION_MODE_DESCRIPTIONS  # noqa: E402
from src.python.config.edit_ops import LLM_TUNING_SPECS  # noqa: E402
from src.python.config.features import (  # noqa: E402
    GROUP_LABELS,
    GROUP_ORDER,
    feature_switch_registry,
    is_feature_enabled,
)
from src.python.core.registry import get_llm_module_names  # noqa: E402


SECTION_LABELS = {
    "enable_fund_deep_analysis": ("基金深度分析", is_enable_fund_deep_analysis),
    "enable_news": ("市场新闻", is_enable_news),
    "enable_history": ("组合历史走势+回撤", is_enable_history),
    "enable_portfolio_evolution": ("组合演进", is_enable_portfolio_evolution),
    "enable_action": ("行动建议", is_enable_action),
}
SECTION_DESCS = {
    "enable_fund_deep_analysis": "基金业绩分析章：基金深度、持仓穿透与归因（关闭即整章隐藏）",
    "enable_news": "市场新闻章：热点抓取、摘要与持仓关联（关闭即整章隐藏）",
    "enable_history": "组合历史走势与回撤章：多期净值、回撤区间与区间收益",
    "enable_portfolio_evolution": "组合演进章：多期快照对比、变化摘要与结构演变",
    "enable_action": "行动建议章：基于持仓、行情与估值的操作建议与理由",
}
PATH_LABELS = {"holdings_dir": "持仓信息目录", "holdings_filename": "持仓信息文件名", "output_dir": "报告输出目录"}
PATH_DESCS = {
    "holdings_dir": "持仓 Excel 所在目录（相对项目根或绝对路径）",
    "holdings_filename": "该目录下要读取的持仓文件名；每个工作表 = 一个账户",
    "output_dir": "报告输出目录（相对项目根或绝对路径）",
}
DEBATE_KEYS = ("llm_debate_procon", "llm_debate_conditional")

#: 需要默认显副行的阈值（注册表尚未提供 needs_hint 字段前，用说明长度作代理）
HINT_MIN_LEN = 30


def _needs_hint(desc: str) -> bool:
    return len(desc) >= HINT_MIN_LEN


def _flag_item(flag: str) -> dict:
    d = feature_switch_registry[flag]
    on = is_feature_enabled(flag)
    return {
        "key": flag,
        "label": d.label,
        "desc": d.desc,
        "on": on,
        "default": d.default,
        "affects": d.affects_report,
        "exp": d.experimental,
        "needs_hint": _needs_hint(d.desc),
    }


def _section_items(config: dict) -> list[dict]:
    return [
        {
            "key": key,
            "label": label,
            "desc": SECTION_DESCS[key],
            "on": bool(getter(config)),
            "default": True,
            "affects": True,
            "exp": False,
            "needs_hint": False,
        }
        for key, (label, getter) in SECTION_LABELS.items()
    ]


def _llm_items(llm_cfg: dict) -> list[dict]:
    enabled = (llm_cfg or {}).get("enabled_llm") or {}
    items = []
    for sfx, name in get_llm_module_names().items():
        items.append(
            {
                "key": sfx,
                "label": name,
                "desc": f"LLM 分析章节：关闭即整章隐藏（写入 enabled_llm.{sfx}）",
                "on": bool(enabled.get(sfx, True)),
                "default": bool(_DEFAULT_LLM_SETTINGS.get("enabled_llm", {}).get(sfx, True)),
                "affects": True,
                "exp": False,
                "needs_hint": False,
            }
        )
    return items


def _tuning_items(llm_cfg: dict) -> list[dict]:
    out = []
    for key, spec in LLM_TUNING_SPECS.items():
        default = spec.get("default", 0)
        out.append(
            {
                "key": key,
                "label": spec["label"],
                "desc": spec.get("hint", ""),
                "value": (llm_cfg or {}).get(key, default),
                "default": default,
                "min": spec["min"],
                "max": spec["max"],
                "step": 1 if spec["kind"] == "int" else 0.1,
                "needs_hint": True,
            }
        )
    return out


def build_data() -> dict:
    config = get_config()
    llm_cfg = get_llm_config() or {}
    providers_cfg = get_llm_providers()
    providers = [p for p in (providers_cfg.get("providers") or []) if isinstance(p, dict)]
    providers.sort(key=lambda p: (p.get("priority", 99), 0))

    flags = {
        flag: {**_flag_item(flag), "group": feature_switch_registry[flag].group}
        for flag in feature_switch_registry
        if flag != "doctor_check"  # 系统自检恒上屏，无该开关
    }
    debate = [flags[k] for k in DEBATE_KEYS if k in flags]
    for item in debate:
        item["sub_of"] = "expert_review"

    def _group(name: str, exclude: tuple[str, ...] = ()) -> list[dict]:
        return [item for flag, item in flags.items() if item["group"] == name and flag not in exclude]

    # 现有实现：辩论仍在「分析增强」组，`doctor_check` 仍在「机制与诊断」组
    groups_current = {name: _group(name) for name in GROUP_ORDER}
    # 目标设计：辩论作为 LLM 章节子项；危机回放归市场与估值；报告页追问归呈现与交互
    regroup = {
        "cost_position": "portfolio", "fund_purchase_limit": "portfolio",
        "cost_lots": "portfolio", "risk_adjusted_excess": "portfolio",
        "market_temperature": "market", "valuation_percentile": "market",
        "prosperity_framework": "market", "crisis_replay": "market",
        "candidate_compare": "fund_style", "industry_beta": "fund_style",
        "factor_catalog": "fund_style",
        "event_window_impact": "event_summary", "market_sentiment": "event_summary",
        "data_quality": "event_summary", "summary_highlights": "event_summary",
    }
    for key, grp in regroup.items():
        if key in flags:
            flags[key]["group"] = grp
    standalone = _group("standalone")
    related_keys = {"whatif_trade_cost"}
    chapters = [item for item in standalone if item["key"] not in related_keys]
    related = [item for item in standalone if item["key"] in related_keys]
    presentation = _group("presentation") + [item for flag, item in flags.items() if flag == "report_qa"]
    mechanism = _group("mechanism", exclude=("report_qa",))
    groups_proposed = {
        "portfolio": _group("portfolio"),
        "market": _group("market"),
        "fund_style": _group("fund_style"),
        "event_summary": _group("event_summary"),
        "standalone_chapters": chapters,
        "standalone_related": related,
        "presentation": presentation,
        "mechanism": mechanism,
    }

    paths = [
        {
            "key": key,
            "label": PATH_LABELS[key],
            "desc": PATH_DESCS[key],
            "value": resolve_output_dir(config) if key == "output_dir" else (config.get(key) or ""),
            "needs_hint": True,
        }
        for key in PATH_LABELS
    ]

    return {
        "config": config,
        "groupsCurrent": list(GROUP_ORDER),
        "groupsProposed": ["portfolio", "market", "fund_style", "event_summary", "presentation", "mechanism", "standalone_chapters", "standalone_related"],
        "groupTitles": {
            **GROUP_LABELS,
            "portfolio": "💼 持仓与交易（成本、申赎状态、成本收益、风险调整）",
            "market": "📈 市场与估值（温度、估值分位、景气度、危机回放）",
            "fund_style": "🧩 基金与风格（候选比较、行业 Beta、因子目录）",
            "event_summary": "📰 事件与摘要（事件窗、情绪热点、数据质量、本期要点）",
            "presentation": "🧭 呈现与交互（图表轴值 / 报告页追问）",
            "mechanism": "⚙ 机制与质量（提示词注入 / 输出评级）",
            "standalone_chapters": "📑 默认关闭的整章（开启后出现）",
            "standalone_related": "🔗 关联产物（仅调仓模拟报告）",
        },
        "flags": flags,
        "groupsCurrent": groups_current,
        "groupsProposed": groups_proposed,
        "sections": _section_items(config),
        "llm": _llm_items(llm_cfg),
        "debate": debate,
        "paths": paths,
        "anonymization": {
            "mode": config.get("anonymization", {}).get("mode", "off")
            if isinstance(config.get("anonymization"), dict)
            else config.get("anonymization", "off"),
            "options": [{"key": k, "label": v} for k, v in ANONYMIZATION_MODE_DESCRIPTIONS.items()],
        },
        "indices": dict(config.get("comparison_indices") or get_default("comparison_indices") or {}),
        "providers": {
            "strategy": str(providers_cfg.get("strategy") or "priority"),
            "items": [{"name": p.get("name"), "provider": p.get("provider"), "priority": p.get("priority", 99)} for p in providers],
        },
        "tuning": _tuning_items(llm_cfg),
    }


# ── 编排：两份页面的域/块顺序 ──────────────────────────────
PROPOSED_DOMAINS = [
    {
        "title": "报告内容",
        "hint": "改这里会改变报告里出现什么：章节显隐（顶层 / LLM / 默认关闭的整章 / 关联产物）与章节内内容",
        "tui": "TUI：[C] 报告章节显隐 + [S] 报告章节内容",
        "blocks": ["sections", "llm", "standalone_chapters", "standalone_related", "features.portfolio", "features.market", "features.fund_style", "features.event_summary"],
    },
    {
        "title": "呈现与机制",
        "hint": "只改呈现口径、匿名化与机制接缝：内容主体不变或仅影响入口显隐",
        "tui": "TUI：[S] 呈现与交互 / 机制与质量 + [G]→[A]",
        "blocks": ["anonymization", "features.presentation", "features.mechanism"],
    },
    {
        "title": "数据与线路",
        "hint": "数据从哪读、跟什么基准比、LLM 走哪条线路",
        "tui": "TUI：[G]→[D]/[F]/[O]、[G]→[I]、[G]→[L] 第 7 项",
        "blocks": ["paths", "indices", "providers"],
    },
    {
        "title": "LLM 运行",
        "hint": "LLM 调用的运行约束（并发 / 重试 / 预算）",
        "tui": "TUI：[G]→[L] 1-6",
        "blocks": ["tuning"],
    },
    {
        "title": "运行与诊断",
        "hint": "日志写盘与控制台输出；级别与轮转在下次启动生效，查看器默认项即时生效",
        "tui": "TUI：[D]→[L]",
        "blocks": ["logging"],
    },
]

CURRENT_BLOCKS = [
    ("paths", "路径与文件"),
    ("sections", "报告章节"),
    ("features.presentation", None),
    ("features.analysis", None),
    ("features.standalone", None),
    ("features.mechanism", None),
    ("anonymization", "持仓匿名化"),
    ("indices", "对比指数池"),
    ("providers", "LLM 多链线路优先级"),
    ("tuning", "LLM 调优参数"),
    ("llm", "LLM 分析章节"),
]

BLOCK_TITLES_PROPOSED = {
    "sections": "顶层章节（5 章）",
    "llm": "LLM 章节（7 章 · 智囊团下含辩论子项）",
    "paths": "目录与文件",
    "indices": "对比基准指数",
    "providers": "多链线路优先级",
    "tuning": "运行参数（6 项）",
    "anonymization": "持仓匿名化",
}


def build_pages() -> None:
    data = build_data()
    payload = {
        "groupsCurrent": data["groupsCurrent"],
        "groupsProposed": data["groupsProposed"],
        "groupTitles": data["groupTitles"],
        "sections": data["sections"],
        "llm": data["llm"],
        "debate": data["debate"],
        "paths": data["paths"],
        "anonymization": data["anonymization"],
        "indices": data["indices"],
        "providers": data["providers"],
        "tuning": data["tuning"],
        "logging": {
            "levels": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            "viewerLevels": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "ALL"],
            "fileLevel": "INFO",
            "consoleLevel": "INFO",
            "maxMB": 10,
            "backupCount": 5,
            "viewerLevel": "INFO",
            "tailLines": 500,
        },
        "blockTitlesProposed": BLOCK_TITLES_PROPOSED,
        "domains": PROPOSED_DOMAINS,
        "currentBlocks": [{"id": b, "title": t} for b, t in CURRENT_BLOCKS],
        "groupOrderCurrent": data["groupsCurrent"],
        "hintMinLen": HINT_MIN_LEN,
    }
    js_data = json.dumps(payload, ensure_ascii=False)

    for filename, view, title, subtitle in (
        ("index.html", "proposed", "Web 配置面板 · 目标设计", "四域编排：报告内容 / 呈现与机制 / 数据与线路 / LLM 运行"),
        ("web-current.html", "current", "Web 配置面板 · 现有实现", "按存储文件编排：config.json → features.json 各组 → config.json → llm_settings.json"),
    ):
        html = (
            TEMPLATE.replace("{{TITLE}}", title)
            .replace("{{SUBTITLE}}", subtitle)
            .replace("{{VIEW}}", view)
            .replace("{{DATA}}", js_data)
        )
        (HERE / filename).write_text(html, encoding="utf-8")
        print(f"写出 {filename}（{view}）")


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}}</title>
<style>
:root {
  --bg: #f3f5f8; --surface: #fff; --surface-2: #f8fafc; --border: #d9dce1;
  --text: #1f2328; --text-secondary: #57606a; --primary: #1f6fb2; --accent: #0e7a5f;
  --warn: #9a6700; --focus: #0969da; --radius: 8px;
  --shadow: 0 1px 2px rgba(31,35,40,.05), 0 4px 16px rgba(31,35,40,.05);
  --font: "PingFang SC","Microsoft YaHei","Noto Sans SC",system-ui,-apple-system,sans-serif;
}
[data-theme="dark"] {
  --bg: #121212; --surface: #1e1e1e; --surface-2: #191919; --border: #3a3a3a;
  --text: #e0e0e0; --text-secondary: #c0c0c0; --accent: #6ecf9f; --warn: #f0a35e;
  --shadow: 0 1px 2px rgba(0,0,0,.5);
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: var(--font); font-size: 14px; line-height: 1.7; }
.toolbar { position: sticky; top: 0; z-index: 10; display: flex; flex-wrap: wrap; gap: 16px; align-items: center;
  padding: 10px 20px; background: var(--surface); border-bottom: 1px solid var(--border); box-shadow: var(--shadow); }
.toolbar h1 { font-size: 15px; font-weight: 600; margin: 0 6px 0 0; }
.toolbar .sub { color: var(--text-secondary); font-size: 12px; }
.seg { display: inline-flex; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
.seg button { border: 0; background: var(--surface); color: var(--text-secondary); font: inherit; font-size: 12px; padding: 4px 10px; cursor: pointer; }
.seg button + button { border-left: 1px solid var(--border); }
.seg button[aria-pressed="true"] { background: var(--primary); color: #fff; }
.filter { border: 1px solid var(--border); border-radius: 6px; background: var(--surface); color: var(--text);
  font: inherit; font-size: 12px; padding: 4px 8px; flex: 1 1 200px; min-width: 160px; }
.wrap { max-width: 1080px; margin: 0 auto; padding: 18px 20px 80px; }
.chips { display: flex; gap: 8px; flex-wrap: wrap; margin: 0 0 16px; }
.chips a { font-size: 12px; color: var(--text-secondary); text-decoration: none; border: 1px solid var(--border);
  border-radius: 999px; padding: 2px 10px; background: var(--surface); }
.chips a:hover { color: var(--primary); border-color: var(--primary); }
.chips a.active { color: #fff; background: var(--primary); border-color: var(--primary); }
.saved { font-size: 12px; color: var(--ok); margin-left: 6px; }
.ref-row { display: flex; gap: 8px; align-items: center; padding: 4px 0; font-size: 12.5px; color: var(--text-secondary); }
.ref-row .mono { color: var(--text); }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow); padding: 20px 24px; }
.domain + .domain { margin-top: 26px; padding-top: 22px; border-top: 1px solid var(--border); }
.domain-title { margin: 0 0 2px; font-size: 16px; font-weight: 600; padding-left: 10px; border-left: 3px solid var(--primary); }
.domain-hint { margin: 0 0 4px 13px; font-size: 12px; color: var(--text-secondary); }
.domain-tui { margin: 0 0 14px 13px; font-size: 11.5px; color: var(--text-secondary); }
.block { border-top: 1px solid var(--border); padding: 12px 0 6px; }
.block:first-of-type { border-top: 0; }
.block-title { margin: 0 0 2px; font-size: 13px; font-weight: 600; color: var(--primary); }
.block-meta { margin: 0 0 8px; font-size: 11.5px; color: var(--text-secondary); }
.row { display: flex; gap: 8px; align-items: flex-start; padding: 3px 0; }
.row input[type="checkbox"], .row input[type="radio"] { margin-top: 6px; }
.row .label { display: flex; gap: 6px; align-items: baseline; flex-wrap: wrap; }
.desc { margin: 1px 0 6px 24px; font-size: 12px; line-height: 1.5; color: var(--text-secondary); }
.subrow { padding-left: 26px; }
.tag { font-size: 11px; border: 1px solid currentColor; border-radius: 4px; padding: 0 4px; white-space: nowrap; }
.tag.affects { color: var(--text-secondary); }
.tag.exp { color: var(--warn); }
.tag.changed { color: var(--primary); }
.mono { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px; }
.field { display: flex; gap: 8px; align-items: center; padding: 4px 0; flex-wrap: wrap; }
.field label { min-width: 8.5em; color: var(--text-secondary); font-size: 13px; }
.field input[type="text"], .field input[type="number"] { flex: 0 1 260px; min-width: 120px; padding: 5px 8px;
  border: 1px solid var(--border); border-radius: 6px; background: var(--surface); color: var(--text); font: inherit; font-size: 13px; }
.field input[type="number"] { flex: 0 0 96px; }
.field select { flex: 0 0 160px; padding: 5px 8px; border: 1px solid var(--border);
  border-radius: 6px; background: var(--surface); color: var(--text); font: inherit; font-size: 13px; }
.btn { border: 1px solid var(--border); border-radius: 6px; background: var(--surface-2); color: var(--text-secondary);
  font: inherit; font-size: 12px; padding: 3px 10px; cursor: pointer; }
.list-row { display: flex; gap: 8px; align-items: center; padding: 3px 0; font-size: 13px; }
.list-row .grow { flex: 1; }
.empty { color: var(--text-secondary); font-size: 12px; padding: 4px 0 8px; }
.note { margin: 8px 0 0; font-size: 12px; color: var(--text-secondary); }
.hidden { display: none !important; }
@media (max-width: 720px) { .wrap { padding: 14px 12px 60px; } .card { padding: 16px 14px; } }
</style>
</head>
<body>
<div class="toolbar">
  <h1>{{TITLE}}</h1>
  <span class="sub">{{SUBTITLE}}</span>
  <span class="sub" id="counts" aria-live="polite"></span>
  <span class="seg" id="seg-desc">
    <button data-v="all">全部说明</button>
    <button data-v="hint" aria-pressed="true">仅需提示项</button>
    <button data-v="off">关闭说明</button>
  </span>
  <span class="seg" id="seg-mark">
    <button data-v="on" aria-pressed="true">标记</button>
    <button data-v="off">无标记</button>
  </span>
  <span class="seg" id="seg-theme">
    <button data-v="light" aria-pressed="true">亮</button>
    <button data-v="dark">暗</button>
  </span>
  <input class="filter" id="filter" type="search" placeholder="筛选配置项（名称 / 说明 / 键名）">
</div>
<div class="wrap">
  <div class="chips" id="chips"></div>
  <div class="card" id="panel"></div>
  <p class="note" id="footnote"></p>
</div>
<script>
var VIEW = "{{VIEW}}";
var DATA = {{DATA}};
var state = { desc: 'hint', mark: 'on', theme: 'light', q: '' };

function currentGroups() { return VIEW === "proposed" ? DATA.groupsProposed : DATA.groupsCurrent; }

function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
  return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

function marks(item) {
  if (state.mark !== 'on') return '';
  var out = '';
  if (item.exp) out += '<span class="tag exp">⚗</span>';
  if (item.affects) out += '<span class="tag affects">影响报告</span>';
  if (item.default !== undefined && item.on !== undefined && item.on !== item.default) out += '<span class="tag changed">✻</span>';
  return out;
}

function desc(item, always) {
  if (state.desc === 'off' || !item.desc) return '';
  if (!always && state.desc === 'hint' && !item.needs_hint) return '';
  return '<p class="desc">' + esc(item.desc) + '</p>';
}

function row(item, type, extra) {
  var id = 'c-' + esc(item.key);
  var control;
  if (type === 'radio') {
    control = '<input type="radio" id="' + id + '" name="anon" ' + (item.on ? 'checked' : '') + '>';
  } else {
    control = '<input type="checkbox" id="' + id + '" ' + (item.on ? 'checked' : '') + '>';
  }
  return '<div class="row' + (extra && extra.sub ? ' subrow' : '') + '">' + control +
    '<div><div class="label"><label for="' + id + '">' + esc(item.label) + '</label>' + marks(item) + '</div>' +
    desc(item, extra && extra.always) + '</div></div>';
}

function blockHtml(id) {
  if (id === 'standalone_chapters' || id === 'standalone_related') {
    var items = currentGroups()[id] || [];
    if (!items.length) return '';
    var on = items.filter(function (i) { return i.on; }).length;
    var rows = items.map(function (i) {
      var r = row(i, 'bool');
      if (id === 'standalone_related') { r = r.replace('</div></div>', '（仅调仓模拟报告）</div></div>'); }
      return r;
    }).join('');
    return '<div class="block" data-block="' + id + '"><h3 class="block-title">' + esc(DATA.groupTitles[id]) +
      '</h3><p class="block-meta">' + items.length + ' 项 · ' + on + ' 开</p>' + rows + '</div>';
  }
  if (id.indexOf('features.') === 0) {
    var key = id.slice(9);
    var items = currentGroups()[key] || [];
    if (!items.length) return '';
    var on = items.filter(function (i) { return i.on; }).length;
    var rows = items.map(function (i) { return row(i, 'bool'); }).join('');
    return '<div class="block" data-block="' + id + '"><h3 class="block-title">' + esc(DATA.groupTitles[key]) + '</h3>' +
      '<p class="block-meta">' + items.length + ' 项 · ' + on + ' 开</p>' + rows + '</div>';
  }
  if (id === 'sections') {
    return block('sections', '顶层章节（5 章）', DATA.sections.map(function (i) { return row(i, 'bool'); }).join(''),
                 DATA.sections);
  }
  if (id === 'llm') {
    var rows = DATA.llm.map(function (m) {
      var html = row(m, 'bool');
      if (VIEW === 'proposed' && m.key === 'expert_review') {
        html += DATA.debate.map(function (d) { return row(d, 'bool', { sub: true }); }).join('');
      }
      return html;
    }).join('');
    return block('llm', 'LLM 章节（' + DATA.llm.length + ' 章 · 智囊团下含辩论子项）', rows, DATA.llm);
  }
  if (id === 'anonymization') {
    var opts = DATA.anonymization.options.map(function (o) {
      return row({ key: o.key, label: o.label, on: o.key === DATA.anonymization.mode, desc: '' }, 'radio');
    }).join('');
    return '<div class="block" data-block="anonymization"><h3 class="block-title">持仓匿名化</h3>' +
      '<p class="block-meta">单选 · 作用于整份报告</p>' + opts + '</div>';
  }
  if (id === 'paths') {
    var rows = DATA.paths.map(function (p) {
      return '<div class="field"><label>' + esc(p.label) + '</label>' +
        '<input type="text" value="' + esc(p.value) + '"><button class="btn">保存</button></div>' + desc(p, true);
    }).join('');
    return block('paths', '目录与文件', rows, DATA.paths);
  }
  if (id === 'indices') {
    var keys = Object.keys(DATA.indices);
    var rows = keys.map(function (code) {
      return '<div class="list-row"><span class="grow">' + esc(DATA.indices[code]) + '　<span class="mono">' +
        esc(code) + '</span></span><button class="btn">删除</button></div>';
    }).join('');
    return '<div class="block" data-block="indices"><h3 class="block-title">对比基准指数</h3>' +
      '<p class="block-meta">' + keys.length + ' 个基准 · 用于图表与超额收益对照</p>' + rows +
      '<div class="field"><input type="text" placeholder="指数代码（如 sh000905）">' +
      '<input type="text" placeholder="名称（如 中证500）"><button class="btn">添加</button></div></div>';
  }
  if (id === 'providers') {
    var p = DATA.providers;
    var rows = p.items.map(function (it, i) {
      return '<div class="list-row"><span class="grow">' + (i + 1) + '. ' + esc(it.name) + '（' + esc(it.provider) +
        '）<span class="mono"> priority ' + esc(it.priority) + '</span></span>' +
        '<button class="btn">▲</button><button class="btn">▼</button></div>';
    }).join('');
    return '<div class="block" data-block="providers"><h3 class="block-title">多链线路优先级</h3>' +
      '<p class="block-meta">策略「' + esc(p.strategy) + '」· 越靠前越优先</p>' + rows + '</div>';
  }
  if (id === 'logging') {
    var g = DATA.logging;
    function sel(name, value, options) {
      return '<select data-key="' + name + '">' + options.map(function (o) {
        return '<option' + (o === value ? ' selected' : '') + '>' + o + '</option>';
      }).join('') + '</select>';
    }
    var rows = '<div class="field"><label>写盘级别</label>' + sel('file.level', g.fileLevel, g.levels) + '</div>' +
      '<div class="field"><label>控制台级别</label>' + sel('console.level', g.consoleLevel, g.levels) + '</div>' +
      '<div class="field"><label>单文件上限 MB</label><input type="number" value="' + g.maxMB + '" min="1" max="1024"></div>' +
      '<div class="field"><label>备份份数</label><input type="number" value="' + g.backupCount + '" min="0" max="50"></div>' +
      '<div class="field"><label>查看器默认级别</label>' + sel('viewer.default_level', g.viewerLevel, g.viewerLevels) + '</div>' +
      '<div class="field"><label>查看器首屏行数</label><input type="number" value="' + g.tailLines + '" min="50" max="10000"></div>';
    return '<div class="block" data-block="logging"><h3 class="block-title">日志设置</h3>' +
      '<p class="block-meta">写入 logger.json · 级别与轮转下次启动生效</p>' + rows +
      '<p class="note">环境变量 INVEST_LOG_FILE_LEVEL / INVEST_LOG_CONSOLE_LEVEL 可临时覆盖级别，优先级高于本文件。</p>' +
      '<div class="ref-row">计价参考（只读）：<span class="mono">data/config/llm_pricing_ref.json</span>' +
      '<span>随供应商调价更新，本面板不提供编辑</span></div></div>';
  }
  if (id === 'tuning') {
    var rows = DATA.tuning.map(function (t) {
      return '<div class="field"><label>' + esc(t.label) + '</label>' +
        '<input type="number" value="' + esc(t.value) + '" min="' + t.min + '" max="' + t.max + '" step="' + t.step + '">' +
        '<button class="btn">保存</button><span class="mono" style="color:var(--text-secondary)">' + t.min + '~' + t.max + '</span></div>' +
        desc(t, true);
    }).join('');
    return block('tuning', '运行参数（6 项）', rows, DATA.tuning);
  }
  return '';
}

function block(id, title, rows, items) {
  var on = (items || []).filter(function (i) { return i.on; }).length;
  var meta = items ? items.length + ' 项 · ' + on + ' 开' : '';
  return '<div class="block" data-block="' + id + '"><h3 class="block-title">' + esc(title) + '</h3>' +
    (meta ? '<p class="block-meta">' + meta + '</p>' : '') + rows + '</div>';
}

function renderProposed() {
  var html = '';
  DATA.domains.forEach(function (d, i) {
    html += '<section class="domain" id="domain-' + i + '">' +
      '<h2 class="domain-title">' + esc(d.title) + '</h2>' +
      '<p class="domain-hint">' + esc(d.hint) + '</p>' +
      '<p class="domain-tui">' + esc(d.tui) + '</p>';
    d.blocks.forEach(function (b) { html += blockHtml(b); });
    html += '</section>';
  });
  return html;
}

function renderCurrent() {
  var html = '';
  DATA.currentBlocks.forEach(function (b) {
    if (b.id.indexOf('features.') === 0) {
      var key = b.id.slice(9);
      var items = currentGroups()[key] || [];
      if (!items.length) return;
      var on = items.filter(function (i) { return i.on; }).length;
      html += '<div class="block" data-block="' + b.id + '"><h3 class="block-title">' +
        esc(DATA.groupTitles[key]) + '</h3><p class="block-meta">' + items.length + ' 项 · ' + on + ' 开</p>' +
        items.map(function (i) { return row(i, 'bool'); }).join('') + '</div>';
      return;
    }
    var fragment = blockHtml(b.id);
    if (b.title && fragment) {
      fragment = fragment.replace(/<h3 class="block-title">[^<]*<\\/h3>/, '<h3 class="block-title">' + esc(b.title) + '</h3>');
    }
    html += fragment;
  });
  return html;
}

function applyFilter() {
  var q = state.q.trim().toLowerCase();
  document.querySelectorAll('.row, .field, .list-row').forEach(function (el) {
    el.classList.toggle('hidden', !!q && el.textContent.toLowerCase().indexOf(q) === -1);
  });
  document.querySelectorAll('.block').forEach(function (blk) {
    var visible = blk.querySelectorAll('.row:not(.hidden), .field:not(.hidden), .list-row:not(.hidden)').length;
    var hasStatic = blk.querySelector('.empty');
    blk.classList.toggle('hidden', !!q && visible === 0 && !hasStatic);
  });
  document.querySelectorAll('.domain').forEach(function (d) {
    var blocks = d.querySelectorAll('.block:not(.hidden)');
    d.classList.toggle('hidden', !!q && blocks.length === 0);
  });
}

function countSummary() {
  var total = 0, changed = 0;
  Object.keys(currentGroups()).forEach(function (k) {
    (currentGroups()[k] || []).forEach(function (i) {
      total++; if (i.on !== i.default) changed++;
    });
  });
  DATA.sections.forEach(function (i) { total++; if (i.on !== i.default) changed++; });
  DATA.llm.forEach(function (i) { total++; if (i.on !== i.default) changed++; });
  DATA.tuning.forEach(function (i) { total++; if (i.value !== i.default) changed++; });
  return { total: total, changed: changed };
}

function markActiveDomain() {
  var chips = document.querySelectorAll('#chips a[data-domain]');
  if (!chips.length) return;
  var current = null;
  document.querySelectorAll('.domain').forEach(function (d) {
    if (d.getBoundingClientRect().top < 160) current = d.id;
  });
  chips.forEach(function (a) { a.classList.toggle('active', a.dataset.domain === current); });
}

function render() {
  document.getElementById('panel').innerHTML = VIEW === 'proposed' ? renderProposed() : renderCurrent();
  var c = countSummary();
  document.getElementById('counts').textContent = '共 ' + c.total + ' 项 · 已改 ' + c.changed + ' 项';
  var chips = VIEW === 'proposed'
    ? DATA.domains.map(function (d, i) { return '<a href="#domain-' + i + '" data-domain="domain-' + i + '">' + esc(d.title) + '</a>'; }).join('')
    : '<a href="#panel">按存储文件顺序</a>';
  document.getElementById('chips').innerHTML = chips;
  document.getElementById('footnote').textContent = VIEW === 'proposed'
    ? '即时保存类失败自动回滚；目录/数值需点「保存」。日志级别与轮转下次启动生效，计价参考为只读文件。'
    : '块顺序按配置值所在文件排列；仅作现有实现的对照。';
  applyFilter();
  markActiveDomain();
}

document.querySelectorAll('.seg').forEach(function (seg) {
  var kind = seg.id.replace('seg-', '');
  seg.addEventListener('click', function (e) {
    var btn = e.target.closest('button');
    if (!btn) return;
    seg.querySelectorAll('button').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
    btn.setAttribute('aria-pressed', 'true');
    if (kind === 'theme') {
      state.theme = btn.dataset.v;
      document.documentElement.setAttribute('data-theme', state.theme);
      return;
    }
    state[kind] = btn.dataset.v;
    render();
  });
});

document.addEventListener('click', function (e) {
  var btn = e.target.closest('.btn');
  if (!btn) return;
  var host = btn.closest('.field, .list-row, .block');
  if (!host) return;
  var old = host.querySelector('.saved');
  if (old) old.remove();
  var tag = document.createElement('span');
  tag.className = 'saved';
  tag.textContent = '已保存';
  btn.insertAdjacentElement('afterend', tag);
  setTimeout(function () { tag.remove(); }, 1600);
});

document.getElementById('filter').addEventListener('input', function (e) {
  state.q = e.target.value;
  applyFilter();
});

render();
window.addEventListener('scroll', markActiveDomain, { passive: true });
</script>
</body>
</html>
"""


if __name__ == "__main__":
    build_pages()
