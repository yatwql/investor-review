"""含注释 JSON 的文本编辑引擎（`config/_json_patch.py`）——字段级替换与顶层键扫描契约。

这套原语是「写回配置时不冲掉用户注释/空白」的唯一实现，也是唯一在**原文上做正则与
括号扫描**的模块：口径错了不会报错，只会把文件写坏。故逐层直测：

  - `_detect_indent_unit`：沿用文件现有缩进（注释行、空行、单行压缩的兜底）；
  - `_skip_ws_and_comments` / `_find_top_level_value_span` / `_find_value_end` /
    `_find_top_level_close_brace`：注释感知、字符串感知的边界定位（嵌套键与字符串
    内的同名片段不得误匹配）；
  - `_update_json_raw_text` / `_patch_config_key` / `_remove_top_level_key`：替换/追加/
    删除三种写回动作后，文本仍可用 `json_comments.loads` 解析，且区块外注释与顺序不变。
"""

from __future__ import annotations

import pytest

from src.python.config._json_patch import (
    _detect_indent_unit,
    _find_top_level_close_brace,
    _find_top_level_value_span,
    _find_value_end,
    _patch_config_key,
    _remove_top_level_key,
    _skip_ws_and_comments,
    _update_json_raw_text,
)
from src.python.core.json_comments import loads

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]

_TWO_SPACE = """{
  // 分组：基础
  "alpha": 1,
  "opts": {
    "x": 1,
    "list": [1, 2]
  },
  "tail": "end"
}
"""

_FOUR_SPACE = """{
    // 四空格风格
    "alpha": 1,
    "tail": "end"
}
"""


class TestDetectIndentUnit:
    def test_uses_first_indented_non_comment_line(self):
        assert _detect_indent_unit(_TWO_SPACE) == 2
        assert _detect_indent_unit(_FOUR_SPACE) == 4

    def test_falls_back_when_minified_or_comment_only(self):
        assert _detect_indent_unit('{"alpha":1}', default=2) == 2
        assert _detect_indent_unit("{\n// 只有注释\n}", default=2) == 2


class TestSkipWsAndComments:
    def test_skips_line_and_block_comments(self):
        text = ' \n// 行注释\n/* 块\n注释 */ "k": 1'
        assert text[_skip_ws_and_comments(text, 0)] == '"'

    def test_returns_length_for_unterminated_block_comment(self):
        text = "{ /* 未闭合"
        assert _skip_ws_and_comments(text, 2) == len(text)

    def test_stops_immediately_at_real_token(self):
        text = '"k": 1'
        assert _skip_ws_and_comments(text, 0) == 0


class TestFindTopLevelValueSpan:
    def test_finds_scalar_span(self):
        span = _find_top_level_value_span(_TWO_SPACE, "alpha")
        assert span is not None
        assert _TWO_SPACE[span[0] : span[1]].strip() == "1"

    def test_finds_structural_span_with_nested_member(self):
        span = _find_top_level_value_span(_TWO_SPACE, "opts")
        assert span is not None
        assert loads("{ " + '"opts": ' + _TWO_SPACE[span[0] : span[1]] + " }")["opts"]["list"] == [1, 2]

    def test_nested_key_is_not_top_level(self):
        """`opts.x` 不是顶层成员：只认深度 1 的键。"""
        assert _find_top_level_value_span(_TWO_SPACE, "x") is None

    def test_same_text_inside_string_or_comment_is_ignored(self):
        text = '{\n  "note": "alpha: 99",\n  // "alpha": 42\n  "alpha": 7\n}'
        span = _find_top_level_value_span(text, "alpha")
        assert span is not None
        assert text[span[0] : span[1]].strip() == "7"

    def test_missing_key_returns_none(self):
        assert _find_top_level_value_span(_TWO_SPACE, "nope") is None

    def test_backslash_in_key_does_not_break_scan(self):
        """含转义反斜杠的合法键：扫到目标键仍能定位（不得被前一个键的转义吞掉）。"""
        text = '{\n  "a\\\\b": 1,\n  "alpha": 2\n}'
        assert loads(text)["a\\b"] == 1
        span = _find_top_level_value_span(text, "alpha")
        assert span is not None
        assert text[span[0] : span[1]].strip() == "2"

    def test_malformed_string_slice_does_not_raise(self):
        """人工改坏的转义不得让扫描抛异常（返回值只为 None，不影响「找不到键」语义）。"""
        text = '{\n  "a\\"b": 1,\n  "alpha": 2\n}'
        assert _find_top_level_value_span(text, "alpha") is None or isinstance(
            _find_top_level_value_span(text, "alpha"), tuple
        )


class TestFindValueEnd:
    def test_scalar_stops_at_comma(self):
        text = '1,\n  "b": 2'
        assert text[_find_value_end(text, 0)] == ","

    def test_last_scalar_stops_at_object_close(self):
        text = "2\n  }"
        assert text[_find_value_end(text, 0) :].lstrip().startswith("}")

    def test_brackets_inside_string_do_not_end_value(self):
        """字符串里的 `]` / `}` 不是结构符——本轮修复的正是这条口径。"""
        text = '["a]b", "c}d"], "next": 1'
        end = _find_value_end(text, 0)
        assert text[:end] == '["a]b", "c}d"]'
        assert loads('{"k": ' + text[:end] + "}")["k"] == ["a]b", "c}d"]

    def test_comment_inside_structure_is_skipped(self):
        text = '[1, // 注释里的 ]\n 2], "k": 1'
        assert text[: _find_value_end(text, 0)] == "[1, // 注释里的 ]\n 2]"

    def test_start_past_end_returns_start(self):
        assert _find_value_end("{}", 9) == 9


