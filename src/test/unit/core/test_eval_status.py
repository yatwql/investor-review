"""决策质量回测入口状态与随报告执行（opt-in）单元测试。

覆盖：产物天数派生（无目录/空目录/今天/多天前）、提示两态（无记录/距上次 N 天）、
随报告执行的三态（脚本缺失 / 子进程超时或异常 / 成功只回报末几行）、CLI `--post-eval`
开关可解析、doctor 状态行进入「日志与缓存」组。全部离线，不真实执行回测脚本。
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

from src.python.core import eval_status

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _write_stub(directory: Path, *, days_ago: int = 0) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "horizon.json"
    path.write_text("{}", encoding="utf-8")
    stamp = time.time() - days_ago * 86400
    os.utime(path, (stamp, stamp))
    return path


def test_last_eval_days_missing_dir_and_empty_dir(tmp_path):
    assert eval_status.last_eval_days(tmp_path / "nope") is None
    empty = tmp_path / "empty"
    empty.mkdir()
    assert eval_status.last_eval_days(empty) is None


def test_last_eval_days_today_and_older(tmp_path):
    _write_stub(tmp_path, days_ago=0)
    assert eval_status.last_eval_days(tmp_path) == 0
    _write_stub(tmp_path, days_ago=5)
    assert eval_status.last_eval_days(tmp_path) == 5


def test_format_eval_hint_two_states(tmp_path):
    assert "尚无回测产物" in eval_status.format_eval_hint(tmp_path / "nope")
    _write_stub(tmp_path, days_ago=3)
    hint = eval_status.format_eval_hint(tmp_path)
    assert "距上次回测 3 天" in hint
    assert eval_status.EVAL_COMMAND in hint


def test_run_post_eval_missing_script(tmp_path):
    out = eval_status.run_post_eval(script=tmp_path / "nope.py")
    assert out["ok"] is False
    assert "脚本不存在" in out["error"]


def test_run_post_eval_swallow_timeout(monkeypatch, tmp_path):
    script = tmp_path / "eval.py"
    script.write_text("print('x')", encoding="utf-8")

    def _boom(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="eval", timeout=1)

    monkeypatch.setattr(eval_status.subprocess, "run", _boom)
    out = eval_status.run_post_eval(script=script)
    assert out["ok"] is False
    assert "TimeoutExpired" in out["error"]


def test_run_post_eval_success_reports_tail(monkeypatch, tmp_path):
    script = tmp_path / "eval.py"
    script.write_text("print('x')", encoding="utf-8")
    captured: dict[str, list[str]] = {}

    def _fake_run(cmd, **_kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="line1\nline2\nline3\n", stderr="")

    monkeypatch.setattr(eval_status.subprocess, "run", _fake_run)
    out = eval_status.run_post_eval(script=script)
    assert out["ok"] is True and out["returncode"] == 0
    assert out["tail"].splitlines()[-1] == "line3"
    assert "--post-eval" not in str(captured["cmd"])  # 子进程只传阶段名
    assert set(eval_status.DEFAULT_POST_EVAL_STAGES) <= {str(p) for p in captured["cmd"]}


def test_cli_report_accepts_post_eval_flag():
    from src.python.cli._parser import _build_parser

    args = _build_parser().parse_args(["report", "--post-eval"])
    assert args.post_eval is True


def test_doctor_reports_eval_status_line():
    from src.python.core import doctor

    items = doctor._check_eval_status()
    assert any(item["label"] == "决策质量回测" for item in items)
    assert items[0]["group"] == doctor.GROUP_LOG_CACHE


def test_last_eval_date_is_single_source_for_report_side(tmp_path):
    """报告侧的「回测产物日期」必须与本模块同源（口径唯一，不得各写一份 glob+mtime）。"""
    from src.python.report import decision_basis

    assert eval_status.last_eval_date(tmp_path / "nope") is None
    _write_stub(tmp_path, days_ago=4)
    latest = eval_status.last_eval_date(tmp_path)
    assert latest is not None
    assert decision_basis.backtest_run_date(tmp_path) == latest.strftime("%Y-%m-%d")
