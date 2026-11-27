"""`scripts/_shared/exceptions.py` 单测：例外表的规范化加载、字段/到期校验、命中标记与陈旧自审。

共用设施的协议由四个检查脚本消费，故这里逐条钉住对外语义：读表失败的三类形态（JSON 非法
/ 顶层不是对象 / 未登记规则键）都要给出同形文案、`defaults` 段按「条目优先」合并、
`expiry` 用 `date.fromisoformat` 回环（不存在的日历日也算违规）、`is_excepted` 命中即记
`used`、`stale_findings` 只报未被查询过的条目。定位键 schema 两种形状各验一遍：单字段
`name` 与「文件路径 + 符号」三元组（规则名后以 `:` 内联）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    # 共享设施是扁平 import（`_shared.*`），注入 scripts/ 才能加载
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _shared.exceptions import (  # noqa: E402
    DEFAULT_STALE_DETAIL,
    ExceptionRule,
    ExceptionTable,
    load_exception_table,
    load_table,
    table_spec,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_NAME_RULE = ExceptionRule("demo-rule")
_TRIPLE_RULE = ExceptionRule("demo-triple", ("path", "name"), ":")

_ENTRY = {"name": "a.py::f", "owner": "o", "reason": "r", "expiry": "2027-06-30", "replacement": "x"}


def _write(path: Path, payload) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


class TestLoading:
    def test_missing_file_is_not_an_error(self, tmp_path):
        table = load_exception_table(tmp_path / "absent.json", (_NAME_RULE,))
        assert table.load_error == ""
        assert table.entries_of("demo-rule") == []

    def test_unparsable_json_reports_same_shape(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{ 不是 JSON", encoding="utf-8")
        table = load_exception_table(path, (_NAME_RULE,))
        assert "无法解析" in table.load_error
        assert "broken.json" in table.load_error

    def test_top_level_must_be_object(self, tmp_path):
        path = _write(tmp_path / "list.json", [{"name": "a"}])
        assert "顶层须为 JSON 对象" in load_exception_table(path, (_NAME_RULE,)).load_error

    def test_rule_value_must_be_array(self, tmp_path):
        path = _write(tmp_path / "obj.json", {"demo-rule": {"name": "a"}})
        assert "须为 JSON 数组" in load_exception_table(path, (_NAME_RULE,)).load_error

    def test_unknown_rule_key_is_a_load_error(self, tmp_path):
        """规则键拼错会让整族例外静默失效，故按读表失败处理。"""
        path = _write(tmp_path / "typo.json", {"demo-rul": [_ENTRY]})
        table = load_exception_table(path, (_NAME_RULE,))
        assert "未登记的规则键 demo-rul" in table.load_error

    def test_non_dict_entries_are_skipped(self, tmp_path):
        path = _write(tmp_path / "mixed.json", {"demo-rule": [_ENTRY, "junk"]})
        assert len(load_exception_table(path, (_NAME_RULE,)).entries_of("demo-rule")) == 1

    def test_defaults_fill_missing_fields_and_entries_override(self, tmp_path):
        entry = {key: value for key, value in _ENTRY.items() if key != "expiry"}
        path = _write(
            tmp_path / "defaults.json",
            {"defaults": {"expiry": "2027-06-30", "owner": "批量"}, "demo-rule": [entry]},
        )
        loaded = load_exception_table(path, (_NAME_RULE,)).entries_of("demo-rule")
        assert loaded[0]["expiry"] == "2027-06-30"
        assert loaded[0]["owner"] == "o"


class TestAudit:
    def _table(self, tmp_path: Path, entries: list[dict]) -> ExceptionTable:
        return load_exception_table(_write(tmp_path / "table.json", {"demo-rule": entries}), (_NAME_RULE,))

    def test_metadata_findings_name_every_missing_field(self, tmp_path):
        table = self._table(tmp_path, [{"name": "a"}])
        findings = table.audit().findings
        assert len(findings) == 1
        assert "[exception-metadata]" in findings[0]
        assert "owner/reason/expiry/replacement" in findings[0]

    def test_expiry_must_round_trip_iso_date(self, tmp_path):
        """正则能放行的 2027-02-30 不存在，回环口径必须判违规。"""
        table = self._table(tmp_path, [{**_ENTRY, "expiry": "2027-02-30"}])
        findings = table.audit().findings
        assert any("YYYY-MM-DD" in finding and "2027-02-30" in finding for finding in findings)

    def test_expired_entry_is_reported(self, tmp_path):
        table = self._table(tmp_path, [{**_ENTRY, "expiry": "2020-01-01"}])
        findings = table.audit().findings
        assert any(finding.startswith("[exception-expiry]") and "2020-01-01" in finding for finding in findings)

    def test_valid_entry_is_usable(self, tmp_path):
        audit = self._table(tmp_path, [_ENTRY]).audit()
        assert audit.findings == []
        assert [rule for rule, _entry in audit.usable] == ["demo-rule"]

    def test_audit_scoped_to_named_rule(self, tmp_path):
        """同一份 JSON 被多个检查共享时，只审自己的族。"""
        path = _write(
            tmp_path / "shared.json",
            {"demo-rule": [_ENTRY], "other-rule": [{"name": "b"}]},
        )
        rules = (ExceptionRule("demo-rule"), ExceptionRule("other-rule"))
        table = load_exception_table(path, rules)
        assert len(table.audit("other-rule").findings) == 1
        assert table.audit("demo-rule").findings == []


class TestUsageAndStaleness:
    def test_hit_marks_used_and_unused_is_stale(self, tmp_path):
        path = _write(
            tmp_path / "table.json",
            {"demo-rule": [_ENTRY, {**_ENTRY, "name": "b.py::g"}]},
        )
        table = load_exception_table(path, (_NAME_RULE,))
        assert table.is_excepted("demo-rule", "a.py::f") is True
        assert table.is_excepted("demo-rule", "c.py::h") is False
        audit = table.audit()
        stale = table.stale_findings(audit)
        assert len(stale) == 1
        assert "[exception-stale]" in stale[0]
        assert "b.py::g" in stale[0]
        assert DEFAULT_STALE_DETAIL in stale[0]

    def test_stale_finding_accepts_custom_detail(self, tmp_path):
        table = load_exception_table(_write(tmp_path / "t.json", {"demo-rule": [_ENTRY]}), (_NAME_RULE,))
        finding = table.stale_finding("demo-rule", _ENTRY, "目标文件不存在，须删除该例外")
        assert finding.endswith("目标文件不存在，须删除该例外")
        assert "未命中任何违规" not in finding

    def test_triple_key_uses_inline_separator_in_finding(self, tmp_path):
        entry = {"path": "src/python/x.py", "name": "sym", "owner": "o", "reason": "r", "expiry": "2027-06-30"}
        table = load_exception_table(_write(tmp_path / "s.json", {"demo-triple": [entry]}), (_TRIPLE_RULE,))
        assert table.is_excepted("demo-triple", "src/python/x.py", "sym") is True
        assert "demo-triple:src/python/x.py::sym" in table.stale_finding("demo-triple", entry)

    def test_undeclared_rule_name_raises(self, tmp_path):
        table = load_exception_table(_write(tmp_path / "t.json", {"demo-rule": []}), (_NAME_RULE,))
        with pytest.raises(KeyError):
            table.allowed("demo-rule-typo")


class TestRegistry:
    """登记表是「表文件名 + 规则 schema」的单一来源，三张表都要能按表键取到。"""

    def test_every_registered_table_loads_clean(self):
        for key in ("code-traces", "test-redundancy", "import-surface"):
            table = load_table(key)
            assert table.load_error == "", f"{key} 例外表读表失败：{table.load_error}"
            assert table.audit().findings == [], f"{key} 例外表有元数据 findings"

    def test_registry_paths_live_under_scripts(self):
        for key in ("code-traces", "test-redundancy", "import-surface"):
            spec = table_spec(key)
            assert spec.path.parent == _SCRIPTS_DIR
            assert spec.path.is_file()
            assert spec.rules

    def test_unknown_table_key_raises(self):
        with pytest.raises(KeyError):
            table_spec("no-such-table")
