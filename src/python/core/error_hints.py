"""异常 → 用户提示的唯一映射（三渠道共性诊断规则）。

判定口径：把「同一故障该怎么跟用户说」从渠道层收敛到这里——TUI 上屏、CLI 的错误行、
Web 的信封 message 都取同一句话，避免同一故障在三个渠道三种说法（此前关键词表只写在
`tui/tui_handlers.print_error_with_hint` 里，Web 走 error_code、CLI 直接打印异常串）。

纯函数、零依赖（只读异常类型与消息文本），可安全被任意层导入。
"""

from __future__ import annotations

from dataclasses import dataclass

#: 网络类关键字（大小写不敏感）：命中即按「网络连接异常」提示
_NETWORK_KEYWORDS = (
    "connect",
    "timeout",
    "dns",
    "resolve",
    "network",
    "read timed out",
    "eof",
    "reset",
)


@dataclass(frozen=True)
class ErrorHint:
    """一条用户提示：`message` 面向用户；`advice` 可选下一步；`log_detail` 是否记堆栈。

    `log_detail` 只对「内部数据处理异常」为真——这类异常对用户不可解释、需留堆栈
    供排查；网络/权限/文件不存在/JSON 语法属用户可自解的情形，不写堆栈噪声。
    """

    message: str
    advice: str | None = None
    log_detail: bool = False


def hint_for(exc: BaseException | str | None) -> ErrorHint:
    """把异常（或其消息）翻成用户可执行的提示。

    顺序敏感：先按异常类型判（权限/文件/JSON/导入），再按消息关键字判网络，
    最后兜底「操作异常」。类型判定优先于关键字——``FileNotFoundError`` 的消息里
    也可能含 "network" 之类的词，按类型说才准确。

    Args:
        exc: 异常实例或异常消息文本；None 视为未知异常。

    Returns:
        :class:`ErrorHint`（永不返回 None：兜底提示保证调用方一定有话可说）。
    """
    if isinstance(exc, PermissionError):
        return ErrorHint("文件读取/写入权限不足", "请检查文件或目录的权限设置")
    if isinstance(exc, FileNotFoundError):
        return ErrorHint("文件未找到，请检查路径是否正确")
    if isinstance(exc, ImportError):
        return ErrorHint("模块加载失败，请检查依赖是否完整安装", "pip install -r requirements.txt", log_detail=True)
    if isinstance(exc, ValueError) and "json" in type(exc).__name__.lower():
        return ErrorHint("配置文件格式错误（JSON 语法错误）", "请检查配置文件是否为有效 JSON 格式")
    # 网络关键字先于泛型 ValueError：``ValueError("cannot connect to host")`` 是网络故障，
    # 说成「数据处理异常」会把用户引向错误方向
    message = str(exc or "").lower()
    if any(keyword in message for keyword in _NETWORK_KEYWORDS):
        return ErrorHint("网络连接异常，请检查网络后重试")

    if isinstance(exc, (KeyError, AttributeError, TypeError, ValueError)):
        return ErrorHint("数据处理异常，详情请查看日志文件 logs/app.log", log_detail=True)

    return ErrorHint("操作异常，详情请查看日志文件 logs/app.log", log_detail=True)
