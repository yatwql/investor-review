"""编排：按各检查支路依次执行并汇总 finding 与统计。CLI 面在入口脚本。"""

from __future__ import annotations
from _test_redundancy.dead_fixtures import (
    check_dead_fixtures,
)
from _test_redundancy.duplicates import (
    _group_duplicate_entries,
)
from _test_redundancy.facts_cache import (
    _collect_facts,
)
from _test_redundancy.patch_surface import (
    audit_exceptions as audit_patch_exceptions,
    check_patch_surface,
    load_exceptions as load_patch_exceptions,
)

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _shared.checklib import rel


def _scans_real_test_tree(facts: dict[str, Any]) -> bool:
    """本次扫描是否覆盖本仓 `src/test`（决定例外表自审是否适用）。"""
    from _test_redundancy._common import _TEST_ROOT as test_root

    root = Path(str(test_root)).resolve()
    return any(Path(str(key)).resolve().is_relative_to(root) for key in facts)


def run_checks(include_live: bool = False) -> tuple[list[str], dict[str, int]]:
    """跑全部检查，返回（findings, 统计）。

    判定逐文件调用同一组 check_*（冷路径才算），跨文件只做事实归并与重复比对归并。
    """
    facts, parse_errors = _collect_facts(include_live)
    dead_fixtures = check_dead_fixtures(facts)  # per-file 事实聚合判定（零额外解析，不污染缓存热路径）
    dead: list[str] = []
    assertion_free: list[str] = []
    self_fulfilling: list[str] = []
    hardcoded: list[str] = []
    trivial: list[str] = []
    weak: list[str] = []
    date_bomb: list[str] = []
    marker: list[str] = []
    entries: list[tuple[str, int, str, str | None]] = []
    n_cases = 0
    for key, item in facts.items():
        rel_path = rel(Path(key))
        dead += item["dead"]
        assertion_free += item["assertion"]
        self_fulfilling += item["self"]
        hardcoded += item["hard"]
        trivial += item["trivial"]
        weak += item["weak"]
        date_bomb += item["date_bomb"]
        marker += item["markers"]
        n_cases += item["count"]
        entries.extend((rel_path, e["lineno"], e["name"], e["sig"]) for e in item["entries"])
    dup_findings, skipped = _group_duplicate_entries(entries)
    # patch 面判定要看目标生产模块，不能只靠测试文件签名缓存——故目标抽取留在 per-file
    # 事实里（测试文件自己的信息），解析/判定在编排处按本次工作树现算。
    patch_exceptions = load_patch_exceptions()
    patch_surface = check_patch_surface(
        {Path(key): item["patch_targets"] for key, item in facts.items()}, patch_exceptions
    )
    # 例外表自审只对「本仓 src/test」的扫描生效：夹具造 tmp 树时例外条目必然全不命中，
    # 那不是陈旧例外而是没扫到。
    if _scans_real_test_tree(facts):
        patch_surface += audit_patch_exceptions(patch_exceptions)
    findings: list[str] = []
    findings += parse_errors
    findings += dead
    findings += assertion_free
    findings += dup_findings
    findings += self_fulfilling
    findings += hardcoded
    findings += trivial
    findings += dead_fixtures
    findings += weak
    findings += date_bomb
    findings += marker
    findings += patch_surface
    stats = {
        "files": len(facts),
        "cases": n_cases,
        "duplicate_skipped": skipped,
        "dead": len(dead),
        "assertion_free": len(assertion_free),
        "duplicate": len(dup_findings),
        "self_fulfilling": len(self_fulfilling),
        "hardcoded_totals": len(hardcoded),
        "trivial": len(trivial),
        "dead_fixtures": len(dead_fixtures),
        "weak_mock": len(weak),
        "date_bombs": len(date_bomb),
        "markers": len(marker),
        "patch_surface": len(patch_surface),
    }
    return findings, stats
