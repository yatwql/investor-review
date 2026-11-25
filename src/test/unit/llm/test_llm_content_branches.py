"""LLM 内容 Excel 写入的边角分支（`report/llm_content`）。

契约面：
  - 分段器对「游离文本出现在块级标签前面」的顺序敏感（漏收拢会丢正文首段）；
  - 占位文案要区分「已知失败原因」与「未登记的新原因」——后者不能退化成
    「请配置 API Key」，否则用户会被指向错误的排查方向；
  - 实验模式注解只落在智囊团复盘页签；
  - 结构化契约（主张与证据）必须写进同一页签，且未建页签时跳过而不是崩。
"""

from __future__ import annotations

import pytest
from openpyxl import Workbook

from src.python.report import llm_content as mod

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]


class TestSplitHtmlBlocks:
    def test_leading_free_text_is_flushed_before_block(self):
        """块级标签之前的游离文本先收拢成独立块，顺序不得颠倒。"""
        blocks = mod._split_html_blocks("前置说明<p>正文</p>")

        assert blocks[0] == "前置说明"
        assert "<p>正文</p>" in blocks

    def test_leading_free_text_only_returns_single_block(self):
        """全程无块级标签 → 整段一块（不得被丢弃）。"""
        assert mod._split_html_blocks("纯文本一行") == ["纯文本一行"]

    def test_trailing_free_text_joins_previous_block(self):
        """块后游离文本并入前块（校验摘要的附属行不得拆成新段）。"""
        blocks = mod._split_html_blocks("<p>摘要</p>附属行")

        assert len(blocks) == 1
        assert "摘要" in blocks[0] and "附属行" in blocks[0]


class TestPlaceholder:
    def _title(self):
        return f"{mod.get_report_section_order()[0]['number']}.{mod.get_report_section_order()[0]['name']}"

    def test_known_reason_maps_to_specific_copy(self, monkeypatch):
        monkeypatch.setattr(mod, "get_llm_module_failure_reason", lambda kind, mk: mod.FAIL_REASON_TIMEOUT)

        placeholder = mod._get_placeholder(self._title())

        assert placeholder == mod._PLACEHOLDER_BY_REASON[mod.FAIL_REASON_TIMEOUT]

    def test_unregistered_reason_falls_back_to_generic_generation_failure(self, monkeypatch):
        """未登记的新失败原因 → 通用「LLM 生成失败」，不得误导成「未配置 API Key」。"""
        monkeypatch.setattr(mod, "get_llm_module_failure_reason", lambda kind, mk: "brand_new_reason")

        placeholder = mod._get_placeholder(self._title())

        assert placeholder == "本节内容待生成 — LLM 生成失败"
        assert "API Key" not in placeholder

    def test_unknown_title_asks_for_api_key(self):
        assert "API Key" in mod._get_placeholder("99.不存在的章节")


class TestWriteContentSheet:
    def _sheet(self):
        wb = Workbook()
        return wb.active

    def test_debate_label_rendered_as_note_row(self):
        """实验模式注解写到标题下方，正文从下一行开始。"""
        ws = self._sheet()

        mod._write_content_sheet(ws, "8.智囊团深度复盘", "<p>正文</p>", debate_mode_label="辩论模式")

        values = [(c.row, str(c.value)) for c in ws["A"] if c.value]
        note_row = next(row for row, value in values if "实验模式输出（辩论模式）" in value)
        body_row = next(row for row, value in values if value == "正文")
        assert body_row > note_row, "注解须在正文之前"

    def test_footer_block_not_duplicated(self):
        """底部 LLM 标识行只写一次：正文里那一块跳过，末尾统一补。"""
        ws = self._sheet()
        footer = "模型：mock · 生成时间：12:00"
        content = f'<p>正文</p><p style="color:#888;font-size:12px">{footer}</p>'

        mod._write_content_sheet(ws, "7.全球政经局势", content)

        values = [str(c.value) for c in ws["A"] if c.value]
        assert values.count(footer) == 1

    def test_empty_block_does_not_create_blank_row(self):
        """自闭合块（`<br/>`）剥离后为空 → 跳过，不得占一行空白。"""
        ws = self._sheet()

        mod._write_content_sheet(ws, "7.全球政经局势", "<p>正文</p><br/>")

        values = [str(c.value) for c in ws["A"] if c.value]
        assert values == ["7.全球政经局势", "正文"]

    def test_contract_rows_written_into_same_sheet(self, monkeypatch):
        """结构化契约（主张与证据）写进同一页签：首行标题 + 声明行 + 灰色明细行。"""
        ws = self._sheet()
        contracts = {
            "global_macro": {
                "verdict_label": "成立",
                "claims": [{"statement": "降息预期升温", "evidence": ["点阵图"], "invalidations": ["通胀反弹"]}],
            }
        }
        monkeypatch.setattr(
            "src.python.report.llm_contract_block.get_module_contracts",
            lambda: contracts,
        )

        mod._write_content_sheet(ws, "7.全球政经局势", "<p>正文</p>", module_key="global_macro")

        values = [str(c.value) for c in ws["A"] if c.value]
        assert any("主张与证据" in v for v in values)
        assert any("降息预期升温" in v for v in values)
        assert any("点阵图" in v for v in values), "证据必须随声明落表"

    def test_no_contract_keeps_sheet_shape(self, monkeypatch):
        """开关关闭（契约载体为空）→ 行内容与无该功能时一致。"""
        ws = self._sheet()
        monkeypatch.setattr("src.python.report.llm_contract_block.get_module_contracts", dict)

        mod._write_content_sheet(ws, "7.全球政经局势", "<p>正文</p>", module_key="global_macro")

        values = [str(c.value) for c in ws["A"] if c.value]
        assert not any("主张与证据" in v for v in values)


class TestWriteLlmSheets:
    def _sheets(self):
        wb = Workbook()
        return {"global_macro": wb.active}

    def test_missing_sheet_is_skipped(self, monkeypatch, caplog):
        """`_create_sheets` 未建页签（功能开关组合差异）→ 告警跳过，不抛 KeyError。"""
        monkeypatch.setattr(mod, "get_llm_module_failure_reason", lambda kind, mk: None)
        sheets = self._sheets()

        mod.write_llm_sheets(sheets, ("<p>a</p>", "<p>b</p>", "<p>c</p>", "<p>d</p>"))

        assert "未由 _create_sheets 创建" in caplog.text

    def test_disabled_module_is_skipped(self, monkeypatch):
        """已禁用模块不写页签（占位文案由创建阶段决定，避免覆盖）。"""
        monkeypatch.setattr(
            mod,
            "get_llm_module_failure_reason",
            lambda kind, mk: mod.FAIL_REASON_DISABLED if mk == "global_macro" else None,
        )
        sheets = self._sheets()
        original = sheets["global_macro"]["A1"].value

        mod.write_llm_sheets(sheets, ("<p>a</p>", None, None, None))

        assert sheets["global_macro"]["A1"].value == original, "禁用模块不得被写入内容"
