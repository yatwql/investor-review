"""`scripts/probe-date-bombs.py` 的 CLI 编排与单文件筛查分支测试。

覆盖 `main()` 的各条编排路径（dry-run / 跳过 / 超时 / rot / 通过 / detail / CI 退出码）
与 `probe_file()` 的早退与异常分支（无字面量、超时、收集期错误）、`_git_dirty()` 的两侧
判定、`_restore_all()` 的写失败兜底。

pytest 子进程一律 mock：本用例验证的是**编排与判定**，不是被测文件的真实性。
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(scope="module")
def probe():
    return load_script("probe-date-bombs.py")


def _run_main(probe, monkeypatch, argv: list[str]) -> int:
    """跑一次 main()，返回退出码（`--dry-run` 正常返回早退，按 0 计）。"""
    monkeypatch.setattr(sys, "argv", ["probe-date-bombs.py", *argv])
    try:
        probe.main()
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


class _Result:
    """`_FakeCompleted` 的命名变体：pytest 子进程输出替身。"""

    def __init__(self, stdout: str = "", stderr: str = "") -> None:
        self.stdout = stdout
        self.stderr = stderr


class TestProbeFileBranches:
    """`probe_file()` 的早退与异常分支。"""

    def test_file_without_date_literal_is_not_run(self, probe, tmp_path, monkeypatch):
        """无绝对日期 → status=no-literal，且不启动 pytest 子进程（否则白跑）。"""
        target = tmp_path / "test_nodate.py"
        target.write_text("def test_x():\n    assert 1 + 1 == 2\n", encoding="utf-8")

        def _fail(*_a, **_k):
            raise AssertionError("无日期字面量时不得启动子进程")

        monkeypatch.setattr(probe.subprocess, "run", _fail)

        result = probe.probe_file(target, years=3, timeout=60, python=sys.executable)

        assert result["status"] == "no-literal"
        assert result["fails"] == []

    def test_timeout_reports_timeout_status(self, probe, tmp_path, monkeypatch):
        """子进程超时 → status=timeout，summary 带超时阈值。"""
        target = tmp_path / "test_slow.py"
        target.write_text('D = "2026-09-01"\n', encoding="utf-8")

        def _timeout(*_a, **_k):
            raise subprocess.TimeoutExpired(cmd="pytest", timeout=30)

        monkeypatch.setattr(probe.subprocess, "run", _timeout)

        result = probe.probe_file(target, years=3, timeout=30, python=sys.executable)

        assert result["status"] == "timeout"
        assert "30" in result["summary"]
        # 超时路径也必须还原原文（finally 兜底）
        assert target.read_text(encoding="utf-8") == 'D = "2026-09-01"\n'

    def test_collection_errors_mark_rot_and_count(self, probe, tmp_path, monkeypatch):
        """收集期 ERROR（无 FAILED 行）同样判 rot，summary 追加错误计数；detail 收集断言原文。"""
        target = tmp_path / "test_import_err.py"
        target.write_text('D = "2026-09-01"\n', encoding="utf-8")
        out = (
            "ERROR test_x.py - ImportError: boom\n"
            "ERROR test_x.py - ImportError: boom2\n"
            "test/x.py:9: AssertionError: assert '2021-09-01' == '2026-09-01'\n"
            "3 errors in 0.20s\n"
        )
        monkeypatch.setattr(probe.subprocess, "run", lambda *_a, **_k: _Result(out))

        result = probe.probe_file(target, years=3, timeout=60, python=sys.executable, detail=True)

        assert result["status"] == "rot"
        assert "收集期错误 2 处" in result["summary"]
        assert result["asserts"] == ["test/x.py:9: AssertionError: assert '2021-09-01' == '2026-09-01'"]


class TestGitDirty:
    """`_git_dirty()` 判定：脏文件不动。"""

    def test_porcelain_output_means_dirty(self, probe, monkeypatch):
        monkeypatch.setattr(probe.subprocess, "run", lambda *_a, **_k: _Result(" M test_x.py\n"))
        assert probe._git_dirty(probe.REPO_ROOT / "test_x.py") is True

    def test_empty_output_means_clean(self, probe, monkeypatch):
        monkeypatch.setattr(probe.subprocess, "run", lambda *_a, **_k: _Result(""))
        assert probe._git_dirty(probe.REPO_ROOT / "test_x.py") is False

    def test_git_failure_falls_back_to_dirty(self, probe, monkeypatch):
        """判不出就当脏：宁可不测也不冒险覆盖用户编辑。"""

        def _boom(*_a, **_k):
            raise OSError("git 不存在")

        monkeypatch.setattr(probe.subprocess, "run", _boom)
        assert probe._git_dirty(probe.REPO_ROOT / "test_x.py") is True


class TestRestoreAll:
    """`_restore_all()` 的异常与校验分支。"""

    def test_unwritable_file_is_skipped(self, probe, tmp_path):
        """写回失败（OSError）→ 跳过并清出登记表，不冒泡。"""
        missing = tmp_path / "gone" / "test_x.py"
        probe._PENDING_RESTORE[missing] = ("ORIGINAL", probe._digest("ORIGINAL"))

        probe._restore_all()

        assert missing not in probe._PENDING_RESTORE

    def test_digest_mismatch_warns(self, probe, tmp_path, capsys, monkeypatch):
        """登记摘要与写回内容不符 → 打 [ERR] 提示人工检查。"""
        target = tmp_path / "test_x.py"
        target.write_text("ORIGINAL\n", encoding="utf-8")
        probe._PENDING_RESTORE[target] = ("ORIGINAL\n", probe._digest("别的原文"))

        probe._restore_all()

        assert "还原校验失败" in capsys.readouterr().out


class TestMainOrchestration:
    """`main()` 编排：候选枚举 → 跳过/超时/rot/通过 → 统一退出码。"""

    def test_dry_run_lists_candidates_without_probing(self, probe, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(probe, "candidate_files", lambda scan_all=False: [tmp_path / "test_a.py"])

        def _fail(*_a, **_k):
            raise AssertionError("dry-run 不得真跑 pytest")

        monkeypatch.setattr(probe.subprocess, "run", _fail)
        code = _run_main(probe, monkeypatch, ["--dry-run"])

        assert code == 0
        assert "候选测试文件 1 个" in capsys.readouterr().out

    def test_dry_run_all_flag_widens_candidate_scope(self, probe, monkeypatch):
        seen: dict = {}

        def _candidates(scan_all=False):
            seen["scan_all"] = scan_all
            return []

        monkeypatch.setattr(probe, "candidate_files", _candidates)
        assert _run_main(probe, monkeypatch, ["--dry-run", "--all"]) == 0
        assert seen["scan_all"] is True

    def test_missing_file_is_skipped(self, probe, monkeypatch, capsys):
        monkeypatch.setattr(probe, "candidate_files", lambda scan_all=False: [])
        monkeypatch.setattr(sys, "argv", ["probe", "--files", "src/test/nope.py", "-v"])
        with pytest.raises(SystemExit) as excinfo:
            probe.main()

        assert excinfo.value.code == 0
        assert "跳过（文件不存在）" in capsys.readouterr().out

    def test_dirty_file_is_skipped_silently_without_verbose(self, probe, tmp_path, monkeypatch, capsys):
        """默认跳过脏文件；非 verbose 不打逐文件行，但汇总行仍出（含跳过数）。"""
        target = tmp_path / "test_dirty.py"
        target.write_text('D = "2026-09-01"\n', encoding="utf-8")
        monkeypatch.setattr(probe, "candidate_files", lambda scan_all=False: [target])
        monkeypatch.setattr(probe, "_git_dirty", lambda _p: True)

        def _fail(*_a, **_k):
            raise AssertionError("跳过分支不得调用子进程")

        monkeypatch.setattr(probe.subprocess, "run", _fail)
        code = _run_main(probe, monkeypatch, [])

        out = capsys.readouterr().out
        assert code == 0
        assert "工作区有未提交改动" not in out
        assert "跳过 1" in out

    def test_dirty_file_skip_is_reported_when_verbose(self, probe, tmp_path, monkeypatch, capsys):
        target = tmp_path / "test_dirty.py"
        target.write_text('D = "2026-09-01"\n', encoding="utf-8")
        monkeypatch.setattr(probe, "candidate_files", lambda scan_all=False: [target])
        monkeypatch.setattr(probe, "_git_dirty", lambda _p: True)

        code = _run_main(probe, monkeypatch, ["-v"])

        assert code == 0
        assert "工作区有未提交改动" in capsys.readouterr().out

    def test_allow_dirty_probes_the_file(self, probe, tmp_path, monkeypatch):
        target = tmp_path / "test_dirty.py"
        target.write_text('D = "2026-09-01"\n', encoding="utf-8")
        monkeypatch.setattr(probe, "candidate_files", lambda scan_all=False: [target])
        monkeypatch.setattr(probe, "_git_dirty", lambda _p: True)
        monkeypatch.setattr(probe.subprocess, "run", lambda *_a, **_k: _Result("2 passed in 0.10s\n"))

        assert _run_main(probe, monkeypatch, ["--allow-dirty"]) == 0

    def test_timeout_produces_finding_and_exit_2(self, probe, tmp_path, monkeypatch, capsys):
        target = tmp_path / "test_slow.py"
        target.write_text('D = "2026-09-01"\n', encoding="utf-8")
        monkeypatch.setattr(probe, "candidate_files", lambda scan_all=False: [target])
        monkeypatch.setattr(probe, "_git_dirty", lambda _p: False)
        monkeypatch.setattr(
            probe,
            "probe_file",
            lambda *a, **k: {"status": "timeout", "fails": [], "summary": "超时（>60s）", "asserts": []},
        )
        # 汇总统计行仅在 verbose 或无跳过时输出，故带 -v
        code = _run_main(probe, monkeypatch, ["--timeout", "60", "-v"])

        out = capsys.readouterr().out
        assert code == 2
        assert "变异后跑测试超时" in out
        assert "超时 1" in out

    def test_rot_finding_truncates_long_case_list_at_four(self, probe, tmp_path, monkeypatch, capsys):
        """命中超过 4 个用例时只列前 4 个并加省略号（防一行刷屏）。"""
        target = tmp_path / "test_rot.py"
        target.write_text('D = "2026-09-01"\n', encoding="utf-8")
        monkeypatch.setattr(probe, "candidate_files", lambda scan_all=False: [target])
        monkeypatch.setattr(probe, "_git_dirty", lambda _p: False)
        monkeypatch.setattr(
            probe,
            "probe_file",
            lambda *a, **k: {
                "status": "rot",
                "fails": ["t1", "t2", "t3", "t4", "t5"],
                "summary": "5 failed in 0.20s",
                "asserts": [],
            },
        )
        code = _run_main(probe, monkeypatch, [])

        out = capsys.readouterr().out
        assert code == 2
        assert "t4" in out and "t5" not in out
        assert "…" in out

    def test_rot_with_detail_prints_assert_lines(self, probe, tmp_path, monkeypatch, capsys):
        target = tmp_path / "test_rot.py"
        target.write_text('D = "2026-09-01"\n', encoding="utf-8")
        monkeypatch.setattr(probe, "candidate_files", lambda scan_all=False: [target])
        monkeypatch.setattr(probe, "_git_dirty", lambda _p: False)
        monkeypatch.setattr(
            probe,
            "probe_file",
            lambda *a, **k: {
                "status": "rot",
                "fails": ["t1"],
                "summary": "1 failed",
                "asserts": ["test/x.py:9: AssertionError: assert 1 == 2"],
            },
        )
        code = _run_main(probe, monkeypatch, ["--detail"])

        out = capsys.readouterr().out
        assert code == 2
        assert "AssertionError: assert 1 == 2" in out

    def test_all_ok_passes_with_zero_exit_and_verbose_line(self, probe, tmp_path, monkeypatch, capsys):
        target = tmp_path / "test_ok.py"
        target.write_text('D = "2026-09-01"\n', encoding="utf-8")
        monkeypatch.setattr(probe, "candidate_files", lambda scan_all=False: [target])
        monkeypatch.setattr(probe, "_git_dirty", lambda _p: False)
        monkeypatch.setattr(
            probe,
            "probe_file",
            lambda *a, **k: {"status": "ok", "fails": [], "summary": "3 passed", "asserts": []},
        )
        code = _run_main(probe, monkeypatch, ["-v"])

        out = capsys.readouterr().out
        assert code == 0
        assert "3 passed" in out
        assert "通过 1" in out

    def test_ci_mode_prints_bare_findings(self, probe, tmp_path, monkeypatch, capsys):
        """`--ci` 下 finding 行不带 `[ERR]` 前缀，也不打汇总行（统一契约）。"""
        target = tmp_path / "test_rot.py"
        target.write_text('D = "2026-09-01"\n', encoding="utf-8")
        monkeypatch.setattr(probe, "candidate_files", lambda scan_all=False: [target])
        monkeypatch.setattr(probe, "_git_dirty", lambda _p: False)
        monkeypatch.setattr(
            probe,
            "probe_file",
            lambda *a, **k: {"status": "rot", "fails": ["t1"], "summary": "1 failed", "asserts": []},
        )
        code = _run_main(probe, monkeypatch, ["--ci"])

        out = capsys.readouterr().out
        assert code == 2
        assert "[ERR]" not in out
        assert "须人工判读后修正或登记" not in out
