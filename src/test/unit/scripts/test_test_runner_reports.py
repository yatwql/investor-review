"""测试：test-runner.py 分阶段测试报告路径与汇总页链接。

回归背景（自审发现）：分阶段模式（dev-verify = Phase A 核心单元 + Phase B 基础场景）
两阶段都把 pytest-html 报告写到同一个 ``report.html``，后跑的 Phase B 覆盖 Phase A——
详细报告只剩 152 个场景用例，Phase A 的 2700+ 用例（真正的失败面）在报告里消失。
修法：每阶段一个报告文件（``report_phase_<tag>.html``），汇总页逐阶段给链接。

覆盖：
  - 报告路径：分阶段带阶段后缀、非分阶段维持 report.html（向后兼容）
  - 汇总页链接：仅有 report.html → 单链接；有分阶段文件 → 逐阶段链接；均无 → 占位

通过 import 方式复用 scripts/test-runner.py 的函数，不运行真实测试。
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest
from src.test._script_loader import load_script

_REPO_ROOT = Path(__file__).resolve().parents[4]

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


class TestProjectRoot:
    """项目根定位：拆包后 `_test_runner/paths.py` 的层级若算错会把报告写到 `scripts/` 下。"""

    def test_project_root_is_repo_root(self):
        runner = load_script("test-runner.py", module_name="test_runner_report_paths")
        assert Path(runner._PROJECT_ROOT).resolve() == _REPO_ROOT
        assert Path(runner._LATEST_DIR) == _REPO_ROOT / "test-reports" / "latest"
        assert Path(runner._SRC_DIR) == _REPO_ROOT / "src" / "test"

    def test_report_dirs_live_under_repo_root(self):
        runner = load_script("test-runner.py", module_name="test_runner_report_paths")
        for path in (runner._LATEST_DIR, runner._ARCHIVES_DIR):
            assert Path(path).is_relative_to(_REPO_ROOT)
            assert "scripts" not in Path(path).relative_to(_REPO_ROOT).parts


class TestPhaseReportPath:
    def test_phased_gets_own_file(self):
        runner = load_script("test-runner.py", module_name="test_runner_report_paths")
        path = runner._phase_report_path("dev-verify", "A")
        assert Path(path).parts[-2:] == ("dev-verify", "report_phase_A.html")
        assert Path(runner._phase_report_path("dev-verify", "B")).name == "report_phase_B.html"

    def test_non_phased_keeps_plain_name(self):
        """非分阶段模式维持 report.html（既有文档/CI artifact 约定不变）。"""
        path = Path(load_script("test-runner.py", module_name="test_runner_report_paths")._phase_report_path("unit"))
        assert path.parts[-2:] == ("unit", "report.html")

    def test_build_args_uses_phase_path(self):
        runner = load_script("test-runner.py", module_name="test_runner_report_paths")
        args = runner._build_pytest_args(
            {"marker": "unit", "parallel": False}, "dev-verify", True, False, None, phase_tag="A"
        )
        assert "--html" in args
        assert args[args.index("--html") + 1].endswith("report_phase_A.html")


class TestIndexLinks:
    def _make(self, runner, tmp_path, monkeypatch, files: list[str]):
        # 汇总页渲染已拆到 _test_runner.report_html：目录常量在该模块内解析
        report_html_mod = importlib.import_module("_test_runner.report_html")
        monkeypatch.setattr(report_html_mod, "_LATEST_DIR", str(tmp_path))
        mode_dir = tmp_path / "dev-verify"
        mode_dir.mkdir(parents=True, exist_ok=True)
        for name in files:
            (mode_dir / name).write_text("<html></html>", encoding="utf-8")
        return runner._report_links_html("dev-verify")

    def test_lists_every_phase(self, tmp_path, monkeypatch):
        html = self._make(
            load_script("test-runner.py", module_name="test_runner_report_paths"),
            tmp_path,
            monkeypatch,
            ["report_phase_A.html", "report_phase_B.html"],
        )
        assert "dev-verify/report_phase_A.html" in html
        assert "dev-verify/report_phase_B.html" in html
        assert "Phase A" in html and "Phase B" in html

    def test_plain_report_still_linked(self, tmp_path, monkeypatch):
        html = self._make(
            load_script("test-runner.py", module_name="test_runner_report_paths"),
            tmp_path,
            monkeypatch,
            ["report.html"],
        )
        assert 'href="dev-verify/report.html"' in html

    def test_no_report_shows_placeholder(self, tmp_path, monkeypatch):
        html = self._make(
            load_script("test-runner.py", module_name="test_runner_report_paths"), tmp_path, monkeypatch, []
        )
        assert "无" in html


class TestDebugLogWriteFailure:
    """失败详情落盘失败时必须留痕——不得静默吞掉（诊断链在那一步断掉）。"""

    def test_debug_log_write_failure_is_reported(self, monkeypatch, tmp_path, capsys):
        runner = load_script("test-runner.py", module_name="test_runner_debug_log_fail")
        blocker = tmp_path / "not_a_dir"
        blocker.write_text("x", encoding="utf-8")
        # 实现已拆到 `_test_runner/runner.py`：按其函数全局命名空间打补丁
        # （父级是文件 → 目录不可创建，落盘必然失败）
        globals_ns = runner._run_phased.__globals__
        monkeypatch.setitem(globals_ns, "_LATEST_DIR", str(blocker / "latest"))
        monkeypatch.setitem(globals_ns, "_check_pytest_html", lambda: False)
        monkeypatch.setitem(globals_ns, "_build_pytest_args", lambda *a, **k: ["pytest"])

        class _Proc:
            returncode = 1
            stdout = "1 failed\n===== FAILURES ====="
            stderr = ""

        monkeypatch.setitem(globals_ns, "subprocess", type("_Sub", (), {"run": staticmethod(lambda *a, **k: _Proc())}))

        result = runner._run_phased([{"marker": "unit", "desc": "d"}], "verify", False)

        out = capsys.readouterr().out
        assert "详细日志写入失败" in out, f"落盘失败必须留痕，实际输出: {out!r}"
        assert result["exit_code"] == 1, "落盘失败不得改变本轮失败判定"
