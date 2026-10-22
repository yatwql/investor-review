"""测试：历史痕迹检查脚本 — check-code-traces.py / check-doc-traces.py

覆盖：
  - 工具自身豁免（_is_tool_self 模式识别，重命名/新增同类工具不失效）
  - 补强模式能检出真实历史痕迹（此前/曾经/原始/历史实现/旧逻辑/迁移到新/重构前）
  - 合法运行时/当前状态描述不被误伤（历史数据/当前版本/此前已配置/之前缓存过）
  - 文档「工具说明」元描述行豁免
  - 测试文件回归场景元描述豁免（仅 src/test/：旧实现/修复前/回归场景；任务编号不在豁免内）
  - 版本号/任务编号等既有模式仍工作
  - 章节编号暗号（"N 章"/"第 N 章"指代报告具体章节）检出，计数表述（共 N 章等）豁免
  - 迭代轮次暗号（"第 N 轮"/"轮N"指代开发迭代轮次）检出，计数/运行时表述（共 N 轮/
    轮询/轮动等）豁免
  - 架构约束代号（C1~C25，technical.md 定义）在注释/文档正文属暗号须检出；约束定义处
    （technical.md / llm-technical.md）豁免；非约束 C+数字（色值 C00000、C26+、内嵌
    AB14/MC19）不误伤
  - MAGIC/DASHTASK/UNDERSCORE 合法领域值豁免由专文件 test_trace_domain_exemptions.py 覆盖

测试通过脚本 import 方式直接复用 PATTERNS / EXCLUDE_LINE / 各扫描函数，
不运行真实 CLI（避免扫描全仓、受控制台 GBK 编码影响）。"""

from __future__ import annotations
import ast
import os
import sys
import tempfile
from pathlib import Path
import pytest
from src.test._script_loader import load_script


@pytest.fixture(scope="module")
def code_traces():
    return load_script("check-code-traces.py")


@pytest.fixture(scope="module")
def doc_traces():
    return load_script("check-doc-traces.py")


pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


def _code_hit(mod, line: str) -> str | None:
    """返回 check-code-traces 命中的 desc；未命中返回 None。

    与 scan_file 行为一致：对 CHAPTER/ROUND 应用计数/序数豁免，
    对 DASHTASK/UNDERSCORE 应用合法领域值豁免，对 MAGIC 逐 token 应用
    合法领域值豁免（"共 19 章"/"T-1 交易日"/"S1 场景"等合法表述不误报）。
    """
    if mod._is_excluded(line):
        return None
    for pat, cat, desc in mod.PATTERNS:
        if cat == "CHAPTER" and mod._is_chapter_excluded(line):
            continue
        if cat == "ROUND" and mod._is_round_excluded(line):
            continue
        if cat == "DASHTASK" and mod._is_dash_excluded(line):
            continue
        if cat == "UNDERSCORE" and mod._is_under_excluded(line):
            continue
        if cat == "MAGIC":
            for m in __import__("re").finditer(pat, line):
                if not mod._is_magic_match_excluded(line, m.start(), m.end()):
                    return desc
            continue
        if __import__("re").search(pat, line):
            return desc
    return None


def _doc_hit(mod, line: str, task_record: bool = False) -> str | None:
    """返回 check-doc-traces 命中的 desc；未命中返回 None。

    与 scan_file 行为一致：对 CHAPTER/ROUND 应用计数/序数豁免；
    目录树行（│ ├ └ 开头）跳过通用豁免且仅 ARCHIVE 类豁免、STATUS
    仅在目录树行检出（正文当前状态叙述不检）；NARRATIVE 复盘叙事
    仅任务记录域检出（task_record=True）。
    """
    is_tree = bool(mod._TREE_LINE.match(line))
    if not is_tree and mod._is_excluded(line):
        return None
    for pat, cat, desc in mod._DOC_PATTERNS:
        if is_tree and cat == "ARCHIVE":
            continue
        if cat == "STATUS" and not is_tree:
            continue
        if cat == "NARRATIVE" and not task_record:
            continue
        if cat == "CHAPTER" and mod._is_chapter_excluded(line):
            continue
        if cat == "ROUND" and mod._is_round_excluded(line):
            continue
        if __import__("re").search(pat, line):
            return desc
    return None


