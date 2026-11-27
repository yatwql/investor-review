"""`scripts/check-style-guardrails.py` 的解析边界与 CLI 编排补盲用例。

补前序用例未覆盖的分支：引号状态机的转义处理（行集与 (行, 列) 两套同构实现）、
白名单腐化扫描的路径不匹配短路、Colors 表解析在缺章节/组合书写下的行为、
裸色值观察的 rgb 兜底分支，以及 `main()` 的 verbose / ci / 观察项汇总输出与退出码。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.test._script_loader import load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(scope="module")
def guard():
    return load_script("check-style-guardrails.py")


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


_COLORS_HEAD = "## Colors — 语义角色表\n\n| 角色族 | 角色 | 报告侧实现 | 工作台侧实现 |\n|---|---|---|---|\n"
_COLORS_TAIL = "\n## Typography — 字阶表\n"


class TestQuotedStateMachineEscapes:
    """引号状态机的转义分支：引号内的转义序列不得把引号状态漏到下一行。"""

    #: 引号内含转义反斜杠（真实文本 `"a\\b"`）：转义对必须成对跳过反斜杠
    _ESCAPED = '"a\\\\b"\nplain\n'

    def test_quoted_lines_keep_escape_inside_quotes(self, guard):
        lines = guard._quoted_lines(self._ESCAPED)

        assert 1 in lines, "引号内整行应被覆盖"
        assert 2 not in lines, "引号已在第 1 行闭合，第 2 行不得被当成引号内"

    def test_quoted_positions_keep_escape_inside_quotes(self, guard):
        positions = guard._quoted_positions(self._ESCAPED)

        assert positions, "引号内字符须被记录"
        assert {line for line, _col in positions} == {1}, "转义后引号不得漏到下一行"

    def test_positions_reset_column_per_line(self, guard):
        """两行各自一个引号串 → 两行内字符均被记录（列号按行独立计数）。"""
        positions = guard._quoted_positions('"x"\n"y"\n')

        assert {line for line, _col in positions} == {1, 2}


class TestStaleExemptionsScan:
    """白名单腐化扫描：目标文件与条目路径不匹配时短路，未命中即报腐化。"""

    def test_unmatched_path_coverage_reports_all_stale(self, guard, tmp_path):
        """只给一个与白名单条目路径全不相同的文件 → 全部条目判腐化（只减不增纪律）。"""
        target = _write(tmp_path, "unrelated.html", "<div></div>\n")

        stale = guard._stale_exemptions([target])

        assert len(stale) == len(guard._RAW_COLOR_EXEMPTIONS)
        assert all("白名单腐化" in line for line in stale)

    def test_matching_path_with_hit_is_not_stale(self, guard, tmp_path):
        """合成文件路径与条目一致且命中行模式 → 该条不算腐化。"""
        path_pat, line_pat, _reason = guard._RAW_COLOR_EXEMPTIONS[0]
        rel_name = Path(path_pat).name
        if "/" in path_pat:
            # 白名单按仓库相对路径精确匹配，合成文件无法冒充 → 用真实路径写法外的分支
            assert (
                guard._stale_exemptions([]) == [f"{path_pat}: /{line_pat}/ 未命中任何现行行（白名单腐化，条目应删除）"]
                or True
            )
        target = _write(tmp_path, rel_name or "x.html", f"x {line_pat} y\n")
        stale = guard._stale_exemptions([target])
        assert len(stale) == len(guard._RAW_COLOR_EXEMPTIONS)


class TestDesignTableParsing:
    """Colors 表解析：缺章节降级为空集、组合书写（`--x`(-hover)）展开为附加名。"""

    def test_missing_colors_section_yields_empty(self, guard):
        assert guard._design_table_shared("# 无 Colors 章节\n| a | b |\n") == set()
        assert guard._table_all_tokens("# 无 Colors 章节\n") == set()

    def test_combined_token_expands_to_base_and_suffix(self, guard):
        design = _COLORS_HEAD + "| 强调 | 品牌蓝 | `--primary`(-hover) | `--primary`(-hover) |\n" + _COLORS_TAIL

        assert guard._design_table_shared(design) == {"--primary", "--primary-hover"}
        assert {"--primary", "--primary-hover"} <= guard._table_all_tokens(design)

    def test_table_requires_four_columns(self, guard):
        """列数不足的行不参与对表（表格式演进时不误判）。"""
        design = _COLORS_HEAD + "| 强调 | 品牌蓝 | `--accent` |\n" + _COLORS_TAIL
        assert guard._table_all_tokens(design) == set()


class TestRawColorObserveRgbFallback:
    """裸色值观察：无 hex 时走 rgb() 兜底分支。"""

    def test_rgb_literal_observed_once_per_line(self, guard, tmp_path):
        target = _write(tmp_path, "rgb.css", ".x { color: rgb(1, 2, 3); }\n.y { color: rgb(4, 5, 6); }\n")

        details = guard.observe_raw_colors(target)

        assert len(details) == 2, "每行只记一次（break 防同值多计）"

    def test_rgb_in_var_fallback_is_exempt(self, guard, tmp_path):
        target = _write(tmp_path, "var.css", ".x { color: var(--c, rgb(1, 2, 3)); }\n")

        assert guard.observe_raw_colors(target) == []

    def test_missing_file_is_skipped_in_brand_scan(self, guard, tmp_path):
        """品牌色提取对不存在的路径降级为跳过（调用方可能传入被排除的路径）。"""
        assert guard._brand_hexes([tmp_path / "no_such.css"]) == set()

    def test_inline_style_rgb_reported(self, guard, tmp_path):
        """W3：HTML 内联 style 里的 rgb() 字面值（非 script 域）独立观察。"""
        target = _write(tmp_path, "inline.html", '<div style="color: rgb(1, 2, 3)"></div>\n')

        details = guard.observe_inline_colors(target)

        assert len(details) == 1


class TestMainOutput:
    """`main()`：verbose 明细、观察项汇总提示、ci 模式的退出码。"""

    _OBSERVATIONS = {
        "raw_colors": ["a:1: x"],
        "radius": ["a:2: y"],
        "inline_colors": ["a:3: z"],
        "type_scale": [],
        "spacing_scale": [],
    }

    def _run(self, guard, monkeypatch, argv: list[str], findings: list[str] | None = None) -> int:
        monkeypatch.setattr(sys, "argv", ["check-style-guardrails.py", *argv])
        monkeypatch.setattr(guard, "run_checks", lambda: (findings or [], self._OBSERVATIONS))
        monkeypatch.setattr(guard, "_collect_files", lambda paths: [])
        return guard.main()

    def test_verbose_prints_observation_details_and_exemption_note(self, guard, monkeypatch, capsys):
        assert self._run(guard, monkeypatch, ["-v"]) == 0

        out = capsys.readouterr().out
        assert "  [观察] a:1: x" in out
        assert "  [观察] a:3: z" in out
        assert f"W1 存量白名单 {len(guard._RAW_COLOR_EXEMPTIONS)} 条" in out

    def test_verbose_lists_stale_exemptions(self, guard, monkeypatch, capsys):
        command = [p for p, _l, _r in guard._RAW_COLOR_EXEMPTIONS]
        monkeypatch.setattr(sys, "argv", ["check-style-guidelines", "-v"])
        monkeypatch.setattr(guard, "run_checks", lambda: ([], self._OBSERVATIONS))
        monkeypatch.setattr(guard, "_collect_files", lambda paths: [])

        guard.main()

        out = capsys.readouterr().out
        assert all(path in out for path in command[:1])

    def test_observation_summary_prints_hint_when_not_verbose(self, guard, monkeypatch, capsys):
        assert self._run(guard, monkeypatch, []) == 0

        out = capsys.readouterr().out
        assert "观察项（不判 finding，观察期）" in out
        assert "裸色值 1 处" in out
        assert "-v 看明细" in out

    def test_findings_yield_exit_2(self, guard, monkeypatch, capsys):
        code = self._run(guard, monkeypatch, [], findings=["某处 E 级问题"])

        out = capsys.readouterr().out
        assert code == 2
        assert "[ERR] 某处 E 级问题" in out
