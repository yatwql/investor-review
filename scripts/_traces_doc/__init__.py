"""文档结构性冗余（DUPLICATE）检查包：check-doc-traces.py 的扫描后端。

原面 re-export：测试与调用方仍按 `doc_traces.scan_structural_duplicates`
访问（实现见 _traces_doc.dedup）；独立成包保证单文件行数守红线与内聚。
"""

from _traces_doc.dedup import (
    _CARD_LINE_RE,
    _CHECKLIST_LINE_RE,
    _CODEISH_RE,
    _DUP_BLOCK_MIN_CHARS,
    _DUP_BLOCK_WINDOW,
    _DUP_MIN_LINE_LEN,
    _HEADING_RE,
    _SEPARATOR_LINE_RE,
    _in_dup_strict_scope,
    _is_codeish_sample,
    _window_is_structural,
    scan_structural_duplicates,
)

__all__ = [
    "_CARD_LINE_RE",
    "_CHECKLIST_LINE_RE",
    "_CODEISH_RE",
    "_DUP_BLOCK_MIN_CHARS",
    "_DUP_BLOCK_WINDOW",
    "_DUP_MIN_LINE_LEN",
    "_HEADING_RE",
    "_SEPARATOR_LINE_RE",
    "_in_dup_strict_scope",
    "_is_codeish_sample",
    "_window_is_structural",
    "scan_structural_duplicates",
]
