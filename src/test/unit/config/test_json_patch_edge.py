"""含注释 JSON 编辑引擎的异常输入（`config/_json_patch.py`）。

边界口径：配置是人工可编辑的文件，损坏形态必须**降级而非崩溃**——
扫描定位失败返回 `None` / 原样返回，只有「无法插入新键」这类不可降级
的动作才抛 `ValueError`（调用方据此提示用户重生成配置）。
"""

from __future__ import annotations

import pytest

from src.python.config._json_patch import (
    _find_top_level_close_brace,
    _find_top_level_value_span,
    _find_value_end,
    _patch_config_key,
    _remove_top_level_key,
    _skip_ws_and_comments,
    _update_json_raw_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_config, pytest.mark.edge]


class TestMalformedInputs:
    def test_unbalanced_braces_yield_none_or_raw(self):
        """括号不平衡：定位返回 None/长度，替换原样返回（绝不留半截文本）。"""
        broken = '{\n  "alpha": {"nested": 1\n'
        assert _find_top_level_close_brace(broken) is None
        assert _find_top_level_value_span(broken, "alpha") is not None  # value 起始仍可定位
        assert _update_json_raw_text(broken, {"alpha": {"nested": 1}}, {"alpha": {}}) == broken

    def test_unterminated_block_comment_consumes_rest(self):
        text = '{\n/* 没闭合\n  "alpha": 1\n}'
        assert _skip_ws_and_comments(text, text.index("/*")) == len(text)
        assert _find_top_level_value_span(text, "alpha") is None

    def test_line_comment_at_eof_is_skipped(self):
        text = '{\n  "alpha": 1\n}\n// 结尾注释无换行'
        assert _skip_ws_and_comments(text, text.index("//")) == len(text)

    def test_patch_raises_when_no_top_level_object(self):
        with pytest.raises(ValueError):
            _patch_config_key("[1, 2]", "alpha", "3")

    def test_remove_key_absent_is_noop_on_locator(self):
        raw = '{\n  "alpha": 1\n}\n'
        assert _find_top_level_value_span(raw, "missing") is None

    def test_value_end_inside_string_at_eof(self):
        """未闭合字符串一直扫到文本尾（返回长度，不抛）。"""
        text = '["a]b'
        assert _find_value_end(text, 0) == len(text)

    def test_crlf_text_patch_keeps_line_shape(self):
        """CRLF 文件：追加键后仍是 CRLF 行，不混入 LF。"""
        raw = '{\r\n  "alpha": 1\r\n}\r\n'
        out = _patch_config_key(raw, "beta", "2")
        assert "\r\n" in out
        assert not any(line.endswith("\n") and not line.endswith("\r\n") for line in out.splitlines(True)[:-1])

    def test_remove_from_single_line_object(self):
        raw = '{"alpha": 1, "beta": 2}'
        span = _find_top_level_value_span(raw, "beta")
        assert span is not None
        assert _remove_top_level_key(raw, "beta", *span).strip().startswith("{")
