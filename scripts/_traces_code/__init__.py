"""check-code-traces 实现包（check-code-traces.py 薄 CLI 的持有者）。

模块划分：
  - config     扫描域配置（REPO_ROOT/SCAN_DIRS/SKIP_FILES/_is_tool_self）
  - patterns   模式表（PATTERNS/IDENTIFIER_PATTERNS/EXCLUDE_LINE）+ 行级豁免
  - exemptions 章节/轮次计数豁免（与 check-doc-traces 共用，原 _traces_common）
  - extract    注释抽取（per-language）与标识符提取
  - scan       scan_file 调度（四支路汇聚）
  - layers     core 反向依赖 AST 守卫
  - logging_discipline 日志统一 AST 守卫（print() 仅限交互呈现层 + 日志器名称须为 "invest"）
  - config_defaults 配置默认值单源 AST 守卫（禁止与默认表同值的字面量兜底）
  - numeric_sum 浮点求和口径 AST 守卫（均值/方差须 math.fsum，禁用内建 sum 朴素累加）
  - broad_capture 宽捕获抑制形态守卫（散文「有意宽捕获」不挂 noqa: BLE001 即报 CAPTURE）
  - pragma_exemptions `pragma: no cover` 豁免清单校验（覆盖率口径债防增长）
"""

from __future__ import annotations

from _traces_code.config import (  # noqa: F401
    REPO_ROOT,
    RULE_CARRIER_DIRS,
    RULE_CARRIER_FILES,
    SCAN_DIRS,
    SKIP_FILES,
    _is_tool_self,
)
from _traces_code.broad_capture import (  # noqa: F401
    _PROSE_MARKER,
    _scan_broad_capture_prose,
)
from _traces_code.config_defaults import (  # noqa: F401
    _DEFAULT_TABLE_FILES,
    _collect_default_pairs,
    _scan_config_default_fallbacks,
)
from _traces_code.exemptions import (  # noqa: F401
    _COMPILED_CHAPTER_EXCLUDE,
    _COMPILED_ROUND_EXCLUDE,
    _chapter_excludes,
    _is_chapter_excluded,
    _is_round_excluded,
    _round_excludes,
)
from _traces_code.extract import (  # noqa: F401
    _html_comment_lines,
    _iter_comment_lines,
    _iter_identifiers,
    _js_comment_lines,
    _js_identifier_names,
    _py_comment_lines,
    _py_identifier_names,
    _shell_comment_lines,
)
from _traces_code.layers import (  # noqa: F401
    _CORE_LAYERING_EXEMPT_FILES,
    _UPPER_PACKAGES,
    _scan_core_layering,
)
from _traces_code.logging_discipline import (  # noqa: F401
    _PRINT_EXEMPT_DIR_PREFIXES,
    _PRINT_EXEMPT_FILES,
    _is_print_exempt,
    _scan_print_calls,
)
from _traces_code.numeric_sum import (  # noqa: F401
    EXCEPTIONS_FILE as FLOAT_SUM_EXCEPTIONS_FILE,
    RULE_KEY as FLOAT_SUM_RULE_KEY,
    _scan_float_sum,
    audit_exceptions as audit_float_sum_exceptions,
    load_exceptions as load_float_sum_exceptions,
)
from _traces_code.patterns import (  # noqa: F401
    _COMPILED_DASH_EXCLUDE,
    _COMPILED_EXCLUDE,
    _COMPILED_IDENTIFIER_PATTERNS,
    _COMPILED_MAGIC_EXCLUDE,
    _COMPILED_PATTERNS,
    _COMPILED_UNDER_EXCLUDE,
    _PATTERNS_PREFILTER,
    _TASK_ID_RE,
    _TEST_META_COMPILED,
    _dash_excludes,
    _is_dash_excluded,
    _is_excluded,
    _is_magic_match_excluded,
    _is_under_excluded,
    _magic_excludes,
    _under_excludes,
    EXCLUDE_LINE,
    IDENTIFIER_PATTERNS,
    PATTERNS,
    TEST_META_EXCLUDE,
)
from _traces_code.scan import (  # noqa: F401
    _scan_identifiers,
    scan_file,
)
from _traces_code.pragma_exemptions import (  # noqa: F401
    PRAGMA_EXEMPTION_DOC,
    _load_exemptions,
    _scan_pragma_no_cover,
)
