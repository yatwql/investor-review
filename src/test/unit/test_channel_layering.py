"""三渠道薄壳层纪律扫描：渠道不持业务规则、不直写配置、不散落默认值字面量。

对应三渠道架构巡检（配置编辑共享、路径解析单源、状态组装单源、缓存编排下沉）。
扫描 src/python/ 下 web / tui / cli 三渠道源码（AST 导入面 + 文本字面量），发现即红——
防止「薄壳重新长出业务」的回退。渠道包内部互相引用（dispatcher / 包 re-export）
不计入。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

_SRC_ROOT = Path(__file__).resolve().parents[2] / "python"

# 禁止渠道直引的私有配置模块（公开替代：config.get_local_flag / config.get_default）
_BANNED_PRIVATE_MODULES = frozenset(
    {
        "src.python.config._local_state",
        "src.python.config._config_defaults",
    }
)

# 禁止渠道直接导入的配置写原语（业务写入必须经 config.edit_ops.apply_config_edit）
_BANNED_WRITERS = frozenset(
    {
        "set_config",
        "set_anonymization_mode",
        "save_feature_overrides",
        "write_llm_settings",
    }
)

# 禁止散落的默认值字面量（真值来源：config.get_default / resolve_holdings_path）。
# 模式带引号：只命中配置回退形态，不误伤文档中对目录的描述性提及
_BANNED_LITERALS = (
    '"data/holdings"',
    "'data/holdings'",
    '"个人投资持仓信息"',
    "'个人投资持仓信息'",
    'get("output_dir", "reports")',
    "get('output_dir', 'reports')",
)


def _channels() -> list[tuple[str, list[Path]]]:
    return [(chan, sorted((_SRC_ROOT / chan).rglob("*.py"))) for chan in ("web", "tui", "cli")]


def _from_imports(tree: ast.AST):
    """产出 (lineno, module, imported_name)；纯 import 产出 module=None。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                yield node.lineno, node.module, alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name, None


class TestImportHygiene:
    def test_no_cross_channel_private_symbol_imports(self):
        violations: list[str] = []
        for chan, files in _channels():
            for path in files:
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for lineno, module, name in _from_imports(tree):
                    if name is None or not name.startswith("_"):
                        continue
                    if module.startswith(f"src.python.{chan}."):
                        continue  # 渠道包内部互相引用
                    violations.append(f"{path.relative_to(_SRC_ROOT)}:{lineno} from {module} import {name}")
        assert violations == []

    def test_no_banned_private_config_modules(self):
        violations: list[str] = []
        for _, files in _channels():
            for path in files:
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for lineno, module, _name in _from_imports(tree):
                    if module in _BANNED_PRIVATE_MODULES:
                        violations.append(f"{path.relative_to(_SRC_ROOT)}:{lineno} import {module}")
        assert violations == []

    def test_no_direct_config_writers(self):
        violations: list[str] = []
        for _, files in _channels():
            for path in files:
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for lineno, _module, name in _from_imports(tree):
                    if name in _BANNED_WRITERS:
                        violations.append(f"{path.relative_to(_SRC_ROOT)}:{lineno} import {name}")
        assert violations == []


class TestLiteralHygiene:
    def test_no_scattered_default_literals(self):
        violations: list[str] = []
        for _, files in _channels():
            for path in files:
                for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    for snippet in _BANNED_LITERALS:
                        if snippet in line:
                            violations.append(f"{path.relative_to(_SRC_ROOT)}:{lineno} 含字面量 {snippet!r}")
        assert violations == []


class TestSharedLayerRouting:
    """结构断言：配置写入的两端（Web/TUI）都接在共享编辑层上。"""

    @pytest.mark.parametrize("rel", ["web/handlers.py", "tui/handlers_config.py"])
    def test_write_entrypoints_reference_shared_edit_layer(self, rel):
        text = (_SRC_ROOT / rel).read_text(encoding="utf-8")
        assert "apply_config_edit" in text

    @pytest.mark.parametrize("rel", ["web/config_edit.py"])
    def test_web_edit_module_is_thin_facade(self, rel):
        """Web 配置编辑模块只做呈现面组装——规则实现引用共享层符号。"""
        text = (_SRC_ROOT / rel).read_text(encoding="utf-8")
        assert "apply_config_edit" in text
        assert "config_edit_whitelist" in text
        # 不在 Web 层重建规则字典
        assert "配置键不在白名单" not in text


