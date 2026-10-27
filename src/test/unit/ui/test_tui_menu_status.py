"""test_tui_menu 兄弟分片（status）：页头状态行 / LLM 状态渲染。"""

from __future__ import annotations
import json
import os
import tempfile
import time
import unittest
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from src.python.tui.status_line import build_status_line, reset_status_memo
from src.python.tui.tui_menu import (
    print_header,
)
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


class TestActionHintKeys:
    """动作提示短语带的菜单键必须仍在主菜单里（防菜单改键后提示按键落空）。"""

    def test_action_keys_exist_in_main_menu(self) -> None:
        from src.python.tui.status_line import ACTION_TEMPLATES
        from src.python.tui.tui_menu import _apply_feature_gates, MENU_ITEMS

        _apply_feature_gates()  # 按当前开关重建菜单（母本裁剪后的真实可见键集）
        menu_keys = {item[0] for item in MENU_ITEMS}
        for name, text in ACTION_TEMPLATES.items():
            assert text.startswith("["), f"动作提示必须以菜单键开头：{name}={text}"
            # 短语形如 `[G]→L 配置 LLM`：只校验首键（二级入口不在主菜单）
            assert text[1] in menu_keys, f"{name} 首键 [{text[1]}] 不在主菜单"

    def test_every_template_is_used(self) -> None:
        """模板不得有死条目（没人引用的提示永远不上屏）。"""
        import inspect

        from src.python.tui import status_line

        source = inspect.getsource(status_line)
        for name in status_line.ACTION_TEMPLATES:
            assert source.count(f'ACTION_TEMPLATES["{name}"]') >= 1, f"模板 {name} 未被任何状态段引用（死条目）"


class TestLlmStatusRendering:
    """_show_llm_config_status — 消费 llm_status 单源的三态终端渲染。"""

    @staticmethod
    def _render() -> str:
        import src.python.tui.tui_menu as tm

        buf = StringIO()
        with patch("sys.stdout", buf):
            tm._show_llm_config_status()
        return buf.getvalue()

    def test_unconfigured_line(self):
        with patch("src.python.config.get_llm_config", return_value=None):
            assert "未配置" in self._render()

    def test_single_provider_fields_show_unconfigured(self):
        """顶层 api_key/provider 不产出已配置渲染（运行期只认 provider 链）。"""
        with patch("src.python.config.get_llm_config", return_value={"api_key": "k", "provider": "claude"}):
            out = self._render()
        assert "未配置" in out

    def test_multi_chain_render(self):
        cfg = {"_provider_list": [{"name": "alpha", "provider": "claude", "priority": 10}]}
        with patch("src.python.config.get_llm_config", return_value=cfg):
            out = self._render()
        assert "多链服务 (1 provider)" in out
        assert "alpha" in out


