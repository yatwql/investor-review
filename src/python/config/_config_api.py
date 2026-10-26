"""渠道共享配置 API — 默认值查询、持仓/输出路径解析、正式源判定、本地状态标记。

这些函数是三渠道（CLI/TUI/Web）共用的**唯一**定位入口，渠道层不得自行拼接
路径或字面量回退。包入口 ``config/__init__.py`` 按原面 re-export，调用方导入
路径不变。
"""

from __future__ import annotations

from src.python.config._config_defaults import _DEFAULT_CONFIG
from src.python.config._core import get_config as _get_config


def get_default(key: str, *path: str):
    """返回配置默认值表中的默认值（``_DEFAULT_CONFIG`` 单一来源）。

    支持嵌套项：``get_default("history.lookback_days")`` 与
    ``get_default("history", "lookback_days")`` 等价；任一层缺失返回 None。

    Args:
        key: 顶层键名，或点分嵌套路径（如 ``"a.b.c"``）
        *path: 可选的逐层键名（与点分写法二选一，显式传参优先）
    """
    segs = (key, *path) if path else tuple(key.split("."))
    node: object = _DEFAULT_CONFIG
    for seg in segs:
        if not isinstance(node, dict) or seg not in node:
            return None
        node = node[seg]
    return node


def resolve_holdings_path(config: dict | None = None) -> str:
    """解析持仓文件路径：``holdings_dir`` + ``holdings_filename``（未配置项回退默认值表）。

    三渠道（CLI/TUI/Web）持仓定位的唯一入口——渠道层不得自行拼接或字面量回退。

    Args:
        config: 可选显式配置（渠道上下文传入其缓存配置）；不传时读全局配置。
    """
    import os

    if config is None:
        config = _get_config()
    holdings_dir = config.get("holdings_dir") or _DEFAULT_CONFIG.get("holdings_dir", "")
    holdings_filename = config.get("holdings_filename") or _DEFAULT_CONFIG.get("holdings_filename", "")
    return os.path.join(holdings_dir, holdings_filename)


def resolve_output_dir(config: dict | None = None, override: str | None = None) -> str:
    """解析报告输出目录：``override`` > ``config.output_dir`` > 出厂默认，统一绝对化。

    三渠道（CLI/TUI/Web）报告产物定位的唯一入口——渠道层不得自行写
    ``config.get("output_dir") or get_default(...) or "reports"`` 这类回退链
    （曾在 12 处各写一份：改默认值或加绝对化规则时必然漏改）。

    Args:
        config: 可选显式配置（渠道上下文传入其缓存配置）；不传时读全局配置。
        override: 调用方显式覆盖（如 CLI ``--output``）；空串视为未覆盖。

    Returns:
        绝对路径字符串（相对路径按当前工作目录解析）。
    """
    import os

    if config is None:
        config = _get_config()
    raw = str(override or "").strip() or str((config or {}).get("output_dir") or "").strip()
    if not raw:
        raw = str(_DEFAULT_CONFIG.get("output_dir") or "reports")
    return os.path.abspath(os.path.expanduser(raw))


def is_formal_holdings_source(config: dict | None = None) -> bool:
    """持仓源是否为正式持仓目录（``data/holdings/``）下的持仓文件。

    持仓快照是用户的长期历史状态（快照对比/组合演进/持仓变动复盘的数据底座），
    只应由正式持仓源写入与比对。demo/试算/临时持仓（路径不在正式目录下，含
    ``data/holdings/uploads/`` 上传暂存区）判定为非正式源——调用方据此跳过快照
    捕获与历史对比，防止幻影持仓污染真实快照历史（症状：未持有品种被报成清仓）。

    解析异常按非正式源处理（fail-closed：宁可少写、不误写用户历史）。

    Args:
        config: 配置字典；None 时读全局配置（与 ``resolve_holdings_path`` 同源解析）。
    """
    import os

    from src.python.core.constants import PROJECT_ROOT

    try:
        source = os.path.abspath(resolve_holdings_path(config))
        formal_dir = os.path.abspath(os.path.join(PROJECT_ROOT, "data", "holdings"))
        if source != formal_dir and not source.startswith(formal_dir + os.sep):
            return False
        # 上传暂存区虽在正式目录下，但内容为外部上传的试算/覆盖文件，非正式存量
        uploads_dir = os.path.abspath(os.path.join(formal_dir, "uploads"))
        return source != uploads_dir and not source.startswith(uploads_dir + os.sep)
    except Exception:
        return False


def get_local_flag(key: str) -> bool:
    """读取机器本地状态标记（公开 API，替代 ``config._local_state`` 私有模块直引）。"""
    from src.python.config._local_state import get_flag

    return get_flag(key)


def set_local_flag(key: str, value: bool) -> None:
    """写入机器本地状态标记（与 ``get_local_flag`` 同一公开面）。"""
    from src.python.config._local_state import set_flag

    set_flag(key, value)


__all__ = [
    "get_default",
    "resolve_holdings_path",
    "resolve_output_dir",
    "is_formal_holdings_source",
    "get_local_flag",
    "set_local_flag",
]
