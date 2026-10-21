"""test_trace_check_scripts 兄弟分片（doc）：文档域痕迹（check-doc-traces）检测与豁免。"""

from __future__ import annotations
import tempfile
from pathlib import Path
import pytest

# 夹具按名注入（由测试签名消费），代码里无引用

# ruff: noqa: F811 — 参数与模块级夹具同名（pytest 按名注入），非重定义
from src.test.unit.scripts.test_trace_check_scripts import (
    code_traces,  # noqa: F401
    doc_traces,  # noqa: F401
    _doc_hit,  # noqa: F401
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


class TestDocTraceDetection:
    def test_prior_state_narrative(self, doc_traces):
        assert _doc_hit(doc_traces, "之前是直接读取文件") is not None

    def test_prior_noun(self, doc_traces):
        assert _doc_hit(doc_traces, "此前的判断逻辑") is not None
        assert _doc_hit(doc_traces, "以前的实现方案") is not None

    def test_once_implemented(self, doc_traces):
        assert _doc_hit(doc_traces, "曾经的实现逻辑") is not None

    def test_original_version(self, doc_traces):
        assert _doc_hit(doc_traces, "原始版本") is not None

    def test_historical_implementation(self, doc_traces):
        assert _doc_hit(doc_traces, "历史实现") is not None

    def test_old_logic(self, doc_traces):
        assert _doc_hit(doc_traces, "旧逻辑") is not None

    def test_migrated_to_new(self, doc_traces):
        assert _doc_hit(doc_traces, "迁移到新模块") is not None

    def test_refactored_before(self, doc_traces):
        assert _doc_hit(doc_traces, "重构前逻辑") is not None

    def test_replaced_old(self, doc_traces):
        assert _doc_hit(doc_traces, "替代了旧方案") is not None

    def test_considered_alternative(self, doc_traces):
        assert _doc_hit(doc_traces, "曾考虑过A方案") is not None

    def test_original_contract_migration_flagged(self, doc_traces):
        """文档正文契约改名叙述（历史主键名变迁）须检出。"""
        flagged = [
            "原 factor_exposure 契约迁移为主键",
            "原 factor_exposure 迁移为 style_factor_data 主键",
            "原 factor_exposure dict 迁移为 style_factor_data 主键",
            "原 contract_a 改称 contract_b",
        ]
        for line in flagged:
            assert _doc_hit(doc_traces, line) is not None, f"契约改名叙述未检出: {line}"

    def test_split_out_narrative(self, doc_traces):
        """「拆出」来源归属叙述须检出（含反引号包裹模块路径）。"""
        flagged = [
            "自 generators_orchestrator.py 拆出",
            "自 `generators_orchestrator.py` 拆出（超限文件拆分重构）",
            "由 `_report_helpers.py` 拆出",
            "拆出自 metrics.py",
        ]
        for line in flagged:
            assert _doc_hit(doc_traces, line) is not None, f"拆出来源叙述未检出: {line}"

    # ── 合法当前状态/工具说明应豁免 ──

    def test_runtime_descriptions_not_flagged(self, doc_traces):
        legit = [
            "当前版本为 1.0",
            "保留了历史数据",
            "回测使用历史序列",
            "此前已配置",
            "之前缓存过",
            "原始数据迁移至新库是运行时功能",
        ]
        for line in legit:
            assert _doc_hit(doc_traces, line) is None, f"合法描述被误伤: {line}"

    def test_tool_description_exempted(self, doc_traces):
        """描述"检查哪些历史痕迹"的工具说明行（元描述）应豁免，而非视为痕迹。"""
        legit = [
            "检查历史痕迹的规则说明",
            "文档正文不得带历史痕迹，只反映当前状态",
            "文档不得包含来源叙述、原/旧实现、迁移/重命名",
        ]
        for line in legit:
            assert _doc_hit(doc_traces, line) is None, f"工具说明被误伤: {line}"

    def test_version_header_exempted(self, doc_traces):
        """文档版本头（行首锚定）应豁免。"""
        assert doc_traces._is_excluded("> 文档版本：0.9.10-dev") is True
        assert doc_traces._is_excluded("## 文档版本：v0.9.10") is True

    def test_ip_address_exempted(self, doc_traces):
        """IP 地址/端口（运行时访问语义）应豁免，防裸版本号模式误匹配。

        回归场景：Web UI 文档正文含回环地址/全网监听地址，其内嵌的零开段
        （形如点分十进制）被裸版本号（无 v 前缀）模式误判为版本号。
        """
        legit = [
            "浏览器访问 http://127.0.0.1:8000",
            "默认仅监听本机回环地址 127.0.0.1",
            "监听地址 0.0.0.0",
            "127.0.0.1:8080 已占用",
        ]
        for line in legit:
            assert _doc_hit(doc_traces, line) is None, f"IP 地址被误伤: {line}"

    def test_bare_version_still_flagged(self, doc_traces):
        """裸版本号（无 v 前缀、零开头的点分数字）仍应检出——IP 豁免只针对 IP 地址形态，不削弱版本号检测。"""
        flagged = [
            "该功能在 0.9.10 引入",
            "版本 0.10.2 起支持",
        ]
        for line in flagged:
            assert _doc_hit(doc_traces, line) is not None, f"裸版本号未被检出: {line}"

    # ── 既有模式仍工作 ──

    def test_archive_reference(self, doc_traces):
        assert _doc_hit(doc_traces, "见 docs/archive/ 归档") is not None

    def test_task_id(self, doc_traces):
        assert _doc_hit(doc_traces, "见 rf-117 修复") is not None

    def test_series_alias(self, doc_traces):
        assert _doc_hit(doc_traces, "G系列 方案") is not None
        assert _doc_hit(doc_traces, "b_series 说明") is not None

    def test_legit_letter_digit_not_flagged(self, doc_traces):
        assert _doc_hit(doc_traces, "全系列报告") is None
        assert _doc_hit(doc_traces, "P1 优先级") is None
        assert _doc_hit(doc_traces, "R17 兼容") is None

    def test_arch_constraint_cipher_flagged(self, doc_traces):
        """文档正文架构约束代号（C1~C25）属暗号须检出（须改写为语义描述）。"""
        flagged = [
            "C19 契约",
            "C20 图下说明",
            "C21 指纹同源",
            "C22 挂载点集中",
            "C23 注册表唯一事实来源",
            "C24 凭据值不落日志",
            "C25 交易日基准",
            "C1 约束：代码类型判定复用 code_utils",
            "C14 合规，不写 _ENV.globals",
        ]
        for line in flagged:
            assert _doc_hit(doc_traces, line) is not None, f"架构约束代号未检出: {line}"

    def test_arch_constraint_cipher_false_positives(self, doc_traces):
        """非约束的 C+数字组合不得误伤：十六进制色值、C26+、内嵌命中。"""
        legit = [
            "色值 C00000 不随版本变",
            "C26 方案不在约束表",
            "AB14 协议对接",
            "MC19 型号",
        ]
        for line in legit:
            assert _doc_hit(doc_traces, line) is None, f"非约束 C+数字被误伤: {line}"


class TestDocCipherExemptFiles:
    """架构约束代号豁免文件：约束定义处（technical.md / llm-technical.md）
    正文大量引用 C1~C21（技术名称表）属定义载体，豁免；其余文档（含
    trace-exempt 的计划/变更记录文档）正文一律禁。"""

    def _scan(self, doc_traces, name: str, content: str, chapter_only: bool) -> list:

        with tempfile.TemporaryDirectory() as tmp:
            fpath = Path(tmp) / name
            fpath.write_text(content, encoding="utf-8")
            return doc_traces.scan_file(fpath, verbose=False, chapter_only=chapter_only)

    def _cipher_hits(self, doc_traces, name: str, content: str, chapter_only: bool) -> list:
        return [h for h in self._scan(doc_traces, name, content, chapter_only) if h[1] == "CIPHER"]

    def test_regular_doc_flagged_both_modes(self, doc_traces):
        """普通文档（含 trace-exempt 的计划/变更记录）正文出现 C1~C21 一律检出。"""
        content = "C19 契约注入 pipeline_data\n"
        for chapter_only in (False, True):
            hits = self._cipher_hits(doc_traces, "other.md", content, chapter_only)
            assert len(hits) == 1, f"chapter_only={chapter_only} 应检出 CIPHER: {hits}"

    def test_technical_md_exempt_both_modes(self, doc_traces):
        """technical.md（约束定义处）正文引用 C1~C21 属定义载体，豁免。"""
        content = "C19 契约 / C20 图下说明 / C1 约束\n"
        for chapter_only in (False, True):
            hits = self._cipher_hits(doc_traces, "technical.md", content, chapter_only)
            assert hits == [], f"chapter_only={chapter_only} technical.md 应豁免: {hits}"

    def test_llm_technical_md_exempt(self, doc_traces):
        """llm-technical.md（约束定义处）同样豁免。"""
        content = "C17 约束 / C4 约束\n"
        hits = self._cipher_hits(doc_traces, "llm-technical.md", content, chapter_only=False)
        assert hits == [], f"llm-technical.md 应豁免: {hits}"


class TestDocChapterDetection:
    """正文用数字章节号（"N 章"/"第 N 章"）指代报告具体章节须检出（可读性暗号，
    须改用语义章节名「X」章）；章节数量/序数表述（共 N 章 / N 章基线 / 减至
    N 章 / 出现第 N 章 / N→M 章 / 引号内"N 章"）是合法计数，豁免。"""

    def test_chapter_codes_flagged(self, doc_traces):
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
            assert _doc_hit(doc_traces, line) is not None, f"章节编号暗号未检出: {line}"

    def test_chapter_codes_chinese_flagged(self, doc_traces):
        """中文数字章节编号（第X章 / 裸X章式）指代报告具体章节须检出。"""
        flagged = [
            "三章渲染成本分档",
            "第五章估值分位",
            "第二章合并",
            "第四章摘要引用",
        ]
        for line in flagged:
            assert _doc_hit(doc_traces, line) is not None, f"中文数字章节暗号未检出: {line}"

    def test_chapter_count_exempted(self, doc_traces):
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
            assert _doc_hit(doc_traces, line) is None, f"章节计数表述被误伤: {line}"

    def test_chapter_count_chinese_exempted(self, doc_traces):
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
            assert _doc_hit(doc_traces, line) is None, f"中文数字章节计数表述被误伤: {line}"

    def test_non_patterns_clean(self, doc_traces):
        legit = [
            "一章三区块",
            "4.2 章节归并对照表",
            "19 个章节",
            "章节",
            "21 轮每轮量化验收",
        ]
        for line in legit:
            assert _doc_hit(doc_traces, line) is None, f"合法表述被误伤: {line}"


class TestDocRoundDetection:
    """正文用数字轮次（"第 N 轮"/"经 N 轮"/"N 轮"/"轮 N"）指代开发迭代历史须检出
    （迭代轮次是开发痕迹，正文须改用语义描述）；轮次数量/运行时表述（共 N 轮 /
    N 轮每轮 / 计划分 N 轮 / 轮询 / 轮动 / 第 N 轮循环）是合法计数或业务/运行时
    概念，豁免。changelog/plan/review-findings 与 docs/plan/ 不查本条
    （ROUND 不进 _CHAPTER_PATTERNS，trace-exempt 文档仅章节编号扫描）。"""

    def test_round_codes_flagged(self, doc_traces):
        flagged = [
            "第 14 轮",
            "第4轮",
            "经 8 轮",
            "轮 8",
            "12 轮迭代",
            "轮13 验收标准",
            "对应轮4/轮5",
        ]
        for line in flagged:
            assert _doc_hit(doc_traces, line) is not None, f"迭代轮次暗号未检出: {line}"

    def test_round_codes_chinese_flagged(self, doc_traces):
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
            assert _doc_hit(doc_traces, line) is not None, f"中文数字轮次暗号未检出: {line}"

    def test_round_count_exempted(self, doc_traces):
        legit = [
            "共 12 轮",
            "目标 8 轮",
            "21 轮每轮量化验收",
            "计划分 5 轮推进",
        ]
        for line in legit:
            assert _doc_hit(doc_traces, line) is None, f"轮次计数表述被误伤: {line}"

    def test_round_runtime_exempted(self, doc_traces):
        legit = [
            "轮询超时重试",
            "第 3 轮循环",
            "行业轮动判断",
            "轮换到下一品种",
            "板块轮涨轮跌",
        ]
        for line in legit:
            assert _doc_hit(doc_traces, line) is None, f"轮次运行时表述被误伤: {line}"

    def test_round_runtime_chinese_exempted(self, doc_traces):
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
            assert _doc_hit(doc_traces, line) is None, f"中文数字轮次运行时表述被误伤: {line}"

    def test_round_non_patterns_clean(self, doc_traces):
        legit = [
            "一轮行情",
            "每轮循环",
            "本轮上涨",
            "首轮筛选",
            "两个回合",
        ]
        for line in legit:
            assert _doc_hit(doc_traces, line) is None, f"合法表述被误伤: {line}"

    def test_physical_merge_flagged(self, doc_traces):
        """章节/模块合并历史痕迹（类似迁移，合并写法见下方 flagged 用例）须检出。"""
        flagged = [
            "物理合并「基金风格分析」+「因子暴露分析」",
            "已物理合并为单模块",
            "两页签已物理合并为统一渲染模块",
        ]
        for line in flagged:
            assert _doc_hit(doc_traces, line) is not None, f"物理合并痕迹未检出: {line}"
