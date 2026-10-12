"""`check-doc-drift` 文档格式族检查 —— 章节表 / 功能开关表 / 默认值 / 面板编号 / 测试覆盖计数。"""

from __future__ import annotations

import re
from pathlib import Path

from _checklib import rel
from _test_runner.modes import UNIT_DOMAIN_LABELS
from src.python.config._config_defaults import _DEFAULT_CONFIG
from src.python.config._llm_settings_defaults import _DEFAULT_LLM_SETTINGS
from src.python.config.features import GROUP_LABELS, GROUP_ORDER, feature_switch_registry, switches_in_group
from src.python.core.registry import _REPORT_SECTION_DEFAULT, get_cache_ttl_defaults, get_llm_module_names
from src.python.tui.tui_menu import filter_menu_llm_modules

from src.python.fetcher.chain import _DEFAULT_CHAINS  # noqa: E402
from _doc_drift._shared import (
    _RELIABILITY_MD,
    _HOW_TO_CONFIG_MD,
    _LLM_TECHNICAL_MD,
    _REPORTS_MD,
    _TEST_COVERAGE_MD,
    _TUI_MENU_MD,
    _values_equal,
)


_CHAIN_TABLE_ROW = re.compile(r"^\|\s*`([a-z_]+)`\s*\|")
#: 链表格内 ``provider id`` 单元格里的反引号 id（与 ``_DEFAULT_CHAINS`` 同序）
_CHAIN_ID_CELL = re.compile(r"`([a-z_0-9]+)`")
#: §4.2 表的 provider id 列表头关键字（列位置按表头文本定位，不依赖列序）
_CHAIN_ID_HEADER = "provider id"


def _chain_id_column_index(doc_text: str) -> tuple[int, int] | None:
    """定位 §4.2 表中「provider id」列：返回 ``(列下标, 表头单元格数)``；未找到返回 None。

    按**表头文本**定位而非硬编码列号：文档调整列顺序时不会误判；同时返回表头单元格数，
    供调用方判断「行内单元格数少于表头」的缺列情形（给出可读 finding，而非静默错位解析）。
    """
    for line in doc_text.splitlines():
        if not line.startswith("|") or _CHAIN_ID_HEADER not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        for idx, cell in enumerate(cells):
            if _CHAIN_ID_HEADER in cell:
                return idx, len(cells)
    return None


_SECTION_COUNT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"页签编号\s*1\s*[~～-]\s*(\d+)"),
    re.compile(r"默认顺序[（(](\d+)\s*项"),
    re.compile(r"返回 result[（(](\d+)\s*项"),
    re.compile(r"(\d+)\s*个报告章节"),
]


def parse_section_rows(doc_text: str) -> list[tuple[int, int, str]]:
    """解析 reports-instruction.md 章节表的 ``(表序号, 章序号, 名称)`` 行。"""
    rows = re.findall(r"^\|\s*(\d+)\s*\|\s*\*\*(\d+)\.([^（(*|\n]+)", doc_text, re.M)
    return [(int(a), int(b), c.strip()) for a, b, c in rows]


def check_section_table(doc_text: str) -> list[str]:
    findings: list[str] = []
    rows = parse_section_rows(doc_text)
    expected = _REPORT_SECTION_DEFAULT
    if len(rows) != len(expected):
        findings.append(f"{rel(_REPORTS_MD)}: 章节表 {len(rows)} 行，注册表 {len(expected)} 章")
    for i, (_, num, name) in enumerate(rows):
        if i >= len(expected):
            break
        exp = expected[i]
        if num != exp["number"] or name != exp["name"]:
            findings.append(
                f"{rel(_REPORTS_MD)}: 章节表第 {i + 1} 行 `{num}.{name}` 与注册表 "
                f"`{exp['number']}.{exp['name']}` 不一致"
            )
    return findings


