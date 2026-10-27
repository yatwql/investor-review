#!/usr/bin/env python3
"""文档与实现一致性检查（doc-code drift check）—— 文档里写死的「事实」与代码/配置文件/文件系统逐条对账。

背景：文档中的**计数、清单、默认值、目录树、统计表**是易漂移的「事实断言」——
代码里加了开关/章节/文件，文档数字不动就静默失真。本脚本把这类断言与权威源绑定，
逐条比对，使漂移在提交前暴露（与 check-doc-traces 的「历史痕迹」检查互补：
那边管「不该写的内容」，这边管「写了但与实现不符的内容」）。

二十一项检查（权威源 → 受检文档）：
  1.  报告章节表        core/report_section_registry.py `_REPORT_SECTION_DEFAULT` → manuals/reports-instruction.md
      （含「可见性规则总览」表 `type` 行：文档 type 集合 ↔ 注册表 type 集合双向对账）
  2.  章节数量断言      同上（`页签编号 1~N` / `默认顺序（N 项` / `返回 result（N 项` / `N 个报告章节`）→ 全库文档
  3.  功能开关表        config/features.py `feature_switch_registry`    → manuals/how-to-config.md
  4.  开关分组计数断言  同上（四组连写链 `呈现与体验 A / 分析增强 B / 独立章节 C / 机制与诊断 D`、单组 `组名（N 项`（含加粗组名）、`共/提供 N 项开关`、`完整 N 项与分组清单`；另检旧三组名残留 `实验组/常规组/报告组/报告章节与增强组`，组名与残留名单以 `_GROUP_DOC_NAMES`/`_RETIRED_GROUP_NAMES` 注册表派生为真值）→ 全库文档
  5.  开关默认值断言    同上（`` `flag` `` 后紧随「默认开/关」）          → 全库文档
  6.  配置标量默认值表   config/_config_defaults.py `_DEFAULT_CONFIG`   → manuals/how-to-config.md + how-to-config-fields.md
  7.  LLM 默认参数表     config/_llm_settings_defaults.py + 缓存 TTL 注册表 → managements/llm-technical.md
  8.  TUI 面板编号       `tui/handlers_config.py` 的派生规则（LLM 可见模块 + 作用域四组顺序连续编号）→ manuals/how-to-use-tui-menu.md
  9.  目录树           文件系统实测（src/、scripts/、docs/{managements,manuals,plan}）+ 版本目录块升序 → managements/folders.md
  10. 项目统计表        文件系统实测（文件数/行数）+ 可选 pytest 收集数 → managements/folders.md
  11. 测试覆盖计数表    `scripts/test-collect-coverage.py` 快照 → managements/test-coverage.md（仅 `--with-test-count`）
  12. 归档索引完整性    changelog / plan / review-findings 的「归档」索引 ↔ 归档目录 `archived_*` 文件（双向）
  13. 管理文档分区纪律  未完成/已解决/已归档三分区互斥 + 「开发期已修复」节须在已解决区（节归属）；现行 changelog 只允许一个 `-dev` 段头
  14. Extended Thinking 支持矩阵  手册对比表/「仅」式枚举/默认开思考提示 ↔ `llm/api_base` 前缀名单
  15. Provider Chain 降级表  `fetcher/chain.py` `_DEFAULT_CHAINS` → manuals/datasource-reliability.md（逐链双向）
  16. 守护清单同源        developer-guide P0/P2 门禁块 + ci.yml guards steps + CLAUDE.md/testplan.md 清单 + .githooks/pre-commit（五处）`check-*.py --ci` 引用集合两两一致
  17. 章节-区块矩阵      区块注册表三向对账（文档行 ↔ 注册表逐列 / 实现提取集合） → managements/technical.md §4.22
  18. 手册菜单块一致性  双手册主菜单 code block（键集合/标签头）→ tui/tui_menu.py MENU_ITEMS；
      正文「菜单 `X`」引用须为主菜单键（`[D]` 二级选项 C/F/O/M 须写作「菜单 `D` → `C`」）；
      全文档「返回主菜单」行键=0 不变量（返回键全局统一，结构化行校验/prose 豁免）
  19. 需求菜单表        requirements.md §3.2 菜单表（键集合/分组标题/组内顺序）→ tui/tui_menu.py MENU_ITEMS + MENU_GROUPS（历史漂移：组重排未跟、M/Q 整行缺失、缓存编号错）
  20. 迁档占位↔归档节    review-findings「已随 vX.Y.Z 发布迁入」占位 ↔ archived_review-findings.{X.Y}.x.md 含该版本二级标题归档节（防占位已写、归档正文缺失）
  21. 树描述计数禁令    folders.md 目录树描述禁写「阿拉伯数字+量词」易漂移计数（docs/archive 记录域豁免；中文数词设计常量不入检）

按设计豁免的历史记录文档：`changelog.md` / `review-findings.md`（会如实引用旧数字作为变更记录）
与 `docs/archive/**`（版本快照）不参与第 2/4/5 项扫描。

用法：
  python scripts/check-doc-drift.py                  # 二十一项全查
  python scripts/check-doc-drift.py -v               # 详细输出（打印解析明细）
  python scripts/check-doc-drift.py --ci             # CI 模式：仅输出 文件:描述，退出码 2；
                                                      结论缓存：全集输入与逻辑指纹未变时逐字回放
                                                      （同树重复命中；--sync 写路径与
                                                      --with-test-count 独立输出面不缓存）
  python scripts/check-doc-drift.py --with-test-count # 附带 pytest 收集，核对「测试用例数」与 test-coverage.md 计数表

退出码：
  0 — 全部一致
  2 — 发现不一致（逐条列出 文件:描述，可直接按提示改）

本文件为入口：仅保留 CLI 与编排（`run_checks` / `main`），检查实现分置于
`_doc_drift/` 包内五个子模块（共享设施 / 文档格式族 / 目录树与统计 / 台账族 / 手册菜单块），
并在下方**原面 re-export** 全部检查函数与常量——调用方（含按路径加载本模块的单测）
零改动。
"""

