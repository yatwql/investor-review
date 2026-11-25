"""新闻关联的边角分支（`report/news_correlation`）。

锁四条与「口径可追溯」相关的路径：
  - 行业/概念关键词扩展：取数失败必须回落原关键词（不能把新闻模块拖死）；
  - LLM 费用估算按归一后用量算（与页脚同源），无用量时写 `-`；
  - 新闻源状态取不到只降级为「无状态」，不影响匹配结果；
  - 页脚/着色：缓存命中带 Thinking 标注、费用与 Thinking 分项上屏、利好利空异色。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from openpyxl import Workbook

from src.python.core.models import Holding
from src.python.report import news_correlation as nc

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]

_ITEM = {
    "title": "新闻",
    "intro": "简介",
    "url": "http://ex.com",
    "ctime": "2026-08-01",
    "media_name": "新浪",
    "matched_keywords": ["长江电力"],
}


class TestExpandIndustryKeywords:
    def test_keywords_expanded_with_industry_and_concepts(self):
        """行业名与概念名并入关键词，且行业/概念部分单独给出（下游据此放宽匹配门槛）。"""
        holdings = [Holding(account="证券", name="长江电力", code="600900", shares=100, cost_price=10.0)]
        industry = {
            "600900": {"industry": "电力行业", "concepts": ["水电", " 绿电 "]},
        }
        with patch("src.python.fetcher.industry.batch_fetch_industry_data", return_value=industry):
            keywords, data, lightweight = nc._expand_industry_keywords(holdings, [], ["长江电力"])

        assert "电力行业" in keywords
        assert "水电" in keywords
        assert "绿电" in keywords, "概念名两侧空白须归一"
        assert lightweight == {"电力行业", "水电", "绿电"}
        assert data == industry

    def test_keywords_sorted_by_length_desc(self):
        """长词优先：保证「长江电力」不被短词先匹配走。"""
        holdings = [Holding(account="证券", name="长江电力", code="600900", shares=100, cost_price=10.0)]
        industry = {"600900": {"industry": "电力", "concepts": ["水力发电运营"]}}
        with patch("src.python.fetcher.industry.batch_fetch_industry_data", return_value=industry):
            keywords, _, _ = nc._expand_industry_keywords(holdings, [], ["长江电力"])

        lengths = [len(k) for k in keywords]
        assert lengths == sorted(lengths, reverse=True)

    def test_fetch_failure_falls_back_to_original_keywords(self, caplog):
        """行业取数异常 → 原关键词 + 空数据 + 警告（新闻匹配照常进行）。"""
        holdings = [Holding(account="证券", name="长江电力", code="600900", shares=100, cost_price=10.0)]
        with patch("src.python.fetcher.industry.batch_fetch_industry_data", side_effect=RuntimeError("probe")):
            keywords, data, lightweight = nc._expand_industry_keywords(holdings, [], ["长江电力"])

        assert keywords == ["长江电力"]
        assert (data, lightweight) == ({}, set())
        assert "行业/概念数据获取失败" in caplog.text

    def test_no_a_share_codes_skips_fetch(self):
        """无 A 股标的（纯 ETF/场外基金）→ 不发起行业取数。"""
        holdings = [Holding(account="证券", name="某ETF", code="511880", shares=100, cost_price=10.0)]
        fetch = MagicMock()
        with patch("src.python.fetcher.industry.batch_fetch_industry_data", fetch):
            keywords, data, lightweight = nc._expand_industry_keywords(holdings, [], ["某ETF"])

        fetch.assert_not_called()
        assert (keywords, data, lightweight) == (["某ETF"], {}, set())

    def test_empty_industry_payload_keeps_keywords(self):
        holdings = [Holding(account="证券", name="长江电力", code="600900", shares=100, cost_price=10.0)]
        with patch("src.python.fetcher.industry.batch_fetch_industry_data", return_value={}):
            assert nc._expand_industry_keywords(holdings, [], ["长江电力"]) == (["长江电力"], {}, set())


class TestExtractActiveSources:
    def test_labels_deduped_and_empty_skipped(self):
        items = [{"_source": "新浪"}, {"_source": "新浪"}, {"_source": ""}, {"_source": "财联社"}, {}]

        assert nc._extract_active_sources(items) == ["新浪", "财联社"]


class TestLlmEnhancementCost:
    _HOLDINGS = [Holding(account="证券", name="长江电力", code="600900", shares=100, cost_price=10.0)]

    def _meta(self, token_usage: dict) -> dict:
        config = {"enabled_llm": {"news_correlation": True}, "api_key": "sk-test"}
        with (
            patch("src.python.config.get_llm_config", return_value=config),
            patch("src.python.llm.pricing.estimate_cost", return_value="¥0.012") as estimate,
            patch("src.python.llm.session._normalize_usage_tokens", return_value=(100, 20, 30)),
            patch("src.python.llm.run_news_correlation_safe", return_value=([dict(_ITEM)], False, token_usage)),
        ):
            meta = nc._apply_llm_enhancement([dict(_ITEM)], self._HOLDINGS, None, {}, {"llm_enabled": False})
        return meta, estimate

    def test_cost_estimated_from_normalized_usage(self):
        """费用按归一后 (输入, 输出, 命中) 三元组估算，与页脚同一口径。"""
        meta, estimate = self._meta({"model": "mock", "total_tokens": 120})

        assert meta["cost_estimation"] == "¥0.012"
        assert estimate.call_args.args[1:] == (100, 20)
        assert estimate.call_args.kwargs["cache_hit_input_tokens"] == 30

    def test_no_usage_writes_dash(self):
        meta, estimate = self._meta({})

        assert meta["cost_estimation"] == "-"
        estimate.assert_not_called()


class TestSourceStatusDegradation:
    _HOLDINGS = [Holding(account="证券", name="长江电力", code="600900", shares=100, cost_price=10.0)]

    def test_status_failure_does_not_break_matching(self, caplog):
        """补充源状态失败 → 只留警告，匹配结果与 meta 其余字段照常返回。"""
        with (
            patch("src.python.fetcher.news.aggregate_news", return_value=[dict(_ITEM)]),
            patch("src.python.fetcher.news.build_holding_keywords", return_value=["长江电力"]),
            patch("src.python.fetcher.industry.batch_fetch_industry_data", return_value={}),
            patch(
                "src.python.fetcher.news.get_last_source_status",
                MagicMock(side_effect=RuntimeError("probe fault")),
            ),
            patch("src.python.config.get_llm_config", return_value=None),
        ):
            news, meta = nc.build_news_data(self._HOLDINGS)

        assert len(news) == 1
        assert meta["source_status"] == {}, "取不到状态时回空表，其余字段照常"
        assert "补充新闻源状态失败" in caplog.text

    def test_status_failure_without_news_keeps_empty_list(self, caplog):
        """news 为空时同样尝试补状态；失败只警告并返回空新闻（不抛）。"""
        with (
            patch("src.python.fetcher.news.aggregate_news", return_value=[]),
            patch("src.python.fetcher.news.build_holding_keywords", return_value=["长江电力"]),
            patch("src.python.fetcher.industry.batch_fetch_industry_data", return_value={}),
            patch(
                "src.python.fetcher.news.get_last_source_status",
                MagicMock(side_effect=RuntimeError("probe fault")),
            ),
            patch("src.python.config.get_llm_config", return_value=None),
        ):
            news, meta = nc.build_news_data(self._HOLDINGS)

        assert news == []
        assert meta["source_status"] == {}
        assert "获取新闻源状态失败" in caplog.text


class TestFootersAndColors:
    def _ws(self):
        wb = Workbook()
        return wb.active

    def _texts(self, ws):
        return [str(cell.value) for row in ws.iter_rows() for cell in row if cell.value is not None]

    def test_cached_hint_carries_thinking_marker(self):
        hint = nc._build_news_footer([_ITEM], {"llm_enabled": True, "llm_cached": True, "thinking_enabled": True})

        assert "LLM缓存" in hint
        assert "Extended Thinking" in hint

    def test_token_footer_skipped_without_usage(self):
        ws = self._ws()

        assert nc._write_news_token_footer(ws, 5, {"llm_enabled": True, "llm_cached": False, "token_usage": {}}) == 5

    def test_token_footer_contains_cost_and_thinking(self):
        """费用与 Extended Thinking 作为独立分项上屏（不是塞进同一句）。"""
        ws = self._ws()
        llm_meta = {
            "llm_enabled": True,
            "llm_cached": False,
            "token_usage": {"model": "mock", "input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
            "cost_estimation": "¥0.012",
            "thinking_enabled": True,
        }

        nc._write_news_token_footer(ws, 1, llm_meta)

        joined = next(t for t in self._texts(ws) if "Token 用量" in t)
        assert "估算费用：¥0.012" in joined
        assert "Extended Thinking" in joined

    def test_cost_dash_not_rendered(self):
        ws = self._ws()
        llm_meta = {
            "llm_enabled": True,
            "llm_cached": False,
            "token_usage": {"model": "mock", "total_tokens": 120},
            "cost_estimation": "-",
        }

        nc._write_news_token_footer(ws, 1, llm_meta)

        assert not any("估算费用" in t for t in self._texts(ws))

    def test_bullish_and_bearish_colors(self):
        """利好红、利空绿；中性无标记不染色。"""
        ws = self._ws()
        ws.cell(row=1, column=1, value="[利好] 涨")
        ws.cell(row=2, column=1, value="[利空] 跌")
        ws.cell(row=3, column=1, value="中性")

        nc._colorize_llm_cell(ws, 1, 1, "[利好] 涨")
        nc._colorize_llm_cell(ws, 2, 1, "[利空] 跌")
        nc._colorize_llm_cell(ws, 3, 1, "中性")

        assert str(ws.cell(row=1, column=1).font.color.rgb).endswith(nc._BULLISH_RED)
        assert str(ws.cell(row=2, column=1).font.color.rgb).endswith(nc._BEARISH_GREEN)
        neutral = ws.cell(row=3, column=1).font.color
        assert neutral is not None and neutral.type == "theme", "中性文本保持默认主题色（不染色）"


class TestPenetratedCodesExpansion:
    def test_penetrated_codes_join_industry_lookup(self):
        """穿透标的的代码也参与行业取数（否则穿透层的概念词永远扩展不出来）。"""
        holdings = [Holding(account="证券", name="长江电力", code="600900", shares=100, cost_price=10.0)]
        fetch = MagicMock(return_value={"300274": {"industry": "光伏设备", "concepts": ["储能"]}})
        with patch("src.python.fetcher.industry.batch_fetch_industry_data", fetch):
            keywords, _data, _light = nc._expand_industry_keywords(
                holdings, [{"name": "阳光电源", "codes": ["300274", "  "]}], ["长江电力"]
            )

        assert sorted(fetch.call_args.args[0]) == ["300274", "600900"]
        assert "光伏设备" in keywords


class TestSourceCallback:
    def test_ok_and_failure_lines(self, caplog):
        """逐源回调：成功记条数，失败记状态文案（TUI/CLI 共用同一行格式）。"""
        nc._news_source_cb("新浪", 12, "OK")
        nc._news_source_cb("财联社", 0, "timeout")

        assert "新闻源 新浪: 12 条" in caplog.text
        assert "新闻源 财联社: timeout" in caplog.text


class TestDisplayMasking:
    _HOLDINGS = [Holding(account="证券", name="长江电力", code="600900", shares=100, cost_price=10.0)]

    def test_off_mode_is_noop(self):
        items = [{"matched_keywords": ["长江电力"], "enriched_keywords": [{"label": "长江电力"}]}]

        nc._mask_news_display_fields(items, self._HOLDINGS, "off")

        assert items[0]["matched_keywords"] == ["长江电力"]

    def test_display_fields_masked(self):
        """打开匿名化 → 匹配词与富化标签换成代号（检索结果本身不动）。"""
        items = [
            {
                "matched_keywords": ["长江电力"],
                "enriched_keywords": [{"label": "长江电力", "kind": "holding"}, "raw-text"],
            }
        ]
        with patch("src.python.config.anonymizer.build_report_alias_map", return_value={"长江电力": "品种A"}):
            nc._mask_news_display_fields(items, self._HOLDINGS, "full_anonymous")

        assert items[0]["matched_keywords"] == ["品种A"]
        assert items[0]["enriched_keywords"][0]["label"] == "品种A"
        assert items[0]["enriched_keywords"][0]["kind"] == "holding", "非显示字段保留"
        assert items[0]["enriched_keywords"][1] == "raw-text", "非字典条目不改写"

    def test_items_without_display_fields_untouched(self):
        items: list[dict] = [{}]
        with patch("src.python.config.anonymizer.build_report_alias_map", return_value={}):
            nc._mask_news_display_fields(items, self._HOLDINGS, "code_display")

        assert items[0] == {}


class TestFootersWithFailedSources:
    def test_failed_sources_listed_in_footer(self):
        footer = nc._build_news_footer(
            [_ITEM],
            {
                "llm_enabled": False,
                "source_status": {"a": {"label": "财联社", "success": False}, "b": {"label": "新浪", "success": True}},
            },
        )

        assert "以下新闻源不可用：财联社" in footer


class TestAllSourcesFailedPlaceholder:
    def _ws(self):
        wb = Workbook()
        return wb.active

    def test_placeholder_written_when_all_sources_failed(self, caplog):
        """全部源失败 → 页签写占位文案（不留白表让用户以为「没有新闻」）。"""
        ws = self._ws()

        nc.write_news_sheet(
            ws, [], llm_meta={"llm_enabled": False, "source_status": {"a": {"label": "新浪", "success": False}}}
        )

        texts = [str(cell.value) for row in ws.iter_rows() for cell in row if cell.value is not None]
        assert texts, "必须写入占位内容"
        assert "所有新闻源均获取失败" in caplog.text
