"""`_test_runner/pytest_env.py` 的命令拼装分支（并行降级 / 单用例超时 / 覆盖率开关）。

契约：缺插件时**不传**该插件专属参数（否则 pytest 以用法错误秒退，把整档跑丢），
而是打印降级提示；xdist 可用时按档位拼 `-n` 并在非 high 档给出提级提示。
"""

from __future__ import annotations

import pytest

from src.test._script_loader import SCRIPTS_DIR, load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="mod")
def fixture_mod(monkeypatch, tmp_path):
    """加载 `_test_runner/pytest_env.py`，并把报告目录常量重定向到临时路径。"""
    # 子包以平铺名互相导入（`from _test_runner.paths import …`），故先补 scripts/ 导入面
    monkeypatch.syspath_prepend(str(SCRIPTS_DIR))
    module = load_script("_test_runner/pytest_env.py", module_name="_test_runner_pytest_env_under_test")
    monkeypatch.setattr(module, "_LATEST_DIR", str(tmp_path / "latest"))
    return module


class TestPluginDetection:
    """插件探测经 `find_spec` 的唯一入口，故可整体打桩。"""

    def test_xdist_detection_delegates_to_find_spec(self, mod, monkeypatch):
        seen: list[str] = []
        monkeypatch.setattr(mod, "_has_plugin", lambda name: seen.append(name) or True)
        assert mod._check_xdist() is True
        assert seen == ["xdist"]


class TestParallelArgs:
    """`-n` 参数与降级提示。"""

    def test_adds_worker_count_and_hint_for_medium(self, mod, monkeypatch, capsys):
        monkeypatch.setattr(mod, "_check_xdist", lambda: True)
        monkeypatch.setattr(mod.os, "cpu_count", lambda: 16)
        args = mod._build_pytest_args({"marker": "", "parallel": True}, "unit", False, False)
        assert "-n" in args
        assert args[args.index("-n") + 1] == "8"
        assert "--parallel high" in capsys.readouterr().out

    def test_high_level_prints_no_hint(self, mod, monkeypatch, capsys):
        monkeypatch.setattr(mod, "_check_xdist", lambda: True)
        monkeypatch.setattr(mod.os, "cpu_count", lambda: 4)
        mod._build_pytest_args({"marker": "", "parallel": True}, "unit", False, False, parallel_level="high")
        assert "--parallel high" not in capsys.readouterr().out

    def test_missing_xdist_degrades_to_serial(self, mod, monkeypatch, capsys):
        monkeypatch.setattr(mod, "_check_xdist", lambda: False)
        args = mod._build_pytest_args({"marker": "", "parallel": True}, "unit", False, False)
        assert "-n" not in args
        assert "降级单线程" in capsys.readouterr().out


class TestTimeoutWatchdog:
    """`TEST_RUNNER_PER_TEST_TIMEOUT` 只在插件就位时生效。"""

    def test_adds_timeout_when_plugin_present(self, mod, monkeypatch):
        monkeypatch.setenv(mod.PER_TEST_TIMEOUT_ENV, "120")
        monkeypatch.setattr(mod, "_check_pytest_timeout", lambda: True)
        args = mod._build_pytest_args({"marker": ""}, "unit", False, False)
        assert "--timeout=120" in args
        assert "--timeout-method=thread" in args

    def test_ignores_timeout_without_plugin(self, mod, monkeypatch, capsys):
        monkeypatch.setenv(mod.PER_TEST_TIMEOUT_ENV, "120")
        monkeypatch.setattr(mod, "_check_pytest_timeout", lambda: False)
        args = mod._build_pytest_args({"marker": ""}, "unit", False, False)
        assert not any(arg.startswith("--timeout") for arg in args)
        assert "未安装 pytest-timeout" in capsys.readouterr().out


class TestCoverageArgs:
    """覆盖率参数：插件缺失时跳过并提示，不改变其余参数。"""

    def test_coverage_args_when_plugin_present(self, mod, monkeypatch):
        monkeypatch.setattr(mod, "_check_pytest_cov", lambda: True)
        args = mod._build_pytest_args({"marker": ""}, "unit", False, True)
        assert any(arg.startswith("--cov=") for arg in args)
        assert "--cov-report=term-missing:skip-covered" in args

    def test_missing_cov_plugin_skips_coverage(self, mod, monkeypatch, capsys):
        monkeypatch.setattr(mod, "_check_pytest_cov", lambda: False)
        args = mod._build_pytest_args({"marker": ""}, "unit", False, True)
        assert not any("--cov" in arg for arg in args)
        assert "pytest-cov 未安装" in capsys.readouterr().out

    def test_phase_tag_gets_its_own_report_file(self, mod):
        args = mod._build_pytest_args({"marker": ""}, "regression", True, False, phase_tag="basic")
        assert any(arg.endswith("regression/report_phase_basic.html") for arg in args)
