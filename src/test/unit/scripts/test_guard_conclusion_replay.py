"""测试：三新增守护的结论缓存回放接线 — code-traces / requirement-trace / doc-drift。

每个守护验证三件事：① --ci 首跑扫描并写缓存；② 同输入二次运行逐字回放
且不再执行扫描（扫描入口被替换为必炸桩以证明未调用）；③ 输入指纹变化后
失效重扫。结论缓存目录由 conftest `_isolate_sensitive_paths` 经
CHECK_CONCLUSION_CACHE_DIR 重定向到 tmp_path（与真实门禁缓存隔离）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from src.test._script_loader import load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


def _main_ci(mod, monkeypatch, capsys) -> tuple[int, str]:
    """monkeypatch argv 为 --ci 并执行 mod.main()，返回 (退出码, stdout)。"""
    monkeypatch.setattr(sys, "argv", [Path(mod.__file__).name, "--ci"])
    with pytest.raises(SystemExit) as excinfo:
        mod.main()
    out = capsys.readouterr().out
    code = excinfo.value.code
    return int(code) if code is not None else 0, out


class TestCodeTracesConclusionReplay:
    def test_replay_skips_scan_and_keeps_exit_code(self, monkeypatch, capsys, tmp_path):
        mod = load_script("check-code-traces.py")
        calls = {"scan": 0}

        def _scan_once(args):
            calls["scan"] += 1
            print("[OK] 未发现历史变更痕迹，注释干净")
            return 0

        monkeypatch.setattr(mod, "_scan_all", _scan_once)
        rc1, out1 = _main_ci(mod, monkeypatch, capsys)
        assert calls["scan"] == 1 and rc1 == 0

        def _boom(args):
            calls["scan"] += 1
            raise AssertionError("回放路径不应重扫")

        monkeypatch.setattr(mod, "_scan_all", _boom)
        rc2, out2 = _main_ci(mod, monkeypatch, capsys)
        assert rc2 == rc1 and out2 == out1
        assert calls["scan"] == 1

    def test_input_change_invalidates_cache(self, monkeypatch, capsys, tmp_path):
        mod = load_script("check-code-traces.py")
        src = tmp_path / "sample.py"
        src.write_text("# 说明\n", encoding="utf-8")
        monkeypatch.setattr(mod, "_collect_scan_files", lambda: [src])
        calls = {"scan": 0}

        def _scan_ok(args):
            calls["scan"] += 1
            return 0

        monkeypatch.setattr(mod, "_scan_all", _scan_ok)
        _main_ci(mod, monkeypatch, capsys)
        _main_ci(mod, monkeypatch, capsys)
        assert calls["scan"] == 1  # 同输入第二跑回放

        src.write_text("# 说明（改写）\n", encoding="utf-8")
        _main_ci(mod, monkeypatch, capsys)
        assert calls["scan"] == 2  # 输入指纹变化 → 重扫


class TestRequirementTraceConclusionReplay:
    def test_replay_skips_check_and_keeps_exit_code(self, monkeypatch, capsys):
        mod = load_script("check-requirement-trace.py")
        calls = {"check": 0}

        def _findings_once(requirements_text=None, testplan_text=None, *, covered_domains=None):
            calls["check"] += 1
            return ["testplan.md:1: 需求 `X-01` 的载体文件 `src/test/x.py` 不存在于磁盘"]

        monkeypatch.setattr(mod, "check_requirement_trace", _findings_once)
        rc1, out1 = _main_ci(mod, monkeypatch, capsys)
        assert calls["check"] == 1 and rc1 == 2  # 发现类结论分级退出 2

        def _boom(*a, **k):
            calls["check"] += 1
            raise AssertionError("回放路径不应重扫")

        monkeypatch.setattr(mod, "check_requirement_trace", _boom)
        rc2, out2 = _main_ci(mod, monkeypatch, capsys)
        assert rc2 == rc1 == 2 and out2 == out1
        assert calls["check"] == 1

    def test_input_change_invalidates_cache(self, monkeypatch, capsys, tmp_path):
        mod = load_script("check-requirement-trace.py")
        req = tmp_path / "requirements.md"
        plan = tmp_path / "testplan.md"
        req.write_text("R-TEST-01", encoding="utf-8")
        plan.write_text("table", encoding="utf-8")
        monkeypatch.setattr(mod, "_cache_inputs", lambda: [req, plan])
        calls = {"check": 0}

        monkeypatch.setattr(
            mod, "check_requirement_trace", lambda *a, **k: calls.__setitem__("check", calls["check"] + 1) or []
        )
        _main_ci(mod, monkeypatch, capsys)
        _main_ci(mod, monkeypatch, capsys)
        assert calls["check"] == 1

        plan.write_text("table-v2", encoding="utf-8")
        _main_ci(mod, monkeypatch, capsys)
        assert calls["check"] == 2


class TestDocDriftConclusionReplay:
    def test_replay_skips_checks_and_keeps_exit_code(self, monkeypatch, capsys, tmp_path):
        mod = load_script("check-doc-drift.py")
        probe = tmp_path / "probe.md"
        probe.write_text("v1", encoding="utf-8")
        monkeypatch.setattr(mod, "_cache_inputs", lambda: [probe])
        calls = {"run": 0}

        def _run_ok(args):
            calls["run"] += 1
            print("[OK] 文档与实现一致性校验通过")
            return 0

        def _boom(args):
            calls["run"] += 1
            raise AssertionError("回放路径不应重扫")

        monkeypatch.setattr(mod, "_run_checks_phase", _run_ok)
        rc1, out1 = _main_ci(mod, monkeypatch, capsys)
        assert calls["run"] == 1 and rc1 == 0

        monkeypatch.setattr(mod, "_run_checks_phase", _boom)
        rc2, out2 = _main_ci(mod, monkeypatch, capsys)
        assert rc2 == rc1 and out2 == out1
        assert calls["run"] == 1

        probe.write_text("v2", encoding="utf-8")
        monkeypatch.setattr(mod, "_run_checks_phase", _run_ok)  # 失效后重扫回装正常桩
        _main_ci(mod, monkeypatch, capsys)
        assert calls["run"] == 2  # 输入变化失效

    def test_none_inputs_skips_cache_entirely(self, monkeypatch, capsys):
        """非 git 环境（inputs=None）直接全量检查，不读不写缓存。"""
        mod = load_script("check-doc-drift.py")
        monkeypatch.setattr(mod, "_cache_inputs", lambda: None)
        calls = {"run": 0}
        monkeypatch.setattr(mod, "_run_checks_phase", lambda args: calls.__setitem__("run", calls["run"] + 1) or 0)
        rc1, _ = _main_ci(mod, monkeypatch, capsys)
        rc2, _ = _main_ci(mod, monkeypatch, capsys)
        assert rc1 == rc2 == 0
        assert calls["run"] == 2  # 每次都真跑