from __future__ import annotations

import argparse
import contextlib
import io
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _shared.checklib import REPO_ROOT, add_common_args, rel, report  # noqa: E402,F401  # rel：单测直接访问 drift.rel
from _shared.checklib import conclusion_cache_load, conclusion_cache_save  # noqa: E402

if str(REPO_ROOT) not in sys.path:  # 允许任意 cwd 下运行
    sys.path.insert(0, str(REPO_ROOT))

# 原面 re-export：实现层用到的外部符号（单测直接访问 drift.<name>，故在此保留绑定）
from src.python.config.chapter_registry import (  # noqa: E402,F401
    BLOCK_LABELS,
    BLOCK_ORDER,
    SOURCE_FEATURES,
    chapter_number,
    chapter_numbers,
    chapter_registry,
    chapters_in_block,
    sub_item_numbers,
)
from src.python.config.features import (  # noqa: E402,F401
    feature_switch_registry,
    panel_option_numbers,
    switches_in_group,
)
from src.python.core.registry import _REPORT_SECTION_DEFAULT, get_llm_module_names  # noqa: E402,F401
from src.python.tui.tui_menu import filter_menu_llm_modules  # noqa: E402,F401
from _doc_drift._format_panels import (  # noqa: E402,F401  # 面板编号族（实现见 _doc_drift/_format_panels.py）
    _HOWTO_PANEL_HEADING,
    _PANEL_ROW,
    _SUB_ITEM_ROW,
    _GROUP_PANEL_RANGE,
    _BLOCK_PANEL_RANGE,
    _PANEL_KEY_MAP_ROW,
    check_panel_numbering,
)
from _doc_drift import (  # noqa: E402,F401  # 原面 re-export（实现见 _doc_drift/）
    _RELIABILITY_MD,
    check_chain_table,
    _README,
    _MANUALS,
    _MANAGEMENTS,
    _FOLDERS_MD,
    _HOW_TO_CONFIG_MD,
    _HOW_TO_CONFIG_FIELDS_MD,
    _REPORTS_MD,
    _TUI_MENU_MD,
    _DATASOURCE_MD,
    _LLM_TECHNICAL_MD,
    _TECHNICAL_MD,
    _TEST_COVERAGE_MD,
    _PLAN_MD,
    _CHANGELOG_MD,
    _REVIEW_FINDINGS_MD,
    _REQUIREMENTS_MD,
    _HISTORY_DOCS,
    _TREE_ROOTS,
    _GENERATED_DIRS,
    _GENERATED_SUFFIXES,
    _GENERATED_FILES,
    _GENERATED_PREFIXES,
    _is_generated,
    _scan_docs,
    _doc_section,
    _split_table_row,
    _first_number,
    _count,
    _values_equal,
    _collect_test_count,
    _collect_test_snapshot,
    _SECTION_COUNT_PATTERNS,
    parse_section_rows,
    check_section_table,
    check_visibility_type_rows,
    check_section_counts,
    _SWITCH_TABLE_START,
    _SWITCH_ROW,
    extract_switch_table,
    check_switch_table,
    _group_counts,
    _GROUP_CHAIN_COUNT,
    _GROUPED_COUNT,
    _GROUP_NAME_TO_KIND,
    _RETIRED_GROUP_NAMES,
    _GROUP_DOC_NAMES,
    _group_doc_name,
    _TOTAL_COUNT,
    _count_finding,
    check_switch_counts,
    _DEFAULT_CLAIM,
    check_switch_default_claims,
    _CONFIG_ROW,
    check_config_defaults,
    _LLM_ROW,
    _TTL_TABLE_ROW,
    _HOURS_ROW,
    _ttl_default,
    check_cache_ttl_tables,
    check_datasource_llm_ttl,
    check_llm_defaults,
    _TEST_COVERAGE_ROW,
    _COUNT_CELL,
    _COUNT_NAME_ALIAS,
    check_test_coverage_counts,
    _TREE_ENTRY,
    parse_tree_paths,
    _actual_files,
    check_dir_tree,
    check_tree_desc_counts,
    check_tree_version_order,
    _STATS_ROW,
    _stats_actual,
    check_project_stats,
    sync_project_stats,
    _BLOCK_MATRIX_TITLE,
    parse_block_matrix,
    check_block_matrix,
    _RF_ID,
    _PLAN_ID,
    _CHANGELOG_HEADER,
    _RF_ROW_ID,
    _PLAN_HEADING_ID,
    _PLAN_DONE_HEADING_ID,
    _ARCHIVE_INDEX_PAIRS,
    check_archive_index,
    check_migration_placeholders,
    audit_management_partitions,
    check_management_partitions,
    _THINKING_MANUAL,
    _THINKING_FAMILY_PREFIXES,
    _THINKING_FAMILY_LABELS,
    _thinking_families,
    check_thinking_support_matrix,
    find_guard_parity,
    check_guard_parity,
    guard_parity_sources,
    check_menu_blocks,
    check_menu_key_references,
    check_return_key_invariant,
    check_requirements_menu_table,
    parse_menu_block_lines,
    _HOW_TO_START_MD,
)


