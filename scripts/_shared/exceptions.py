"""例外表统一设施（检查脚本的 `owner` / `reason` / `expiry` / `replacement` 例外表）。

`scripts/` 下每个守卫脚本都允许把「确属合法但形态命中规则」的登记点写进同目录的 JSON
例外表，并自审这些条目：字段是否齐全、是否到期、是否仍命中违规（规则修好后仍留着的条目
就是永不到期的豁免）。这份协议此前在四个消费者里各写一遍，口径已经分叉——到期日一套
用正则、一套用 `date.fromisoformat` 回环；「是否仍命中」三种结构（重扫文件 / 拆两个函数 /
`used` 标记）。本模块把协议收成一处，判定与 finding 文案只在这里定义：

  - **规范化加载**：文件缺失视为无例外（不是错误）；JSON 非法、顶层不是对象、规则值不是
    数组、出现未登记的规则键，一律落进 `load_error`，文案形如
    `脚本/_xxx_exceptions.json 无法解析：<原因>`，由调用方决定是否加 `[exception-metadata]` 前缀。
  - **字段校验**：条目须齐 `REQUIRED_FIELDS`；`expiry` 须是 `date.fromisoformat` 能回环的
    ISO 日历日——正则能放行的 `2027-02-30` 这类不存在的日期在这里同样判违规。
  - **到期判定**：`expiry` 早于当天即 `[exception-expiry]`。
  - **「已使用」标记与陈旧自审**：查询走 :meth:`ExceptionTable.is_excepted`（命中即记入
    `used`），扫描结束后 :meth:`ExceptionTable.stale_findings` 把「登记了但本次没被查询过」
    的条目报成 `[exception-stale]`。不需要「查询即标记」的场景（登记点靠重扫文件判定是否
    仍命中）可用 :meth:`ExceptionTable.stale_finding` 自行拼同形文案。
  - **定位键 schema 按规则声明**：不同检查的定位键形状不同（多数是单字段 `name`；导入面
    检查是「规则 + 文件路径 + 符号」），故 :class:`ExceptionRule` 用 `key_fields` 声明键字段、
    用 `separator` 声明 finding 文案里规则名与键之间的分隔符，不强行归并成一种形状。
  - **`defaults` 段**：同表内多条共用的字段（典型：同一续期日）写在顶层 `defaults` 对象里，
    加载时合并进每条、条目字段优先——新增一条只写差异字段，续期只改一处。

**登记表**：三张例外表的文件名与规则 schema 单源登记在 :data:`TABLE_SPECS`。新增例外表、
改文件名或加规则键只改注册表，并在 `scripts-reference.md` 的例外表清单补一行；各检查脚本
按表键取自己的 `path` / `rules`，不再各自写字面量路径。
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import NamedTuple

from _shared.checklib import rel

#: 例外条目必填字段（缺一即无法追责或无法自动到期）
REQUIRED_FIELDS: tuple[str, ...] = ("owner", "reason", "expiry", "replacement")

#: 表内「批量默认字段」段：条目未写的字段取此处，写了则以条目为准
DEFAULTS_SECTION = "defaults"

#: 陈旧例外的通用说明（各检查共用；定位点另有失效原因的用 `stale_finding(detail=…)` 覆盖）
DEFAULT_STALE_DETAIL = "未命中任何违规（规则已修复），须删除该例外"

#: `scripts/` 目录（默认表路径按它推导）
_SCRIPTS_DIR = Path(__file__).resolve().parents[1]


class ExceptionRule(NamedTuple):
    """一条例外规则的定位键 schema。

    Args:
        name: 规则键（JSON 里的字段名，同时是 finding 文案里的规则标签）。
        key_fields: 定位键取条目里的哪些字段（顺序即文案里的拼接顺序）。
        separator: 规则名与定位键之间的分隔符（多数检查用 `::`；导入面检查用 `:` 把
            文件路径内联在规则名后，符号仍以 `::` 相接，故这里的定位键自身用 `::` 拼接）。
    """

    name: str
    key_fields: tuple[str, ...] = ("name",)
    separator: str = "::"

    def key_of(self, entry: Mapping[str, object]) -> tuple[str, ...]:
        """条目 → 定位键（缺字段取空串，与「字段缺失即元数据违规」互不遮蔽）。"""
        return tuple(str(entry.get(field, "")) for field in self.key_fields)

    def where(self, table_path: Path, entry: Mapping[str, object]) -> str:
        """finding 文案里的定位段：`<表文件> <规则><分隔符><定位键>`。"""
        return f"{rel(table_path)} {self.name}{self.separator}{'::'.join(self.key_of(entry))}"


class ExceptionAudit(NamedTuple):
    """元数据自审结果：finding 列表 + 通过校验（可供陈旧判定）的条目。"""

    findings: list[str]
    usable: list[tuple[str, dict]]


class ExceptionTable:
    """一张规范化后的例外表：规则 → 条目（`defaults` 已合并）+ 命中记录 + 读表失败原因。"""

    def __init__(
        self,
        path: Path,
        rules: Sequence[ExceptionRule],
        entries: Mapping[str, Sequence[dict]] | None = None,
        *,
        load_error: str = "",
        used: set[tuple[str, ...]] | None = None,
    ) -> None:
        self.path = Path(path)
        self.rules = tuple(rules)
        self.entries: dict[str, list[dict]] = {
            rule.name: [dict(entry) for entry in (entries or {}).get(rule.name) or ()] for rule in self.rules
        }
        self.load_error = load_error
        self.used: set[tuple[str, ...]] = set(used or ())

    def __contains__(self, rule_name: object) -> bool:
        """`"<规则名>" in table`：该规则是否在本表登记。"""
        return rule_name in self.entries

    def rule(self, rule_name: str) -> ExceptionRule:
        """按规则名取 schema（未登记的名字直接 KeyError——登记表与调用点漂移即暴露）。"""
        for rule in self.rules:
            if rule.name == rule_name:
                return rule
        raise KeyError(f"例外表未登记规则 {rule_name}")

    def entries_of(self, rule_name: str) -> list[dict]:
        """该规则的条目（按 JSON 顺序；未登记的规则名返空列表）。"""
        return self.entries.get(rule_name, [])

    def allowed(self, rule_name: str) -> set[tuple[str, ...]]:
        """该规则已登记的定位键集合。"""
        rule = self.rule(rule_name)
        return {rule.key_of(entry) for entry in self.entries_of(rule_name)}

    def is_excepted(self, rule_name: str, *key: str) -> bool:
        """该定位键是否已登记例外；命中即记入 `used`（供 :meth:`stale_findings` 判陈旧）。"""
        if tuple(key) not in self.allowed(rule_name):
            return False
        self.used.add((rule_name, *key))
        return True

    def where(self, rule_name: str, entry: Mapping[str, object]) -> str:
        """条目在 finding 文案里的定位段。"""
        return self.rule(rule_name).where(self.path, entry)

    def stale_finding(self, rule_name: str, entry: Mapping[str, object], detail: str = DEFAULT_STALE_DETAIL) -> str:
        """一条陈旧例外的 finding（`detail` 描述失效原因）。"""
        return f"[exception-stale] {self.where(rule_name, entry)} {detail}"

    def audit(self, *rule_names: str) -> ExceptionAudit:
        """元数据自审：字段齐全 + `expiry` 合法未到期。

        未给规则名时审全表；给了就只审这些规则（同一份 JSON 被多个检查共享时，各检查
        只自审自己那一族，避免把别的族的条目误判成陈旧）。
        """
        selected = [rule_name for rule_name in (rule_names or tuple(self.entries)) if rule_name in self.entries]
        findings: list[str] = []
        usable: list[tuple[str, dict]] = []
        today = date.today()
        for rule_name in selected:
            for entry in self.entries_of(rule_name):
                where = self.where(rule_name, entry)
                missing = [field for field in REQUIRED_FIELDS if not str(entry.get(field, "")).strip()]
                if missing:
                    findings.append(f"[exception-metadata] {where} 缺少字段 {'/'.join(missing)}")
                    continue
                expiry_raw = str(entry["expiry"]).strip()
                if not _is_iso_date(expiry_raw):
                    findings.append(f"[exception-metadata] {where} expiry 须为 YYYY-MM-DD，实为「{expiry_raw}」")
                    continue
                if date.fromisoformat(expiry_raw) < today:
                    findings.append(f"[exception-expiry] {where} 已于 {expiry_raw} 到期，须删除例外或续期并复核理由")
                    continue
                usable.append((rule_name, entry))
        return ExceptionAudit(findings, usable)

    def stale_findings(self, audit: ExceptionAudit) -> list[str]:
        """「登记了但本次没被查询过」的条目即陈旧（规则已修复，例外成免死金牌）。"""
        stale: list[str] = []
        for rule_name, entry in audit.usable:
            key = (rule_name, *self.rule(rule_name).key_of(entry))
            if key not in self.used:
                stale.append(self.stale_finding(rule_name, entry))
        return stale


class TableSpec(NamedTuple):
    """一张例外表的登记信息：文件路径 + 该表的规则 schema。"""

    path: Path
    rules: tuple[ExceptionRule, ...]

    def rule(self, rule_name: str) -> ExceptionRule:
        """按规则名取 schema（名字须在本表登记，拼错即 KeyError）。"""
        for rule in self.rules:
            if rule.name == rule_name:
                return rule
        raise KeyError(f"例外表 {rel(self.path)} 未登记规则 {rule_name}")


#: 例外表登记表：表键 → 文件路径与规则 schema（新增表/改文件名只改这里）
TABLE_SPECS: dict[str, TableSpec] = {
    "code-traces": TableSpec(
        path=_SCRIPTS_DIR / "_code_traces_exceptions.json",
        rules=(ExceptionRule("float-sum"),),
    ),
    "test-redundancy": TableSpec(
        path=_SCRIPTS_DIR / "_test_redundancy_exceptions.json",
        rules=(ExceptionRule("patch-surface"), ExceptionRule("slow-or-subprocess")),
    ),
    "import-surface": TableSpec(
        path=_SCRIPTS_DIR / "_import_surface_exceptions.json",
        rules=(
            ExceptionRule("compat-comment", ("path", "name"), ":"),
            ExceptionRule("private-all", ("path", "name"), ":"),
            ExceptionRule("cross-private", ("path", "name"), ":"),
            ExceptionRule("cross-private-scripts", ("path", "name"), ":"),
            ExceptionRule("dynamic-target", ("path", "name"), ":"),
            ExceptionRule("layer-inversion", ("path", "name"), ":"),
        ),
    ),
}


def table_spec(key: str) -> TableSpec:
    """按表键取登记信息（`KeyError` 即表键拼错）。"""
    return TABLE_SPECS[key]


def load_table(key: str) -> ExceptionTable:
    """按表键加载例外表（路径与规则 schema 均取自 :data:`TABLE_SPECS`）。"""
    spec = table_spec(key)
    return load_exception_table(spec.path, spec.rules)


def load_exception_table(path: Path, rules: Sequence[ExceptionRule]) -> ExceptionTable:
    """规范化加载例外表：缺失视为无例外，结构不符落在 `load_error`。"""
    if not path.exists():
        return ExceptionTable(path, rules)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ExceptionTable(path, rules, load_error=f"{rel(path)} 无法解析：{exc}")
    if not isinstance(raw, dict):
        return ExceptionTable(path, rules, load_error=f"{rel(path)} 无法解析：顶层须为 JSON 对象")
    defaults = raw.get(DEFAULTS_SECTION) or {}
    if not isinstance(defaults, dict):
        return ExceptionTable(path, rules, load_error=f"{rel(path)} 无法解析：{DEFAULTS_SECTION} 段须为 JSON 对象")
    declared = {rule.name for rule in rules}
    unknown = sorted(str(key) for key in raw if key != DEFAULTS_SECTION and key not in declared)
    if unknown:
        # 规则键拼错时整族例外静默失效（登记了却没生效）比报错更危险，故按读表失败处理
        return ExceptionTable(path, rules, load_error=f"{rel(path)} 无法解析：未登记的规则键 {'/'.join(unknown)}")
    entries: dict[str, list[dict]] = {}
    for rule in rules:
        value = raw.get(rule.name, [])
        if not isinstance(value, list):
            return ExceptionTable(path, rules, load_error=f"{rel(path)} 无法解析：规则 {rule.name} 须为 JSON 数组")
        entries[rule.name] = [{**defaults, **entry} for entry in value if isinstance(entry, dict)]
    return ExceptionTable(path, rules, entries)


def _is_iso_date(text: str) -> bool:
    """是否为 `date.fromisoformat` 能原样回环的 ISO 日历日。"""
    try:
        return date.fromisoformat(text).isoformat() == text
    except ValueError:
        return False
