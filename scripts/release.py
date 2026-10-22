#!/usr/bin/env python3
"""发布流程分步编排 — 入口（路径常量 + env 投影 + 薄包装 + CLI）。

把「版本发布流程」固化为可执行子命令，每步独立可审阅、失败即停：

    .venv/bin/python scripts/release.py check
    .venv/bin/python scripts/release.py archive-init
    .venv/bin/python scripts/release.py prepare
    .venv/bin/python scripts/release.py refresh
    .venv/bin/python scripts/release.py evolution --release
    .venv/bin/python scripts/release.py gate
    .venv/bin/python scripts/release.py publish --title "<发布主题>"
    .venv/bin/python scripts/release.py devbump

退出码：0 = 通过；2 = 预检/门禁发现（与守护脚本 CLI 契约一致）；1 = 执行失败。

耗时埋点：每命令的总墙钟与分步耗时（gate 的回归/十守护/护栏、refresh 的
bench/collect/sync、publish 的 P1 verify）追加写入 `logs/release.jsonl`（git 忽略域，
不入目录树、无门禁依赖），终端尾行同步打印摘要——跨版本对拍直接
`tail -n 20 logs/release.jsonl`，无需现场重测。

**分层**：命令实现与其共用原语（预检/耗时/发布戳/归档路径推导）在
`_release/_commands_prep.py`（准备阶段）与 `_release/_commands_ship.py`（交付阶段），
二者共用的原语在 `_release/_commands_base.py`；argparse 装配与分派在 `_release/_cli.py`；纯文本变换在
`_release/_ledger_archive.py` / `_changelog_archive.py` / `_evolution.py`。本文件
只保留**路径常量**（测试重定向锚点）、`_Env` 投影、命令薄包装与 `main`。
"""

from __future__ import annotations

import argparse
import os  # noqa: F401 — 测试以 `rel.os.cpu_count` 重定向并行度探测
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
CONSTANTS_FILE = REPO_ROOT / "src" / "python" / "core" / "constants.py"
README_FILE = REPO_ROOT / "README.md"
# 文档树路径（本脚本自包含不依赖 _checklib，常量语义与其同名项一致）
_MANAGEMENTS_DIR = REPO_ROOT / "docs" / "managements"
_ARCHIVE_DOCS_DIR = REPO_ROOT / "docs" / "archive"
CHANGELOG_FILE = _MANAGEMENTS_DIR / "changelog.md"
RF_FILE = _MANAGEMENTS_DIR / "review-findings.md"
PLAN_FILE = _MANAGEMENTS_DIR / "plan.md"
PLAN_DOCS_DIR = REPO_ROOT / "docs" / "plan"
FOLDERS_FILE = _MANAGEMENTS_DIR / "folders.md"
TEST_COVERAGE_FILE = _MANAGEMENTS_DIR / "test-coverage.md"

# P2 十守护清单（与 CLAUDE.md / testplan.md / developer-guide.md / ci.yml / pre-commit 钩子同源）
GUARD_SCRIPTS = [
    "scripts/check-code-traces.py",
    "scripts/check-doc-traces.py",
    "scripts/check-task-numbering.py",
    "scripts/check-semantic-index.py",
    "scripts/check-doc-drift.py",
    "scripts/check-test-redundancy.py",
    "scripts/check-requirement-trace.py",
    "scripts/check-version-consistency.py",
    "scripts/check-doc-links.py",
    "scripts/check-file-length.py",
]

#: 发布耗时台账（`logs/` 属 git 忽略域：不入目录树、不进门禁）
RELEASE_LOG_FILE = REPO_ROOT / "logs" / "release.jsonl"
#: gate 通过戳：记录「版本 + 工作区树指纹 + verify 项数」，publish 指纹一致时复用
#: gate 已跑的 P1 verify（避免 28s 重复；指纹不一致则照常重跑，绝不盲信）
GATE_STAMP_FILE = REPO_ROOT / "logs" / "release-gate-stamp.json"
#: refresh bench 通过戳：记录「实际跑过 unit（verify 超集）+ 代码指纹」，
#: gate 据此跳过重复的 P1 verify；任一条件不满足即回落实跑
BENCH_STAMP_FILE = REPO_ROOT / "logs" / "release-bench-stamp.json"