def check_section_counts(docs: dict[Path, str]) -> list[str]:
    findings: list[str] = []
    total = len(_REPORT_SECTION_DEFAULT)
    for path, text in docs.items():
        for line_no, line in enumerate(text.splitlines(), 1):
            for pat in _SECTION_COUNT_PATTERNS:
                for m in pat.finditer(line):
                    if int(m.group(1)) != total:
                        findings.append(f"{rel(path)}:{line_no}: 章节数量断言「{m.group(0)}」与注册表 {total} 章不一致")
    return findings


def _group_doc_name(group: str) -> str:
    """组的**文档短名**（手册措辞）= 组标签「（」前缀去 emoji、取「·」前主名。

    唯一事实来源仍是 ``GROUP_LABELS``/``GROUP_ORDER``；手册的组表头、连写计数与
    面板块标题一律使用该短名，注册表改名则文档断言随之漂移报错。
    """
    prefix = GROUP_LABELS[group].split("（", 1)[0].strip()
    return re.sub(r"^[^\u4e00-\u9fff]+", "", prefix).split("·", 1)[0]


#: 按 ``GROUP_ORDER`` 派生的文档短名（呈现与体验/分析增强/独立章节与回放/机制与诊断）
_GROUP_DOC_NAMES: tuple[str, ...] = tuple(_group_doc_name(g) for g in GROUP_ORDER)

_SWITCH_TABLE_START = f"**{_GROUP_DOC_NAMES[0]}（"


_SWITCH_ROW = re.compile(r"^\|\s*`([a-z0-9_]+)`\s*\|\s*\**`?(true|false)`?\**\s*\|")


def extract_switch_table(doc_text: str) -> dict[str, bool]:
    """取 how-to-config.md 功能开关表区段内的 ``{flag: 默认值}``（其它表格不误取）。"""
    lines = doc_text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith(_SWITCH_TABLE_START)), None)
    if start is None:
        return {}
    table: dict[str, bool] = {}
    for line in lines[start:]:
        if line.startswith("## "):
            break
        m = _SWITCH_ROW.match(line)
        if m:
            table[m.group(1)] = m.group(2) == "true"
    return table


def check_switch_table(doc_text: str) -> list[str]:
    findings: list[str] = []
    table = extract_switch_table(doc_text)
    if not table:
        return [f"{rel(_HOW_TO_CONFIG_MD)}: 未找到功能开关表区段（起点 `{_SWITCH_TABLE_START}`）"]
    for flag, definition in feature_switch_registry.items():
        if flag not in table:
            findings.append(f"{rel(_HOW_TO_CONFIG_MD)}: 功能开关 `{flag}` 未列入开关表")
        elif table[flag] != definition.default:
            findings.append(
                f"{rel(_HOW_TO_CONFIG_MD)}: 开关 `{flag}` 表中默认值 {table[flag]} 与注册表 {definition.default} 不一致"
            )
    for flag in table:
        if flag not in feature_switch_registry:
            findings.append(f"{rel(_HOW_TO_CONFIG_MD)}: 开关表出现未登记开关 `{flag}`")
    return findings


def _group_counts() -> dict[str, int]:
    """四组计数（键 = ``GROUP_ORDER``）——drift 断言与面板编号派生共用。"""
    return {group: len(switches_in_group(group)) for group in GROUP_ORDER}


#: 四组连写计数（顺序 = GROUP_ORDER）：如「呈现与体验 2 / 分析增强 14 / 独立章节与回放 6 / 机制与诊断 9」
_GROUP_CHAIN_COUNT = re.compile(r"\s*/\s*".join(re.escape(name) + r"\s*(\d+)" for name in _GROUP_DOC_NAMES))

_GROUPED_COUNT = re.compile(
    r"(?:\*\*)?(" + "|".join(re.escape(name) for name in _GROUP_DOC_NAMES) + r")(?:组)?"
    r"(?:\*\*)?[（(](?:前|次|后)?\s*(\d+)\s*项"
)

_GROUP_NAME_TO_KIND: dict[str, str] = {}
for _g_name, _g_key in zip(_GROUP_DOC_NAMES, GROUP_ORDER):
    _GROUP_NAME_TO_KIND[_g_name] = _g_key
    _GROUP_NAME_TO_KIND[_g_name + "组"] = _g_key

