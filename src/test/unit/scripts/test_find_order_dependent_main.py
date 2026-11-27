"""`scripts/test-find-order-dependent.py` 定位主流程覆盖（打桩 pytest 子进程）。

该工具每次判定都对应一次真实 pytest 往返，编排错了的代价是「白跑十几分钟却给出
假污染源」。因此这里把 `subprocess.run` 换成脚本化应答，断言的是**调度行为**：
单跑门 → 收集 → 复现门 → 二分收敛到最小前缀 → 单文件配对/精简，以及输出里的
污染源与最小复现命令。全程无真实子进程。
"""

from __future__ import annotations

import runpy
import subprocess
import sys
from types import SimpleNamespace

import pytest
from src.test._script_loader import SCRIPTS_DIR, load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_SCRIPT = "test-find-order-dependent.py"
_TARGET = "src/test/a/test_target.py::test_t"
_FILES = [
    "src/test/a/test_1.py",
    "src/test/a/test_2.py",
    "src/test/a/test_3.py",
]


def _collect_output(files: list[str], target_file: str) -> str:
    """构造 `--collect-only -q` 的节点行输出（含目标文件在末位）。"""
    lines = [f"{path}::test_case" for path in files]
    lines.append(f"{target_file}::test_t")
    return "\n".join(lines) + "\n"


class _FakePytest:
    """按命令行脚本化应答 `subprocess.run` 的打桩器，并记录每次调用。"""

    def __init__(self, nodes: str, plan):
        self.nodes = nodes
        self.plan = plan
        self.commands: list[list[str]] = []

    def run(self, cmd, **kwargs):
        self.commands.append(list(cmd))
        if "--collect-only" in cmd:
            return subprocess.CompletedProcess(cmd, 0, self.nodes, "")
        code, out = self.plan([c for c in cmd if c.endswith("::test_t") or c.endswith(".py")])
        return subprocess.CompletedProcess(cmd, code, out, "")

    def pytest_calls(self) -> list[list[str]]:
        """仅取真正跑用例的调用（排除收集），节点名列表。"""
        return [
            [c for c in cmd if c.endswith(".py") or "::" in c] for cmd in self.commands if "--collect-only" not in cmd
        ]


def _install(monkeypatch, mod, fake: _FakePytest) -> None:
    monkeypatch.setattr(mod, "subprocess", SimpleNamespace(run=fake.run, TimeoutExpired=subprocess.TimeoutExpired))


def _fail_line(node: str = _TARGET) -> str:
    return f"FAILED {node} - AssertionError\n1 failed"


@pytest.fixture(scope="module")
def order_script():
    return load_script(_SCRIPT, module_name="test_find_order_dependent_main")


class TestClassifyOutput:
    """返回码与摘要行判定：只有「目标确实在 FAILED 列表里」才算命中。"""

    def test_old_style_summary_line_is_recognised(self, order_script):
        """极旧格式 `path::test FAILED [xx%]` 走 findall 兜底分支。"""
        out = "src/test/a/test_target.py::test_t FAILED [ 50%]\n"
        assert order_script.classify_output(1, out, _TARGET) is order_script.Outcome.TARGET_FAILED

    def test_failure_without_summary_lines_is_execution_error(self, order_script):
        """返回码 1 却拿不到任何 FAILED 行 → 视为执行错误（不是「目标失败」）。"""
        assert order_script.classify_output(1, "collected 1 item\n", _TARGET) is order_script.Outcome.ERROR

    def test_other_failure_is_distinguished_from_target_failure(self, order_script):
        out = _fail_line("src/test/a/test_other.py::test_x")
        assert order_script.classify_output(1, out, _TARGET) is order_script.Outcome.OTHER_FAILURE

    def test_zero_returncode_is_target_passed(self, order_script):
        assert order_script.classify_output(0, "", _TARGET) is order_script.Outcome.TARGET_PASSED


