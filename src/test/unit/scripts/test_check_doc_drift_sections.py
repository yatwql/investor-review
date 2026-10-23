"""test_check_doc_drift 兄弟分片（sections）：章节-区块矩阵 / 手册菜单块与键引用 / 返回键不变式 / 可见性类型行。"""
# ruff: noqa: F811 — 夹具以参数名注入（与模块级同名导入非重定义）

from __future__ import annotations
from dataclasses import replace
from src.python.core.section_block_registry import SECTION_BLOCK_SPECS
from src.python.tui.tui_menu import MENU_ITEMS
import pytest

# 夹具按名注入（由测试签名消费），代码里无引用

from src.test.unit.scripts.test_check_doc_drift import (
    drift,  # noqa: F401
    drift_parts,  # noqa: F401
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
    pytest.mark.usefixtures("offline_external_sources"),
]


class TestBlockMatrix:
    """§4.22 章节-区块矩阵三向对账：文档行 ↔ 区块注册表 ↔ 双端实现提取。"""

    @staticmethod
    def _doc(drift) -> str:
        return drift._TECHNICAL_MD.read_text(encoding="utf-8")

    def test_current_doc_passes(self, drift):
        """真实 technical.md 矩阵与注册表/双端实现三向一致（零 finding）。"""
        assert drift.check_block_matrix(self._doc(drift)) == []

    def test_matrix_keys_match_registry_bidirectionally(self, drift):
        """矩阵 key 集合与注册表双向相等且无重复（结构关系断言，不写死条数）。"""
        rows, findings = drift.parse_block_matrix(self._doc(drift))
        assert findings == []
        assert {r["key"] for r in rows} == {sec["key"] for sec in drift._REPORT_SECTION_DEFAULT}
        assert len({r["key"] for r in rows}) == len(rows)

    def test_stale_html_count_reported(self, drift):
        """改大某章 HTML 区块数 → 与 partial 实测重算不一致。"""
        doc = self._doc(drift)
        rows, _ = drift.parse_block_matrix(doc)
        target = next(r for r in rows if r["count"].isdigit())
        lines = doc.splitlines(keepends=True)
        idx = int(target["line"]) - 1
        old = f"| `{target['key']}` | {target['count']} |"
        assert old in lines[idx]
        lines[idx] = lines[idx].replace(old, f"| `{target['key']}` | {int(target['count']) + 1} |", 1)
        findings = drift.check_block_matrix("".join(lines))
        assert any("HTML 区块数" in f for f in findings)

    def test_missing_row_reported(self, drift):
        """删掉矩阵一行 → 注册表章节缺行被报出。"""
        doc = self._doc(drift)
        rows, _ = drift.parse_block_matrix(doc)
        lines = doc.splitlines(keepends=True)
        victim = lines.pop(int(rows[0]["line"]) - 1)
        assert victim.startswith("|")
        findings = drift.check_block_matrix("".join(lines))
        assert any("缺少注册表章节" in f for f in findings)

    def test_tampered_excel_list_reported(self, drift):
        """篡改矩阵 Excel 区块清单单元格 → 与区块注册表逐列不一致被报出。"""
        doc = self._doc(drift)
        rows, _ = drift.parse_block_matrix(doc)
        target = next(r for r in rows if r["markers"] != "—")
        marker = target["markers"].split(" / ")[0]
        lines = doc.splitlines(keepends=True)
        idx = int(target["line"]) - 1
        assert marker in lines[idx]
        lines[idx] = lines[idx].replace(marker, "已改名的占位区块", 1)
        findings = drift.check_block_matrix("".join(lines))
        assert any("Excel 区块清单与区块注册表不一致" in f for f in findings)

    def test_dash_row_not_counted(self, drift):
        """「—」行不参与重算；计数行若写成「—」会被报出（双向而非单向放行）。"""
        doc = self._doc(drift)
        rows, _ = drift.parse_block_matrix(doc)
        target = next(r for r in rows if r["count"].isdigit())
        lines = doc.splitlines(keepends=True)
        idx = int(target["line"]) - 1
        old = f"| `{target['key']}` | {target['count']} |"
        lines[idx] = lines[idx].replace(old, f"| `{target['key']}` | — |", 1)
        findings = drift.check_block_matrix("".join(lines))
        assert any("HTML 区块数" in f for f in findings)

    def test_impl_html_drift_reported(self, drift, monkeypatch):
        """注册表 html 清单多出一区块 → HTML 实现提取与注册表不一致被报出。"""
        spec = SECTION_BLOCK_SPECS["holdings_detail"]
        monkeypatch.setitem(SECTION_BLOCK_SPECS, "holdings_detail", replace(spec, html=spec.html + ("幽灵区块",)))
        findings = drift.check_block_matrix(self._doc(drift))
        assert any("HTML 区块实测" in f for f in findings)

    def test_impl_excel_drift_reported(self, drift, monkeypatch):
        """注册表 excel 清单多出一区块 → Excel 实现提取与注册表不一致被报出。"""
        spec = SECTION_BLOCK_SPECS["holdings_detail"]
        monkeypatch.setitem(SECTION_BLOCK_SPECS, "holdings_detail", replace(spec, excel=spec.excel + ("幽灵区块",)))
        findings = drift.check_block_matrix(self._doc(drift))
        assert any("Excel 区块实测" in f for f in findings)

    def test_missing_block_contract_reported(self, drift, monkeypatch):
        """删掉注册表某章区块契约 → 键集双向检查报缺契约。"""
        monkeypatch.delitem(SECTION_BLOCK_SPECS, "llm_usage")
        findings = drift.check_block_matrix(self._doc(drift))
        assert any("缺区块契约" in f for f in findings)


