"""测试：check-code-traces 日志统一守卫（非交互层 print() 检出）。

约束口径：``print()`` 仅允许出现在直接面向终端的交互呈现层（TUI/CLI 整目录 +
逐文件列举的进度/一次性检查报告/向导模块），其余生产模块须走 ``logging`` 落盘。
覆盖四类边界：
  - 检出：非豁免模块的 ``print()`` 调用（含函数体内嵌套、多行调用）
  - 豁免：交互呈现层目录与白名单文件
  - 不误伤：``sys.stdout.write``、``obj.print()``、字符串中的 "print("、非 .py 文件
  - 容错：语法错误文件静默跳过

另以结构断言钉住白名单自身不腐化：白名单条目必须真实存在，且当前含 ``print()``
的生产模块必须全部落在豁免域内（新增裸 print 即被本守卫拦截）。

测试通过脚本 import 复用扫描实现，不运行真实 CLI。
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
def discipline():
    """日志统一守卫实现（load_script 先把 scripts/ 注入 sys.path）。"""
    load_script("check-code-traces.py")
    from _traces_code import logging_discipline

    return logging_discipline


def _write_production(tmp_path: Path, rel: str, body: str) -> Path:
    """在临时仓库根下按仓库相对路径落一个生产模块。"""
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


class TestPrintCallDetection:
    """非豁免模块的 print() 必须被检出。"""

    def test_print_in_analysis_module_flagged(self, tmp_path, discipline) -> None:
        path = _write_production(
            tmp_path,
            "src/python/analysis/sample.py",
            "def run():\n    print('debug')\n",
        )
        hits = discipline._scan_print_calls(path, tmp_path)
        assert [h[1] for h in hits] == ["LOG"]
        assert hits[0][0] == 2, "行号应指向 print 调用所在行"

    def test_nested_print_inside_function_body_flagged(self, tmp_path, discipline) -> None:
        body = (
            "def outer():\n"
            "    def inner():\n"
            "        print('nested')\n"
            "    return inner\n"
        )
        path = _write_production(tmp_path, "src/python/core/deep.py", body)
        hits = discipline._scan_print_calls(path, tmp_path)
        assert len(hits) == 1
        assert hits[0][0] == 3

    def test_multiple_prints_reported_per_call(self, tmp_path, discipline) -> None:
        body = "print('a')\nprint('b')\n"
        path = _write_production(tmp_path, "src/python/report/writer.py", body)
        hits = discipline._scan_print_calls(path, tmp_path)
        assert [h[0] for h in hits] == [1, 2]

    def test_report_layer_print_flagged(self, tmp_path, discipline) -> None:
        """报告层属非交互域（仅进度/一次性报告模块豁免）。"""
        path = _write_production(
            tmp_path,
            "src/python/report/html_writer.py",
            "print('should be logging')\n",
        )
        assert discipline._scan_print_calls(path, tmp_path) != []


class TestPrintExemptions:
    """交互呈现层与白名单文件不检出。"""

    def test_tui_layer_exempt(self, tmp_path, discipline) -> None:
        path = _write_production(tmp_path, "src/python/tui/tui_menu.py", "print('menu')\n")
        assert discipline._scan_print_calls(path, tmp_path) == []

    def test_cli_layer_exempt(self, tmp_path, discipline) -> None:
        path = _write_production(tmp_path, "src/python/cli/cli.py", "print('usage')\n")
        assert discipline._scan_print_calls(path, tmp_path) == []

    @pytest.mark.parametrize(
        "rel",
        [
            "src/python/report/progress.py",
            "src/python/report/cli_progress.py",
            "src/python/report/privacy_notice.py",
            "src/python/core/check_sources.py",
            "src/python/doctor.py",  # 不在白名单的真实路径（反向用例）
        ],
    )
    def test_whitelist_membership_decides(self, tmp_path, discipline, rel) -> None:
        """白名单内文件豁免；非白名单单文件路径（doctor 根层）仍须检出。"""
        path = _write_production(tmp_path, rel, "print('x')\n")
        exempt = rel in discipline._PRINT_EXEMPT_FILES
        hits = discipline._scan_print_calls(path, tmp_path)
        assert (hits == []) is exempt


class TestPrintFalsePositives:
    """非 print() 调用与非法扫描域不得误报。"""

    def test_stdout_write_not_flagged(self, tmp_path, discipline) -> None:
        body = "import sys\nsys.stdout.write('x')\n"
        path = _write_production(tmp_path, "src/python/core/quiet.py", body)
        assert discipline._scan_print_calls(path, tmp_path) == []

    def test_method_named_print_not_flagged(self, tmp_path, discipline) -> None:
        path = _write_production(
            tmp_path,
            "src/python/core/objcall.py",
            "obj.print('x')\n",
        )
        assert discipline._scan_print_calls(path, tmp_path) == []

    def test_print_inside_string_not_flagged(self, tmp_path, discipline) -> None:
        path = _write_production(
            tmp_path,
            "src/python/core/literal.py",
            "MSG = \"print('not a call')\"\n",
        )
        assert discipline._scan_print_calls(path, tmp_path) == []

    def test_test_layer_not_flagged(self, tmp_path, discipline) -> None:
        """测试夹具打印不在纪律内（仅约束 src/python 生产层）。"""
        path = _write_production(tmp_path, "src/test/unit/test_x.py", "print('debug')\n")
        assert discipline._scan_print_calls(path, tmp_path) == []

    def test_non_python_file_not_flagged(self, tmp_path, discipline) -> None:
        path = _write_production(tmp_path, "src/python/static/app.js", "print('x')\n")
        assert discipline._scan_print_calls(path, tmp_path) == []

    def test_syntax_error_tolerated(self, tmp_path, discipline) -> None:
        path = _write_production(tmp_path, "src/python/core/broken.py", "def (:\n    print('x')\n")
        assert discipline._scan_print_calls(path, tmp_path) == []


class TestWhitelistIntegrity:
    """白名单本身不腐化：条目存在 + 现有 print 全部落在豁免域。"""

    def test_whitelisted_files_exist(self, discipline) -> None:
        from src.python.core.constants import PROJECT_ROOT

        root = Path(PROJECT_ROOT)
        missing = [rel for rel in sorted(discipline._PRINT_EXEMPT_FILES) if not (root / rel).is_file()]
        assert missing == [], f"白名单条目应指向真实文件：{missing}"

    def test_current_print_sites_all_within_exempt_domain(self, discipline) -> None:
        """当前生产层含 print() 的文件必须全部被豁免域覆盖（否则守护基线不自洽）。"""
        import ast

        from src.python.core.constants import PROJECT_ROOT

        root = Path(PROJECT_ROOT)
        offenders = []
        for path in (root / "src" / "python").rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            has_print = any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
                for node in ast.walk(tree)
            )
            if not has_print:
                continue
            rel = path.relative_to(root).as_posix()
            if not discipline._is_print_exempt(rel):
                offenders.append(rel)
        assert offenders == [], f"这些模块含 print() 却不在豁免域，应改用 logging：{offenders}"
