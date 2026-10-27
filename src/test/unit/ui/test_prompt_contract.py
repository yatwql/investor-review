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
5. 键名口径统一：屏幕上只写「回车」，不写英文 `Enter`（同一按键两种叫法让用户
   以为是两个键，见契约 Keys 节）——扫 TUI 全量字面量与启动向导；
6. 回车必须带动作名：凡出现「回车」的字面量，须写成 `回车=<动作名>` 或
   `回车跳过` / `回车/q` / `回车也返回` / `空回车=` 等声明形式；回车承担
   取消/中止/跳过语义时，该分句必须位于句首（不得藏在末尾括注）。

新增违反须改实现，不得加白名单；白名单只减不增。
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
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


class TestStatusRenderingContract:
    """开关状态只有 ``switch_panel.status_text`` 一个实现；其他面板复用它。"""

    def test_status_text_has_single_implementation(self):
        definitions: list[str] = []
        for path in _tui_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in {"status_text", "_status_text"}:
                    definitions.append(path.name)
        assert definitions == ["switch_panel.py"], f"状态渲染重复实现: {definitions}"

    def test_report_chapters_reuses_shared_status(self):
        source = (TUI_DIR / "handlers_report_chapters.py").read_text(encoding="utf-8")
        assert "from src.python.tui.switch_panel import" in source
        assert "status_text" in source
        assert "_status_text" not in source


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
    ("report_artifacts.py", "_wait_any_key"),  # 远程/无图形会话报告产物清单（无 y/N 询问）
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


class TestEnterWordingUnified:
    """规则 5：屏幕上只写「回车」，不写英文 `Enter`（同键异名会让用户以为是两个键）。"""

    def test_no_english_enter_on_screen(self):
        violations = []
        for path in _tui_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            docstrings = {
                id(node.body[0].value)
                for node in ast.walk(tree)
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
            }
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                    continue
                if id(node) in docstrings:
                    continue
                if "Enter" in node.value:
                    violations.append(f"{path.name}:{node.lineno} {node.value.strip()[:60]}")
        assert violations == [], "屏幕上应写「回车」而非 `Enter`（键名口径统一）：\n" + "\n".join(violations)


class TestEnterDeclaresAction:
    """规则 6：回车必须带动作名；取消类语义不得藏在末尾分句。"""

    # 合法声明形态：回车 += 动作名 / 回车 + 紧凑动作词 / 回车 + 按键组合
    _ENTER_DECLARED = re.compile(r"回车\s*[=＝]|回车[/或]|回车\s*[\u4e00-\u9fff]{1,4}")
    _CANCEL_WORDS = ("取消", "中止", "跳过")

    def _user_literals(self) -> Iterator[tuple[Path, ast.Constant, str]]:
        for path in _tui_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            docstrings = {
                id(node.body[0].value)
                for node in ast.walk(tree)
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
            }
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if id(node) in docstrings or "回车" not in node.value:
                        continue
                    yield path, node, node.value

    def test_enter_declares_action_name(self):
        violations = []
        for path, node, text in self._user_literals():
            if self._ENTER_DECLARED.search(text):
                continue
            violations.append(f"{path.name}:{node.lineno} {text.strip()[:70]}")
        assert violations == [], (
            "「回车」必须带动作名（写成 `回车=<动作名>` 等声明形式），否则用户读不出按键后果：\n"
            + "\n".join(violations)
        )

    def test_enter_cancel_clause_leads(self):
        """回车承担取消/中止/跳过时，该分句须是提示首句（不得放在末尾括注）。"""
        violations = []
        for path, node, text in self._user_literals():
            if not any(w in text for w in self._CANCEL_WORDS):
                continue
            clauses = [c.strip() for c in text.split("/")]
            enter_clause = next((i for i, c in enumerate(clauses) if "回车" in c), None)
            if enter_clause is None:
                continue  # 回车不承担动作
            if not any(w in clauses[enter_clause] for w in self._CANCEL_WORDS):
                continue  # 取消由其它键承担（如 q=取消），回车另有正动作
            if enter_clause != 0:
                violations.append(f"{path.name}:{node.lineno} {text.strip()[:70]}")
        assert violations == [], (
            "回车承担取消/中止/跳过语义时必须置于句首显式声明（如 `回车=取消 / 输入编号`）：\n" + "\n".join(violations)
        )


