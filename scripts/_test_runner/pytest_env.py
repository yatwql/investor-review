"""pytest 环境探测与命令构建（插件检查 / xdist worker 数 / 参数拼装 / 结果解析）。"""

from __future__ import annotations

import os
import re
import sys

from _test_runner.paths import _LATEST_DIR, _PROJECT_ROOT, _SRC_DIR


def _check_pytest_html() -> bool:
    """检查 pytest-html 是否已安装。"""
    try:
        import pytest_html  # noqa: F401

        return True
    except ImportError:
        return False


def _check_pytest_cov() -> bool:
    """检查 pytest-cov 是否已安装。"""
    # 可选依赖只探测是否可解析（不导入：插件导入有副作用，且 pyright 无该包的类型信息）
    import importlib.util

    return importlib.util.find_spec("pytest_cov") is not None


def _extract_count(text: str, pattern: str) -> int:
    """从文本中提取匹配的数字，未匹配返回 0。"""
    match = re.search(pattern, text)
    return int(match.group(1)) if match else 0


def _parse_pytest_output(output: str) -> dict:
    """从 pytest 输出中解析测试计数。

    Returns:
        {passed, failed, skipped, errors, subtests, duration}
    """
    result: dict = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0, "subtests": 0, "duration": 0.0}

    lines = output.strip().splitlines()
    summary_line = ""
    for line in reversed(lines):
        cleaned = line.strip()
        if cleaned and ("passed" in cleaned or "failed" in cleaned):
            summary_line = cleaned
            break

    if not summary_line:
        return result

    result["passed"] = _extract_count(summary_line, r"(\d+)\s+passed")
    result["failed"] = _extract_count(summary_line, r"(\d+)\s+failed")
    result["skipped"] = _extract_count(summary_line, r"(\d+)\s+skipped")
    result["errors"] = _extract_count(summary_line, r"(\d+)\s+error")
    result["subtests"] = _extract_count(summary_line, r"(\d+)\s+subtests passed")

    dur_match = re.search(r"in\s+([\d.]+)s", summary_line)
    if dur_match:
        result["duration"] = float(dur_match.group(1))

    return result


def _check_xdist() -> bool:
    """检查 pytest-xdist 是否已安装。"""
    try:
        import xdist  # noqa: F401

        return True
    except ImportError:
        return False


_PARALLEL_FACTOR: dict[str, float] = {
    "high": 1.0,
    "medium": 0.5,
    "low": 0.25,
}


#: 环境变量覆盖并行级别（与 `--parallel` 同义）：慢盘/慢 CPU 机器上可一次性固定，
#: 不必每次命令行带参（ANSI 前缀与 `--parallel` 优先级：CLI > 本变量 > medium）
PARALLEL_ENV = "TEST_RUNNER_PARALLEL"

#: 单用例超时（秒）：设了就为每个用例加看门狗，超时即失败并打印该用例的堆栈——
#: 把「整档 720s 超时」变成「用例 X 超时」的可定位结论。缺省不启用（慢机器上过短会误杀；
#: 排障时显式给值，如 ``TEST_RUNNER_PER_TEST_TIMEOUT=120``）。
PER_TEST_TIMEOUT_ENV = "TEST_RUNNER_PER_TEST_TIMEOUT"

#: medium 档的 worker 上限：实测 16 核上 8 worker 最优、16 worker 反而慢 17%
#: （xdist 进程争抢 + 磁盘/杀软扫描），故默认档不再随核数无上限放大；
#: 显式 `--parallel high` 仍按 100% 核数执行（用户明确要求时尊重其选择）
_MEDIUM_WORKER_CAP = 8


def resolve_parallel_level(cli_level: str | None) -> str:
    """并行级别解析：CLI > `TEST_RUNNER_PARALLEL` > 缺省 medium。

    Returns:
        ``"high"`` / ``"medium"`` / ``"low"``（非法环境变量值按 medium 处理）。
    """
    if cli_level:
        return cli_level
    raw = (os.environ.get(PARALLEL_ENV) or "").strip().lower()
    return raw if raw in _PARALLEL_FACTOR else "medium"


def _calc_parallel_workers(level: str | bool) -> str:
    """根据并行级别计算 worker 数。

    Args:
        level: "high"（100% 核数）/ "medium"（50%，默认）/ "low"（25%，最小 2）
               或 True（等价 medium）

    Returns:
        "-n" 参数的字符串值，如 "8"、"4"、"2"
    """
    level_key = "medium" if level is True else str(level)
    factor = _PARALLEL_FACTOR.get(level_key, 0.5)
    n_cores = os.cpu_count() or 4
    workers = max(1, int(n_cores * factor))
    if level_key == "low":
        workers = max(2, workers)
    elif level_key == "medium":
        workers = min(workers, _MEDIUM_WORKER_CAP)
    return str(workers)


def _phase_report_path(mode_key: str, phase_tag: str = "") -> str:
    """该模式的 pytest-html 报告路径。

    多阶段模式**每阶段一个文件**（``report_phase_<tag>.html``）：多阶段共用
    ``report.html`` 会让后跑的阶段覆盖前者，详细报告只剩最后一阶段（实测只剩
    152 个场景用例、首阶段的 2700+ 用例全丢），排查时看不到真正的失败面。
    单阶段（合一后的 dev-verify）与非分阶段模式用 ``report.html``。
    """
    name = f"report_phase_{phase_tag}.html" if phase_tag else "report.html"
    return os.path.join(_LATEST_DIR, mode_key, name)


def _build_pytest_args(
    mode_cfg: dict,
    mode_key: str,
    html_available: bool,
    coverage: bool,
    parallel_level: str | None = None,
    phase_tag: str = "",
) -> list[str]:
    """构建 pytest 命令参数列表（``phase_tag`` 非空时报告文件名带阶段后缀）。"""
    args = [
        sys.executable,
        "-m",
        "pytest",
        _SRC_DIR,
        "-q",
        "--tb=short",
    ]

    marker = mode_cfg["marker"]
    if marker:
        args.extend(["-m", marker])

    # ── 并行执行 ──
    parallel_enabled = mode_cfg.get("parallel", False)
    if parallel_enabled and _check_xdist():
        level = resolve_parallel_level(parallel_level)
        workers = _calc_parallel_workers(level)
        args.extend(["-n", workers])
        hint = ""
        n_cores = os.cpu_count() or 0
        if level != "high" and n_cores and int(workers) < n_cores:
            hint = f"；如需更多并发：--parallel high 或设 {PARALLEL_ENV}=high"
        print(f"      [..] 并行 worker={workers}（级别: {level}{hint}）")
    elif parallel_enabled:
        print("      [!] pytest-xdist 未安装，降级单线程执行")

    per_test_timeout = (os.environ.get(PER_TEST_TIMEOUT_ENV) or "").strip()
    if per_test_timeout:
        args.extend([f"--timeout={per_test_timeout}", "--timeout-method=thread"])
        print(f"      [..] 单用例超时看门狗: {per_test_timeout}s（{PER_TEST_TIMEOUT_ENV}）")

    if html_available:
        args.extend(["--html", _phase_report_path(mode_key, phase_tag), "--self-contained-html"])

    if coverage:
        if _check_pytest_cov():
            cov_report_dir = os.path.join(_LATEST_DIR, "coverage")
            args.extend(
                [
                    "--cov=" + os.path.join(_PROJECT_ROOT, "src", "python"),
                    "--cov-report=html:" + cov_report_dir,
                    "--cov-report=term-missing:skip-covered",
                ]
            )
        else:
            print("  [!] pytest-cov 未安装，跳过覆盖率收集")

    return args