class TestStatusLine(unittest.TestCase):
    """页头状态行：五项取数、逐项降级、TTL 记忆化与页头接线。"""

    def setUp(self) -> None:
        reset_status_memo()

    def tearDown(self) -> None:
        reset_status_memo()

    # ── 分项取数 ──

    def test_last_report_formats_timestamp(self) -> None:
        """perf 历史末条时间戳 → MM-DD HH:MM。"""
        with patch(
            "src.python.core.perf.load_history",
            return_value=[{"timestamp": "2026-10-07T09:55:00"}],
        ):
            from src.python.tui.status_line import _last_report_part

            self.assertEqual(_last_report_part(), "上次报告 10-07 09:55")

    def test_last_report_interrupted_marker(self) -> None:
        """末条 status=interrupted → 时间戳带「（已中断）」，下次启动不误判为成功。"""
        with patch(
            "src.python.core.perf.load_history",
            return_value=[{"timestamp": "2026-10-07T09:55:00", "status": "interrupted"}],
        ):
            from src.python.tui.status_line import _last_report_part

            self.assertEqual(_last_report_part(), "上次报告 10-07 09:55（已中断）")

    def test_last_report_empty_and_broken(self) -> None:
        """无历史 / 读取异常 → 逐项降级为 —。"""
        from src.python.tui.status_line import _last_report_part

        with patch("src.python.core.perf.load_history", return_value=[]):
            self.assertEqual(_last_report_part(), "上次报告 —")
        with patch("src.python.core.perf.load_history", side_effect=OSError("损坏")):
            self.assertEqual(_last_report_part(), "上次报告 —")

    def test_cache_expired_from_stats(self) -> None:
        """缓存统计 expired 计数；异常降级为 —。"""
        from src.python.tui.status_line import _cache_expired_part

        with patch(
            "src.python.cache.operations.get_cache_stats",
            return_value=SimpleNamespace(expired=3),
        ):
            self.assertEqual(_cache_expired_part(), "缓存过期 3")
        with patch(
            "src.python.cache.operations.get_cache_stats",
            side_effect=OSError("目录不可读"),
        ):
            self.assertEqual(_cache_expired_part(), "", "取数失败同样不上屏（改由 [3] 面板查看）")

    def test_freshness_latest_from_price_cache(self) -> None:
        """最新价格缓存的 price_date → 数据日期 + 自然日龄（纯本地，不触交易日历）。"""
        from datetime import datetime

        today = datetime.now().date()
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "price_demo_v1.json"), "w", encoding="utf-8") as f:
                json.dump({"_data": {"price": 1.23, "price_date": today.isoformat()}}, f)
            with (
                patch("src.python.cache.get_cache_dir", return_value=tmp),
                patch(
                    "src.python.cache.get",
                    return_value={"price": 1.23, "price_date": today.isoformat()},
                ),
            ):
                from src.python.tui.status_line import _freshness_part

                self.assertEqual(_freshness_part(), f"新鲜度 {today:%m-%d}（0天）")

    def test_freshness_reads_version_stamped_cache_file(self) -> None:
        """回归：带版本戳的缓存文件名 → 逻辑键，且 ``get`` 的 TTL 参数必填。

        两个缺陷曾让本项恒为「—」：① 从文件名反推键时未剥版本戳，拼出
        `{key}_v4_v4.json`；② ``cache.get`` 的 ``max_age_seconds`` 未传，
        TypeError 被兜底吞掉。本用例不 patch ``get``，走真实读档路径。
        """
        from datetime import datetime

        from src.python.cache._paths import _CACHE_KEY_VERSION

        today = datetime.now().date()
        with tempfile.TemporaryDirectory() as tmp:
            payload = {"_ts": time.time(), "_data": {"price": 1.23, "price_date": today.isoformat()}}
            fname = f"price_demo_{_CACHE_KEY_VERSION}.json"
            with open(os.path.join(tmp, fname), "w", encoding="utf-8") as f:
                json.dump(payload, f)
            # 目录单源在 _paths._CACHE_DIR（get_cache_dir 与 get 的路径拼装同读它）
            with patch("src.python.cache._paths._CACHE_DIR", tmp):
                from src.python.tui.status_line import _freshness_part

                part = _freshness_part()
        assert part == f"新鲜度 {today:%m-%d}（0天）", f"未读到版本戳缓存：{part!r}"
        assert part.action == ""  # 数据新鲜 → 不提示动作

    def test_freshness_no_price_cache(self) -> None:
        """无价格缓存 → 新鲜度 —。"""
        with tempfile.TemporaryDirectory() as tmp:
            with patch("src.python.cache.get_cache_dir", return_value=tmp):
                from src.python.tui.status_line import _freshness_part

                self.assertEqual(_freshness_part(), "新鲜度 —")

    def test_freshness_source_failure(self) -> None:
        """取数异常 → 逐项降级为 —。"""
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "price_demo_v1.json"), "w", encoding="utf-8") as f:
                json.dump({"_data": {"price": 1.23, "price_date": "2026-10-07"}}, f)
            with (
                patch("src.python.cache.get_cache_dir", return_value=tmp),
                patch("src.python.cache.get", side_effect=OSError("读档失败")),
            ):
                from src.python.tui.status_line import _freshness_part

                self.assertEqual(_freshness_part(), "新鲜度 —")

    def test_degraded_count_from_health_history(self) -> None:
        """健康历史末条 fail_count → 数据源失败数；无记录 → —。"""
        from src.python.tui.status_line import _degraded_part

        with patch(
            "src.python.core.perf.summarize_health_history",
            return_value=[{"fail_count": 2}],
        ):
            self.assertEqual(_degraded_part(), "数据源失败 2")
        with patch("src.python.core.perf.summarize_health_history", return_value=[]):
            self.assertEqual(_degraded_part(), "数据源失败 —")
        with patch(
            "src.python.core.perf.summarize_health_history",
            side_effect=OSError("读档失败"),
        ):
            self.assertEqual(_degraded_part(), "数据源失败 —")

    def test_llm_status_dot(self) -> None:
        """LLM 状态点：已配置 ● / 未配置 ○ / 异常 —。"""
        from src.python.tui.status_line import _llm_part

        with patch(
            "src.python.core.system_info.llm_status",
            return_value={"configured": True},
        ):
            self.assertEqual(_llm_part(), "LLM ●")
        with patch(
            "src.python.core.system_info.llm_status",
            return_value={"configured": False},
        ):
            self.assertEqual(_llm_part(), "LLM ○")
        with patch(
            "src.python.core.system_info.llm_status",
            side_effect=RuntimeError("配置故障"),
        ):
            self.assertEqual(_llm_part(), "LLM —")

    def test_llm_status_dot_shows_chain_head(self) -> None:
        """多链时 LLM 段携带链首线路名（换序/手改后回首页即见新链首）。"""
        from src.python.tui.status_line import _llm_part

        with patch(
            "src.python.core.system_info.llm_status",
            return_value={"configured": True, "chain_head": "kimi-k3"},
        ):
            self.assertEqual(_llm_part(), "LLM ● kimi-k3")

    # ── 整行组装 ──

    def test_full_line_format_and_action_line(self) -> None:
        """五项拼接为单行；异常段汇总为第二行动作提示。"""
        with (
            patch("src.python.core.perf.load_history", return_value=[]),
            patch(
                "src.python.cache.operations.get_cache_stats",
                return_value=SimpleNamespace(expired=5),
            ),
            patch("src.python.core.perf.summarize_health_history", return_value=[]),
            patch(
                "src.python.core.system_info.llm_status",
                return_value={"configured": True},
            ),
            tempfile.TemporaryDirectory() as tmp,
            patch("src.python.cache.get_cache_dir", return_value=tmp),
        ):
            line = build_status_line()
        head, _, actions = line.partition("\n")
        self.assertTrue(head.startswith("状态 │ "))
        for segment in ("上次报告 —", "缓存过期 5", "新鲜度 —", "数据源失败 —", "LLM ●"):
            self.assertIn(segment, head)
        self.assertIn("[B] 生成标准报告", actions)
        self.assertIn("[3] 清理过期缓存", actions)
        self.assertIn("[2] 更新行情缓存", actions)

    def test_normal_state_has_no_action_line(self) -> None:
        """全部正常 → 无第二行（不向「一切正常」喊话）。"""
        from datetime import datetime

        from src.python.cache._paths import _CACHE_KEY_VERSION

        today = datetime.now().date()
        with tempfile.TemporaryDirectory() as tmp:
            payload = {"_ts": time.time(), "_data": {"price": 1.23, "price_date": today.isoformat()}}
            with open(os.path.join(tmp, f"price_demo_{_CACHE_KEY_VERSION}.json"), "w", encoding="utf-8") as f:
                json.dump(payload, f)
            with (
                patch(
                    "src.python.core.perf.load_history",
                    return_value=[{"timestamp": "2026-10-07T09:55:00"}],
                ),
                patch(
                    "src.python.cache.operations.get_cache_stats",
                    return_value=SimpleNamespace(expired=0),
                ),
                patch("src.python.core.perf.summarize_health_history", return_value=[{"fail_count": 0}]),
                patch(
                    "src.python.core.system_info.llm_status",
                    return_value={"configured": True},
                ),
                patch(
                    "src.python.core.data_freshness.header_freshness",
                    return_value={
                        "date": today.isoformat(),
                        "age_days": 0,
                        "stale": False,
                    },
                ),
                patch("src.python.cache._paths._CACHE_DIR", tmp),
            ):
                line = build_status_line()
        self.assertNotIn("└", line)
        self.assertIn("LLM ●", line)
        self.assertNotIn("缓存过期", line)  # 0 个过期 → 整段静默
        self.assertIn(f"新鲜度 {today:%m-%d}（0天）", line)

    def test_action_line_wraps_on_narrow_terminal(self) -> None:
        """窄终端：动作提示按列宽折行，不丢菜单键、不屈出终宽。"""
        from src.python.tui.text_layout import display_width

        reset_status_memo()
        with (
            patch("src.python.core.perf.load_history", return_value=[]),
            patch(
                "src.python.cache.operations.get_cache_stats",
                return_value=SimpleNamespace(expired=5),
            ),
            patch("src.python.core.perf.summarize_health_history", return_value=[{"fail_count": 3}]),
            patch(
                "src.python.core.system_info.llm_status",
                return_value={"configured": False},
            ),
            patch("src.python.tui.status_line.terminal_columns", return_value=46),
            tempfile.TemporaryDirectory() as tmp,
            patch("src.python.cache.get_cache_dir", return_value=tmp),
        ):
            lines = build_status_line().split("\n")
        reset_status_memo()  # 防窄版文字漏入后续用例的记忆
        self.assertGreater(len(lines), 2, f"窄终端未折行：{lines}")
        for text in lines[1:]:
            self.assertLessEqual(display_width(text), 44, f"动作提示超出终宽：{text!r}")
        joined = " ".join(lines[1:])
        for template in ("[B] 生成标准报告", "[2] 更新行情缓存", "[D]→V 看数据源记录", "[G]→L 配置 LLM"):
            self.assertIn(template, joined)

    def test_all_sources_fail_degrades_per_item(self) -> None:
        """四路取数全挂 → 逐项显示 —，不向调用方抛出；缓存过期段静默不上屏。"""
        boom = side_effect = RuntimeError("全挂")
        with (
            patch("src.python.core.perf.load_history", side_effect=boom),
            patch("src.python.cache.operations.get_cache_stats", side_effect=side_effect),
            patch("src.python.cache.get_cache_dir", side_effect=side_effect),
            patch("src.python.core.perf.summarize_health_history", side_effect=side_effect),
            patch("src.python.core.system_info.llm_status", side_effect=side_effect),
        ):
            line = build_status_line()
        for label in ("上次报告", "新鲜度", "数据源失败", "LLM"):
            self.assertIn(f"{label} —", line)
        self.assertNotIn("缓存过期", line)

    def test_cache_expired_segment_hidden_when_zero(self) -> None:
        """缓存过期 0 → 整段不上屏（启动已自动清理，常态 0 只会引人发问）。"""
        from src.python.tui.status_line import _cache_expired_part

        with patch(
            "src.python.cache.operations.get_cache_stats",
            return_value=SimpleNamespace(expired=0),
        ):
            self.assertEqual(_cache_expired_part(), "")

        with (
            patch(
                "src.python.cache.operations.get_cache_stats",
                return_value=SimpleNamespace(expired=0),
            ),
            patch("src.python.core.perf.load_history", return_value=[]),
            patch("src.python.core.perf.summarize_health_history", return_value=[]),
            patch("src.python.core.system_info.llm_status", return_value={"configured": True}),
            tempfile.TemporaryDirectory() as tmp,
            patch("src.python.cache.get_cache_dir", return_value=tmp),
        ):
            line = build_status_line()
        self.assertNotIn("缓存过期", line)
        self.assertNotIn(" ·  · ", line)  # 空段不留下多余分隔符

    def test_memo_ttl_reuses_then_refreshes(self) -> None:
        """TTL 内复用记忆（重活不重取），过期后重新取数。"""
        mock_stats = MagicMock(return_value=SimpleNamespace(expired=1))
        with patch("src.python.cache.operations.get_cache_stats", mock_stats):
            build_status_line(now=1_000.0)
            build_status_line(now=1_020.0)  # TTL 内 → 复用
            self.assertEqual(mock_stats.call_count, 1)
            build_status_line(now=1_100.0)  # 超过 45s → 重取
            self.assertEqual(mock_stats.call_count, 2)

    def test_print_header_renders_status_line(self) -> None:
        """print_header 输出常驻状态行（页头接线）。"""
        with patch(
            "src.python.tui.status_line.build_status_line",
            return_value="状态 │ 单测行",
        ):
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                print_header()
                out = mock_out.getvalue()
        self.assertIn("状态 │ 单测行", out)


