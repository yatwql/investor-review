"""``handlers_config`` 三处面板的中断/筛选/页脚支路：未修改态、EOF 中断、筛选态跳行。

每个面板的「输入中断」与「筛选态只渲染命中项」都被主循环吞成静默分支——错一次
用户看到的是「面板莫名退出」或「筛选后仍见未命中项」，所以逐条按可观察输出断言：
Esc 不改配置、EOF 不写盘、筛选后隐藏行不再出现在帧里、页脚随改动计数出现。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.tui import handlers_config

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


@patch("src.python.tui.handlers_config.refresh_config")
@patch("src.python.tui.handlers_config.get_config_cache", return_value={})
def test_edit_single_config_escape_leaves_value_untouched(_mock_cache, _mock_refresh, capsys):
    """Esc（``input_choice`` 返回 None）→ 打印「未修改」且不落盘。"""
    with (
        patch.object(handlers_config, "input_choice", return_value=None),
        patch.object(handlers_config, "_apply_edit") as mock_apply,
    ):
        handlers_config._edit_single_config("holdings_dir", "目录")

    assert "未修改" in capsys.readouterr().out
    assert not mock_apply.called, "Esc 退出不得触发保存"


@patch("src.python.tui.handlers_config.refresh_config")
def test_llm_tuning_edit_eof_returns_to_panel(_mock_refresh, capsys):
    """调优项编辑处 EOF → 中止本次编辑回到面板循环，不写任何配置。"""
    with (
        patch.object(handlers_config, "input_choice", side_effect=["1", EOFError("eof"), "0"]),
        patch("src.python.config.get_llm_config", return_value={}),
        patch.object(handlers_config, "_apply_edit") as mock_apply,
    ):
        handlers_config._cmd_config_llm_tuning()

    assert "LLM 调优参数" in capsys.readouterr().out
    assert not mock_apply.called, "输入中断不得触发保存"


@patch("src.python.tui.handlers_config.refresh_config")
def test_llm_tuning_render_skips_rows_outside_filter(_mock_refresh, capsys):
    """筛选态：未命中项不渲染（索引仍占筛选前的位置）。

    以 EOF 收尾而非 ``0``：``0`` 会先清筛选再重绘一帧全量行，把「跳行」证据冲掉。
    """
    with (
        patch.object(handlers_config, "input_choice", side_effect=["/", EOFError("eof")]),
        patch("src.python.tui.panel_runtime.input_choice", return_value="预算"),
        patch("src.python.config.get_llm_config", return_value={}),
    ):
        handlers_config._cmd_config_llm_tuning()

    out = capsys.readouterr().out
    filtered_frame = out.split("筛选「预算」", 1)[1]
    assert "LLM 总时间预算（秒）" in filtered_frame, "命中项须保留在帧内"
    assert "单请求重试次数" not in filtered_frame, "未命中项须被跳过"


@patch("src.python.tui.handlers_config.refresh_config")
def test_llm_tuning_render_prints_undo_footer(_mock_refresh, capsys):
    """有改动时页脚随帧渲染（页脚由会话改动计数派生，此处以页脚存在态驱动该分支）。"""
    footer = "  本次改动 2 项（u 撤销上次 · U 全部还原）"
    with (
        patch.object(handlers_config, "input_choice", side_effect=["0"]),
        patch.object(handlers_config, "config_undo_footer", return_value=footer),
        patch("src.python.config.get_llm_config", return_value={}),
    ):
        handlers_config._cmd_config_llm_tuning()

    assert footer in capsys.readouterr().out


@patch("src.python.tui.handlers_config.refresh_config")
@patch("src.python.tui.handlers_config.get_config_cache", return_value={})
def test_comparison_indices_eof_exits_panel_quietly(_mock_cache, _mock_refresh, capsys):
    """对比指数池面板 EOF → 吞掉异常退出（首帧已渲染，不把中断抛给上层菜单）。"""
    with patch.object(handlers_config, "input_choice", side_effect=EOFError):
        handlers_config._cmd_config_comparison_indices()

    assert "管理对比指数池" in capsys.readouterr().out


def test_add_comparison_index_eof_on_name_aborts(capsys):
    """输入名称处 EOF → 中止添加，不写盘。"""
    with (
        patch.object(handlers_config, "input_choice", side_effect=["sh000905", EOFError("eof")]),
        patch.object(handlers_config, "_apply_edit") as mock_apply,
    ):
        handlers_config._add_comparison_index()

    assert "请输入指数名称" in capsys.readouterr().out
    assert not mock_apply.called, "名称输入中断不得写入对比池"


def test_add_comparison_index_escape_on_name_aborts(capsys):
    """输入名称处 Esc（返回 None）→ 静默返回，不写盘。"""
    with (
        patch.object(handlers_config, "input_choice", side_effect=["sh000905", None]),
        patch.object(handlers_config, "_apply_edit") as mock_apply,
    ):
        handlers_config._add_comparison_index()

    assert "请输入指数名称" in capsys.readouterr().out
    assert not mock_apply.called, "Esc 不得写入对比池"


@patch("src.python.tui.handlers_config.refresh_config")
def test_anonymization_render_skips_filtered_modes_and_prints_footer(_mock_refresh, capsys):
    """匿名化面板筛选态跳过未命中模式，且页脚随帧渲染。

    以 EOF 收尾，避免 ``0`` 清筛选后的全量重绘混进「跳行」证据。
    """
    footer = "  本次改动 1 项（u 撤销上次 · U 全部还原）"
    with (
        patch.object(handlers_config, "input_choice", side_effect=["/", EOFError("eof")]),
        patch("src.python.tui.panel_runtime.input_choice", return_value="完全匿名"),
        patch.object(handlers_config, "config_undo_footer", return_value=footer),
        patch("src.python.config.anonymizer.get_anonymization_mode", return_value="off"),
    ):
        handlers_config._cmd_config_anonymization_mode()

    out = capsys.readouterr().out
    filtered_frame = out.split("筛选「完全匿名」", 1)[1]
    assert "完全匿名" in filtered_frame, "命中项须保留在帧内"
    assert "代码显示" not in filtered_frame, "未命中模式须被跳过"
    assert footer in filtered_frame