def run_checks(with_test_count: bool = False, docs: dict | None = None) -> list[str]:
    """跑全部检查，返回不一致描述列表（空 = 全部一致）。

    ``docs``：受检文档内容映射；None 时自行扫描（测试/独立调用形态）。
    CLI 入口扫描一次后传入，供 verbose 统计块复用（避免 -v 模式二次全量读）。
    """
    if docs is None:
        docs = _scan_docs()
    snapshot = _collect_test_snapshot(full_buckets=True) if with_test_count else {}
    findings: list[str] = []
    findings += check_section_table(docs[_REPORTS_MD])
    findings += check_visibility_type_rows(docs[_REPORTS_MD])
    findings += check_section_counts(docs)
    findings += check_switch_table(docs[_HOW_TO_CONFIG_MD])
    findings += check_switch_counts(docs)
    findings += check_switch_default_claims(docs)
    findings += check_config_defaults(docs[_HOW_TO_CONFIG_MD])
    # 字段详解拆篇后，B/C/E/G/M 等节的默认值表落在该文件，同受检（漏扫即静默失去漂移保护）
    findings += check_config_defaults(docs[_HOW_TO_CONFIG_FIELDS_MD])
    findings += check_llm_defaults(docs[_LLM_TECHNICAL_MD])
    findings += check_datasource_llm_ttl(docs[_DATASOURCE_MD])
    findings += check_cache_ttl_tables(
        (_TECHNICAL_MD, docs[_TECHNICAL_MD]),
        (_HOW_TO_CONFIG_MD, docs[_HOW_TO_CONFIG_MD]),
    )
    findings += check_panel_numbering(docs[_TUI_MENU_MD])
    findings += check_menu_blocks({_HOW_TO_START_MD: docs[_HOW_TO_START_MD], _TUI_MENU_MD: docs[_TUI_MENU_MD]})
    findings += check_menu_key_references(docs)
    findings += check_return_key_invariant(docs)
    findings += check_requirements_menu_table(docs[_REQUIREMENTS_MD])
    findings += check_dir_tree(docs[_FOLDERS_MD])
    findings += check_tree_version_order(docs[_FOLDERS_MD])
    findings += check_tree_desc_counts(docs[_FOLDERS_MD])
    findings += check_chain_table(docs[_RELIABILITY_MD])
    findings += check_archive_index()
    findings += check_migration_placeholders()
    findings += check_management_partitions()
    findings += check_thinking_support_matrix(docs.get(_THINKING_MANUAL))
    findings += check_guard_parity()
    findings += check_block_matrix(docs[_TECHNICAL_MD])
    findings += check_project_stats(docs[_FOLDERS_MD], with_test_count=with_test_count, snapshot=snapshot)
    if with_test_count:
        findings += check_test_coverage_counts(docs[_TEST_COVERAGE_MD], snapshot)
    return findings


