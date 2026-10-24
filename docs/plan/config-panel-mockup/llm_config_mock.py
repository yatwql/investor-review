#!/usr/bin/env python3
"""生成 LLM 配置纵切图样（llm-config.html）——设计产物，不含任何生产代码改动。

数据来源：真实 `data/config/llm_settings.json` + 模块注册表。
v2 结构按设计文档的规则推导（defaults 取各模块众数、模块只留差异），
用于评审「文件会长什么样、能省多少行」。

用法::

    .venv/bin/python docs/plan/config-panel-mockup/llm_config_mock.py
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

from src.python.config import read_llm_settings_file  # noqa: E402
from src.python.core.registry import get_llm_module_names  # noqa: E402

PARAMS = [
    "model",
    "temperature",
    "max_tokens",
    "timeout",
    "cache_enabled",
    "output_brief",
    "system_prompt",
    "thinking_enabled",
    "thinking_budget",
    "reasoning_effort",
]
RUN_KEYS = {
    "llm_max_concurrency": "max_concurrency",
    "llm_max_thinking_concurrency": "thinking_concurrency",
    "max_retries": "max_retries",
    "llm_full_fail_retry_delay": "full_fail_retry_delay_sec",
    "llm_total_time_budget_sec": "time_budget_sec",
    "daily_cost_limit": "daily_cost_limit",
}
RUN_DEFAULTS = {
    "max_concurrency": 3,
    "thinking_concurrency": 2,
    "max_retries": 2,
    "full_fail_retry_delay_sec": 30,
    "time_budget_sec": 0,
    "daily_cost_limit": 0,
}


def load_flat() -> dict:
    snap = read_llm_settings_file()
    return snap[0] if snap else {}


def build_v2(flat: dict, modules: list[str]) -> dict:
    """按设计规则推导 v2：defaults = 程序内置默认（确定性），模块只写差异。"""
    from src.python.config._llm_settings_defaults import _DEFAULT_LLM_SETTINGS as builtin

    defaults: dict = {}
    for param in PARAMS:
        sample = next((builtin.get(f"{param}_{m}") for m in modules if f"{param}_{m}" in builtin), None)
        defaults[param] = sample

    enabled = flat.get("enabled_llm") or {}
    mods: dict = {}
    for m in modules:
        entry: dict = {"enabled": bool(enabled.get(m, True))}
        for param in PARAMS:
            key = f"{param}_{m}"
            if key not in flat:
                continue
            val = flat[key]
            if val == defaults.get(param):
                continue
            if param == "cache_enabled":
                entry["cache"] = val
            elif param == "thinking_enabled":
                entry.setdefault("thinking", {})["enabled"] = val
            elif param == "thinking_budget":
                entry.setdefault("thinking", {})["budget"] = val
            elif param == "reasoning_effort":
                entry.setdefault("thinking", {})["effort"] = val
            else:
                entry[param] = val
        mods[m] = entry

    run = {new: flat.get(old, RUN_DEFAULTS[new]) for old, new in RUN_KEYS.items()}

    # 设计归属：辩论的生成选项归智囊团模块，报告级预算归 runtime；计价表独立成文件
    debate = dict(flat.get("debate") or {})
    run["debate_limits"] = {
        "max_tokens_per_report": debate.pop("max_total_tokens_per_report", 72000),
        "call_timeout_override_sec": debate.pop("per_call_timeout_override", 90),
    }
    if debate:
        mods.setdefault("expert_review", {})["debate"] = debate

    advanced = {
        "fact_check": flat.get("fact_check") or {},
        "news_correlation": {"top_n": flat.get("news_correlation_top_n", 10)},
    }
    return {"schema_version": 2, "defaults": defaults, "modules": mods, "runtime": run, "advanced": advanced}


def render_v1(flat: dict, modules: list[str]) -> tuple[str, int, dict]:
    """扁平组织视图：按文件顺序逐键渲染，标注同一模块的键散落在哪几行。"""
    rows: list[str] = ['<span class="ln">// 扁平组织：顶层键按「参数 × 模块」平铺</span>']
    line_of: dict[str, list[int]] = {m: [] for m in modules}
    dup = 0
    lineno = 0
    for key, value in flat.items():
        lineno += 1
        text = f'  "{key}": {json.dumps(value, ensure_ascii=False)}'
        if len(text) > 76:
            text = text[:73] + "…"
        esc = html.escape(text)
        if key.startswith("enabled_llm") or key in ("debate", "fact_check", "pricing", "news_correlation_top_n"):
            rows.append(f'<span class="feat">{esc}</span>')
        elif key in RUN_KEYS:
            rows.append(f'<span class="rt">{esc}</span>')
        else:
            mod = next((m for m in modules if key.endswith("_" + m)), None)
            if mod:
                line_of[mod].append(lineno)
                idx = modules.index(mod) % 7
                rows.append(f'<span class="c{idx}">{esc}</span>')
            else:
                rows.append(esc)
    for mod, lines in line_of.items():
        if len(lines) > 1:
            dup += len(lines) - 1
    return "\n".join(rows), dup, line_of


def render_v2(v2: dict) -> str:
    """目标视图：features 内部结构原样移入，此处折叠以免淹没主线。"""
    compact = dict(v2)
    compact["advanced"] = {
        "debate": "…（原样移入）",
        "fact_check": "…（原样移入）",
        "pricing": "…（原样移入）",
        "news_correlation": {"top_n": v2["advanced"]["news_correlation"]["top_n"]},
    }
    text = json.dumps(compact, ensure_ascii=False, indent=2)
    out: list[str] = []
    for line in text.split("\n"):
        esc = html.escape(line)
        if '"schema_version"' in line:
            out.append(f'<span class="ln">{esc}</span>')
        elif re.match(r'\s*"(defaults|modules|runtime|advanced)"', line):
            out.append(f'<span class="head">{esc}</span>')
        elif re.match(r'\s{4}"[a-z_]+":\s*\{', line):
            out.append(f'<span class="mod">{esc}</span>')
        elif re.match(r'\s{6}"(thinking|news_correlation)"', line):
            out.append(f'<span class="nest">{esc}</span>')
        else:
            out.append(esc)
    return "\n".join(out)


def main() -> int:
    flat = load_flat()
    modules = list(get_llm_module_names())
    v2 = build_v2(flat, modules)
    v1_html, dup, line_of = render_v1(flat, modules)
    v2_html = render_v2(v2)
    v2_keys = 1 + len(v2["defaults"]) + len(v2["modules"]) + len(v2["runtime"]) + 4
    scatter = "　".join(f"{m} 占 {len(v)} 行" for m, v in line_of.items() if v)

    current = PAGE_CURRENT
    for token, value in {
        "{{FLAT}}": v1_html,
        "{{N_V1}}": str(len(flat)),
        "{{N_SCATTER}}": str(dup),
        "{{N_MOD}}": str(len(modules)),
        "{{SCATTER}}": html.escape(scatter),
    }.items():
        current = current.replace(token, value)
    out_current = HERE / "llm-config-current.html"
    out_current.write_text(current, encoding="utf-8")

    target = PAGE_TARGET
    for token, value in {
        "{{V2}}": v2_html,
        "{{N_V2}}": str(v2_keys),
        "{{N_MOD}}": str(len(modules)),
        "{{DEFAULTS}}": html.escape(json.dumps(v2["defaults"], ensure_ascii=False)),
        "{{RUNTIME}}": html.escape(json.dumps(v2["runtime"], ensure_ascii=False)),
    }.items():
        target = target.replace(token, value)
    out_target = HERE / "llm-config.html"
    out_target.write_text(target, encoding="utf-8")
    print(f"写出 {out_current}（现有：{len(flat)} 个顶层键，散落 {dup} 个）")
    print(f"写出 {out_target}（目标：{v2_keys} 个一级键，模块 {len(modules)}）")
    return 0


TEMPLATE_CSS = """
:root {
  --bg: #0d1117; --panel: #161b22; --border: #30363d; --text: #c9d1d9; --dim: #8b949e;
  --blue: #79c0ff; --green: #7ee787; --yellow: #ffd479; --red: #ff7b72; --orange: #f0883e;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, "Noto Sans Mono CJK SC", monospace;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; font-size: 14px; line-height: 1.7; }
header { padding: 18px 24px; border-bottom: 1px solid var(--border); background: var(--panel); }
header h1 { margin: 0 0 4px; font-size: 17px; font-weight: 600; }
header p { margin: 0; color: var(--dim); font-size: 12.5px; }
.stats { display: flex; gap: 26px; flex-wrap: wrap; padding: 14px 24px; border-bottom: 1px solid var(--border); }
.stat { font-size: 12.5px; color: var(--dim); }
.stat b { display: block; font-size: 19px; color: var(--text); font-variant-numeric: tabular-nums; }
.stat.warn b { color: var(--orange); }
main { padding: 20px 24px 60px; max-width: 1100px; }
h2 { font-size: 14px; margin: 0 0 8px; }
.sub { margin: 0 0 10px; color: var(--dim); font-size: 12px; }
pre { margin: 0 0 20px; background: #0b0f14; border: 1px solid var(--border); border-radius: 8px;
  padding: 14px 16px; font-family: var(--mono); font-size: 12.5px; line-height: 1.6; overflow-x: auto; }
.side { color: var(--dim); font-size: 11.5px; }
.dup { color: var(--orange); } .var { color: var(--green); } .feat { color: var(--blue); }
.rt { color: var(--yellow); } .head { color: var(--blue); font-weight: 600; } .mod { color: var(--green); }
.nest { color: var(--yellow); } .ln { color: var(--dim); }
.c0 { color: #79c0ff; } .c1 { color: #7ee787; } .c2 { color: #ffd479; }
.c3 { color: #ff9bce; } .c4 { color: #a5d6ff; } .c5 { color: #d2a8ff; } .c6 { color: #ffa657; }
.table { border-collapse: collapse; width: 100%; font-size: 12.5px; margin-bottom: 18px; }
.table th, .table td { border-bottom: 1px solid var(--border); padding: 5px 8px; text-align: left; }
.table th { color: var(--dim); font-weight: 600; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.card { border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; background: var(--panel); }
.card h3 { margin: 0 0 6px; font-size: 13px; }
.card p { margin: 4px 0; font-size: 12.5px; color: var(--dim); }
.card code { font-family: var(--mono); font-size: 12px; color: var(--text); }
"""

PAGE_CURRENT = (
    "<!DOCTYPE html>\n<html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
    "<title>LLM 配置 · 现有实现</title><style>" + TEMPLATE_CSS + "</style></head><body>"
    "<header><h1>LLM 配置 · 现有实现</h1>"
    "<p><code>data/config/llm_settings.json</code> 的扁平组织：顶层键按「参数 × 模块」平铺。</p></header>"
    '<div class="stats"><div class="stat">顶层键<b>{{N_V1}}</b></div>'
    '<div class="stat warn">同一模块散落的键<b>{{N_SCATTER}}</b></div>'
    '<div class="stat">模块数<b>{{N_MOD}}</b></div></div>'
    "<main><h2>扁平组织 · 参数为横切轴</h2>"
    '<p class="sub">{{SCATTER}}——改一个模块要在文件里跳着找。</p>'
    "<pre>{{FLAT}}</pre></main></body></html>"
)

PAGE_TARGET = (
    "<!DOCTYPE html>\n<html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
    "<title>LLM 配置 · 目标设计</title><style>" + TEMPLATE_CSS + "</style></head><body>"
    "<header><h1>LLM 配置 · 目标设计</h1>"
    "<p><code>llm_settings.json</code> 以模块为第一层：<code>defaults</code> 声明缺省，"
    "<code>modules</code> 只写差异，<code>runtime</code> 收运行参数，<code>advanced</code> 收高级选项；计价参考在独立的 <code>llm_pricing_ref.json</code>。</p></header>"
    '<div class="stats"><div class="stat">一级键<b>{{N_V2}}</b></div>'
    '<div class="stat">模块数<b>{{N_MOD}}</b></div></div>'
    "<main><h2>纵切组织 · 模块为第一层</h2>"
    '<p class="sub">蓝=分区，绿=模块，黄=嵌套子对象；模块段只写与 <code>defaults</code> 不同的项。</p>'
    "<pre>{{V2}}</pre>"
    "<h2>键位映射（兼容读取用）</h2>"
    '<table class="table"><thead><tr><th>扁平键</th><th>目标位置</th><th>说明</th></tr></thead><tbody>'
    "<tr><td><code>temperature_&lt;模块&gt;</code> 等 6 项</td><td><code>modules.&lt;模块&gt;.&lt;参数&gt;</code></td><td>模型/温度/长度/超时/简报/提示词</td></tr>"
    "<tr><td><code>cache_enabled_&lt;模块&gt;</code></td><td><code>modules.&lt;模块&gt;.cache</code></td><td>段内已表达归属</td></tr>"
    "<tr><td><code>thinking_enabled/budget/reasoning_effort_&lt;模块&gt;</code></td><td><code>modules.&lt;模块&gt;.thinking.{enabled,budget,effort}</code></td><td>三者同属一个概念</td></tr>"
    "<tr><td><code>enabled_llm.&lt;模块&gt;</code></td><td><code>modules.&lt;模块&gt;.enabled</code></td><td>启停与参数同段</td></tr>"
    "<tr><td><code>llm_max_thinking_concurrency</code> 等 6 项</td><td><code>runtime.*</code></td><td>对应面板「LLM 调优参数」组</td></tr>"
    "<tr><td><code>debate</code> / <code>fact_check</code> / <code>pricing</code> / <code>news_correlation_top_n</code></td><td><code>advanced.*</code></td><td>高级选项（避免与 features.json 同名）</td></tr>"
    "</tbody></table>"
    '<div class="cards">'
    '<div class="card"><h3>缺省继承（三层，确定性）</h3>'
    "<p>模块值 → <code>defaults</code> → 代码内置默认。<code>defaults</code> 初值取程序内置默认，不做统计推断。</p>"
    "<p><code>{{DEFAULTS}}</code></p></div>"
    '<div class="card"><h3>运行约束段（＝面板「LLM 调优参数」）</h3>'
    "<p><code>{{RUNTIME}}</code></p>"
    "<p>面板 6 个调优项的标签与范围不变，写入落 <code>runtime.*</code>。</p></div>"
    '<div class="card"><h3>读写契约</h3>'
    "<p><code>get_llm_config()</code> 仍返回扁平视图，<code>llm/</code> 包零改动；"
    "写入反展平为纵切结构，写前 <code>.bak</code>。</p></div>"
    '<div class="card"><h3>未知内容保留</h3>'
    "<p>不认识的段与参数原样保留；<code>schema_version</code> 高于支持值时拒绝加载。</p></div>"
    "</div></main></body></html>"
)

if __name__ == "__main__":
    raise SystemExit(main())
