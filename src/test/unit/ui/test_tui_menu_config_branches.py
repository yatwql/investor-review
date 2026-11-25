"""TUI 菜单配置面板（`tui/tui_menu`）：`show_config` 全量字段与 LLM 状态渲染分支。

锁住的契约：`[G]/[R]` 后的配置回显必须把「持仓目录 / 持仓文件 / 输出目录 / 抓取上限 /
文件状态」与匿名化、隐私、LLM 三行一次上屏；文件缺失时给 `[!!] 文件未找到` 而不是静默
省略——用户据此判断下一步该去改哪一项。
"""

from __future__ import annotations

import io

import pytest

from src.python.tui import tui_menu as tm
from src.python.tui.tui_keys import KEY_CTRL_C

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


def _llm_single(*, circuit: str = "—") -> dict:
    """单 provider 已配置的 `llm_status` 单源结果形状。"""
    return {
        "configured": True,
        "mode": "single",
        "provider": "deepseek",
        "model": "deepseek-chat",
        "endpoint_display": "api.deepseek.com",
        "route": ["analysis → deepseek-chat"],
        "circuit": circuit,
    }


def _llm_multi(preferred: list[str]) -> dict:
    return {
        "configured": True,
        "mode": "multi",
        "strategy": "priority",
        "providers": [{"name": "alpha", "backend": "claude", "model": "opus", "priority": 10, "circuit": "正常"}],
        "preferred": preferred,
        "circuit": "—",
        "route": [],
    }


def _isolate_config(monkeypatch, *, holdings_exists: bool, privacy_shown: bool, tmp_path) -> None:
    """把 show_config 的三条外部读点固定住（配置缓存 / 持仓路径 / 隐私本地标志）。"""
    holdings = tmp_path / "holdings.xlsx"
    if holdings_exists:
        holdings.write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        tm,
        "_config_cache",
        {"holdings_dir": str(tmp_path), "holdings_filename": "holdings.xlsx", "news_top_count": 300},
    )
    monkeypatch.setattr("src.python.config.resolve_holdings_path", lambda _cfg: str(holdings))
    monkeypatch.setattr(tm, "resolve_output_dir", lambda _cfg: str(tmp_path / "reports"))
    monkeypatch.setattr("src.python.config.anonymizer.get_anonymization_mode", lambda: "partial")
    monkeypatch.setattr("src.python.core.system_info.anon_mode_label", lambda mode: f"部分匿名（{mode}）")
    monkeypatch.setattr("src.python.config.get_local_flag", lambda _name: privacy_shown)


def _show(monkeypatch, capsys) -> str:
    tm.show_config()
    return capsys.readouterr().out


class TestShowConfigFields:
    def test_all_fields_and_ready_file(self, monkeypatch, capsys, tmp_path):
        """持仓文件就绪 → 逐项回显配置，文件状态为 `[OK] 文件就绪`。"""
        _isolate_config(monkeypatch, holdings_exists=True, privacy_shown=True, tmp_path=tmp_path)
        monkeypatch.setattr("src.python.core.system_info.llm_status", _llm_single)

        out = _show(monkeypatch, capsys)

        assert f"持仓目录: {tmp_path}" in out
        assert "持仓文件: holdings.xlsx" in out
        assert f"输出目录: {tmp_path / 'reports'}" in out
        assert "新闻抓取上限: 300 条" in out
        assert "[OK]" in out and "文件就绪" in out

    def test_missing_file_reports_not_found(self, monkeypatch, capsys, tmp_path):
        """持仓文件缺失 → `[!!] 文件未找到`（提示用户先配持仓目录，而非静默）。"""
        _isolate_config(monkeypatch, holdings_exists=False, privacy_shown=True, tmp_path=tmp_path)
        monkeypatch.setattr("src.python.core.system_info.llm_status", _llm_single)

        out = _show(monkeypatch, capsys)

        assert "[!!]" in out and "文件未找到" in out

    def test_config_cache_absent_reads_config(self, monkeypatch, capsys, tmp_path):
        """缓存未载入时 show_config 自行读取配置（首屏 [R] 刷新后的第一条路径）。"""
        _isolate_config(monkeypatch, holdings_exists=True, privacy_shown=True, tmp_path=tmp_path)
        monkeypatch.setattr(tm, "_config_cache", None)
        monkeypatch.setattr(tm, "get_config", lambda: {"holdings_dir": "/cache/empty", "holdings_filename": "z.xlsx"})
        monkeypatch.setattr(tm, "refresh_config", lambda: {"holdings_dir": "/from/read", "holdings_filename": "r.xlsx"})
        monkeypatch.setattr("src.python.core.system_info.llm_status", _llm_single)

        out = _show(monkeypatch, capsys)

        assert "持仓目录: /from/read" in out
        assert "持仓文件: r.xlsx" in out


