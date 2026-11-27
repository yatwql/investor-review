"""`scripts/test-extract-failures.py` 报告解析与输出面覆盖。

该脚本是「测试红了之后第一步要跑」的取失败清单工具：解析错一条就会少给一个
失败用例名，`--summary`/`--json` 输出错则误导排查方向。既有用例已覆盖
`_find_json_blob` 的实体转义回归，这里补 `parse_report` 的归类口径、日志提取
与三条 HTML 回退路径、两种输出形态，以及 `main` 的端到端落点。
报告夹具用 tmp_path 现造，不依赖真实 `test-reports/`。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_SCRIPT = "test-extract-failures.py"


def _escape_json_for_attr(payload: dict) -> str:
    """按 pytest-html 的方式把 JSON 转义成可放进 `data-jsonblob` 属性的文本。"""
    raw = json.dumps(payload, ensure_ascii=False)
    return raw.replace("&", "&amp;").replace('"', "&#34;").replace(">", "&gt;").replace("<", "&lt;")


def _report_html(tests: dict, extra_body: str = "") -> str:
    blob = _escape_json_for_attr({"tests": tests})
    return f'<html><body><div id="data-container" data-jsonblob="{blob}"></div>{extra_body}</body></html>'


def _entry(result: str, *, log: str | None = None, duration: str = "0.01s") -> list[dict]:
    info: dict = {"result": result, "duration": duration}
    if log is not None:
        info["extras"] = [{"content": [{"log": log}]}]
    return [info]


@pytest.fixture(scope="module")
def extract_script():
    return load_script(_SCRIPT, module_name="test_extract_failures_report")


class TestParseReportSummary:
    """summary 归类口径：Failed/Error 进 failures，其余（含 xfailed/xpassed）计入通过。"""

    def test_counts_each_result_kind(self, extract_script, tmp_path):
        tests = {
            "a::t_pass": _entry("Passed"),
            "a::t_fail": _entry("Failed", log="boom"),
            "a::t_err": _entry("Error", log="setup failed"),
            "a::t_skip": _entry("Skipped"),
            "a::t_xfail": _entry("xfailed"),
            "a::t_xpass": _entry("xpassed"),
            "a::t_unknown": _entry("Something-New"),
        }
        path = tmp_path / "report.html"
        path.write_text(_report_html(tests), encoding="utf-8")

        result = extract_script.parse_report(str(path))

        assert result["summary"] == {
            "total": 7,
            "passed": 4,
            "failed": 1,
            "errors": 1,
            "skipped": 1,
        }
        assert [f["test_id"] for f in result["failures"]] == ["a::t_err", "a::t_fail"]
        assert [f["result"] for f in result["failures"]] == ["Error", "Failed"]

    def test_empty_entry_list_is_skipped_not_counted(self, extract_script, tmp_path):
        """pytest-html 偶有 `"id": []` 空条目——既不算通过也不算失败。"""
        path = tmp_path / "report.html"
        path.write_text(_report_html({"a::empty": [], "a::pass": _entry("Passed")}), encoding="utf-8")

        result = extract_script.parse_report(str(path))

        assert result["summary"]["total"] == 2
        assert result["summary"]["passed"] == 1
        assert result["failures"] == []

    def test_duration_is_carried_through(self, extract_script, tmp_path):
        path = tmp_path / "report.html"
        path.write_text(_report_html({"a::t": _entry("Failed", log="x", duration="1.23s")}), encoding="utf-8")
        assert extract_script.parse_report(str(path))["failures"][0]["duration"] == "1.23s"


class TestLogExtraction:
    """失败日志优先取 extras，缺失时回退到 HTML 结构；两条路都不能返回空。"""

    def test_log_taken_from_extras(self, extract_script, tmp_path):
        path = tmp_path / "report.html"
        path.write_text(_report_html({"a::t": _entry("Failed", log="assert 1 == 2")}), encoding="utf-8")
        assert "assert 1 == 2" in extract_script.parse_report(str(path))["failures"][0]["log"]

    def test_multiple_extras_are_joined(self, extract_script):
        info = {
            "extras": [
                {"content": [{"log": "第一段"}]},
                {"content": [{"log": "第二段"}, {"text": "非日志"}]},
            ]
        }
        assert extract_script._extract_log_text(info) == "第一段\n第二段"

    def test_extras_without_log_yields_empty_text(self, extract_script):
        assert extract_script._extract_log_text({"extras": [{"content": [{"text": "x"}]}]}) == ""
        assert extract_script._extract_log_text({}) == ""

    def test_log_falls_back_to_html_structure(self, extract_script, tmp_path):
        """extras 无日志时从 `<div class="log">…<pre>` 段落里抠出内容并去标签。"""
        body = (
            '<div class="log"><span>a::t</span><pre>E   AssertionError: &#34;x&#34; &gt; 1 &amp; 2 &lt; 3</pre></div>'
        )
        path = tmp_path / "report.html"
        path.write_text(_report_html({"a::t": _entry("Failed")}, extra_body=body), encoding="utf-8")

        log = extract_script.parse_report(str(path))["failures"][0]["log"]

        assert 'AssertionError: "x" > 1 & 2 < 3' in log
        assert "<pre>" not in log

    def test_log_fallback_stops_at_first_block_containing_test_id(self, extract_script):
        """回退检索按 test_id 定位日志块，且命中即停（不跨到后续无关日志段）。"""
        html = '<div class="log">a::t<pre>我的日志</pre></div><div class="log">other::case<pre>别人的日志</pre></div>'
        assert extract_script._extract_log_from_html(html, "a::t") == "我的日志"

    def test_log_fallback_returns_empty_when_no_matching_block(self, extract_script):
        assert extract_script._extract_log_from_html('<div class="log"><pre>x</pre></div>', "a::t") == ""


class TestPrinting:
    """两种输出形态：人类可读（可摘要）与 JSON（日志截尾以控体积）。"""

    def _result(self) -> dict:
        return {
            "summary": {"total": 3, "passed": 1, "failed": 1, "errors": 1, "skipped": 0},
            "failures": [
                {"test_id": "a::fail", "result": "Failed", "log": "line1\n\nline2", "duration": "0.1s"},
                {"test_id": "a::err", "result": "Error", "log": "", "duration": "0.2s"},
            ],
        }

    def test_print_report_detail_shows_symbols_and_indented_log(self, extract_script, capsys):
        extract_script.print_report(self._result(), detail=True)
        out = capsys.readouterr().out
        assert "=== 测试报告汇总 ===" in out
        assert "总计: 3" in out and "失败: 1" in out and "错误: 1" in out
        assert "[FAIL] a::fail" in out and "[ERR] a::err" in out
        assert "  line1" in out and "  line2" in out

    def test_print_report_summary_mode_omits_log_lines(self, extract_script, capsys):
        extract_script.print_report(self._result(), detail=False)
        out = capsys.readouterr().out
        assert "[FAIL] a::fail" in out
        assert "line1" not in out

    def test_print_report_clean_run_reports_ok(self, extract_script, capsys):
        extract_script.print_report(
            {"summary": {"total": 2, "passed": 2, "failed": 0, "errors": 0, "skipped": 0}, "failures": []}
        )
        assert "[OK] 无失败或错误" in capsys.readouterr().out

    def test_print_report_truncates_long_log_to_tail(self, extract_script, capsys):
        long_log = "HEAD-MARK\n" + "填充\n" * 300 + "TAIL-MARK"
        result = {
            "summary": {"total": 1, "passed": 0, "failed": 1, "errors": 0, "skipped": 0},
            "failures": [{"test_id": "a::t", "result": "Failed", "log": long_log, "duration": ""}],
        }
        extract_script.print_report(result, detail=True)
        out = capsys.readouterr().out
        assert "TAIL-MARK" in out
        assert "HEAD-MARK" not in out

    def test_print_json_keeps_tail_and_is_valid_json(self, extract_script, capsys):
        long_log = "HEAD-MARK" + "x" * 2000 + "TAIL-MARK"
        result = {
            "summary": {"total": 1, "passed": 0, "failed": 1, "errors": 0, "skipped": 0},
            "failures": [{"test_id": "a::t", "result": "Failed", "log": long_log, "duration": ""}],
        }
        extract_script.print_json(result)
        payload = json.loads(capsys.readouterr().out)
        log = payload["failures"][0]["log"]
        assert len(log) == 1000
        assert log.endswith("TAIL-MARK")
        assert "HEAD-MARK" not in log

    def test_print_json_keeps_short_log_intact(self, extract_script, capsys):
        result = {
            "summary": {"total": 1, "passed": 0, "failed": 1, "errors": 0, "skipped": 0},
            "failures": [{"test_id": "a::t", "result": "Failed", "log": "短日志", "duration": "0.1s"}],
        }
        extract_script.print_json(result)
        assert json.loads(capsys.readouterr().out)["failures"][0]["log"] == "短日志"


class TestResolveReportPath:
    """报告路径解析：显式路径优先，否则按候选顺序找最新的两份布局。"""

    def test_explicit_path_is_absolutised(self, extract_script):
        assert extract_script.resolve_report_path("some/report.html") == str(Path("some/report.html").resolve())

    @pytest.mark.parametrize(
        "existing",
        ["test-reports/latest/all/report.html", "test-reports/latest/report.html"],
    )
    def test_first_existing_candidate_wins(self, extract_script, monkeypatch, existing):
        seen: list[str] = []

        def fake_exists(path):
            seen.append(path.replace("\\", "/"))
            return path.replace("\\", "/").endswith(existing)

        monkeypatch.setattr(extract_script.os.path, "exists", fake_exists)
        resolved = extract_script.resolve_report_path(None)

        assert resolved.replace("\\", "/").endswith(existing)
        assert Path(resolved).is_absolute()
        # 命中即返回：不存在「找到还继续找」的扫描
        assert len(seen) == (1 if existing.endswith("all/report.html") else 2)


class TestMain:
    """`main` 端到端落点：位置参数被采信，`--summary`/`--json` 切换输出形态。"""

    def test_main_prints_detail_by_default(self, extract_script, monkeypatch, tmp_path, capsys):
        path = tmp_path / "report.html"
        path.write_text(_report_html({"a::t": _entry("Failed", log="assert nope")}), encoding="utf-8")
        monkeypatch.setattr(sys, "argv", [_SCRIPT, str(path)])

        extract_script.main()

        out = capsys.readouterr().out
        assert "[FAIL] a::t" in out
        assert "assert nope" in out

    def test_main_summary_flag_hides_log(self, extract_script, monkeypatch, tmp_path, capsys):
        path = tmp_path / "report.html"
        path.write_text(_report_html({"a::t": _entry("Failed", log="assert nope")}), encoding="utf-8")
        monkeypatch.setattr(sys, "argv", [_SCRIPT, str(path), "--summary"])

        extract_script.main()

        out = capsys.readouterr().out
        assert "[FAIL] a::t" in out
        assert "assert nope" not in out

    def test_main_json_flag_emits_json_only(self, extract_script, monkeypatch, tmp_path, capsys):
        path = tmp_path / "report.html"
        path.write_text(_report_html({"a::t": _entry("Error", log="setup boom")}), encoding="utf-8")
        monkeypatch.setattr(sys, "argv", [_SCRIPT, str(path), "--json"])

        extract_script.main()

        payload = json.loads(capsys.readouterr().out)
        assert payload["summary"]["errors"] == 1
        assert payload["failures"][0]["test_id"] == "a::t"

    def test_main_without_argument_reports_missing_report(self, extract_script, monkeypatch, tmp_path, capsys):
        """无位置参数且无候选报告 → 退出 1（不是静默产出空清单）。"""
        monkeypatch.setattr(sys, "argv", [_SCRIPT])
        monkeypatch.setattr(extract_script.os.path, "exists", lambda path: False)

        with pytest.raises(SystemExit) as exc:
            extract_script.main()

        assert exc.value.code == 1
        assert "未找到测试报告" in capsys.readouterr().err
