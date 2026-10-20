# -*- coding: utf-8 -*-
"""三渠道用户词一致性契约（TUI / CLI / Web 同一决策不得两个名字）。

背景：端点重试状态与日预算确认是**同一件事**在三个渠道各说一遍的地方；
三处各写各的词时，用户会看到「熔断中 / 降级走缓存 / 暂时失败 / 用已有结果」
四套说法，同一按钮四个名字。

两条纪律：
1. **状态标签与状态词同源**——端点状态由 ``core.system_info.circuit_display`` 唯一归一，
   各渠道只渲染，不得自带映射表；
2. **决策屏同词**——「用已有结果继续」在 TUI / CLI / Web 一致，不得各自命名。

报告/Web 的**数据降级**呈现不在此域（口径归 ``DESIGN.md`` Data States）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.integration_contract]

REPO_ROOT = Path(__file__).resolve().parents[3]

WEB_TEMPLATE = REPO_ROOT / "src" / "static" / "web" / "index.html"
WEB_MAIN_JS = REPO_ROOT / "src" / "static" / "web" / "main.js"
WEB_HANDLERS = REPO_ROOT / "src" / "python" / "web" / "handlers.py"
CLI_HANDLERS = REPO_ROOT / "src" / "python" / "cli" / "_handlers.py"
TUI_MENU = REPO_ROOT / "src" / "python" / "tui" / "tui_menu.py"
CORE_SYSTEM_INFO = REPO_ROOT / "src" / "python" / "core" / "system_info.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestEndpointStatusUserWord:
    """端点状态：上屏一律「自动重试: 正常 / 暂时失败」。"""

    def test_web_template_labels_status_as_auto_retry(self):
        text = _read(WEB_TEMPLATE)
        assert "自动重试" in text, "Web 工作台健康面板未用用户词标签"
        assert "熔断状态" not in text, "Web 模板仍在上屏技术词「熔断状态」"

    def test_cli_status_label_uses_user_word(self):
        text = _read(CLI_HANDLERS)
        assert "自动重试: %s" in text, "CLI 状态表未用用户词标签"
        assert "熔断: %s" not in text, "CLI 状态表仍在上屏技术词「熔断」"

    def test_tui_renders_shared_value_without_local_mapping(self):
        text = _read(TUI_MENU)
        assert "自动重试: {llm['circuit']}" in text, "TUI 应直接渲染共享原语的归一结果"
        assert "_CIRCUIT_USER_TEXT" not in text, "TUI 不得自带端点状态映射表（须走 core 唯一归一）"

    def test_mapping_lives_in_single_display_primitive(self):
        text = _read(CORE_SYSTEM_INFO)
        assert '"熔断中": "暂时失败"' in text, "用户词映射必须落在 core 展示原语（三渠道共用的唯一处）"


class TestBudgetDecisionWording:
    """日预算超限：三渠道统一说「用已有结果继续」。"""

    def test_tui_uses_plain_words(self):
        text = _read(REPO_ROOT / "src" / "python" / "tui" / "handlers_report.py")
        assert "用已有结果" in text
        assert "降级走缓存" not in text, "TUI 预算安全网仍是技术词"

    def test_cli_prompt_uses_same_words(self):
        text = _read(CLI_HANDLERS)
        assert "用已有结果" in text, "CLI 交互确认未与 TUI 同词"
        assert "降级走缓存" not in text

    def test_web_backend_messages_use_same_words(self):
        text = _read(WEB_HANDLERS)
        assert "用已有结果继续" in text, "Web 409/错误提示未与 TUI 同词"
        assert "降级走缓存" not in text

    def test_web_confirm_dialog_uses_same_words(self):
        text = _read(WEB_MAIN_JS)
        assert "用已有结果继续" in text, "Web 确认弹层未与 TUI 同词"
        assert "降级走缓存" not in text


class TestWebChainNoteVocabulary:
    """Web 多链线路说明与 TUI 菜单同词（备用顺序）。"""

    def test_chain_note_says_standby_order(self):
        text = _read(WEB_MAIN_JS)
        assert "按下列顺序作为备用" in text, "Web 线路说明未与 TUI「备用顺序」对齐"
