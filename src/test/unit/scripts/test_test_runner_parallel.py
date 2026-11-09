"""测试：test-runner 并行级别解析与 worker 数计算。

回归背景：`--parallel` 的 worker 数 = 核数 × 档位系数，缺省档（medium，50%）不设上限——
16 核上开到 8 worker 最优，开到 16 反而慢约 17%（xdist 进程争抢 + 磁盘/杀软扫描）；
32 核机器则会按 16 worker 起跑。故本文件锁住两条契约：

  - **medium 封顶 8**（多核机器不再无上限放大），`--parallel high` 仍按 100% 核数（显式要求尊重）；
  - **级别来源优先级**：CLI `--parallel` > 环境变量 `TEST_RUNNER_PARALLEL` > 缺省 medium，
    非法环境值按 medium 处理（不让拼错的变量静默改变并发度）。
"""

from __future__ import annotations

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

runner = load_script("test-runner.py", module_name="test_runner_parallel_probe")
pytest_env = runner  # 入口 re-export 了并行解析与 worker 计算（同一实现，避免二次加载分叉）


def _with_cores(monkeypatch, cores: int) -> None:
    monkeypatch.setattr(pytest_env.os, "cpu_count", lambda: cores)


class TestResolveParallelLevel:
    """级别来源优先级：CLI > 环境变量 > 缺省。"""

    def test_cli_wins_over_env(self, monkeypatch):
        """显式 `--parallel` 覆盖环境变量。"""
        monkeypatch.setenv(pytest_env.PARALLEL_ENV, "low")
        assert pytest_env.resolve_parallel_level("high") == "high"

    def test_env_used_when_cli_absent(self, monkeypatch):
        """无 CLI 参数时取环境变量（便于在慢机器上一次性固定）。"""
        monkeypatch.setenv(pytest_env.PARALLEL_ENV, "high")
        assert pytest_env.resolve_parallel_level(None) == "high"

    def test_env_is_case_insensitive_and_trimmed(self, monkeypatch):
        """环境变量大小写与空白不敏感。"""
        monkeypatch.setenv(pytest_env.PARALLEL_ENV, "  LOW ")
        assert pytest_env.resolve_parallel_level(None) == "low"

    def test_invalid_env_falls_back_to_medium(self, monkeypatch):
        """拼错的环境值按 medium 处理（不静默改变并发度）。"""
        monkeypatch.setenv(pytest_env.PARALLEL_ENV, "turbo")
        assert pytest_env.resolve_parallel_level(None) == "medium"

    def test_default_is_medium(self, monkeypatch):
        """两者都缺省 → medium。"""
        monkeypatch.delenv(pytest_env.PARALLEL_ENV, raising=False)
        assert pytest_env.resolve_parallel_level(None) == "medium"


class TestPerTestTimeout:
    """单用例超时看门狗：设了环境变量才启用（默认不启用，避免慢机器误杀）。"""

    _CFG = {"marker": "unit", "parallel": False, "timeout_sec": 60}

    def _args(self, monkeypatch, value: str | None) -> list[str]:
        if value is None:
            monkeypatch.delenv(pytest_env.PER_TEST_TIMEOUT_ENV, raising=False)
        else:
            monkeypatch.setenv(pytest_env.PER_TEST_TIMEOUT_ENV, value)
        return pytest_env._build_pytest_args(self._CFG, "unit", False, False, None)

    def test_disabled_by_default(self, monkeypatch):
        """未设环境变量 → 不加 `--timeout`（慢机器上不应被默认看门狗误杀）。"""
        args = self._args(monkeypatch, None)
        assert not any(a.startswith("--timeout") for a in args)

    def test_enabled_by_env(self, monkeypatch):
        """设了环境变量 → 加 `--timeout=<秒>` 与 thread 方法（超时即失败并带堆栈）。"""
        pytest.importorskip("pytest_timeout", reason="需安装 pytest-timeout 才启用看门狗")
        args = self._args(monkeypatch, "120")
        assert "--timeout=120" in args
        assert "--timeout-method=thread" in args

    def test_missing_plugin_is_ignored_with_warning(self, monkeypatch, capsys):
        """装了没装插件两种情况：缺插件时不传 `--timeout`（否则 pytest 用法错误秒退 0/0），只告警。"""
        monkeypatch.setenv(pytest_env.PER_TEST_TIMEOUT_ENV, "120")
        # 补丁打到「实际执行 _build_pytest_args 的模块命名空间」（经脚本加载器重命名后不是同一对象）
        monkeypatch.setitem(pytest_env._build_pytest_args.__globals__, "_check_pytest_timeout", lambda: False)

        args = pytest_env._build_pytest_args(self._CFG, "unit", False, False, None)

        assert not any(a.startswith("--timeout") for a in args)
        out = capsys.readouterr().out
        assert "已忽略" in out and "pytest-timeout" in out

    def test_blank_value_ignored(self, monkeypatch):
        """空白值视为未启用（不产生 `--timeout=` 空参）。"""
        args = self._args(monkeypatch, "   ")
        assert not any(a.startswith("--timeout") for a in args)


class TestPytestExitCodeHints:
    """pytest 非测试失败退出码的提示（避免只看到「0 passed, 0 failed（0.0s）」）。"""

    @staticmethod
    def _run(monkeypatch, capsys, returncode: int, stdout: str = "") -> str:
        runner = load_script("_test_runner/runner.py", module_name=f"test_runner_exit_hint_{returncode}")
        fake = type("P", (), {"returncode": returncode, "stdout": stdout, "stderr": ""})()
        monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: fake)
        monkeypatch.setattr(runner, "html_available", lambda: False, raising=False)
        runner.run_mode("scenario", coverage=False)
        return capsys.readouterr().out

    def test_usage_error_explains_missing_plugin(self, monkeypatch, capsys):
        """退出码 4（用法错误）→ 明确提示可能缺插件/环境变量残留，并回放输出尾部。"""
        out = self._run(monkeypatch, capsys, 4, "pytest: error: unrecognized arguments: --timeout=120")
        assert "退出码 4" in out
        assert "pytest-timeout" in out
        assert "unrecognized arguments" in out

    def test_no_tests_collected_explains_marker(self, monkeypatch, capsys):
        """退出码 5（未收集到用例）→ 提示 marker 与测试树不匹配。"""
        out = self._run(monkeypatch, capsys, 5, "no tests ran in 0.01s")
        assert "退出码 5" in out
        assert "未收集到用例" in out


class TestWorkerCount:
    """worker 数 = 核数 × 系数，medium 封顶 8。"""

    def test_medium_is_half_cores_below_cap(self, monkeypatch):
        """小幅核数：medium = 50% 核数（8 核 → 4）。"""
        _with_cores(monkeypatch, 8)
        assert pytest_env._calc_parallel_workers("medium") == "4"

    def test_medium_is_capped_for_many_cores(self, monkeypatch):
        """多核机器：medium 封顶 8（32 核仍 8，避免超订反而变慢）。"""
        _with_cores(monkeypatch, 32)
        assert pytest_env._calc_parallel_workers("medium") == "8"

    def test_high_keeps_full_cores(self, monkeypatch):
        """`--parallel high` 仍按 100% 核数（显式要求尊重，不套 medium 的上限）。"""
        _with_cores(monkeypatch, 32)
        assert pytest_env._calc_parallel_workers("high") == "32"

    def test_low_has_floor_of_two(self, monkeypatch):
        """低配机器：low 至少 2 worker（4 核 → 2）。"""
        _with_cores(monkeypatch, 4)
        assert pytest_env._calc_parallel_workers("low") == "2"