class TestToolSelfExemption:
    def test_recognizes_self(self, code_traces):
        assert code_traces._is_tool_self("check-code-traces.py") is True
        assert code_traces._is_tool_self("check-doc-traces.py") is True

    def test_recognizes_future_sibling(self, code_traces):
        """未来新增同类工具（check-xml-traces.py）自动豁免，无需改豁免列表。"""
        assert code_traces._is_tool_self("check-xml-traces.py") is True

    def test_does_not_exempt_other_scripts(self, code_traces):
        assert code_traces._is_tool_self("test-runner.py") is False
        assert code_traces._is_tool_self("check-version-consistency.py") is False
        assert code_traces._is_tool_self("chart.min.js") is False

    def test_self_file_scan_clean(self, code_traces):
        """工具自身文件（含新增强模式特征字面量——合并历史与中文数字章节/轮次字样）应
        整文件豁免——扫描 check-code-traces.py 自身不命中任何痕迹，防模式增强自伤。"""
        hits = code_traces.scan_file(Path(code_traces.__file__), verbose=False)
        assert hits == [], f"工具自身文件应豁免，实际命中: {hits}"


class TestCodeTraceDetection:
    """补强后 check-code-traces 应能检出此前/曾经/原始/历史/旧逻辑/迁移等痕迹。"""

    def test_prior_state_narrative(self, code_traces):
        assert _code_hit(code_traces, "之前是直接读取文件") is not None

    def test_prior_noun(self, code_traces):
        assert _code_hit(code_traces, "此前的判断逻辑") is not None
        assert _code_hit(code_traces, "以前的实现方案") is not None

    def test_once_implemented(self, code_traces):
        assert _code_hit(code_traces, "曾经的实现逻辑") is not None

    def test_considered_alternative(self, code_traces):
        assert _code_hit(code_traces, "曾考虑过A方案") is not None

    def test_original_version(self, code_traces):
        assert _code_hit(code_traces, "原始版本") is not None

    def test_historical_implementation(self, code_traces):
        assert _code_hit(code_traces, "历史实现") is not None

    def test_old_logic(self, code_traces):
        assert _code_hit(code_traces, "旧逻辑") is not None

    def test_refactored_before(self, code_traces):
        assert _code_hit(code_traces, "重构前逻辑") is not None

    def test_migrated_to_new(self, code_traces):
        assert _code_hit(code_traces, "迁移到新模块") is not None

    def test_replaced_old(self, code_traces):
        assert _code_hit(code_traces, "替代了旧方案") is not None

    def test_original_contract_migration_flagged(self, code_traces):
        """契约改名叙述（历史主键名变迁）须检出，当前只描述 style_factor_data。"""
        flagged = [
            "原 factor_exposure 契约迁移为主键",
            "原 factor_exposure 迁移为 style_factor_data 主键",
            "原 factor_exposure dict 迁移为 style_factor_data 主键",
            "原 contract_a 改称 contract_b",
        ]
        for line in flagged:
            assert _code_hit(code_traces, line) is not None, f"契约改名叙述未检出: {line}"

    # ── 合法运行时/当前状态描述不应误伤 ──

    def test_runtime_descriptions_not_flagged(self, code_traces):
        legit = [
            "当前版本为 1.0",
            "保留了历史数据",
            "该字段为历史值",
            "回测使用历史序列",
            "此前已配置",
            "之前缓存过",
            "回退到默认配置",
            "原始数据迁移至新库是运行时功能",
        ]
        for line in legit:
            assert _code_hit(code_traces, line) is None, f"合法描述被误伤: {line}"

    # ── 既有模式仍工作 ──

    def test_version_marker(self, code_traces):
        assert _code_hit(code_traces, "该功能在 v0.9.9 引入") is not None

    def test_task_id(self, code_traces):
        assert _code_hit(code_traces, "见 rf-117 修复") is not None

    def test_source_narrative(self, code_traces):
        assert _code_hit(code_traces, "从 utils.py 拆分而来") is not None

    def test_split_out_narrative(self, code_traces):
        """「拆出」来源归属叙述须检出（含反引号包裹模块路径）。"""
        flagged = [
            "自 generators_orchestrator.py 拆出",
            "从 generators_orchestrator.py 拆出",
            "自 `generators_orchestrator.py` 拆出（超限文件拆分重构）",
            "由 `_report_helpers.py` 拆出",
            "拆出自 metrics.py",
        ]
        for line in flagged:
            assert _code_hit(code_traces, line) is not None, f"拆出来源叙述未检出: {line}"


