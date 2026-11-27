"""测试：散文形态宽捕获抑制守卫（口径词无 `noqa: BLE001` 即报 CAPTURE）。

口径来源：`pyproject.toml` 的 ruff 规则口径——抑制宽捕获只认 `# noqa: BLE001 — <理由>`，
散文理由（只写口径词、不挂 noqa）与 BLE001/RUF100 脱钩，无人校验其是否真在跑。
本文件锁四侧：散文形态 → finding；noqa 形态 → 放行；无口径词 → 放行；非 .py → 不参判。
"""

from __future__ import annotations

import pytest

from src.test._script_loader import load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(name="capture_guard")
def fixture_capture_guard():
    """宽捕获形态守卫模块（先加载薄 CLI 以接入 `scripts/` 的 sys.path）。"""
    load_script("check-code-traces.py")
    return load_script("_traces_code/broad_capture.py", module_name="_traces_code_broad_capture")


def _write_source(tmp_path, handler_line: str):
    """造一个带 ``except`` 行内注释的样例源文件，返回（文件, 注释行号）。"""
    body = ["def f():", "    try:", "        return 1", f"    {handler_line}", "        return 0"]
    source = tmp_path / "sample.py"
    source.write_text("\n".join(body) + "\n", encoding="utf-8")
    return source, body.index(f"    {handler_line}") + 1


class TestBroadCaptureProseGuard:
    def test_prose_form_without_noqa_is_a_finding(self, capture_guard, tmp_path):
        marker = capture_guard._PROSE_MARKER
        source, lineno = _write_source(tmp_path, f"except Exception:  # {marker}：降级即可")
        hits = capture_guard._scan_broad_capture_prose(source)
        assert [(line, cat) for line, cat, _desc, _text in hits] == [(lineno, "CAPTURE")]

    def test_noqa_form_is_accepted(self, capture_guard, tmp_path):
        marker = capture_guard._PROSE_MARKER
        source, _lineno = _write_source(tmp_path, f"except Exception:  # noqa: BLE001 — {marker}：降级即可")
        assert capture_guard._scan_broad_capture_prose(source) == []

    def test_comment_without_marker_is_accepted(self, capture_guard, tmp_path):
        """不主张「有意抑制」的注释（如降级契约说明）不在本规则内。"""
        source, _lineno = _write_source(tmp_path, "except Exception:  # 默认吞异常返回 None")
        assert capture_guard._scan_broad_capture_prose(source) == []

    def test_non_python_file_is_skipped(self, capture_guard, tmp_path):
        source = tmp_path / "sample.sh"
        source.write_text(f"# {capture_guard._PROSE_MARKER}：样例\n", encoding="utf-8")
        assert capture_guard._scan_broad_capture_prose(source) == []
