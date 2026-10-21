"""测试：check-doc-drift.py — 文档与实现一致性（章节/开关/默认值/面板编号/目录树/统计表/归档索引/分区纪律/章节-区块矩阵）

覆盖：
  - 章节表解析与比对（行数不符 / 序号或名称漂移）
  - 章节数量断言扫描（`页签编号 1~N`、`默认顺序（N 项`、`返回 result（N 项`、`N 个报告章节`）
  - 功能开关表区段提取（其它表格不误取）与成员/默认值比对
  - 开关分组计数断言（三组连写 / 单组 / 合计 三种写法）
  - 开关默认值断言（`flag` + 默认开/关）与「不跨到下一个开关」的守卫
  - 配置标量默认值表的等价判定（bool / None / 数字 / 路径 / 引号差异）
  - LLM 默认参数表（max_tokens / timeout / TTL 三方比对）
  - TUI [S] 面板编号连续性、分组边界与报告块编号枚举
  - 目录树解析（按缩进还原仓库相对路径）
  - 版本目录块升序（同父目录 vN.N.x/ 按版本号升序；数值序非字典序；集合比对不看先后的盲区）
  - 项目统计表比对（文件数 / 行数）
  - 归档索引完整性（管理文档 ↔ `docs/archive/` 双向对齐）
  - 迁档占位↔归档节（「已随 vX.Y.Z 发布迁入」占位 ↔ 归档文件含该版本二级标题节；缺节/缺文件报出）
  - 树描述计数禁令（目录树描述禁写「阿拉伯数字+量词」易漂移计数；docs/archive 记录域豁免）
  - 管理文档分区纪律（未完成/已解决/已归档错置、现行 changelog 只允许开发段头）
  - 章节-区块矩阵（technical.md §4.22：文档行 ↔ 区块注册表逐列 / 键集双向 / 双端实现提取集合三向对账）
  - 手册主菜单 code block ↔ MENU_ITEMS（键集合/标签头/多列与光标前缀解析/无块报错）

兄弟分片：test_check_doc_drift_crosscheck.py（文档↔代码交叉校验：数据源链路表/Extended Thinking 支持矩阵/
测试收集快照/生成产物/真实仓库冒烟/统计表回写同步/守护清单同源）。

测试通过脚本 import 方式直接复用解析/校验函数，不运行真实 CLI（`run_checks` 的 pytest 收集项
默认不跑，故冒烟测试只读文件、不触发 pytest 子进程）。
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from src.python.core.section_block_registry import SECTION_BLOCK_SPECS
from src.python.tui.tui_menu import MENU_ITEMS

import pytest
from src.test._script_loader import load_script


def _documented_test_count(doc_text: str) -> int | None:
    """从 folders.md 「测试用例」行的「N 个」取当前登记用例数（避免嵌套 pytest 收集）。"""
    for line in doc_text.splitlines():
        if line.startswith("|") and "测试用例" in line:
            m = re.search(r"([\d,]+)\s*个", line)
            if m:
                return int(m.group(1).replace(",", ""))
    return None


@pytest.fixture(scope="module")
def drift():
    return load_script("check-doc-drift.py")


@pytest.fixture(scope="module")
def drift_parts(drift):
    """实现包各子模块（补丁须打到**持有被替换符号的模块**，见 CLAUDE.md「scripts 共享设施」条）。

    依赖 `drift`：入口模块加载时才会把 `scripts/` 加入 sys.path（`_doc_drift` 才可导入）。
    """
    import _doc_drift

    return _doc_drift


pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
    pytest.mark.usefixtures("offline_external_sources"),
]


# ═══ 章节表 ═══


class TestSectionTable:
    def test_parses_rows(self, drift):
        doc = "| 1 | **1.投资分析汇总**（始终显示） |\n| 2 | **2.持仓明细与分类** |\n"
        assert drift.parse_section_rows(doc) == [(1, 1, "投资分析汇总"), (2, 2, "持仓明细与分类")]

    def test_row_count_mismatch(self, drift):
        findings = drift.check_section_table("| 1 | **1.投资分析汇总** |\n")
        assert any("章节表 1 行" in f for f in findings)

    def test_name_drift_detected(self, drift, monkeypatch, drift_parts):
        doc = "| 1 | **1.投资分析汇总** |\n| 2 | **2.持仓明细** |\n"
        full = [dict(s) for s in drift._REPORT_SECTION_DEFAULT[:2]]
        monkeypatch.setattr(drift_parts._format, "_REPORT_SECTION_DEFAULT", full)
        findings = drift.check_section_table(doc)
        assert any("`2.持仓明细`" in f for f in findings)


# ═══ 章节数量断言 ═══


class TestSectionCounts:
    @pytest.mark.parametrize(
        "template",
        [
            "| R-OUT-05 | Excel 格式：页签编号 1~{n}，数字前缀保证排序 |",
            "> 空对象使用默认顺序（{n} 项）",
            "返回 result（{n} 项，key/number/type/data_flag）",
            "报告章节表（{n} 个报告章节）",
        ],
    )
    def test_stale_count_flagged(self, drift, template):
        # 样本数取「当前注册表章数 + 1」动态构造——与真值同源，随章数演进不腐化
        n = len(drift._REPORT_SECTION_DEFAULT) + 1
        findings = drift.check_section_counts({Path("manual.md"): template.format(n=n)})
        assert len(findings) == 1 and "章节数量断言" in findings[0]

    def test_correct_count_passes(self, drift):
        total = len(drift._REPORT_SECTION_DEFAULT)
        assert drift.check_section_counts({Path("manual.md"): f"页签编号 1~{total}；返回 result（{total} 项）"}) == []

    def test_other_numbers_ignored(self, drift):
        assert drift.check_section_counts({Path("manual.md"): "共 30 项功能开关、19 个指标"}) == []


# ═══ 功能开关表 ═══


def drift_marker() -> str:
    return "**呈现与体验（默认开启 · 只改呈现不改内容）**：\n\n| 开关名 | 默认值 | 说明 |\n|:--|:--|:--|"


class TestSwitchTable:
    def test_extract_stops_at_next_heading(self, drift):
        doc = drift_marker() + "\n| `data_quality` | `true` | 说明 |\n\n## 下一节\n\n| `sina` | `true` | 非开关表 |\n"
        assert drift.extract_switch_table(doc) == {"data_quality": True}

    def test_missing_section_reported(self, drift):
        findings = drift.check_switch_table("没有开关表\n")
        assert len(findings) == 1 and "未找到功能开关表区段" in findings[0]

    def test_missing_flag_and_unknown_flag_reported(self, drift, monkeypatch, drift_parts):
        registry = {"data_quality": drift.feature_switch_registry["data_quality"]}
        monkeypatch.setattr(drift_parts._format, "feature_switch_registry", registry)
        doc = drift_marker() + "\n| `ghost_switch` | `true` | 说明 |\n"
        findings = drift.check_switch_table(doc)
        assert any("`data_quality` 未列入开关表" in f for f in findings)
        assert any("未登记开关 `ghost_switch`" in f for f in findings)

    def test_default_mismatch_reported(self, drift, monkeypatch, drift_parts):
        registry = {"data_quality": drift.feature_switch_registry["data_quality"]}
        monkeypatch.setattr(drift_parts._format, "feature_switch_registry", registry)
        doc = drift_marker() + "\n| `data_quality` | `false` | 说明 |\n"
        findings = drift.check_switch_table(doc)
        assert any("默认值 False 与注册表 True" in f for f in findings)


# ═══ 开关分组计数与默认值断言 ═══


class TestSwitchCounts:
    def test_chain_form_mismatch(self, drift):
        # 计数从注册表现算取值（禁写死演进总数）：仅首组写错一位数
        counts = drift._group_counts()
        wrong = list(counts.values())[0] + 1
        units = [f"{name} {count}" for name, count in zip(drift._GROUP_DOC_NAMES, counts.values())]
        units[0] = f"{drift._GROUP_DOC_NAMES[0]} {wrong}"
        _text = f"分四组（{' / '.join(units)}）"
        findings = drift.check_switch_counts({Path("m.md"): _text})
        assert len(findings) == 1 and str(wrong) in findings[0]

    def test_retired_group_name_flagged(self, drift):
        """旧三组名残留即报——不留新旧两套分组名共存的口子。"""
        findings = drift.check_switch_counts({Path("m.md"): "报告组（后 8 项）= 报告块"})
        assert len(findings) == 1 and "报告组" in findings[0]

    def test_single_group_and_total_forms(self, drift):
        counts = drift._group_counts()
        headers = "\n".join(
            f"**{name}（{count} 项，默认关）**" for name, count in zip(drift._GROUP_DOC_NAMES, counts.values())
        )
        text = f"{headers}\n全部 {len(drift.feature_switch_registry)} 项开关\n"
        assert drift.check_switch_counts({Path("m.md"): text}) == []

    def test_total_mismatch(self, drift):
        wrong_total = len(drift.feature_switch_registry) + 1  # 故意写错的总数（与注册表同演进，不写死字面量）
        findings = drift.check_switch_counts({Path("m.md"): f"提供 **{wrong_total} 项功能开关**的运行时覆写"})
        assert len(findings) == 1 and f"{wrong_total} 项功能开关" in findings[0]

    def test_bold_grouped_counts_from_requirements(self, drift):
        """requirements §11.5 加粗组名写法（分**呈现与体验**（N 项…）等四组）同样受检。"""
        counts = drift._group_counts()
        names = drift._GROUP_DOC_NAMES
        keys = list(counts)
        _wrong = counts[keys[0]] + 1  # 仅首组写错（计数从注册表现算，禁写死演进总数）
        text = (
            f"开关分**{names[0]}**（{_wrong} 项，默认关）、**{names[1]}**（{counts[keys[1]]} 项，默认开）"
            f"与**{names[3]}**（{counts[keys[3]]} 项，多数默认关）四块"
        )
        findings = drift.check_switch_counts({Path("m.md"): text})
        assert len(findings) == 1 and f"**{names[0]}**（{_wrong} 项" in findings[0]

    def test_provide_unbolded_total_mismatch(self, drift):
        """「提供 N 项功能开关」（未加粗）合计写法受检（requirements §11.5 正文原式）。"""
        wrong_total = len(drift.feature_switch_registry) + 1
        findings = drift.check_switch_counts({Path("m.md"): f"提供 {wrong_total} 项功能开关的运行时覆写"})
        assert len(findings) == 1 and f"提供 {wrong_total} 项功能开关" in findings[0]

    def test_complete_items_list_total_form(self, drift):
        """「完整 N 项与分组清单」指引式合计（含加粗形态）与注册表一致时零 finding。"""
        total = len(drift.feature_switch_registry)
        text = f"下表列常用开关（完整 {total} 项与分组清单见配置指引）\n完整 **{total} 项**与分组清单见上表"
        assert drift.check_switch_counts({Path("m.md"): text}) == []


class TestDefaultClaims:
    def test_stale_default_flagged(self, drift):
        findings = drift.check_switch_default_claims({Path("m.md"): "`data_quality`（默认关）"})
        assert len(findings) == 1 and "`data_quality`" in findings[0]

    def test_correct_default_passes(self, drift):
        assert drift.check_switch_default_claims({Path("m.md"): "`data_quality`（默认开）"}) == []

    def test_does_not_cross_to_next_switch(self, drift):
        """相邻开关的默认值不得算到前一个开关头上。"""
        text = "`market_sentiment`（默认关）/ `data_quality`（默认开）"
        assert drift.check_switch_default_claims({Path("m.md"): text}) == []

    def test_suffixed_identifier_not_matched(self, drift):
        assert drift.check_switch_default_claims({Path("m.md"): "`market_temperature_data` 默认关的键"}) == []

    def test_unknown_flag_ignored(self, drift):
        assert drift.check_switch_default_claims({Path("m.md"): "`not_a_switch`（默认关）"}) == []


# ═══ 配置标量默认值表 ═══


class TestConfigDefaults:
    @pytest.mark.parametrize(
        ("shown", "code", "expected"),
        [
            ("true", True, True),
            ("false", False, True),
            ("null", None, True),
            ("None", None, True),
            ("300", 300, True),
            ("300", 299, False),
            ('""', "", True),
            ("data/holdings", "/abs/path/data/holdings", True),
            ("reports", "/abs/path/other", False),
        ],
    )
    def test_values_equal(self, drift, shown, code, expected):
        assert drift._values_equal(shown, code) is expected

    def test_table_mismatch_reported(self, drift):
        doc = "| `news_top_count` | `999` | 新闻条数 |\n"
        findings = drift.check_config_defaults(doc)
        assert len(findings) == 1 and "`news_top_count`" in findings[0]

    def test_structured_and_unknown_keys_skipped(self, drift):
        doc = "| `report_section_order` | `{}` | 结构型 |\n| `not_a_key` | `x` | 未登记 |\n"
        assert drift.check_config_defaults(doc) == []


# ═══ LLM 默认参数表 ═══


class TestLlmDefaults:
    def test_correct_row_passes(self, drift):
        doc = "| `expert_review` | 智囊团深度复盘 | 36000 | 120s | 2h（7200s） | 三阶段 |\n"
        assert drift.check_llm_defaults(doc) == []

    def test_max_tokens_and_timeout_mismatch(self, drift):
        doc = "| `expert_review` | 智囊团深度复盘 | 999 | 30s | 2h（7200s） | 三阶段 |\n"
        findings = drift.check_llm_defaults(doc)
        assert any("max_tokens 文档 999" in f for f in findings)
        assert any("timeout 文档 30s" in f for f in findings)

    def test_ttl_table_mismatch(self, drift):
        doc = "| `news_correlation` | 60s (1m) | 说明 |\n"
        findings = drift.check_llm_defaults(doc)
        assert any("TTL 表 60s" in f for f in findings)


# ═══ TUI 面板编号 ═══


def _panel_doc(
    drift,
    *,
    drop_row: int | None = None,
    wrong_range_idx: int | None = None,
    reverse_map: bool = False,
) -> str:
    """按注册表现造 [S] 面板文档：四组块标题 + 全量行号表 + 键名映射表。

    drop_row 行号表抽掉一行；wrong_range_idx 指定组的块标题区间写错；
    reverse_map 颠倒映射表顺序——三种破坏各对应一类 finding。
    """
    llm = len(drift.filter_menu_llm_modules(drift.get_llm_module_names()))
    counts = drift._group_counts()
    names = drift._GROUP_DOC_NAMES
    lines = ["交互式子菜单（面板标题「配置 LLM 报告章节与功能开关」）"]
    mapping: list[str] = []
    cursor = llm + 1
    for idx, (group, name) in enumerate(zip(counts, names)):
        flags = [flag for flag, _d in drift.switches_in_group(group)]
        first = cursor
        last = cursor + len(flags) - 1
        shown = (first + 1, last + 1) if wrong_range_idx == idx else (first, last)
        lines.append("")
        lines.append(f"**{name}（面板编号 {shown[0]}-{shown[1]}）**：组说明")
        for offset, flag in enumerate(flags):
            n = cursor + offset
            if n != drop_row:
                lines.append(f"| {n} | 开关 {n} | 效果 |")
            mapping.append(f"> | `{flag}` | {n} | {name} |")
        cursor = last + 1
    lines.append("")
    lines.extend(reversed(mapping) if reverse_map else mapping)
    return "\n".join(lines) + "\n"


class TestPanelNumbering:
    def test_correct_panel_passes(self, drift):
        assert drift.check_panel_numbering(_panel_doc(drift)) == []

    def test_missing_number_reported(self, drift):
        llm = len(drift.filter_menu_llm_modules(drift.get_llm_module_names()))
        findings = drift.check_panel_numbering(_panel_doc(drift, drop_row=llm + 3))
        assert any("编号序列" in f for f in findings)

    def test_group_range_mismatch_reported(self, drift):
        findings = drift.check_panel_numbering(_panel_doc(drift, wrong_range_idx=2))
        assert any("块标题编号" in f for f in findings)

    def test_key_map_order_mismatch_reported(self, drift):
        findings = drift.check_panel_numbering(_panel_doc(drift, reverse_map=True))
        assert any("键名→菜单编号映射" in f for f in findings)

    def test_missing_section_reported(self, drift):
        findings = drift.check_panel_numbering("无面板表\n")
        assert len(findings) == 1 and "未找到 [S] 面板编号表区段" in findings[0]


# ═══ 目录树 / 统计表 ═══


class TestTreeParsing:
    def test_reconstructs_nested_paths(self, drift):
        doc = (
            "```\n"
            "investor-util/\n"
            "├── src/                              # 源代码\n"
            "│   ├── __init__.py                   #   包标记\n"
            "│   └── python/                       # 主程序\n"
            "│       └── cache.py                  #   缓存\n"
            "└── scripts/                          # 脚本\n"
            "    └── test-runner.py                #   测试驱动\n"
            "```\n"
        )
        paths = drift.parse_tree_paths(doc)
        assert "src/__init__.py" in paths
        assert "src/python/cache.py" in paths
        assert "scripts/test-runner.py" in paths

    def test_outside_code_fence_ignored(self, drift):
        assert drift.parse_tree_paths("├── ghost.py  # 不在代码块内\n") == set()


class TestProjectStats:
    def test_stats_rows_parsed(self, drift):
        actual = drift._stats_actual()
        files, lines = actual["辅助脚本"]
        doc = f"| 辅助脚本 | Python | {files} | {lines} | 脚本 |\n"
        assert drift.check_project_stats(doc) == []

    def test_stale_stats_reported(self, drift):
        doc = "| 辅助脚本 | Python | 3 | 10 | 脚本 |\n"
        findings = drift.check_project_stats(doc)
        assert any("「辅助脚本」文件数 3" in f for f in findings)
        assert any("「辅助脚本」行数 10" in f for f in findings)

    def test_bold_label_parsed(self, drift):
        """加粗标签行（`| **测试代码** | …`）也须参与比对。"""
        findings = drift.check_project_stats("| **测试代码** | Python | 1 | 2 | 说明 |\n")
        assert any("「测试代码」" in f for f in findings)

    def test_test_count_row_parsed(self, drift, monkeypatch, drift_parts):
        """「测试用例」行的形状（`| — | — | **N 个** |`）须能解析并核对。"""
        monkeypatch.setattr(drift_parts._tree, "_collect_test_count", lambda: 12345)
        findings = drift.check_project_stats("| **测试用例** | — | — | **7,579 个** | 说明 |", with_test_count=True)
        assert any("测试用例数 7579 与 collect-test-coverage 快照 12345" in f for f in findings)

    def test_test_count_skipped_without_flag(self, drift):
        assert drift.check_project_stats("| **测试用例** | — | — | **1 个** | 说明 |") == []

    def test_unknown_label_ignored(self, drift):
        assert drift.check_project_stats("| 不存在的行 | Python | 1 | 1 | — |\n") == []


# ═══ 测试覆盖计数表 ═══


class TestTestCoverageCounts:
    def test_matching_row_passes(self, drift):
        assert drift.check_test_coverage_counts("| `unit` | **100** | ~18s |\n", {"unit": 100}) == []

    def test_mismatch_reported(self, drift):
        findings = drift.check_test_coverage_counts("| `unit` | **99** | ~18s |\n", {"unit": 100})
        assert len(findings) == 1 and "标记 `unit` 覆盖项数 99" in findings[0]

    def test_all_alias_maps_to_total(self, drift):
        findings = drift.check_test_coverage_counts("| `all` | **7532** | ~29s |\n", {"_总收集": 7581})
        assert len(findings) == 1 and "覆盖项数 7532" in findings[0]

    def test_description_cell_number_not_mistaken_for_count(self, drift):
        """「12 子组合计」这类以数字开头的描述列不得当成计数列。"""
        assert (
            drift.check_test_coverage_counts("| `unit`（父标记） | 12 子组合计 | **7,264** |\n", {"unit": 7264}) == []
        )

    def test_annotated_count_cell_parsed(self, drift):
        row = "| `llm` | 全部 LLM 相关（全部为 mock） | **750**（2026-09-16 复核：收集快照 750，未变） |\n"
        assert drift.check_test_coverage_counts(row, {"llm": 750}) == []

    def test_unknown_name_skipped(self, drift):
        assert drift.check_test_coverage_counts("| `ghost_marker` | **1** |\n", {"unit": 1}) == []

    def test_domain_row_matching_passes(self, drift):
        """功能域中文加粗标签行参与核对（标签 → unit 子标记经共享映射）。"""
        row = "| **数据源 Provider** | `providers/` | `unit/providers/` | 545 |\n"
        assert drift.check_test_coverage_counts(row, {"unit_providers": 545}) == []

    def test_domain_row_mismatch_reported(self, drift):
        row = "| **LLM 智能分析** | `llm/` | `unit/llm/` | 1,169 |\n"
        findings = drift.check_test_coverage_counts(row, {"unit_llm": 1183})
        assert len(findings) == 1 and "标记 `unit_llm` 覆盖项数 1169" in findings[0]

    def test_scenario_alias_row_maps_to_parent_marker(self, drift):
        """表内聚合行「端到端业务场景」经别名映射到 scenario 父标记计数。"""
        row = "| **端到端业务场景** | 多模块组合 | `scenario/` | 257 |\n"
        assert drift.check_test_coverage_counts(row, {"scenario": 257}) == []
        findings = drift.check_test_coverage_counts(row, {"scenario": 999})
        assert len(findings) == 1 and "标记 `scenario` 覆盖项数 257" in findings[0]

    def test_bold_row_outside_domain_section_skipped(self, drift):
        """功能域章外的加粗行（其它表）不属本核对域，未登记也不报。"""
        row = "| **任意加粗标签** | 说明 | 1 |\n"
        assert drift.check_test_coverage_counts(row, {"unit": 1}) == []

    def test_unregistered_label_in_domain_section_reported(self, drift):
        """功能域章内出现未登记标签 → 报出而非静默跳过（行加了但映射没跟上）。"""
        from _test_runner.modes import UNIT_DOMAIN_LABELS

        doc = "## 功能域对应测试源\n\n" + "".join(
            f"| **{label}** | `x/` | `unit/` | {i} |\n" for i, label in enumerate(UNIT_DOMAIN_LABELS.values(), 1)
        )
        snapshot = {m: i for i, m in enumerate(UNIT_DOMAIN_LABELS, 1)}
        doc += "| **新功能域** | `x/` | `unit/x/` | 5 |\n"
        findings = drift.check_test_coverage_counts(doc, snapshot)
        assert len(findings) == 1 and "标签 `新功能域` 未登记" in findings[0]

    def test_domain_section_missing_rows_reported(self, drift):
        """映射中的功能域在表中缺行 → 反查报出（以映射集动态遍历，不写死条数）。"""
        from _test_runner.modes import UNIT_DOMAIN_LABELS

        doc = "## 功能域对应测试源\n\n| **数据源 Provider** | `providers/` | `unit/providers/` | 545 |\n"
        findings = drift.check_test_coverage_counts(doc, {"unit_providers": 545})
        for marker, label in UNIT_DOMAIN_LABELS.items():
            if marker == "unit_providers":
                assert not any(label in f for f in findings)
            else:
                assert any(label in f and marker in f for f in findings), label

    def test_domain_labels_single_source_with_collect(self, drift):
        """功能域标签映射与 collect-test-coverage 同一对象（防双处定义漂移）。"""
        from _test_runner.modes import UNIT_DOMAIN_LABELS

        collect = load_script("collect-test-coverage.py")
        assert collect.UNIT_DOMAIN_LABELS is UNIT_DOMAIN_LABELS


# ═══ 构建产物排除 ═══


# ═══ 归档索引 ═══


class TestArchiveIndex:
    """归档索引完整性：管理文档须列全 ``docs/archive/`` 下对应归档文件。

    历史缺口：changelog 的 `## 归档` 索引曾因「发布切换时整段重写已发布段」被一并删除，
    当时无任何断言拦住；本类即该缺口的回归守卫。
    """

    def test_passes_on_real_repo(self, drift):
        """真实仓库：当前三份管理文档的归档索引与磁盘双向一致。"""
        assert drift.check_archive_index() == []

    def test_detects_real_repo_violation(self, drift, tmp_path, monkeypatch, drift_parts):
        """回归：索引被删时能报出（不依赖 `_scan_docs`——changelog 属历史记录类被其排除）。"""
        doc = drift._MANAGEMENTS / "changelog.md"
        broken = tmp_path / "changelog.md"
        broken.write_text(
            doc.read_text(encoding="utf-8").replace("archived_changelog.0.10.x.md", "（已删）"), encoding="utf-8"
        )
        monkeypatch.setattr(drift_parts._ledger, "_ARCHIVE_INDEX_PAIRS", ((broken, "archived_changelog."),))
        findings = drift.check_archive_index()
        assert any("archived_changelog.0.10.x.md" in f and "缺少" in f for f in findings)

    def test_reports_missing_index_entry(self, drift, tmp_path, monkeypatch, drift_parts):
        """索引缺失某归档文件 → 报 finding（正向）。"""
        doc = drift._MANAGEMENTS / "changelog.md"
        broken = tmp_path / "changelog.md"
        broken.write_text(
            doc.read_text(encoding="utf-8").replace("archived_changelog.0.10.x.md", "（已删）"), encoding="utf-8"
        )
        monkeypatch.setattr(drift_parts._ledger, "_ARCHIVE_INDEX_PAIRS", ((broken, "archived_changelog."),))
        assert any("缺少" in f for f in drift.check_archive_index())

    def test_reports_ghost_index_entry(self, drift, tmp_path, monkeypatch, drift_parts):
        """索引引用了不存在的归档文件 → 报 finding（反向）。"""
        doc = drift._MANAGEMENTS / "changelog.md"
        ghost = tmp_path / "changelog.md"
        ghost.write_text(
            doc.read_text(encoding="utf-8") + "\n[x](docs/archive/v9.9.x/archived_changelog.9.9.x.md)\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(drift_parts._ledger, "_ARCHIVE_INDEX_PAIRS", ((ghost, "archived_changelog."),))
        assert any("archived_changelog.9.9.x.md" in f and "不存在" in f for f in drift.check_archive_index())

    def test_covers_three_management_docs(self, drift):
        """三份带归档的管理文档均在被检面内（changelog / plan / review-findings）。"""
        names = {p.name for p, _ in drift._ARCHIVE_INDEX_PAIRS}
        assert names == {"changelog.md", "plan.md", "review-findings.md"}


class TestManagementPartitions:
    """管理文档分区纪律：未完成/已解决/已归档不得错置（含历史失误的可检特征）。"""

    _CHANGELOG_OK = "## [0.11.3-dev] - 开发中（未发布）\n"

    def test_passes_on_real_repo(self, drift):
        """真实仓库：三份管理文档分区纪律无违规。"""
        assert drift.check_management_partitions() == []

    def test_pending_item_in_resolved_section(self, drift):
        """未完成项被误置已解决区（无 changelog 修复记录）→ 报 finding。"""
        rf = (
            "## 当前待处理问题\n\n### P2C\n\n| # | 问题 |\n| **rf-999** | x |\n\n"
            "## 已解决问题\n\n| # | 问题 |\n| **rf-999** | y |\n\n### 归档档案\n"
        )
        findings = drift.audit_management_partitions(review_findings=rf, plan="", changelog=self._CHANGELOG_OK)
        assert any("分区互斥" in f for f in findings)
        assert any("无修复记录" in f for f in findings)

    def test_resolved_item_without_changelog_record(self, drift):
        """仅已解决区一条、但 changelog 无记录 → 报 finding（对应「未完成项误置已解决区」类失误）。"""
        rf = "## 已解决问题\n\n| # | 问题 |\n| **rf-998** | y |\n\n### 归档档案\n"
        findings = drift.audit_management_partitions(review_findings=rf, plan="", changelog=self._CHANGELOG_OK)
        assert any("rf-998" in f and "无修复记录" in f for f in findings)

    def test_resolved_item_backed_by_archived_changelog(self, drift):
        """修复记录在归档 changelog 中亦算有记录（不误报）。"""
        rf = "## 已解决问题\n\n| # | 问题 |\n| **rf-997** | y |\n\n### 归档档案\n"
        findings = drift.audit_management_partitions(
            review_findings=rf,
            plan="",
            changelog=self._CHANGELOG_OK,
            archived_changelogs=["### 修复 rf-997\n"],
        )
        assert findings == []

    def test_completed_plan_left_in_todo(self, drift):
        """未完成区出现 ✅ 已完成项 → 报 finding。"""
        plan = "## 当前迭代待办\n\n#### ✅ `plan-9` 已做完\n\n## 归档\n"
        findings = drift.audit_management_partitions(review_findings="", plan=plan, changelog=self._CHANGELOG_OK)
        assert any("plan-9" in f and "已完成项须移入归档" in f for f in findings)

    def test_archived_plan_still_in_todo(self, drift):
        """已归档项仍在未完成区 → 报 finding（分区互斥）。"""
        plan = "## 当前迭代待办\n\n#### 🔲 `plan-9` 待做\n\n## 归档\n"
        findings = drift.audit_management_partitions(
            review_findings="",
            plan=plan,
            changelog=self._CHANGELOG_OK,
            archived_plans=["#### ✅ `plan-9` 已完成\n"],
        )
        assert any("分区互斥" in f for f in findings)

    def test_archive_prose_mention_is_not_archived_item(self, drift):
        """归档文件正文里的提及不算已归档项（防误报：如「后续项：某某计划项 …」）。"""
        plan = "## 当前迭代待办\n\n#### 🔲 `plan-49` 待做\n\n## 归档\n"
        findings = drift.audit_management_partitions(
            review_findings="",
            plan=plan,
            changelog=self._CHANGELOG_OK,
            archived_plans=["**后续项（另行登记）**：`plan-47`、`plan-49` 转正评估。\n"],
        )
        assert findings == []

    def test_released_section_still_in_live_changelog(self, drift):
        """现行 changelog 段头非开发版本 → 报 finding（已发布段须归归档）。"""
        findings = drift.audit_management_partitions(
            review_findings="", plan="", changelog="## [0.11.2] - 2026-09-24\n"
        )
        assert any("非开发版本" in f for f in findings)

    def test_multiple_version_headers_in_live_changelog(self, drift):
        """现行 changelog 含多个版本段头 → 报 finding。"""
        findings = drift.audit_management_partitions(
            review_findings="", plan="", changelog="## [0.11.3-dev] - x\n\n## [0.11.2] - 2026-09-24\n"
        )
        assert any("个版本段头" in f for f in findings)

    def test_missing_files_do_not_crash(self, drift):
        """空文本（文件缺失）不抛异常，也不臆造 finding。"""
        assert drift.audit_management_partitions(review_findings="", plan="", changelog="") == []


# ═══ 章节-区块矩阵 ═══


class TestBlockMatrix:
    """§4.22 章节-区块矩阵三向对账：文档行 ↔ 区块注册表 ↔ 双端实现提取。"""

    @staticmethod
    def _doc(drift) -> str:
        return drift._TECHNICAL_MD.read_text(encoding="utf-8")

    def test_current_doc_passes(self, drift):
        """真实 technical.md 矩阵与注册表/双端实现三向一致（零 finding）。"""
        assert drift.check_block_matrix(self._doc(drift)) == []

    def test_matrix_keys_match_registry_bidirectionally(self, drift):
        """矩阵 key 集合与注册表双向相等且无重复（结构关系断言，不写死条数）。"""
        rows, findings = drift.parse_block_matrix(self._doc(drift))
        assert findings == []
        assert {r["key"] for r in rows} == {sec["key"] for sec in drift._REPORT_SECTION_DEFAULT}
        assert len({r["key"] for r in rows}) == len(rows)

    def test_stale_html_count_reported(self, drift):
        """改大某章 HTML 区块数 → 与 partial 实测重算不一致。"""
        doc = self._doc(drift)
        rows, _ = drift.parse_block_matrix(doc)
        target = next(r for r in rows if r["count"].isdigit())
        lines = doc.splitlines(keepends=True)
        idx = int(target["line"]) - 1
        old = f"| `{target['key']}` | {target['count']} |"
        assert old in lines[idx]
        lines[idx] = lines[idx].replace(old, f"| `{target['key']}` | {int(target['count']) + 1} |", 1)
        findings = drift.check_block_matrix("".join(lines))
        assert any("HTML 区块数" in f for f in findings)

    def test_missing_row_reported(self, drift):
        """删掉矩阵一行 → 注册表章节缺行被报出。"""
        doc = self._doc(drift)
        rows, _ = drift.parse_block_matrix(doc)
        lines = doc.splitlines(keepends=True)
        victim = lines.pop(int(rows[0]["line"]) - 1)
        assert victim.startswith("|")
        findings = drift.check_block_matrix("".join(lines))
        assert any("缺少注册表章节" in f for f in findings)

    def test_tampered_excel_list_reported(self, drift):
        """篡改矩阵 Excel 区块清单单元格 → 与区块注册表逐列不一致被报出。"""
        doc = self._doc(drift)
        rows, _ = drift.parse_block_matrix(doc)
        target = next(r for r in rows if r["markers"] != "—")
        marker = target["markers"].split(" / ")[0]
        lines = doc.splitlines(keepends=True)
        idx = int(target["line"]) - 1
        assert marker in lines[idx]
        lines[idx] = lines[idx].replace(marker, "已改名的占位区块", 1)
        findings = drift.check_block_matrix("".join(lines))
        assert any("Excel 区块清单与区块注册表不一致" in f for f in findings)

    def test_dash_row_not_counted(self, drift):
        """「—」行不参与重算；计数行若写成「—」会被报出（双向而非单向放行）。"""
        doc = self._doc(drift)
        rows, _ = drift.parse_block_matrix(doc)
        target = next(r for r in rows if r["count"].isdigit())
        lines = doc.splitlines(keepends=True)
        idx = int(target["line"]) - 1
        old = f"| `{target['key']}` | {target['count']} |"
        lines[idx] = lines[idx].replace(old, f"| `{target['key']}` | — |", 1)
        findings = drift.check_block_matrix("".join(lines))
        assert any("HTML 区块数" in f for f in findings)

    def test_impl_html_drift_reported(self, drift, monkeypatch):
        """注册表 html 清单多出一区块 → HTML 实现提取与注册表不一致被报出。"""
        spec = SECTION_BLOCK_SPECS["holdings_detail"]
        monkeypatch.setitem(SECTION_BLOCK_SPECS, "holdings_detail", replace(spec, html=spec.html + ("幽灵区块",)))
        findings = drift.check_block_matrix(self._doc(drift))
        assert any("HTML 区块实测" in f for f in findings)

    def test_impl_excel_drift_reported(self, drift, monkeypatch):
        """注册表 excel 清单多出一区块 → Excel 实现提取与注册表不一致被报出。"""
        spec = SECTION_BLOCK_SPECS["holdings_detail"]
        monkeypatch.setitem(SECTION_BLOCK_SPECS, "holdings_detail", replace(spec, excel=spec.excel + ("幽灵区块",)))
        findings = drift.check_block_matrix(self._doc(drift))
        assert any("Excel 区块实测" in f for f in findings)

    def test_missing_block_contract_reported(self, drift, monkeypatch):
        """删掉注册表某章区块契约 → 键集双向检查报缺契约。"""
        monkeypatch.delitem(SECTION_BLOCK_SPECS, "llm_usage")
        findings = drift.check_block_matrix(self._doc(drift))
        assert any("缺区块契约" in f for f in findings)


class TestMenuBlockConsistency:
    """手册主菜单 code block ↔ tui_menu.MENU_ITEMS 一致性（doc-drift 第 18 项）。"""

    @staticmethod
    def _menu_doc(*, skip: str | None = None, relabel: tuple[str, str] | None = None, extra: str | None = None) -> str:
        """按当前 MENU_ITEMS 动态生成主菜单块（真值派生，不写死清单与条数）。"""
        lines = []
        for key, label, _cb, _is_quit in MENU_ITEMS:
            if key == skip:
                continue
            if relabel and key == relabel[0]:
                label = relabel[1]
            lines.append(f"    [{key}] {label}")
        if extra:
            lines.append(extra)
        return "```text\n" + "\n".join(lines) + "\n```\n"

    def test_consistent_block_passes(self, drift, tmp_path):
        """与真值一致的主菜单块无 finding。"""
        p = tmp_path / "how-to-use-tui-menu.md"
        assert drift.check_menu_blocks({p: self._menu_doc()}) == []

    def test_missing_key_reported(self, drift, tmp_path):
        """块内缺某个菜单键 → 报「缺少」并带真值标签。"""
        p = tmp_path / "how-to-start.md"
        findings = drift.check_menu_blocks({p: self._menu_doc(skip="Q")})
        assert any("[Q]" in f and "缺少" in f for f in findings)

    def test_unknown_key_reported(self, drift, tmp_path):
        """块内出现 MENU_ITEMS 不存在的键 → 报「未知按键」。"""
        p = tmp_path / "how-to-start.md"
        findings = drift.check_menu_blocks({p: self._menu_doc(extra="    [Z] 不存在的项")})
        assert any("[Z]" in f and "未知按键" in f for f in findings)

    def test_label_head_drift_reported(self, drift, tmp_path):
        """标签头与真值不一致 → 报漂移。"""
        p = tmp_path / "how-to-use-tui-menu.md"
        findings = drift.check_menu_blocks({p: self._menu_doc(relabel=("E", "生成基础版报告（仅 Excel）"))})
        assert any("[E]" in f and "标签头" in f for f in findings)

    def test_parenthetical_clarification_allowed(self, drift, tmp_path):
        """括号内补充手册说明（头一致）不误报。"""
        p = tmp_path / "how-to-use-tui-menu.md"
        findings = drift.check_menu_blocks(
            {p: self._menu_doc(relabel=("4", "缓存管理（统计与清理）（二级：先统计后清理）"))}
        )
        assert findings == []

    def test_multicolumn_and_cursor_prefix_parsed(self, drift):
        """两列排版与 `> ` 光标前缀均能解析出完整键集。"""
        items = list(MENU_ITEMS)
        half = (len(items) + 1) // 2
        left = [f"    [{k}] {lb}" for k, lb, _cb, _q in items[:half]]
        left[0] = "  > " + left[0][4:]
        right = [f"    [{k}] {lb}" for k, lb, _cb, _q in items[half:]]
        rows = [left[i] + ("        " + right[i] if i < len(right) else "") for i in range(half)]
        parsed = drift.parse_menu_block_lines("```text\n" + "\n".join(rows) + "\n```\n")
        assert set(parsed) == {k for k, _lb, _cb, _q in MENU_ITEMS}
        assert parsed[items[0][0]] == items[0][1]

    def test_no_menu_block_reported(self, drift, tmp_path):
        """无主菜单块（缺 [E]/[X] 识别标志）→ 报未找到。"""
        p = tmp_path / "faq.md"
        findings = drift.check_menu_blocks({p: "# 无菜单块\n\n普通段落。\n"})
        assert any("未找到主菜单 code block" in f for f in findings)


class TestMigrationPlaceholders:
    """迁档占位↔归档节：占位声明与归档文件对应版本二级标题节的一致性。"""

    def test_real_repo_passes(self, drift):
        """真实仓库当前占位与归档节一致（结构关系断言，不写死版本清单）。"""
        assert drift.check_migration_placeholders() == []

    def test_no_placeholder_no_findings(self, drift, tmp_path):
        """台账无占位 → 无 finding（占位是断言的触发前提）。"""
        assert drift.check_migration_placeholders("无占位文本", archive_root=tmp_path) == []

    def test_reports_placeholder_without_version_section(self, drift, tmp_path):
        """占位存在但归档文件缺该版本二级标题节 → 报出（占位已写、归档正文缺失）。"""
        archive_dir = tmp_path / "v9.9.x"
        archive_dir.mkdir()
        (archive_dir / "archived_review-findings.9.9.x.md").write_text(
            "## 开发期已修复（9.8-dev）\n\n内容\n", encoding="utf-8"
        )
        findings = drift.check_migration_placeholders(
            "（本版开发期已修复项已随 v9.9.9 发布迁入上方归档档案）", archive_root=tmp_path
        )
        assert any("v9.9.9" in f and "无对应版本归档节" in f for f in findings)

    def test_accepts_version_section(self, drift, tmp_path):
        """归档节标题含该版本（v 前缀式）→ 通过。"""
        archive_dir = tmp_path / "v9.9.x"
        archive_dir.mkdir()
        (archive_dir / "archived_review-findings.9.9.x.md").write_text(
            "## v9.9.9 开发期已修复（2026-10-20）\n\n- **rf-x**：条目\n", encoding="utf-8"
        )
        assert drift.check_migration_placeholders("已随 v9.9.9 发布迁入", archive_root=tmp_path) == []

    def test_accepts_legacy_dev_heading(self, drift, tmp_path):
        """旧式节标题（`## 开发期已修复（X.Y.Z-dev）`）同样视为该版本归档节。"""
        archive_dir = tmp_path / "v9.9.x"
        archive_dir.mkdir()
        (archive_dir / "archived_review-findings.9.9.x.md").write_text(
            "## 开发期已修复（9.9.9-dev）\n\n内容\n", encoding="utf-8"
        )
        assert drift.check_migration_placeholders("已随 v9.9.9 发布迁入", archive_root=tmp_path) == []

    def test_reports_missing_archive_file(self, drift, tmp_path):
        """占位存在但对应归档文件不存在 → 报出。"""
        findings = drift.check_migration_placeholders("已随 v8.8.8 发布迁入", archive_root=tmp_path)
        assert any("archived_review-findings.8.8.x.md" in f and "不存在" in f for f in findings)

    def test_duplicate_placeholders_single_finding(self, drift, tmp_path):
        """同一版本多处占位只断言一次（去重后单条 finding）。"""
        archive_dir = tmp_path / "v9.9.x"
        archive_dir.mkdir()
        findings = drift.check_migration_placeholders(
            "已随 v9.9.9 发布迁入\n已随 v9.9.9 发布迁入", archive_root=tmp_path
        )
        assert len(findings) == 1


class TestTreeDescCounts:
    """folders.md 树描述计数禁令：阿拉伯数字+量词禁写（docs/archive 记录域豁免）。"""

    def test_flags_arabic_count(self, drift):
        """文件条目描述含数字+量词 → 报出。"""
        doc = "```\nroot/\n├── a.py # 工具（3 项检查）\n```\n"
        findings = drift.check_tree_desc_counts(doc)
        assert any("a.py" in f and "3 项" in f for f in findings)

    def test_flags_dir_line_count(self, drift):
        """目录条目行同样入检（目录描述也会写文件计数）。"""
        doc = "```\nroot/\n├── llm/ # 场景测试（9 个测试文件）\n```\n"
        assert any("`llm`" in f for f in drift.check_tree_desc_counts(doc))

    def test_archive_domain_exempt(self, drift):
        """docs/archive/ 记录域描述豁免（归档文档的固有数字属记录内容）。"""
        doc = "```\nroot/\n├── docs/\n│   └── archive/\n│       └── x.md # 记录（10 项分析）\n```\n"
        assert drift.check_tree_desc_counts(doc) == []

    def test_chinese_numeral_allowed(self, drift):
        """中文数词形态（设计常量/分类名）不在扫描面。"""
        doc = "```\nroot/\n├── b.py # 合成（三因子/四类路由/多层防御）\n```\n"
        assert drift.check_tree_desc_counts(doc) == []

    def test_real_repo_passes(self, drift):
        """真实仓库树描述无违规计数（结构关系断言，不写死条数）。"""
        text = drift._FOLDERS_MD.read_text(encoding="utf-8")
        assert drift.check_tree_desc_counts(text) == []


class TestTreeVersionOrder:
    """版本目录块升序禁令：同父目录 vN.N.x/ 条目按版本号升序（集合比对不看先后的盲区补位）。"""

    def test_ascending_passes(self, drift):
        """升序版本块 → 无 finding。"""
        doc = (
            "```\nroot/\n├── archive/\n│   ├── v0.1.x/\n│   │   └── a.md # 记录\n"
            "│   ├── v0.9.x/\n│   │   └── b.md # 记录\n"
            "│   └── v0.10.x/\n│       └── c.md # 记录\n```\n"
        )
        assert drift.check_tree_version_order(doc) == []

    def test_descending_reported(self, drift):
        """新块插到组首（真实缺陷形态：0.9 后接 0.13→0.10 倒序）→ 报出乱序。"""
        doc = (
            "```\nroot/\n├── archive/\n│   ├── v0.9.x/\n│   │   └── a.md # 记录\n"
            "│   ├── v0.13.x/\n│   │   └── b.md # 记录\n"
            "│   └── v0.10.x/\n│       └── c.md # 记录\n```\n"
        )
        findings = drift.check_tree_version_order(doc)
        assert any("v0.10.x" in f and "v0.13.x" in f and "乱序" in f for f in findings)

    def test_lexicographic_trap_numeric_order(self, drift):
        """数值序而非字典序：v0.9.x → v0.10.x 合法（字典序会误报）。"""
        doc = (
            "```\nroot/\n├── archive/\n│   ├── v0.9.x/\n│   │   └── a.md # 记录\n"
            "│   └── v0.10.x/\n│       └── b.md # 记录\n```\n"
        )
        assert drift.check_tree_version_order(doc) == []

    def test_independent_parents(self, drift):
        """不同父目录独立判定（a 乱序报出、b 升序不牵连）。"""
        doc = (
            "```\nroot/\n├── a/\n│   ├── v0.2.x/\n│   │   └── x.md # 记录\n"
            "│   └── v0.1.x/\n│       └── y.md # 记录\n└── b/\n"
            "    ├── v0.1.x/\n    │   └── p.md # 记录\n"
            "    └── v0.2.x/\n        └── q.md # 记录\n```\n"
        )
        findings = drift.check_tree_version_order(doc)
        assert len(findings) == 1 and "a/v0.1.x" in findings[0]

    def test_real_repo_passes(self, drift):
        """真实仓库版本块升序（结构关系断言，不写死条数）。"""
        text = drift._FOLDERS_MD.read_text(encoding="utf-8")
        assert drift.check_tree_version_order(text) == []


class TestReturnKeyInvariant:
    """全文档「返回主菜单」键=0 不变量（第 18 项扩展：返回键全局统一）。"""

    def test_zero_forms_all_pass(self, drift, tmp_path):
        """各合法 0 键形态（图块/列表/表格）无 finding。"""
        p = tmp_path / "how-to-use-tui-menu.md"
        text = (
            "```text\n   [0] 返回主菜单\n```\n"
            "- **0 返回主菜单**（回车同效）\n"
            "| D | 聚合三项；`[0]` 返回主菜单，改完可继续改其它项 |\n"
        )
        assert drift.check_return_key_invariant({p: text}) == []

    def test_block_b_key_reported(self, drift, tmp_path):
        """图块 [B] 返回 → 报应为 0。"""
        p = tmp_path / "how-to-use-tui-menu.md"
        findings = drift.check_return_key_invariant({p: "```text\n   [B] 返回主菜单\n```\n"})
        assert any("[B]" in f and "应为 0" in f for f in findings)

    def test_list_bold_b_reported(self, drift, tmp_path):
        """列表项「**B 返回主菜单**」→ 报应为 0。"""
        p = tmp_path / "how-to-use-tui-menu.md"
        findings = drift.check_return_key_invariant({p: "- **B 返回主菜单**（回车同效）\n"})
        assert any("[B]" in f and "应为 0" in f for f in findings)

    def test_table_backtick_key_reported(self, drift, tmp_path):
        """表格内反引号包裹的 `[B]` 返回（真实残留形态，人工 grep 模式会漏）→ 报应为 0。"""
        p = tmp_path / "requirements.md"
        findings = drift.check_return_key_invariant(
            {p: "| D | 聚合三项，另有配置入口地图；`[B]` 返回主菜单，改完可继续改其它项 |\n"}
        )
        assert any("[B]" in f and "应为 0" in f for f in findings)

    def test_prose_exempt(self, drift, tmp_path):
        """自由 prose 叙述豁免（FAQ 的 Ctrl+C 形态 / QA 流内 q 退出非面板导航）。"""
        p = tmp_path / "faq.md"
        text = "按 `Ctrl+C` 中断返回主菜单，检查 `logs/app.log`。\n\n3. 输入问题回车；输入回车或 `q` 返回主菜单。\n"
        assert drift.check_return_key_invariant({p: text}) == []

    def test_distant_key_and_tail_chinese_exempt(self, drift, tmp_path):
        """行内远处非返回键与行尾中文（changelog 式列表/表格叙述）不误报。"""
        p = tmp_path / "technical.md"
        text = (
            "- **优化**：`[L]` 生成确认合并，Esc 即时取消（返回主菜单）语义不变\n"
            "| **Esc** | 子菜单：按 Esc 即时取消返回主菜单，无需找「0 返回」 |\n"
        )
        assert drift.check_return_key_invariant({p: text}) == []