class TestRunPytestCase:
    """单次运行：超时视为执行错误（不静默当成通过或目标失败）。"""

    def test_timeout_maps_to_error(self, order_script, monkeypatch):
        def boom(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 1))

        monkeypatch.setattr(
            order_script, "subprocess", SimpleNamespace(run=boom, TimeoutExpired=subprocess.TimeoutExpired)
        )
        assert order_script.run_pytest_case([_TARGET], _TARGET) is order_script.Outcome.ERROR

    def test_command_carries_node_order_and_quiet_flags(self, order_script, monkeypatch):
        fake = _FakePytest("", lambda nodes: (0, ""))
        _install(monkeypatch, order_script, fake)
        order_script.run_pytest_case([_FILES[0], _TARGET], _TARGET)
        cmd = fake.commands[0]
        assert cmd[1:3] == ["-m", "pytest"]
        assert cmd.index(_FILES[0]) < cmd.index(_TARGET)
        assert "-p" in cmd and "no:cacheprovider" in cmd


class TestMainLocate:
    """端到端：定位到单文件污染源，二分不白跑（不重复探测已排除的文件）。"""

    def test_single_file_leak_is_reported_as_culprit(self, order_script, monkeypatch, capsys):
        # 仅当 test_2.py 与目标同跑时目标失败
        fake = _FakePytest(
            _collect_output(_FILES, "src/test/a/test_target.py"),
            lambda nodes: (1, _fail_line()) if any("test_2.py" in n for n in nodes) and len(nodes) > 1 else (0, ""),
        )
        _install(monkeypatch, order_script, fake)

        rc = order_script.main([_TARGET])

        out = capsys.readouterr().out
        assert rc == 0
        assert "[OK] 污染源已定位" in out
        assert "- src/test/a/test_2.py" in out
        assert "最小复现：" in out
        # 二分收窄：排在污染源之后的文件只出现在「全量候选」运行里，不再参与局部探测
        calls = fake.pytest_calls()
        with_third = [call for call in calls if _FILES[2] in call]
        assert with_third, "复现门与二分起点的全量运行必需探测过后置文件"
        assert all(len([n for n in call if n in _FILES]) == len(_FILES) for call in with_third)
        assert any(len([n for n in call if n in _FILES]) < len(_FILES) for call in calls)

    def test_minimal_prefix_length_is_reported(self, order_script, monkeypatch, capsys):
        fake = _FakePytest(
            _collect_output(_FILES, "src/test/a/test_target.py"),
            lambda nodes: (1, _fail_line()) if any("test_2.py" in n for n in nodes) and len(nodes) > 1 else (0, ""),
        )
        _install(monkeypatch, order_script, fake)

        order_script.main([_TARGET])

        assert "最小失败前缀长度 K=2" in capsys.readouterr().out

    def test_pairing_failure_falls_back_to_subset_minimisation(self, order_script, monkeypatch, capsys):
        """污染源需两文件合跑才复现（单文件配对不成立）→ 精简集合仍须给出两者。"""

        def plan(nodes):
            has_1 = any("test_1.py" in n for n in nodes)
            has_3 = any("test_3.py" in n for n in nodes)
            if has_1 and has_3 and _TARGET in nodes:
                return 1, _fail_line()
            return 0, ""

        fake = _FakePytest(_collect_output(_FILES, "src/test/a/test_target.py"), plan)
        _install(monkeypatch, order_script, fake)

        rc = order_script.main([_TARGET])

        out = capsys.readouterr().out
        assert rc == 0
        assert "- src/test/a/test_1.py" in out
        assert "- src/test/a/test_3.py" in out
        # 与复现无关的 test_2.py 被精简掉
        assert "- src/test/a/test_2.py" not in out

    def test_dry_run_stops_before_bisection(self, order_script, monkeypatch, capsys):
        fake = _FakePytest(_collect_output(_FILES, "src/test/a/test_target.py"), lambda nodes: (0, ""))
        _install(monkeypatch, order_script, fake)

        rc = order_script.main([_TARGET, "--dry-run"])

        out = capsys.readouterr().out
        assert rc == 0
        assert "[OK] dry-run 结束（未执行二分）" in out
        assert "候选前置文件：3 个" in out
        assert len(fake.pytest_calls()) == 1  # 只有单跑确认

    def test_candidates_option_narrows_prefix(self, order_script, monkeypatch, capsys):
        fake = _FakePytest(
            _collect_output(_FILES, "src/test/a/test_target.py"),
            lambda nodes: (1, _fail_line()) if any("test_2.py" in n for n in nodes) and len(nodes) > 1 else (0, ""),
        )
        _install(monkeypatch, order_script, fake)

        rc = order_script.main([_TARGET, "--candidates", f"{_FILES[0]},{_FILES[1]}"])

        out = capsys.readouterr().out
        assert rc == 0
        assert "候选前置文件：2 个" in out
        assert "- src/test/a/test_2.py" in out