class TestFindTopLevelCloseBrace:
    def test_returns_outer_close_not_nested(self):
        close = _find_top_level_close_brace(_TWO_SPACE)
        assert close is not None
        assert _TWO_SPACE[close] == "}"
        assert _TWO_SPACE[close + 1 :].strip() == ""

    def test_brace_in_string_is_ignored(self):
        text = '{\n  "k": "}"\n}'
        close = _find_top_level_close_brace(text)
        assert close == len(text) - 1

    def test_returns_none_when_unbalanced(self):
        assert _find_top_level_close_brace('{"k": 1') is None


class TestUpdateJsonRawText:
    def test_scalar_replace_keeps_comments(self):
        raw = '{\n  // 保留我\n  "alpha": 1,\n  "tail": "end"\n}\n'
        out = _update_json_raw_text(raw, {"alpha": 1, "tail": "end"}, {"alpha": 5, "tail": "end"})
        assert "// 保留我" in out
        assert loads(out)["alpha"] == 5
        assert loads(out)["tail"] == "end"

    def test_dict_block_uses_file_indent(self):
        out = _update_json_raw_text(_TWO_SPACE, loads(_TWO_SPACE), {"opts": {"y": {"z": 3}}})
        assert loads(out)["opts"] == {"y": {"z": 3}}
        assert '\n    "y"' in out, "缩进单位应沿用文件的 2 空格"

    def test_four_space_file_stays_four_space(self):
        raw = '{\n    "opts": {\n        "x": 1\n    },\n    "tail": "end"\n}\n'
        out = _update_json_raw_text(raw, loads(raw), {"opts": {"k": {"n": 1}}})
        assert '\n        "k"' in out, "容器→容器替换的缩进单位应沿用文件的 4 空格"
        assert loads(out)["opts"] == {"k": {"n": 1}}

    def test_scalar_to_object_stays_valid_json(self):
        """标量→容器的替换走正则分支（内含固定 2 空格缩进）：结果只需合法，不要求版式自适应。"""
        out = _update_json_raw_text(_FOUR_SPACE, loads(_FOUR_SPACE), {"alpha": {"k": 1}})
        assert loads(out)["alpha"] == {"k": 1}
        assert loads(out)["tail"] == "end"

    def test_array_with_bracket_in_string_replaced_intact(self):
        raw = '{\n  "list": ["a]b"],\n  "tail": "end"\n}\n'
        out = _update_json_raw_text(raw, loads(raw), {"list": ["c", "d"]})
        assert loads(out) == {"list": ["c", "d"], "tail": "end"}

    def test_null_round_trip(self):
        raw = '{\n  "alpha": null,\n  "tail": 1\n}\n'
        out = _update_json_raw_text(raw, loads(raw), {"alpha": "now"})
        assert loads(out)["alpha"] == "now"
        back = _update_json_raw_text(out, loads(out), {"alpha": None})
        assert loads(back)["alpha"] is None

    def test_unchanged_values_are_not_touched(self):
        raw = '{\n  "alpha":    1,\n  "tail": 1\n}\n'
        assert _update_json_raw_text(raw, loads(raw), {"alpha": 1}) == raw


class TestPatchConfigKey:
    def test_replaces_existing_key_and_keeps_other_comments(self):
        out = _patch_config_key(_TWO_SPACE, "alpha", "9")
        assert loads(out)["alpha"] == 9
        assert "// 分组：基础" in out
        assert loads(out)["tail"] == "end"

    def test_appends_missing_key_with_comma(self):
        out = _patch_config_key(_TWO_SPACE, "added", '{"k": 1}')
        assert loads(out)["added"] == {"k": 1}
        assert loads(out)["tail"] == "end"

    def test_appends_into_empty_object(self):
        out = _patch_config_key("{\n}\n", "added", "true")
        assert loads(out) == {"added": True}

    def test_raise_when_top_level_close_missing(self):
        with pytest.raises(ValueError):
            _patch_config_key('{"alpha": 1', "added", "2")


class TestRemoveTopLevelKey:
    def test_removes_middle_entry_with_its_comment(self):
        raw = '{\n  "a": 1,\n  "b": 2, // 行尾注释\n  "c": 3\n}\n'
        span = _find_top_level_value_span(raw, "b")
        assert span is not None
        out = _remove_top_level_key(raw, "b", *span)
        assert loads(out) == {"a": 1, "c": 3}
        assert "行尾注释" not in out

    def test_removes_last_entry_and_cleans_trailing_comma(self):
        raw = '{\n  "a": 1,\n  "b": 2\n}\n'
        span = _find_top_level_value_span(raw, "b")
        assert span is not None
        out = _remove_top_level_key(raw, "b", *span)
        assert loads(out) == {"a": 1}

    def test_only_key_leaves_empty_object(self):
        raw = '{\n  "a": 1\n}\n'
        span = _find_top_level_value_span(raw, "a")
        assert span is not None
        assert loads(_remove_top_level_key(raw, "a", *span)) == {}
