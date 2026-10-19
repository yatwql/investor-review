# -*- coding: utf-8 -*-
"""提示语契约机检（DESIGN-TUI.md「Prompts / Defaults / Vocabulary」三节的执行载体）。

四条硬规则：

1. 列表面板提示必须由 ``prompt_text.panel_prompt`` 产出——手写字面量即失败；
2. 提示里不得出现「（直接回车取消）」这类**把回车取消藏进括注**的形态
   （回车承担取消语义时必须置句首显式声明，见契约 Defaults 节）；
3. ``input_choice`` 的字符串字面量提示必须声明回车行为（含「回车=」），
   否则用户读不出按键后果——运行时内部短提示在 ALLOWLIST 内豁免；
4. 术语表左列（强刷 / 走缓存 / 降级 / 分档 / 游标 / 配置漂移 / 熔断 / 退避）
   不得出现在上屏文案里（见契约 Vocabulary 节）——CJK 术语扫全量字面量
   （排除 docstring 与日志消息），英文术语仅扫展示型调用，避免命中程序标识符。

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

# 术语表禁上屏词（左列）。CJK 项扫全量字面量；英文项仅扫展示型调用
FORBIDDEN_CJK_TERMS = ("强刷", "走缓存", "降级", "分档", "窄档", "宽档", "游标", "配置漂移", "熔断", "退避")
FORBIDDEN_EN_TERMS = ("force", "cache hit", "tier", "cursor")

# 展示型调用：字面量会直接进用户眼睛
_DISPLAY_CALLS = {
    "print",
    "input_choice",
    "wrap_prompt",
    "wrap_hanging",
    "panel_prompt",
    "print_error_with_hint",
    "ok",
    "warn",
    "info",
    "error",
}

# 内部值豁免：作为查表键/槽名等程序标识符存在，不直接上屏
# （当前为空：端点状态映射在 `core.system_info.circuit_display`，TUI 只渲染归一结果）
ALLOWLIST_INTERNAL_VALUES: set[tuple[str, str]] = set()


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
            "panel_loop 的 prompt 必须由 prompt_text.panel_prompt 产出（禁止手写字面量）：\n" + "\n".join(violations)
        )


class TestNoHiddenEnterCancel:
    """规则 2：回车取消不得藏在括注里。"""

    def test_no_parenthesized_enter_cancel(self):
        violations = []
        for path in _tui_sources():
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "直接回车取消" in line or "（回车取消" in line:
                    violations.append(f"{path.name}:{lineno} {line.strip()[:60]}")
        assert violations == [], "回车承担取消语义时须置句首显式声明（如 `回车=取消 / ...`）：\n" + "\n".join(
            violations
        )


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


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """模块/类/函数首条 Expr 字符串（docstring）节点 id 集合。"""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    ids.add(id(body[0].value))
    return ids


def _logging_nodes(tree: ast.AST) -> set[int]:
    """``logger.*`` 调用内部全部节点（日志消息不上屏，不进术语检查）。"""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "logger":
            ids.update(id(sub) for sub in ast.walk(node))
    return ids


def _display_nodes(tree: ast.AST) -> set[int]:
    """展示型调用（print / input_choice / 提示模板 / reporter）内部全部节点。"""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_name(node) in _DISPLAY_CALLS:
            ids.update(id(sub) for sub in ast.walk(node))
    return ids


class TestForbiddenVocabulary:
    """规则 4：内部工程词不得上屏（DESIGN-TUI Vocabulary 表左列）。"""

    def test_no_internal_cjk_terms_in_literals(self):
        """CJK 术语扫全量字面量（排除 docstring 与日志消息）。"""
        violations = []
        for path in _tui_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            skip = _docstring_nodes(tree) | _logging_nodes(tree)
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                    continue
                if id(node) in skip:
                    continue
                hits = [term for term in FORBIDDEN_CJK_TERMS if term in node.value]
                if not hits:
                    continue
                if (path.name, node.value) in ALLOWLIST_INTERNAL_VALUES:
                    continue
                violations.append(f"{path.name}:{node.lineno} {hits} {node.value[:60]}")
        assert violations == [], "上屏文案含内部工程词（见 DESIGN-TUI Vocabulary，改用用户词）：\n" + "\n".join(
            violations
        )

    def test_no_internal_english_terms_in_display_calls(self):
        """英文术语仅扫展示型调用，避免命中 force_llm / layout_tier 等程序标识符。"""
        violations = []
        for path in _tui_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            display = _display_nodes(tree)
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                    continue
                if id(node) not in display:
                    continue
                low = node.value.lower()
                hits = [term for term in FORBIDDEN_EN_TERMS if term in low]
                if hits:
                    violations.append(f"{path.name}:{node.lineno} {hits} {node.value[:60]}")
        assert violations == [], "展示型调用里出现英文工程词（见 DESIGN-TUI Vocabulary）：\n" + "\n".join(violations)

    def test_internal_value_allowlist_is_live(self):
        """白名单条目必须仍被需要——失效即删（防止豁免清单只增不减）。"""
        stale = []
        for filename, value in ALLOWLIST_INTERNAL_VALUES:
            source = (TUI_DIR / filename).read_text(encoding="utf-8")
            if f'"{value}"' not in source and f"'{value}'" not in source:
                stale.append(f"{filename}: {value}")
        assert stale == [], "术语豁免条目已失效，请从 ALLOWLIST_INTERNAL_VALUES 删除：\n" + "\n".join(stale)


# 保留闸门的唯一合法位置 =「长输出后」（契约 Feedback 节「按键闸门白名单」）
GATE_WHITELIST = {
    ("handlers_cache.py", "_run_cache_update"),  # 缓存更新结果摘要（多行统计块）
    ("handlers_log.py", "_cmd_view_logs"),  # 运行日志详情
    ("handlers_log.py", "_cmd_view_health_history"),  # 数据源健康历史
    ("handlers_log.py", "_cmd_run_doctor"),  # 系统自检结果
    ("tui_handlers.py", "finish_report"),  # 报告生成收尾摘要
}


def _gate_call_sites() -> set[tuple[str, str]]:
    """扫描 ``press_any_key()`` 调用点，返回 (文件名, 所在函数名) 集合。"""
    sites: set[tuple[str, str]] = set()
    for path in _tui_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for func in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            for node in ast.walk(func):
                if isinstance(node, ast.Call) and _call_name(node) == "press_any_key":
                    sites.add((path.name, func.name))
    return sites


class TestPressAnyKeyGateWhitelist:
    """长输出闸门白名单：短反馈/动作完成一律直接回菜单。"""

    def test_only_long_output_gates_remain(self):
        sites = _gate_call_sites()
        extra = sites - GATE_WHITELIST
        missing = GATE_WHITELIST - sites
        assert not extra, (
            "新增了「按任意键」闸门——短反馈/动作完成不得加闸门，"
            "确属长输出请先更新 DESIGN-TUI Feedback 节与白名单：\n" + "\n".join(sorted(map(str, extra)))
        )
        assert not missing, "白名单条目已无对应闸门（白名单只减不增，请删除失效项）：\n" + "\n".join(
            sorted(map(str, missing))
        )