#: 旧三组分组名（生命周期轴曾兼作分组轴的遗留措辞）——扫描域命中即报残留
_RETIRED_GROUP_NAMES: tuple[str, ...] = ("实验组", "常规组", "报告组", "报告章节与增强组")


# 三种合计写法：带前缀未加粗（共/全部/提供 N 项开关，如 requirements §11.5「提供 N 项功能开关」）/
# 加粗无前缀（**N 项功能开关**）/ 清单指引式（完整 N 项与分组清单）；前缀与加粗写法互斥不重复命中
_TOTAL_COUNT = re.compile(
    r"(?:共|全部|提供)\s*(\d+)\s*项(?:功能)?开关"
    r"|\*\*(\d+)\s*项功能开关\*\*"
    r"|完整\s*\*{0,2}(\d+)\s*\*{0,2}项与分组清单"
)


def _count_finding(path: Path, line_no: int, shown: str, expected: int) -> str:
    return f"{rel(path)}:{line_no}: 开关分组计数「{shown}」与注册表 {expected} 不一致"


def check_switch_counts(docs: dict[Path, str]) -> list[str]:
    """开关分组计数断言 ↔ 注册表分组计数（四种写法：四组连写 / 分组枚举 / 单块 / 合计）。

    另报**旧三组名残留**（``_RETIRED_GROUP_NAMES`` 命中即报）——文档措辞与
    重构后的四组作用域轴保持一致，不给新旧两套分组名共存留口子。
    """
    findings: list[str] = []
    counts = _group_counts()
    total = len(feature_switch_registry)
    for path, text in docs.items():
        for line_no, line in enumerate(text.splitlines(), 1):
            for m in _GROUP_CHAIN_COUNT.finditer(line):
                got = [int(m.group(i)) for i in range(1, len(GROUP_ORDER) + 1)]
                exp = [counts[group] for group in GROUP_ORDER]
                if got != exp:
                    findings.append(
                        f"{rel(path)}:{line_no}: 开关分组计数「{m.group(0)}」与注册表 "
                        f"{'/'.join(str(v) for v in exp)} 不一致"
                    )
            for m in _GROUPED_COUNT.finditer(line):
                expected = counts[_GROUP_NAME_TO_KIND[m.group(1)]]
                if int(m.group(2)) != expected:
                    findings.append(_count_finding(path, line_no, m.group(0), expected))
            retired = [name for name in _RETIRED_GROUP_NAMES if name in line]
            if retired:
                findings.append(
                    f"{rel(path)}:{line_no}: 旧三组分组名残留「{'/'.join(retired)}」"
                    f"——四分组后应改用 {'/'.join(_GROUP_DOC_NAMES)} 相应措辞"
                )
            for m in _TOTAL_COUNT.finditer(line):
                if int(m.group(1) or m.group(2) or m.group(3)) != total:
                    findings.append(_count_finding(path, line_no, m.group(0), total))
    return findings


_DEFAULT_CLAIM = re.compile(r"`([a-z0-9_]+)`([^\n`]{0,6}?)默认\s*(开|关|true|false)")


def check_switch_default_claims(docs: dict[Path, str]) -> list[str]:
    findings: list[str] = []
    for path, text in docs.items():
        for line_no, line in enumerate(text.splitlines(), 1):
            for m in _DEFAULT_CLAIM.finditer(line):
                flag, claim = m.group(1), m.group(3)
                if flag not in feature_switch_registry:
                    continue
                claim_bool = claim in ("开", "true")
                if claim_bool != feature_switch_registry[flag].default:
                    findings.append(
                        f"{rel(path)}:{line_no}: `{flag}` 文档写「默认{claim}」而注册表默认 "
                        f"{'开' if feature_switch_registry[flag].default else '关'}"
                    )
    return findings


_CONFIG_ROW = re.compile(r"^\|\s*`([a-z0-9_]+)`\s*\|\s*`([^`]*)`\s*\|")


