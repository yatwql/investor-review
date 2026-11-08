"""Web 配置面契约测试（`domains` 编排契约的机检载体）。

契约（见 `docs/plan/config-web-design.md` §3.3/§3.4/§3.4.1）：

  1. **块 ↔ 渲染器**：`domains[].blocks` 出现的每个块 id 在 `main.js` 都有渲染器，
     且 `main.js` 的渲染器表不列任何 `domains` 之外的块（双向相等，防漏接与僵尸渲染器）；
  2. **文案零硬编码**：`main.js` 不含中文标签字典（`CONFIG_LABELS`/`ANON_LABELS`），
     标签/说明/默认值全部由服务端 `labels`/`descriptions`/`defaults` 下发；
  3. **覆盖完备**：白名单里每个可编辑键都有 `label` 与 `description`，布尔与数值键有 `defaults`；
  4. **域覆盖**：`domains` 的五域顺序与 `DOMAIN_ORDER` 一致，块清单无重复、无空域；
  5. **XSS 与无障碍**：`main.js` 不含 `innerHTML` 赋值，勾选/输入控件均带 `label`；
  6. **日志面可写**：`logging.*` 六键在共享白名单内且写入落到 `logger.json`。

隔离：conftest 的 `_isolate_sensitive_paths` 已把 config/llm/features 重定向到临时目录；
本文件另把 `logger.json` 与计价参考路径指向 `tmp_path`，不触碰真实 `data/config/`。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.python.web import config_edit

pytestmark = [pytest.mark.unit, pytest.mark.unit_web]

_MAIN_JS = Path(__file__).resolve().parents[3] / "static" / "web" / "main.js"


@pytest.fixture(scope="module")
def surface() -> dict:
    return config_edit.get_config_edit_surface()


@pytest.fixture(scope="module")
def main_js() -> str:
    return _MAIN_JS.read_text(encoding="utf-8")


class TestBlockRendererContract:
    def test_every_block_has_renderer(self, surface, main_js):
        """`domains` 里的块 id 在 main.js 都有落点（`BLOCK_RENDERERS` 表项或 `features.` 前缀分支）。"""
        blocks = [block for domain in surface["domains"] for block in domain["blocks"]]
        assert blocks, "domains 不得为空"
        table = set(re.findall(r"^\s{4}([a-z_]+): function \(surface\)", main_js, re.M))
        for block in blocks:
            if block.startswith("features."):
                assert "features." in main_js and "renderFeatureBlock" in main_js, (
                    f"缺少 features 前缀渲染分支：{block}"
                )
            else:
                assert block in table, f"块 {block} 在 main.js 无渲染器"

    def test_no_orphan_renderers(self, surface, main_js):
        """反向：渲染器表不列 `domains` 之外的块（防僵尸渲染器/漏登记到 domains）。"""
        blocks = {block for domain in surface["domains"] for block in domain["blocks"]}
        table = set(re.findall(r"^\s{4}([a-z_]+): function \(surface\)", main_js, re.M))
        assert table <= blocks, f"渲染器表含未登记块：{sorted(table - blocks)}"

    def test_domains_follow_domain_order(self, surface):
        from src.python.config.features import DOMAIN_ORDER

        assert [domain["key"] for domain in surface["domains"]] == list(DOMAIN_ORDER)

    def test_blocks_are_unique_and_domains_nonempty(self, surface):
        for domain in surface["domains"]:
            assert domain["blocks"], f"域 {domain['key']} 无块（空域不应出现）"
            assert len(domain["blocks"]) == len(set(domain["blocks"])), f"域 {domain['key']} 块重复"

    def test_standalone_block_derives_from_chapter_registry(self, surface):
        """独立整章块键集 = 章节注册表对应块（单一来源，不另写清单）。

        `artifact` 分块位当前无条目（What-if 交易成本对比归 `[S]` 持仓与交易组），
        故 Web 面不单列「关联产物」块；一旦注册表往该块放条目，本用例直接变红，
        提醒同步补 Web 块与前端渲染器。
        """
        from src.python.config.chapter_registry import BLOCK_ARTIFACT, BLOCK_STANDALONE, chapters_in_block

        assert set(surface["standalone_chapters"]) == {e.key for e in chapters_in_block(BLOCK_STANDALONE)}
        assert not chapters_in_block(BLOCK_ARTIFACT), "artifact 块出现条目时须同步补 Web 块与渲染器"
        assert "standalone_related" not in surface

    def test_feature_blocks_cover_panel_visible_switches(self, surface):
        """功能开关块与 TUI `[S]` 面板同源：组集、组内上屏项一致，隐藏项不得下发。

        回归：Web 曾按 `switches_in_group` 全量下发，会把不上屏的默认常开机制项
        （`decision_basis` / `module_quality_gate`）与自动项（`candidate_compare`）
        推到面板上，与 TUI 面板口径分叉。
        """
        from src.python.config.features import PANEL_GROUPS, panel_switches

        groups = surface["features"]["groups"]
        assert [group["key"] for group in groups] == list(PANEL_GROUPS["[S]"])
        emitted = [flag for group in groups for flag in group["switches"]]
        assert emitted == [flag for flag, _d in panel_switches("[S]")], "顺序与集合均须与 [S] 面板一致"
        assert "whatif_trade_cost" in emitted, "归入持仓与交易组的 What-if 必须下发"
        assert not ({"decision_basis", "module_quality_gate", "candidate_compare"} & set(emitted))

    def test_every_feature_block_is_referenced_by_a_domain(self, surface):
        """不留下无人引用的开关分组（某个组没进任何域 = 面板上永远看不到它）。"""
        blocks = {block for domain in surface["domains"] for block in domain["blocks"]}
        for group in surface["features"]["groups"]:
            assert f"features.{group['key']}" in blocks, group["key"]


class TestBlockTitles:
    def test_every_block_has_chinese_title(self, surface):
        """每个块 id 都有随面下发的中文标题（`features.*` 用组自身标题）。

        回归：块标题曾回退到块 id 本身，面板上直接显示 `sections` / `llm` 这类内部标识。
        """
        titles = surface["block_titles"]
        for domain in surface["domains"]:
            for block in domain["blocks"]:
                if block.startswith("features."):
                    assert block.split(".", 1)[1] in {group["key"] for group in surface["features"]["groups"]}, block
                    continue
                assert block in titles, f"块 {block} 缺中文标题"
                assert any("\u4e00" <= ch <= "\u9fff" for ch in titles[block]), (block, titles[block])

    def test_titles_are_not_block_ids(self, surface):
        """标题不得等于块 id（前端显示的应是中文名，而不是内部标识）。"""
        for block, title in surface["block_titles"].items():
            assert title != block, block


class TestNoChineseTablesInFrontend:
    def test_no_label_tables(self, main_js):
        """前端不持有中文标签字典（标签/说明/默认值一律服务端下发）。"""
        assert "CONFIG_LABELS" not in main_js
        assert "ANON_LABELS" not in main_js

    def test_no_inner_html_assignment(self, main_js):
        """XSS 纪律：不得出现 `innerHTML =` 赋值（注释里提到该词不算）。"""
        assert not re.search(r"innerHTML\s*=", main_js)

    def test_controls_have_labels(self, main_js):
        """勾选/输入控件均通过 `<label>` 包裹或 `htmlFor` 关联。"""
        assert "config-input-" in main_js and "htmlFor" in main_js
        assert "cb.type = 'checkbox'" in main_js  # 勾选框由 label 元素包裹
        assert "radio.type = 'radio'" in main_js


class TestMetadataCoverage:
    def test_every_editable_key_has_label_and_description(self, surface):
        """白名单每个可编辑键都有 label 与 description（面板不出现裸键名）。"""
        editable = [key for key, entry in config_edit.config_edit_whitelist.items() if entry["kind"] != "action"]
        missing_label = [key for key in editable if key not in surface["labels"]]
        missing_desc = [key for key in editable if key not in surface["descriptions"]]
        assert not missing_label, f"缺 label：{missing_label}"
        assert not missing_desc, f"缺 description：{missing_desc}"

    def test_bool_and_number_keys_have_defaults(self, surface):
        """布尔/数值类可编辑键必须下发出厂默认（前端据此标「已改」，不自行推算）。"""
        editable = [
            key
            for key, entry in config_edit.config_edit_whitelist.items()
            if entry["kind"] in {"bool", "int", "float", "enum"}
        ]
        missing = [key for key in editable if key not in surface["defaults"]]
        assert not missing, f"缺 default：{missing}"

    def test_features_metadata_matches_registry(self, surface):
        """功能开关的 label/description/default 与注册表逐项一致（不另写副本）。"""
        from src.python.config.features import feature_switch_registry

        for flag, definition in feature_switch_registry.items():
            assert surface["labels"][flag] == definition.label
            assert surface["descriptions"][flag] == definition.desc
            assert surface["defaults"][flag] == definition.default

    def test_anonymization_labels_cover_options(self, surface):
        anon = surface["anonymization"]
        assert set(anon["labels"]) == set(anon["options"])


class TestLoggingSurface:
    def test_logging_items_cover_whitelist_keys(self, surface):
        keys = {item["key"] for item in surface["logging"]["items"]}
        expected = {key for key in config_edit.config_edit_whitelist if key.startswith("logging.")}
        assert keys == expected

    def test_restart_keys_are_subset_of_items(self, surface):
        keys = {item["key"] for item in surface["logging"]["items"]}
        assert set(surface["logging"]["restart_keys"]) <= keys
        assert "logging.viewer_level" not in surface["logging"]["restart_keys"], "查看器项应即时生效"

    def test_logging_write_lands_in_logger_json(self, tmp_path, monkeypatch):
        """面板写 `logging.level` 落到 logger.json（三渠道同一写入原语）。"""
        import src.python.config._logging as logging_config
        from src.python.config.edit_ops import apply_config_edit

        monkeypatch.setattr(logging_config, "LOGGER_CONFIG_PATH", str(tmp_path / "logger.json"))
        apply_config_edit({"key": "logging.level", "value": "DEBUG"})
        assert logging_config.read_logger_config()["level"] == "DEBUG"

    def test_logging_invalid_value_rejected(self, tmp_path, monkeypatch):
        """非法枚举值被共享层拒绝，文件保持原值（不落盘）。"""
        import src.python.config._logging as logging_config
        from src.python.config.edit_ops import ConfigEditError, apply_config_edit

        monkeypatch.setattr(logging_config, "LOGGER_CONFIG_PATH", str(tmp_path / "logger.json"))
        apply_config_edit({"key": "logging.level", "value": "INFO"})
        with pytest.raises(ConfigEditError):
            apply_config_edit({"key": "logging.level", "value": "NOISY"})
        assert logging_config.read_logger_config()["level"] == "INFO"


class TestReferenceSurface:
    def test_reference_is_readonly_info(self, surface):
        assert surface["reference"]["pricing_path"].endswith("llm_pricing_ref.json")
        assert "reference" not in config_edit.config_edit_whitelist, "参考面只读，不进编辑白名单"
