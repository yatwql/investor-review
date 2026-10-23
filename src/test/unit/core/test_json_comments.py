"""``core/json_comments`` 叶子模块契约：注释剥离、统一解析入口、无向上依赖。"""

from __future__ import annotations

import ast
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest

from src.python.core.json_comments import load, loads, strip_json_comments

pytestmark = pytest.mark.unit_core

_CORE_DIR = Path(__file__).resolve().parents[4] / "src" / "python" / "core"


@pytest.mark.unit
class TestStripJsonComments:
    def test_line_and_block_comments_removed(self):
        text = '// 分类：行情\n{\n  "a": 1, /* 行尾块注释 */\n  "b": 2\n}\n'
        assert loads(text) == {"a": 1, "b": 2}

    def test_comment_markers_inside_strings_preserved(self):
        text = '{"url": "http://x//y", "glob": "a/*b*/c", "note": "含 // 与 /* */"}'
        assert loads(text) == {"url": "http://x//y", "glob": "a/*b*/c", "note": "含 // 与 /* */"}

    def test_escaped_quote_does_not_end_string(self):
        text = '{"k": "a\\"// not comment"}'
        assert loads(text) == {"k": 'a"// not comment'}

    def test_newline_inside_comment_kept(self):
        stripped = strip_json_comments('{\n  "a": 1 // 说明\n}\n')
        assert stripped.count("\n") == 3
        assert "说明" not in stripped

    def test_load_from_file_object(self):
        assert load(StringIO('// 头注释\n{"x": true}\n')) == {"x": True}


@pytest.mark.unit
class TestLeafModuleBoundary:
    """叶子模块只依赖标准库；core/logger.py 不导入 config 包（依赖不成环）。"""

    def test_json_comments_imports_stdlib_only(self):
        tree = ast.parse((_CORE_DIR / "json_comments.py").read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
        assert imported <= {"__future__", "json", "typing"}, imported

    def test_import_does_not_pull_config_package(self):
        code = "import sys; import src.python.core.json_comments as m; print('src.python.config' in sys.modules)"
        out = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(_CORE_DIR.parents[2]),
        )
        assert out.stdout.strip() == "False"

    def test_logger_module_does_not_import_config(self):
        tree = ast.parse((_CORE_DIR / "logger.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "config" in node.module:
                raise AssertionError(f"core/logger.py 不得导入 config：{node.module}")
            if isinstance(node, ast.Import):
                assert all("config" not in alias.name for alias in node.names)
