# -*- coding: utf-8 -*-
"""终端交互契约（docs/managements/DESIGN-TUI.md）结构守卫。

契约是 TUI 交互改动的首个读取入口，断言其骨架不漂移：必需节（含配色与闸门白名单）
子集存在、键分工表覆盖必备键、各表列集合稳定、关键纪律成句存在（口径句）、
护栏编号连续且 DO/DON'T 对偶、术语对照表覆盖内部词、闸门白名单与代码一致、
文内引用的实现文件真实存在。新增节/新增行不破坏断言（子集关系）。
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
    "Colors",
    "Vocabulary",
    "Feedback",
    "Do's and Don'ts",
    "Iteration Guide",
    "Known Gaps",
]

# 表格列契约：列名是判据的一部分（降级成散文即失效），按子集校验
REQUIRED_TABLE_COLUMNS = {
    "Keys": ["键", "唯一语义", "禁止用法"],
    "Defaults": ["场景", "写法", "禁止写法"],
    "Colors": ["角色", "取值", "用在哪", "不得用在"],
    "Feedback": ["场景", "前缀", "要求"],
}

# 口径句：关键纪律必须以成句形式存在（改写成同义弱化表述即失守）
REQUIRED_VERDICTS = {
    "Colors": ["一色一职责", "NO_COLOR", "先排版后上色"],
    "Defaults": ["回车=取消", "安全侧"],
    "Vocabulary": ["适用范围", "数据质量"],
    "Feedback": ["[..]", "[OK]", "[!]", "[ERR]"],
}

# 键分工表必须覆盖的键（子集断言）
REQUIRED_KEYS = ["数字", "回车", "`?`", "`0`", "`Esc`", "字母"]

# 术语对照表必须覆盖的内部词（子集断言）
REQUIRED_INTERNAL_TERMS = ["强刷", "走缓存", "降级"]


def _read() -> str:
    assert CONTRACT.exists(), f"交互契约缺失: {CONTRACT}"
    return CONTRACT.read_text(encoding="utf-8")


def _section(text: str, name: str) -> str:
    """截取以 `## {name}` 开头的章节（含标题行，到下个 `## ` 为止）。

    含标题行：部分纪律写在标题里（如 Colors 的「一色一职责」），口径句需覆盖到。
    """
    lines = text.splitlines()
    buf: list[str] = []
    inside = False
    for line in lines:
        if line.startswith("## "):
            if inside:
                break
            inside = name in line
            if inside:
                buf.append(line)
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


def _subsection(text: str, heading: str) -> str:
    """截取以 `### {heading}` 开头的子章节正文（到下个 `##`/`###` 为止）。"""
    buf: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            if inside:
                break
            inside = heading in line and line.startswith("### ")
            continue
        if line.startswith("### "):
            if inside:
                break
            inside = heading in line
            continue
        if inside:
            buf.append(line)
    return "\n".join(buf)


def _table_columns(body: str) -> list[list[str]]:
    """解析 markdown 表格列头（跳过分隔行）。"""
    tables: list[list[str]] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(set(c) <= set("-: ") and c for c in cells):
            continue  # 分隔行
        tables.append(cells)
    return tables


class TestTableColumns:
    """各表的列集合稳定——表格降级为散文或删列会立刻失守。"""

    @pytest.mark.parametrize(("section", "columns"), sorted(REQUIRED_TABLE_COLUMNS.items()))
    def test_table_headers(self, section, columns):
        body = _section(_read(), section)
        headers = _table_columns(body)
        assert headers, f"{section} 节缺表格"
        assert any(set(columns) <= set(h) for h in headers), (
            f"{section} 节表格列缺项（需含 {columns}），实际列头：{headers}"
        )


class TestVerdictSentences:
    """关键纪律的成句存在性——改写成弱化表述即失守。"""

    @pytest.mark.parametrize(("section", "phrases"), sorted(REQUIRED_VERDICTS.items()))
    def test_verdict_phrases(self, section, phrases):
        body = _section(_read(), section)
        missing = [p for p in phrases if p not in body]
        assert not missing, f"{section} 节缺口径句: {missing}"


class TestGateWhitelistDoc:
    """闸门白名单：文档登记项与代码实际调用点一一对应（防文档与实现各说一套）。"""

    def _doc_gate_functions(self) -> set[str]:
        rows = [ln for ln in _subsection(_read(), "按键闸门白名单").splitlines() if ln.strip().startswith("|")]
        funcs = set()
        for row in rows:
            cell = row.strip().strip("|").split("|")[0].strip().strip("`")
            if "." in cell:
                funcs.add(cell)
        return funcs

    def test_whitelist_rows_match_code(self):
        from src.test.unit.ui.test_prompt_contract import GATE_WHITELIST

        code_funcs = {f"{mod.removesuffix('.py')}.{fn}" for mod, fn in GATE_WHITELIST}
        doc_funcs = self._doc_gate_functions()
        assert doc_funcs == code_funcs, (
            f"契约白名单与代码闸门不一致：文档多 {sorted(doc_funcs - code_funcs)} / "
            f"代码多 {sorted(code_funcs - doc_funcs)}"
        )

    def test_whitelist_has_reason_column(self):
        body = _subsection(_read(), "按键闸门白名单")
        headers = _table_columns(body)
        assert any({"闸门位置", "理由"} <= set(h) for h in headers), headers


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
