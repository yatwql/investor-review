"""测试：check-code-traces 扫描输入层（`_traces_code/extract.py`）——标识符与注释抽取。

覆盖：
  - 标识符抽取：`.py` 走 AST（函数/类/参数/`*args`/`**kwargs`/赋值目标/导入别名）、
    `.js`/`.mjs` 走声明正则、不参与扫描的扩展名返回空、读失败与语法错误静默跳过
  - 标识符命中：抽取出的名字交给 `_COMPILED_IDENTIFIER_PATTERNS` 分类（任务代号命中 IDENT）
  - 注释抽取分派：不支持的扩展名不参与；读失败静默跳过
  - `.sh`/`.ps1`/`.bat`/`.cmd`：shebang 不算注释、`<# #>` 块状态、`REM `/`::`、行内 ` #`
  - `.js`/`.mjs`：`//` 行注释、`/* */` 跨行块、行内注释、URL `://` 不误判
  - `.html`：`<!-- -->`、Jinja `{# #}`、CSS/JS `/* */` 三种注释与跨行状态
  - `.py`：`#` 行注释 + 行内注释 + 真正 docstring（代码字符串的收尾行不误判）、
    tokenize 失败静默返回

测试通过脚本 import 复用抽取实现，不运行真实 CLI、不扫描仓库。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from src.test._script_loader import load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(scope="module")
def extract():
    """抽取层实现（load_script 先把 scripts/ 注入 sys.path）。"""
    load_script("check-code-traces.py")
    from _traces_code import extract as extract_module  # pyright: ignore[reportMissingImports]  # scripts/ 由 load_script 注入 sys.path

    return extract_module


def _write(tmp_path: Path, name: str, body: str) -> Path:
    """在临时目录写一个源码文件（用于抽取层输入）。"""
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


class TestIdentifierExtraction:
    """标识符抽取：Python 走 AST，JS 走声明正则，其余不参与。"""

    def test_python_names_come_from_ast(self, extract, tmp_path):
        """函数/类/参数/`*args`/`**kwargs`/赋值目标/导入别名全部产出。"""
        src = _write(
            tmp_path,
            "sample.py",
            "import os.path as osp\n"
            "import json\n"
            "\n"
            "class Holder:\n"
            "    pass\n"
            "\n"
            "\n"
            "def worker(a, *rest, key=1, **extra):\n"
            "    target = a\n"
            "    return target, rest, key, extra\n",
        )

        names = {name for _lineno, name in extract._iter_identifiers(src)}
        assert {"Holder", "worker", "a", "rest", "key", "extra", "target", "osp", "json"} <= names

    def test_javascript_declarations_are_extracted(self, extract, tmp_path):
        """`.js` 的 const/let/var/function/class 声明名逐行产出。"""
        src = _write(
            tmp_path,
            "panel.js",
            "const alpha = 1;\nlet beta;\nvar gamma = 2;\nfunction delta() {}\nclass Epsilon {}\n",
        )

        pairs = list(extract._iter_identifiers(src))
        assert [name for _lineno, name in pairs] == ["alpha", "beta", "gamma", "delta", "Epsilon"]
        assert [lineno for lineno, _name in pairs] == [1, 2, 3, 4, 5]

    def test_mjs_suffix_also_scanned(self, extract, tmp_path):
        """`.mjs` 与 `.js` 同口径（扫描 JS 声明）。"""
        src = _write(tmp_path, "module.mjs", "export const zeta = 1;\n")
        assert [name for _lineno, name in extract._iter_identifiers(src)] == ["zeta"]

    def test_unsupported_suffix_yields_nothing(self, extract, tmp_path):
        """不参与标识符扫描的扩展名（如 .md）产出为空。"""
        src = _write(tmp_path, "notes.md", "const alpha = 1;\n")
        assert list(extract._iter_identifiers(src)) == []

    def test_missing_file_is_skipped(self, extract, tmp_path):
        """文件不存在（OSError）静默跳过，不抛异常。"""
        assert list(extract._iter_identifiers(tmp_path / "absent.py")) == []

    def test_syntax_error_file_is_skipped(self, extract, tmp_path):
        """语法错误的 .py 静默跳过而不是让扫描整体失败。"""
        src = _write(tmp_path, "broken.py", "def broken(:\n    pass\n")
        assert list(extract._iter_identifiers(src)) == []

    def test_non_utf8_file_is_skipped(self, extract, tmp_path):
        """非 UTF-8 字节（解码失败）同样静默跳过。"""
        path = tmp_path / "latin.py"
        path.write_bytes(b"# \xff\xfe latin1 remark\nX1 = 1\n")
        assert list(extract._iter_identifiers(path)) == []

    def test_scan_identifiers_classifies_task_code_names(self, extract, tmp_path):
        """抽取层命中任务代号时按 IDENT 分类返回四元组（行号/分类/说明/标识符）。"""
        src = _write(
            tmp_path,
            "coded.py",
            "def plan18_hack():\n    pass\n\n\ndef semantic_helper():\n    pass\n",
        )

        hits = extract._scan_identifiers(src)
        assert [(lineno, cat, ident) for lineno, cat, _desc, ident in hits] == [(1, "IDENT", "plan18_hack")]

    def test_scan_identifiers_ignores_semantic_names(self, extract, tmp_path):
        """语义命名的标识符不产生任何命中（不误伤正常代码）。"""
        src = _write(tmp_path, "clean.py", "def resolve_parallel_level(level):\n    return level\n")
        assert extract._scan_identifiers(src) == []


class TestCommentDispatch:
    """注释抽取的分派与容错。"""

    def test_unsupported_suffix_yields_nothing(self, extract, tmp_path):
        """不支持的扩展名（如 .md）不参与注释扫描。"""
        src = _write(tmp_path, "readme.md", "<!-- 注释 -->\n")
        assert list(extract._iter_comment_lines(src)) == []

    def test_missing_file_is_skipped(self, extract, tmp_path):
        """文件不存在时静默跳过。"""
        assert list(extract._iter_comment_lines(tmp_path / "absent.sh")) == []

    def test_non_utf8_file_is_skipped(self, extract, tmp_path):
        """解码失败的文件静默跳过。"""
        path = tmp_path / "latin.sh"
        path.write_bytes(b"# \xff\xfe remark\n")
        assert list(extract._iter_comment_lines(path)) == []


class TestShellCommentLines:
    """`.sh` / `.ps1` / `.bat` / `.cmd` 注释抽取。"""

    def test_shell_line_and_inline_comments(self, extract, tmp_path):
        """`#` 整行注释与空白引导的行内注释都产出，URL 内的 `#` 不算注释。"""
        src = _write(
            tmp_path,
            "run.sh",
            "#!/bin/sh\n# 整行注释\necho hi  # 行内注释\ncurl https://example.test/page#frag\n",
        )

        lines = dict(extract._iter_comment_lines(src))
        assert lines[2] == "# 整行注释"
        assert lines[3] == "# 行内注释"
        assert 1 not in lines  # shebang 不是注释
        assert 4 not in lines  # URL 锚点不是注释

    def test_ps1_block_comment_state(self, extract, tmp_path):
        """PowerShell `<# #>` 块：开启行与后续行都算注释，闭合后回到普通行处理。"""
        src = _write(
            tmp_path,
            "task.ps1",
            "<#\n块注释首行\n块注释末行 #>\n# 单行注释\nWrite-Host ok  # 行内\n",
        )

        lines = dict(extract._iter_comment_lines(src))
        assert lines[1] == "<#"
        assert lines[2] == "块注释首行"
        assert lines[3] == "块注释末行 #>"
        assert lines[4] == "# 单行注释"
        assert lines[5] == "# 行内"

    def test_ps1_single_line_block_stays_open_only_when_unterminated(self, extract, tmp_path):
        """单行内闭合的 `<# ... #>` 不把后续行拖进块注释状态。"""
        src = _write(tmp_path, "one.ps1", "<# 单行块 #>\nWrite-Host ok\n")
        assert dict(extract._iter_comment_lines(src)) == {1: "<# 单行块 #>"}

    def test_batch_rem_and_double_colon(self, extract, tmp_path):
        """`.bat`/`.cmd` 的 `REM ` 与 `::` 两种注释写法都产出（大小写不敏感）。"""
        src = _write(
            tmp_path,
            "start.bat",
            "rem 首行说明\n:: 冒号注释\necho hi\n",
        )

        lines = dict(extract._iter_comment_lines(src))
        assert lines[1] == "首行说明"
        assert lines[2] == "冒号注释"
        assert 3 not in lines

    def test_batch_double_colon_via_cmd_suffix(self, extract, tmp_path):
        """`.cmd` 与 `.bat` 同口径。"""
        src = _write(tmp_path, "start.cmd", ":: 说明\n")
        assert dict(extract._iter_comment_lines(src)) == {1: "说明"}


class TestJsCommentLines:
    """`.js` / `.mjs` 注释抽取。"""

    def test_line_block_and_inline_comments(self, extract, tmp_path):
        """`//` 行注释、`/* */` 跨行块、行内注释三种都产出。"""
        src = _write(
            tmp_path,
            "app.js",
            "// 行注释\nconst a = 1; // 行内\n/* 块首\n块体\n块尾 */\nconst b = 2;\n",
        )

        lines = dict(extract._iter_comment_lines(src))
        assert lines[1] == "// 行注释"
        assert lines[2] == "// 行内"
        assert lines[3] == "/* 块首"
        assert lines[4] == "块体"
        assert lines[5] == "块尾 */"
        assert 6 not in lines

    def test_url_scheme_is_not_a_comment(self, extract, tmp_path):
        """`https://` 里的 `//` 不算注释（否则每条外链都被当注释扫）。"""
        src = _write(tmp_path, "net.mjs", 'const u = "https://example.test/a";\n')
        assert dict(extract._iter_comment_lines(src)) == {}

    def test_inline_block_comment_is_trimmed_to_marker_end(self, extract, tmp_path):
        """行内 `/* ... */` 只取到闭合标记为止，同行代码不计入注释文本。"""
        src = _write(tmp_path, "inline.js", "const a = 1; /* 备注 */ const b = 2;\n")
        assert dict(extract._iter_comment_lines(src)) == {1: "/* 备注 */"}

    def test_unterminated_inline_block_opens_block_state(self, extract, tmp_path):
        """行内 `/*` 未闭合时把后续行继续当注释。"""
        src = _write(tmp_path, "open.js", "const a = 1; /* 未闭合\n后续行\n尾 */\n")
        lines = dict(extract._iter_comment_lines(src))
        assert lines[1] == "/* 未闭合"
        assert lines[2] == "后续行"
        assert lines[3] == "尾 */"


class TestHtmlCommentLines:
    """`.html` 的 `<!-- -->` / `{# #}` / `/* */` 三种注释。"""

    def test_html_comment_single_and_multi_line(self, extract, tmp_path):
        """HTML 注释单行闭合与跨行都产出。"""
        src = _write(
            tmp_path,
            "page.html",
            "<!-- 单行 -->\n<!-- 跨行首\n跨行尾 -->\n<p>正文</p>\n",
        )

        lines = dict(extract._iter_comment_lines(src))
        assert lines[1] == "<!-- 单行 -->"
        assert lines[2] == "<!-- 跨行首"
        assert lines[3] == "跨行尾 -->"
        assert 4 not in lines

    def test_jinja_comment_single_and_multi_line(self, extract, tmp_path):
        """Jinja `{# #}` 注释单行与跨行都产出。"""
        src = _write(
            tmp_path,
            "tpl.html",
            "{# 单行 #}\n{# 跨行首\n跨行尾 #}\n",
        )

        lines = dict(extract._iter_comment_lines(src))
        assert lines[1] == "{# 单行 #}"
        assert lines[2] == "{# 跨行首"
        assert lines[3] == "跨行尾 #}"

    def test_css_block_comment_single_and_multi_line(self, extract, tmp_path):
        """内联 CSS/JS `/* */` 注释单行与跨行都产出。"""
        src = _write(
            tmp_path,
            "style.html",
            "/* 单行 */\n/* 跨行首\n跨行尾 */\n",
        )

        lines = dict(extract._iter_comment_lines(src))
        assert lines[1] == "/* 单行 */"
        assert lines[2] == "/* 跨行首"
        assert lines[3] == "跨行尾 */"

    def test_earliest_marker_wins_on_mixed_line(self, extract, tmp_path):
        """同一行出现多种注释起点时按最靠前的标记判定类型。"""
        src = _write(tmp_path, "mixed.html", "{# 先 {# #} 后 <!-- 不参与 --> #}\n")
        lines = dict(extract._iter_comment_lines(src))
        assert lines[1] == "{# 先 {# #}"

    def test_plain_html_line_yields_nothing(self, extract, tmp_path):
        """无注释的正文行不产出。"""
        src = _write(tmp_path, "plain.html", "<html><body>正文</body></html>\n")
        assert dict(extract._iter_comment_lines(src)) == {}


class TestPythonCommentLines:
    """`.py` 的 `#` 注释与真正 docstring。"""

    def test_line_and_inline_comments(self, extract, tmp_path):
        """`#` 整行与行内注释都产出（行内只取 `#` 之后）。"""
        src = _write(
            tmp_path,
            "mod.py",
            "# 模块注释\nvalue = 1  # 行内注释\ntext = 'has # inside string'\n",
        )

        lines = dict(extract._iter_comment_lines(src))
        assert lines[1] == "# 模块注释"
        assert lines[2] == "# 行内注释"
        assert 3 not in lines

    def test_real_docstring_lines_are_reported(self, extract, tmp_path):
        """模块/类/函数 docstring 按 AST 判定的行范围逐行产出。"""
        src = _write(
            tmp_path,
            "doc.py",
            '"""模块说明首行\n模块说明次行\n"""\n\n\ndef func():\n    """函数说明"""\n    return 1\n',
        )

        lines = dict(extract._iter_comment_lines(src))
        assert "模块说明首行" in lines[1]
        assert lines[2] == "模块说明次行"
        assert lines[3] == '"""'
        assert lines[7] == '"""函数说明"""'

    def test_code_string_tail_line_is_not_treated_as_docstring(self, extract, tmp_path):
        """多行代码字符串的收尾行不是 docstring——不能被计入注释（否则块状态泄漏）。"""
        src = _write(
            tmp_path,
            "assign.py",
            'payload = """\n正文行\n"""\ncount = 1\n',
        )

        lines = dict(extract._iter_comment_lines(src))
        assert lines == {}

    def test_unparsable_python_still_yields_comment_tokens(self, extract, tmp_path):
        """AST 解析失败（无 docstring 可判定）时仍按 tokenize 抽注释，不整体丢弃。"""
        src = _write(tmp_path, "bad.py", "# 前置注释\nreturn 1  # 行内\n")

        lines = dict(extract._iter_comment_lines(src))
        assert lines[1] == "# 前置注释"
        assert lines[2] == "# 行内"
