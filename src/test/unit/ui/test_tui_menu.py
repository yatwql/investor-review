"""TUI 菜单模块单元测试。

测试目标：
  - MENU_ITEMS 结构完整性
  - index_by_key 快捷键查找
  - print_sep / print_header 不崩溃
  - _exit_app 退出行为
  - _show_llm_config_status 格式

运行：
  pytest src/test/unit/ui/test_tui_menu.py -v"""

from __future__ import annotations
import unittest
from io import StringIO
from unittest.mock import patch
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

    def test_numeric_keys_are_contiguous(self) -> None:
        """首页数字键必须是 1..N 连续区间（允许字母项任意；禁止 1/3 这类跳号）。

        数字键在首页是少数数据类操作的快捷别名（字母才是主入口），因此不要求
        「全菜单编号化」；但一旦出现跳号，用户按空号会得到「未登记键」反馈，
        属界面误导而非用户误操作。
        """
        numeric = sorted(int(key) for key, *_ in MENU_ITEMS if key.isdigit())
        self.assertEqual(numeric, list(range(1, len(numeric) + 1)), f"首页数字键跳号：{numeric}")

    def test_key_set_complete(self) -> None:
        """菜单键集合完整（会话/报告/缓存/配置/诊断/退出各域齐备，逐键断言不写死条数）。"""
        expected = {
            "E", "B", "L", "W", "Q", "D",
            "1", "2", "3", "U",
            "C", "S", "G", "R",
            "X",
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

    def test_diagnose_item(self) -> None:
        """诊断与排查聚合为一项（L/V/H/T 均下沉到二级）。"""
        key, label, cb, is_exit = MENU_ITEMS[index_by_key("D")]
        self.assertEqual(key, "D")
        self.assertIn("诊断", label)
        self.assertIsNone(cb)
        self.assertFalse(is_exit)
        for letter in ("V", "H", "T"):
            self.assertIsNone(index_by_key(letter), f"顶层不应再有 {letter}")

    def test_global_settings_item(self) -> None:
        """全局设置聚合为一项（D/F/O/L/I/A/M 下沉）。"""
        key, label, _cb, is_exit = MENU_ITEMS[index_by_key("G")]
        self.assertEqual(key, "G")
        self.assertIn("全局设置", label)
        self.assertFalse(is_exit)
        for letter in ("M", "I", "A"):
            self.assertIsNone(index_by_key(letter), f"顶层不应再有 {letter}")

    def test_config_dir_info_item(self) -> None:
        """配置与目录信息已下沉为 [G] 子项，顶层不单列（顶层 C 是章节显隐）。"""
        key, label, _cb, _is_exit = MENU_ITEMS[index_by_key("C")]
        self.assertEqual(key, "C")
        self.assertIn("章节显隐", label)
        self.assertNotIn("目录", label)

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

    def test_doctor_item_never_gated(self):
        """[T] 已下沉到 [D] 且恒上屏，不再受功能开关门控。"""
        import src.python.tui.tui_menu as tm

        self._apply(enabled=False)
        assert "T" not in {item[0] for item in tm.MENU_ITEMS}
        self._apply(enabled=True)
        assert "T" not in {item[0] for item in tm.MENU_ITEMS}
        assert "T" not in tm.FEATURE_GATED_ITEMS


class TestMenuGroups(unittest.TestCase):
    """主菜单任务分组（生成 / 数据与查看 / 配置 / 诊断）：结构关系，不写死条数。"""

    def test_groups_cover_every_item_exactly_once_except_exit(self) -> None:
        """分组必须恰好覆盖全部非退出项一次；退出项列在分组之外。"""
        from src.python.tui.tui_menu import MENU_GROUPS

        keys = {item[0] for item in MENU_ITEMS}
        grouped = [key for _title, group_keys in MENU_GROUPS for key in group_keys]
        assert len(grouped) == len(set(grouped)), f"分组内键重复: {grouped}"
        assert set(grouped) <= keys, f"分组含未知键: {set(grouped) - keys}"
        assert keys - set(grouped) == {"X"}, f"未入组项应仅退出项，实测: {keys - set(grouped)}"

    def test_group_titles_are_task_domains(self) -> None:
        """组标题按任务域（用户视角）而非模块分层（工程视角）。"""
        from src.python.tui.tui_menu import MENU_GROUPS

        titles = [title for title, _keys in MENU_GROUPS]
        assert len(titles) == len(set(titles)), f"组标题重复: {titles}"
        for expected in ("生成报告", "数据与查看", "配置", "诊断与排查"):
            assert expected in titles, f"缺少任务分组「{expected}」: {titles}"

    def test_generation_group_holds_all_report_actions(self) -> None:
        """生成组收纳全部报告产出动线（含调仓模拟与报告追问），用户不必在菜单里翻找。

        判据是「产生或消费报告产物的动作」同组：`Q` 消费已生成报告且消耗 LLM，
        与零成本的缓存维护（`1`/`2`/`3`）不同族，故不留在「数据与查看」。
        """
        from src.python.tui.tui_menu import MENU_GROUPS

        generation = next(keys for title, keys in MENU_GROUPS if title == "生成报告")
        assert {"E", "B", "L", "W", "Q"} <= set(generation)


class TestMatchMenuItems(unittest.TestCase):
    """`/` 关键词筛选：标签子串 + 按键等值（大小写不敏感）。"""

    def test_empty_keyword_returns_every_index(self) -> None:
        from src.python.tui.tui_menu import match_menu_items

        assert match_menu_items("") == list(range(len(MENU_ITEMS)))
        assert match_menu_items("   ") == list(range(len(MENU_ITEMS)))

    def test_label_substring_matches(self) -> None:
        from src.python.tui.tui_menu import match_menu_items

        keys = [MENU_ITEMS[i][0] for i in match_menu_items("缓存")]
        assert set(keys) == {"1", "2", "3"}, f"「缓存」应命中三个缓存项: {keys}"

    def test_key_equality_is_case_insensitive(self) -> None:
        from src.python.tui.tui_menu import match_menu_items

        # 按键精确命中优先：单键名筛选不得被标签里的拉丁字母（Excel/HTML）带偏
        assert [MENU_ITEMS[i][0] for i in match_menu_items("s")] == ["S"]
        assert [MENU_ITEMS[i][0] for i in match_menu_items("G")] == ["G"]
        assert [MENU_ITEMS[i][0] for i in match_menu_items("d")] == ["D"]
        assert [MENU_ITEMS[i][0] for i in match_menu_items("1")] == ["1"]

    def test_no_match_returns_empty(self) -> None:
        from src.python.tui.tui_menu import match_menu_items

        assert match_menu_items("不存在的关键词") == []

    def test_next_matching_wraps_both_directions(self) -> None:
        from src.python.tui.tui_menu import match_menu_items, next_matching

        matches = match_menu_items("缓存")
        assert next_matching(matches, matches[-1], 1) == matches[0], "向下越界须回绕到首个匹配"
        assert next_matching(matches, matches[0], -1) == matches[-1], "向上越界须回绕到末个匹配"
        assert next_matching([], 0, 1) is None, "无匹配项时不得返回索引"


class TestRenderMenuGroups(unittest.TestCase):
    """渲染：分组标题 + 筛选态只显示命中项（含筛选状态行）。"""

    def _render(self, filter_text: str = "") -> str:
        from src.python.tui.tui_menu import render_menu

        buf = StringIO()
        with patch("sys.stdout", buf):
            render_menu(0, filter_text)
        return buf.getvalue()

    def test_group_headers_rendered_in_menu(self) -> None:
        from src.python.tui.tui_menu import MENU_GROUPS

        out = self._render()
        positions = [out.find(f"── {title} ──") for title, _keys in MENU_GROUPS]
        assert all(p >= 0 for p in positions), f"分组标题未全部上屏: {out[:400]}"
        assert positions == sorted(positions), "分组标题须按 MENU_GROUPS 次序出现"
        for key, _label, _cb, _exit in MENU_ITEMS:
            assert f"[{key}]" in out, f"菜单项 [{key}] 未渲染"

    def test_filter_keeps_only_matching_items(self) -> None:
        out = self._render("缓存")
        assert "筛选「缓存」：3 项" in out, f"缺少筛选状态行: {out[:300]}"
        assert "[1]" in out and "[2]" in out and "[3]" in out
        assert "[L]" not in out, "未命中项不得出现在筛选结果中"
        assert "── 配置 ──" not in out, "无命中项的分组标题不得出现"

    def test_empty_filter_result_keeps_frame(self) -> None:
        out = self._render("不存在的关键词")
        assert "筛选「不存在的关键词」：0 项" in out
        assert "[X]" not in out and "[E]" not in out


if __name__ == "__main__":
    unittest.main()
