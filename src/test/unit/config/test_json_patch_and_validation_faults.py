"""JSONC patch 扫描器与配置校验函数的分支容错测试。

覆盖契约（`config/_json_patch.py`）：
  - 区块替换：目标键不存在时原样返回（不改动文本）
  - 顶层键扫描：字符串内转义、块注释、不可解析的字符串片段都不误判结构符
  - 末位标量值扫描遇未闭合块注释时退到文本末尾（不越界）
  - 单行（压缩）对象删键、无顶层闭合花括号时的容错

覆盖契约（`config/_validation_llm.py`）：
  - 报告深度非法档位计数、`enabled_llm` 缺失视为正常
  - `param_violation` 对未登记参数与「区间声明非数值」的配置表缺陷不误报
  - 出厂默认查找的「模块段缺失 → defaults 段」回落链
  - `sanitize_document` 跳过非对象模块段，debate 段缺失时补齐容器，无默认值时删键

覆盖契约（`config/_validation_scalars.py`）：
  - 跨盘符无法相对化的路径保持绝对
  - 缓存类型注册表不可用时不对未知 TTL 键误报
  - 交易时段值类型非法、建仓日期非字符串或非法日期的告警
"""

from __future__ import annotations

import json
from unittest import mock

import pytest

from src.python.config import _json_patch, _validation_llm, _validation_scalars

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]


# ══════════════════════════════════════════════════════════════
# _json_patch
# ══════════════════════════════════════════════════════════════


class TestReplaceValueBlock:
    def test_missing_key_returns_text_unchanged(self):
        """目标键不在文本中时原样返回（不插入、不改动其它键）。"""
        text = '{\n  "a": 1\n}'

        assert _json_patch._replace_dict_block(text, "missing", {"x": 1}) == text


class TestScanersIgnoreEscapesAndComments:
    def test_unparsable_key_fragment_is_not_treated_as_target(self):
        """人工编辑出的非法转义片段在解析失败时按「非目标键」继续扫。"""
        raw = r'{"bad\x": 1, "target": {"k": 1}}'

        span = _json_patch._find_top_level_value_span(raw, "target")

        assert span is not None
        assert raw[span[0] : span[1]] == '{"k": 1}'

    def test_escaped_quote_inside_string_does_not_end_scan(self):
        """字符串内的转义引号不让键扫描提前结束。"""
        raw = '{"q": "a\\"b", "target": 2}'

        span = _json_patch._find_top_level_value_span(raw, "target")

        assert span is not None
        assert raw[span[0] : span[1]] == "2"

    def test_block_comment_before_key_is_skipped(self):
        """键前的块注释被跳过，键仍能定位。"""
        raw = '{\n  /* note */\n  "target": 1\n}'

        span = _json_patch._find_top_level_value_span(raw, "target")

        assert span is not None
        assert raw[span[0] : span[1]].strip() == "1"

    def test_escaped_quote_inside_nested_value(self):
        """结构值内部字符串的转义引号不提前闭合外层区块。"""
        raw = '{"target": {"k": "a\\"b"}}'

        span = _json_patch._find_top_level_value_span(raw, "target")

        assert span is not None
        assert raw[span[0] : span[1]] == '{"k": "a\\"b"}'

    def test_unterminated_block_comment_scan_stops_at_end(self):
        """标量值后面跟着未闭合块注释时扫描退到文本末尾（不越界、不抛异常）。"""
        raw = '{"target": 1 /* tail'

        assert _json_patch._find_value_end(raw, raw.index("1")) == len(raw)

    def test_block_comment_inside_structural_value_is_skipped(self):
        """结构值内部的块注释不被当成结束符（否则区块提前截断）。"""
        raw = '{"target": [1 /* c */, 2]}'

        span = _json_patch._find_top_level_value_span(raw, "target")

        assert span is not None
        assert raw[span[0] : span[1]] == "[1 /* c */, 2]"

    def test_escape_inside_scalar_string_value(self):
        """标量字符串值内的转义引号不让值扫描提前结束。"""
        raw = '{"target": "a\\"b", "after": 1}'

        span = _json_patch._find_top_level_value_span(raw, "target")

        assert span is not None
        assert raw[span[0] : span[1]] == '"a\\"b"'

    def test_line_comment_inside_scalar_value_is_skipped(self):
        """标量值后的行注释被跳过，值结束位置落回顶层闭合花括号。"""
        raw = '{"target": 1 // note\n}'

        end = _json_patch._find_value_end(raw, raw.index("1"))

        assert raw[end] == "}", "行注释不应被当成值的一部分或终止符"

    def test_close_brace_scan_skips_block_comment(self):
        """块注释里的花括号不计入顶层深度。"""
        raw = '{\n  /* } */\n  "a": 1\n}'

        assert _json_patch._find_top_level_close_brace(raw) == raw.rindex("}")


class TestRemoveTopLevelKeyOnSingleLineObject:
    def test_middle_key_removed_from_compact_object(self):
        """单行压缩对象删中间键：只删该条目与逗号，其余成员与闭合花括号保留。"""
        raw = '{"a": 1, "b": 2}'
        span = _json_patch._find_top_level_value_span(raw, "a")
        assert span is not None

        patched = _json_patch._remove_top_level_key(raw, "a", span[0], span[1])

        assert json.loads(patched) == {"b": 2}, "删除后仍须是合法 JSON 且只少一个键"


