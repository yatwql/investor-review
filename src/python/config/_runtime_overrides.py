"""运行期配置覆写（CLI 命令行的「仅本次运行」语义，不写盘）。

持久化编辑走 ``config/edit_ops.py``（TUI / Web / CLI ``config set``）——本模块只承载
进程内覆写：报告生成链路没有「按调用注入配置」的入口，命令行的一次性开关
（``--chapter`` / ``--anonymize``）在进程生命周期内叠加到 ``get_config()`` /
``get_llm_config()`` 的返回值上，进程退出即消失，也不进入配置缓存。

覆写值不参与写盘：``set_config`` 仍基于磁盘原文 patch，避免「临时开关被持久化」。
"""

from __future__ import annotations

from typing import Any

#: config.json 覆写（支持点分键，如 ``anonymization.mode``）
_config_overrides: dict[str, Any] = {}
#: llm_settings.json 的 ``enabled_llm.<模块>`` 覆写
_llm_enabled_overrides: dict[str, bool] = {}


def set_config_override(key: str, value: Any) -> None:
    """登记一个仅本进程生效的配置覆写（键重复时后者覆盖前者）。"""
    _config_overrides[key] = value


def set_llm_enabled_override(module: str, enabled: bool) -> None:
    """登记一个仅本进程生效的 LLM 章节开关覆写。"""
    _llm_enabled_overrides[module] = bool(enabled)


def config_overrides() -> dict[str, Any]:
    """当前 config 覆写快照（副本）。"""
    return dict(_config_overrides)


def llm_enabled_overrides() -> dict[str, bool]:
    """当前 LLM 章节覆写快照（副本）。"""
    return dict(_llm_enabled_overrides)


def reset_overrides() -> None:
    """清空全部覆写（测试隔离与进程内重入用）。"""
    _config_overrides.clear()
    _llm_enabled_overrides.clear()


def _set_dotted(target: dict[str, Any], key: str, value: Any) -> None:
    """按点分键写入嵌套 dict（沿途复制，调用方传入的浅副本不被串改）。"""
    parts = key.split(".")
    node = target
    for part in parts[:-1]:
        child = node.get(part)
        child = dict(child) if isinstance(child, dict) else {}
        node[part] = child
        node = child
    node[parts[-1]] = value


def apply_config_overrides(config: dict) -> dict:
    """把覆写叠加到配置副本上（无覆写时原样返回，零拷贝开销）。"""
    if not _config_overrides:
        return config
    merged = dict(config)
    for key, value in _config_overrides.items():
        _set_dotted(merged, key, value)
    return merged


def apply_llm_enabled_overrides(llm: dict | None) -> dict | None:
    """把 ``enabled_llm`` 覆写叠加到 LLM 配置副本上（None/无覆写原样返回）。"""
    if not isinstance(llm, dict) or not _llm_enabled_overrides:
        return llm
    merged = dict(llm)
    enabled = dict(merged.get("enabled_llm") or {})
    enabled.update(_llm_enabled_overrides)
    merged["enabled_llm"] = enabled
    return merged


__all__ = [
    "apply_config_overrides",
    "apply_llm_enabled_overrides",
    "config_overrides",
    "llm_enabled_overrides",
    "reset_overrides",
    "set_config_override",
    "set_llm_enabled_override",
]
