"""`scripts/probe-date-bombs.py`（时间炸弹探测）单元测试。

覆盖：日期回移（两种写法）、候选筛选口径、rot 判定与失败用例提取、以及最关键的
**改写后必还原**（真实跑 pytest 的路径 + 异常路径双兜底）。
"""

from __future__ import annotations

import sys

import pytest

from src.test._script_loader import load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
    pytest.mark.usefixtures("offline_external_sources"),
]


@pytest.fixture(scope="module")
def probe():
    return load_script("probe-date-bombs.py")


def test_mutate_dates_shifts_string_and_tuple_forms(probe):
    text = 'D = "2026-09-01"\nT = datetime(2026, 9, 1)\n'
    mutated = probe.mutate_dates(text, years=3)
    assert '"2023-09-01"' in mutated
    assert "datetime(2023, 9, 1)" in mutated


def test_mutate_dates_leaves_non_date_text_alone(probe):
    text = "assert len(items) == 2026\nname = 'v2026'\n"
    assert probe.mutate_dates(text, years=3) == text


def test_has_absolute_date_predicate(probe):
    assert probe._has_absolute_date('x = "2026-09-01"')
    assert probe._has_absolute_date("y = datetime(2026, 9, 1)")
    assert not probe._has_absolute_date("z = 2026")


def test_candidate_files_only_hold_dated_retention_sensitive_files(probe):
    """候选 = 含绝对日期 **且** 与保留期/TTL 关键词同现（默认口径）。"""
    candidates = probe.candidate_files()
    assert candidates, "仓库里应存在保留期相关的含日期测试文件"
    for path in candidates:
        text = path.read_text(encoding="utf-8")
        assert probe._has_absolute_date(text), f"{path} 无绝对日期却被选为候选"
        assert probe._RETENTION_HINTS.search(text), f"{path} 无保留期关键词却被选为候选"


def test_probe_file_detects_rot_and_reports_failing_case(probe, tmp_path, monkeypatch):
    """rot 判定：变异后 pytest 报 FAILED → status=rot，失败用例名被提取。"""
    target = tmp_path / "test_sample.py"
    target.write_text('def test_x():\n    assert "2026-09-01" == "x"\n', encoding="utf-8")

    class _FakeCompleted:
        stdout = "FAILED test_sample.py::TestX::test_bomb - AssertionError\n1 failed, 2 passed in 0.10s\n"
        stderr = ""

    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **k: _FakeCompleted())

    result = probe.probe_file(target, years=3, timeout=60, python=sys.executable)

    assert result["status"] == "rot"
    assert result["fails"] == ["TestX::test_bomb"]
    assert "1 failed" in result["summary"]
    # 异常路径同样还原：文件内容必须回到改写前
    assert target.read_text(encoding="utf-8") == 'def test_x():\n    assert "2026-09-01" == "x"\n'


def test_probe_file_restores_after_real_run(probe, tmp_path):
    """真实子进程跑 pytest：通过用例 + 还原校验（改写能力与还原能力一体验证）。"""
    original = 'DATA = "2026-09-01"\n\n\ndef test_ok():\n    assert DATA.startswith("20")\n'
    target = tmp_path / "test_sample_ok.py"
    target.write_text(original, encoding="utf-8")

    result = probe.probe_file(target, years=3, timeout=300, python=sys.executable)

    assert result["status"] == "ok", result
    assert target.read_text(encoding="utf-8") == original, "改写后必须逐字还原"


def test_restore_all_verifies_content(probe, tmp_path, capsys):
    """还原表兜底：登记后调用 `_restore_all` 会写回原文并清空登记。"""
    target = tmp_path / "test_pending.py"
    original = 'def test_a():\n    assert "2026-09-01"\n'
    target.write_text("MUTATED\n", encoding="utf-8")

    probe._PENDING_RESTORE[target] = (original, probe._digest(original))
    probe._restore_all()

    assert target.read_text(encoding="utf-8") == original
    assert target not in probe._PENDING_RESTORE
    assert "还原校验失败" not in capsys.readouterr().out