class TestMenuBlockConsistency:
    """手册主菜单 code block ↔ tui_menu.MENU_ITEMS 一致性（doc-drift 第 18 项）。"""

    @staticmethod
    def _menu_doc(*, skip: str | None = None, relabel: tuple[str, str] | None = None, extra: str | None = None) -> str:
        """按当前 MENU_ITEMS 动态生成主菜单块（真值派生，不写死清单与条数）。"""
        lines = []
        for key, label, _cb, _is_quit in MENU_ITEMS:
            if key == skip:
                continue
            if relabel and key == relabel[0]:
                label = relabel[1]
            lines.append(f"    [{key}] {label}")
        if extra:
            lines.append(extra)
        return "```text\n" + "\n".join(lines) + "\n```\n"

    def test_consistent_block_passes(self, drift, tmp_path):
        """与真值一致的主菜单块无 finding。"""
        p = tmp_path / "how-to-use-tui-menu.md"
        assert drift.check_menu_blocks({p: self._menu_doc()}) == []

    def test_missing_key_reported(self, drift, tmp_path):
        """块内缺某个菜单键 → 报「缺少」并带真值标签。"""
        p = tmp_path / "how-to-start.md"
        findings = drift.check_menu_blocks({p: self._menu_doc(skip="Q")})
        assert any("[Q]" in f and "缺少" in f for f in findings)

    def test_unknown_key_reported(self, drift, tmp_path):
        """块内出现 MENU_ITEMS 不存在的键 → 报「未知按键」。"""
        p = tmp_path / "how-to-start.md"
        findings = drift.check_menu_blocks({p: self._menu_doc(extra="    [Z] 不存在的项")})
        assert any("[Z]" in f and "未知按键" in f for f in findings)

    def test_label_head_drift_reported(self, drift, tmp_path):
        """标签头与真值不一致 → 报漂移。"""
        p = tmp_path / "how-to-use-tui-menu.md"
        findings = drift.check_menu_blocks({p: self._menu_doc(relabel=("E", "生成基础版报告（仅 Excel）"))})
        assert any("[E]" in f and "标签头" in f for f in findings)

    def test_parenthetical_clarification_allowed(self, drift, tmp_path):
        """括号内补充手册说明（头一致）不误报。"""
        p = tmp_path / "how-to-use-tui-menu.md"
        findings = drift.check_menu_blocks(
            {p: self._menu_doc(relabel=("4", "缓存管理（统计与清理）（二级：先统计后清理）"))}
        )
        assert findings == []

    def test_multicolumn_and_cursor_prefix_parsed(self, drift):
        """两列排版与 `> ` 光标前缀均能解析出完整键集。"""
        items = list(MENU_ITEMS)
        half = (len(items) + 1) // 2
        left = [f"    [{k}] {lb}" for k, lb, _cb, _q in items[:half]]
        left[0] = "  > " + left[0][4:]
        right = [f"    [{k}] {lb}" for k, lb, _cb, _q in items[half:]]
        rows = [left[i] + ("        " + right[i] if i < len(right) else "") for i in range(half)]
        parsed = drift.parse_menu_block_lines("```text\n" + "\n".join(rows) + "\n```\n")
        assert set(parsed) == {k for k, _lb, _cb, _q in MENU_ITEMS}
        assert parsed[items[0][0]] == items[0][1]

    def test_no_menu_block_reported(self, drift, tmp_path):
        """无主菜单块（缺 [E]/[X] 识别标志）→ 报未找到。"""
        p = tmp_path / "faq.md"
        findings = drift.check_menu_blocks({p: "# 无菜单块\n\n普通段落。\n"})
        assert any("未找到主菜单 code block" in f for f in findings)


