"""LLM Provider 多链默认配置模板 — llm_providers.json 缺省模板生成。

职责：
  提供 _DEFAULT_LLM_PROVIDERS 缺省值 dict 与 _get_default_llm_providers_template()
  模板函数（手工拼注释）。首次初始化时由 _core.py 的
  _ensure_llm_providers_file() 调用写入磁盘。

与 _llm_settings_defaults.py 同构：dict 存值 + 模板函数逐行拼注释，
保证缺省值与模板内容一致，新增/修改 provider 条目只动 dict（注释在
_PROVIDER_NOTES 里按 name 对齐）。
"""

from __future__ import annotations

import json
from typing import Any

# LLM Provider 多链缺省配置（与模板一一对应，确保一致性）
_DEFAULT_LLM_PROVIDERS: dict[str, Any] = {
    "strategy": "priority",
    "preferred_providers": {},
    "providers": [
        {
            "name": "deepseek-main",
            "provider": "claude",
            "credentials_ref": "deepseek-main",
            "priority": 10,
            "timeout": 120,
        },
        {
            "name": "opencode-go",
            "provider": "claude",
            "credentials_ref": "opencode-go",
            "priority": 20,
            "timeout": 120,
            "pacing": {"min_interval": 5, "max_concurrency": 1},
        },
    ],
}

#: 每条线路的专属说明（模板里写在对应条目上方；按 provider name 对齐，
#: 只写该线路的**稳定事实**——角色、端点类型、节流意图，不写换序后会失效的相对标注）。
_PROVIDER_NOTES: dict[str, str] = {
    "deepseek-main": "DeepSeek：Anthropic 兼容的按量付费端点，不额外限速",
    "opencode-go": (
        "OpenCode Go：订阅制编码中转（Anthropic 兼容）；pacing 令请求串行低频"
        "（间隔 ≥5s、在途 ≤1），去掉该段即无额外约束"
    ),
}


def _get_default_llm_providers_template() -> str:
    """返回带注释的默认 llm_providers.json 模板字符串。

    注释针对出厂的两条线路写：各自是什么端点、各自要去 llm_key.json 配哪个凭据块、
    pacing 为什么只加在第二条。链序仍只由 priority 升序决定，不写「主/备」这类
    换序后就会失效的相对标注——避免注释与字段相互矛盾。
    """
    d = _DEFAULT_LLM_PROVIDERS
    lines = ["{"]

    # ── 头部注释 ──
    lines.append("  // LLM Provider 多链配置：按 priority 升序逐条尝试，直到第一条成功返回")
    lines.append("  // 链序真值看 providers[].priority（数值小者靠前），与数组项摆放顺序无关；")
    lines.append("  // 调顺序用 [G]→[M] 面板 / Web 配置面 / --llm-provider-order，不必手改数组")
    lines.append("  //")
    lines.append("  // 两条线路都是 Anthropic 兼容端点，密钥与模型按 credentials_ref 写在 llm_key.json：")
    for entry in d["providers"]:
        lines.append(f"  //   {entry['credentials_ref']:<14} → llm_key.json 同名块（api_key / model / endpoint）")
    lines.append("  //")
    lines.append("  // pacing 是端点级节流（只约束本条目的端点），不写该段 = 无额外约束：")
    lines.append("  //   min_interval=两次请求最小间隔秒；jitter=间隔随机抖动比例(0~1)；max_concurrency=在途上限")
    lines.append("")

    # ── strategy / preferred_providers ──
    lines.append(f'  "strategy": {json.dumps(d["strategy"])},')
    lines.append(f'  "preferred_providers": {json.dumps(d["preferred_providers"])},')
    lines.append('  "providers": [')

    # ── providers 列表（每条上方写该线路的专属说明）──
    for idx, entry in enumerate(d["providers"]):
        note = _PROVIDER_NOTES.get(entry["name"])
        if note:
            lines.append(f"    // {note}")
        lines.append("    {")
        items = list(entry.items())
        for i, (key, val) in enumerate(items):
            comma = "," if i < len(items) - 1 else ""
            lines.append(f'      "{key}": {json.dumps(val, ensure_ascii=False)}{comma}')
        closing = "    }," if idx < len(d["providers"]) - 1 else "    }"
        lines.append(closing)

    lines.append("  ]")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)