def check_config_defaults(doc_text: str) -> list[str]:
    findings: list[str] = []
    known = set(_DEFAULT_CONFIG)
    for line_no, line in enumerate(doc_text.splitlines(), 1):
        m = _CONFIG_ROW.match(line)
        if not m:
            continue
        key, shown = m.group(1), m.group(2)
        if key not in known:
            continue
        default = _DEFAULT_CONFIG[key]
        if isinstance(default, (dict, list)):
            continue  # 结构型默认值在文档中以「见下节」描述，不做逐值比对
        if not _values_equal(shown, default):
            findings.append(
                f"{rel(_HOW_TO_CONFIG_MD)}:{line_no}: 配置项 `{key}` 文档默认值 `{shown}` 与代码 "
                f"`{_DEFAULT_CONFIG[key]!r}` 不一致"
            )
    return findings


_LLM_ROW = re.compile(
    r"^\|\s*`([a-z_]+)`\s*\|\s*[^|]+\|\s*(\d+)\s*\|\s*(\d+)s\s*\|\s*([^|]+?)\s*\|",
    re.M,
)


_TTL_TABLE_ROW = re.compile(r"^\|\s*`([a-z_]+)`\s*\|\s*(\d+)s\s*(?:\([^)]*\))?\s*\|", re.M)


_HOURS_ROW = re.compile(r"^|\s*`([a-z_]+)`\s*\|\s*(\d+)h（(\d+)s）\s*\|")


def _ttl_default(module: str) -> float | None:
    """缓存 TTL 注册表中该 LLM 模块的默认 TTL（新闻关联为批量模块，键名带前缀）。"""
    defaults = get_cache_ttl_defaults()
    for key in (f"llm_{module}", f"llm_news_{module}", f"llm_{module}_item"):
        if key in defaults:
            return float(defaults[key])
    return None


def check_llm_defaults(doc_text: str) -> list[str]:
    findings: list[str] = []
    for m in _LLM_ROW.finditer(doc_text):
        module, max_tokens, timeout, ttl_text = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
        if module not in get_llm_module_names():
            continue
        exp_max = _DEFAULT_LLM_SETTINGS.get(f"max_tokens_{module}")
        exp_timeout = _DEFAULT_LLM_SETTINGS.get(f"timeout_{module}")
        if exp_max is not None and max_tokens != exp_max:
            findings.append(
                f"{rel(_LLM_TECHNICAL_MD)}: 模块 `{module}` max_tokens 文档 {max_tokens} 与代码 {exp_max} 不一致"
            )
        if exp_timeout is not None and timeout != exp_timeout:
            findings.append(
                f"{rel(_LLM_TECHNICAL_MD)}: 模块 `{module}` timeout 文档 {timeout}s 与代码 {exp_timeout}s 不一致"
            )
        ttl_hours = re.search(r"(\d+)h", ttl_text)
        ttl_secs = re.search(r"(\d+)s", ttl_text)
        exp_ttl = _ttl_default(module)
        if exp_ttl is not None and ttl_secs and int(ttl_secs.group(1)) != int(exp_ttl):
            findings.append(
                f"{rel(_LLM_TECHNICAL_MD)}: 模块 `{module}` TTL 文档 {ttl_secs.group(1)}s 与缓存注册表 {int(exp_ttl)}s 不一致"
            )
        elif exp_ttl is not None and ttl_hours and int(ttl_hours.group(1)) * 3600 != int(exp_ttl):
            findings.append(
                f"{rel(_LLM_TECHNICAL_MD)}: 模块 `{module}` TTL 文档 {ttl_hours.group(1)}h 与缓存注册表 {int(exp_ttl)}s 不一致"
            )
    for m in _TTL_TABLE_ROW.finditer(doc_text):
        module, ttl = m.group(1), int(m.group(2))
        exp_ttl = _ttl_default(module)
        if exp_ttl is not None and ttl != int(exp_ttl):
            findings.append(
                f"{rel(_LLM_TECHNICAL_MD)}: 模块 `{module}` TTL 表 {ttl}s 与缓存注册表 {int(exp_ttl)}s 不一致"
            )
    return findings


