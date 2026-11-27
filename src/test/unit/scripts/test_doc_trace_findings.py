"""测试：doc-traces 结论输出与缓存回放解析（_traces_doc/findings.py）。

覆盖：
  - `_render_summary` 退出码契约：无痕迹=0 / 含高置信度=1 / 仅 LOW=2，
    汇总行分类统计按分类名排序、逐字稳定（缓存回放与全量两路同源的基础）
  - `_replay_conclusion` 缓存结论结构校验：非映射/缺键/类型不可转/字段类型不符
    → None（回退全量重算），结构完整 → 回放元组且计数已转 int
"""

from __future__ import annotations

import contextlib
import io
import sys

import pytest
from src.test._script_loader import SCRIPTS_DIR, load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(scope="module")
def findings():
    # 子包模块按 `_traces_doc.bundle` 绝对名导入——与入口脚本一致，需 scripts/ 在
    # import 路径上（生产侧由入口脚本自行插入）
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    return load_script("_traces_doc/findings.py", module_name="doc_traces_findings")


def _render(findings, total: int, high: int, low: int, summary: dict[str, int]) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = findings._render_summary(total, high, low, summary)
    return rc, buf.getvalue()


class TestRenderSummary:
    """汇总输出的退出码契约与分类统计。"""

    def test_clean_reports_zero(self, findings):
        rc, out = _render(findings, 0, 0, 0, {})
        assert rc == 0
        assert "文档干净" in out

    def test_high_confidence_exit_one(self, findings):
        rc, out = _render(findings, 2, 1, 1, {"LOW": 1, "HIGH": 1})
        assert rc == 1
        assert "1 处高置信度" in out
        # 分类统计按分类名排序（缓存与全量两路逐字一致的前提）
        assert out.index("HIGH=1") < out.index("LOW=1")

    def test_low_only_exit_two(self, findings):
        rc, out = _render(findings, 3, 0, 3, {"LOW": 3})
        assert rc == 2
        assert "3 处 LOW 级别痕迹" in out


class TestReplayConclusion:
    """缓存结论结构校验：不完整即回退全量重算。"""

    def test_non_mapping_rejected(self, findings):
        assert findings._replay_conclusion(None) is None
        assert findings._replay_conclusion(["findings"]) is None

    def test_missing_key_rejected(self, findings):
        assert findings._replay_conclusion({"findings": [], "total": 0, "high": 0}) is None

    def test_unconvertible_count_rejected(self, findings):
        """计数不可转 int（脏缓存）→ 回退全量，不半信半疑回放。"""
        assert findings._replay_conclusion({"findings": [], "total": "多", "high": 0, "low": 0, "summary": {}}) is None

    def test_wrong_field_types_rejected(self, findings):
        """findings 非列表 / summary 非映射 → 回退全量。"""
        assert findings._replay_conclusion({"findings": "行", "total": 0, "high": 0, "low": 0, "summary": {}}) is None
        assert findings._replay_conclusion({"findings": [], "total": 0, "high": 0, "low": 0, "summary": []}) is None

    def test_complete_structure_replays(self, findings):
        replay = findings._replay_conclusion(
            {"findings": ["a.md:1 [LOW] 说明 — 正文"], "total": "3", "high": 0, "low": "3", "summary": {"LOW": 3}}
        )
        assert replay is not None
        lines, total, high, low, summary = replay
        assert lines == ["a.md:1 [LOW] 说明 — 正文"]
        assert (total, high, low) == (3, 0, 3)  # 计数已从缓存字符串转 int
        assert summary == {"LOW": 3}