class TestMainArgvDefault:
    """`main()` 无实参时从 `sys.argv` 取目标（脚本入口路径）。"""

    def test_reads_target_from_argv(self, order_script, monkeypatch, capsys):
        fake = _FakePytest(_collect_output(_FILES, "src/test/a/test_target.py"), lambda nodes: (0, ""))
        _install(monkeypatch, order_script, fake)
        monkeypatch.setattr(sys, "argv", [_SCRIPT, _TARGET, "--dry-run"])

        assert order_script.main() == 0
        assert f"目标用例：{_TARGET}" in capsys.readouterr().out


_TARGET_FILE = "src/test/a/test_target.py"


def _install_runner(monkeypatch, mod, run) -> None:
    """只替换 `subprocess.run`（用于收集失败/自定义应答，`_FakePytest` 覆盖不到的形态）。"""
    monkeypatch.setattr(mod, "subprocess", SimpleNamespace(run=run, TimeoutExpired=subprocess.TimeoutExpired))


class TestMainGates:
    """入口各道门的拒绝路径：单跑门 → 收集 → 目标在列 → 候选 → 复现门 → 二分/精简预算。"""

    def test_single_run_target_failure_exits_one(self, order_script, monkeypatch, capsys):
        fake = _FakePytest(_collect_output(_FILES, _TARGET_FILE), lambda nodes: (1, _fail_line()))
        _install(monkeypatch, order_script, fake)

        assert order_script.main([_TARGET]) == 1
        out = capsys.readouterr().out
        assert "不是顺序依赖问题" in out
        assert fake.commands and all("--collect-only" not in cmd for cmd in fake.commands), "单跑门即判死，不必收集"

    def test_single_run_unrelated_failure_exits_two(self, order_script, monkeypatch, capsys):
        fake = _FakePytest(
            _collect_output(_FILES, _TARGET_FILE),
            lambda nodes: (1, "FAILED src/test/a/test_1.py::test_x - boom\n1 failed"),
        )
        _install(monkeypatch, order_script, fake)

        assert order_script.main([_TARGET]) == 2
        assert "[ERR] 单跑出现无关失败或执行错误" in capsys.readouterr().out

    @pytest.mark.parametrize(("code", "nodes"), [(1, ""), (0, "")])
    def test_collection_failure_or_empty_exits_two(self, order_script, monkeypatch, capsys, code, nodes):
        def _run(cmd, **_kwargs):
            if "--collect-only" in cmd:
                return subprocess.CompletedProcess(cmd, code, nodes, "collect error")
            return subprocess.CompletedProcess(cmd, 0, "1 passed", "")

        _install_runner(monkeypatch, order_script, _run)
        assert order_script.main([_TARGET]) == 2
        assert "收集失败" in capsys.readouterr().out

    def test_target_file_absent_from_collection_exits_two(self, order_script, monkeypatch, capsys):
        fake = _FakePytest(_collect_output(_FILES, "src/test/other/test_elsewhere.py"), lambda nodes: (0, ""))
        _install(monkeypatch, order_script, fake)

        assert order_script.main([_TARGET]) == 2
        assert "目标文件不在收集结果中" in capsys.readouterr().out

    def test_unknown_candidates_rejected(self, order_script, monkeypatch, capsys):
        fake = _FakePytest(_collect_output(_FILES, _TARGET_FILE), lambda nodes: (0, ""))
        _install(monkeypatch, order_script, fake)

        assert order_script.main([_TARGET, "--candidates", "src/test/a/test_9.py"]) == 2
        assert "候选文件不在收集结果中" in capsys.readouterr().out

    def test_no_candidate_before_target_exits_two(self, order_script, monkeypatch, capsys):
        fake = _FakePytest(_collect_output([], _TARGET_FILE), lambda nodes: (0, ""))
        _install(monkeypatch, order_script, fake)

        assert order_script.main([_TARGET]) == 2
        assert "目标前无候选文件" in capsys.readouterr().out

    def test_reproduction_gate_failure_exits_two(self, order_script, monkeypatch, capsys):
        fake = _FakePytest(_collect_output(_FILES, _TARGET_FILE), lambda nodes: (0, "1 passed"))
        _install(monkeypatch, order_script, fake)

        assert order_script.main([_TARGET]) == 2
        assert "无法复现" in capsys.readouterr().out

    def test_run_budget_exhausted_before_minimisation_exits_two(self, order_script, monkeypatch, capsys):
        """配对不成立要转精简时，剩余预算已耗尽须报上限而不是继续跑。"""

        def plan(nodes):
            files = [n for n in nodes if n.endswith(".py")]
            return (1, _fail_line()) if len(files) >= 2 and _TARGET in nodes else (0, "")

        fake = _FakePytest(_collect_output(_FILES, _TARGET_FILE), plan)
        _install(monkeypatch, order_script, fake)

        assert order_script.main([_TARGET, "--max-runs", "6"]) == 2
        assert "无法进一步精简" in capsys.readouterr().out

    def test_run_budget_reached_right_after_reproduction_gate(self, order_script, monkeypatch, capsys):
        fake = _FakePytest(
            _collect_output(_FILES, _TARGET_FILE),
            lambda nodes: (1, _fail_line()) if len(nodes) > 1 else (0, "1 passed"),
        )
        _install(monkeypatch, order_script, fake)

        assert order_script.main([_TARGET, "--max-runs", "2"]) == 2
        assert "已达运行上限" in capsys.readouterr().out

    def test_bisection_budget_exhaustion_reports_non_convergence(self, order_script, monkeypatch, capsys):
        wide = [f"src/test/a/test_{i}.py" for i in range(1, 6)]

        def plan(nodes):
            files = [n for n in nodes if n.endswith(".py")]
            return (1, _fail_line()) if len(files) >= 4 and _TARGET in nodes else (0, "")

        fake = _FakePytest(_collect_output(wide, _TARGET_FILE), plan)
        _install(monkeypatch, order_script, fake)

        assert order_script.main([_TARGET, "--max-runs", "3"]) == 2
        out = capsys.readouterr().out
        assert "二分未收敛" in out
        assert len(fake.pytest_calls()) <= 5, "预算见底后不得继续投喂子进程"

    def test_minimised_subset_not_reproducible_exits_two(self, order_script, monkeypatch, capsys):
        def plan(nodes):
            files = [n for n in nodes if n.endswith(".py")]
            return (1, _fail_line()) if len(files) >= 2 and _TARGET in nodes else (0, "")

        fake = _FakePytest(_collect_output(_FILES, _TARGET_FILE), plan)
        _install(monkeypatch, order_script, fake)
        monkeypatch.setattr(order_script, "minimize_subset", lambda prefix, fails, budget=40: ["src/test/a/ghost.py"])

        assert order_script.main([_TARGET]) == 2
        assert "精简集合无法复现" in capsys.readouterr().out


class TestMainGuard:
    """`if __name__ == "__main__"` 入口：缺目标参数即按 argparse 契约退出 2（不起子进程）。"""

    def test_main_guard_exits_two_without_target(self, monkeypatch):
        if str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))
        monkeypatch.setattr(sys, "argv", [_SCRIPT])
        with pytest.raises(SystemExit) as excinfo:
            runpy.run_path(str(SCRIPTS_DIR / _SCRIPT), run_name="__main__")
        assert excinfo.value.code == 2