class TestDropTrailingMemberComma:
    def test_text_without_top_level_brace_returned_as_is(self):
        """找不到顶层闭合花括号时原样返回（调用方文本形态异常，不强行改写）。"""
        assert _json_patch._drop_trailing_member_comma('"a": 1') == '"a": 1'


# ══════════════════════════════════════════════════════════════
# _validation_llm
# ══════════════════════════════════════════════════════════════


class TestValidateLlmReportDepth:
    def test_invalid_level_counts_as_issue(self):
        """非法报告深度档位记一条问题（按默认档处理）。"""
        assert _validation_llm._validate_llm_report_depth({"llm_report_depth": "bogus"}, 0) == 1


class TestValidateEnableLlm:
    def test_missing_enabled_map_is_not_an_issue(self, monkeypatch):
        """llm_settings 缺 enabled_llm 段属正常（默认全启用），不计问题。"""
        monkeypatch.setattr(
            "src.python.config._llm_settings.get_llm_config",
            lambda: {"enabled_llm": None},
        )

        assert _validation_llm._validate_enable_llm(0) == 0


class TestParamViolationMisses:
    def test_unregistered_param_is_not_judged(self):
        """未登记的参数不参与范围校验（返回 None）。"""
        assert _validation_llm.param_violation("not_a_registered_param", 999) is None

    def test_non_numeric_bounds_do_not_judge_value(self, monkeypatch):
        """区间声明自身不是数值（配置表缺陷）时不拿它判用户值。"""
        monkeypatch.setitem(_validation_llm.LLM_PARAM_RANGES, "broken_bounds", (None, 5))

        assert _validation_llm.param_violation("broken_bounds", 100) is None


class TestModuleDefaultFallbackChain:
    def test_nested_param_falls_back_to_defaults_section(self):
        """模块段缺该嵌套参数时，按 defaults 段的同名尾路径回落。"""
        defaults = {"modules": {"m": {"thinking": {}}}, "defaults": {"budget": 2048}}

        assert _validation_llm._module_default(defaults, "m", "thinking.budget") == 2048

    def test_below_default_advisory_skipped_without_numeric_factory(self):
        """出厂默认缺失（非数值）时不给「低于默认」提示。"""
        assert _validation_llm._below_default_advisory("m", "max_tokens", 10, {}) is None


class TestSanitizeDocument:
    def test_non_object_module_is_skipped(self):
        """modules 段里的非对象条目跳过（不误判、不抛异常）。"""
        document = {"modules": {"bad": "not-a-dict"}}

        sanitized, issues = _validation_llm.sanitize_document(document, {})

        assert sanitized["modules"]["bad"] == "not-a-dict"
        assert issues == []

    def test_param_without_default_is_removed(self):
        """越界参数在出厂默认也缺失时删键（让下游走内置兜底）。"""
        document = {"modules": {"m": {"temperature": 99.0}}}

        sanitized, _issues = _validation_llm.sanitize_document(document, {})

        assert "temperature" not in sanitized["modules"]["m"]


# ══════════════════════════════════════════════════════════════
# _validation_scalars
# ══════════════════════════════════════════════════════════════


class TestDeabsolutizePaths:
    def test_cross_drive_path_stays_absolute(self, monkeypatch):
        """不同盘符无法计算相对路径时保持绝对路径（Windows 场景）。"""
        monkeypatch.setattr(
            _validation_scalars.os.path,
            "relpath",
            mock.Mock(side_effect=ValueError("path is on mount 'D:', start on mount 'C:'")),
        )
        key = sorted(_validation_scalars._PATH_CONFIG_KEYS)[0]
        absolute = "/tmp/some/absolute/holdings"
        config = {key: absolute}

        result = _validation_scalars._deabsolutize_paths(config)

        assert result[key] == absolute


class TestValidateCacheTtl:
    def test_registry_failure_does_not_flag_unknown_keys(self, monkeypatch):
        """缓存类型注册表不可用时不对未知 TTL 键误报（只做数值校验）。"""
        monkeypatch.setattr(
            "src.python.core.data_registry.get_registered_data_types",
            mock.Mock(side_effect=RuntimeError("registry broken")),
        )

        assert _validation_scalars._validate_cache_ttl({"cache_ttl": {"unknown_type": 3600}}, 0) == 0


class TestValidateMarketHours:
    def test_non_string_time_value_is_reported(self):
        """交易时段的 start/end 非字符串时逐项计数告警。"""
        config = {"market_hours": {"start": 930, "end": 1130}}

        assert _validation_scalars._validate_market_hours(config, 0) == 2


class TestValidateHoldingsStartDate:
    def test_non_string_value_is_reported(self):
        """建仓日期非字符串时告警并计一条问题。"""
        assert _validation_scalars._validate_holdings_start_date({"holdings_start_date": 20260101}, 0) == 1

    def test_valid_date_passes(self):
        """合法日期不产生问题。"""
        assert _validation_scalars._validate_holdings_start_date({"holdings_start_date": "2026-01-05"}, 0) == 0

    def test_invalid_date_is_reported(self):
        """非法日期形态告警并计一条问题。"""
        assert _validation_scalars._validate_holdings_start_date({"holdings_start_date": "2026-13-40"}, 0) == 1