# ── 内部实现拆分（_release/ 包）：入口只保留路径常量、env 投影、薄包装与 main ──
sys.path.insert(0, str(REPO_ROOT))  # 仓库根：耗时台账复用 core 层 JSONL 原子追加原语
sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享设施（_release 包）
from _release import _commands_base as _cmd_base  # noqa: E402
from _release import _commands_prep as _cmd_prep  # noqa: E402
from _release import _commands_ship as _cmd_ship  # noqa: E402
from _release import _gate  # noqa: E402
from _release._archive_flow import ArchiveContext  # noqa: E402, F401 — 归档上下文类型面
from _release._archive_init import init_archive  # noqa: E402, F401
from _release._changelog_archive import SECTION_NOTE as _SECTION_NOTE  # noqa: E402, F401
from _release._changelog_archive import (  # noqa: E402, F401 — 纯函数面经入口 re-export
    apply_changelog_release,
    release_section_has_entries,
    render_archive_header,
    write_archive_release,
)
from _release._cli import RELEASE_BENCH_MODES, build_parser, run_cli  # noqa: E402, F401
from _release._commands_base import (  # noqa: E402, F401 — 共用原语
    _gate_workers,
    _print_results,
    _reset_timer,
    _timer,
    run_preflight,
)
from _release._commands_prep import run_archive  # noqa: E402, F401
from _release._common import ReleaseError, exec_command as _exec  # noqa: E402, F401
from _release._evolution import (  # noqa: E402, F401 — 演进纯函数面
    build_evolution_stats,
    check_evolution_freshness,
    fmt_pair as _fmt_pair,
    line_count as _line_count,
    update_case_note,
    update_evolution_table,
    update_ratio_note,
)
from _release._ledger_archive import (  # noqa: E402, F401 — 台账变换纯函数面
    RF_PLACEHOLDER,
    _INDEX_RANGE_RE,
    _RF_ARCHIVE_HEAD_FMT,
    _bump_index_range,
    _collapse_superseded_placeholders,
    apply_plan_archive,
    apply_rf_archive,
    archive_header_findings,
    count_rf_rows,
    design_doc_candidates,
    drop_migration_placeholders,
    extract_rf_table,
    has_archive_section,
    move_tree_entry,
    open_ids,
    pending_rf_rows,
    plan_completed_sections,
    recompute_current_iteration,
    rewrite_doc_refs,
    rf_archive_status,
    stale_reference_files,
    unreferenced_docs,
)
from _release._timing import (  # noqa: E402, F401 — 耗时台账纯函数面
    agent_identity,
    build_record,
    format_agent,
    format_tokens,
    release_token_usage,
    session_usage,
)
from _release._versioning import (  # noqa: E402, F401 — 版本纯函数面
    DEV_VERSION_RE as _DEV_VERSION_RE,
    RELEASE_VERSION_RE as _RELEASE_VERSION_RE,
    next_dev_version_of,
    normalize_release_title,
    read_app_version,
    release_version_of,
    render_app_version,
    render_readme_version,
)


# ─────────────────────────── 环境投影（测试重定向的单一入口） ───────────────────────────


class _Env:
    """命令实现的环境视图——每次属性访问都回读本模块的**当前**属性。

    全部可重定向路径常量（`REPO_ROOT` / `CONSTANTS_FILE` / `*_STAMP_FILE` …）与
    入口侧原语（`_archive_ctx` / `archive_paths_for` / `run_preflight` …）经此
    投影读取，故单测对入口模块做 `setattr` 重定向时，`_commands_prep` /
    `_commands_ship` 里的命令实现同步生效（无需 patch 到内部包）。
    """

    #: 外部名 → 入口模块属性名（仅名称不同者需要；其余同名直取）
    _ALIAS = {
        "archive_ctx": "_archive_ctx",
        "ARCHIVE_DOCS_DIR": "_ARCHIVE_DOCS_DIR",
    }

    def __getattr__(self, name: str):
        target = self._ALIAS.get(name, name)
        if target not in globals():
            raise AttributeError(name)
        return globals()[target]


_ENV = _Env()


def _env() -> _Env:
    """取环境投影（无状态，单例复用）。"""
    return _ENV


def _archive_ctx(version: str) -> ArchiveContext:
    """按当前模块路径常量组装归档上下文（测试对模块属性的重定向在此生效）。"""
    rf_archive, plan_archive = ledger_archive_paths(version)
    return ArchiveContext(
        repo_root=REPO_ROOT,
        rf_file=RF_FILE,
        plan_file=PLAN_FILE,
        folders_file=FOLDERS_FILE,
        changelog_file=CHANGELOG_FILE,
        readme_file=README_FILE,
        claude_file=REPO_ROOT / "CLAUDE.md",
        plan_docs_dir=PLAN_DOCS_DIR,
        rf_archive=rf_archive,
        plan_archive=plan_archive,
    )