class TestHeaderBrandColor(unittest.TestCase):
    """页头品牌色与分组结构色：一色一职责（测试环境颜色常量为空，故强制着色后校验包裹位置）。"""

    def test_app_name_version_bold_orange(self):
        import src.python.core.ansi_colors as colors
        from src.python.core.constants import APP_NAME, APP_VERSION

        buf = StringIO()
        with (
            patch.object(colors, "ORANGE", "<O>"),
            patch.object(colors, "BOLD", "<B>"),
            patch.object(colors, "BLUE", "<U>"),
            patch.object(colors, "RESET", "</>"),
            patch("sys.stdout", buf),
        ):
            print_header()
        out = buf.getvalue()
        self.assertIn(f"<B><O>{APP_NAME}  v{APP_VERSION}</>", out, "应用名与版本号须为橙色粗体")
        self.assertNotIn("<U>", out, "品牌行不得落结构蓝——蓝只属于分组标题")

    def test_menu_group_heading_bold_blue(self):
        import src.python.core.ansi_colors as colors
        from src.python.tui.tui_menu import render_menu

        buf = StringIO()
        with (
            patch.object(colors, "BLUE", "<U>"),
            patch.object(colors, "BOLD", "<B>"),
            patch.object(colors, "RESET", "</>"),
            patch("sys.stdout", buf),
        ):
            render_menu(0)
        out = buf.getvalue()
        self.assertIn("<B><U>  ── 生成报告 ──</>", out, "分组标题须为蓝色粗体")
