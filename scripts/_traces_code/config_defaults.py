"""配置默认值单源守卫（check-code-traces 的 AST 级 DEFAULTDUP 扫描支路）。

约束口径：配置项的**缺省值只有一份**，住在 `config/_config_defaults.py`、
`config/_llm_settings_defaults.py`、`config/_llm_providers_defaults.py` 三张
默认值表里；读取侧一律走 `get_default()` / `get_llm_setting_default()` 等
单一入口，**不得自带一份与默认表同值的字面量兜底**。理由：字面量兜底与默认
表是两个事实位，改默认值时必然漏改其一，症状是「配置文件里没写这个键，却
拿到旧值」，且随读取点增加而扩散（同类问题已在缓存/报告/问答多处复发）。

判定方式：AST 扫描生产代码中的 `x.get("<键>", <字面量>)` 调用，键与字面量
同时与默认表某条 `(键, 值)` 完全一致即命中（值按类型比较，`True` 与 `1`
不互认）。默认值表自身与测试不在扫描域内——前者是事实位，后者本就该
断言字面量。

新默认值表加入扫描域须在这一处登记（`_DEFAULT_TABLE_FILES`），不得在
扫描逻辑里就地判断。
"""

from __future__ import annotations

import ast
from pathlib import Path

#: 默认值事实位（相对仓库根，POSIX 形态）：这三份之外的"默认值"都不合法
_DEFAULT_TABLE_FILES = (
    "src/python/config/_config_defaults.py",
    "src/python/config/_llm_settings_defaults.py",
    "src/python/config/_llm_providers_defaults.py",
)

#: 扫描域前缀（只约束生产代码；测试断言字面量属正常用法）
_SCAN_PREFIX = "src/python/"

#: 默认值对缓存（repo_root 字符串 → {(键, 值字面量)}）
_PAIRS_CACHE: dict[str, frozenset[tuple[str, str]]] = {}


def _rel_posix(fpath: Path, repo_root: Path) -> str:
    """仓库相对 POSIX 路径（不在仓库内时退回绝对形态，避免误判豁免）。"""
    try:
        return fpath.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except ValueError:
        return fpath.as_posix()


def _literal_value(node: ast.expr) -> tuple[str, bool]:
    """把 AST 节点归一为（比较用字面量, 是否标量常量）。

    只认编译期常量（str/int/float/bool/None）：默认表里的路径拼接、函数调用
    等运行期表达式不参与比较（它们本就不可能被字面量兜底复制）。
    """
    if not isinstance(node, ast.Constant):
        return "", False
    value = node.value
    if value is None or isinstance(value, (str, int, float, bool)):
        return repr(value), True
    return "", False


def _collect_default_pairs(repo_root: Path) -> frozenset[tuple[str, str]]:
    """汇总三张默认值表的 `(键, 值)` 对（按仓库根缓存，单轮扫描只解析一次）。"""
    cache_key = str(Path(repo_root).resolve())
    cached = _PAIRS_CACHE.get(cache_key)
    if cached is not None:
        return cached

    pairs: set[tuple[str, str]] = set()
    for rel_path in _DEFAULT_TABLE_FILES:
        path = Path(repo_root) / rel_path
        if not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError, OSError, ValueError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key_node, value_node in zip(node.keys, node.values, strict=False):
                key_lit, key_ok = _literal_value(key_node) if key_node is not None else ("", False)
                if not key_ok or not key_lit.startswith(("'", '"')):
                    continue
                value_lit, value_ok = _literal_value(value_node)
                if value_ok:
                    pairs.add((ast.literal_eval(key_lit), value_lit))
    result = frozenset(pairs)
    _PAIRS_CACHE[cache_key] = result
    return result


def _scan_config_default_fallbacks(fpath: Path, repo_root: Path) -> list[tuple[int, str, str, str]]:
    """扫描单文件里「与默认表同值的字面量兜底」，返回 [(行号, 分类, 说明, 调用片段)]。"""
    if fpath.suffix.lower() != ".py":
        return []
    rel_path = _rel_posix(fpath, repo_root)
    if not rel_path.startswith(_SCAN_PREFIX) or rel_path in _DEFAULT_TABLE_FILES:
        return []

    pairs = _collect_default_pairs(repo_root)
    if not pairs:
        return []
    try:
        tree = ast.parse(fpath.read_text(encoding="utf-8-sig"), filename=str(fpath))
    except (SyntaxError, UnicodeDecodeError, OSError, ValueError):
        return []

    hits: list[tuple[int, str, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "get" or len(node.args) < 2:
            continue
        key_lit, key_ok = _literal_value(node.args[0])
        if not key_ok or not key_lit.startswith(("'", '"')):
            continue
        value_lit, value_ok = _literal_value(node.args[1])
        if not value_ok:
            continue
        key = ast.literal_eval(key_lit)
        if (key, value_lit) not in pairs:
            continue
        hits.append(
            (
                node.lineno,
                "DEFAULTDUP",
                "配置默认值重复兜底（改默认表不会跟随；改走 get_default()/get_llm_setting_default()）",
                f'get("{key}", {value_lit})',
            )
        )
    return hits
