"""报告章节注册表结构测试：四块划分、编号派生、与来源注册表双向一致。

为什么需要：``[C]`` 面板的 16 项 / 两个子项 / 四块边界全部由
``config.chapter_registry`` 派生——注册表一旦与 LLM 模块注册表 / 功能开关注册表
脱钩，面板会静默少项或错位。本文件锁定三件事：

  1. 结构：键名唯一、块内连续、块序固定、编号 1..N 连续（不写死条数）；
  2. 同源：LLM 块 = 模块注册表键序，功能开关块 + 子项 = 注册表对应分组全集；
  3. 可写：每个章节的写入键都在共享编辑层白名单内（否则面板切换会报未知键）。
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]

_FEATURE_BLOCKS = ("standalone", "chapter_options")


class TestChapterRegistryStructure:
    def test_keys_are_unique(self):
        from src.python.config.chapter_registry import chapter_registry

        keys = [entry.key for entry in chapter_registry]
        assert len(keys) == len(set(keys))

    def test_numbers_are_contiguous_from_one(self):
        """编号 = 表序派生：1..N 连续（增删章节后自动重排，不写死数字）。"""
        from src.python.config.chapter_registry import chapter_numbers, chapter_registry

        numbered = chapter_numbers()
        assert [n for n, _e in numbered] == list(range(1, len(chapter_registry) + 1))
        assert [e.key for _n, e in numbered] == [e.key for e in chapter_registry]

    def test_four_blocks_partition_registry_in_declared_order(self):
        """四块不重叠、并集为全集，且各块在表中是连续区间（边界正确）。"""
        from src.python.config.chapter_registry import (
            BLOCK_ORDER,
            chapter_registry,
            chapters_in_block,
        )

        blocks = [[e.key for e in chapters_in_block(block)] for block in BLOCK_ORDER]
        assert [key for block in blocks for key in block] == [e.key for e in chapter_registry]
        assert all(blocks), "四块都应有章节（结构断言）"
        starts = [chapter_registry.index(chapters_in_block(block)[0]) for block in BLOCK_ORDER]
        assert starts == sorted(starts), "块序必须与 BLOCK_ORDER 一致"

    def test_every_block_has_label(self):
        from src.python.config.chapter_registry import BLOCK_LABELS, BLOCK_ORDER

        assert set(BLOCK_LABELS) == set(BLOCK_ORDER)

    def test_source_files_cover_all_sources(self):
        from src.python.config.chapter_registry import SOURCE_FILES, chapter_registry

        assert {entry.source for entry in chapter_registry} <= set(SOURCE_FILES)


class TestChapterRegistrySources:
    def test_llm_block_matches_module_registry_order(self):
        """LLM 章节块 = 模块注册表全集与顺序（单一来源，面板不另写清单）。"""
        from src.python.config.chapter_registry import BLOCK_LLM, chapters_in_block
        from src.python.core.registry import get_llm_module_names

        keys = [entry.key for entry in chapters_in_block(BLOCK_LLM)]
        assert keys == list(get_llm_module_names())

    def test_feature_backed_chapters_match_feature_groups(self):
        """功能开关承载的章节 + 子项 = 注册表 standalone / chapter_options 两组全集。"""
        from src.python.config.chapter_registry import chapter_registry
        from src.python.config.features import switches_in_group

        expected = {flag for group in _FEATURE_BLOCKS for flag, _d in switches_in_group(group)}
        actual = {e.key for e in chapter_registry if e.source == "features"}
        actual |= {flag for e in chapter_registry for flag in e.sub_items}
        assert actual == expected

    def test_sub_item_numbers_derive_from_parent_number(self):
        """子项编号 = 父章节当前编号 + 子项序（``7.1`` 不写死）。"""
        from src.python.config.chapter_registry import chapter_number, chapter_registry, sub_item_numbers

        expected = {
            f"{chapter_number(entry.key)}.{offset}": flag
            for entry in chapter_registry
            for offset, flag in enumerate(entry.sub_items, 1)
        }
        assert sub_item_numbers() == expected

    def test_chapter_by_key_finds_entries_and_parents(self):
        from src.python.config.chapter_registry import chapter_by_key, chapter_registry

        for entry in chapter_registry:
            assert chapter_by_key(entry.key) is entry
            for flag in entry.sub_items:
                assert chapter_by_key(flag) is entry
        assert chapter_by_key("not_a_chapter") is None

    def test_labels_resolve_from_source_registries(self):
        """LLM / 功能开关章节的显示名取自各自注册表，注册表条目不重复写中文。"""
        from src.python.config.chapter_registry import chapter_label, chapter_registry
        from src.python.config.features import feature_switch_registry
        from src.python.core.registry import get_llm_module_names

        llm_names = get_llm_module_names()
        for entry in chapter_registry:
            label = chapter_label(entry, llm_names)
            assert label
            if entry.source == "llm_settings":
                # 显式 label 仅允许「同源 + 括注」（同一报告章拆成本体/增强两行时用）
                assert label.startswith(llm_names[entry.key])
            elif entry.source == "features":
                assert label == feature_switch_registry[entry.key].label
            else:
                assert entry.label == label

    def test_defaults_match_source_registries(self):
        from src.python.config.chapter_registry import chapter_default, chapter_registry
        from src.python.config.features import feature_switch_registry

        for entry in chapter_registry:
            if entry.source == "features":
                assert chapter_default(entry) == feature_switch_registry[entry.key].default
            if entry.source == "config":
                assert chapter_default(entry) is True


class TestChapterWritability:
    def test_every_chapter_edit_key_is_whitelisted(self):
        """面板切换走共享编辑层：每个章节（含子项）的写键必须在白名单内。"""
        from src.python.config.chapter_registry import chapter_edit_key, chapter_registry
        from src.python.config.edit_ops import config_edit_whitelist

        for entry in chapter_registry:
            assert chapter_edit_key(entry) in config_edit_whitelist, entry.key
            for flag in entry.sub_items:
                assert flag in config_edit_whitelist

    def test_storage_points_at_the_right_file(self):
        from src.python.config.chapter_registry import SOURCE_FILES, chapter_registry, chapter_storage

        for entry in chapter_registry:
            storage = chapter_storage(entry)
            assert storage.startswith(SOURCE_FILES[entry.source])
            assert entry.key in storage


class TestPanelMatchesReportChapterNames:
    """C 面板显示名须与报告产物章节名一致（同一章不得两种叫法）。"""

    def test_news_chapter_label_matches_report_chapter(self):
        from src.python.config.chapter_registry import chapter_by_key, chapter_label
        from src.python.core.report_section_registry import get_report_section_order

        report_name = next(sec["name"] for sec in get_report_section_order() if sec["key"] == "news_correlation")
        top = chapter_by_key("enable_news")
        llm = chapter_by_key("news_correlation")
        assert top is not None and llm is not None
        # 章节本体：显示名即报告产物里的章节名（改名前曾叫「市场新闻」，与产物不一致）
        assert chapter_label(top) == report_name
        # 同一报告章的 LLM 增强行：同源 + 括注，不另起别名
        llm_label = chapter_label(llm)
        assert llm_label.startswith(report_name)
        assert llm_label != report_name
