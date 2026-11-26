"""TUI 侧残余守卫分支：筛选态跳过渲染 / 非数字配对输入 / isatty 异常降级。

覆盖目标：
  - `[M]` LLM 多链面板：筛选态下命中项之外的线路不渲染（编号仍占位）；
    拾取到非数字键 → 按 `ValueError` 归为非法配对并统一重提示
  - 开关面板：筛选态下命中项之外的开关不渲染（索引仍占位）
  - `LiveStatusBar.supported`：`isatty()` 抛异常 → False（不因探测失败炸掉回退路径）
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.python.tui import handlers_llm_providers, handlers_switch, tui as tui_mod
from src.python.tui.live_status import LiveStatusBar
from src.python.tui.panel_runtime import NavState
from src.test._subprocess_coverage import run_entry_child

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


# ── 状态条支持性探测 ───────────────────────────────────────


class _BoomIsatty:
    """`isatty()` 直接抛异常的流替代（老管道/被替换的 sys.stdout）。"""

    def write(self, _text: str) -> None:
        return None

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        raise OSError("终端能力不可查")


def test_live_status_unsupported_when_isatty_raises(monkeypatch):
    """`isatty()` 抛异常 → 判为不支持（原地刷新降级，不中断面板）。"""
    monkeypatch.delenv("TUI_PLAIN", raising=False)
    monkeypatch.setattr(os, "name", "posix")

    assert LiveStatusBar.supported(_BoomIsatty()) is False


# ── 筛选态渲染跳过 ─────────────────────────────────────────


def test_llm_providers_panel_skips_filtered_rows_and_rejects_non_numeric_pair(monkeypatch, capsys):
    """筛选态下隐藏线路不渲染；拾取非数字键 → 「请输入两个不同的编号」重提示。"""
    monkeypatch.setattr(
        "src.python.config.get_llm_providers",
        lambda: {
            "strategy": "priority",
            "providers": [
                {"name": "甲线路", "provider": "openai", "priority": 1},
                {"name": "乙线路", "provider": "openai", "priority": 2},
            ],
        },
    )
    rendered: list[str] = []

    def _fake_panel_loop(items, render, **_kwargs):
        nav = NavState(count=len(items))
        nav.apply_filter(list(range(1, len(items))), "乙")
        rendered.extend(render(nav))
        # 拾取到非数字键（如导航态误回车收集到的返回项编号与字母）→ ValueError 分支
        _kwargs["on_picked"](("0", "x"))

    monkeypatch.setattr(handlers_llm_providers, "panel_loop", _fake_panel_loop)

    handlers_llm_providers.run_llm_providers_panel()

    out = capsys.readouterr().out
    assert "乙线路" in out, "命中项须照常渲染"
    assert "甲线路（openai）" not in out, "被筛掉的线路不得渲染"
    assert "请输入两个不同的编号" in out, "非数字配对须回统一重提示"


def test_switch_panel_skips_filtered_rows(monkeypatch, capsys):
    """筛选态下隐藏开关不渲染：输出行是未筛选时的真子集（命中项照常渲染）。"""

    def _render_with(visible: list[int] | None) -> list[str]:
        def _fake_panel_loop(items, render, **_kwargs):
            nav = NavState(count=len(items))
            if visible is not None:
                nav.apply_filter(visible, "关键词")
            render(nav)

        monkeypatch.setattr(handlers_switch, "panel_loop", _fake_panel_loop)
        handlers_switch.run_content_options_panel()
        return [line for line in capsys.readouterr().out.splitlines() if line.strip()]

    monkeypatch.setattr("src.python.tui.handlers_config.reset_config_session", lambda: _StubSession())

    unfiltered = _render_with(None)
    filtered = _render_with([0])

    assert set(filtered) < set(unfiltered), "筛选态须只少渲染被隐藏的开关行（不得多出或改写其他行）"
    assert len(filtered) < len(unfiltered), "命中项不足全部时渲染行数须实际变少"


class _StubSession:
    """面板会话替身：本用例只在渲染期断言，不触发写盘/退回。"""

    count = 0

    def record_payload(self, _payload: dict) -> None:
        return None


# ── 包入口 `python -m src.python.tui` ──────────────────────


_PACKAGE_ENTRY_CHILD_CODE = """
import runpy

import src.python.tui.tui as tui

tui.main = lambda: print("PACKAGE_ENTRY_OK")
runpy.run_module("src.python.tui", run_name="__main__")
"""


def test_package_entry_calls_tui_main():
    """`python -m src.python.tui` 的包入口守卫 → 调用 `tui.main`（子进程执行）。"""
    completed = run_entry_child(_PACKAGE_ENTRY_CHILD_CODE, cwd=Path(tui_mod.__file__).resolve().parents[3])

    assert completed.returncode == 0, completed.stderr
    assert "PACKAGE_ENTRY_OK" in completed.stdout, "包入口须以 `tui.main` 为入口"
