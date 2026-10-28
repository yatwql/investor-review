"""跨进程 LLM 指纹基线 — 让「缓存键为什么变了」在进程重启后仍可回答。

问题：缓存未命中归因（`fingerprint_changed` / `ttl_expired` / `cache_miss`）原本只靠
**进程内存**里的上轮快照（`_LAST_FP_COMPONENTS` / `_PREV_MODULE_CACHE_KEY`）。每份报告
是一次独立进程，此路径下基线永远为空 → 键确实变了也只能落进 `ttl_expired`（实测
两轮之间 expert_review 键 `bb5e0593dabe…` → `d86f4195c09f…` 被记成 ttl_expired），
而「到底哪一段输入变了」拿不到任何证据。

做法：把上一轮的**指纹组件哈希 + 各模块缓存键**落一份小快照（`data/state/`），
下次进程启动时读它作基线：

- 键不同 ⇒ `fingerprint_changed`，并打出变化的组件名（哪一段输入变了）；
- 键相同但读不到内容 ⇒ `ttl_expired`（内容没变，只是老化）；
- 无快照（首次运行/文件损坏）⇒ `cache_miss`（冷启动，不臆测原因）。

快照只是**诊断输入**：读写失败一律降级为「无基线」，绝不参与缓存键构造，也不影响
生成主链路。
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any

from src.python.core.atomic_write import write_json_atomic
from src.python.core.constants import PROJECT_ROOT

logger = logging.getLogger("invest")

#: 快照落点（与其它运行状态同目录，git 忽略；删掉只影响归因可读性）
BASELINE_FILE = os.path.join(PROJECT_ROOT, "data", "state", "llm_fingerprint_snapshot.json")

_lock = threading.Lock()
_loaded: dict[str, Any] | None = None


def _path() -> str:
    """当前快照路径（模块级常量，测试可 monkeypatch 重定向）。"""
    return BASELINE_FILE


def reset_baseline_cache() -> None:
    """丢弃进程内缓存（报告边界/测试隔离用；下次读取重新落盘读）。"""
    global _loaded
    with _lock:
        _loaded = None


def load_baseline() -> dict[str, Any]:
    """读取上一轮快照；缺失/损坏/结构异常一律返回空字典（不抛错）。"""
    global _loaded
    with _lock:
        if _loaded is not None:
            return dict(_loaded)
        path = _path()
        data: dict[str, Any] = {}
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                data = raw
        except FileNotFoundError:
            data = {}
        except (OSError, json.JSONDecodeError) as e:  # 损坏快照只影响归因，不影响生成
            logger.debug("[fingerprint] 基线快照不可读（按无基线处理）：%s", e)
            data = {}
        _loaded = dict(data)
        return dict(data)


def baseline_components() -> dict[str, str]:
    """上一轮的指纹组件哈希表；无快照时为空字典。"""
    comps = load_baseline().get("components")
    return {str(k): str(v) for k, v in comps.items()} if isinstance(comps, dict) else {}


def baseline_module_key(module_key: str) -> str:
    """上一轮某模块的缓存键；无快照/无该模块时为空串。"""
    keys = load_baseline().get("keys")
    if not isinstance(keys, dict):
        return ""
    return str(keys.get(str(module_key or ""), "") or "")


def save_baseline(components: dict[str, str], keys: dict[str, str]) -> bool:
    """写入本轮基线快照（模型/指纹/键），供下个进程归因使用。

    Args:
        components: 本轮指纹组件哈希（`module_fingerprint.fingerprint_components`）。
        keys: 各模块本轮使用的缓存键。

    Returns:
        写入成功为 True；异常/空输入返回 False（只影响归因，不影响生成）。
    """
    global _loaded
    if not components and not keys:
        return False
    payload: dict[str, Any] = {
        "components": {str(k): str(v) for k, v in (components or {}).items()},
        "keys": {str(k): str(v) for k, v in (keys or {}).items() if v},
    }
    try:
        write_json_atomic(_path(), payload, log_tag="fingerprint", noun="指纹基线")
    except Exception:  # 快照只是诊断输入，写不进去不影响本轮
        logger.debug("[fingerprint] 基线快照写入失败（忽略）", exc_info=True)
        return False
    with _lock:
        _loaded = dict(payload)
    return True


def changed_components(current: dict[str, str], baseline: dict[str, str] | None = None) -> list[str]:
    """相对基线的变化组件名（升序）；无基线时返回空列表（不臆测）。"""
    base = baseline if baseline is not None else baseline_components()
    if not base:
        return []
    names = set(base) | set(current)
    return sorted(name for name in names if base.get(name) != current.get(name))
