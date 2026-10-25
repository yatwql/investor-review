"""配置文件与生成器模板的新旧对比。

**为什么需要**：`config.json` / `llm_settings.json` / `llm_providers.json` 的键与
注释只在**生成那一刻**写入，之后文件就冻结——代码侧调了菜单键（注释引用的字母
可能已不是当前键位）、补了新键（`notify` / `scheduler`）或改写了说明，用户手上
那份文件不会跟着变，于是注释与当前程序对不上，用户照着注释找菜单键会找不到。

本模块只做**只读判据**，供系统自检提示「该重生成配置了」：

- **缺键**：模板里有、文件里没有 → 新功能的配置项缺失（功能按默认值跑，但用户在
  文件里看不到、也无法就地调），属需要处理的问题。
- **缺说明**：模板里的注释文本在文件里找不到 → 文件是旧版产物，说明落后于当前版本，
  属提示（不影响运行，但注释可能指向已改名的菜单键或旧口径）。

不比较「文件有而模板没有」的注释：那是用户自己加的（或旧措辞），不能据此判落后，
否则用户每加一条注释就会被自检唠叨一次。
"""

from __future__ import annotations

import json
from typing import Any

from src.python.core.json_comments import strip_json_comments


def _comment_texts(text: str) -> set[str]:
    """抽取文本里的注释正文集合（字符串感知，不会把 ``https://…`` 当注释）。"""
    texts: set[str] = set()
    i = 0
    length = len(text)
    in_string = False
    while i < length:
        ch = text[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == "/" and i + 1 < length and text[i + 1] == "/":
            end = text.find("\n", i + 2)
            end = length if end < 0 else end
            frag = text[i + 2 : end].strip()
            if frag:
                texts.add(frag)
            i = end
            continue
        if ch == "/" and i + 1 < length and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            end = length if end < 0 else end
            frag = text[i + 2 : end].strip()
            if frag:
                texts.add(frag)
            i = end + 2
            continue
        i += 1
    return texts


def _keys_of(text: str) -> set[str] | None:
    """抽取文本解析后的顶层键集合；解析失败返回 ``None``（不可比较，不当成「全缺」）。"""
    try:
        data = json.loads(strip_json_comments(text))
    except (ValueError, TypeError):
        return None
    return set(data) if isinstance(data, dict) else None


def _diff(path: str, template: str) -> dict[str, Any]:
    """对比单个文件与模板，返回差异描述。

    文件本身解析不了（手改语法错、编码不对）时置 ``parse_error``：此时既不能说「缺键」
    也不能说「一致」——自检需要把「解析失败」与「落后」分开报，否则会把一个语法错
    误导成「缺了全部 40 个新键」。
    """
    with open(path, encoding="utf-8") as f:
        current = f.read()
    current_keys = _keys_of(current)
    template_keys = _keys_of(template) or set()
    parse_error = current_keys is None
    missing_keys = sorted(template_keys - (current_keys or set())) if not parse_error else []
    missing_comments = sorted(_comment_texts(template) - _comment_texts(current))
    return {
        "path": path,
        "missing_keys": missing_keys,
        "missing_comments": missing_comments,
        "parse_error": parse_error,
        "stale": bool(missing_keys or missing_comments or parse_error),
    }


def check_config_freshness() -> list[dict[str, Any]]:
    """对比可重生成的配置文件与当前模板。

    Returns:
        每个**存在且落后于模板**的文件一项：
        ``{"path", "missing_keys", "missing_comments", "parse_error", "stale"}``。
        文件不存在或与模板一致时不返回（不存在的文件由首次运行生成，不算「落后」；
        编码损坏或无法解码的文件跳过，由配置加载检查负责报错）。
    """
    from src.python.config._config_defaults import _build_template_from_defaults, get_config_path
    from src.python.config._core import get_config
    from src.python.config._llm_providers_defaults import _get_default_llm_providers_template
    from src.python.config._llm_settings_defaults import _get_default_llm_settings_template

    try:
        config = get_config()
    except Exception:  # noqa: BLE001 —— 自检链路必须吞掉一切异常
        return []

    targets = (
        (get_config_path(), _build_template_from_defaults()),
        (str(config.get("llm_settings_file") or ""), _get_default_llm_settings_template()),
        (str(config.get("llm_providers_file") or ""), _get_default_llm_providers_template()),
    )

    results: list[dict[str, Any]] = []
    for path, template in targets:
        if not path or not template:
            continue
        try:
            diff = _diff(path, template)
        except (OSError, UnicodeDecodeError):
            continue  # 文件不存在（首次运行）或编码不可解码（配置加载检查会单独报错）
        if diff["stale"]:
            results.append(diff)
    return results
