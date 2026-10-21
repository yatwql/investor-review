"""结构化决策头渲染剥离接线测试（决策头生命周期：登记 → 剥离 → HTML/Excel 双端写出）。

核心剥离逻辑在 `core/decision_header.py` 单测覆盖；本文件锁定报告装配层的接线
契约：登记解析先读到原始载荷，双端 writer 收到的 llm_content 已完成剥离。
"""

import re
from pathlib import Path

import pytest

from src.python.core.constants import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]

_ASSEMBLY = Path(PROJECT_ROOT) / "src" / "python" / "report" / "_generation_full.py"
_ASSEMBLY_BOTH = Path(PROJECT_ROOT) / "src" / "python" / "report" / "_generation_both.py"


class TestHeaderStripWiring:
    """装配层接线：strip 在登记之后、HTML/Excel 写出之前作用于 llm_content。"""

    def test_capture_registered_before_strip(self) -> None:
        source = _ASSEMBLY.read_text(encoding="utf-8")
        capture = source.index("record_llm_decisions_and_review_block(")
        strip = source.index("strip_structured_header(")
        assert capture < strip

    def test_strip_before_both_writer_calls(self) -> None:
        source = _ASSEMBLY.read_text(encoding="utf-8")
        strip = source.index("strip_structured_header(")
        assert strip < source.index("_generate_full_html_report(")
        assert strip < source.index("_generate_full_excel_report(")

    def test_strip_applied_to_llm_content_tuple(self) -> None:
        source = _ASSEMBLY.read_text(encoding="utf-8")
        assert re.search(r"llm_content\s*=\s*tuple\(\s*strip_structured_header", source)

    def test_strip_function_imported_from_core_decision_header(self) -> None:
        source = _ASSEMBLY.read_text(encoding="utf-8")
        assert "from src.python.core.decision_header import strip_structured_header" in source
