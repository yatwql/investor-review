"""TUI 入口模块的非交互分支：会话用量回显、就地重绘可用性、筛选关键词读取、启动硬闸。

覆盖点（均为「不进入主循环」的入口层）：
  - `_print_session_usage_on_exit`：有调用时逐行回显（含 per_module 缓存标记）、异常静默
  - `_can_repaint_inplace`：`isatty()` 抛异常时降级为整屏追加
  - `_FrameLineCounter.flush`：透传底层流
  - `_read_filter_keyword` / `_ask_menu_filter`：Esc/EOF/关键字无匹配/有效关键字四条路径
  - `main()` 启动硬闸：解释器预检失败时打印原因并以退出码 1 中止
"""

from __future__ import annotations

import io

import pytest

from src.python.tui import tui

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


# ── 会话用量回显 ────────────────────────────────────────


def _usage() -> dict:
    return {
        "call_count": 3,
        "input_tokens": 1200,
        "output_tokens": 340,
        "cache_hit_tokens": 800,
        "costs": {"CNY": 0.12},
        "model": "deepseek-chat",
        "per_module": {"expert_review": {"model": "deepseek-reasoner", "cached": True}},
    }


class TestSessionUsagePrint:
    def test_prints_totals_and_per_module_cache_tag(self, monkeypatch, capsys):
        monkeypatch.setattr("src.python.llm.get_session_usage", _usage)
        tui._print_session_usage_on_exit()
        out = capsys.readouterr().out
        assert "LLM 会话统计" in out
        assert "模型: deepseek-chat" in out
        # per_module 行带「(缓存)」标记（该模块命中缓存）
        assert "deepseek-reasoner (缓存)" in out
        assert "调用次数: 3" in out
        assert "输入 tokens: 1,200" in out
        assert "输出 tokens: 340" in out
        assert "缓存命中: 800" in out
        assert "总 tokens: 1,540" in out

    def test_zero_calls_prints_nothing(self, monkeypatch, capsys):
        monkeypatch.setattr("src.python.llm.get_session_usage", lambda: {"call_count": 0})
        tui._print_session_usage_on_exit()
        assert capsys.readouterr().out == ""

    def test_broken_usage_is_swallowed(self, monkeypatch, caplog):
        """用量结构异常（缺键/类型错）→ 只记 warning，绝不因统计回显影响退出。"""

        class _Broken:
            def get(self, key, default=None):
                raise AttributeError(f"no {key}")

        monkeypatch.setattr("src.python.llm.get_session_usage", lambda: _Broken())
        with caplog.at_level("WARNING"):
            tui._print_session_usage_on_exit()
        assert "打印 LLM 会话统计时出错" in caplog.text


# ── 就地重绘可用性 ──────────────────────────────────────


class TestCanRepaintInplace:
    def test_isatty_exception_degrades_to_append(self, monkeypatch):
        class _Stdout:
            def isatty(self):
                raise OSError("stream closed")

        monkeypatch.delenv("TUI_PLAIN", raising=False)
        monkeypatch.setattr(tui.sys, "stdout", _Stdout())
        assert tui._can_repaint_inplace() is False

    def test_plain_env_disables_inplace(self, monkeypatch):
        monkeypatch.setenv("TUI_PLAIN", "1")
        assert tui._can_repaint_inplace() is False


class TestFrameLineCounter:
    def test_flush_passthrough(self):
        sink = io.StringIO()
        counter = tui._FrameLineCounter(sink)
        counter.write("a\nb\n")
        counter.flush()
        assert counter.lines == 2
        assert sink.getvalue() == "a\nb\n"


# ── 筛选关键词读取 ──────────────────────────────────────


class TestMenuFilterKeyword:
    def test_read_filter_keyword_delegates_to_input_choice(self, monkeypatch):
        seen: list[str] = []

        def _fake_input_choice(prompt: str) -> str:
            seen.append(prompt)
            return "  基金  "

        monkeypatch.setattr("src.python.tui.tui_keys.input_choice", _fake_input_choice)
        assert tui._read_filter_keyword("请输入: ") == "  基金  "
        assert seen == ["请输入: "]

    def test_esc_keeps_current(self, monkeypatch):
        """Esc（None）不改筛选，且不打印提示行。"""
        monkeypatch.setattr(tui, "_read_filter_keyword", lambda prompt: None)
        assert tui._ask_menu_filter("缓存") == "缓存"

    @pytest.mark.parametrize("exc", [EOFError, KeyboardInterrupt])
    def test_interrupt_keeps_current(self, monkeypatch, exc):
        def _raise(prompt):
            raise exc

        monkeypatch.setattr(tui, "_read_filter_keyword", _raise)
        assert tui._ask_menu_filter("") == ""

    def test_unmatched_keyword_keeps_current_and_hints(self, monkeypatch, capsys):
        monkeypatch.setattr(tui, "_read_filter_keyword", lambda prompt: "绝无此项")
        assert tui._ask_menu_filter("缓存") == "缓存"
        assert "「绝无此项」无匹配菜单项，保持原菜单" in capsys.readouterr().out

    def test_matched_keyword_is_stripped_and_returned(self, monkeypatch):
        monkeypatch.setattr(tui, "_read_filter_keyword", lambda prompt: "  报告  ")
        assert tui._ask_menu_filter("") == "报告"

    def test_empty_input_clears_filter(self, monkeypatch):
        monkeypatch.setattr(tui, "_read_filter_keyword", lambda prompt: "")
        assert tui._ask_menu_filter("缓存") == ""


# ── 启动硬闸 ───────────────────────────────────────────


class TestMainPreflightGate:
    def test_preflight_error_prints_and_exits_one(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "src.python.core.doctor.interpreter_preflight_error",
            lambda: "[ERR] 缺少重依赖 pandas",
        )
        with pytest.raises(SystemExit) as exc:
            tui.main()
        assert exc.value.code == 1
        assert "[ERR] 缺少重依赖 pandas" in capsys.readouterr().err