class TestPrivacyStatusLine:
    def test_privacy_notice_pending_wording(self, monkeypatch, capsys, tmp_path):
        """隐私声明尚未展示 → 一行「待首次报告生成时显示」，不谎报已完成。"""
        _isolate_config(monkeypatch, holdings_exists=True, privacy_shown=False, tmp_path=tmp_path)
        monkeypatch.setattr("src.python.core.system_info.llm_status", _llm_single)

        out = _show(monkeypatch, capsys)

        assert "持仓匿名化: 部分匿名（partial）" in out
        assert "隐私声明: 待首次报告生成时显示" in out

    def test_privacy_notice_shown_marks_done(self, monkeypatch, capsys, tmp_path):
        _isolate_config(monkeypatch, holdings_exists=True, privacy_shown=True, tmp_path=tmp_path)
        monkeypatch.setattr("src.python.core.system_info.llm_status", _llm_single)

        out = _show(monkeypatch, capsys)

        assert "隐私声明: 待首次报告生成时显示" not in out
        assert "隐私声明: " in out


class TestLlmStatusSingleAndMulti:
    def test_single_provider_includes_retry_and_route(self, monkeypatch, capsys, tmp_path):
        """单 provider 已配置：带自动重试状态与模型路由（三渠道同源文案）。"""
        _isolate_config(monkeypatch, holdings_exists=True, privacy_shown=True, tmp_path=tmp_path)
        monkeypatch.setattr("src.python.core.system_info.llm_status", lambda: _llm_single(circuit="已熔断"))

        out = _show(monkeypatch, capsys)

        assert "provider=deepseek" in out and "model=deepseek-chat" in out
        assert "自动重试: 已熔断" in out
        assert "模型路由: analysis → deepseek-chat" in out

    def test_single_provider_omits_retry_when_unavailable(self, monkeypatch, capsys, tmp_path):
        """熔断状态为「—」（未启用）时不打印重试段（不留 `自动重试: —` 噪声）。"""
        _isolate_config(monkeypatch, holdings_exists=True, privacy_shown=True, tmp_path=tmp_path)
        monkeypatch.setattr("src.python.core.system_info.llm_status", _llm_single)

        out = _show(monkeypatch, capsys)

        assert "自动重试" not in out
        assert "模型路由: analysis → deepseek-chat" in out

    def test_multi_chain_module_preference_line(self, monkeypatch, capsys, tmp_path):
        """多链且配了模块偏好 → 末行回显偏好链（用户据此判断模块走哪个后端）。"""
        _isolate_config(monkeypatch, holdings_exists=True, privacy_shown=True, tmp_path=tmp_path)
        monkeypatch.setattr("src.python.core.system_info.llm_status", lambda: _llm_multi(["analysis → alpha"]))

        out = _show(monkeypatch, capsys)

        assert "多链服务 (1 provider)" in out
        assert "模块偏好: analysis → alpha" in out


class TestPressAnyKeyCtrlC:
    def test_ctrl_c_exits_app(self, monkeypatch, capsys):
        """「按任意键返回」时按 Ctrl+C = 退出程序（不是返回菜单）。"""
        fired: list[str] = []
        monkeypatch.setattr("src.python.tui.tui_keys.get_key", lambda: KEY_CTRL_C)
        monkeypatch.setattr(tm, "exit_app", lambda: fired.append("exit"))

        tm.press_any_key()

        assert fired == ["exit"]
        assert "按任意键返回菜单" in capsys.readouterr().out

    def test_other_key_does_not_exit(self, monkeypatch):
        fired: list[str] = []
        monkeypatch.setattr("src.python.tui.tui_keys.get_key", lambda: "A")
        monkeypatch.setattr(tm, "exit_app", lambda: fired.append("exit"))

        tm.press_any_key(echo=lambda _text: None)

        assert fired == []


def test_press_any_key_injected_reader_used():
    """注入读者优先于终端读键（调用方自管输入通道时不被 get_key 抢走）。"""
    echoed: list[str] = []
    tm.press_any_key(key_reader=lambda: "Z", echo=echoed.append)
    assert echoed == ["  按任意键返回菜单..."]


def test_show_config_writes_blank_line_separator(monkeypatch, tmp_path):
    """面板末行留一空行（与菜单渲染之间的视觉分界，紧邻下一帧不粘连）。"""
    _isolate_config(monkeypatch, holdings_exists=True, privacy_shown=True, tmp_path=tmp_path)
    monkeypatch.setattr("src.python.core.system_info.llm_status", _llm_single)
    buf = io.StringIO()
    with monkeypatch.context() as patch_ctx:
        patch_ctx.setattr("sys.stdout", buf)
        tm.show_config()
    assert buf.getvalue().endswith("\n\n")
