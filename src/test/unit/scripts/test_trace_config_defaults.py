"""测试：check-code-traces 配置默认值单源守卫（DEFAULTDUP）。

约束口径：配置缺省值只在三张默认值表里，读取侧不得自带与默认表同值的字面量
兜底（改默认表不会跟随）。覆盖：
  - 检出：与默认表同值同键的 ``.get(key, literal)``（含关键字参数调用）
  - 不误伤：改走 ``get_default()`` / 不同值的兜底 / 非 ``get`` 方法 / 非 .py
  - 豁免：默认值表自身（事实位）、测试目录、src/python 之外
  - 真实仓库：当前生产代码零 finding（收敛结果被钉住）

测试复用脚本扫描实现，不运行真实 CLI；默认值表按临时仓库根解析。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.test._script_loader import load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]

_DEFAULTS_TABLE = '''"""合成默认表。"""

_DEFAULT_CONFIG = {
    "news_top_count": 300,
    "enable_history": True,
    "history": {"lookback_days": 90},
}
'''


@pytest.fixture(scope="module")
def guard():
    """配置默认值守卫实现（load_script 先把 scripts/ 注入 sys.path）。"""
    load_script("check-code-traces.py")
    from _traces_code import config_defaults

    return config_defaults


def _repo(tmp_path: Path, body: str, rel: str = "src/python/sample.py") -> tuple[Path, Path]:
    """构造临时仓库：默认值表 + 一个待查模块。"""
    table = tmp_path / "src/python/config/_config_defaults.py"
    table.parent.mkdir(parents=True, exist_ok=True)
    table.write_text(_DEFAULTS_TABLE, encoding="utf-8")
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return tmp_path, target


class TestDuplicateFallbackDetection:
    """与默认表同值的字面量兜底必须被检出。"""

    def test_same_value_literal_flagged(self, guard, tmp_path: Path) -> None:
        root, target = _repo(tmp_path, 'val = cfg.get("news_top_count", 300)\n')
        hits = guard._scan_config_default_fallbacks(target, root)
        assert [h[1] for h in hits] == ["DEFAULTDUP"]
        assert "news_top_count" in hits[0][3]

    def test_bool_literal_flagged(self, guard, tmp_path: Path) -> None:
        root, target = _repo(tmp_path, 'val = cfg.get("enable_history", True)\n')
        assert len(guard._scan_config_default_fallbacks(target, root)) == 1

    def test_nested_default_key_flagged(self, guard, tmp_path: Path) -> None:
        """默认表嵌套段的标量同样参与比对（子段读取不得另抄一份）。"""
        root, target = _repo(tmp_path, 'val = cfg.get("lookback_days", 90)\n')
        hits = guard._scan_config_default_fallbacks(target, root)
        assert len(hits) == 1
        assert "lookback_days" in hits[0][3]


class TestNoFalsePositive:
    """合法写法与其它形态不得被误报。"""

    def test_accessor_call_not_flagged(self, guard, tmp_path: Path) -> None:
        root, target = _repo(tmp_path, 'val = cfg.get("news_top_count", get_default("news_top_count"))\n')
        assert guard._scan_config_default_fallbacks(target, root) == []

    def test_different_literal_not_flagged(self, guard, tmp_path: Path) -> None:
        root, target = _repo(tmp_path, 'val = cfg.get("news_top_count", 50)\n')
        assert guard._scan_config_default_fallbacks(target, root) == []

    def test_bool_int_not_interchangeable(self, guard, tmp_path: Path) -> None:
        """``True`` 与 ``1`` 不互认（类型敏感，避免把标志位当计数）。"""
        root, target = _repo(tmp_path, 'val = cfg.get("enable_history", 1)\n')
        assert guard._scan_config_default_fallbacks(target, root) == []

    def test_non_get_call_not_flagged(self, guard, tmp_path: Path) -> None:
        root, target = _repo(tmp_path, 'val = cfg.pop("news_top_count", 300)\n')
        assert guard._scan_config_default_fallbacks(target, root) == []

    def test_non_python_file_ignored(self, guard, tmp_path: Path) -> None:
        root, target = _repo(tmp_path, 'cfg.get("news_top_count", 300)\n', rel="src/python/sample.js")
        assert guard._scan_config_default_fallbacks(target, root) == []


class TestExemptions:
    """默认值表自身与扫描域外文件不检查。"""

    def test_defaults_table_itself_exempt(self, guard, tmp_path: Path) -> None:
        root, _ = _repo(tmp_path, 'val = cfg.get("news_top_count", 300)\n')
        table = root / "src/python/config/_config_defaults.py"
        assert guard._scan_config_default_fallbacks(table, root) == []

    def test_test_tree_not_scanned(self, guard, tmp_path: Path) -> None:
        root, target = _repo(tmp_path, 'val = cfg.get("news_top_count", 300)\n', rel="src/test/unit/sample.py")
        assert guard._scan_config_default_fallbacks(target, root) == []

    def test_syntax_error_file_tolerated(self, guard, tmp_path: Path) -> None:
        root, target = _repo(tmp_path, "def broken(:\n")
        assert guard._scan_config_default_fallbacks(target, root) == []


class TestRealRepoClean:
    """真实仓库当前无重复兜底（收敛结果由本用例钉住，回潮即红）。"""

    def test_production_code_has_no_duplicate_fallbacks(self, guard) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        findings: list[str] = []
        for path in sorted((repo_root / "src/python").rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            for lineno, _cat, _desc, text in guard._scan_config_default_fallbacks(path, repo_root):
                findings.append(f"{path.relative_to(repo_root)}:{lineno} {text}")
        assert findings == []
