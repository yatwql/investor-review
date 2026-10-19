# -*- coding: utf-8 -*-
"""终端交互契约（docs/managements/DESIGN-TUI.md）结构守卫。

契约是 TUI 交互改动的首个读取入口，断言其骨架不漂移：必需节子集存在、
键分工表覆盖必备键、护栏编号连续且 DO/DON'T 对偶、术语对照表覆盖内部词、
文内引用的实现文件真实存在。新增节/新增护栏不破坏断言（子集关系）。
"""

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]

REPO_ROOT = Path(__file__).resolve().parents[4]
CONTRACT = REPO_ROOT / "docs" / "managements" / "DESIGN-TUI.md"

# 必需节（子集断言：只防删除/改名，不锁总数）
REQUIRED_SECTIONS = [
    "Overview",
    "Keys",
    "Prompts",
    "Defaults",
    "Vocabulary",
    "Feedback",
    "Do's and Don'ts",
    "Iteration Guide",
    "Known Gaps",
]

# 键分工表必须覆盖的键（子集断言）
REQUIRED_KEYS = ["数字", "回车", "`?`", "`0`", "`Esc`", "字母"]

# 术语对照表必须覆盖的内部词（子集断言）
REQUIRED_INTERNAL_TERMS = ["强刷", "走缓存", "降级"]


def _read() -> str:
    assert CONTRACT.exists(), f"交互契约缺失: {CONTRACT}"
    return CONTRACT.read_text(encoding="utf-8")


def _section(text: str, name: str) -> str:
    """截取以 `## {name}` 开头的章节正文（到下个 `## ` 为止）。"""
    lines = text.splitlines()
    buf: list[str] = []
    inside = False
    for line in lines:
        if line.startswith("## "):
            if inside:
                break
            inside = name in line
            continue
        if inside:
            buf.append(line)
    return "\n".join(buf)


class TestContractStructure:
    """骨架与内容契约。"""

    def test_required_sections_present(self):
        text = _read()
        headings = [line for line in text.splitlines() if line.startswith("## ")]
        missing = [s for s in REQUIRED_SECTIONS if not any(s in h for h in headings)]
        assert not missing, f"DESIGN-TUI.md 缺契约节: {missing}"

    def test_key_table_covers_required_keys(self):
        body = _section(_read(), "Keys")
        missing = [k for k in REQUIRED_KEYS if k not in body]
        assert not missing, f"键分工总表缺键: {missing}"

    def test_vocabulary_table_covers_internal_terms(self):
        body = _section(_read(), "Vocabulary")
        missing = [t for t in REQUIRED_INTERNAL_TERMS if t not in body]
        assert not missing, f"术语对照表缺内部词: {missing}"

    def test_prompt_template_has_four_components(self):
        """提示三段式（用户称「三段式」、实为四成分）不得丢项。"""
        body = _section(_read(), "Prompts")
        for component in ["动作指令", "默认项声明", "帮助入口", "返回键", "折行"]:
            assert component in body, f"提示模板缺成分说明: {component}"


class TestGuardrails:
    """护栏条目结构。"""

    def test_guardrails_numbered_and_paired(self):
        body = _section(_read(), "Do's and Don'ts")
        items = [ln for ln in body.splitlines() if ln.strip() and ln.strip()[0].isdigit()]
        assert items, "护栏条目为空"
        numbered = [int(ln.strip().split(".")[0]) for ln in items]
        assert numbered == list(range(1, len(numbered) + 1)), f"护栏编号不连续: {numbered}"
        unpaired = [ln for ln in items if "DO" not in ln or "DON'T" not in ln]
        assert not unpaired, f"护栏未成对（缺 DO 或 DON'T）: {unpaired}"

    def test_known_gaps_have_status(self):
        """未覆盖面必须逐条标注状态（不得留无主缺口，也不得在此引用任务代号）。"""
        body = _section(_read(), "Known Gaps")
        rows = [ln for ln in body.splitlines() if ln.strip().startswith("|") and "缺口" not in ln and "---" not in ln]
        assert len(rows) >= 3, "Known Gaps 至少登记三项"
        no_status = [ln for ln in rows if ln.rstrip().rstrip("|").endswith("| ")]
        assert not no_status, f"缺口行缺状态列: {no_status}"

    def test_no_task_codes_in_contract(self):
        """契约是常驻判据文档，不得引用任务代号（任务代号只活在计划/自审台账）。"""
        text = _read()
        leaked = re.findall(r"\b(?:plan|rf)-\d+\b", text)
        assert not leaked, f"契约中出现任务代号: {sorted(set(leaked))}"


class TestContractReferencedFilesExist:
    """契约里点名的实现文件必须真实存在（防引用漂移）。"""

    def test_referenced_impl_files_exist(self):
        for rel in [
            "src/python/tui/tui_keys.py",
            "src/python/tui/panel_runtime.py",
            "src/python/tui/text_layout.py",
            "src/python/tui/tui_menu.py",
        ]:
            assert (REPO_ROOT / rel).is_file(), f"契约引用的实现文件不存在: {rel}"

    def test_companion_design_contract_linked(self):
        """与 Web 侧 DESIGN.md 的对称关系必须在文内可点（两侧契约不得各自为政）。"""
        text = _read()
        assert "DESIGN.md" in text, "缺少指向 DESIGN.md 的对称引用"
        assert (REPO_ROOT / "docs" / "managements" / "DESIGN.md").is_file()
