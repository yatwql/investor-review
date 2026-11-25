"""report/cli_progress.py 的毫秒口径与 verbose stderr 通道分支。

锁住的契约：
  - 耗时上屏：<1ms 显示 ``<1ms``，亚秒显示整数毫秒，其余一位小数秒；
  - ``--verbose`` 下 warn/error、耗时排行、收尾摘要同步写 stderr（带 ``[!]``/``[ERR]`` 前缀），
    常规模式只走 logging（stderr 无内容）。
"""

from __future__ import annotations

import pytest

from src.python.report import cli_progress as cp

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def test_fmt_duration_sub_millisecond() -> None:
    assert cp._fmt_duration(0.0004) == "<1ms"


def test_fmt_duration_millisecond_range() -> None:
    assert cp._fmt_duration(0.25) == "250ms"


def test_verbose_warn_and_error_write_prefixed_lines(capsys: pytest.CaptureFixture[str]) -> None:
    reporter = cp.CliProgressReporter(verbose=True)
    reporter.warn("行情源降级")
    reporter.error("写盘失败")
    err = capsys.readouterr().err
    assert "[!] 行情源降级" in err
    assert "[ERR] 写盘失败" in err


def test_verbose_timing_summary_written_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    reporter = cp.CliProgressReporter(verbose=True)
    with reporter.timer("持仓页签"):
        pass
    reporter.print_timing_summary()
    err = capsys.readouterr().err
    assert "模块耗时排行" in err
    assert "持仓页签" in err


def test_emit_summary_lines_verbose_channel(capsys: pytest.CaptureFixture[str]) -> None:
    reporter = cp.CliProgressReporter(verbose=True)
    cp._emit_summary_lines(reporter, ["缓存命中率: 3/4（75.0%）"])
    assert "缓存命中率: 3/4（75.0%）" in capsys.readouterr().err
