"""中断收口各步的独立容错（`report/run_integrity`）。

`handle_interruption` 是 KeyboardInterrupt 的安全落点：五步（读阶段 / 清临时文件 /
落中断记录 / 组装提示 / 收敛健康检查）各自 best-effort，任一步失败都不得阻断后续步骤
与中断传播——否则用户按 Ctrl+C 后看到的是 traceback 而不是「清到什么程度」。
本文件逐步骤注入故障，锁住「单步失败不影响其余步骤」这条契约。
"""

from __future__ import annotations

import logging
import os

import pytest

from src.python.report import run_integrity as ri
from src.test._fixtures.reporters import RecordingReporter

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class _Perf:
    def __init__(self, *, stage_error: bool = False, mark_error: bool = False) -> None:
        self._stage_error = stage_error
        self._mark_error = mark_error
        self.marked = False

    def stage_status(self):
        if self._stage_error:
            raise RuntimeError("probe fault")
        return {"phase": "行情获取"}

    def mark_interrupted(self) -> None:
        if self._mark_error:
            raise RuntimeError("probe fault")
        self.marked = True

    def save(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _clean_context():
    yield
    ri.clear_run()


@pytest.fixture()
def output_dir(tmp_path):
    return tmp_path


class TestBeginRunSweepFault:
    def test_sweep_failure_still_returns_context(self, output_dir, monkeypatch, caplog):
        """预清扫失败（目录权限）只记警告，运行上下文照常建立。"""

        def _raise(path):
            raise OSError("permission denied")

        monkeypatch.setattr(ri, "_sweep_product_tmps", _raise)

        ctx = ri.begin_run("basic", str(output_dir))

        assert ctx.report_type == "basic"
        assert ri.current_run() is ctx
        assert "预清扫遗留临时文件失败" in caplog.text


class TestUnlinkQuiet:
    def test_missing_file_returns_false(self, output_dir):
        assert ri._unlink_quiet(str(output_dir / "absent.tmp")) is False

    def test_permission_error_returns_false_with_warning(self, output_dir, monkeypatch, caplog):
        """删除失败（只读挂载）→ 告警 + False，由调用方继续处理其余文件。"""
        target = output_dir / "probe.tmp"
        target.write_bytes(b"x")

        def _raise(path):
            raise OSError("read-only file system")

        monkeypatch.setattr(ri.os, "unlink", _raise)

        assert ri._unlink_quiet(str(target)) is False
        assert "删除临时文件失败" in caplog.text


class TestCleanupDedup:
    def test_registered_path_counted_once(self, output_dir):
        ctx = ri.begin_run("basic", str(output_dir))
        stray = output_dir / f"{ri.REPORT_FILE_BASE}_probe{ri.TEMP_SUFFIX}"
        stray.write_bytes(b"x")
        ri.note_temp(str(stray))

        removed = ri._cleanup_context_temps(ctx)

        assert removed == [str(stray)]
        assert not stray.exists()

    def test_undeletable_registered_path_not_double_counted(self, output_dir, monkeypatch):
        """登记路径删不掉时，产物前缀兜底再扫到它也不得重复计入清理数。"""
        ctx = ri.begin_run("basic", str(output_dir))
        stray = output_dir / f"{ri.REPORT_FILE_BASE}_locked{ri.TEMP_SUFFIX}"
        stray.write_bytes(b"x")
        ri.note_temp(str(stray))
        monkeypatch.setattr(ri, "_unlink_quiet", lambda path: False)

        removed = ri._cleanup_context_temps(ctx)

        assert removed == [], "删除失败不计入清理数"
        assert stray.exists()


class TestDisplayPath:
    def test_cross_drive_falls_back_to_absolute(self, output_dir, monkeypatch):
        """`relpath` 不可算（跨盘）→ 原样给绝对路径，不抛异常。"""

        def _raise(path, start=None):
            raise ValueError("different drives")

        monkeypatch.setattr(ri.os.path, "relpath", _raise)

        assert ri._display_path(str(output_dir / "a.html"), str(output_dir)) == str(output_dir / "a.html")

    def test_outside_output_dir_keeps_absolute(self, tmp_path):
        outside = tmp_path.parent / "elsewhere.html"

        assert ri._display_path(str(outside), str(tmp_path)) == str(outside)


class TestEmitFault:
    def test_reporter_failure_is_swallowed(self, caplog):
        """进度通道 warn 抛异常 → DEBUG 后继续（中断收口不能因通道故障失败）。"""
        ri._emit(RecordingReporter(raise_on_warn=True), "提示")

        assert "中断提示输出失败" in caplog.text

    def test_reporter_without_warn_is_noop(self, caplog):
        """进度通道没有 warn（静默报告器）→ 静默跳过，不记错误。"""
        ri._emit(object(), "提示")

        assert not [r for r in caplog.records if r.levelno >= logging.WARNING], (
            "无 warn 通道属正常配置，不得记告警及以上日志"
        )


class TestHandleInterruptionSteps:
    def test_stage_read_failure_keeps_default_label(self, output_dir, caplog):
        """读阶段失败 → 回落到缺省「启动准备」，提示仍要发出去。"""
        ri.begin_run("basic", str(output_dir))
        ri.bind_perf(_Perf(stage_error=True))
        reporter = RecordingReporter()

        ri.handle_interruption(reporter)

        assert reporter.warns, "提示不得因读阶段失败而丢失"
        assert "阶段：启动准备" in reporter.warns[0]

    def test_cleanup_failure_keeps_going(self, output_dir, monkeypatch, caplog):
        """清理临时文件失败 → 告警 + 提示里记 0 个，后续步骤（落中断记录/提示）照跑。"""
        ri.begin_run("basic", str(output_dir))
        perf = _Perf()
        ri.bind_perf(perf)
        reporter = RecordingReporter()

        def _raise(ctx):
            raise OSError("io error")

        monkeypatch.setattr(ri, "_cleanup_context_temps", _raise)

        ri.handle_interruption(reporter)

        assert "清理临时文件失败" in caplog.text
        assert perf.marked, "清理失败不得阻断中断记录落盘"
        assert "已清理临时文件 0 个" in reporter.warns[0]

    def test_interrupt_record_failure_keeps_going(self, output_dir, caplog):
        """落中断记录失败 → 告警，但仍要给用户「已写盘/已丢弃」提示。"""
        ri.begin_run("basic", str(output_dir))
        ri.bind_perf(_Perf(mark_error=True))
        reporter = RecordingReporter()

        ri.handle_interruption(reporter)

        assert "中断运行记录落盘失败" in caplog.text
        assert reporter.warns, "记录失败不得连提示一起丢"

    def test_message_assembly_failure_is_swallowed(self, output_dir, monkeypatch, caplog):
        """组装提示失败（如产物清单异常）→ 告警，不向外抛。"""
        ri.begin_run("basic", str(output_dir))
        ri.note_artifact("html", str(output_dir / "r.html"))

        def _raise(path, directory):
            raise RuntimeError("probe fault")

        monkeypatch.setattr(ri, "_display_path", _raise)

        ri.handle_interruption(RecordingReporter())

        assert "组装中断提示失败" in caplog.text

    def test_health_collect_failure_is_swallowed(self, output_dir, monkeypatch, caplog):
        """收敛健康检查失败（future 卡死/异常）→ DEBUG，不阻断中断收口。"""
        ri.begin_run("basic", str(output_dir))
        ri.bind_health(object(), "basic", [])
        reporter = RecordingReporter()

        import src.python.report._report_health as health_mod

        def _raise(*args, **kwargs):
            raise RuntimeError("probe fault")

        monkeypatch.setattr(health_mod, "_collect_health_checks", _raise)

        ri.handle_interruption(reporter)

        assert "健康检查收敛失败" in caplog.text
        assert reporter.warns, "收敛失败不得影响已完成的提示"
        assert os.path.isdir(output_dir)


class TestStraySweep:
    def test_unregistered_stray_is_collected(self, output_dir):
        """未登记的在写临时文件（崩溃残留）也按产物前缀兜底清扫。"""
        ctx = ri.begin_run("basic", str(output_dir))
        stray = output_dir / f"{ri.REPORT_FILE_BASE}_orphan{ri.TEMP_SUFFIX}"
        stray.write_bytes(b"x")

        removed = ri._cleanup_context_temps(ctx)

        assert removed == [str(stray)]
        assert not stray.exists()


class TestCurrentPerf:
    def test_none_without_run_context(self):
        assert ri.current_perf() is None

    def test_returns_bound_perf(self, output_dir):
        ri.begin_run("basic", str(output_dir))
        perf = _Perf()
        ri.bind_perf(perf)

        assert ri.current_perf() is perf
