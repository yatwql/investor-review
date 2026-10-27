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
默认不跑，故冒烟测试只读文件、不触发 pytest 子进程）。"""

from __future__ import annotations
import re
from pathlib import Path
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


def drift_marker() -> str:
    return "**持仓与交易（4 项；成本 / 申赎 / 成本收益 / 风险调整）**：\n\n| 开关名 | 默认值 | 说明 |\n|:--|:--|:--|"


class TestSwitchTable:
    def test_extract_stops_at_next_heading(self, drift):
        doc = drift_marker() + "\n| `market_temperature` | `true` | 说明 |\n\n## 下一节\n\n| `sina` | `true` | 非开关表 |\n"
        assert drift.extract_switch_table(doc) == {"market_temperature": True}

    def test_missing_section_reported(self, drift):
        findings = drift.check_switch_table("没有开关表\n")
        assert len(findings) == 1 and "未找到功能开关表区段" in findings[0]

    def test_missing_flag_and_unknown_flag_reported(self, drift, monkeypatch, drift_parts):
        registry = {"market_temperature": drift.feature_switch_registry["market_temperature"]}
        monkeypatch.setattr(drift_parts._format, "feature_switch_registry", registry)
        doc = drift_marker() + "\n| `ghost_switch` | `true` | 说明 |\n"
        findings = drift.check_switch_table(doc)
        assert any("`market_temperature` 未列入开关表" in f for f in findings)
        assert any("未登记开关 `ghost_switch`" in f for f in findings)

    def test_default_mismatch_reported(self, drift, monkeypatch, drift_parts):
        registry = {"market_temperature": drift.feature_switch_registry["market_temperature"]}
        monkeypatch.setattr(drift_parts._format, "feature_switch_registry", registry)
        doc = drift_marker() + "\n| `market_temperature` | `false` | 说明 |\n"
        findings = drift.check_switch_table(doc)
        assert any("默认值 False 与注册表 True" in f for f in findings)


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
        """requirements §11.5 加粗组名写法（分**持仓与交易**（N 项…）等八组）同样受检。"""
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
        findings = drift.check_switch_default_claims({Path("m.md"): "`market_temperature`（默认关）"})
        assert len(findings) == 1 and "`market_temperature`" in findings[0]

    def test_correct_default_passes(self, drift):
        assert drift.check_switch_default_claims({Path("m.md"): "`market_temperature`（默认开）"}) == []

    def test_does_not_cross_to_next_switch(self, drift):
        """相邻开关的默认值不得算到前一个开关头上。"""
        text = "`market_sentiment`（默认关）/ `market_temperature`（默认开）"
        assert drift.check_switch_default_claims({Path("m.md"): text}) == []

    def test_suffixed_identifier_not_matched(self, drift):
        assert drift.check_switch_default_claims({Path("m.md"): "`market_temperature_data` 默认关的键"}) == []

    def test_unknown_flag_ignored(self, drift):
        assert drift.check_switch_default_claims({Path("m.md"): "`not_a_switch`（默认关）"}) == []


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


class TestDatasourceLlmTtl:
    """`datasource.md` 的 LLM 缓存 TTL 行必须与缓存注册表一致。"""

    def test_correct_rows_pass(self, drift):
        doc = (
            "| 全球政经局势 | `llm_global_macro_` | 24h | 持仓类 |\n"
            "| 智囊团深度复盘 | `llm_expert_review_` | 4h | 持仓类 |\n"
            "| 财经新闻热点与持仓关联分析（LLM 二次关联） | `llm_news_item_` | 4h | 基础类 |\n"
            "| 辩论三段 | `llm_debate_pro_` / `llm_debate_con_` / `llm_debate_synthesis_` | 24h | 持仓类 |\n"
        )
        assert drift.check_datasource_llm_ttl(doc) == []

    def test_wrong_ttl_reports_file_and_row(self, drift):
        doc = "| 智囊团深度复盘 | `llm_expert_review_` | 2h | 持仓类 |\n"
        findings = drift.check_datasource_llm_ttl(doc)
        assert len(findings) == 1
        assert "datasource.md" in findings[0] and "llm_expert_review_" in findings[0]

    def test_news_prefix_maps_to_batch_module(self, drift):
        """`llm_news_item_` 属批量模块（`llm_news_correlation`），前缀反查须命中。"""
        doc = "| 新闻关联 | `llm_news_item_` | 1h | 基础类 |\n"
        findings = drift.check_datasource_llm_ttl(doc)
        assert findings and "llm_news_item_" in findings[0]

    def test_unregistered_prefix_reported(self, drift):
        doc = "| 不存在 | `llm_not_registered_` | 4h | 持仓类 |\n"
        findings = drift.check_datasource_llm_ttl(doc)
        assert findings and "未在缓存注册表登记" in findings[0]

    def test_day_unit_parsed(self, drift):
        """非小时单位（天）也要正确换算：`1天` 与 24h 等价视为一致，`2天` 报不一致。"""
        assert drift.check_datasource_llm_ttl("| 自检 | `llm_self_review_` | 1天 | 持仓类 |\n") == []
        findings = drift.check_datasource_llm_ttl("| 自检 | `llm_self_review_` | 2天 | 持仓类 |\n")
        assert findings and "llm_self_review_" in findings[0]


class TestLlmDefaults:
    def test_correct_row_passes(self, drift):
        doc = "| `expert_review` | 智囊团深度复盘 | 36000 | 120s | 4h（14400s） | 三阶段 |\n"
        assert drift.check_llm_defaults(doc) == []

    def test_max_tokens_and_timeout_mismatch(self, drift):
        doc = "| `expert_review` | 智囊团深度复盘 | 999 | 30s | 4h（14400s） | 三阶段 |\n"
        findings = drift.check_llm_defaults(doc)
        assert any("max_tokens 文档 999" in f for f in findings)
        assert any("timeout 文档 30s" in f for f in findings)

    def test_ttl_table_mismatch(self, drift):
        doc = "| `news_correlation` | 60s (1m) | 说明 |\n"
        findings = drift.check_llm_defaults(doc)
        assert any("TTL 表 60s" in f for f in findings)


def _panel_doc(
    drift,
    *,
    drop_row: int | None = None,
    wrong_range_idx: int | None = None,
    reverse_map: bool = False,
) -> str:
    """按注册表现造两面板文档：``[S]`` 六组块标题 + 行号表、``[C]`` 四块 + 子项 + 键名映射表。

    drop_row 行号表抽掉一行；wrong_range_idx 指定 ``[S]`` 组的块标题区间写错；
    reverse_map 颠倒映射表顺序——三种破坏各对应一类 finding。
    """
    numbered = drift.panel_option_numbers("[S]")
    lines = ["#### [S] 配置报告章节内容呈现", ""]
    mapping: list[str] = []
    by_group: dict[str, list[tuple[int, str]]] = {}
    for number, flag, definition in numbered:
        by_group.setdefault(definition.group, []).append((number, flag))
    for idx, (group, items) in enumerate(by_group.items()):
        name = drift._group_doc_name(group)
        first, last = items[0][0], items[-1][0]
        shown = (first + 1, last + 1) if wrong_range_idx == idx else (first, last)
        lines.append(f"**{name}（面板编号 {shown[0]}-{shown[1]}）**：组说明")
        lines.append("")
        for number, flag in items:
            if number != drop_row:
                lines.append(f"| {number} | 开关 {number} | 效果 |")
            mapping.append(f"> | `{flag}` | `[S]` {number} | {name} |")
        lines.append("")

    lines.append("#### [C] 配置报告章节显隐")
    lines.append("")
    for block in drift.BLOCK_ORDER:
        entries = drift.chapters_in_block(block)
        numbers = [drift.chapter_number(entry.key) for entry in entries]
        first, last = numbers[0], numbers[-1]
        lines.append(f"**{drift.BLOCK_LABELS[block]}（{first}-{last}，写配置文件）**：块说明")
        lines.append("")
        lines.append("| 编号 | 章节 | 键名 |")
        lines.append("|:----:|:-----|:-----|")
        for entry, number in zip(entries, numbers):
            lines.append(f"| {number} | 章节 {number} | `{entry.key}` |")
            if entry.source == drift.SOURCE_FEATURES:
                mapping.append(
                    f"> | `{entry.key}` | `[C]` {number} | {drift._group_doc_name(drift.feature_switch_registry[entry.key].group)} |"
                )
        lines.append("")
    for sub_number, flag in drift.sub_item_numbers().items():
        lines.append(f"| {sub_number} | 子项 {sub_number} | `{flag}` |")
        mapping.append(
            f"> | `{flag}` | `[C]` {sub_number} | {drift._group_doc_name(drift.feature_switch_registry[flag].group)} |"
        )
    lines.append("")
    lines.extend(reversed(mapping) if reverse_map else mapping)
    return "\n".join(lines) + "\n"


class TestPanelNumbering:
    def test_correct_panel_passes(self, drift):
        assert drift.check_panel_numbering(_panel_doc(drift)) == []

    def test_missing_number_reported(self, drift):
        findings = drift.check_panel_numbering(_panel_doc(drift, drop_row=3))
        assert any("编号序列" in f for f in findings)

    def test_group_range_mismatch_reported(self, drift):
        findings = drift.check_panel_numbering(_panel_doc(drift, wrong_range_idx=2))
        assert any("块标题编号" in f for f in findings)

    def test_key_map_order_mismatch_reported(self, drift):
        findings = drift.check_panel_numbering(_panel_doc(drift, reverse_map=True))
        assert any("键名→面板编号映射" in f for f in findings)

    def test_missing_section_reported(self, drift):
        findings = drift.check_panel_numbering("无面板表\n")
        assert any("未找到 [S] 面板编号表区段" in f for f in findings)
        assert any("未找到 [C] 面板编号表区段" in f for f in findings)

    def test_sub_item_number_mismatch_reported(self, drift):
        """子项编号写错（`7.3`）→ 与注册表派生不一致即报出。"""
        doc = _panel_doc(drift).replace("| 7.2 | 子项 7.2 |", "| 7.3 | 子项 7.3 |")
        doc = doc.replace("| `llm_debate_conditional` | `[C]` 7.2 |", "| `llm_debate_conditional` | `[C]` 7.3 |")
        findings = drift.check_panel_numbering(doc)
        assert any("子项编号" in f for f in findings)


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
        assert any("测试用例数 7579 与 test-collect-coverage 快照 12345" in f for f in findings)

    def test_test_count_skipped_without_flag(self, drift):
        assert drift.check_project_stats("| **测试用例** | — | — | **1 个** | 说明 |") == []

    def test_unknown_label_ignored(self, drift):
        assert drift.check_project_stats("| 不存在的行 | Python | 1 | 1 | — |\n") == []


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
        """功能域标签映射与 test-collect-coverage 同一对象（防双处定义漂移）。"""
        from _test_runner.modes import UNIT_DOMAIN_LABELS

        collect = load_script("test-collect-coverage.py")
        assert collect.UNIT_DOMAIN_LABELS is UNIT_DOMAIN_LABELS
