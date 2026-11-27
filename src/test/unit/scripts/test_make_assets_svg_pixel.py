"""`scripts/_assets/svg_check.py` 像素审查与入口调度面测试。

既有 `test_make_assets_svg.py` 覆盖几何审查（文本越界/贴边/重叠/底部对齐）与入口转发；
本文件补像素审查两类 finding（亮色越界 / 文字色越界）、Pillow 缺失降级（走 `check-svg.py`
的 1=环境缺失契约）与 `main` 的子命令报告分支。

像素用例自造小 PNG（Pillow 生成），不依赖仓库架构图产物；缺 Pillow 时整体跳过。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

PNG_SIZE = 100
SCALE = 10.0  # 1 svg 单位 = 10 px


@pytest.fixture(name="mod")
def fixture_mod():
    return load_script("_assets/svg_check.py", module_name="_assets_svg_check_pixel_under_test")


@pytest.fixture(name="png_factory")
def fixture_png_factory():
    """按 `{(x, y): (r, g, b)}` 点阵生成 PNG（其余像素为深色卡片底）。"""
    Image = pytest.importorskip("PIL.Image")

    def _build(path: Path, points: dict[tuple[int, int], tuple[int, int, int]]) -> Path:
        image = Image.new("RGB", (PNG_SIZE, PNG_SIZE), (20, 24, 32))
        for (x_pos, y_pos), color in points.items():
            image.putpixel((x_pos, y_pos), color)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
        return path

    return _build


class TestPillowMissingContract:
    """Pillow 缺失 = 环境缺失（退出码 1），不是「审查通过」。"""

    @pytest.fixture(name="no_pillow")
    def _no_pillow(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "PIL", None)

    def test_require_pillow_returns_none_with_install_hint(self, mod, no_pillow, capsys):
        assert mod._require_pillow() is None
        assert "pip install Pillow" in capsys.readouterr().out

    def test_pixel_findings_exits_one_without_pillow(self, mod, no_pillow, tmp_path):
        with pytest.raises(SystemExit) as excinfo:
            mod.pixel_findings(tmp_path / "a.png", SCALE, 5.0, 1.0, 3.0, 3.0)
        assert excinfo.value.code == 1

    def test_text_overflow_exits_one_without_pillow(self, mod, no_pillow, tmp_path):
        with pytest.raises(SystemExit) as excinfo:
            mod.text_overflow_findings(tmp_path / "a.png", SCALE, 5.0, 1.0, 3.0, 3.0)
        assert excinfo.value.code == 1

    def test_main_pixel_returns_environment_missing_code(self, mod, no_pillow, tmp_path):
        """`check-svg.py` 契约：环境缺失退出 1（否则「没装 Pillow」会被读成审查通过）。"""
        with pytest.raises(SystemExit) as excinfo:
            mod.main(["pixel", str(tmp_path / "a.png"), "10", "5", "1", "3", "3"])
        assert excinfo.value.code == 1


class TestPixelFindings:
    """副标题行亮色像素越出卡片右缘。"""

    def test_bright_pixel_beyond_card_edge_reported(self, mod, png_factory, tmp_path):
        png = png_factory(tmp_path / "frames" / "shot.png", {(60, 20): (240, 245, 250)})
        findings = mod.pixel_findings(png, SCALE, 5.0, 1.0, 3.0, 3.0)
        assert len(findings) == 1
        assert "亮色像素越出卡片右缘 1 个" in findings[0]
        assert "最右 x=6.0px" in findings[0]
        assert "shot.png" in findings[0]

    def test_dark_band_clean(self, mod, png_factory, tmp_path):
        png = png_factory(tmp_path / "frames" / "shot.png", {(60, 20): (20, 24, 32)})
        assert mod.pixel_findings(png, SCALE, 5.0, 1.0, 3.0, 3.0) == []

    def test_pixels_before_card_edge_ignored(self, mod, png_factory, tmp_path):
        png = png_factory(tmp_path / "frames" / "shot.png", {(45, 20): (240, 245, 250)})
        assert mod.pixel_findings(png, SCALE, 5.0, 1.0, 3.0, 3.0) == []


class TestTextOverflowFindings:
    """精确匹配文字色（±20 容差）越界，避免把卡片阴影误判成文字溢出。"""

    def test_text_color_pixel_beyond_edge_reported(self, mod, png_factory, tmp_path):
        text_color = mod._TEXT_COLORS[0]
        png = png_factory(tmp_path / "frames" / "shot.png", {(70, 20): text_color, (75, 22): text_color})
        findings = mod.text_overflow_findings(png, SCALE, 5.0, 1.0, 3.0, 3.0)
        assert len(findings) == 1
        assert "文字色像素越出卡片右缘 2 个" in findings[0]
        assert "最右 x=7.5px" in findings[0]

    def test_off_palette_pixel_ignored(self, mod, png_factory, tmp_path):
        png = png_factory(tmp_path / "frames" / "shot.png", {(70, 20): (200, 60, 60)})
        assert mod.text_overflow_findings(png, SCALE, 5.0, 1.0, 3.0, 3.0) == []


class TestMainDispatch:
    """子命令调度：verbose 进度行与三类 finding 的消息口径。"""

    def test_pixel_subcommand_clean_reports_ok(self, mod, png_factory, tmp_path, capsys):
        png = png_factory(tmp_path / "shot.png", {})
        assert mod.main(["--verbose", "pixel", str(png), "10", "5", "1", "3", "3"]) == 0
        out = capsys.readouterr().out
        assert "像素越界检查" in out
        assert "无亮色像素越界" in out

    def test_pixel_subcommand_with_finding_returns_two(self, mod, png_factory, tmp_path, capsys):
        png = png_factory(tmp_path / "shot.png", {(60, 20): (240, 245, 250)})
        assert mod.main(["pixel", str(png), "10", "5", "1", "3", "3"]) == 2
        assert "发现 1 处 SVG 问题" in capsys.readouterr().out

    def test_text_overflow_subcommand_reports_ok(self, mod, png_factory, tmp_path, capsys):
        png = png_factory(tmp_path / "shot.png", {})
        assert mod.main(["--verbose", "text-overflow", str(png), "10", "5", "1", "3", "3"]) == 0
        out = capsys.readouterr().out
        assert "文字越界检查" in out
        assert "无文字色像素越出卡片右缘" in out

    def test_geom_missing_file_reported(self, mod, tmp_path, capsys):
        missing = tmp_path / "absent.svg"
        assert mod.main(["geom", str(missing)]) == 2
        assert "文件不存在" in capsys.readouterr().out
