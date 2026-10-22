"""编排：按八类检查依次执行并汇总 finding 与统计。CLI 面在入口脚本。"""

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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _shared.checklib import rel  # noqa: E402


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
        n_cases += item["count"]
        entries.extend((rel_path, e["lineno"], e["name"], e["sig"]) for e in item["entries"])
    dup_findings, skipped = _group_duplicate_entries(entries)
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
    }
    return findings, stats
