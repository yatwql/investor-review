"""eval-factor-zoo.py 的 CLI 入口：阶段分发与产物目录准备。

覆盖 `main()` 的单阶段分发（含 `--refresh-pool` 透传）、`all` 的执行顺序，
以及「仓库根 / scripts 不在 sys.path 时自助补路径」的导入期分支。
"""

from __future__ import annotations

import sys

import pytest
from src.test._script_loader import SCRIPTS_DIR, load_module_file, load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="zoo")
def fixture_zoo():
    return load_script("eval-factor-zoo.py")


def _record_calls(mod, monkeypatch) -> list[tuple[str, object]]:
    """把五个 stage 函数换成只记录调用的桩。"""
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(mod, "stage_catalog", lambda out_dir: calls.append(("catalog", out_dir)))
    monkeypatch.setattr(
        mod,
        "stage_fields",
        lambda out_dir, refresh_pool=False: calls.append(("fields", refresh_pool)),
    )
    monkeypatch.setattr(mod, "stage_signals", lambda out_dir: calls.append(("signals", out_dir)))
    monkeypatch.setattr(mod, "stage_timing", lambda out_dir: calls.append(("timing", out_dir)))
    monkeypatch.setattr(mod, "stage_verdict", lambda out_dir: calls.append(("verdict", out_dir)))
    return calls


class TestStageDispatch:
    @pytest.mark.parametrize("stage", ["catalog", "signals", "timing", "verdict"])
    def test_single_stage_runs_only_itself(self, zoo, monkeypatch, tmp_path, stage):
        calls = _record_calls(zoo, monkeypatch)
        assert zoo.main([stage, "--out-dir", str(tmp_path)]) == 0
        assert [name for name, _ in calls] == [stage]

    def test_fields_forwards_refresh_pool(self, zoo, monkeypatch, tmp_path):
        calls = _record_calls(zoo, monkeypatch)
        assert zoo.main(["fields", "--out-dir", str(tmp_path), "--refresh-pool"]) == 0
        assert calls == [("fields", True)]

    def test_fields_defaults_to_frozen_pool(self, zoo, monkeypatch, tmp_path):
        calls = _record_calls(zoo, monkeypatch)
        assert zoo.main(["fields", "--out-dir", str(tmp_path)]) == 0
        assert calls == [("fields", False)]

    def test_all_runs_stages_in_defined_order(self, zoo, monkeypatch, tmp_path):
        calls = _record_calls(zoo, monkeypatch)
        assert zoo.main(["all", "--out-dir", str(tmp_path)]) == 0
        assert [name for name, _ in calls] == ["catalog", "fields", "signals", "timing", "verdict"]

    def test_out_dir_is_created(self, zoo, monkeypatch, tmp_path):
        _record_calls(zoo, monkeypatch)
        out_dir = tmp_path / "nested" / "factor-zoo"
        assert zoo.main(["catalog", "--out-dir", str(out_dir)]) == 0
        assert out_dir.is_dir()

    def test_unknown_stage_exits_two(self, zoo, tmp_path, capsys):
        with pytest.raises(SystemExit) as excinfo:
            zoo.main(["nope", "--out-dir", str(tmp_path)])
        assert excinfo.value.code == 2
        assert "invalid choice" in capsys.readouterr().err


class TestSelfPathBootstrap:
    def test_missing_entries_are_prepended(self, monkeypatch):
        """仓库根与 scripts 都不在 sys.path 时，导入期会自行补上。"""
        scripts_dir = SCRIPTS_DIR
        root, scripts = str(scripts_dir.parent), str(scripts_dir)
        monkeypatch.setattr(sys, "path", [p for p in sys.path if p not in (root, scripts)])
        load_module_file(scripts_dir / "eval-factor-zoo.py", "eval_factor_zoo_bootstrap_probe")
        assert sys.path[0] == scripts
        assert sys.path[1] == root