class TestTestFileMetaExemption:
    """回归测试 docstring/注释描述"旧实现做错什么、修复后如何"属测试元数据，
    test_file=True 时豁免；非测试文件（test_file=False）不受影响仍检出。"""

    def test_regression_scene_exempted_in_test_file(self, code_traces):
        """含"回归场景/回归断言/回归："的回归测试说明行应豁免。"""
        legit = [
            "回归场景：建设银行'今日下跌3.41%'曾被误修正为 1.9%（误当收益率）。",
            "回归断言 1.9 → 187.1（而非旧实现把 3.41/4.43 修正成 1.9）。",
            "# ── 回归：百分单位契约 + 单日涨跌语境 + 表格行归因 ──",
        ]
        for line in legit:
            assert code_traces._is_excluded(line, test_file=True) is True, f"回归元描述未豁免: {line}"

    def test_old_behavior_narrative_exempted_in_test_file(self, code_traces):
        """测试注释描述旧实现错误行为（旧实现+误/把/会）应豁免。"""
        legit = [
            "旧实现'整句最近'误归因到 016055",
            "旧实现会误报'016055 为最大持仓'",
            "修复后 orchestrator 源头 ×100、单日涨跌语境按 change_pct 校验。",
        ]
        for line in legit:
            assert code_traces._is_excluded(line, test_file=True) is True, f"旧行为描述未豁免: {line}"

    def test_rf_task_id_in_test_comment_not_exempted(self, code_traces):
        """任务编号不属测试元描述豁免范围：测试注释中的 rf-N 仍视为违规。

        `TEST_META_EXCLUDE` 只覆盖「回归场景/旧实现」等元描述；任务代号只属
        内部计划表（plan.md/review-findings.md），不扩散到实现层注释。
        """
        assert code_traces._is_excluded("表格行归因（rf-159 批次修复）", test_file=True) is False
        assert code_traces._is_excluded("表格行归因（rf-159 批次修复）", test_file=False) is False

    def test_task_id_hard_ban_in_test_file_comment(self, code_traces):
        """scan_file 对 src/test/ 注释中的任务编号硬检出（不受整行豁免放行）。"""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "src" / "test" / "sample.py"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                "x = 1  # 回归：某修复（rf-159 批次修复）\n",
                encoding="utf-8",
            )
            hits = code_traces.scan_file(p, verbose=False)
            assert any(h[1] == "CODE" for h in hits), f"测试注释中的任务编号未检出: {hits}"

    def test_task_id_hard_ban_in_source_comment(self, code_traces):
        """scan_file 对源码注释中的任务编号同样硬检出。"""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "src" / "python" / "sample.py"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("y = 2  # 见 plan-18 任务\n", encoding="utf-8")
            hits = code_traces.scan_file(p, verbose=False)
            assert any(h[1] == "CODE" for h in hits), f"源码注释中的任务编号未检出: {hits}"

    def test_not_exempted_outside_test_file(self, code_traces):
        """同样的旧实现叙述在非测试文件（test_file=False）仍应被检出——工具应检出此历史痕迹，源码侧不削弱。"""
        assert code_traces._is_excluded("旧实现把 3.41/4.43 修正成 1.9", test_file=False) is False
        assert _code_hit(code_traces, "旧实现把 3.41/4.43 修正成 1.9") is not None


class TestReleaseTagExemption:
    """版本演进对照「最新发布」列：tag 名是滚动读数（当前状态），行中版本叙述仍检出。"""

    def test_release_tag_in_evolution_header_exempt(self, doc_traces):
        assert _doc_hit(doc_traces, "| 最新发布（最近发布 tag v0.12.0 · 2026-10-03） |") is None

    def test_release_tag_in_reading_note_exempt(self, doc_traces):
        assert _doc_hit(doc_traces, "最新发布 = 最近一次发布 tag（v0.12.0 · 2026-10-03）；") is None

    def test_version_in_prose_still_flagged(self, doc_traces):
        """豁免不外溢：无「最近发布 tag」上下文的行中版本号叙述仍须检出。"""
        assert _doc_hit(doc_traces, "该缺陷在 v0.12.0 中修复") is not None