class TestSharedCopyIsSingleSource:
    """渠道共用文案与枚举值只允许一份来源。"""

    @pytest.mark.unit_core
    def test_whatif_holdings_unreadable_messages_not_duplicated_in_channels(self):
        """调仓输入持仓读取失败提示：三渠道引用 whatif_operations 常量，不自写句子。"""
        from src.python.report import whatif_operations as wops

        assert wops.WHATIF_BASE_HOLDINGS_UNREADABLE == "基准持仓读取失败或为空"
        assert wops.WHATIF_TARGET_HOLDINGS_UNREADABLE == "目标持仓读取失败或为空"
        root = Path(__file__).resolve().parents[3]
        for rel in ("src/python/cli/_handlers.py", "src/python/tui/handlers_whatif.py", "src/python/web/handlers.py"):
            text = (root / rel).read_text(encoding="utf-8")
            assert "WHATIF_BASE_HOLDINGS_UNREADABLE" in text, rel
            assert "WHATIF_TARGET_HOLDINGS_UNREADABLE" in text, rel
            for literal in ("基准持仓读取失败或为空", "目标持仓读取失败或为空"):
                assert f'"{literal}' not in text, f"{rel} 仍有重复字面量：{literal}"

    @pytest.mark.unit_core
    def test_log_and_health_failure_messages_not_duplicated_in_channels(self):
        """日志/健康历史读取失败提示：三渠道引用核心层常量，措辞不得各自演化。"""
        from src.python.core import log_reader, perf

        assert log_reader.LOG_READ_FAILED_MESSAGE == "读取运行日志失败"
        assert perf.HEALTH_HISTORY_READ_FAILED_MESSAGE == "读取数据源健康历史失败"
        root = Path(__file__).resolve().parents[3]
        cases = (
            ("src/python/cli/_handlers.py", "LOG_READ_FAILED_MESSAGE"),
            ("src/python/tui/handlers_log.py", "LOG_READ_FAILED_MESSAGE"),
            ("src/python/web/handlers_health.py", "LOG_READ_FAILED_MESSAGE"),
            ("src/python/cli/_handlers.py", "HEALTH_HISTORY_READ_FAILED_MESSAGE"),
            ("src/python/tui/handlers_log.py", "HEALTH_HISTORY_READ_FAILED_MESSAGE"),
            ("src/python/web/handlers_health.py", "HEALTH_HISTORY_READ_FAILED_MESSAGE"),
        )
        for rel, symbol in cases:
            text = (root / rel).read_text(encoding="utf-8")
            assert symbol in text, f"{rel} 应引用 {symbol}"

    @pytest.mark.unit_core
    def test_tui_config_change_footer_has_one_definition(self):
        """「本次改动 N 项」页脚句只在 switch_panel 定义，配置/导航面板共用。"""
        from src.python.tui import switch_panel

        assert switch_panel.change_footer(0) is None
        assert switch_panel.change_footer(2) == "  本次改动 2 项（u 撤销上次 · U 全部还原）"
        root = Path(__file__).resolve().parents[3]
        for rel in ("src/python/tui/handlers_config.py", "src/python/tui/handlers_switch.py"):
            text = (root / rel).read_text(encoding="utf-8")
            assert "change_footer" in text, rel
            assert "本次改动" not in text, f"{rel} 仍有重复字面量"

    @pytest.mark.unit_core
    def test_whatif_unavailable_message_not_duplicated_in_channels(self):
        """调仓不可用提示：三渠道都走 whatif_operations 的单源拼装，不各自写字面量。"""
        from src.python.report.whatif_operations import whatif_unavailable_message

        assert whatif_unavailable_message("持仓不足") == "调仓对比数据不可用: 持仓不足"
        root = Path(__file__).resolve().parents[3]
        for rel in ("src/python/cli/_handlers.py", "src/python/tui/handlers_whatif.py", "src/python/web/handlers.py"):
            text = (root / rel).read_text(encoding="utf-8")
            assert "whatif_unavailable_message" in text, rel
            assert "调仓对比数据不可用: " not in text, f"{rel} 仍有重复字面量"

    @pytest.mark.unit_core
    def test_price_type_label_has_one_definition(self):
        """取价方式标签「官方净值(T-1)」只在 market_value 定义，消费方引用常量。"""
        from src.python.report import html_jinja_env, market_value
        from src.python.report import _holdings_detail_blocks as blocks

        assert market_value.PRICE_TYPE_OFFICIAL_NAV_T1 == "官方净值(T-1)"
        for mod in (html_jinja_env, blocks):
            assert mod.__file__ is not None
            text = Path(mod.__file__).read_text(encoding="utf-8")
            assert "PRICE_TYPE_OFFICIAL_NAV_T1" in text, mod.__name__
            code_lines = [
                line
                for line in text.splitlines()
                if not line.lstrip().startswith(("#", '"""', "*")) and '"官方净值(T-1)"' in line
            ]
            assert not code_lines, f"{mod.__name__} 仍有重复字面量：{code_lines[:2]}"
