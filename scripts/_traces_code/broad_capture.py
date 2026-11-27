"""宽捕获抑制形态守卫（check-code-traces 的 CAPTURE 扫描支路）。

纪律源：`pyproject.toml` 的 `[tool.ruff.lint]` 口径——`select` 含 `BLE001`，必留的
宽捕获抑制一律写成 `# noqa: BLE001 — <理由>`。散文形态（只写一句「有意宽捕获：…」
而不挂 noqa）与 ruff 脱钩：规则真命中时 CI 红在 BLE001，抑制空转时红在 RUF100——
两种失败都得等 CI 才暴露，而注释读起来却像「已经声明过抑制」，评审时最容易被放过。
故本支路只认一种形态：`noqa: BLE001` + 破折号理由；散文形态逐行报 CAPTURE。

边界：只判 `src/python/**` 与 `scripts/**` 的 `.py` 注释（守卫面判据由 scan_file 统一
给出，与 `pragma: no cover` 支路同一道门）；`src/test` 的抑制面由 `per-file-ignores`
豁免，不入此规则。判定词是本仓表达「有意抑制宽捕获」的口径词（见 `_PROSE_MARKER`）。
同义但不同语序的表述（如「宽捕获后按判据重试」）不属该标记——那类命中本就由上抛构成，
BLE001 不会命中，写 noqa 反被 RUF100 判空转。
"""

from __future__ import annotations

from pathlib import Path

from _traces_code.extract import _iter_comment_lines

#: 「有意抑制宽捕获」的口径词：出现即表示作者主张「此处抑制是故意的」，
#: 该主张必须以 `noqa: BLE001` 落地才可被 RUF100/BLE001 双向校验。
_PROSE_MARKER = "有意宽捕获"

#: 合规形态（`noqa` 指令 + 规则码）
_NOQA_FORM = "noqa: BLE001"


def _scan_broad_capture_prose(fpath: Path) -> list[tuple[int, str, str, str]]:
    """扫描单文件的散文形态宽捕获抑制：有口径词而无 `noqa: BLE001` 即报 CAPTURE。"""
    if fpath.suffix != ".py":
        return []
    hits: list[tuple[int, str, str, str]] = []
    for lineno, ctext in _iter_comment_lines(fpath):
        if _PROSE_MARKER not in ctext or _NOQA_FORM in ctext:
            continue
        hits.append(
            (
                lineno,
                "CAPTURE",
                "散文形态宽捕获抑制（须改写为 # noqa: BLE001 — <理由>）",
                ctext.strip()[:120],
            )
        )
    return hits
