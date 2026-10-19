"""交互图表单渲染器（Chart.js 唯一路径）+ 报告管线集成单元测试。

覆盖：
  - enable_interactive_charts 开关已随 Canvas 回退分支移除（注册表与模板零残留）
  - _build_chart_datasets_for_report：恒构建数据集（无 Flag 分支）
  - 顶层兜底：build_chart_datasets 异常 → 返回空 dict（报告仍正常）
  - _copy_js_assets：Chart.js 本地 bundle 全部 JS 文件随报告复制
  - 调试页 test-chart.html 引擎注入列表与报告模板一致（浏览器人工验证前置载体）

运行：
  cd <项目根目录>
  .venv/bin/python -m pytest src/test/unit/report/test_feature_interactive.py -v
"""

from __future__ import annotations

import builtins
import io
import os
import re
from unittest.mock import patch

import pytest

from src.python.report._report_generation import _build_chart_datasets_for_report
from src.python.report.html_writer import _copy_js_assets, _inline_js_assets
from src.python.report.html_writer_assets import JS_ASSETS

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]

_DEBUG_PAGE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "static", "test-chart.html"),
)
_CHART_PRINT_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "static", "chart-print.js"),
)
_CHART_EXPORT_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "static", "chart-export.js"),
)
# 携带导出按钮样式的模板（主报告 / What-if 独立页 / 调试页）
_EXPORT_BTN_TEMPLATES = (
    os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "static", "tmpl", "report_template.html")
    ),
    os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "static", "tmpl", "whatif_template.html")
    ),
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "static", "test-chart.html")),
)


def _history_ok() -> dict:
    return {
        "status": "ok",
        "bars": [{"date": "2026-01-01", "total_value": 100.0, "drawdown_pct": 0.0}],
        "benchmarks": [],
    }


class TestChartSoleRendererRegression:
    """单渲染器回归：enable_interactive_charts 已随 Canvas 回退路径整体移除。"""

    def test_flag_entry_absent_from_registry(self) -> None:
        from src.python.config.features import feature_switch_registry

        assert "enable_interactive_charts" not in feature_switch_registry

    def test_templates_free_of_legacy_canvas_path(self) -> None:
        tmpl_root = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "static", "tmpl"),
        )
        hits = []
        for dirpath, _dirs, files in os.walk(tmpl_root):
            for fname in files:
                if not fname.endswith(".html"):
                    continue
                with open(os.path.join(dirpath, fname), encoding="utf-8") as f:
                    txt = f.read()
                if "drawSimpleChart" in txt or "enable_interactive" in txt:
                    hits.append(fname)
        assert hits == []


class TestBuildChartDatasetsForReport:
    def test_always_returns_datasets(self) -> None:
        """无 Flag 分支：helper 恒构建数据集 dict。"""
        result = _build_chart_datasets_for_report(history_data=_history_ok())
        assert isinstance(result, dict)
        assert "portfolio_line" in result

    def test_top_level_fallback_returns_empty_dict(self) -> None:
        """顶层兜底：build_chart_datasets 抛异常 → 返回空 dict（报告仍正常）。"""
        # 函数内为 `from ...chart_data_builder import build_chart_datasets`，
        # 需 patch 源模块属性才会被函数内 import 取到。
        with patch(
            "src.python.report.chart_data_builder.build_chart_datasets",
            side_effect=RuntimeError("boom"),
        ):
            result = _build_chart_datasets_for_report(history_data=_history_ok())
        assert result == {}


class TestCopyJsAssets:
    def test_copies_all_js_files(self, tmp_path) -> None:
        """Chart.js 本地 bundle 全部 JS 文件随报告复制到输出目录。"""
        _copy_js_assets(str(tmp_path))
        for fname in (
            "chart.min.js",
            "chart-print.js",
            "chart-config.js",
            "chart-export.js",
            "chart-common.js",
            "chart-init.js",
            "toc.js",
            "theme.js",
        ):
            assert (tmp_path / fname).exists(), f"{fname} 未复制"


