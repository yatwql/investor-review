"""检查 11：测试内的真实耗时等待与真实子进程执行。

背景：测试应当**验证行为**，不应**消耗墙钟**。两类写法把测试变成不稳定源：

  1. `time.sleep(<≥0.1s 的字面量>)`——真实睡满整段墙钟。CI 上多数抖动、超时、
     「本机绿、CI 红」都由此而来：单条用例多睡 0.2s，上千条用例叠加就是分钟级
     浪费，且与门禁并行度耦合（并发抢核时睡得越久越容易踩超时）。
  2. 测试里 `subprocess.run/check_output/Popen` 真跑 `pytest` 或 `python -m …`——
     真起解释器再跑一遍测试，墙钟随宿主环境漂移，失败信息还隔着子进程边界。

判据（AST 静态，不执行测试）：

  - `time.sleep(<字面量 ≥ `SLOW_SLEEP_SECONDS`>)` → 报。非字面量实参无法静态判定，不报。
  - `subprocess.run/check_output/Popen` 的调用源码里出现 `pytest` 或 `sys.executable`
    （即真跑解释器/真跑测试），且**同作用域内没有 mock 证据** → 报。
    mock 证据 = 外层任一测试函数（含其装饰器）或模块级出现 `patch(...)` /
    `patch.object(...)` / `monkeypatch.setattr(...)` 且目标文本含 `subprocess`——
    被替身接管的子进程不真执行，不属本规则要拦的形态。

确认必须真等/真跑（并发重叠量测、假源模拟慢源、CLI 退出码契约量测等）的，登记在
`scripts/_test_redundancy_exceptions.json` 的 `slow-or-subprocess` 规则键下：
定位键为 `<仓库相对路径>::<分类>::<细节>`（sleep 取字面量值，子进程取 argv 源码），
字段与 `patch-surface` 规则同风格（owner / reason / expiry / replacement），并由
:func:`audit_exceptions` 自审（字段齐全 / 未到期 / 仍命中违规）。
"""

from __future__ import annotations

import ast
import json
import sys
from datetime import date
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _shared.checklib import rel


#: 例外表路径（与被检入口同目录，便于随检查一起评审）
EXCEPTIONS_FILE = Path(__file__).resolve().parents[1] / "_test_redundancy_exceptions.json"

#: 例外表里的规则键
RULE_KEY = "slow-or-subprocess"

#: 例外条目必填字段（缺一即无法追责或无法自动到期）
REQUIRED_FIELDS = ("owner", "reason", "expiry", "replacement")

_EXPIRY_LEN = len("YYYY-MM-DD")

#: 真实等待的秒数阈值：低于它（轮询/让出一次调度）的短等待不属浪费墙钟的形态
SLOW_SLEEP_SECONDS = 0.1

#: 分类（同时写进例外定位键，便于按类追责）
KIND_SLEEP = "slow-sleep"
KIND_SUBPROCESS = "real-subprocess"

#: 真跑子进程的入口（与本规则声明面一致）
_SUBPROCESS_CALLS = frozenset({"run", "check_output", "Popen"})

#: 「真跑解释器/真跑测试」的证据词（出现在调用源码里即认定）
_EXECUTOR_MARKERS = ("pytest", ".executable")

#: mock 证据的调用名后缀（`patch` / `patch.object` / `monkeypatch.setattr`）
_MOCK_CALLS = frozenset({"patch", "setattr"})

_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def _chain(node: ast.AST) -> str:
    """属性的点分链源码（`subprocess.run` / `monkeypatch.setattr`；解析不出返空串）。"""
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        return ""
    parts.append(cur.id)
    return ".".join(reversed(parts))


def _call_source(call: ast.AST) -> str:
    """调用源码单行化（定位键与 finding 文案共用）。"""
    try:
        return " ".join(ast.unparse(call).split())
    except (AttributeError, ValueError):  # 节点无法反解（unparse 缺字段/节点损坏）
        return ""


