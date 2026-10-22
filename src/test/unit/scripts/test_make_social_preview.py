"""`scripts/make-social-preview.py`（GitHub Social Preview 生成）测试。

覆盖画布模板（尺寸/品牌文案/吉祥物素材内嵌）与渲染面（栅格化参数、JPG 落盘、
中间 PNG 去留、依赖缺失与素材不可读的退出码口径）。渲染依赖以替身注入，
用例不依赖本机是否装 cairosvg。
"""

from __future__ import annotations

import base64
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

SVG_NS = "{http://www.w3.org/2000/svg}"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"


@pytest.fixture(name="mod")
def fixture_mod():
    """加载 `scripts/make-social-preview.py` 为可测模块。"""
    from src.test._script_loader import load_script

    return load_script("make-social-preview.py")


class _FakeCairosvg:
    """栅格化替身：记录调用参数，并写出一张真实可解码的 PNG。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def svg2png(self, *, bytestring: bytes, write_to: str, output_width: int, output_height: int) -> None:
        from PIL import Image

        self.calls.append(
            {
                "bytestring": bytestring,
                "write_to": write_to,
                "output_width": output_width,
                "output_height": output_height,
            }
        )
        Image.new("RGB", (output_width, output_height), (11, 21, 36)).save(write_to, "PNG")


class TestCanvasTemplate:
    """画布模板：尺寸、品牌文案与吉祥物素材。"""

    def test_canvas_is_social_preview_size(self, mod):
        root = ET.fromstring(mod.build_svg(""))
        assert root.get("width") == "1200"
        assert root.get("height") == "630"
        assert root.get("viewBox") == "0 0 1200 630"

    def test_brand_copy_is_present(self, mod):
        texts = "".join(node.text or "" for node in ET.fromstring(mod.build_svg("")).iter(f"{SVG_NS}text"))
        for expected in ("投资复盘助手", "INVESTOR REVIEW", "本地优先的投资分析引擎"):
            assert expected in texts

    def test_mascot_payload_matches_repository_asset(self, mod):
        owl_bytes = mod.OWL_SVG.read_bytes()
        root = ET.fromstring(mod.compose_preview(owl_bytes))
        image = root.find(f"{SVG_NS}image")
        assert image is not None, "画布缺少吉祥物图片节点"
        href = image.get(XLINK_HREF) or ""
        prefix = "data:image/svg+xml;base64,"
        assert href.startswith(prefix)
        assert base64.b64decode(href[len(prefix) :]) == owl_bytes

    def test_mascot_box_keeps_source_aspect_ratio(self, mod):
        """卡片落位与素材 viewBox 的宽高比一致（±3% 内不留可见形变）。"""
        owl_root = ET.fromstring(mod.OWL_SVG.read_text(encoding="utf-8"))
        _, _, vb_w, vb_h = (float(v) for v in owl_root.get("viewBox").split())
        box = mod.OWL_BOX
        assert (box["w"] / box["h"]) == pytest.approx(vb_w / vb_h, rel=0.03)


class TestRender:
    """渲染面：栅格化参数、JPG 产物与中间文件去留。"""

    def _deps(self, mod):
        from PIL import Image

        return mod.RenderDeps(cairosvg=_FakeCairosvg(), image_module=Image)

    def test_rasterizes_at_canvas_size(self, mod, tmp_path: Path):
        deps = self._deps(mod)
        out = tmp_path / "preview.jpg"
        size = mod.render_jpeg(mod.build_svg(""), out, deps)
        assert size == (1200, 630)
        assert deps.cairosvg.calls[0]["output_width"] == 1200
        assert deps.cairosvg.calls[0]["output_height"] == 630
        assert deps.cairosvg.calls[0]["bytestring"] == mod.build_svg("").encode("utf-8")

    def test_writes_jpeg_and_drops_intermediate_png(self, mod, tmp_path: Path):
        from PIL import Image

        out = tmp_path / "nested" / "preview.jpg"
        mod.render_jpeg(mod.build_svg(""), out, self._deps(mod))
        assert out.is_file()
        assert Image.open(out).format == "JPEG"
        assert not out.with_suffix(".png").exists()

    def test_keep_png_option_preserves_intermediate(self, mod, tmp_path: Path):
        out = tmp_path / "preview.jpg"
        mod.render_jpeg(mod.build_svg(""), out, self._deps(mod), keep_png=True)
        assert out.with_suffix(".png").is_file()


class TestMainExitCodes:
    """入口退出码与提示文案。"""

    def test_missing_dependency_exits_one_with_install_hint(self, mod, monkeypatch, capsys):
        def _boom():
            raise mod.RenderDependencyError("缺少依赖：cairosvg 用于 SVG 栅格化。安装：.venv/bin/pip install cairosvg")

        monkeypatch.setattr(mod, "_load_render_deps", _boom)
        assert mod.main(["-o", "unused.jpg"]) == 1
        assert "pip install cairosvg" in capsys.readouterr().out

    def test_unreadable_asset_exits_one(self, mod, tmp_path: Path, monkeypatch, capsys):
        monkeypatch.setattr(mod, "OWL_SVG", tmp_path / "missing.svg")
        monkeypatch.setattr(
            mod, "_load_render_deps", lambda: mod.RenderDeps(cairosvg=_FakeCairosvg(), image_module=object)
        )
        assert mod.main(["-o", str(tmp_path / "out.jpg")]) == 1
        assert "素材不可读" in capsys.readouterr().out

    def test_success_writes_requested_output(self, mod, tmp_path: Path, monkeypatch, capsys):
        monkeypatch.setattr(
            mod,
            "_load_render_deps",
            lambda: mod.RenderDeps(cairosvg=_FakeCairosvg(), image_module=__import__("PIL.Image", fromlist=["Image"])),
        )
        out = tmp_path / "out.jpg"
        assert mod.main(["-o", str(out)]) == 0
        assert out.is_file()
        assert "[OK]" in capsys.readouterr().out