class TestPanelNumberingContiguous:
    """面板内编号必须 1..N 连续（0=返回除外）——编号是面板第一入口，跳号即按到空号。

    由 ``enumerate`` 生成的编号天然连续，本守卫只盯**手写数字字面量**的分组
    （如某面板显式写 ``PanelItem("6", ...)``）：同一函数内手写数字键 ≥2 个时，
    必须补齐 1..N。单个数字键不与字母键构成编号序列（如 ``[I]`` 的 ``A/D/R + 0``），
    不参与连续性判定。
    """

    def _literal_numeric_keys_by_scope(self):
        """{文件:函数名: [手写数字键…]} —— 只收 ``PanelItem("3", …)`` 这类字面量键。"""
        scopes: dict[tuple[str, str], list[int]] = {}
        for path in _tui_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for func in ast.walk(tree):
                if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for node in ast.walk(func):
                    if not (isinstance(node, ast.Call) and _call_name(node) == "PanelItem"):
                        continue
                    if not node.args:
                        continue
                    key = node.args[0]
                    if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                        continue
                    if not key.value.isdigit():
                        continue
                    scopes.setdefault((path.name, func.name), []).append(int(key.value))
        return scopes

    def test_literal_panel_numbers_form_contiguous_range(self):
        violations = []
        for (filename, func), keys in self._literal_numeric_keys_by_scope().items():
            numbers = sorted(n for n in keys if n != 0)  # 0 是返回项，不参与编号连续性
            if len(numbers) < 2:
                continue  # 字母型面板里的单个数字项不构成编号序列
            expected = list(range(1, len(numbers) + 1))
            if numbers != expected:
                violations.append(f"{filename}:{func} 编号 {numbers} ≠ {expected}")
        assert violations == [], "面板手写编号须 1..N 连续（0 为返回项）：\n" + "\n".join(violations)


class TestFirstRunHintsPointToRealMenus:
    """首次使用指引里的菜单键必须真实存在且指向正确入口。

    回归背景：持仓目录实际在 `[G] 全局设置 → [H]/[F]`，LLM 设置在 `[G] → [L]`；
    指引曾指向 `[D]` / `[S]`（分别是诊断与章节内容面板），用户按提示走不到目标项。
    """

    @staticmethod
    def _hints(monkeypatch, tmp_path) -> str:
        """在「持仓文件不存在 + LLM 未配置」条件下捕获指引文本。"""
        import io

        from src.python.tui import tui_menu

        monkeypatch.setattr(
            tui_menu, "_config_cache", {"holdings_dir": str(tmp_path), "holdings_filename": "missing.xlsx"}
        )
        import src.python.core.system_info as system_info

        monkeypatch.setattr(system_info, "llm_status", lambda: {"configured": False})
        out = io.StringIO()
        monkeypatch.setattr("sys.stdout", out)
        tui_menu.print_header()
        return out.getvalue()

    def test_holdings_hint_points_to_global_settings(self, monkeypatch, tmp_path):
        text = self._hints(monkeypatch, tmp_path)
        holdings_line = next(line for line in text.splitlines() if "持仓" in line and "配置" in line)
        assert "[G]" in holdings_line, f"持仓目录入口应在 [G]，实际：{holdings_line}"
        assert "[H]" in holdings_line and "[F]" in holdings_line
        assert "[D]" not in holdings_line, f"持仓目录不在 [D]，实际：{holdings_line}"

    def test_llm_hint_does_not_point_to_chapter_panel(self, monkeypatch, tmp_path):
        text = self._hints(monkeypatch, tmp_path)
        llm_line = next(line for line in text.splitlines() if "llm_key.json" in line)
        assert "[G]" in llm_line and "[L]" in llm_line
        assert "[S]" not in llm_line, f"LLM 设置不在 [S]（章节内容面板），实际：{llm_line}"