# ─────────────────────────── 共用原语的薄包装（原签名不变） ───────────────────────────


def _finish_timing(command: str, rc: int) -> None:
    return _cmd_base._finish_timing(command, rc, _env())


def archive_paths_for(release_version: str) -> tuple[Path, str]:
    return _cmd_base.archive_paths_for(release_version, _env())


def ledger_archive_paths(release_version: str) -> tuple[Path, Path]:
    return _cmd_base.ledger_archive_paths(release_version, _env())


def archive_prerequisites(release_version: str) -> list[str]:
    return _cmd_base.archive_prerequisites(release_version, _env())


def _tree_fingerprint(runner=None) -> str:
    return _cmd_base._tree_fingerprint(_env(), runner)


def _code_fingerprint(runner=None) -> str:
    return _cmd_base._code_fingerprint(_env(), runner)


def _bench_covers_verify(runner=None) -> dict | None:
    return _cmd_base._bench_covers_verify(_env(), runner)


def _write_gate_stamp(version: str, fingerprint: str, verify_passed: str, source: str = "run") -> None:
    return _cmd_base._write_gate_stamp(version, fingerprint, verify_passed, _env(), source)


def _write_bench_stamp(fingerprint: str, modes: list[str], covers_unit: bool) -> None:
    return _cmd_base._write_bench_stamp(fingerprint, modes, covers_unit, _env())


def _gate_stamp_matches(version: str, fingerprint: str) -> dict | None:
    return _cmd_base._gate_stamp_matches(version, fingerprint, _env())


# ─────────────────────────── 命令薄包装（保持既有调用面） ───────────────────────────


def cmd_check(args: argparse.Namespace, runner=None) -> int:
    return _cmd_prep.cmd_check(args, _env(), runner)


def cmd_archive_init(args: argparse.Namespace, runner=None) -> int:
    return _cmd_prep.cmd_archive_init(args, _env(), runner)


def cmd_prepare(args: argparse.Namespace, runner=None) -> int:
    return _cmd_prep.cmd_prepare(args, _env(), runner)


def cmd_archive(args: argparse.Namespace, runner=None) -> int:
    return _cmd_prep.cmd_archive(args, _env(), runner)


def cmd_refresh(args: argparse.Namespace, runner=None) -> int:
    return _cmd_ship.cmd_refresh(args, _env(), runner)


def cmd_evolution(args: argparse.Namespace, runner=None) -> int:
    return _cmd_ship.cmd_evolution(args, _env(), runner)


def cmd_publish(args: argparse.Namespace, runner=None) -> int:
    return _cmd_ship.cmd_publish(args, _env(), runner)


def cmd_devbump(args: argparse.Namespace, runner=None) -> int:
    return _cmd_ship.cmd_devbump(args, _env(), runner)


# ─────────────────────────── gate ───────────────────────────


def cmd_gate(args: argparse.Namespace, runner=None) -> int:
    """P2 门禁编排（实现在 `_release/_gate.py`；依赖按当前模块状态注入）。"""
    ctx = SimpleNamespace(
        check_evolution_freshness=check_evolution_freshness,
        read_app_version=read_app_version,
        ledger_archive_paths=ledger_archive_paths,
        changelog_archive_paths=archive_paths_for,
        changelog_section_has_entries=release_section_has_entries,
        rf_archive_status=rf_archive_status,
        has_archive_section=has_archive_section,
        folders_file=FOLDERS_FILE,
        constants_file=CONSTANTS_FILE,
        rf_file=RF_FILE,
        root=REPO_ROOT,
        guard_scripts=GUARD_SCRIPTS,
        timer=_timer,
        gate_workers=_gate_workers,
        exec_fn=_exec,
        stamp_file=GATE_STAMP_FILE,
        bench_stamp_file=BENCH_STAMP_FILE,
    )
    return _gate.run_gate(args, ctx, runner=runner)


# ─────────────────────────── CLI ───────────────────────────


def main(argv: list[str] | None = None) -> int:
    return run_cli(
        argv,
        {
            "check": cmd_check,
            "prepare": cmd_prepare,
            "archive": cmd_archive,
            "archive-init": cmd_archive_init,
            "refresh": cmd_refresh,
            "evolution": cmd_evolution,
            "gate": cmd_gate,
            "publish": cmd_publish,
            "devbump": cmd_devbump,
        },
        reset_timer=_reset_timer,
        finish_timing=_finish_timing,
        release_error=ReleaseError,
    )


if __name__ == "__main__":
    sys.exit(main())
