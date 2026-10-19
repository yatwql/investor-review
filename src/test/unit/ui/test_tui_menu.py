"""TUI 菜单模块单元测试。

测试目标：
  - MENU_ITEMS 结构完整性
  - index_by_key 快捷键查找
  - print_sep / print_header 不崩溃
  - _exit_app 退出行为
  - _show_llm_config_status 格式

运行：
  pytest src/test/unit/ui/test_tui_menu.py -v
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.python.tui.status_line import build_status_line, reset_status_memo
from src.python.tui.tui_menu import (
    MENU_ITEMS,
    index_by_key,
    print_header,
    print_sep,
    get_config_cache,
)
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


class TestMenuItems(unittest.TestCase):
    """MENU_ITEMS 结构完整性测试。"""

    def setUp(self):
        """重置 MENU_ITEMS 回调为 None，防止前序测试副作用。"""
        import src.python.tui.tui_menu as _tm

        for i, (key, label, _cb, is_exit) in enumerate(_tm.MENU_ITEMS):
            _tm.MENU_ITEMS[i] = (key, label, None, is_exit)

    def test_key_set_complete(self) -> None:
        """菜单键集合完整（会话/报告/缓存/配置/诊断/退出各域齐备，逐键断言不写死条数）。"""
        expected = {
            "E", "B", "L", "W", "Q", "D",
            "1", "2", "3",
            "P", "I", "A", "S", "M", "R",
            "V", "H", "T", "X",
        }  # fmt: skip
        self.assertSetEqual({item[0] for item in MENU_ITEMS}, expected)

    def test_digit_keys_contiguous(self) -> None:
        """数字键必须连续无断层（1..N）：断层会让用户按到一个「不存在的键」并被当成误操作。

        守护要点：数字键是主菜单第一入口（识别成本为零），一旦中间缺号，界面就在
        误导用户；本断言只锁「连续 + 从 1 起」的结构关系，不锁具体条数。
        """
        digits = sorted(int(item[0]) for item in MENU_ITEMS if item[0].isdigit())
        assert digits == list(range(1, len(digits) + 1)), f"数字键不连续: {digits}"

    def test_callback_dispatch_covers_every_non_exit_item(self) -> None:
        """每个非退出菜单项都有派发回调（键改号后不得漏接线）。"""
        import src.python.tui.tui as _tui

        _tui._bind_callbacks()
        missing = [key for key, _label, cb, is_exit in MENU_ITEMS if not is_exit and cb is None]
        assert missing == [], f"菜单项缺回调: {missing}"

    def test_labels_within_display_budget(self) -> None:
        """菜单标签显示宽 ≤ 48（渲染前缀 7 列，80 列终端不折行，东亚宽度口径）。"""
        import unicodedata

        for key, label, _cb, _ex in MENU_ITEMS:
            width = sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in label)
            self.assertLessEqual(width, 48, f"[{key}] 标签显示宽 {width} 超预算: {label}")

    def test_whatif_item(self) -> None:
        """What-if 菜单项在报告生成组后（快捷键 W）。"""
        key, label, cb, is_exit = MENU_ITEMS[index_by_key("W")]
        self.assertEqual(key, "W")
        self.assertIn("What-if", label)
        self.assertIsNone(cb)
        self.assertFalse(is_exit)

    def test_first_item_excel(self) -> None:
        """第一项快捷键 E。"""
        key, label, cb, is_exit = MENU_ITEMS[index_by_key("E")]
        self.assertEqual(key, "E")
        self.assertIn("Excel", label)
        self.assertIsNone(cb)
        self.assertFalse(is_exit)

    def test_qa_item(self) -> None:
        """报告追问项在 What-if 后（快捷键 Q）。"""
        key, label, cb, is_exit = MENU_ITEMS[index_by_key("Q")]
        self.assertEqual(key, "Q")
        self.assertIn("追问", label)
        self.assertIsNone(cb)
        self.assertFalse(is_exit)

    def test_last_item_exit(self) -> None:
        """最后一项快捷键 X，is_exit=True。"""
        key, label, cb, is_exit = MENU_ITEMS[-1]
        self.assertEqual(key, "X")
        self.assertIn("退出", label)
        self.assertIsNone(cb)
        self.assertTrue(is_exit)

    def test_view_logs_item(self) -> None:
        """日志查看项在退出前（快捷键 V）。"""
        key, label, cb, is_exit = MENU_ITEMS[index_by_key("V")]
        self.assertEqual(key, "V")
        self.assertIn("运行日志", label)
        self.assertIsNone(cb)
        self.assertFalse(is_exit)

    def test_health_history_item(self) -> None:
        """健康历史项在日志查看后（快捷键 H）。"""
        key, label, cb, is_exit = MENU_ITEMS[index_by_key("H")]
        self.assertEqual(key, "H")
        self.assertIn("健康历史", label)
        self.assertIsNone(cb)
        self.assertFalse(is_exit)

    def test_config_dir_info_item(self) -> None:
        """查看配置与目录信息项在报告追问后（快捷键 D）。"""
        key, label, cb, is_exit = MENU_ITEMS[index_by_key("D")]
        self.assertEqual(key, "D")
        self.assertIn("配置与目录信息", label)
        self.assertIsNone(cb)
        self.assertFalse(is_exit)

    def test_doctor_item(self) -> None:
        """系统自检项在健康历史后、退出前（快捷键 T）。"""
        key, label, cb, is_exit = MENU_ITEMS[index_by_key("T")]
        self.assertEqual(key, "T")
        self.assertIn("系统自检", label)
        self.assertIsNone(cb)
        self.assertFalse(is_exit)

    def test_all_keys_unique(self) -> None:
        """所有快捷键不重复。"""
        keys = [item[0] for item in MENU_ITEMS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_all_labels_nonempty(self) -> None:
        """所有标签非空。"""
        for item in MENU_ITEMS:
            self.assertTrue(len(item[1]) > 0, f"Label for key '{item[0]}' is empty")

    def test_callbacks_are_none_initially(self) -> None:
        """回调初始化为 None。"""
        for item in MENU_ITEMS:
            self.assertIsNone(item[2], f"Key '{item[0]}' callback should be None initially")

    def test_only_exit_is_exit(self) -> None:
        """仅退出项 is_exit=True。"""
        exit_count = sum(1 for item in MENU_ITEMS if item[3])
        self.assertEqual(exit_count, 1)


class TestIndexByKey(unittest.TestCase):
    """index_by_key 快捷键查找测试（结构关系断言，菜单增删不失效）。"""

    def test_every_key_resolves_to_itself(self) -> None:
        """每个菜单键经 index_by_key 定位回自身（键↔索引双向一致）。"""
        for key, _label, _cb, _ex in MENU_ITEMS:
            idx = index_by_key(key)
            self.assertIsNotNone(idx, key)
            self.assertEqual(MENU_ITEMS[idx][0], key)

    def test_first_and_last_positions(self) -> None:
        """首项为 E、末项为退出键 X（位序语义，不写死条数）。"""
        self.assertEqual(index_by_key("E"), 0)
        self.assertEqual(index_by_key("X"), len(MENU_ITEMS) - 1)

    def test_whatif_after_llm(self) -> None:
        """What-if 紧跟完整报告之后。"""
        self.assertEqual(index_by_key("W"), index_by_key("L") + 1)

    def test_find_nonexistent(self) -> None:
        self.assertIsNone(index_by_key("Z"))

    def test_find_lowercase(self) -> None:
        """小写字母未实现——必须大写。"""
        self.assertIsNone(index_by_key("e"))

    def test_find_number(self) -> None:
        """数字快捷键可定位（缓存类命令项）。"""
        idx = index_by_key("1")
        self.assertIsNotNone(idx)
        self.assertEqual(MENU_ITEMS[idx][0], "1")

    def test_find_empty(self) -> None:
        self.assertIsNone(index_by_key(""))


class TestPrintFunctions(unittest.TestCase):
    """打印函数不崩溃测试。"""

    def test_print_sep_default(self) -> None:
        """默认分隔线。"""
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            print_sep()
            output = mock_out.getvalue()
            self.assertIn("=", output)

    def test_print_sep_custom(self) -> None:
        """自定义字符和宽度。"""
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            print_sep(char="-", width=10)
            self.assertIn("----------", mock_out.getvalue())

    def test_print_header(self) -> None:
        """标题头包含系统名称 + 版本号。"""
        from src.python.core.constants import APP_NAME, APP_VERSION

        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            print_header()
            self.assertIn(APP_NAME, mock_out.getvalue())
            self.assertIn(f"v{APP_VERSION}", mock_out.getvalue())


class TestConfigCache(unittest.TestCase):
    """配置缓存访问测试。"""

    def setUp(self) -> None:
        """重置模块级 _config_cache 为初始 None，防止前序测试的副作用。"""
        import src.python.tui.tui_menu as _tm

        _tm._config_cache = None

    def test_get_config_cache_default(self) -> None:
        """未初始化时返回 None。"""
        self.assertIsNone(get_config_cache())


class TestFilterMenuLlmModules(unittest.TestCase):
    """菜单 LLM 清单门面恒等；模块清单与缓存域注册表职责分离。"""

    def test_filter_is_identity_facade(self):
        """过滤器恒等返回（调用面保留）：键值对与注册表清单完全一致。"""
        from src.python.core.registry import get_llm_module_names
        from src.python.tui.tui_menu import filter_menu_llm_modules

        module_names = get_llm_module_names()
        self.assertEqual(filter_menu_llm_modules(module_names), module_names)

    def test_registry_excludes_debate_but_cache_domain_keeps(self):
        """模块清单不含辩论三段；缓存域注册表仍登记其前缀/TTL/组归属。"""
        from src.python.core.registry import get_cache_registry, get_llm_module_names

        names = get_llm_module_names()
        for key in ("debate_pro", "debate_con", "debate_synthesis"):
            self.assertNotIn(key, names)
        cache_types = {m.data_type for m in get_cache_registry()}
        for data_type in ("llm_debate_pro", "llm_debate_con", "llm_debate_synthesis"):
            self.assertIn(data_type, cache_types)


@pytest.mark.unit
@pytest.mark.unit_ui
class TestFeatureGatedMenuItems:
    """受功能开关约束的菜单项（[T] 系统自检）。

    `_apply_feature_gates` 就裁剪 `MENU_ITEMS`，故每个用例前后都必须快照/还原——
    否则会污染同进程内其它测试对菜单项数量的断言。
    """

    @pytest.fixture(autouse=True)
    def _restore_menu(self):
        import src.python.tui.tui_menu as tm

        snapshot = list(tm.MENU_ITEMS)
        yield
        tm.MENU_ITEMS[:] = snapshot

    def _apply(self, enabled: bool):
        import src.python.tui.tui_menu as tm

        with patch("src.python.config.features.is_feature_enabled", return_value=enabled):
            tm._apply_feature_gates()

    def test_gated_keys_are_registered_in_menu(self):
        """门控表里的键必须真实存在于菜单——否则开关写了也没人看得见。"""
        import src.python.tui.tui_menu as tm

        keys = {item[0] for item in tm.MENU_ITEMS}
        assert set(tm.FEATURE_GATED_ITEMS) <= keys

    def test_gated_flag_is_registered_feature(self):
        """门控开关必须是注册表中已声明的功能开关（防拼写错误静默失效）。"""
        import src.python.tui.tui_menu as tm
        from src.python.config.features import FEATURE_FLAGS

        for flag in tm.FEATURE_GATED_ITEMS.values():
            assert flag in FEATURE_FLAGS

    def test_doctor_item_hidden_when_flag_off(self):
        import src.python.tui.tui_menu as tm

        self._apply(enabled=False)
        assert "T" not in {item[0] for item in tm.MENU_ITEMS}

    def test_doctor_item_visible_when_flag_on(self):
        import src.python.tui.tui_menu as tm

        self._apply(enabled=True)
        assert "T" in {item[0] for item in tm.MENU_ITEMS}

    def test_doctor_item_visible_under_defaults(self):
        """默认配置下 [T] 即在菜单里（系统自检已转正为默认开启）。

        上面两条都用 patch 覆盖取值，测不出默认值本身——默认值若改回关闭，
        它们仍全绿，而用户打开的菜单里会少一项。
        """
        import src.python.tui.tui_menu as tm

        tm._apply_feature_gates()

        assert "T" in {item[0] for item in tm.MENU_ITEMS}

    def test_config_dir_info_unaffected_by_doctor_gate(self):
        """开关关闭只裁剪 [T] 自检，[D] 查看配置与目录信息（无门控）仍在菜单中。"""
        import src.python.tui.tui_menu as tm

        self._apply(enabled=False)
        assert "D" in {item[0] for item in tm.MENU_ITEMS}

    def test_callback_binding_survives_gating(self):
        """裁剪后其余项的回调绑定不受影响（索引与渲染一致）。"""
        import src.python.tui.tui_menu as tm

        self._apply(enabled=False)
        keys = [item[0] for item in tm.MENU_ITEMS]
        assert keys[-1] == "X"
        assert len(keys) == len(set(keys))

    def test_gating_is_idempotent(self):
        import src.python.tui.tui_menu as tm

        self._apply(enabled=False)
        first = list(tm.MENU_ITEMS)
        self._apply(enabled=False)
        assert tm.MENU_ITEMS == first


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

    def test_flat_configured_line(self):
        with patch("src.python.config.get_llm_config", return_value={"api_key": "k", "provider": "claude"}):
            out = self._render()
        assert "已配置" in out
        assert "provider=claude" in out
        assert "模型路由" in out

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
            self.assertEqual(_cache_expired_part(), "缓存过期 —")

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
        """健康历史末条 fail_count → 备用源数；无记录 → —。"""
        from src.python.tui.status_line import _degraded_part

        with patch(
            "src.python.core.perf.summarize_health_history",
            return_value=[{"fail_count": 2}],
        ):
            self.assertEqual(_degraded_part(), "备用源 2")
        with patch("src.python.core.perf.summarize_health_history", return_value=[]):
            self.assertEqual(_degraded_part(), "备用源 —")
        with patch(
            "src.python.core.perf.summarize_health_history",
            side_effect=OSError("读档失败"),
        ):
            self.assertEqual(_degraded_part(), "备用源 —")

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

    # ── 整行组装 ──

    def test_full_line_format_with_menu_hint(self) -> None:
        """五项拼接为单行并携带详情菜单指引。"""
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
        self.assertTrue(line.startswith("状态 │ "))
        self.assertIn("上次报告 —", line)
        self.assertIn("缓存过期 5", line)
        self.assertIn("新鲜度 —", line)
        self.assertIn("备用源 —", line)
        self.assertIn("LLM ●", line)
        self.assertIn("〔详情 [4][H][S]〕", line)

    def test_all_sources_fail_degrades_per_item(self) -> None:
        """五路取数全挂 → 逐项显示 —，不向调用方抛出。"""
        boom = side_effect = RuntimeError("全挂")
        with (
            patch("src.python.core.perf.load_history", side_effect=boom),
            patch("src.python.cache.operations.get_cache_stats", side_effect=side_effect),
            patch("src.python.cache.get_cache_dir", side_effect=side_effect),
            patch("src.python.core.perf.summarize_health_history", side_effect=side_effect),
            patch("src.python.core.system_info.llm_status", side_effect=side_effect),
        ):
            line = build_status_line()
        for label in ("上次报告", "缓存过期", "新鲜度", "备用源", "LLM"):
            self.assertIn(f"{label} —", line)

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


if __name__ == "__main__":
    unittest.main()


class TestMainLoopExitKeys(unittest.TestCase):
    """首页退出通道：`X`（显式退出项）与 `0`（退出别名）都退出、其它键不误退。"""

    """首页退出通道：`X`（显式退出项）与 `0`（退出别名）都退出；其它键不误退。"""

    @staticmethod
    def _drive(keys: list[str]) -> tuple[list[str], str]:
        """驱动真实 main() 循环：返回（退出回调触发记录, 打印内容）。"""
        import contextlib
        import io
        from unittest.mock import patch

        import src.python.tui.tui as tui_mod
        import src.python.tui.tui_menu as menu_mod

        fired: list[str] = []
        seq = iter(keys)

        def _fake_key() -> str:
            try:
                return next(seq)
            except StopIteration:
                raise SystemExit from None

        def _fake_exit() -> None:
            fired.append("exit")
            raise SystemExit

        out = io.StringIO()
        with (
            patch.object(tui_mod, "get_key", _fake_key),
            patch.object(tui_mod, "exit_app", _fake_exit),
            patch.object(menu_mod, "exit_app", _fake_exit),
            patch.object(tui_mod, "init_config"),
            patch.object(tui_mod, "_apply_feature_gates"),
            patch.object(tui_mod, "_bind_callbacks"),
            patch.object(tui_mod, "print_header"),
            patch.object(tui_mod, "show_config"),
            patch.object(tui_mod, "render_menu"),
        ):
            try:
                with contextlib.redirect_stdout(out):
                    tui_mod.main()
            except SystemExit:
                pass
        return fired, out.getvalue()

    def test_zero_key_exits(self):
        """按 0 → 退出（与子菜单「0 = 返回」的习惯一致，首页返回即退出程序）。"""
        fired, _ = self._drive(["0"])
        self.assertEqual(fired, ["exit"])

    def test_upper_x_exits_via_menu_item(self):
        """按 X → 命中 [X] 退出项。"""
        fired, _ = self._drive(["X"])
        self.assertEqual(fired, ["exit"])

    def test_non_exit_key_does_not_exit(self):
        """按未映射键（如 Z）不退出（按键无效但不误退）。"""
        fired, _ = self._drive(["Z"])
        self.assertEqual(fired, [])

    def test_footer_documents_both_exit_keys(self):
        """页脚同时写出 `Esc`、`0` 与 `X` 都能退出，否则用户无从发现退出别名。"""
        import contextlib
        import io

        from src.python.tui.tui_menu import render_menu

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            render_menu(0)
        footer = buf.getvalue()
        self.assertIn("Esc / 0 / X 退出", footer)
        self.assertIn("Ctrl+C 退出", footer)

    def test_exit_item_label_mentions_zero_alias(self):
        """退出项标签本身也点明 `0 亦可`——光标停在该项时就能看到，不必只看页脚。"""
        from src.python.tui.tui_menu import MENU_ITEMS

        exit_items = [item for item in MENU_ITEMS if item[3]]
        self.assertEqual(len(exit_items), 1)
        self.assertIn("0 亦可", exit_items[0][1])

    def test_footer_wraps_within_terminal_width(self):
        """窄屏（手机）页脚按可用宽度折行：不硬折、不越界，续行缩进对齐。"""
        import contextlib
        import io
        from unittest.mock import patch

        from src.python.tui.text_layout import display_width
        from src.python.tui.tui_menu import render_menu

        for columns in (40, 46, 60):
            buf = io.StringIO()
            with (
                patch.dict("os.environ", {"COLUMNS": str(columns)}),
                patch("os.get_terminal_size", side_effect=OSError()),
                contextlib.redirect_stdout(buf),
            ):
                render_menu(0)
            for line in buf.getvalue().splitlines():
                self.assertLessEqual(display_width(line), columns, (columns, line))


class TestRenderMenuNarrowDirect(unittest.TestCase):
    """首页菜单两档渲染：narrow 直达+导航并存（选中态 + 双提示页脚）/ 宽中档导航。"""

    @staticmethod
    def _render(columns: int) -> str:
        import contextlib
        import io
        from unittest.mock import patch

        from src.python.tui.tui_menu import render_menu

        buf = io.StringIO()
        with (
            patch.dict("os.environ", {"COLUMNS": str(columns)}),
            patch("os.get_terminal_size", side_effect=OSError()),
            contextlib.redirect_stdout(buf),
        ):
            render_menu(1)
        return buf.getvalue()

    def test_narrow_renders_selection_indicator(self):
        """narrow（40 列）同样渲染 `>` 选中指示器——方向键导航在窄屏可用。"""
        out = self._render(40)
        self.assertIn(">", out)

    def test_narrow_footer_documents_direct_and_nav_keys(self):
        """narrow 页脚同时写明直达与导航路径及退出键（40 列折行，按逻辑内容断言）。"""
        out = self._render(40)
        footer = " ".join(out.split("窄屏直达", 1)[1].split())
        self.assertIn("窄屏直达", out)
        self.assertIn("↑↓ 选择", footer)
        self.assertIn("Enter 执行", footer)
        self.assertIn("Esc / 0 /", footer)
        self.assertIn("X 退出", footer)
        self.assertIn("Ctrl+C 退出", footer)
        self.assertNotIn("方向键移动", out)

    def test_wide_keeps_selection_indicator_and_nav_footer(self):
        """宽屏（100 列）保留 `>` 选中态与方向键页脚（导航主路径不变）。"""
        out = self._render(100)
        self.assertIn(">", out)
        self.assertIn("方向键移动", out)
        self.assertIn("Esc / 0 / X 退出", out)


class TestNarrowMainLoopDirectNav(unittest.TestCase):
    """narrow 档主循环：直达键零重绘主路径不变；方向键/Enter 导航可用
    （非 TTY 回退整屏追加，TTY 原地重绘不滚屏）。"""

    @staticmethod
    def _drive(keys: list[str], columns: int, *, tty: bool = False):
        """驱动真实 main()：返回（退出记录, render_menu 次数, execute_item 参数, stdout, 清帧 spy）。"""
        import contextlib
        import io
        from unittest.mock import MagicMock, patch

        import src.python.tui.tui as tui_mod
        import src.python.tui.tui_menu as menu_mod

        fired: list[str] = []
        executed: list[int] = []
        seq = iter(keys)

        def _fake_key() -> str:
            try:
                return next(seq)
            except StopIteration:
                raise SystemExit from None

        def _fake_exit() -> None:
            fired.append("exit")
            raise SystemExit

        def _fake_execute(idx: int) -> None:
            executed.append(idx)

        render_mock = MagicMock()
        clear_mock = MagicMock()
        buf = io.StringIO()
        if tty:
            buf.isatty = lambda: True  # 模拟交互终端以走窄屏原地重绘分支
        with (
            patch.object(tui_mod, "get_key", _fake_key),
            patch.object(tui_mod, "exit_app", _fake_exit),
            patch.object(menu_mod, "exit_app", _fake_exit),
            patch.object(tui_mod, "terminal_columns", return_value=columns),
            patch.object(tui_mod, "init_config"),
            patch.object(tui_mod, "_apply_feature_gates"),
            patch.object(tui_mod, "_bind_callbacks"),
            patch.object(tui_mod, "execute_item", _fake_execute),
            patch.object(tui_mod, "print_header"),
            patch.object(tui_mod, "show_config"),
            patch.object(tui_mod, "render_menu", render_mock),
            patch.object(tui_mod, "_clear_last_frame", clear_mock),
        ):
            try:
                with contextlib.redirect_stdout(buf):
                    tui_mod.main()
            except SystemExit:
                pass
        return fired, render_mock.call_count, executed, buf.getvalue(), clear_mock

    def test_narrow_nav_keys_move_selection_and_rerender(self):
        """窄屏（40 列）方向键移动选中态并重绘（非 TTY 回退整屏追加）；未登记字母仍零重绘。"""
        fired, renders, executed, _, _ = self._drive(["KEY_DOWN", "KEY_UP", "Z", "0"], columns=40)
        self.assertEqual(fired, ["exit"])
        self.assertEqual(executed, [])
        self.assertEqual(renders, 3, "初帧 + 方向键两帧；未登记字母不重绘")

    def test_narrow_enter_executes_selected(self):
        """窄屏 Enter 执行当前选中项（与宽/中档一致的导航确认语义）。"""
        import src.python.tui.tui_menu as menu_mod

        fired, renders, executed, _, _ = self._drive(["KEY_ENTER", "0"], columns=40)
        sel_default = [i for i, (key, *_rest) in enumerate(menu_mod.MENU_ITEMS) if key == "L"][0]
        self.assertEqual(executed, [sel_default], "Enter 执行默认选中项（缺省键 L）")
        self.assertEqual(fired, ["exit"])
        self.assertEqual(renders, 2)

    def test_narrow_arrow_inplace_repaint_on_tty(self):
        """TTY 窄屏方向键走原地重绘分支：清帧助手被调用，仍在内层循环（不追加新屏）。"""
        fired, renders, _, _, cleared = self._drive(["KEY_DOWN", "0"], columns=40, tty=True)
        self.assertEqual(fired, ["exit"])
        self.assertEqual(renders, 2, "初帧 + 原地重绘一帧（不追加新屏）")
        cleared.assert_called_once()

    def test_narrow_arrow_fallback_without_ansi(self):
        """非 TTY（管道/测试）窄屏方向键回退整屏追加：清帧助手不被调用、重绘计数正确。"""
        fired, renders, _, _, cleared = self._drive(["KEY_DOWN", "0"], columns=40, tty=False)
        self.assertEqual(fired, ["exit"])
        self.assertEqual(renders, 2)
        cleared.assert_not_called()

    def test_clear_last_frame_writes_ansi(self):
        """清帧助手：n>0 输出光标上移 n 行 + 清屏至末尾；n=0 不输出。"""
        import contextlib
        import io as _io

        import src.python.tui.tui as tui_mod

        buf = _io.StringIO()
        with contextlib.redirect_stdout(buf):
            tui_mod._clear_last_frame(5)
            tui_mod._clear_last_frame(0)
        self.assertEqual(buf.getvalue(), "\x1b[5A\x1b[0J")

    def test_wide_arrow_key_rerenders(self):
        """宽屏（100 列）方向键仍走导航主路径：每按一次重绘一屏（整屏追加，不走原地重绘）。"""
        fired, renders, _, _, cleared = self._drive(["KEY_DOWN", "0"], columns=100)
        self.assertEqual(fired, ["exit"])
        self.assertEqual(renders, 2, "宽屏方向键移动选中态后重绘")
        cleared.assert_not_called()

    def test_esc_double_press_exits(self):
        """Esc 连按两次（3 秒窗口内）→ 退出（首按给确认提示，不立即退出）。"""
        fired, _, _, _, _ = self._drive(["KEY_ESC", "KEY_ESC"], columns=100)
        self.assertEqual(fired, ["exit"])

    def test_esc_single_press_shows_confirm_hint(self):
        """单次 Esc 不退出：输出「再按一次」确认提示（方向键拆包误判不致退出）。"""
        fired, renders, _, out, _ = self._drive(["KEY_ESC", "0"], columns=100)
        self.assertEqual(fired, ["exit"])
        self.assertIn("再按一次 Esc 退出", out)
        self.assertEqual(renders, 1, "提示不触发整屏重绘")

    def test_esc_armed_cancelled_by_navigation_key(self):
        """任何非 Esc 按键解除退出确认态：孤 Esc 挂起的确认不被后续按键引爆。"""
        fired, _, _, out, _ = self._drive(["KEY_ESC", "KEY_DOWN", "KEY_ESC", "0"], columns=100)
        self.assertEqual(fired, ["exit"])
        self.assertEqual(out.count("再按一次 Esc 退出"), 2, "两次独立 Esc 首按（确认态已被方向键解除）")

    def test_wide_arrow_inplace_repaint_on_tty(self):
        """宽屏 TTY 方向键同样原地重绘：宽/窄导航手感一致，不滚屏堆积。"""
        fired, renders, _, _, cleared = self._drive(["KEY_DOWN", "0"], columns=100, tty=True)
        self.assertEqual(fired, ["exit"])
        self.assertEqual(renders, 2)
        cleared.assert_called_once()

    def test_hint_lines_included_in_inplace_clear(self):
        """反馈行并入原地重绘清除范围：清帧调用 = 帧行数 + 反馈行数（防清帧错位）。"""
        fired, renders, _, out, cleared = self._drive(["KEY_ESC", "KEY_DOWN", "0"], columns=40, tty=True)
        self.assertEqual(fired, ["exit"])
        self.assertEqual(renders, 2)
        cleared.assert_called_once_with(1)  # 渲染器 mock 帧行数 0 + Esc 提示 1 行


class TestTierSemanticParity(unittest.TestCase):
    """守护「分档只改版式不改语义」（架构设计约束·TUI 分档条目）：同一按键在窄/宽两档产生
    相同的语义动作与可观察反馈——分档至多改变呈现方式（原地重绘 vs 整屏追加、
    单行提示 vs 重绘一屏），不得删改按键语义或反馈本身。"""

    _drive = staticmethod(TestNarrowMainLoopDirectNav._drive)

    def test_registered_letter_parity(self):
        """登记字母键：两档执行同一菜单项（语义不随宽度漂移）。"""
        narrow = self._drive(["A", "0"], columns=40)
        wide = self._drive(["A", "0"], columns=100)
        self.assertEqual(narrow[2], wide[2], "执行同一选中项")
        self.assertTrue(narrow[2], "确实执行了 [A]")

    def test_enter_and_nav_parity(self):
        """方向键 + Enter：两档执行同一选中项。"""
        narrow = self._drive(["KEY_DOWN", "KEY_ENTER", "0"], columns=40)
        wide = self._drive(["KEY_DOWN", "KEY_ENTER", "0"], columns=100)
        self.assertEqual(narrow[2], wide[2], "↓ 后 Enter 执行同一项")
        self.assertTrue(narrow[2])

    def test_unregistered_letter_feedback_both_tiers(self):
        """未登记字母：两档都有可观察反馈（窄 = 单行提示文本，宽 = 重绘一屏）。"""
        narrow = self._drive(["Z", "0"], columns=40)
        wide = self._drive(["Z", "0"], columns=100)
        self.assertIn("未登记", narrow[3], "窄屏未登记键须有单行反馈")
        self.assertEqual(wide[1], 2, "宽档未登记键反馈 = 重绘一屏")

    def test_unknown_key_feedback_both_tiers(self):
        """未知键（KEY_RIGHT）：两档都有可观察反馈（窄 = 单行提示，宽 = 重绘）。"""
        narrow = self._drive(["KEY_RIGHT", "0"], columns=40)
        wide = self._drive(["KEY_RIGHT", "0"], columns=100)
        self.assertIn("未识别按键", narrow[3], "窄屏未知键须有单行反馈")
        self.assertEqual(wide[1], 2, "宽档未知键反馈 = 重绘一屏")

    def test_esc_exit_parity(self):
        """Esc 连按两次退出：两档一致。"""
        narrow = self._drive(["KEY_ESC", "KEY_ESC"], columns=40)
        wide = self._drive(["KEY_ESC", "KEY_ESC"], columns=100)
        self.assertEqual(narrow[0], ["exit"])
        self.assertEqual(wide[0], ["exit"])