class TestEvolutionDevVersionExemption:
    """「当前开发版（」列头版本号豁免（evolution_head 断言强制与 APP_VERSION 同步）。"""

    def test_dev_column_head_exempt(self, doc_traces):
        assert _doc_hit(doc_traces, "| 当前开发版（0.99.0-dev · 本次重跑时的 HEAD · 2026-10-03） |") is None

    def test_version_in_prose_still_flagged(self, doc_traces):
        """豁免不外溢：无「当前开发版（」锚点的行中版本号叙述仍须检出。"""
        assert _doc_hit(doc_traces, "该缺陷在 0.99.0 中已修复") is not None


class TestCodeChapterDetection:
    """代码注释用数字章节号（"N 章"/"第 N 章"）指代报告具体章节须检出（语义命名
    纪律：章节合并/重排后数字即失效，须改用语义章节名「X」章）；章节数量/序数
    表述（共 N 章 / N 章基线 / 减至 N 章 / 出现第 N 章 / N→M 章 / 引号内"N 章"）
    是合法计数，豁免（与 check-doc-traces 的 CHAPTER 检测行为一致）。"""

    def test_chapter_codes_flagged(self, code_traces):
        flagged = [
            "改造 5 章",
            "合并 9 章",
            "9章加X",
            "第 5 章加估值分位",
            "输出到 20 章行动建议",
            "14 章摘要引用",
            "1/2/3 章渲染",
            "4 章估值分位",
        ]
        for line in flagged:
            assert _code_hit(code_traces, line) is not None, f"章节编号暗号未检出: {line}"

    def test_chapter_codes_chinese_flagged(self, code_traces):
        """中文数字章节编号（第X章 / 裸X章式）指代报告具体章节须检出。"""
        flagged = [
            "三章渲染成本分档",
            "第五章估值分位",
            "第二章合并",
            "第四章摘要引用",
        ]
        for line in flagged:
            assert _code_hit(code_traces, line) is not None, f"中文数字章节暗号未检出: {line}"

    def test_chapter_count_exempted(self, code_traces):
        legit = [
            "共 19 章",
            "目标 19 章",
            "合并后 18 章基线",
            "总数 21 章减至 19 章",
            "减至 19 章",
            "20→19 章",
            "「19 章」",
            "开启才出现第 19 章",
        ]
        for line in legit:
            assert _code_hit(code_traces, line) is None, f"章节计数表述被误伤: {line}"

    def test_chapter_count_chinese_exempted(self, code_traces):
        """中文数字计数表述（共X章 / 减至X章 / 一章三区块式计数）应豁免。"""
        legit = [
            "共 二十 章",
            "总数 二十一章 减至 十九章",
            "减至 十九章",
            "「十九章」",
            "一章三区块",
            "一章两区块",
        ]
        for line in legit:
            assert _code_hit(code_traces, line) is None, f"中文数字章节计数表述被误伤: {line}"

    def test_non_patterns_clean(self, code_traces):
        legit = [
            "一章三区块",
            "4.2 章节归并对照表",
            "19 个章节",
            "章节",
            "21 轮每轮量化验收",
        ]
        for line in legit:
            assert _code_hit(code_traces, line) is None, f"合法表述被误伤: {line}"


