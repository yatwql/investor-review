"""`scripts/eval-mutation-score.py` 单测：目标配置、干跑输出、得分解析、阈值三态与输出面。

全部离线：**不跑真实变异、不发起网络、不写 git**——后端可用性探测与 `subprocess.run`
一律由 monkeypatch 换成桩，故 mutmut 未安装的机器上本文件照常全绿。
"""

from __future__ import annotations

import json
import subprocess

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

#: 真实 mutmut 输出片段：进度行每行都是**累计值**（killed / timeout / suspicious / survived / skipped）
MUTMUT_OUTPUT = """⠋ Generating mutants
2/40  🎉 1  ⏰ 0  🤔 0  🙁 1  🔇 0
40/40  🎉 28  ⏰ 1  🤔 0  🙁 3  🔇 0
"""


@pytest.fixture(name="mutation")
def fixture_mutation():
    """加载脚本（每次拿到全新模块实例，补丁不外溢）。"""
    return load_script("eval-mutation-score.py")


def _completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    """构造一个假的后端完成结果（只填解析用得到的字段）。"""
    return subprocess.CompletedProcess(args=["mutmut"], returncode=returncode, stdout=stdout, stderr="")


def _patch_backend(monkeypatch, module, outputs: list[str]) -> list[dict]:
    """把后端调用换成按目标顺序返回固定输出的桩，返回收到的调用参数列表。

    `outputs` 逐个目标切片消费（用尽后重复最后一项），便于构造「部分达标」的混合场景。
    """
    calls: list[dict] = []

    def fake_run(command, **kwargs):
        index = min(len(calls), len(outputs) - 1)
        calls.append({"command": command, **kwargs})
        return _completed(outputs[index])

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module, "backend_available", lambda **_: True)
    return calls


class TestTargetTable:
    """目标与算子配置表本身的约束（不改配置就能自查口径退化）。"""

    def test_target_names_unique(self, mutation):
        names = [target.name for target in mutation.TARGETS]
        assert names
        assert len(names) == len(set(names))

    def test_every_target_path_resolves_to_real_code(self, mutation):
        for target in mutation.TARGETS:
            assert target.paths
            for path in target.paths:
                assert list(mutation.REPO_ROOT.glob(path)), f"目标路径无匹配文件：{path}"

    def test_every_target_declares_subset_of_operators(self, mutation):
        for target in mutation.TARGETS:
            assert target.operators
            assert set(target.operators) <= set(mutation.OPERATORS)