def _cache_inputs() -> list[Path] | None:
    """结论缓存的输入指纹集：git tracked + 未跟踪（排除忽略）全集。

    doc-drift 结论依赖全仓（目录树结构/统计行数/注册表内容），必须用
    权威全集防漏；非 git 环境返回 None（跳过缓存，直接全量检查）。
    """

    def _ls(*extra: str) -> list[str] | None:
        proc = subprocess.run(
            ["git", "ls-files", *extra],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            return None
        return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]

    tracked = _ls()
    others = _ls("--others", "--exclude-standard")
    if tracked is None or others is None:
        return None
    return [REPO_ROOT / p for p in dict.fromkeys([*tracked, *others])]


def _run_checks_phase(args: argparse.Namespace) -> int:
    """扫描 + verbose 详细段 + report 统一输出，返回退出码。"""
    scanned_docs = _scan_docs() if args.verbose else None
    findings = run_checks(with_test_count=args.with_test_count, docs=scanned_docs)

    if args.verbose:
        docs = scanned_docs
        actual = _stats_actual()
        print(f"  受检文档 {len(docs)} 份（历史记录类 changelog/review-findings 不参与计数扫描）")
        print(
            f"  报告章节 {len(_REPORT_SECTION_DEFAULT)} 章 / 功能开关 {len(feature_switch_registry)} 项 {_group_counts()}"
        )
        print(f"  开关表解析 {len(extract_switch_table(docs[_HOW_TO_CONFIG_MD]))} 行")
        print(f"  目录树解析 {len(parse_tree_paths(docs[_FOLDERS_MD]))} 条 / 实测文件 {len(_actual_files())} 个")
        for label, (files, lines) in actual.items():
            print(f"    {label}: {files} 文件 / {lines} 行")
        block_rows, _ = parse_block_matrix(docs[_TECHNICAL_MD])
        print(f"  章节-区块矩阵解析 {len(block_rows)} 行")

    return report(
        findings,
        "[OK] 文档与实现一致性校验通过（章节/开关/默认值/面板编号/目录树/统计表/归档索引/分区纪律/占位归档节/树描述计数/Thinking 支持矩阵/章节-区块矩阵/手册菜单块均与代码一致）",
        ci=args.ci,
        fail_message="[!] 发现 {n} 处文档与实现不一致，须修正后提交",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="校验文档中的章节/开关/默认值/目录树/统计断言/归档索引/分区纪律/占位归档节/树描述计数/Thinking 支持矩阵/章节-区块矩阵/手册菜单块与代码、配置文件、文件系统的一致性",
    )
    add_common_args(parser)
    parser.add_argument(
        "--with-test-count",
        action="store_true",
        help="附带 pytest 收集快照，核对 folders.md 「测试用例」行与 test-coverage.md 各计数表（较慢）",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="把实测的统计表数字（文件数/行数/用例数）自动回写 folders.md（治理统计快照漂移；"
        "其余类目漂移仍需人工修正）——回写后继续跑全部检查，仍有不一致则退出码 2",
    )
    args = parser.parse_args()

    if args.sync:
        applied = sync_project_stats()
        if applied:
            for line in applied:
                print(f"[sync] {rel(_FOLDERS_MD)}: {line}")
        else:
            print("[sync] 统计表数字与实测一致，无需回写")
        # 同步后自动把回写结果加进 git 暂存区（pre-commit 钩子内使用），
        # 非 git 环境或未在提交流程中调用时忽略错误
        if applied:
            subprocess.run(["git", "add", str(_FOLDERS_MD)], cwd=REPO_ROOT, check=False)

    # 结论缓存（仅 --ci 且非 verbose/非 sync/非 with-test-count）：全集输入与逻辑指纹未变时
    # 逐字回放——同树重复（发布 gate → 提交钩子 / 重试）命中省全仓扫描；
    # --sync 为写路径不缓存，verbose 详细段输出不入缓存；--with-test-count 含
    # pytest 收集、输出面不同，不读不写缓存（防止跨模式回放丢核对段/污染结论）
    if args.ci and not args.verbose and not args.sync and not args.with_test_count:
        inputs = _cache_inputs()
        logic = [Path(__file__), *sorted((Path(__file__).resolve().parent / "_doc_drift").glob("*.py"))]
        if inputs is not None:
            cached = conclusion_cache_load("doc_drift", logic, inputs)
            if cached is not None:
                print("\n".join(cached["lines"]))
                sys.exit(int(cached["rc"]))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = _run_checks_phase(args)
        out = buf.getvalue()
        print(out, end="")
        if inputs is not None:
            conclusion_cache_save(
                "doc_drift",
                logic,
                inputs,
                {"findings": [] if rc == 0 else out.splitlines(), "lines": out.splitlines(), "rc": rc},
            )
        sys.exit(rc)
    sys.exit(_run_checks_phase(args))


if __name__ == "__main__":
    main()
