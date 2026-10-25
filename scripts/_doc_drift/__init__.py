"""`check-doc-drift` 内部实现包（入口 `scripts/check-doc-drift.py` 保留 CLI 与编排）。

拆分轴：共享设施（_shared）/ 文档格式族（_format）/ 目录树与统计（_tree）/ 台账族（_ledger）。
入口与原面 re-export 全部检查函数与常量，调用方（含单测按路径加载入口模块）零改动。
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from _doc_drift._format import (  # noqa: F401
    check_chain_table,
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
    check_llm_defaults,
    _DATASOURCE_LLM_ROW,
    check_cache_ttl_tables,
    check_datasource_llm_ttl,
    _TEST_COVERAGE_ROW,
    _COUNT_CELL,
    _COUNT_NAME_ALIAS,
    check_test_coverage_counts,
)
from _doc_drift._format_panels import (  # noqa: F401
    _HOWTO_PANEL_HEADING,
    _PANEL_ROW,
    _SUB_ITEM_ROW,
    _GROUP_PANEL_RANGE,
    _BLOCK_PANEL_RANGE,
    _PANEL_KEY_MAP_ROW,
    check_panel_numbering,
)
from _doc_drift._tree import (  # noqa: F401
    _TREE_ENTRY,
    parse_tree_paths,
    _iter_tree_entries,
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
)
from _doc_drift._ledger import (  # noqa: F401
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
)
from _doc_drift._guards import (  # noqa: F401
    find_guard_parity,
    check_guard_parity,
    guard_parity_sources,
)
from _doc_drift._shared import (  # noqa: F401
    _RELIABILITY_MD,
    _DATASOURCE_MD,
    _README,
    _MANUALS,
    _MANAGEMENTS,
    _FOLDERS_MD,
    _HOW_TO_CONFIG_MD,
    _REPORTS_MD,
    _TUI_MENU_MD,
    _HOW_TO_START_MD,
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
)

from _doc_drift._menu_blocks import (  # noqa: F401
    check_menu_blocks,
    check_menu_key_references,
    check_return_key_invariant,
    parse_menu_block_lines,
)

from _doc_drift._requirements_menu import check_requirements_menu_table  # noqa: F401