_PANEL_SECTION_START = "交互式子菜单（面板标题"


_PANEL_ROW = re.compile(r"^\|\s*(\d+)(?:[-–](\d+))?\s*\|")


#: 每组块标题「组短名（面板编号 X-Y）」——由 ``GROUP_LABELS`` 派生，手册措辞漂移即报错
_GROUP_PANEL_RANGE: dict[str, "re.Pattern[str]"] = {
    group: re.compile(re.escape(_group_doc_name(group)) + r"（面板编号\s*(\d+)-(\d+)）") for group in GROUP_ORDER
}


#: features.json 键名 → 菜单编号映射表行（兼容引用式 `> |` 前缀）：| `flag` | N | 组名 | 功能 |
_PANEL_KEY_MAP_ROW = re.compile(r"^(?:>\s*)?\|\s*`([a-z0-9_]+)`\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|")


def check_panel_numbering(doc_text: str) -> list[str]:
    """校验 [S] 面板编号表：行号序列 / 四组块标题区间 / features.json 键名映射均与注册表派生一致。

    面板编号 = LLM 菜单模块数 + 四组按 ``GROUP_ORDER`` 连续派生（handlers_config.py
    运行时派发，非硬编码）；组块标题与映射表组名措辞须与 ``GROUP_LABELS`` 组短名一致。
    """
    findings: list[str] = []
    lines = doc_text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith(_PANEL_SECTION_START)), None)
    if start is None:
        return [f"{rel(_TUI_MENU_MD)}: 未找到 [S] 面板编号表区段"]
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if lines[i].startswith("#### ") or lines[i].startswith("## ") or lines[i] == "---"
        ),
        len(lines),
    )
    section = lines[start:end]
    llm_visible = len(filter_menu_llm_modules(get_llm_module_names()))
    total = len(feature_switch_registry)
    expect_nums = list(range(llm_visible + 1, llm_visible + total + 1))

    numbers: list[int] = []
    for line in section:
        m = _PANEL_ROW.match(line)
        if not m:
            continue
        lo = int(m.group(1))
        hi = int(m.group(2)) if m.group(2) else lo
        numbers.extend(range(lo, hi + 1))
    if numbers != expect_nums:
        findings.append(
            f"{rel(_TUI_MENU_MD)}: 功能开关编号序列 {numbers or '空'} 与派生编号 "
            f"{expect_nums[0]}~{expect_nums[-1]}（LLM 菜单模块 {llm_visible} 项 + 功能开关 {total} 项，连续无缺）不一致"
        )

    # 四组块标题区间：「组短名（面板编号 X-Y）」与组计数派生边界逐一比对
    section_text = "\n".join(section)
    cursor = llm_visible + 1
    for group in GROUP_ORDER:
        name = _group_doc_name(group)
        first = cursor
        last = cursor + len(switches_in_group(group)) - 1
        m = _GROUP_PANEL_RANGE[group].search(section_text)
        if not m:
            findings.append(f"{rel(_TUI_MENU_MD)}: 缺少组块标题「{name}（面板编号 {first}-{last}）」")
        elif (int(m.group(1)), int(m.group(2))) != (first, last):
            findings.append(
                f"{rel(_TUI_MENU_MD)}: 组「{name}」块标题编号 {m.group(1)}-{m.group(2)} 与派生区间 {first}-{last} 不一致"
            )
        cursor = last + 1

    # features.json 键名 → 菜单编号映射表：全量、按面板顺序、组名一致
    got_pairs: list[tuple[str, int, str]] = []
    for line in section:
        m = _PANEL_KEY_MAP_ROW.match(line)
        if m and m.group(1) in feature_switch_registry:
            got_pairs.append((m.group(1), int(m.group(2)), m.group(3)))
    expect_pairs: list[tuple[str, int, str]] = []
    cursor = llm_visible + 1
    for group in GROUP_ORDER:
        name = _group_doc_name(group)
        for flag, _d in switches_in_group(group):
            expect_pairs.append((flag, cursor, name))
            cursor += 1
    if got_pairs != expect_pairs:
        findings.append(
            f"{rel(_TUI_MENU_MD)}: features.json 键名→菜单编号映射 {got_pairs} 与注册表派生 {expect_pairs} 不一致"
        )
    return findings