class TestCodeRoundDetection:
    """代码注释用"第 N 轮"/"轮N"指代开发迭代轮次须检出（语义命名纪律：
    迭代轮次是开发痕迹，代码注释须改用语义描述）；轮次数量/运行时表述
    （共 N 轮 / N 轮每轮 / 轮询 / 轮动 / 第 N 轮循环）是合法计数或业务/
    运行时概念，豁免（与 CHAPTER 检测的计数豁免行为一致）。"""

    def test_round_codes_flagged(self, code_traces):
        flagged = [
            "第 4 轮",
            "第4轮",
            "第 12 轮",
            "12 轮迭代",
            "经 8 轮",
            "轮5 落地",
            "轮 4 落地",
            "轮13 验收标准",
            "对应轮6/轮7",
        ]
        for line in flagged:
            assert _code_hit(code_traces, line) is not None, f"迭代轮次暗号未检出: {line}"

    def test_round_codes_chinese_flagged(self, code_traces):
        """中文数字迭代轮次（第 X 轮式——X 为中文数字三及以上；及"轮 X"式）指代
        开发迭代历史须检出；唯第一轮/第二轮为运行时序数（LLM 圆桌会两轮辩论等），
        不纳入。"""
        flagged = [
            "第三轮落地",
            "第 三 轮验收标准",
            "轮三 落地",
            "对应轮四/轮五",
        ]
        for line in flagged:
            assert _code_hit(code_traces, line) is not None, f"中文数字轮次暗号未检出: {line}"

    def test_round_count_exempted(self, code_traces):
        legit = [
            "共 12 轮",
            "目标 8 轮",
            "21 轮每轮量化验收",
            "计划分 5 轮推进",
        ]
        for line in legit:
            assert _code_hit(code_traces, line) is None, f"轮次计数表述被误伤: {line}"

    def test_round_runtime_exempted(self, code_traces):
        legit = [
            "轮询超时重试",
            "第 3 轮循环",
            "行业轮动判断",
            "轮换到下一品种",
        ]
        for line in legit:
            assert _code_hit(code_traces, line) is None, f"轮次运行时表述被误伤: {line}"

    def test_round_runtime_chinese_exempted(self, code_traces):
        """中文数字运行时序数/计数表述应豁免：LLM 圆桌会两轮辩论、第一轮/第二轮
        增量抓取等为正常行为，非开发迭代痕迹。"""
        legit = [
            "第一轮增量获取",
            "第二轮互相反驳聚焦调仓",
            "圆桌会两轮辩论",
            "共 二十 轮迭代实施",
            "一轮行情",
        ]
        for line in legit:
            assert _code_hit(code_traces, line) is None, f"中文数字轮次运行时表述被误伤: {line}"

    def test_round_non_patterns_clean(self, code_traces):
        legit = [
            "一轮行情",
            "每轮循环",
            "本轮上涨",
            "首轮筛选",
            "两个回合",
        ]
        for line in legit:
            assert _code_hit(code_traces, line) is None, f"合法表述被误伤: {line}"

    def test_physical_merge_flagged(self, code_traces):
        """章节/模块合并历史痕迹（类似迁移，合并写法见下方 flagged 用例）须检出。"""
        flagged = [
            "物理合并「基金风格分析」+「因子暴露分析」",
            "已物理合并为单模块",
            "两页签已物理合并为统一渲染模块",
        ]
        for line in flagged:
            assert _code_hit(code_traces, line) is not None, f"物理合并痕迹未检出: {line}"


class TestCommentExtraction:
    """_py_comment_lines 对多行 docstring 的 in_docstring 状态必须正确开关，
    否则 docstring 后的 assert/代码行会被误当作 docstring 提取（泄漏误报）。"""

    def test_close_line_with_trailing_text_no_leak(self, code_traces):
        """关闭行含内容（…内容\"\"\"）时正确关闭，docstring 后的 assert 不泄漏。"""
        sample = 'x = 1\n"""这是说明，\n第二行内容。"""\nassert _doc_hit(doc_traces, "此前直接读取文件") is not None\n'
        extracted = [txt for _, txt in code_traces._py_comment_lines(sample)]
        assert "此前直接读取文件" not in "".join(extracted), "docstring 状态泄漏到 assert 行"

    def test_plain_close_line_no_leak(self, code_traces):
        """单独一行的关闭三引号（\"\"\"）正常关闭，后续代码不泄漏。"""
        sample = (
            '"""回归场景：旧实现把 3.41/4.43 修正成 1.9（描述被测行为）。\n'
            "这是 docstring 第二行。\n"
            '"""\n'
            'assert _doc_hit(doc_traces, "历史实现") is not None\n'
        )
        extracted = [txt for _, txt in code_traces._py_comment_lines(sample)]
        assert '历史实现" is not None' not in "".join(extracted), "docstring 状态泄漏到 assert 行"