class TestReturnKeyInvariant:
    """全文档「返回主菜单」键=0 不变量（第 18 项扩展：返回键全局统一）。"""

    def test_zero_forms_all_pass(self, drift, tmp_path):
        """各合法 0 键形态（图块/列表/表格）无 finding。"""
        p = tmp_path / "how-to-use-tui-menu.md"
        text = (
            "```text\n   [0] 返回主菜单\n```\n"
            "- **0 返回主菜单**（回车同效）\n"
            "| D | 聚合三项；`[0]` 返回主菜单，改完可继续改其它项 |\n"
        )
        assert drift.check_return_key_invariant({p: text}) == []

    def test_block_b_key_reported(self, drift, tmp_path):
        """图块 [B] 返回 → 报应为 0。"""
        p = tmp_path / "how-to-use-tui-menu.md"
        findings = drift.check_return_key_invariant({p: "```text\n   [B] 返回主菜单\n```\n"})
        assert any("[B]" in f and "应为 0" in f for f in findings)

    def test_list_bold_b_reported(self, drift, tmp_path):
        """列表项「**B 返回主菜单**」→ 报应为 0。"""
        p = tmp_path / "how-to-use-tui-menu.md"
        findings = drift.check_return_key_invariant({p: "- **B 返回主菜单**（回车同效）\n"})
        assert any("[B]" in f and "应为 0" in f for f in findings)

    def test_table_backtick_key_reported(self, drift, tmp_path):
        """表格内反引号包裹的 `[B]` 返回（真实残留形态，人工 grep 模式会漏）→ 报应为 0。"""
        p = tmp_path / "requirements.md"
        findings = drift.check_return_key_invariant(
            {p: "| D | 聚合三项，另有配置入口地图；`[B]` 返回主菜单，改完可继续改其它项 |\n"}
        )
        assert any("[B]" in f and "应为 0" in f for f in findings)

    def test_prose_exempt(self, drift, tmp_path):
        """自由 prose 叙述豁免（FAQ 的 Ctrl+C 形态 / QA 流内 q 退出非面板导航）。"""
        p = tmp_path / "faq.md"
        text = "按 `Ctrl+C` 中断返回主菜单，检查 `logs/app.log`。\n\n3. 输入问题回车；输入回车或 `q` 返回主菜单。\n"
        assert drift.check_return_key_invariant({p: text}) == []

    def test_distant_key_and_tail_chinese_exempt(self, drift, tmp_path):
        """行内远处非返回键与行尾中文（changelog 式列表/表格叙述）不误报。"""
        p = tmp_path / "technical.md"
        text = (
            "- **优化**：`[L]` 生成确认合并，Esc 即时取消（返回主菜单）语义不变\n"
            "| **Esc** | 子菜单：按 Esc 即时取消返回主菜单，无需找「0 返回」 |\n"
        )
        assert drift.check_return_key_invariant({p: text}) == []


