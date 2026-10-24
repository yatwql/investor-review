"""``[C]`` 报告章节显隐面板：四块渲染、编号派生、四来源写入与子项闸门。

面板的章节清单/编号/来源全部来自 ``config.chapter_registry``，本文件按注册表
**派生**编号驱动输入（不写死 1-16），并逐块断言写入落到正确文件的正确键：
``config.json``（顶层）/ ``llm_settings.json``（LLM）/ ``features.json``（整章与
关联产物）。子项闸门（智囊团关闭时不可切换）与只读 ``?`` 详情同批覆盖。
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestInvalidNumberHint:
    """无效编号提示的范围必须从注册表派生（章节增删后不得把用户引到旧编号）。"""

    def test_hint_spans_registry_extremes(self):
        from src.python.config.chapter_registry import chapter_numbers, sub_item_numbers
        from src.python.tui.handlers_report_chapters import invalid_number_hint

        numbers = [str(number) for number, _entry in chapter_numbers()]
        hint = invalid_number_hint()
        assert f"{numbers[0]}-{numbers[-1]}" in hint
        subs = sorted(sub_item_numbers())
        assert subs, "注册表应至少有一个生成子项（提示需列出子项编号）"
        assert all(sub in hint for sub in subs)

    def test_hint_does_not_hardcode_replaced_range(self, monkeypatch):
        """章节注册表缩短时提示跟着缩短（写死 1-16 的实现会立刻失配）。"""
        from src.python.config import chapter_registry as registry
        from src.python.tui.handlers_report_chapters import invalid_number_hint

        monkeypatch.setattr(registry, "chapter_numbers", lambda: [(1, registry.chapter_registry[0])])
        assert "可输入 1-1" in invalid_number_hint()


def _chapter_number(key: str) -> int:
    from src.python.config.chapter_registry import chapter_number

    return chapter_number(key)


def _sub_number(flag: str) -> str:
    from src.python.config.chapter_registry import sub_item_numbers

    return next(number for number, name in sub_item_numbers().items() if name == flag)


def _run(monkeypatch, keys: list[str], columns: int = 120) -> str:
    """驱动 ``[C]`` 面板（输入 keys 后退出），返回全部上屏文本。"""
    from src.python.tui.handlers_config import _cmd_config_report_boards

    monkeypatch.setenv("COLUMNS", str(columns))
    buf = io.StringIO()
    with (
        patch("os.get_terminal_size", side_effect=OSError()),
        patch("builtins.input", side_effect=keys),
        patch("src.python.tui.handlers_config.refresh_config"),
        contextlib.redirect_stdout(buf),
    ):
        _cmd_config_report_boards()
    return buf.getvalue()


@pytest.fixture
def llm_settings(tmp_path, monkeypatch):
    """``llm_settings.json`` 写入器（断言路径已隔离到临时目录，绝不碰真实配置）。"""
    from src.python.config._llm_settings import get_llm_settings_path, write_llm_settings

    path = Path(get_llm_settings_path())
    assert str(tmp_path) in str(path), f"测试必须使用隔离路径：{path}"

    def _seed(enabled: dict[str, bool]) -> Path:
        write_llm_settings({"enabled_llm": enabled}, str(path))
        return path

    return _seed


def _features_file() -> dict:
    from src.python.core.json_comments import strip_json_comments
    from src.python.config.features import FEATURES_FILE

    path = Path(FEATURES_FILE)
    if not path.exists():
        return {}
    raw = strip_json_comments(path.read_text(encoding="utf-8"))
    return json.loads(raw) if raw.strip() else {}


def _llm_enabled() -> dict:
    from src.python.config._llm_settings import read_llm_settings_file

    snapshot = read_llm_settings_file()
    assert snapshot is not None
    return snapshot[0].get("enabled_llm") or {}


class TestChapterPanelRendering:
    def test_renders_four_blocks_with_derived_numbers(self, monkeypatch, llm_settings):
        """四块标题按固定顺序上屏，章节编号由注册表派生（1..N 连续）。"""
        from src.python.config.chapter_registry import BLOCK_LABELS, BLOCK_ORDER, chapter_numbers

        llm_settings({})
        out = _run(monkeypatch, ["0"])
        positions = [out.index(f"── {BLOCK_LABELS[block]}（") for block in BLOCK_ORDER]
        assert positions == sorted(positions), "块序应为 BLOCK_ORDER"
        for number, entry in chapter_numbers():
            assert f"{number}. " in out
            assert entry.key in out

    def test_every_chapter_and_sub_item_shows_its_key(self, monkeypatch, llm_settings):
        """每个开关都有键名展示（宽档行内键名列；子项同列）。"""
        from src.python.config.chapter_registry import chapter_registry

        llm_settings({})
        out = _run(monkeypatch, ["0"])
        for entry in chapter_registry:
            assert entry.key in out
            for flag in entry.sub_items:
                assert flag in out

    def test_sub_items_render_under_parent_with_derived_numbers(self, monkeypatch, llm_settings):
        from src.python.config.chapter_registry import sub_item_numbers

        llm_settings({})
        out = _run(monkeypatch, ["0"])
        parent_line = next(
            i
            for i, line in enumerate(out.splitlines())
            if f"{_chapter_number('expert_review')}. 智囊团深度复盘" in line
        )
        lines = out.splitlines()
        for number in sub_item_numbers():
            sub_line = next(i for i, line in enumerate(lines) if f"{number}" in line and "辩论" in line)
            assert sub_line > parent_line, "子项应排在父章节之后"

    def test_narrow_shows_key_on_second_line(self, monkeypatch, llm_settings):
        """窄档两行：名称+状态 / 键名（键名不因窄屏丢失）。"""
        llm_settings({})
        out = _run(monkeypatch, ["0"], columns=40)
        lines = out.splitlines()
        assert all(len(line) <= 40 for line in lines)
        assert any("enable_fund_deep_analysis" in line for line in lines)

    def test_cost_suffix_only_on_llm_rows(self, monkeypatch, llm_settings):
        """LLM 章节行尾带近 7 日费用摘要；顶层章节行不带。"""
        llm_settings({})
        with patch(
            "src.python.core.perf.module_cost_summary",
            return_value={"global_macro": {"total": 1.234567, "runs": 3, "avg": 0.411522}},
        ):
            out = _run(monkeypatch, ["0"])
        gm_lines = [line for line in out.splitlines() if "global_macro" in line]
        assert gm_lines and "3次 ¥1.2346 均¥0.4115" in gm_lines[0]
        top_lines = [line for line in out.splitlines() if "enable_news " in line]
        assert top_lines and "次 ¥" not in top_lines[0]

    def test_cost_read_failure_is_silent(self, monkeypatch, llm_settings):
        """费用摘要读取异常：面板照常渲染（不留摘要、不抛错）。"""
        llm_settings({})
        with patch("src.python.core.perf.module_cost_summary", side_effect=RuntimeError("boom")):
            out = _run(monkeypatch, ["0"])
        assert "报告章节显隐" in out
        assert "次 ¥" not in out

    def test_non_default_chapter_is_star_marked(self, monkeypatch, llm_settings):
        """LLM 章节当前值 ≠ 出厂默认时行尾标 *（关闭的默认开章节）。"""
        llm_settings({"global_macro": False})
        out = _run(monkeypatch, ["0"])
        assert any("[关闭]*" in line and "global_macro" in line for line in out.splitlines())


class TestChapterPanelWrites:
    def test_top_chapter_writes_config_json(self, monkeypatch, llm_settings):
        """顶层章节 → ``config.json`` 的 ``enable_*``（断言读回值）。"""
        from src.python.config import get_config

        llm_settings({})
        _run(monkeypatch, [str(_chapter_number("enable_news")), "0"])
        assert get_config()["enable_news"] is False

    def test_llm_chapter_writes_enabled_llm(self, monkeypatch, llm_settings):
        """LLM 章节 → ``llm_settings.json`` 的 ``enabled_llm.<模块>``。"""
        llm_settings({})
        _run(monkeypatch, [str(_chapter_number("global_macro")), "0"])
        assert _llm_enabled()["global_macro"] is False

    def test_standalone_chapter_writes_features_json(self, monkeypatch, llm_settings):
        """默认关闭的整章 → ``features.json`` 覆写（默认关 → 开）。"""
        llm_settings({})
        _run(monkeypatch, [str(_chapter_number("rebalance_schedule_replay")), "0"])
        assert _features_file()["rebalance_schedule_replay"] is True

    def test_artifact_chapter_writes_features_json(self, monkeypatch, llm_settings):
        """关联产物 → ``features.json`` 覆写（仅影响调仓模拟报告页签）。"""
        llm_settings({})
        _run(monkeypatch, [str(_chapter_number("whatif_trade_cost")), "0"])
        assert _features_file()["whatif_trade_cost"] is True


class TestChapterSubItems:
    def test_sub_item_toggles_when_parent_enabled(self, monkeypatch, llm_settings):
        """智囊团开启时子项可切换，落到 ``features.json``。"""
        llm_settings({"expert_review": True})
        _run(monkeypatch, [_sub_number("llm_debate_procon"), "0"])
        assert _features_file()["llm_debate_procon"] is True

    def test_sub_item_gated_when_parent_disabled(self, monkeypatch, llm_settings):
        """智囊团关闭时子项置灰：输入子项编号给出原因且不写盘。"""
        llm_settings({"expert_review": False})
        out = _run(monkeypatch, [_sub_number("llm_debate_procon"), "0"])
        assert f"先启用第 {_chapter_number('expert_review')} 项" in out
        assert "llm_debate_procon" not in _features_file()

    def test_greyed_sub_row_hints_reason(self, monkeypatch, llm_settings):
        """置灰子项行带「启用本章节后可切换」提示（不只靠颜色表达不可用）。"""
        llm_settings({"expert_review": False})
        out = _run(monkeypatch, ["0"])
        sub_lines = [line for line in out.splitlines() if "llm_debate_procon" in line]
        assert sub_lines and "启用本章节后可切换" in sub_lines[0]


class TestChapterStatusColor:
    """关闭项的状态字必须保持红色；置灰只作用于名称/键名，不得吞掉状态色。"""

    def test_status_text_colors_closed_red_in_both_tiers(self, monkeypatch):
        from src.python.tui import switch_panel

        monkeypatch.setattr(switch_panel, "RED", "\033[91m")
        monkeypatch.setattr(switch_panel, "RESET", "\033[0m")
        assert switch_panel.status_text(False, "wide") == "[\033[91m关闭\033[0m]"
        assert switch_panel.status_text(False, "narrow") == "[\033[91m关\033[0m]"

    def test_default_off_sub_item_shows_red_under_enabled_parent(self, monkeypatch, llm_settings):
        """7.1（llm_debate_procon）默认关、父项开启时应显示红色「关闭」。"""
        from src.python.tui import switch_panel

        monkeypatch.setattr(switch_panel, "RED", "\033[91m")
        monkeypatch.setattr(switch_panel, "RESET", "\033[0m")
        llm_settings({"expert_review": True})
        out = _run(monkeypatch, ["0"])
        line = next(line for line in out.splitlines() if "llm_debate_procon" in line)
        assert "\033[91m关闭\033[0m" in line

    def test_greyed_sub_item_still_shows_red_closed(self, monkeypatch, llm_settings):
        """父项关闭时子项不可切换，但状态字仍须是红色「关闭」而非无色。"""
        from src.python.tui import switch_panel

        monkeypatch.setattr(switch_panel, "RED", "\033[91m")
        monkeypatch.setattr(switch_panel, "RESET", "\033[0m")
        llm_settings({"expert_review": False})
        out = _run(monkeypatch, ["0"])
        line = next(line for line in out.splitlines() if "llm_debate_procon" in line)
        assert "\033[91m关闭\033[0m" in line
        assert "启用本章节后可切换" in line


class TestChapterPanelReadonly:
    def test_question_mark_shows_chapter_detail(self, monkeypatch, llm_settings):
        """``?编号`` 上屏来源文件 / 写键 / 默认 / 影响面，且不写任何配置。"""
        llm_settings({})
        out = _run(monkeypatch, [f"?{_chapter_number('expert_review')}", "0"])
        assert "llm_settings.json → enabled_llm.expert_review" in out
        assert "出厂默认" in out and "关闭后整章不出现" in out
        assert _llm_enabled().get("expert_review") is True

    def test_question_mark_shows_sub_item_detail(self, monkeypatch, llm_settings):
        """``?7.1`` 上屏子项说明与存储位置（只读）。"""
        llm_settings({"expert_review": True})
        out = _run(monkeypatch, [f"?{_sub_number('llm_debate_procon')}", "0"])
        assert "features.json → llm_debate_procon" in out
        assert "智囊团深度复盘的生成选项" in out
        assert _features_file() == {}

    def test_question_mark_accepts_stable_key(self, monkeypatch, llm_settings):
        """``?键名`` 与编号通道等价（编号漂移免疫的稳定入口）。"""
        llm_settings({})
        out = _run(monkeypatch, ["?news_correlation", "0"])
        assert "llm_settings.json → enabled_llm.news_correlation" in out

    def test_unknown_question_target_reports(self, monkeypatch, llm_settings):
        llm_settings({})
        out = _run(monkeypatch, ["?nope", "0"])
        assert "无效选择" in out

    def test_invalid_number_reports(self, monkeypatch, llm_settings):
        llm_settings({})
        out = _run(monkeypatch, ["99", "0"])
        assert "无效编号" in out
