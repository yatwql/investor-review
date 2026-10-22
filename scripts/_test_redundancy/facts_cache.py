"""文件事实缓存：按「脚本 + _checklib + 解释器版本 + 逐文件 size:mtime」判定命中。"""

from __future__ import annotations
from _test_redundancy._common import (
    TestCase,
    _iter_test_files,
    cases_in_module,
)
from _test_redundancy.cases import (
    check_dead_tests,
    check_assertion_free,
)
from _test_redundancy.dead_fixtures import (
    _fixture_exposed_name,
)
from _test_redundancy.duplicates import (
    body_signature,
)
from _test_redundancy.hardcoded import (
    check_hardcoded_evolving_totals,
)
from _test_redundancy.self_fulfilling import (
    check_self_fulfilling,
)
from _test_redundancy.trivial import (
    check_trivially_true,
)
from _test_redundancy.weak_mock import (
    check_weak_mock_assertions,
)

import ast
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _shared.checklib import REPO_ROOT, rel  # noqa: E402


_CACHE_ENV = "TEST_REDUNDANCY_CACHE"


_CACHE_FILE = "test_redundancy_facts.json"


def _facts_cache_path() -> Path:
    override = os.environ.get(_CACHE_ENV)
    return Path(override) if override else REPO_ROOT / "data" / "cache" / _CACHE_FILE


def _cache_version() -> str:
    """缓存格式/判定逻辑版本：本脚本 + 同目录 _checklib + 解释器大版本，任一变化全量失效。"""
    parts = [f"{sys.version_info[0]}.{sys.version_info[1]}"]
    for src in (Path(__file__), Path(__file__).resolve().parents[1] / "_shared" / "checklib.py"):
        try:
            parts.append(hashlib.sha1(src.read_bytes()).hexdigest())
        except OSError:
            parts.append("?")
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


def _file_signature(path: Path) -> str:
    st = path.stat()
    return f"{st.st_size}:{st.st_mtime_ns}"


def _load_facts_cache(path: Path) -> dict[str, dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("version") != _cache_version():
        return {}
    files = data.get("files")
    return files if isinstance(files, dict) else {}


def _save_facts_cache(path: Path, files: dict[str, dict]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"version": _cache_version(), "files": files}, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, path)
    except OSError:  # 缓存只影响速度不影响结论：写失败静默降级为下次全量
        pass


def _file_facts(path: Path, tree: ast.Module, cases: list[TestCase]) -> dict:
    """单文件冷路径事实：各类文件内检查结果 + fixture 消费面 + 跨文件重复比对所需指纹。

    检查函数本体不改（单测契约不变），仅把调用从「全集两遍」变为「每文件一遍、命中缓存零遍」。
    """
    fixtures: list[list] = []
    params: list[str] = []
    usefix: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            params.extend(a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs))
            for extra in (args.vararg, args.kwarg):
                if extra is not None:
                    params.append(extra.arg)
            exposed = _fixture_exposed_name(node)
            if exposed is not None:
                fixtures.append([exposed, node.lineno])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "usefixtures":
            usefix.extend(a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str))
    return {
        "count": len(cases),
        "dead": check_dead_tests(cases, {path: tree}),
        "assertion": check_assertion_free(cases),
        "self": check_self_fulfilling(cases),
        "hard": check_hardcoded_evolving_totals(cases),
        "trivial": check_trivially_true(cases),
        "weak": check_weak_mock_assertions(cases),
        "fixtures": fixtures,
        "params": params,
        "usefix": usefix,
        "entries": [{"sig": body_signature(c), "lineno": c.lineno, "name": c.name} for c in cases],
    }


def _collect_facts(include_live: bool) -> tuple[dict[str, dict], list[str]]:
    """逐文件取事实：签名未变直接复用缓存（免解析免检查），变更文件仅增量重算。

    返回（{绝对路径: 事实}, parse_errors）。已删除文件的陈旧条目随写回自动剔除。
    """
    cache_path = _facts_cache_path()
    cached = _load_facts_cache(cache_path)
    facts: dict[str, dict] = {}
    parse_errors: list[str] = []
    for path in _iter_test_files(include_live):
        key = str(path)
        sig = _file_signature(path)
        old = cached.get(key)
        if isinstance(old, dict) and old.get("sig") == sig:
            facts[key] = old
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:  # 语法错误由 pytest 自己报，这里不重复报
            parse_errors.append(f"{rel(path)}: 无法解析（{exc.msg}）")
            continue
        facts[key] = {"sig": sig, **_file_facts(path, tree, cases_in_module(path, tree))}
    if facts != cached:
        _save_facts_cache(cache_path, facts)
    return facts, parse_errors