class TestMenuKeyReferences:
    """正文「菜单 `X`」引用须为主菜单键；`[D]` 二级键须写作 `D` → `X`。"""

    def test_legal_forms_pass(self, drift, tmp_path):
        """主菜单键各书写形态（裸键/反引号/方括号/加粗）均无 finding。"""
        p = tmp_path / "faq.md"
        text = (
            "菜单 `L` 会先检查缓存。\n"
            "在菜单 **[S]** 的机制与诊断块切换。\n"
            "菜单 `[3]` 清理过期缓存。\n"
            "菜单 `G` → `C` 可改持仓目录。\n"
            "菜单 C 的五个章节组相互独立。\n"
        )
        assert drift.check_menu_key_references({p: text}) == []

    def test_stale_main_key_reported(self, drift, tmp_path):
        """缓存管理编号迁移后遗留的旧主菜单键 `[4]` → 报出（历史真实残留）。"""
        p = tmp_path / "faq.md"
        findings = drift.check_menu_key_references({p: "也可通过菜单 `[4]` → `3` 清理过期缓存。\n"})
        assert any("[4]" in f and "不是主菜单键" in f for f in findings)

    def test_submenu_key_needs_g_prefix(self, drift, tmp_path):
        """[G] 的二级键裸写为「菜单 `F`」→ 报出并提示 `G` → `F` 写法。

        取 `F`（持仓文件名）作反例而不是 `C`：`C` 已是主菜单键（章节显隐），
        裸写合法；二级键里与主菜单键重名者按设计文档「层级间互不冲突」放行。
        """
        p = tmp_path / "how-to-config.md"
        findings = drift.check_menu_key_references({p: "| `holdings_filename` | 持仓文件名 | 菜单 `F` |\n"})
        assert any("`G` → `F`" in f for f in findings)

    def test_bare_word_not_captured(self, drift, tmp_path):
        """「主菜单 code block」里的英文词首字母不当作键（裸键形态须跟空白/标点）。"""
        p = tmp_path / "developer-guide.md"
        text = "| 新增菜单项 | 同步两本手册的主菜单 code block |\n"
        assert drift.check_menu_key_references({p: text}) == []


class TestVisibilityTypeRows:
    """`reports-instruction.md` 可见性表 type 行 ↔ 章节注册表 type 集合双向对账。"""

    @staticmethod
    def _doc(*types: str) -> str:
        rows = "".join(f"| `{t}` | 控制 | 条件 | E / B / L |\n" for t in types)
        return f"### 可见性规则总览\n\n| type | board | data | 菜单 |\n|:--|:--|:--|:--|\n{rows}\n---\n"

    def _patch(self, drift_parts, monkeypatch, types: tuple[str, ...]):
        registry = [{"number": i + 1, "name": f"章{i}", "type": t} for i, t in enumerate(types)]
        monkeypatch.setattr(drift_parts._format, "_REPORT_SECTION_DEFAULT", registry)

    def test_matching_set_passes(self, drift, drift_parts, monkeypatch):
        self._patch(drift_parts, monkeypatch, ("always", "llm"))
        assert drift.check_visibility_type_rows(self._doc("always", "llm")) == []

    def test_missing_type_reported(self, drift, drift_parts, monkeypatch):
        """注册表有而表里没有（`schedule_replay` 漏行即此型）→ 报出。"""
        self._patch(drift_parts, monkeypatch, ("always", "schedule_replay"))
        findings = drift.check_visibility_type_rows(self._doc("always"))
        assert any("缺少 type `schedule_replay`" in f for f in findings)

    def test_unknown_type_reported(self, drift, drift_parts, monkeypatch):
        """表里写了注册表没有的 type（`financial_report` 混入即此型）→ 报出。"""
        self._patch(drift_parts, monkeypatch, ("always", "fundamental_snapshot"))
        findings = drift.check_visibility_type_rows(self._doc("always", "financial_report"))
        assert any("没有的 type `financial_report`" in f for f in findings)

    def test_duplicate_type_reported(self, drift, drift_parts, monkeypatch):
        self._patch(drift_parts, monkeypatch, ("always",))
        findings = drift.check_visibility_type_rows(self._doc("always", "always"))
        assert any("重复" in f for f in findings)
