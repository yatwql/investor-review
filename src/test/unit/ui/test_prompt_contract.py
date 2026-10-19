# -*- coding: utf-8 -*-
"""提示语契约机检（DESIGN-TUI.md「Prompts / Defaults」两节的执行载体）。

三条硬规则：

1. 列表面板提示必须由 ``prompt_text.panel_prompt`` 产出——手写字面量即失败；
2. 提示里不得出现「（直接回车取消）」这类**把回车取消藏进括注**的形态
   （回车承担取消语义时必须置句首显式声明，见契约 Defaults 节）；
3. ``input_choice`` 的字符串字面量提示必须声明回车行为（含「回车=」），
   否则用户读不出按键后果——运行时内部短提示在 ALLOWLIST 内豁免。

新增违反须改实现，不得加白名单；白名单只减不增。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]

REPO_ROOT = Path(__file__).resolve().parents[4]
TUI_DIR = REPO_ROOT / "src" / "python" / "tui"

# 运行时/键位层内部的短提示（非面向用户的选择提示，无可声明的回车默认项）
ALLOWLIST_PROMPTS = {
    ("panel_runtime.py", "  > "),
    ("handlers_config.py", "  > "),
    ("handlers_whatif.py", "  请输入编号: "),
    ("tui_handlers.py", "  请输入编号: "),
}


def _tui_sources():
    return sorted(TUI_DIR.glob("*.py"))


def _call_name(node: ast.Call) -> str:
    func = node.func
    return func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")


class TestPanelPromptsUseTemplate:
    """规则 1：panel_loop 的 prompt 必须来自模板函数。"""

    def test_panel_loop_prompt_is_template_call(self):
        violations = []
        for path in _tui_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and _call_name(node) == "panel_loop"):
                    continue
                prompt_kw = next((kw for kw in node.keywords if kw.arg == "prompt"), None)
                assert prompt_kw is not None, f"{path.name}:{node.lineno} panel_loop 未传 prompt"
                if not (isinstance(prompt_kw.value, ast.Call) and _call_name(prompt_kw.value) == "panel_prompt"):
                    violations.append(f"{path.name}:{node.lineno}")
        assert violations == [], (
            "panel_loop 的 prompt 必须由 prompt_text.panel_prompt 产出（禁止手写字面量）：\n"
            + "\n".join(violations)
        )


class TestNoHiddenEnterCancel:
    """规则 2：回车取消不得藏在括注里。"""

    def test_no_parenthesized_enter_cancel(self):
        violations = []
        for path in _tui_sources():
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "直接回车取消" in line or "（回车取消" in line:
                    violations.append(f"{path.name}:{lineno} {line.strip()[:60]}")
        assert violations == [], "回车承担取消语义时须置句首显式声明（如 `回车=取消 / ...`）：\n" + "\n".join(violations)


class TestInputChoiceDeclaresEnter:
    """规则 3：input_choice 字面量提示必须写清回车做什么。"""

    def test_literal_prompts_declare_enter_behaviour(self):
        violations = []
        for path in _tui_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and _call_name(node) == "input_choice"):
                    continue
                if not node.args:
                    continue
                arg = node.args[0]
                if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                    continue  # 模板/折行助手产出，另由规则 1 与结构测试覆盖
                if (path.name, arg.value) in ALLOWLIST_PROMPTS:
                    continue
                if "回车=" not in arg.value:
                    violations.append(f"{path.name}:{node.lineno} {arg.value[:50]}")
        assert violations == [], "input_choice 提示须声明回车行为（`回车=<动作名>`）：\n" + "\n".join(violations)
