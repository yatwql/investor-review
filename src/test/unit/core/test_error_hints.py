"""`core/error_hints` —— 异常→用户提示的唯一映射（三渠道共用）单元测试。

判定口径：
- 类型优先于关键词（`FileNotFoundError("network path")` 说「文件未找到」而不是网络）；
- JSON 语法错误先于一般 ValueError；
- 网络类关键词大小写不敏感，命中即「网络连接异常」；
- 内部数据处理异常标 `log_detail=True`（需堆栈排查），用户可自解的错误不标。
"""

from __future__ import annotations

import json

import pytest

from src.python.core.error_hints import ErrorHint, hint_for

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


@pytest.mark.parametrize(
    ("exc", "expected", "log_detail"),
    [
        (PermissionError("denied"), "权限不足", False),
        (FileNotFoundError("no such file"), "文件未找到", False),
        (ImportError("no module"), "依赖", True),
        (json.JSONDecodeError("bad", "{}", 0), "JSON 语法错误", False),
        (ValueError("invalid value"), "数据处理异常", True),
        (KeyError("k"), "数据处理异常", True),
        (TypeError("bad type"), "数据处理异常", True),
        (AttributeError("x"), "数据处理异常", True),
        (RuntimeError("boom"), "操作异常", True),
    ],
)
def test_type_based_mapping(exc, expected, log_detail):
    hint = hint_for(exc)
    assert isinstance(hint, ErrorHint)
    assert expected in hint.message
    assert hint.log_detail is log_detail


@pytest.mark.parametrize(
    "keyword", ["connect", "timeout", "dns", "resolve", "network", "reset", "eof", "read timed out"]
)
def test_network_keywords_case_insensitive(keyword):
    assert "网络连接异常" in hint_for(ConnectionError(f"Some {keyword.upper()} problem")).message


def test_type_beats_keyword():
    """消息里含 network 但类型是文件不存在 → 按类型提示（否则用户去查网络，白费劲）。"""
    assert "文件未找到" in hint_for(FileNotFoundError("network share missing")).message


def test_none_and_empty_text():
    assert "操作异常" in hint_for(None).message
    assert "操作异常" in hint_for("").message