_TEST_COVERAGE_ROW = re.compile(r"^\|\s*(?:├─|└─)?\s*`([a-z0-9_-]+)`")


_COUNT_CELL = re.compile(r"^\**(\d[\d,]*)\**\s*(?:（[^）]*）)?$")


_COUNT_NAME_ALIAS = {"all": "_总收集"}

#: 功能域表所在章节标题（`## ` 级）：该区域内加粗标签行必须全部可映射，
#: 区域外的加粗行（其它表）不属本核对域。
_DOMAIN_SECTION_TITLE = "功能域对应测试源"

#: 功能域表行（中文加粗标签，形如 `| **数据源 Provider** | … | 545 |`）：标签 →
#: unit 子标记映射与 collect-test-coverage 功能域聚合单一来源
#: （`_test_runner.modes.UNIT_DOMAIN_LABELS`）。另收表内非 unit 域的聚合行别名
#: （`端到端业务场景` 行取 scenario 父标记计数，与 unit 功能域共表但不属映射集）。
#: 功能域章内标签未登记 / 映射中的功能域缺行一律报出，不得静默跳过。
_TEST_COVERAGE_DOMAIN_ROW = re.compile(r"^\|\s*\*\*([^*|]+)\*\*\s*\|")
_DOMAIN_LABEL_TO_MARKER = {
    **{label: marker for marker, label in UNIT_DOMAIN_LABELS.items()},
    "端到端业务场景": "scenario",
}


def check_test_coverage_counts(doc_text: str, snapshot: dict[str, int]) -> list[str]:
    """test-coverage.md 各计数行 ↔ collect-test-coverage 快照。

    两类行：反引号标记行（模式/unit/场景/跨类表，按标记名比对），以及功能域章
    内的中文加粗标签行（经共享映射反查标记）。功能域章内出现未登记标签、或映射
    中的功能域在表中缺行，均报 finding——这类行过去以「未收录名」静默跳过，
    实测导致该表 4 行长期无人核对。
    """
    findings: list[str] = []
    in_domain_section = False
    domain_section_seen = False
    seen_domain_markers: set[str] = set()
    for line_no, line in enumerate(doc_text.splitlines(), 1):
        if line.startswith("## "):
            in_domain_section = line[3:].strip() == _DOMAIN_SECTION_TITLE
            domain_section_seen = domain_section_seen or in_domain_section
            continue
        m = _TEST_COVERAGE_ROW.match(line)
        if m:
            name = _COUNT_NAME_ALIAS.get(m.group(1), m.group(1))
        else:
            dm = _TEST_COVERAGE_DOMAIN_ROW.match(line)
            if not dm:
                continue
            label = dm.group(1).strip()
            marker = _DOMAIN_LABEL_TO_MARKER.get(label)
            if marker is None:
                if in_domain_section:
                    findings.append(
                        f"{rel(_TEST_COVERAGE_MD)}:{line_no}: 功能域行标签 `{label}` 未登记"
                        "（映射见 `_test_runner.modes.UNIT_DOMAIN_LABELS`），计数无法核对"
                    )
                continue  # 功能域章外的加粗行不属本核对域
            if in_domain_section:
                seen_domain_markers.add(marker)
            name = marker
        if name not in snapshot:
            continue
        got: int | None = None
        for cell in [c.strip() for c in line.strip().strip("|").split("|")][1:]:
            num = _COUNT_CELL.match(cell)
            if num:
                got = int(num.group(1).replace(",", ""))
                break
        if got is not None and got != snapshot[name]:
            findings.append(
                f"{rel(_TEST_COVERAGE_MD)}:{line_no}: 标记 `{name}` 覆盖项数 {got} 与 collect-test-coverage 快照 {snapshot[name]} 不一致"
            )
    if domain_section_seen:  # 表存在才做完整性反查（单行输入的既有用例不适用）
        for marker, label in UNIT_DOMAIN_LABELS.items():
            if marker not in seen_domain_markers:
                findings.append(
                    f"{rel(_TEST_COVERAGE_MD)}: 功能域章缺少 `{label}` 行（映射标记 `{marker}`，"
                    "见 `_test_runner.modes.UNIT_DOMAIN_LABELS`，collect 输出已有该域）"
                )
    return findings


