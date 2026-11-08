"""测试：类型检查守护脚本 — check-types.py

覆盖：
  - 解析器定位：PATH 有 pyright 用它 / 只有 npx 时走 `npx --no-install` / 两者皆无返回 None
  - 报告解析：仅 ERROR 级入 finding，WARNING/INFORMATION 不计；行/列按 1 基输出、按文件行序排序
  - 多行 message 只取首行（CI 日志一行一条）
  - 报告不可用（无 stdout / 非 JSON）→ 视为调用失败，main 退出 1（环境缺失口径）
  - 退出码契约：干净 0 / 有 finding 2 / 解析器缺失 1
  - 超量 finding 截断并补一行「其余 N 条已省略」

测试直接 import 脚本模块复用其纯函数，不启动真实 pyright 进程（只 monkeypatch
`subprocess.run` / `shutil.which`），保证离线、确定性。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.test._script_loader import load_script

SCRIPTS_DIR = Path(__file__).resolve().parents[4] / "scripts"
# 磁盘脚本名为 check-types.py（连字符不可 import）：按项目惯例经共享装载器载入模块
check_types = load_script("check-types.py")

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


def _diag(
    severity: str = "error", line: int = 0, character: int = 0, rule: str = "reportArgumentType", message: str = "bad"
):
    return {
        "file": str(SCRIPTS_DIR.parent / "src" / "python" / "demo.py"),
        "severity": severity,
        "rule": rule,
        "message": message,
        "range": {"start": {"line": line, "character": character}},
    }


class TestPyrightCommand:
    """解析器定位策略。"""

    def test_prefers_path_binary(self):
        """PATH 上有 pyright 时直接用它（不额外拼 npx）。"""
        with patch.object(
            check_types.shutil, "which", side_effect=lambda name: "/usr/bin/pyright" if name == "pyright" else None
        ):
            assert check_types.pyright_command() == ["/usr/bin/pyright"]

    def test_prefers_venv_binary_over_npx(self):
        """PATH 没有、但虚拟环境里装了 pyright 时用 venv 那份（钩子场景通常未激活 venv）。"""
        with patch.object(check_types.shutil, "which", return_value=None):
            with patch.object(check_types, "venv_pyright_path", return_value=Path("/repo/.venv/bin/pyright")):
                assert check_types.pyright_command() == ["/repo/.venv/bin/pyright"]

    def test_falls_back_to_npx(self):
        """PATH 与 venv 都没有、但 npx 可用时走 `npx --no-install pyright`（不联网安装）。"""
        with patch.object(
            check_types.shutil, "which", side_effect=lambda name: "/usr/bin/npx" if name == "npx" else None
        ):
            with patch.object(check_types, "venv_pyright_path", return_value=None):
                assert check_types.pyright_command() == ["/usr/bin/npx", "--no-install", "pyright"]

    def test_missing_returns_none(self):
        """三处皆无 → None（调用方按环境缺失退出 1）。"""
        with patch.object(check_types.shutil, "which", return_value=None):
            with patch.object(check_types, "venv_pyright_path", return_value=None):
                assert check_types.pyright_command() is None


class TestCollectFindings:
    """报告 → finding 行。"""

    def test_only_errors_reported(self):
        """WARNING/INFORMATION 不算 finding（守护只看 ERROR）。"""
        report = {
            "generalDiagnostics": [
                _diag("error", line=4, character=2),
                _diag("warning", line=1),
                _diag("information", line=2),
            ]
        }
        findings = check_types.collect_findings(report)
        assert len(findings) == 1
        assert "src/python/demo.py:5:3 reportArgumentType: bad" in findings[0]

    def test_sorted_by_file_and_position(self):
        """多条 finding 按 文件:行:列 升序（输出稳定，CI diff 可读）。"""
        report = {"generalDiagnostics": [_diag(line=9, character=9), _diag(line=1, character=1)]}
        findings = check_types.collect_findings(report)
        assert [line.split(" ")[0] for line in findings] == ["src/python/demo.py:2:2", "src/python/demo.py:10:10"]

    def test_message_first_line_only(self):
        """pyright 的多行 message 只取首行（一行一条 finding）。"""
        report = {"generalDiagnostics": [_diag(message="第一行说明\n第二行细节")]}
        assert "第一行说明" in check_types.collect_findings(report)[0]
        assert "第二行细节" not in check_types.collect_findings(report)[0]


class TestRunPyright:
    """子进程调用与 JSON 解析。"""

    def test_parses_json_stdout(self):
        """正常输出：返回解析后的报告（pyright 有 error 时退出码非 0 也算成功取到报告）。"""
        fake = type("R", (), {"stdout": '{"generalDiagnostics": [], "summary": {"errorCount": 0}}'})()
        with patch.object(check_types.subprocess, "run", return_value=fake) as run:
            result = check_types.run_pyright(["pyright"], ["src/python"])
        assert result == {"generalDiagnostics": [], "summary": {"errorCount": 0}}
        assert run.call_args.args[0] == ["pyright", "--outputjson", "src/python"]

    def test_empty_stdout_returns_none(self):
        """无输出（参数错误等）→ None，由 main 按调用失败处理。"""
        fake = type("R", (), {"stdout": ""})()
        with patch.object(check_types.subprocess, "run", return_value=fake):
            assert check_types.run_pyright(["pyright"], ["src/python"]) is None

    def test_non_json_stdout_returns_none(self):
        """非 JSON 输出 → None（不让解析异常冒成堆栈）。"""
        fake = type("R", (), {"stdout": "not json"})()
        with patch.object(check_types.subprocess, "run", return_value=fake):
            assert check_types.run_pyright(["pyright"], ["src/python"]) is None


class TestMainContract:
    """退出码契约（0 通过 / 1 环境缺失 / 2 有 finding）。"""

    def test_missing_pyright_exits_one(self, capsys):
        """解析器不可用 → 1，且提示如何安装。"""
        with patch.object(check_types, "pyright_command", return_value=None):
            assert check_types.main(["--ci"]) == 1
        assert "pyright" in capsys.readouterr().err

    def test_clean_report_exits_zero(self):
        """无 ERROR 级诊断 → 0。"""
        with patch.object(check_types, "pyright_command", return_value=["pyright"]):
            with patch.object(check_types, "run_pyright", return_value={"generalDiagnostics": []}):
                assert check_types.main(["--ci"]) == 0

    def test_findings_exit_two(self, capsys):
        """有 ERROR 级诊断 → 2，并逐条打印 文件:行:列。"""
        report = {"generalDiagnostics": [_diag(line=0, character=0)]}
        with patch.object(check_types, "pyright_command", return_value=["pyright"]):
            with patch.object(check_types, "run_pyright", return_value=report):
                assert check_types.main(["--ci"]) == 2
        assert "src/python/demo.py:1:1" in capsys.readouterr().out

    def test_unusable_report_exits_one(self, capsys):
        """报告拿不到（None）→ 1，与解析器缺失同口径（不静默放过）。"""
        with patch.object(check_types, "pyright_command", return_value=["pyright"]):
            with patch.object(check_types, "run_pyright", return_value=None):
                assert check_types.main(["--ci"]) == 1
        assert "JSON" in capsys.readouterr().err

    def test_truncates_long_finding_lists(self, capsys):
        """finding 超过上限时截断并补一行总数提示（CI 日志友好）。"""
        report = {"generalDiagnostics": [_diag(line=i) for i in range(check_types.MAX_REPORTED + 5)]}
        with patch.object(check_types, "pyright_command", return_value=["pyright"]):
            with patch.object(check_types, "run_pyright", return_value=report):
                assert check_types.main(["--ci"]) == 2
        assert "其余 5 条已省略" in capsys.readouterr().out