class TestListTargets:
    """`--list-targets` 是纯配置读取，不依赖后端。"""

    def test_prints_every_target_and_operator(self, mutation, capsys):
        assert mutation.main(["--list-targets"]) == 0
        out = capsys.readouterr().out
        for target in mutation.TARGETS:
            assert target.name in out
            for path in target.paths:
                assert path in out
        for operator in mutation.OPERATORS:
            assert operator in out

    def test_json_payload_matches_config(self, mutation, capsys):
        assert mutation.main(["--list-targets", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert [item["name"] for item in payload["targets"]] == [target.name for target in mutation.TARGETS]
        assert [item["paths"] for item in payload["targets"]] == [list(target.paths) for target in mutation.TARGETS]
        assert set(payload["operators"]) == set(mutation.OPERATORS)


class TestDryRun:
    """`--dry` 只打印将要执行的命令，绝不启动后端。"""

    def test_dry_never_calls_subprocess(self, mutation, monkeypatch, capsys):
        def forbidden(*_args, **_kwargs):
            raise AssertionError("--dry 不得执行任何子进程")

        monkeypatch.setattr(mutation.subprocess, "run", forbidden)
        assert mutation.main(["--dry"]) == 0
        assert "干跑" in capsys.readouterr().out

    def test_dry_prints_one_mutmut_command_per_target(self, mutation, capsys):
        assert mutation.main(["--dry"]) == 0
        out = capsys.readouterr().out
        assert out.count("-m mutmut run") == len(mutation.TARGETS)
        for target in mutation.TARGETS:
            assert f"--paths-to-mutate={','.join(target.paths)}" in out
        assert str(mutation.REPO_ROOT) in out

    def test_dry_json_lists_commands(self, mutation, capsys):
        assert mutation.main(["--dry", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert [item["name"] for item in payload["commands"]] == [target.name for target in mutation.TARGETS]
        for item in payload["commands"]:
            assert item["command"][1:4] == ["-m", "mutmut", "run"]
            assert item["command"][-1].startswith("--paths-to-mutate=")
        assert payload["threshold"] == mutation.DEFAULT_THRESHOLD


class TestParseCounts:
    """得分解析：真 mutmut 进度行优先，计数行备用，认不出即无数据。"""

    def test_progress_line_last_snapshot_wins(self, mutation):
        counts = mutation.parse_counts(MUTMUT_OUTPUT)
        assert counts is not None
        assert (counts.killed, counts.survived, counts.timed_out) == (28, 3, 1)
        # 超时不计入分母：28 / (28 + 3)
        assert counts.score == pytest.approx(28 * 100.0 / 31)
        assert counts.evaluated == 31

    def test_labelled_counters_used_as_fallback(self, mutation):
        counts = mutation.parse_counts("存活: 报错\nkilled: 9\nsurvived = 1\n")
        assert counts is not None
        assert (counts.killed, counts.survived) == (9, 1)
        assert counts.score == pytest.approx(90.0)

    def test_output_without_counters_is_none(self, mutation):
        assert mutation.parse_counts("building mutants...\nno counters here\n") is None
        assert mutation.parse_counts("killed: 3\n") is None  # 缺 survived，不猜

    def test_zero_mutants_scores_none_not_zero(self, mutation):
        counts = mutation.MutationCounts(killed=0, survived=0)
        assert counts.evaluated == 0
        assert counts.score is None


class TestEvaluateTarget:
    """后端调用的参数口径与异常收敛（漏 encoding / 漏超时会在此暴露）。"""

    def test_subprocess_receives_text_encoding_timeout_and_cwd(self, mutation, monkeypatch):
        calls = _patch_backend(monkeypatch, mutation, [MUTMUT_OUTPUT])
        mutation.evaluate_target(mutation.TARGETS[0], timeout=42)
        assert len(calls) == 1
        assert calls[0]["text"] is True
        assert calls[0]["encoding"] == "utf-8"
        assert calls[0]["timeout"] == 42
        assert calls[0]["cwd"] == str(mutation.REPO_ROOT)
        assert calls[0]["command"][1:4] == ["-m", "mutmut", "run"]

    def test_timeout_becomes_no_data(self, mutation, monkeypatch):
        def raise_timeout(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd=["mutmut"], timeout=5)

        monkeypatch.setattr(mutation.subprocess, "run", raise_timeout)
        result = mutation.evaluate_target(mutation.TARGETS[0], timeout=5)
        assert result.counts is None
        assert "超时" in result.note

    def test_launch_failure_becomes_no_data(self, mutation, monkeypatch):
        def raise_oserror(*_args, **_kwargs):
            raise OSError("no such executable")

        monkeypatch.setattr(mutation.subprocess, "run", raise_oserror)
        result = mutation.evaluate_target(mutation.TARGETS[0])
        assert result.counts is None
        assert "启动失败" in result.note


class TestThresholdVerdicts:
    """阈值判定三态：达标 0 / 低于阈值 2 / 后端缺失 1。"""

    def test_score_at_threshold_exits_zero(self, mutation, monkeypatch, capsys):
        _patch_backend(monkeypatch, mutation, ["40/40  🎉 9  ⏰ 0  🤔 0  🙁 1  🔇 0\n"])
        assert mutation.main([]) == 0
        out = capsys.readouterr().out
        assert "[OK]" in out
        assert "90.0%" in out
        assert "[ERR]" not in out

    def test_score_below_threshold_exits_two(self, mutation, monkeypatch, capsys):
        _patch_backend(monkeypatch, mutation, ["40/40  🎉 5  ⏰ 0  🤔 0  🙁 5  🔇 0\n"])
        assert mutation.main([]) == 2
        out = capsys.readouterr().out
        assert "[ERR]" in out
        assert "50.0%" in out
        assert "低于阈值 80%" in out

    def test_threshold_override_rescues_low_score(self, mutation, monkeypatch):
        _patch_backend(monkeypatch, mutation, ["40/40  🎉 5  ⏰ 0  🤔 0  🙁 5  🔇 0\n"])
        assert mutation.main(["--threshold", "50"]) == 0

    def test_backend_missing_exits_one_and_prints_install(self, mutation, monkeypatch, capsys):
        def forbidden(*_args, **_kwargs):
            raise AssertionError("后端缺失时不得尝试跑变异")

        monkeypatch.setattr(mutation.subprocess, "run", forbidden)
        monkeypatch.setattr(mutation, "backend_available", lambda **_: False)
        assert mutation.main([]) == 1
        out = capsys.readouterr().out
        assert "pip install mutmut" in out
        assert "[ERR]" in out

    def test_unparsable_output_fails_closed(self, mutation, monkeypatch, capsys):
        _patch_backend(monkeypatch, mutation, ["后端崩了，没有任何计数\n"])
        assert mutation.main([]) == 2
        out = capsys.readouterr().out
        assert "无法解析变异得分" in out


class TestOutputModes:
    """`-v` 逐目标明细 / `--ci` 仅 finding / `--json` 机读。"""

    def test_verbose_prints_every_target_line(self, mutation, monkeypatch, capsys):
        _patch_backend(monkeypatch, mutation, [MUTMUT_OUTPUT])
        assert mutation.main(["-v"]) == 0
        out = capsys.readouterr().out
        for target in mutation.TARGETS:
            assert target.name in out

    def test_ci_prints_only_bare_findings(self, mutation, monkeypatch, capsys):
        passed = "40/40  🎉 9  ⏰ 0  🤔 0  🙁 1  🔇 0\n"
        below = "40/40  🎉 5  ⏰ 0  🤔 0  🙁 5  🔇 0\n"
        _patch_backend(monkeypatch, mutation, [passed, *([below] * len(mutation.TARGETS))])
        assert mutation.main(["--ci"]) == 2
        lines = [line for line in capsys.readouterr().out.splitlines() if line]
        assert len(lines) == len(mutation.TARGETS) - 1  # 只有首个目标达标
        below_prefixes = tuple(f"{target.paths[0]}:" for target in mutation.TARGETS[1:])
        for line in lines:
            assert line.startswith(below_prefixes)  # `文件:描述` 形态，文件即该切片路径
            assert "[ERR]" not in line and "[!]" not in line and "[OK]" not in line

    def test_ci_prints_nothing_when_all_pass(self, mutation, monkeypatch, capsys):
        _patch_backend(monkeypatch, mutation, ["40/40  🎉 9  ⏰ 0  🤔 0  🙁 1  🔇 0\n"])
        assert mutation.main(["--ci"]) == 0
        assert capsys.readouterr().out.strip() == ""

    def test_json_reports_per_target_status_and_overall_score(self, mutation, monkeypatch, capsys):
        passed = "40/40  🎉 9  ⏰ 0  🤔 0  🙁 1  🔇 0\n"
        below = "40/40  🎉 5  ⏰ 0  🤔 0  🙁 5  🔇 0\n"
        _patch_backend(monkeypatch, mutation, [passed, *([below] * len(mutation.TARGETS))])
        assert mutation.main(["--json"]) == 2
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is False
        assert payload["exit_code"] == 2
        assert payload["threshold"] == mutation.DEFAULT_THRESHOLD
        assert [item["name"] for item in payload["targets"]] == [target.name for target in mutation.TARGETS]
        assert payload["targets"][0]["status"] == mutation.STATUS_PASSED
        assert payload["targets"][1]["status"] == mutation.STATUS_BELOW
        # 按变异体加权：9 + 3×5 杀掉 / (10 + 3×10) 计入
        assert payload["score"] == pytest.approx(24 * 100.0 / 40)

    def test_json_status_no_data_for_unparsable_target(self, mutation, monkeypatch, capsys):
        _patch_backend(monkeypatch, mutation, ["garbage\n"])
        assert mutation.main(["--json"]) == 2
        payload = json.loads(capsys.readouterr().out)
        statuses = {item["status"] for item in payload["targets"]}
        assert statuses == {mutation.STATUS_NO_DATA}
        assert payload["score"] is None