def _ident_hit(code_traces, source: str) -> str | None:
    """返回 _scan_identifiers 对临时 .py 代码片段的命中 desc；未命中返回 None。

    每次调用生成唯一临时文件，避免并行 worker 写同一路径冲突。
    """
    fd, path = tempfile.mkstemp(suffix=".py", prefix="trace_ident_")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(source)
    try:
        hits = code_traces._scan_identifiers(Path(path))
        return hits[0][2] if hits else None
    finally:
        os.remove(path)


class TestTaskCodeCommentPatterns:
    """注释 CODE 模式应检出任务编号/系列代号，不误伤合法字母+数字引用。"""

    def test_series_alias_english(self, code_traces):
        assert _code_hit(code_traces, "b_series 说明") is not None

    def test_series_alias_chinese(self, code_traces):
        assert _code_hit(code_traces, "G系列 方案") is not None
        assert _code_hit(code_traces, "B系列 批次") is not None

    def test_existing_task_id_patterns_still_work(self, code_traces):
        assert _code_hit(code_traces, "见 rf-117 修复") is not None
        assert _code_hit(code_traces, "plan-18 任务") is not None

    def test_legit_series_words_not_flagged(self, code_traces):
        legit = [
            "drawdown_series 列表",
            "holding_series",
            "全系列报告",
            "中证指数系列",
        ]
        for line in legit:
            assert _code_hit(code_traces, line) is None, f"合法系列词被误伤: {line}"

    def test_arch_constraint_codes_flagged(self, code_traces):
        """架构约束代号（C1~C25，technical.md 定义）在注释中属暗号须检出。"""
        flagged = [
            "C1 约束：代码类型判定复用 code_utils",
            "C3 原子写入",
            "C8 日志统一",
            "C14 合规，不写 _ENV.globals",
            "C20 图下说明",
            "C21 指纹同源",
            "C22 挂载点集中",
            "C23 注册表唯一事实来源",
            "C24 凭据值不落日志",
            "C25 交易日基准",
        ]
        for line in flagged:
            assert _code_hit(code_traces, line) is not None, f"架构约束代号未检出: {line}"

    def test_arch_constraint_code_false_positives(self, code_traces):
        """非约束 C+数字不误伤：十六进制色值（#C00000）、标识符内嵌（x_c20_style）。"""
        legit = [
            "#C00000",  # 十六进制色值（# 前缀且 5 位数字，MAGIC/CODE 均不命中）
            "x_c20_style",  # 标识符内嵌（_c20 前为小写字母，MAGIC 需大写开头）
        ]
        for line in legit:
            assert _code_hit(code_traces, line) is None, f"非约束 C+数字被误伤: {line}"


class TestTaskCodeIdentifierCheck:
    """代码标识符不得使用任务编号/系列代号（IDENT 扫描）。"""

    def test_task_code_identifiers_flagged(self, code_traces):
        flagged = [
            "F4 = 1",
            "b_series = []",
            "G系列 = 1",
            "rf_205_fix = 1",
            "plan18_hack = 1",
            "def rf_100_helper():\n    pass",
            "class TestSP5QDII:\n    pass",  # 测试类名内嵌系列编号
            "class TestSP10CrossHoldingMerge:\n    pass",
        ]
        for src in flagged:
            assert _ident_hit(code_traces, src) is not None, f"应命中: {src}"

    def test_legit_short_locals_not_flagged(self, code_traces):
        legit = [
            "h1 = 1",
            "f1 = 1",
            "x0 = 0.0",
            "p50 = 1",
            "drawdown_series = []",
            "def test_provider(x1, y1):\n    pass",
            "class TestPenetrationQdii:\n    pass",  # 纯语义名
            "class TestDegradationSignal1:\n    pass",  # 语义词 + 变体号
            "class TestHTTP2Support:\n    pass",  # 协议名（连续大写后接数字再接大写）待评估形状
        ]
        for src in legit:
            assert _ident_hit(code_traces, src) is None, f"不应命中: {src}"


