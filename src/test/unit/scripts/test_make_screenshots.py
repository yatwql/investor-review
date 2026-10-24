"""`scripts/make-screenshots.py`（演示截图生成器）测试。

三块实现各测其纯逻辑面：演示工作区的持仓/配置口径与报告命令装配、TUI 帧的折行与
路径瘦身（渲染尺寸在依赖齐备时抽验）、Web 截图的浏览器解析与命令装配。
外部依赖（Pillow / CJK 字体 / Node / Chromium）缺失即跳过或走纯函数断言，不发起网络请求。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="demo")
def fixture_demo():
    """加载演示工作区模块。"""
    return load_script("_screenshots/demo_workspace.py", module_name="_screenshots_demo_workspace_under_test")


@pytest.fixture(name="tui")
def fixture_tui():
    """加载 TUI 帧渲染模块。"""
    return load_script("_screenshots/tui_frame.py", module_name="_screenshots_tui_frame_under_test")


@pytest.fixture(name="web")
def fixture_web():
    """加载 Web 截图模块。"""
    return load_script("_screenshots/web_shot.py", module_name="_screenshots_web_shot_under_test")


class TestDemoWorkspace:
    """演示工作区：自造持仓、绝对路径配置、报告命令。"""

    @pytest.mark.unit_scripts
    def test_builds_one_sheet_per_account_with_declared_rows(self, demo, tmp_path):
        workspace = demo.build(tmp_path / "shots")
        assert (workspace / "data" / "holdings" / demo.HOLDINGS_FILENAME).is_file()

        from openpyxl import load_workbook

        workbook = load_workbook(workspace / "data" / "holdings" / demo.HOLDINGS_FILENAME)
        accounts = list(dict.fromkeys(row[0] for row in demo.HOLDINGS))
        assert workbook.sheetnames == accounts
        for account in accounts:
            rows = list(workbook[account].iter_rows(values_only=True))
            assert rows[0] == ("名称", "代码", "持仓份额", "每份成本")
            expected = [row[1:] for row in demo.HOLDINGS if row[0] == account]
            assert [tuple(row) for row in rows[1:]] == expected

    @pytest.mark.unit_scripts
    def test_config_uses_absolute_paths(self, demo, tmp_path):
        workspace = demo.build(tmp_path / "shots")
        config = json.loads((workspace / "data" / "config" / "config.json").read_text(encoding="utf-8"))

        assert Path(config["holdings_dir"]).is_absolute()
        assert Path(config["output_dir"]).is_absolute()
        assert not (workspace / "display-config.json").exists()

    @pytest.mark.unit_scripts
    def test_placeholder_key_is_obviously_fake(self, demo, tmp_path):
        workspace = demo.build(tmp_path / "shots")
        key = json.loads((workspace / "data" / "config" / "llm_key.json").read_text(encoding="utf-8"))
        assert key["api_key"] == demo.DEMO_API_KEY
        assert "demo" in key["api_key"]

    @pytest.mark.unit_scripts
    def test_report_command_runs_report_subcommand_on_demo_config(self, demo, tmp_path):
        config = demo.config_path(tmp_path / "shots")
        command = demo.report_command(config)
        assert command[0] == sys.executable
        assert command[1:3] == ["-m", "src.python.cli"]
        assert command[command.index("--config") + 1] == str(config)
        assert "report" in command
        assert command[-1] == "--yes"


class TestTuiFrame:
    """TUI 帧：折行保色、路径瘦身、渲染尺寸。"""

    @pytest.mark.unit_scripts
    def test_short_line_is_returned_untouched(self, tui):
        line = "\x1b[1m\x1b[32m首页\x1b[0m"
        assert tui.wrap_line(line, 40) == [line]

    @pytest.mark.unit_scripts
    def test_wrapped_rows_respect_width_and_reopen_color(self, tui):
        plain = "中" * 60
        rows = tui.wrap_line(f"\x1b[32m{plain}\x1b[0m", 20)
        assert len(rows) > 1
        assert [tui.strip_ansi(row) for row in rows] == [plain[index : index + 10] for index in range(0, 60, 10)]
        for row in rows:
            assert tui.display_width(tui.strip_ansi(row)) <= 20
        # 续行重新打开配色，首行带原始起始序列
        assert rows[0].startswith("\x1b[32m")
        assert all(row.startswith("\x1b[32m") for row in rows[1:])

    @pytest.mark.unit_scripts
    def test_scrub_paths_removes_longest_prefix_first(self, tui, tmp_path):
        demo_dir = tmp_path / "shots" / "demo"
        text = f"{demo_dir}/reports/报告.html 与 {tmp_path}/README.md"
        scrubbed = tui.scrub_paths(text, (demo_dir, tmp_path))
        assert str(demo_dir) not in scrubbed
        assert str(tmp_path) not in scrubbed
        assert "reports/报告.html" in scrubbed
        assert "README.md" in scrubbed

    @pytest.mark.unit_scripts
    def test_render_sizes_canvas_from_line_count(self, tui, tmp_path):
        pytest.importorskip("PIL.Image")
        try:
            tui.resolve_font()
        except tui.RenderDependencyError as exc:
            pytest.skip(str(exc))
        output = tui.render("\x1b[32m第一行\x1b[0m\n第二行\n", tmp_path / "frame.png")
        from PIL import Image

        with Image.open(output) as image:
            assert image.size[1] == tui.LINE_HEIGHT * 2 + tui.PADDING * 2
            assert image.size[0] >= 320


class TestWebShot:
    """Web 截图：浏览器解析次序与命令装配。"""

    @pytest.mark.unit_scripts
    def test_explicit_chrome_wins_over_env(self, web, tmp_path, monkeypatch):
        explicit = tmp_path / "chrome"
        fallback = tmp_path / "fallback"
        for path in (explicit, fallback):
            path.write_text("", encoding="utf-8")
        monkeypatch.setenv("CHROME_BIN", str(fallback))
        assert web.resolve_chrome(str(explicit)) == explicit

    @pytest.mark.unit_scripts
    def test_missing_explicit_falls_back_to_env(self, web, tmp_path, monkeypatch):
        fallback = tmp_path / "fallback"
        fallback.write_text("", encoding="utf-8")
        monkeypatch.setenv("CHROME_BIN", str(fallback))
        assert web.resolve_chrome(str(tmp_path / "absent")) == fallback

    @pytest.mark.unit_scripts
    def test_build_command_maps_positional_arguments(self, web, tmp_path):
        command = web.build_command(
            "http://127.0.0.1:8000/workbench",
            tmp_path / "shot.png",
            scroll_y=120,
            width=1280,
            height=800,
            replace="临时=>演示",
        )
        assert Path(command[1]).name == "cdp_shot.mjs"
        assert command[2:] == [
            "http://127.0.0.1:8000/workbench",
            str(tmp_path / "shot.png"),
            "120",
            "1280",
            "800",
            "临时=>演示",
        ]

    @pytest.mark.unit_scripts
    def test_cdp_script_reads_chrome_from_environment(self, web):
        source = web.CDP_SCRIPT.read_text(encoding="utf-8")
        assert "CHROME_BIN" in source
        assert "remote-debugging-port" in source


class TestEntry:
    """入口：子命令分发与参数错误口径。"""

    @pytest.mark.unit_scripts
    def test_demo_subcommand_writes_workspace(self, tmp_path, monkeypatch):
        entry = load_script("make-screenshots.py", module_name="_make_screenshots_under_test")
        monkeypatch.setattr(entry.demo_workspace, "DEFAULT_ROOT", tmp_path / "shots")
        assert entry.main(["demo"]) == 0
        holdings = tmp_path / "shots" / "demo" / "data" / "holdings"
        assert (holdings / entry.demo_workspace.HOLDINGS_FILENAME).is_file()

    @pytest.mark.unit_scripts
    def test_report_subcommand_returns_underlying_exit_code(self, monkeypatch):
        entry = load_script("make-screenshots.py", module_name="_make_screenshots_under_test")
        monkeypatch.setattr(entry.demo_workspace, "run_report", lambda root=None: 3)
        assert entry.main(["report"]) == 3

    @pytest.mark.unit_scripts
    def test_unknown_subcommand_exits_with_usage_error(self):
        entry = load_script("make-screenshots.py", module_name="_make_screenshots_under_test")
        with pytest.raises(SystemExit) as caught:
            entry.main(["bogus"])
        assert caught.value.code == 2

    @pytest.mark.unit_scripts
    def test_help_lists_every_subcommand(self, capsys):
        entry = load_script("make-screenshots.py", module_name="_make_screenshots_under_test")
        with pytest.raises(SystemExit) as caught:
            entry.main(["--help"])
        assert caught.value.code == 0
        printed = capsys.readouterr().out
        assert {"demo", "report", "tui", "web"} <= set(printed.split())