def _is_literal_slow(node: ast.AST) -> float | None:
    """字面量秒数 ≥ 阈值则返回该值（非字面量/低于阈值返 None）。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value) if float(node.value) >= SLOW_SLEEP_SECONDS else None
    return None


def _is_subprocess_call(call: ast.Call) -> bool:
    """是否 `subprocess.<run|check_output|Popen>` 形态（含工作树内的别名写法）。"""
    chain = _chain(call.func)
    if not chain:
        return False
    head, _, attr = chain.rpartition(".")
    return attr in _SUBPROCESS_CALLS and head.split(".")[-1] == "subprocess"


def _runs_executor(call: ast.Call) -> bool:
    """该子进程调用是否真跑解释器/真跑测试（argv 源码里出现证据词）。"""
    source = _call_source(call)
    return any(marker in source for marker in _EXECUTOR_MARKERS)


class _MockEvidence(NamedTuple):
    """mock 证据的所在位置：模块级 / 各测试函数（含装饰器）内。"""

    module_level: bool
    per_function: dict[ast.AST, bool]


def _enclosing_functions(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> list[ast.AST]:
    """外围函数链（由内到外）。"""
    found: list[ast.AST] = []
    cur = parents.get(node)
    while cur is not None:
        if isinstance(cur, _SCOPE_NODES):
            found.append(cur)
        cur = parents.get(cur)
    return found


def _mock_evidence_owners(node: ast.AST, tree: ast.Module, parents: dict[ast.AST, ast.AST]) -> list[ast.AST | None]:
    """mock 证据所属的作用域：外围函数链（由内到外）+ None（模块级）。

    装饰器不在函数体内（它是函数的 decorator_list），故装饰器里的 patch 另按
    「谁的 decorator_list 含该节点」归属到该测试函数。
    """
    outer = _enclosing_functions(node, parents)
    owners: list[ast.AST | None] = list(outer)
    for parent in ast.walk(tree):
        if isinstance(parent, _SCOPE_NODES) and any(node in ast.walk(decorator) for decorator in parent.decorator_list):
            owners.append(parent)
    if not outer:
        owners.append(None)
    return owners


def _collect_mock_evidence(tree: ast.Module, parents: dict[ast.AST, ast.AST]) -> _MockEvidence:
    """收集「子进程被替身接管」的证据点：`patch(...)` / `monkeypatch.setattr(...)` 且目标含 `subprocess`。"""
    module_level = False
    per_function: dict[ast.AST, bool] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        attr = _chain(node.func).rpartition(".")[2]
        if attr not in _MOCK_CALLS:
            continue
        if "subprocess" not in _call_source(node):
            continue
        for owner in _mock_evidence_owners(node, tree, parents):
            if owner is None:
                module_level = True
            else:
                per_function[owner] = True
    return _MockEvidence(module_level, per_function)


def extract_slow_or_subprocess(tree: ast.Module, path: Path) -> list[list]:
    """文件内事实：``[[行号, 分类, 定位键], ...]``（不套例外表，供事实缓存与例外自审复用）。"""
    rel_path = rel(path)
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    evidence = _collect_mock_evidence(tree, parents)

    hits: list[list] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        chain = _chain(node.func)
        if chain == "time.sleep" and node.args:
            seconds = _is_literal_slow(node.args[0])
            if seconds is not None:
                hits.append([node.lineno, KIND_SLEEP, f"{rel_path}::{KIND_SLEEP}::time.sleep({seconds:g})"])
            continue
        if not _is_subprocess_call(node) or not _runs_executor(node):
            continue
        if evidence.module_level or any(
            evidence.per_function.get(func) for func in _enclosing_functions(node, parents)
        ):
            continue
        argv = _call_source(node.args[0]) if node.args else ""
        hits.append([node.lineno, KIND_SUBPROCESS, f"{rel_path}::{KIND_SUBPROCESS}::{argv}"])
    return hits


class _ExceptionTable(NamedTuple):
    """例外表：允许的定位键集合 + 原始条目 + 读表失败原因。"""

    allowed: set[str]
    raw: list[dict]
    load_error: str = ""


def load_exceptions() -> _ExceptionTable:
    """读 `slow-or-subprocess` 例外（文件缺失视为无例外，解析失败落在 `load_error`）。"""
    if not EXCEPTIONS_FILE.exists():
        return _ExceptionTable(set(), [])
    try:
        raw_table = json.loads(EXCEPTIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _ExceptionTable(set(), [], f"{rel(EXCEPTIONS_FILE)} 无法解析：{exc}")
    raw = [entry for entry in raw_table.get(RULE_KEY, []) if isinstance(entry, dict)]
    return _ExceptionTable({str(entry.get("name", "")) for entry in raw}, raw)


def check_slow_or_subprocess(
    facts_by_file: dict[Path, list[list]],
    exceptions: _ExceptionTable | None = None,
) -> list[str]:
    """L：测试内真实等待 / 真实子进程——未登记例外的逐条报 finding。

    Args:
        facts_by_file: ``{测试文件: [[行号, 分类, 定位键], ...]}``（由本模块的
            :func:`extract_slow_or_subprocess` 逐文件产出，经事实缓存传递）。
        exceptions: 例外表；缺省读 ``_test_redundancy_exceptions.json``。
    """
    table = exceptions if exceptions is not None else load_exceptions()
    findings: list[str] = []
    for path, facts in sorted(facts_by_file.items()):
        for lineno, kind, key in facts:
            if key in table.allowed:
                continue
            detail = key.split("::", 2)[2]
            if kind == KIND_SLEEP:
                findings.append(
                    f"{rel(path)}:{lineno}: 测试内真实等待 {detail}（≥{SLOW_SLEEP_SECONDS:g}s）——"
                    "CI 抖动与 flaky 的主要来源；改用事件/条件等待（threading.Event 等）或在 "
                    "_test_redundancy_exceptions.json 登记例外"
                )
            else:
                findings.append(
                    f"{rel(path)}:{lineno}: 测试内真实执行子进程 {detail}（真跑解释器/测试，未见 mock 证据）——"
                    "墙钟随宿主环境漂移；改 patch 掉 subprocess.run/check_output/Popen，或在 "
                    "_test_redundancy_exceptions.json 登记例外"
                )
    return findings


def audit_exceptions(table: _ExceptionTable) -> list[str]:
    """例外表自审：字段齐全 + expiry 合法未到期（登记点的存活性由下一轮扫描发现）。"""
    findings: list[str] = []
    if table.load_error:
        findings.append(table.load_error)
    today = date.today()
    for entry in table.raw:
        name = str(entry.get("name", ""))
        where = f"{rel(EXCEPTIONS_FILE)} {RULE_KEY}::{name}"
        missing = [field for field in REQUIRED_FIELDS if not str(entry.get(field, "")).strip()]
        if missing:
            findings.append(f"[exception-metadata] {where} 缺少字段 {'/'.join(missing)}")
            continue
        expiry_raw = str(entry["expiry"]).strip()
        if not _is_iso_date(expiry_raw):
            findings.append(f"[exception-metadata] {where} expiry 须为 YYYY-MM-DD，实为「{expiry_raw}」")
        elif date.fromisoformat(expiry_raw) < today:
            findings.append(f"[exception-expiry] {where} 已于 {expiry_raw} 到期，须删除例外或续期并复核理由")
    return findings


def audit_stale_exceptions(table: _ExceptionTable, facts_by_file: dict[Path, list[list]]) -> list[str]:
    """例外存活性自审：本次扫描里未命中任何违规的条目即陈旧（规则已修复），须删除。"""
    used = {key for facts in facts_by_file.values() for _lineno, _kind, key in facts}
    return [
        f"[exception-stale] {rel(EXCEPTIONS_FILE)} {RULE_KEY}::{entry.get('name', '')} 未命中任何违规（规则已修复），须删除该例外"
        for entry in table.raw
        if str(entry.get("name", "")) not in used
    ]


def _is_iso_date(text: str) -> bool:
    try:
        return len(text) == _EXPIRY_LEN and date.fromisoformat(text).isoformat() == text
    except ValueError:
        return False
