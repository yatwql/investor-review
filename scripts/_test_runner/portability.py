"""CI `portability` job 的本地等价探针（隐式编码严格档 + 需求文件 locale 解码）。

CI 的 `portability` job 跑两道探针，专门拦「本机 UTF-8 locale 掩盖」的两类缺陷：

1. **隐式编码严格档**：`PYTHONWARNDEFAULTENCODING=1` 跑单元套件——任何未显式
   `encoding=` 的文本 I/O 立即失败（`pytest.ini` 已把 `EncodingWarning` 升为 error）；
2. **旧 pip 的 locale 解码回退**：pip ≤24.x 对 `requirements.txt` 按「BOM → PEP263
   cookie → locale 编码」解码，无 BOM 时在 cp936 上回退 GBK 并报错。本模块用两道更稳的
   等价判定——**确定性**检查需求文件是否带 BOM/cookie（正是该回退的触发条件），再以
   `LC_ALL=C` 跑一次 `pip install --dry-run` 做真实解析烟测（当前 pip ≥25 起默认 UTF-8，
   故真实解析不再走回退分支，输出会提示该探针只在旧 pip 上具备完整判定力）。

本机跑通即与 CI 同档（locale 差异、系统库差异除外），因此日常提交无需轮询 CI。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:  # 测试经文件路径加载本模块时补齐兄弟包导入面
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _test_runner.paths import _PROJECT_ROOT  # noqa: E402

#: 需求文件（旧 pip 解码回退的判定对象）
REQUIREMENTS = Path(_PROJECT_ROOT) / "requirements.txt"

#: 探针默认超时（秒）：单元套件最慢，其余为秒级
ENCODING_PROBE_TIMEOUT = 900
PIP_PROBE_TIMEOUT = 180

_PEP263_COOKIE = re.compile(rb"^[ \t\f]*#.*?coding[:=][ \t]*([-_.a-zA-Z0-9]+)")


def _short(proc_text: str, limit: int = 40) -> str:
    """取子进程输出末尾若干行（失败定位用）。"""
    lines = [ln for ln in proc_text.splitlines() if ln.strip()]
    return "\n".join(lines[-limit:])


def check_requirements_bom(path: Path | None = None) -> tuple[bool, str]:
    """需求文件是否满足「BOM 或 PEP263 cookie」——旧 pip 按 locale 回退的触发条件。

    Args:
        path: 需求文件路径（缺省取模块级 `REQUIREMENTS`，调用时解析以支持重定向）

    Returns:
        (是否满足, 说明)。缺失文件视为不满足。
    """
    path = path or REQUIREMENTS
    if not path.is_file():
        return False, f"未找到需求文件：{path}"
    head = path.read_bytes()[:512]
    if head.startswith(b"\xef\xbb\xbf"):
        return True, "带 UTF-8 BOM"
    for line in head.splitlines()[:2]:
        if _PEP263_COOKIE.match(line):
            return True, "带 PEP263 编码声明"
    return False, "既无 UTF-8 BOM 也无 PEP263 编码声明（旧 pip 会按 locale 解码）"


def run_encoding_probe(timeout: int | None = ENCODING_PROBE_TIMEOUT) -> list[str]:
    """以 `PYTHONWARNDEFAULTENCODING=1` 跑单元套件（CI 探针 ①）。

    Returns:
        失败时的输出末尾行（通过则为空列表）
    """
    env = os.environ.copy()
    env["PYTHONWARNDEFAULTENCODING"] = "1"
    env["INVEST_RUNNING_TESTS"] = "1"
    cmd = [sys.executable, "-m", "pytest", "src/test/unit", "-q", "--tb=short"]
    print(f"    [..] 隐式编码严格档：{' '.join(cmd[1:])}（PYTHONWARNDEFAULTENCODING=1）")
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=_PROJECT_ROOT,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return [f"隐式编码严格档超时（{timeout}s）"]
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0:
        tail = [ln.strip() for ln in out.splitlines() if "passed" in ln]
        print(f"    [OK] 隐式编码严格档：{tail[-1] if tail else '通过'}")
        return []
    print(f"    [ERR] 隐式编码严格档失败（exit={proc.returncode}）")
    tail_lines = _short(out).splitlines()
    for line in tail_lines:
        print(f"      {line}")
    return tail_lines


def pip_version(timeout: int | None = PIP_PROBE_TIMEOUT) -> str:
    """当前 pip 版本串（用于提示探针 ② 的判定力，失败返回空串）。"""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=_PROJECT_ROOT,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return (proc.stdout or "").strip().split(" ")[1] if proc.stdout else ""


def run_pip_locale_probe(timeout: int | None = PIP_PROBE_TIMEOUT) -> list[str]:
    """在 `LC_ALL=C` 下真实解析需求文件（CI 探针 ②）。

    先做确定性判定（BOM / PEP263 cookie），再跑一次 `pip install --dry-run` 烟测。

    Returns:
        失败时的输出末尾行（通过则为空列表）
    """
    ok, detail = check_requirements_bom()
    if ok:
        print(f"    [OK] 需求文件编码判定：{detail}")
    else:
        print(f"    [ERR] 需求文件编码判定：{detail}")
        return [detail]

    version = pip_version(timeout)
    if version:
        major = version.split(".")[0]
        if major.isdigit() and int(major) >= 25:
            print(
                f"    [!] 当前 pip {version} 默认按 UTF-8 解码需求文件，"
                "`LC_ALL=C` 烟测不经过旧 pip 的 locale 回退分支"
                "（确定性判定已覆盖该缺陷类；完整判定需 pip ≤24.x）"
            )

    env = os.environ.copy()
    env.update({"LC_ALL": "C", "LANG": "C", "PYTHONCOERCECLOCALE": "0", "PYTHONUTF8": "0"})
    cmd = [sys.executable, "-m", "pip", "install", "--dry-run", "--no-deps", "-r", str(REQUIREMENTS.name)]
    print(f"    [..] 非 UTF-8 locale 解析：{' '.join(cmd[1:])}（LC_ALL=C）")
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=_PROJECT_ROOT,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return [f"pip 解析烟测超时（{timeout}s）"]
    if proc.returncode == 0:
        print("    [OK] 非 UTF-8 locale 解析：通过")
        return []
    out = (proc.stdout or "") + (proc.stderr or "")
    print(f"    [ERR] 非 UTF-8 locale 解析失败（exit={proc.returncode}）")
    tail_lines = _short(out).splitlines()
    for line in tail_lines:
        print(f"      {line}")
    return tail_lines


def run_portability(
    mode_key: str = "portability",
    timeout_override: int | None = None,
    no_timeout: bool = False,
    desc: str = "",
) -> dict:
    """执行两道 CI portability 等价探针，返回 test-runner 统一结果结构。

    Args:
        mode_key: 模式名（汇总页与统计用）
        timeout_override: `--timeout` 覆盖（None 用探针默认）
        no_timeout: 禁用超时（CI 同档行为：等待自然结束）
        desc: 模式说明（取自 MODES）

    Returns:
        `{"mode","desc","passed","failed",...}`；其中 passed/failed 计的是**探针项数**
    """
    started = time.monotonic()
    enc_timeout = None if no_timeout else (timeout_override or ENCODING_PROBE_TIMEOUT)
    pip_timeout = None if no_timeout else (timeout_override or PIP_PROBE_TIMEOUT)

    print(f"\n  {'=' * 54}")
    print(f"  [..] 正在运行 [{mode_key}] — {desc}")
    print()

    failures: list[str] = []
    probes = [
        ("隐式编码严格档", lambda: run_encoding_probe(enc_timeout)),
        ("需求文件 locale 解码", lambda: run_pip_locale_probe(pip_timeout)),
    ]
    for label, probe in probes:
        problems = probe()
        if problems:
            failures.append(label)

    duration = time.monotonic() - started
    passed = len(probes) - len(failures)
    ok = not failures
    tag = "OK" if ok else "ERR"
    print(f"\n  [{tag}] {mode_key}: {passed} 项探针通过, {len(failures)} 项失败  ({duration:.1f}s)")
    if failures:
        print(f"    失败探针：{'、'.join(failures)}（修复方法见 developer-guide「编码/locale 自检」）")
    return {
        "mode": mode_key,
        "desc": desc,
        "passed": passed,
        "failed": len(failures),
        "skipped": 0,
        "errors": 0,
        "subtests": 0,
        "duration": duration,
        "exit_code": 0 if ok else 1,
        "timed_out": False,
    }
