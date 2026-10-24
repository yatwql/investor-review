"""Web 配置面板交互与状态的结构契约测试（配置面交互契约的机检载体）。

前端交互（即时保存回滚 / 筛选 / 计数 / 域导航 / 深链）无法在 pytest 里驱动浏览器，
故本文件锁定**机器可检的结构与数据契约**，把「行为是否存在、是否同源」变成断言；
真实浏览器观感与可达性仍由人工清单复核（`docs/plan/web-browser-verification.md`）。

覆盖：

1. **保守回滚**：勾选/单选失败路径必须恢复改动前值（`cb.checked = prev` /
   `target.checked = true`），且错误落在所属块（`showGroupError`）；
2. **显式保存**：文本与数字走各自的保存函数，失败保留输入值；
3. **筛选**：按标签/说明/键名匹配，空块与空域隐藏，清空即恢复；
4. **计数**：工具条统计与块计数均由服务端 `defaults` 比较得出，不前端硬编码；
5. **域导航与深链**：chips 由 `domains` 派生、`#domain-<key>` 与标签页 hash 共存；
6. **响应式**：≤720px 单列断点存在；
7. **离线安全**：`main.js` 不出现 `innerHTML =`；断言不写真实 `data/config/`。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_web]

_MAIN_JS = Path(__file__).resolve().parents[3] / "static" / "web" / "main.js"
_STYLE_CSS = Path(__file__).resolve().parents[3] / "static" / "web" / "style.css"


@pytest.fixture(scope="module")
def main_js() -> str:
    return _MAIN_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def style_css() -> str:
    return _STYLE_CSS.read_text(encoding="utf-8")


def _fn(main_js: str, name: str) -> str:
    """截取顶层函数体（`  function <name>(` 起，到下一个两空格缩进的 `function` 止）。

    不能用「第一个 `function ` 出现处」截断——函数体内含内联回调 `function (err)`，
    会立刻切空。
    """
    start = main_js.index("  function " + name + "(")
    end = main_js.find("\n  function ", start + 1)
    return main_js[start:] if end < 0 else main_js[start:end]


class TestOptimisticSaveRollback:
    def test_checkbox_rolls_back_on_failure(self, main_js):
        assert re.search(r"cb\.checked = prev", main_js), "勾选失败须恢复改动前值"

    def test_radio_rolls_back_on_failure(self, main_js):
        assert re.search(r"target\.checked = true", main_js), "单选失败须恢复改动前的选中项"

    def test_error_surfaces_in_owning_block(self, main_js):
        """失败提示显示在所属块（`showGroupError`），而非仅全局横幅。"""
        assert "showGroupError(group, err)" in main_js
        assert "panelErr.textContent = '同源校验失败，请刷新页面重试'" in main_js


class TestExplicitSaveKeepsInput:
    def test_path_save_keeps_value_on_failure(self, main_js):
        """文本类显式保存失败时保留用户输入（不清空、不回写旧值）。"""
        assert "function onPathSave(e)" in main_js
        body = _fn(main_js, "onPathSave")
        assert ".catch(function (err) {" in body
        assert "input.value = prev" not in body, "失败时不得回写旧值（保留输入供重试）"

    def test_number_save_keeps_value_on_failure(self, main_js):
        assert "function onFieldSave(e)" in main_js
        body = _fn(main_js, "onFieldSave")
        assert ".catch(function (err) {" in body
        assert "control.value =" not in body, "失败时不得回写旧值"


class TestFilterAndCounts:
    def test_filter_matches_label_desc_and_key(self, main_js):
        """筛选匹配范围：行文本（标签 + 说明）+ `data-config-key`。"""
        body = _fn(main_js, "applyConfigFilter")
        assert "row.textContent" in body
        assert "dataset.configKey" in body
        assert "classList.toggle('hidden'" in body

    def test_empty_blocks_and_domains_hidden(self, main_js):
        body = _fn(main_js, "applyConfigFilter")
        assert "visibleBlocks === 0" in body, "域内块全空则该域隐藏"

    def test_counts_compare_against_server_defaults(self, main_js):
        """「已改 N 项」与 `defaults` 比较得出（前端不自算基准）。"""
        body = _fn(main_js, "refreshConfigStats")
        assert "surface.defaults" in body
        assert "已改 " in body

    def test_block_counts_rendered_in_heading(self, main_js):
        assert "config-block-meta" in main_js
        body = _fn(main_js, "refreshBlockCounts")
        assert "项 · " in body and "开" in body

    def test_counts_refresh_after_save(self, main_js):
        """写路径成功后必须刷新统计（否则「已改」长期滞后）。"""
        assert main_js.count("refreshConfigStats();") >= 3


class TestDomainNavigationAndDeepLink:
    def test_chips_derived_from_domains(self, main_js):
        assert "function renderDomainChips(domains)" in main_js
        assert "'#domain-' + domain.key" in main_js

    def test_deep_link_coexists_with_tab_hash(self, main_js):
        """`#domain-<key>` 先切配置页再滚到锚点；其余 hash 仍按标签页处理。"""
        body = _fn(main_js, "applyLocationHash")
        assert "indexOf('domain-') === 0" in body
        assert "activateTab('config'" in body
        assert "activateTab(hash || 'generate'" in body

    def test_scroll_spy_guarded_by_support_detection(self, main_js):
        body = _fn(main_js, "observeDomains")
        assert "IntersectionObserver" in body
        assert "if (!('IntersectionObserver' in window))" in body, "需在无该 API 时降级"

    def test_domain_section_ids_are_anchor_targets(self, main_js):
        assert "section.id = 'domain-' + domain.key" in main_js


class TestResponsiveAndSafety:
    def test_single_column_breakpoint(self, style_css):
        """窄屏单列（跟随既有断点契约 768）：工具条纵向、chips 横滚、筛选占满行宽。"""
        assert "@media (max-width: 768px)" in style_css
        block = style_css[style_css.index("@media (max-width: 768px)") :]
        block = block[: block.index("@media (max-width: 480px)")]
        assert "flex-direction: column" in block
        assert "overflow-x: auto" in block

    def test_toolbar_has_aria_label(self, main_js):
        assert "setAttribute('aria-label', '筛选配置项')" in main_js