class TestInlineJsAssets:
    """_inline_js_assets：报告 HTML 单文件自包含（外链脚本 → 行内脚本）。

    回归背景：报告 HTML 以相对路径外链 8 个 Chart.js 资产，下载/移动到
    其他目录（如 Web 下载到本地）后 JS 找不到，资产穿透等图表全部空白；
    仅当 HTML 与 JS 同目录时图表才渲染。内嵌后单文件即可在任意位置浏览。
    """

    # 资产清单从生产代码派生（单一事实来源，新增资产无需改测试）
    _ALL_ASSETS = JS_ASSETS

    @staticmethod
    def _static_dir() -> str:
        from src.python.core.constants import PROJECT_ROOT

        return os.path.join(PROJECT_ROOT, "src", "static")

    def test_inline_replaces_all_external_script_tags(self) -> None:
        """全部本地 bundle 外链脚本内嵌为行内 <script>，且追加到 </body> 前（内容来自 src/static）。"""
        html = (
            "<html><head>"
            + "".join(f'<script defer src="{a}"></script>' for a in self._ALL_ASSETS)
            + "</head><body>x</body></html>"
        )
        out = _inline_js_assets(html)
        # 外链 src 全部消失（被内嵌移除）
        for a in self._ALL_ASSETS:
            assert f'src="{a}"' not in out, f"{a} 应被内嵌而非外链"
        # 行内脚本数 = 8，且全部位于 </body> 前（defer 时序：DOM 解析完后执行）
        assert out.count("<script>") == len(self._ALL_ASSETS)
        assert out.rfind("<script>") < out.rfind("</body>"), "内嵌脚本应追加到 </body> 前"
        # 真实资产内容已内嵌（chart.min.js 头部片段为证）
        with open(os.path.join(self._static_dir(), "chart.min.js"), encoding="utf-8") as f:
            head = f.read(200)
        assert head in out, "chart.min.js 内容应内嵌进 HTML"

    def test_inline_appended_before_body_close(self) -> None:
        """内嵌脚本追加到 </body> 前——复刻 defer 时序（canvas/chart-data 已解析）。"""
        html = '<html><head><script defer src="chart.min.js"></script><script defer src="chart-init.js"></script></head><body><div id="chart_penetration_bar"></div></body></html>'
        out = _inline_js_assets(html)
        init_inline = out.find("<script>")
        body_close = out.find("</body>")
        assert init_inline != -1 and init_inline < body_close, "内嵌脚本必须在 </body> 前"

    def test_asset_order_common_before_init(self) -> None:
        """内嵌后行内脚本按 bundle 依赖顺序（chart-common 在 chart-init 前）。"""
        src = self._static_dir()
        with open(os.path.join(src, "chart-common.js"), encoding="utf-8") as f:
            common = f.read()
        with open(os.path.join(src, "chart-init.js"), encoding="utf-8") as f:
            init = f.read()
        html = (
            "<html><head>"
            '<script defer src="chart-init.js"></script>'
            '<script defer src="chart-common.js"></script>'
            "</head><body>x</body></html>"
        )
        out = _inline_js_assets(html)
        # 追加顺序按 bundle 依赖序（common 先于 init），而非源标签出现顺序
        assert out.index(common) < out.index(init), "chart-common.js 必须先于 chart-init.js"

    def test_unrelated_script_tag_untouched(self) -> None:
        """非本地 bundle 的外链脚本（其他 .js）保持原位原样。"""
        html = (
            '<html><head><script defer src="other.js"></script>'
            '<script defer src="theme.js"></script></head><body>x</body></html>'
        )
        out = _inline_js_assets(html)
        assert 'src="other.js"' in out, "非 bundle 外链脚本应保留"
        assert 'src="theme.js"' not in out, "bundle 资产应内嵌"

    def test_missing_asset_keeps_external_tag(self, monkeypatch) -> None:
        """资产文件缺失时保留原外链标签（不阻断、不静默丢脚本）。"""
        missing = os.path.normpath(os.path.join(self._static_dir(), "theme.js"))
        orig_open = builtins.open

        def fake_open(path, *args, **kwargs):
            if os.path.normpath(os.fspath(path)) == missing:
                raise FileNotFoundError(path)
            return orig_open(path, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", fake_open)
        html = (
            "<html><head>"
            '<script defer src="chart.min.js"></script>\n'
            '<script defer src="theme.js"></script>'
            "</head><body>x</body></html>"
        )
        out = _inline_js_assets(html)
        assert 'src="theme.js"' in out, "缺失资产应保留外链"
        assert 'src="chart.min.js"' not in out, "存在资产应正常内嵌"

    def test_asset_with_closing_sequence_skipped(self, monkeypatch) -> None:
        """资产内容含 </script 序列时跳过内嵌（防止截断行内脚本），保留外链。"""
        risky = os.path.normpath(os.path.join(self._static_dir(), "theme.js"))
        orig_open = builtins.open

        def fake_open(path, *args, **kwargs):
            if os.path.normpath(os.fspath(path)) == risky:
                return io.StringIO('var bad = "</script>"')
            return orig_open(path, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", fake_open)
        html = '<script defer src="theme.js"></script>'
        out = _inline_js_assets(html)
        assert 'src="theme.js"' in out, "含 </script 序列的资产应保留外链"


class TestDebugPageAssets:
    """调试页 test-chart.html 引擎注入列表与报告模板一致（浏览器人工验证前置载体）。"""

    def test_injection_list_contains_chart_common_before_init(self) -> None:
        """注入列表必须含 chart-common.js 且先于 chart-init.js（回归防护）。

        chart-init.js 依赖 window.ChartCommon（chart-common.js 提供），报告模板
        已加载它，但调试页 test-chart.html 注入列表曾漏掉该文件，导致调试页
        0/6 图全部跳过、自检无法进行。本用例保证两处注入顺序一致。
        """
        with open(_DEBUG_PAGE_PATH, encoding="utf-8") as f:
            content = f.read()
        m = re.search(r"var scripts\s*=\s*\[(.*?)\];", content)
        assert m, "test-chart.html 应包含 scripts 引擎注入数组"
        scripts = [s.strip().strip("'\"") for s in m.group(1).split(",")]
        assert "chart.min.js" in scripts, "注入列表应包含 chart.min.js"
        assert "chart-common.js" in scripts, "注入列表应包含 chart-common.js（chart-init 依赖）"
        assert "chart-init.js" in scripts, "注入列表应包含 chart-init.js"
        assert scripts.index("chart-common.js") < scripts.index("chart-init.js"), (
            "chart-common.js 必须先于 chart-init.js 注入"
        )

    def test_offline_scenario_removes_only_engine(self) -> None:
        """离线场景仅移除 chart.min.js（引擎），chart-common.js 保留。

        与报告离线验证（删除/改名 chart.min.js）行为一致：chart-init.js 靠
        typeof Chart 守卫静默跳过，无 JS 报错。
        """
        with open(_DEBUG_PAGE_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "scripts.shift();" in content, "离线场景应通过 shift() 仅移除第一个引擎文件"
        assert "if (scenario === 'offline') { scripts.shift(); }" in content, "离线场景应在注入前移除 chart.min.js"

    def test_grid_column_min_shrinks_with_container(self) -> None:
        """调试页 grid 列下限随容器收缩（回归防护：窄视口自身溢出）。

        调试页 .grid 的列下限若为裸 minmax(420px, 1fr)，在窄视口下加 body
        边距会撑破页面自身横向溢出；列下限须为 min(420px, 100%)，窄视口
        下随容器收缩。
        """
        with open(_DEBUG_PAGE_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "minmax(min(420px, 100%), 1fr)" in content, "列下限须随容器宽收缩（min(420px,100%)）"
        assert "minmax(420px, 1fr)" not in content, "裸 420px 列下限在窄视口必溢出（回归）"


class TestChartPrintDisplayRestore:
    """打印前后 canvas 内联 display 记录-还原闭环（回归防护）。"""

    @staticmethod
    def _src() -> str:
        with open(_CHART_PRINT_PATH, encoding="utf-8") as f:
            return f.read()

    def test_beforeprint_remembers_inline_display(self) -> None:
        """beforeprint 快照时记录各 canvas 原内联 display，重复打印不覆盖首个值。"""
        src = self._src()
        assert "rememberDisplay" in src, "应有记录原内联 display 的函数"
        assert "canvas.style.display" in src.split("rememberDisplay", 1)[1], "记录源须为 canvas.style.display"
        assert "if (savedDisplays[i].canvas === canvas) return;" in src, "同一 canvas 只记首个值，避免二次快照覆盖原值"

    def test_afterprint_restores_recorded_display_not_empty(self) -> None:
        """afterprint 按记录还原 display，禁止置空串（置空使 computed display 漂移）。"""
        src = self._src()
        assert "canvas.style.display = savedDisplayOf(canvas);" in src, "恢复须按记录还原原值"
        assert "canvas.style.display = '';" not in src, (
            "置空串会使 computed display 漂移（Chart.js 初始化写 block，置空后变 inline）"
        )

    def test_unrecorded_falls_back_to_block_and_state_clears(self) -> None:
        """未记录的 canvas 回退 block；一次打印周期结束后清空记录。"""
        src = self._src()
        assert "return 'block';" in src, "未记录回退 block（与 Chart.js 初始化内联值一致）"
        assert re.search(r"savedDisplays\s*=\s*\[\];", src), "打印周期结束应清空记录，避免跨周期残留"


class TestChartExportCsv:
    """单图导出 CSV：PNG/CSV 双按钮注入 + 屏显同源数据本地 Blob 下载。"""

    @staticmethod
    def _src() -> str:
        with open(_CHART_EXPORT_PATH, encoding="utf-8") as f:
            return f.read()

    def test_injects_png_and_csv_buttons_in_group(self) -> None:
        """每图注入 PNG/CSV 两枚按钮，按组容器判重（同一图只注入一组）。"""
        src = self._src()
        assert "导出PNG" in src, "应保留 PNG 导出按钮"
        assert "导出CSV" in src, "应提供 CSV 导出按钮"
        assert "chart-export-actions" in src, "双按钮须有组容器统一布局"
        assert "box.querySelector('.chart-export-actions')" in src, "幂等守卫须按组容器判重，避免重复注入"

    def test_csv_download_is_local_blob_with_utf8_bom(self) -> None:
        """CSV 走本地 Blob 下载（零后端），MIME 为 text/csv，带 UTF-8 BOM 供 Excel 直开。"""
        src = self._src()
        assert "text/csv" in src, "Blob MIME 须为 text/csv"
        assert "\\ufeff" in src, "CSV 须带 UTF-8 BOM（Excel 双击打开不乱码）"
        assert "URL.createObjectURL" in src and "URL.revokeObjectURL" in src, "ObjectURL 用后须释放，避免内存泄漏"
        assert ".csv'" in src, "下载文件名以 .csv 结尾"

    def test_csv_rows_derived_from_chart_display_data(self) -> None:
        """CSV 行列取自 chart.data（与屏显同源），RFC 4180 转义 + CRLF 行分隔。"""
        src = self._src()
        assert "data.labels" in src and "data.datasets" in src, "首列为标签、其后各列为数据系列"
        assert """s.replace(/"/g, '""')""" in src, "引号须翻倍转义（RFC 4180）"
        assert "'\\r\\n'" in src, "行分隔须为 CRLF"

    def test_templates_anchor_actions_group_not_single_button(self) -> None:
        """三处模板把绝对定位放在组容器上，按钮自身静态排布（双按钮并排不重叠）。"""
        for path in _EXPORT_BTN_TEMPLATES:
            name = os.path.basename(path)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            assert ".chart-export-actions" in content, f"{name} 缺组容器样式"
            blocks = re.findall(r"\.chart-export-btn\s*\{([^}]*)\}", content)
            assert blocks, f"{name} 缺按钮样式"
            for block in blocks:
                assert "position: absolute" not in block, f"{name} 按钮自身不得绝对定位（两按钮同坐标会重叠）"