def check_chain_table(doc_text: str) -> list[str]:
    """校验可靠性手册 §4.2「Provider Chain 降级路径」表与 `_DEFAULT_CHAINS` 逐链一致。

    两层比对：
      1. **链路名集合**双向一致（漏链 / 幽灵行）；
      2. **槽位级**双向一致：表的「provider id（机器可读）」列（按 ``→`` 顺序列出的
         ``source_id``）必须与 ``_DEFAULT_CHAINS[chain]`` **逐项同序**相等——覆盖
         「文档写主源+备源、代码只注册一个槽」这类漂移（漏槽 / 多槽 / 顺序错）。

    缺口：只比对链路名时槽位漂移无人发现——巨潮备源适配器已登记而
    ``_DEFAULT_CHAINS['financial_report']`` 只列主源槽，备源正文路径实际不可用；
    另该表曾只列 5 行却声称枚举全部链路。故本检查同时做槽位级同序比对。
    """
    findings: list[str] = []
    header = _chain_id_column_index(doc_text)
    id_col, header_cells = header if header is not None else (None, 0)
    documented: set[str] = set()
    documented_slots: dict[str, list[str]] = {}
    missing_id_column: list[str] = []
    for line in doc_text.splitlines():
        m = _CHAIN_TABLE_ROW.match(line)
        if not m:
            continue
        chain = m.group(1)
        documented.add(chain)
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        # 列位置按**表头文本**定位（而非硬编码下标）：列序调整不会造成误判
        if id_col is None or len(cells) < header_cells:
            missing_id_column.append(chain)
            documented_slots[chain] = []
            continue
        documented_slots[chain] = _CHAIN_ID_CELL.findall(cells[id_col])
    if id_col is None and documented:
        findings.append(f"{rel(_RELIABILITY_MD)}: §4.2 表未找到「provider id」列表头（槽位级校验须据此定位列）")
    if not documented:
        findings.append(f"{rel(_RELIABILITY_MD)}: 未找到 §4.2 Provider Chain 降级路径表（表行须以 | `链路名` | 开头）")
        return findings
    expected = set(_DEFAULT_CHAINS)
    for chain in sorted(expected - documented):
        findings.append(f"{rel(_RELIABILITY_MD)}: §4.2 表缺少链路 `{chain}`（`_DEFAULT_CHAINS` 有定义，须补行）")
    for chain in sorted(documented - expected):
        findings.append(f"{rel(_RELIABILITY_MD)}: §4.2 表列出链路 `{chain}` 但 `_DEFAULT_CHAINS` 无此链（幽灵行）")
    for chain in sorted(documented & expected):
        if chain in missing_id_column:
            findings.append(
                f"{rel(_RELIABILITY_MD)}: §4.2 链路 `{chain}` 行缺 provider id 列"
                "（该列承载槽位清单，须保留；表头与其它列可按需调整顺序）"
            )
            continue
        doc_slots = documented_slots[chain]
        code_slots = list(_DEFAULT_CHAINS[chain])
        if doc_slots == code_slots:
            continue
        missing = [s for s in code_slots if s not in doc_slots]
        extra = [s for s in doc_slots if s not in code_slots]
        detail = []
        if missing:
            detail.append(f"漏槽 {missing}")
        if extra:
            detail.append(f"多槽 {extra}")
        if not detail:
            detail.append("顺序不一致")
        findings.append(
            f"{rel(_RELIABILITY_MD)}: §4.2 链路 `{chain}` 槽位不一致（{'；'.join(detail)}）"
            f"——文档 {doc_slots} vs 代码 {code_slots}"
        )
    return findings
