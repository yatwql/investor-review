"""llm_providers.json 多链线路优先级写入（共享编辑层 llm_providers.priority / reorder）测试。

覆盖：置换校验（缺名/重名/未知名拒绝）/ priority 归一化 10,20,30 且其余字段原样保留 /
注释保留写回 / 写前 .bak 备份 / 文件缺失回退内置模板并物化 / get_llm_providers 访问器回退 /
重写后沿用文件原有缩进（2 空格风格不被拉成 4 空格）/ 头注释「主：/备：」标注写盘时中性化。
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import pytest

from src.python.config._comments import _strip_json_comments
from src.python.config.edit_ops import ConfigEditError, apply_config_edit

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]


_CONFIG_WITH_COMMENTS = """// llm_providers 多链配置：优先级数字越小越优先
{
  "strategy": "priority", // 降级策略
  "providers": [
    {
      "name": "main",
      "provider": "claude",
      "credentials_ref": "env:CRED",
      "model": "m1",
      "priority": 10,
      "weight": 6
    },
    {
      "name": "aux",
      "provider": "openai",
      "credentials_ref": "env:CRED2",
      "model": "m2",
      "priority": 20,
      "weight": 4
    },
    {
      "name": "last",
      "provider": "gemini",
      "credentials_ref": "env:CRED3",
      "model": "m3",
      "priority": 30
    }
  ]
}
"""


class _ProviderFileMixin:
    """临时 providers 文件 + edit_ops 目标路径重定向。"""

    def _setup_provider_file(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.providers_path = os.path.join(self.tmp, "llm_providers.json")
        with open(self.providers_path, "w", encoding="utf-8") as f:
            f.write(_CONFIG_WITH_COMMENTS)
        self._path_patch = patch(
            "src.python.config._llm_providers._get_llm_providers_path", return_value=self.providers_path
        )
        self._path_patch.start()

    def _teardown_provider_file(self) -> None:
        self._path_patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _read_config(self) -> dict:
        with open(self.providers_path, encoding="utf-8") as f:
            return json.loads(_strip_json_comments(f.read()))

    @staticmethod
    def _reorder(order: list[str]) -> dict:
        return apply_config_edit({"key": "llm_providers.priority", "action": "reorder", "order": order})


class TestLlmProviderReorder(_ProviderFileMixin, unittest.TestCase):
    """reorder 动作：置换校验 + priority 归一化 + 注释/字段保留。"""

    def setUp(self) -> None:
        self._setup_provider_file()

    def tearDown(self) -> None:
        self._teardown_provider_file()

    def test_reorder_normalizes_priorities_and_preserves_fields(self) -> None:
        """逆序重排：priority 归一化 10/20/30，其余字段（weight/model/credentials_ref）原样保留。"""
        result = self._reorder(["last", "aux", "main"])
        self.assertEqual(result["value"]["order"], ["last", "aux", "main"])
        by_name = {p["name"]: p for p in self._read_config()["providers"]}
        self.assertEqual(by_name["last"]["priority"], 10)
        self.assertEqual(by_name["aux"]["priority"], 20)
        self.assertEqual(by_name["main"]["priority"], 30)
        self.assertEqual(by_name["main"]["weight"], 6)
        self.assertEqual(by_name["main"]["model"], "m1")
        self.assertEqual(by_name["main"]["credentials_ref"], "env:CRED")

    def test_reorder_preserves_comments(self) -> None:
        """注释保留：重排写回后文件仍含原始行注释（_update_json_raw_text 文本级替换）。"""
        self._reorder(["aux", "main", "last"])
        with open(self.providers_path, encoding="utf-8") as f:
            raw = f.read()
        self.assertIn("// llm_providers 多链配置", raw)
        self.assertIn("// 降级策略", raw)

    def test_reorder_creates_backup_before_write(self) -> None:
        """写前 .bak 备份：内容为重排前的原配置。"""
        self._reorder(["aux", "main", "last"])
        bak = self.providers_path + ".bak"
        self.assertTrue(os.path.exists(bak))
        with open(bak, encoding="utf-8") as f:
            self.assertIn('"name": "main"', f.read())

    def test_reorder_rejects_missing_name(self) -> None:
        """order 缺名（非置换）→ ConfigEditError，原文件不动。"""
        with pytest.raises(ConfigEditError):
            self._reorder(["main", "aux"])
        self.assertIn('"priority": 10', open(self.providers_path, encoding="utf-8").read())

    def test_reorder_rejects_unknown_name(self) -> None:
        """order 含未知名（多出一条）→ ConfigEditError。"""
        with pytest.raises(ConfigEditError):
            self._reorder(["main", "aux", "last", "ghost"])

    def test_reorder_rejects_duplicate_name(self) -> None:
        """order 含重复名 → ConfigEditError。"""
        with pytest.raises(ConfigEditError):
            self._reorder(["main", "main", "last"])

    def test_reorder_rejects_bad_action_and_format(self) -> None:
        """动作不在白名单 / order 非列表非字符串 → ConfigEditError。"""
        with pytest.raises(ConfigEditError):
            apply_config_edit({"key": "llm_providers.priority", "action": "swap", "order": ["a", "b"]})
        with pytest.raises(ConfigEditError):
            self._reorder(["main", 42])

    def test_reorder_missing_file_falls_back_to_default_template(self) -> None:
        """文件缺失：基于内置模板重排并物化文件（写入即生成默认配置）。"""
        from src.python.config._llm_providers_defaults import _DEFAULT_LLM_PROVIDERS

        missing = os.path.join(self.tmp, "absent", "llm_providers.json")
        with patch("src.python.config._llm_providers._get_llm_providers_path", return_value=missing):
            default_names = [p["name"] for p in _DEFAULT_LLM_PROVIDERS["providers"]]
            reversed_names = list(reversed(default_names))
            result = self._reorder(reversed_names)
        self.assertEqual(result["value"]["order"], reversed_names)
        self.assertTrue(os.path.exists(missing))
        by_name = {p["name"]: p for p in self._read_missing(missing)["providers"]}
        for idx, name in enumerate(reversed_names, 1):
            self.assertEqual(by_name[name]["priority"], idx * 10)

    @staticmethod
    def _read_missing(path: str) -> dict:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_reorder_keeps_file_indent_style(self) -> None:
        """重写数组后沿用原有 2 空格缩进（条目 4 / 字段 6），不拉成 4 空格风格。"""
        self._reorder(["last", "aux", "main"])
        lines = open(self.providers_path, encoding="utf-8").read().splitlines()
        field_line = next(line for line in lines if '"name": "last"' in line)
        entry_line = next(line for line in lines if line.strip() == "{" and line.startswith(" "))
        self.assertEqual(len(entry_line) - len(entry_line.lstrip()), 4)
        self.assertEqual(len(field_line) - len(field_line.lstrip()), 6)

    def test_reorder_neutralizes_primary_backup_labels(self) -> None:
        """头注释「主：/备：」在写盘时中性化为「线路：」，其余注释与描述原样保留。"""
        with open(self.providers_path, "w", encoding="utf-8") as f:
            f.write(
                _CONFIG_WITH_COMMENTS.replace(
                    "// llm_providers 多链配置：优先级数字越小越优先",
                    "// llm_providers 多链配置：优先级数字越小越优先\n"
                    "// 主：main（按量付费端点）\n"
                    "// 备：aux（订阅中转）",
                )
            )
        self._reorder(["aux", "main", "last"])
        raw = open(self.providers_path, encoding="utf-8").read()
        self.assertNotIn("// 主：", raw)
        self.assertNotIn("// 备：", raw)
        self.assertIn("// 线路：main（按量付费端点）", raw)
        self.assertIn("// 线路：aux（订阅中转）", raw)
        self.assertIn("// 降级策略", raw)  # 无关注释不动

    def test_reorder_label_neutralization_is_idempotent(self) -> None:
        """重复写盘不叠加改写（第二次仍只剩「线路：」，无二次替换痕迹）。"""
        with open(self.providers_path, "w", encoding="utf-8") as f:
            f.write(
                _CONFIG_WITH_COMMENTS.replace(
                    "// llm_providers 多链配置：优先级数字越小越优先",
                    "// 主：main（端点 A）",
                )
            )
        self._reorder(["aux", "main", "last"])
        self._reorder(["main", "aux", "last"])
        raw = open(self.providers_path, encoding="utf-8").read()
        self.assertIn("// 线路：main（端点 A）", raw)
        self.assertNotIn("线路：线路：", raw)

    def test_reorder_fixes_array_order_misstatement(self) -> None:
        """注释把数组物理顺序误当链序时，写盘一并归正为 priority 升序口径。"""
        with open(self.providers_path, "w", encoding="utf-8") as f:
            f.write(
                _CONFIG_WITH_COMMENTS.replace(
                    "// llm_providers 多链配置：优先级数字越小越优先",
                    "// LLM Provider 多链配置（顺序即 priority 升序）",
                )
            )
        self._reorder(["last", "aux", "main"])
        raw = open(self.providers_path, encoding="utf-8").read()
        self.assertNotIn("顺序即 priority 升序", raw)
        self.assertIn("链序按 priority 升序，数值小者靠前，与数组项顺序无关", raw)


class TestOrderProvidersByChain:
    """展示/面板共用的唯一排序口径：priority 升序，同值保持数组原序。"""

    def test_sorts_by_priority_value(self) -> None:
        from src.python.config._llm_providers import order_providers_by_chain

        entries = [
            {"name": "a", "priority": 30},
            {"name": "b", "priority": 10},
            {"name": "c", "priority": 20},
        ]
        assert [p["name"] for p in order_providers_by_chain(entries)] == ["b", "c", "a"]

    def test_keeps_array_order_on_tie(self) -> None:
        from src.python.config._llm_providers import order_providers_by_chain

        entries = [{"name": "x", "priority": 10}, {"name": "y", "priority": 10}]
        assert [p["name"] for p in order_providers_by_chain(entries)] == ["x", "y"]

    def test_does_not_mutate_input(self) -> None:
        from src.python.config._llm_providers import order_providers_by_chain

        entries = [{"name": "a", "priority": 20}, {"name": "b", "priority": 10}]
        order_providers_by_chain(entries)
        assert [p["name"] for p in entries] == ["a", "b"]


class TestLlmProviderTemplateComment:
    """默认模板头注释只写稳定事实（链序由 priority 决定），不含会失效的主/备标注。"""

    def test_template_has_neutral_chain_guidance(self) -> None:
        from src.python.config._llm_providers_defaults import _get_default_llm_providers_template

        template = _get_default_llm_providers_template()
        assert "链序真值" in template
        assert "priority 升序" in template

    def test_template_has_no_primary_backup_labels(self) -> None:
        from src.python.config._llm_providers_defaults import _get_default_llm_providers_template

        template = _get_default_llm_providers_template()
        assert "// 主：" not in template
        assert "// 备：" not in template


class TestGetLlmProvidersAccessor(_ProviderFileMixin, unittest.TestCase):
    """get_llm_providers 公开只读访问器的回退行为。"""

    def setUp(self) -> None:
        self._setup_provider_file()

    def tearDown(self) -> None:
        self._teardown_provider_file()

    def test_reads_ordered_providers_from_file(self) -> None:
        """正常读取：返回文件配置（providers 原始数组由调用方排序展示）。"""
        from src.python.config import get_llm_providers

        names = [p["name"] for p in get_llm_providers()["providers"]]
        self.assertEqual(names, ["main", "aux", "last"])

    def test_missing_file_returns_default_template_copy(self) -> None:
        """文件缺失 → 内置默认模板深拷贝（调用方修改不污染默认值）。"""
        from src.python.config import get_llm_providers

        missing = os.path.join(self.tmp, "absent", "llm_providers.json")
        with patch("src.python.config._llm_providers._get_llm_providers_path", return_value=missing):
            cfg = get_llm_providers()
            self.assertTrue(cfg.get("providers"))
            first = [p["name"] for p in cfg["providers"]]
            cfg["providers"].append({"name": "polluted"})
            self.assertEqual([p["name"] for p in get_llm_providers()["providers"]], first)

    def test_invalid_json_returns_empty_dict(self) -> None:
        """JSON 损坏 → {}（调用方按空处理，不抛异常）。"""
        from src.python.config import get_llm_providers

        with open(self.providers_path, "w", encoding="utf-8") as f:
            f.write("{broken")
        self.assertEqual(get_llm_providers(), {})