class TestIdentifierExtraction:
    """_iter_identifiers 应从代码中提取到预期标识符名。"""

    def test_py_ast_extracts_names(self, code_traces):
        src = (
            "import math as m\n"
            "class PortfolioModel:\n"
            "    def compute(self, data):\n"
            "        result = data + 1\n"
            "        return result\n"
        )
        names = {n for _, n in code_traces._py_identifier_names(ast.parse(src))}
        assert {"PortfolioModel", "compute", "data", "result", "m"} <= names

    def test_js_decl_extracts_names(self, code_traces):
        src = "var B6 = 1;\nconst chart = new Chart();\nfunction draw() {}\n"
        names = sorted(n for _, n in code_traces._js_identifier_names(src))
        assert "B6" in names
        assert "chart" in names
        assert "draw" in names


class TestCoreLayeringGuard:
    """core → 上层反向 import 守卫（check-code-traces 分层纪律分支）。

    装配契约：上游层通过注册钩子把状态快照注入 core（如
    circuit_breaker.register_breaker_status / doctor.register_adapter_survey），
    core 生产代码不得再 ``src.python.<上层>`` 反向 import（含函数内延迟 import）。
    """

    def test_core_reverse_import_flagged(self, code_traces, tmp_path):
        core_dir = tmp_path / "src" / "python" / "core"
        core_dir.mkdir(parents=True)
        fpath = core_dir / "demo_module.py"
        fpath.write_text(
            "def bad():\n    from src.python.llm.circuit_breaker import _circuit_failures\n    return _circuit_failures\n",
            encoding="utf-8",
        )
        hits = code_traces._scan_core_layering(fpath)
        assert hits and hits[0][1] == "HIGH" and "llm" in hits[0][3]

    def test_core_top_level_import_flagged(self, code_traces, tmp_path):
        core_dir = tmp_path / "src" / "python" / "core"
        core_dir.mkdir(parents=True, exist_ok=True)
        fpath = core_dir / "demo_top_import.py"
        fpath.write_text("from src.python.fetcher import chain\n", encoding="utf-8")
        assert code_traces._scan_core_layering(fpath)

    def test_non_core_and_tests_not_in_scope(self, code_traces, tmp_path):
        fpath = tmp_path / "src" / "test" / "unit" / "core" / "test_x.py"
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text("from src.python.fetcher.chain import _DEFAULT_CHAINS\n", encoding="utf-8")
        assert code_traces._scan_core_layering(fpath) == []
        # 测试文件位置的其他 core 目录同样不约束
        other = tmp_path / "elsewhere" / "core" / "demo.py"
        other.parent.mkdir(parents=True, exist_ok=True)
        other.write_text("from src.python.report.foo import bar\n", encoding="utf-8")
        assert code_traces._scan_core_layering(other) == []

    def test_exempt_probe_file(self, code_traces, tmp_path):
        core_dir = tmp_path / "src" / "python" / "core"
        core_dir.mkdir(parents=True, exist_ok=True)
        # 生产目录中的豁免文件名（探针网关薄透传，technical.md 已登记例外）
        fpath = core_dir / "check_sources.py"
        fpath.write_text("from src.python.fetcher.gw import x\n", encoding="utf-8")
        assert code_traces._scan_core_layering(fpath) == []
        del tmp_path


