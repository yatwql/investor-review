"""测试：check-code-traces 合法领域值豁免边界（MAGIC/DASHTASK/UNDERSCORE 三类）。

覆盖字母+数字魔法编号、字母-数字疑似任务编号、字母_数字疑似无意义代码三类的
「检出↔豁免」边界：合法领域值（场景标签/分位记号/Excel 单元格/交易日/护栏编号等）
不误伤，越界近邻仍须检出。测试通过脚本 import 复用各扫描判定，不运行真实 CLI。
"""

from __future__ import annotations

import pytest
from src.test._script_loader import load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(scope="module")
def code_traces():
    return load_script("check-code-traces.py")


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


class TestDomainValueExemptions:
    """MAGIC/DASHTASK/UNDERSCORE 三类"字母+数字"模式的检出边界与合法领域值豁免。"""

    def test_legit_letter_digit_not_flagged(self, code_traces):
        """合法领域值不误伤：场景标签（S-P1）、小写缩写（f9）、Excel 单元格/范围。"""
        legit = [
            "S-P1 场景",
            "f9=市盈率",
            "合并 A1:B1",
            "数据在 B2~B5",
        ]
        for line in legit:
            assert _code_hit(code_traces, line) is None, f"合法字母+数字被误伤: {line}"

    def test_magic_number_letter_digit_flagged(self, code_traces):
        """MAGIC：注释中"字母+数字/连续字母+数字"（R11/C26/AB14/HH6）属魔法编号须检出。"""
        flagged = [
            "K9 优先级",  # P0~P4 已入合法领域值（门禁档位/公式价格符号），非此列
            "R17 兼容",
            "C26 兼容",  # 超出约束表编号范围仍是字母+数字，属魔法编号
            "AB14 兼容",  # 连续字母+数字（内嵌命中也是魔法编号）
            "MC19 协议",
            "D8 数据",
            "HH6 组合",
            "C19 契约",
        ]
        for line in flagged:
            assert _code_hit(code_traces, line) is not None, f"魔法编号未检出: {line}"

    def test_magic_percentile_notation_not_flagged(self, code_traces):
        """MAGIC 合法领域值：分位记号（P50/P90/P95/P99）为性能/风险统计口径，非任务编号。"""
        legit = [
            "P95 / P99 报告生成耗时",
            "P50 中位数",
            "P90 上限",
            "分位输出 P95、P99",
        ]
        for line in legit:
            assert _code_hit(code_traces, line) is None, f"分位记号被误伤: {line}"

    def test_magic_percentile_exemption_stays_narrow(self, code_traces):
        """豁免只覆盖两位数分位记号：一位数近邻（P9）仍属魔法编号须检出。"""
        assert _code_hit(code_traces, "P9 协议") is not None

    def test_magic_style_guardrail_codes_not_flagged(self, code_traces):
        """MAGIC 合法领域值：样式护栏编号（E1~E3/W1~W5）为 DESIGN.md「机检落地」
        定义的分类名不误伤；越界邻值（W6/E6）仍须检出，豁免不随手扩位。"""
        for line in ["W3 内联色值观察", "W4/W5 档外字号间距", "E1 强调色越权", "W2 圆角档外"]:
            assert _code_hit(code_traces, line) is None, f"护栏编号被误伤: {line}"
        for line in ["W6 新维度", "E6 规则"]:
            assert _code_hit(code_traces, line) is not None, f"越界护栏编号未检出: {line}"

    def test_dashtask_letter_digit_flagged(self, code_traces):
        """DASHTASK：注释中"字母-数字/连续字母-数字"（F-1/G-1/TASK-22/D-8）疑似任务编号须检出。"""
        flagged = [
            "F-1 方案",
            "G-1 批次",
            "TASK-22 编号",
            "D-8 数据",
            "I-02 配置",
            "CONCENTRATION-03 阈值",  # 非 requirements.md 需求 ID 形态的裸字母-数字
        ]
        for line in flagged:
            assert _code_hit(code_traces, line) is not None, f"疑似任务编号未检出: {line}"

    def test_dashtask_legit_not_flagged(self, code_traces):
        """DASHTASK 合法领域值不误伤：交易日（T-1）、小写下标/编码（i-1/utf-8）、计数算术（N-2 项）。"""
        legit = [
            "T-1 交易日",
            "i-1 下标",
            "utf-8 编码",
            "N-2 项",
            "R-LLM-DB-QA-CONCENTRATION-03/04：需求",  # requirements.md 定义的需求 ID
        ]
        for line in legit:
            assert _code_hit(code_traces, line) is None, f"合法字母-数字被误伤: {line}"

    def test_underscore_letter_digit_flagged(self, code_traces):
        """UNDERSCORE：注释中"字母_数字/连续字母_数字"（F_1/H_1/MINE_22）疑似无意义代码须检出。"""
        flagged = [
            "F_1 变量",
            "H_1 命名",
            "MINE_22 编号",
        ]
        for line in flagged:
            assert _code_hit(code_traces, line) is not None, f"疑似无意义代码未检出: {line}"

    def test_underscore_legit_not_flagged(self, code_traces):
        """UNDERSCORE 合法领域值不误伤：小写语义短名（changed_1m/syl_1y）。"""
        legit = [
            "changed_1m 周期",
            "syl_1y 跨度",
        ]
        for line in legit:
            assert _code_hit(code_traces, line) is None, f"合法字母_数字被误伤: {line}"
