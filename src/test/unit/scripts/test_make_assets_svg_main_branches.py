"""`_assets/svg_check.py` 的 `geom` 子命令输出分支与畸形 SVG 容错。

契约：单个坏元素（缺数值属性）只跳过该元素，不中断整轮审查；`geom` 的人类可读报告
只在非 `--ci` 下打印；缺文件本身即 finding，退出码 2。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="600">
  <rect x="10" y="10" width="300" height="100" fill="#ffffff"/>
  <rect x="10" y="200" width="60"/>
  <text x="12" y="50" font-size="15">贴边文本</text>
  <text x="12" y="60" font-size="15">重叠文本</text>
  <text x="12" y="2000" font-size="15">画布外文本</text>
</svg>
"""


@pytest.fixture(name="mod")
def fixture_mod():
    return load_script("_assets/svg_check.py", module_name="_assets_svg_check_branches_under_test")


@pytest.fixture(name="svg")
def fixture_svg(tmp_path: Path) -> Path:
    path = tmp_path / "diagram.svg"
    path.write_text(_SVG, encoding="utf-8")
    return path


class TestMalformedElements:
    """缺 `height` 的 `<rect>` 被跳过，其余元素照常审查。"""

    def test_rect_without_height_is_skipped(self, mod, svg: Path):
        _texts, rects = mod._parse_svg(svg)
        assert all(rect[1] != () for rect in rects)
        assert len(rects) == 1

    def test_text_without_position_is_skipped(self, mod, tmp_path: Path):
        path = tmp_path / "no-x.svg"
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text font-size="15">无坐标</text></svg>', "utf-8")
        assert mod._parse_svg(path) == ([], [])


class TestGeomMainBranches:
    """`geom` 的 finding 分类与报告输出。"""

    def test_human_readable_report_lists_findings(self, mod, svg: Path, capsys):
        assert mod.main(["geom", str(svg)]) == 2
        out = capsys.readouterr().out
        assert "=====" in out
        assert "贴边文本" in out

    def test_ci_mode_prints_only_finding_lines(self, mod, svg: Path, capsys):
        assert mod.main(["--ci", "geom", str(svg)]) == 2
        out = capsys.readouterr().out
        assert "=====" not in out
        assert "diagram.svg" in out

    def test_verbose_reports_per_file_count(self, mod, svg: Path, capsys):
        mod.main(["-v", "geom", str(svg)])
        assert "处几何 finding" in capsys.readouterr().out

    def test_missing_file_is_a_finding(self, mod, tmp_path: Path, capsys):
        assert mod.main(["geom", str(tmp_path / "absent.svg")]) == 2
        assert "文件不存在" in capsys.readouterr().out

    def test_clean_svg_passes(self, mod, tmp_path: Path, capsys):
        path = tmp_path / "clean.svg"
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="600">'
            '<rect x="0" y="0" width="300" height="100"/>'
            '<text x="40" y="60" font-size="15">居中文本</text></svg>',
            "utf-8",
        )
        assert mod.main(["geom", str(path)]) == 0
        assert "无" in capsys.readouterr().out