class TestScanDomainIntegrity:
    """扫描域自证：扫描目录真实存在、规则载体目录被跳过、合法领域值不误伤。

    关键回归：扫描目录路径一旦算错（深度不对），目录不存在 → 整轮扫描
    静默跳过 → 永远“通过”。故此处对目录存在性做硬断言，并用种入式样本
    （tmp 目录）验证扫描器确实会报事——两者合起来才排除“绿得没问题”。
    """

    def test_scan_dirs_exist_under_repo_root(self, code_traces):
        assert (code_traces.REPO_ROOT / "src" / "python").is_dir()
        assert (code_traces.REPO_ROOT / "scripts" / "_traces_code").is_dir()
        missing = [str(p) for p in code_traces.SCAN_DIRS if not p.is_dir()]
        assert missing == [], f"扫描目录不存在（会静默跳过整轮扫描）：{missing}"
        outside = [str(p) for p in code_traces.SCAN_DIRS if not p.is_relative_to(code_traces.REPO_ROOT)]
        assert outside == [], f"扫描目录跑出仓库根（路径深度算错）：{outside}"

    def test_planted_violation_is_reported(self, code_traces, tmp_path, monkeypatch, capsys):
        """种入式样本：扫描器必须真的报出违规（正面探针）。"""
        src_dir = tmp_path / "src" / "python"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "demo_planted.py").write_text("# rf-999\n", encoding="utf-8")
        monkeypatch.setattr(code_traces, "SCAN_DIRS", [src_dir])
        monkeypatch.setattr(sys, "argv", ["check-code-traces.py", "--ci"])
        with pytest.raises(SystemExit) as exc:
            code_traces.main()
        out = capsys.readouterr().out
        assert exc.value.code != 0
        assert "demo_planted.py:1" in out and "[CODE]" in out

    def test_planted_clean_tree_passes(self, code_traces, tmp_path, monkeypatch, capsys):
        """同样的扫描路径，无违规文件 → 必须通过（负面探针，防止“永远报事”）。"""
        src_dir = tmp_path / "src" / "python"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "demo_clean.py").write_text("# 逐笔聚合后再分桶\n", encoding="utf-8")
        monkeypatch.setattr(code_traces, "SCAN_DIRS", [src_dir])
        monkeypatch.setattr(sys, "argv", ["check-code-traces.py", "--ci"])
        with pytest.raises(SystemExit) as exc:
            code_traces.main()
        assert exc.value.code == 0
        assert "未发现历史变更痕迹" in capsys.readouterr().out

    def test_rule_carrier_dir_skipped(self, code_traces, tmp_path):
        """规则定义载体目录（模式/豁免正则字面量所在）整文件跳过。"""
        carrier = tmp_path / "_traces_code"
        carrier.mkdir()
        fpath = carrier / "patterns.py"
        fpath.write_text("# 规则定义：rf-123 第X章 R11 F-1\n", encoding="utf-8")
        assert code_traces.scan_file(fpath, False) == []

    def test_identical_literal_outside_carrier_still_flagged(self, code_traces, tmp_path):
        """同一字面量落在扫描域内（非载体目录）必须照报，豁免不外溢。"""
        fpath = tmp_path / "demo_patterns.py"
        # 每类各占一行：scan_file 每行首个命中即 break（任务编号还会提前 continue），
        # 因此逐类分行才能验证四类全部仍被检出。
        fpath.write_text(
            "# 暗号代号 R11\n# 指代说明见第3章\n# 疑似任务 F-1\n# 任务号 rf-123\n",
            encoding="utf-8",
        )
        cats = {cat for _, cat, _, _ in code_traces.scan_file(fpath, False)}
        assert {"CODE", "CHAPTER", "MAGIC", "DASHTASK"} <= cats


class TestLegitimateDomainValueExemption:
    """合法领域值（门禁档位/页面/时序/阶段/网络地址）不误伤，且豁免不吞同侧违规。"""

    def test_domain_values_do_not_flag(self, code_traces):
        for line in (
            "# F10 交易费率页取数",
            "# P1 门禁档位",
            "# T0 为事件窗口锚定交易日",
            "# Phase1 基准与 Phase3 对照",
            "# S0 起始市值 MV0",
            "# 样式护栏 E1/W2 已机检",
            "# 回环网段 127.0.0.0/8 覆盖全部本机地址",
        ):
            assert _code_hit(code_traces, line) is None, line

    def test_neighbour_violation_on_same_line_still_flagged(self, code_traces):
        """合法值与违规 token 同行 → 仍必须报出（行级豁免不吞 token）。"""
        assert _code_hit(code_traces, "# F10 与 P1 之外还有 R11") is not None
        assert _code_hit(code_traces, "# 127.0.0.1 另有 0.12.6 版本痕迹") is not None


class TestSharedCliContract:
    """本脚本采纳 _checklib 统一 CLI 契约（-v/--verbose + --ci）。"""

    def test_help_exposes_shared_flags(self, code_traces, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["check-code-traces.py", "--help"])
        with pytest.raises(SystemExit) as exc:
            code_traces.main()
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "-v, --verbose" in out
        assert "--ci" in out

    def test_add_common_args_is_shared_helper(self, code_traces):
        shared = sys.modules.get("_checklib")
        assert shared is not None, "check-code-traces 应从 _checklib 引入共享 CLI 助手"
        assert code_traces.add_common_args is shared.add_common_args
