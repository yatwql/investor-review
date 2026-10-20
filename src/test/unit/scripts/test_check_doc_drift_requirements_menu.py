"""doc-drift 第 19 项「需求菜单表」单元测试。

守护 `requirements.md` §3.2 菜单表与 `tui/tui_menu.py`（MENU_ITEMS / MENU_GROUPS）的一致性：
历史漂移（配置组重排未跟、`M`/`Q` 整行缺失、缓存编号写错）此前无任何机检。
断言均构造于**真实文档文本的改动**上，不写死菜单条数（新增菜单项自动纳入）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(scope="module", autouse=True)
def _menu_check():
    """经入口模块加载 `scripts/` 到 sys.path 后再取实现（与相邻 doc-drift 用例同法）。

    直接 `import _doc_drift...` 在测试进程里不可用：只有入口脚本加载时才会把
    `scripts/` 加入 `sys.path`。
    """
    from src.test._script_loader import load_script

    load_script("check-doc-drift.py")
    from _doc_drift._requirements_menu import (
        check_requirements_menu_table as _check,
    )
    from _doc_drift._requirements_menu import (
        parse_requirements_menu as _parse,
    )

    return _check, _parse


REPO_ROOT = Path(__file__).resolve().parents[4]
REQUIREMENTS = REPO_ROOT / "docs" / "managements" / "requirements.md"


def _doc_text() -> str:
    return REQUIREMENTS.read_text(encoding="utf-8")


class TestParseRequirementsMenu:
    """解析器：分组标题与键行按文档顺序取出。"""

    def test_parses_groups_and_keys(self, _menu_check):
        _check, parse = _menu_check
        groups = parse(_doc_text())
        assert groups, "未解析到 §3.2 菜单表"
        titles = [title for title, _keys in groups]
        assert "系统" in titles, "退出项应归入「系统」组"
        keys = [k for _t, ks in groups for k in ks]
        assert len(keys) == len(set(keys)), f"表格键重复: {keys}"

    def test_missing_section_returns_empty(self, _menu_check):
        _check, parse = _menu_check
        assert parse("# 无关文档\n") == []


class TestMenuTableMatchesCode:
    """真实仓库：§3.2 菜单表与 tui_menu 定义一致（回归当前状态）。"""

    def test_current_repo_consistent(self, _menu_check):
        check, _parse = _menu_check
        assert check(_doc_text()) == []

    def test_key_set_equals_menu_items(self, _menu_check):
        from src.python.tui.tui_menu import MENU_ITEMS

        _check, parse = _menu_check
        doc_keys = {k for _t, ks in parse(_doc_text()) for k in ks}
        assert doc_keys == {key for key, *_ in MENU_ITEMS}


class TestDriftDetection:
    """构造漂移：缺行 / 多行 / 组内顺序改 / 分组标题改，均须报出。"""

    def test_missing_row_detected(self, _menu_check):
        """删掉一行菜单项 → 报「缺菜单项」。"""
        text = _doc_text()
        from src.python.tui.tui_menu import MENU_ITEMS

        key = MENU_ITEMS[0][0]
        # 删除形如 `| X | ... |` 的整行（仅表格行，避免误伤正文）
        lines = [ln for ln in text.splitlines(keepends=True) if not ln.startswith(f"| {key} |")]
        check, _parse = _menu_check
        findings = check("".join(lines))
        assert any("缺菜单项" in f for f in findings), findings

    def test_extra_row_detected(self, _menu_check):
        """插入一行未实现的菜单项 → 报「多出未实现的菜单项」。"""
        text = _doc_text().replace(
            "| **系统** | | |",
            "| Z | 不存在的功能 | 占位 |\n| **系统** | | |",
            1,
        )
        check, _parse = _menu_check
        findings = check(text)
        assert any("多出未实现" in f for f in findings), findings

    def test_group_order_drift_detected(self, _menu_check):
        """组内顺序被改（交换两行）→ 报组键顺序不一致。"""
        from src.python.tui.tui_menu import MENU_GROUPS

        title, keys = MENU_GROUPS[0]
        first, second = keys[0], keys[1]
        text = _doc_text()
        lines = text.splitlines(keepends=True)
        i = next(n for n, ln in enumerate(lines) if ln.startswith(f"| {first} |"))
        j = next(n for n, ln in enumerate(lines) if ln.startswith(f"| {second} |"))
        lines[i], lines[j] = lines[j], lines[i]
        check, _parse = _menu_check
        findings = check("".join(lines))
        assert any(f"「{title}」组键顺序" in f for f in findings), findings

    def test_group_title_drift_detected(self, _menu_check):
        """组标题改名 → 报分组标题/次序不一致。"""
        from src.python.tui.tui_menu import MENU_GROUPS

        title = MENU_GROUPS[0][0]
        text = _doc_text().replace(f"| **{title}** | | |", "| **随便改名** | | |", 1)
        check, _parse = _menu_check
        findings = check(text)
        assert any("分组标题/次序" in f for f in findings), findings
