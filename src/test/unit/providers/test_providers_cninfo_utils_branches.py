"""provider 公共设施与巨潮公告 provider 的防御分支（utils / cninfo）。

测试场景：
  1. 风控页判定：非文本响应、空白体、空值都判「非风控页」，特征词命中判风控页
  2. 超时包装：观测登记自身异常不影响「全部失败返回 None」的契约
  3. 时间戳串：超出可表示范围返回空串
  4. 巨潮：无 scheme 的 URL 不作主机标记；重试槽失败由 _post_json 收口；
     空代码不取数；标题无年份的公告跳过；PDF 逐页提取空页跳过
"""

from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import patch

import pytest

from src.python.providers import cninfo, utils

pytestmark = [pytest.mark.unit, pytest.mark.unit_providers, pytest.mark.usefixtures("offline_external_sources")]


class TestUtilsGuards:
    """``looks_like_block_page`` / ``run_with_timeout`` / ``ts_to_str`` 的兜底。"""

    @pytest.mark.parametrize("payload", [None, b'{"a": 1}', "   ", ""])
    def test_non_text_or_blank_payload_is_not_block_page(self, payload: object):
        """非文本 / 空白响应体 → 不判风控页（交给解析层或链路）。"""
        assert utils.looks_like_block_page(payload) is False

    def test_rate_limit_hint_is_block_page(self):
        """纯文本限流提示（无 HTML）→ 判风控页。"""
        assert utils.looks_like_block_page("访问过于频繁，请稍后再试") is True

    def test_retry_observer_failure_does_not_break_none_contract(self):
        """观测登记本身抛异常 → 仍按「全部失败返回 None」收口。"""

        def _boom() -> float:
            raise ValueError("取数失败")

        with patch("src.python.core.rate_limit_state.note_failure", side_effect=RuntimeError("登记失败")):
            assert utils.run_with_timeout(_boom, timeout=1.0, retries=1) is None

    def test_timestamp_out_of_range_returns_empty(self):
        """时间戳超出平台可表示范围 → 空串（不让 OSError 冒给报告）。"""
        assert utils.ts_to_str(10**18) == ""


class TestCninfoGuards:
    """巨潮公告 provider 的主机标记、失败收口与脏元数据。"""

    def test_url_without_scheme_never_marked_unreachable(self):
        """无 scheme 的 URL 无法取主机名 → 不标记也不命中不可达。"""
        cninfo._mark_host_unreachable("www.cninfo.com.cn/new/index")
        assert cninfo._is_host_unreachable("www.cninfo.com.cn/new/index") is False

    def test_post_json_returns_none_when_retry_slot_fails(self):
        """重试槽整体失败（None）→ ``_post_json`` 直接收口为 None。"""
        with patch.object(cninfo, "_with_transient_retry", return_value=None):
            assert cninfo._post_json("/new/hisAnnouncement/query", {}) is None

    def test_post_json_none_after_rate_limit_retry(self):
        """HTTP 429 后重试仍失败（None）→ 收口为 None，不继续读 status_code。"""
        throttled = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock(status_code=429)
        with patch.object(cninfo, "_with_transient_retry", side_effect=[throttled, None]):
            assert cninfo._post_json("/new/hisAnnouncement/query", {}) is None

    def test_empty_code_returns_none(self):
        """空代码（含纯空白）→ 不发起查询。"""
        assert cninfo.fetch_report_listings("   ") is None

    def test_announcement_without_year_skipped(self):
        """标题可分类但不含年份 → 该公告跳过（不产出无报告期的候选）。"""
        payload = {
            "announcements": [
                {"announcementTitle": "年度报告", "adjunctUrl": "finalpage/1.PDF", "announcementTime": 1},
                {"announcementTitle": "2018年年度报告", "adjunctUrl": "finalpage/2.PDF", "announcementTime": 2},
            ]
        }
        with (
            patch.object(cninfo, "cache_get", return_value=None),
            patch.object(cninfo, "cache_set"),
            patch.object(cninfo, "resolve_org_id", return_value="gssz0000001"),
            patch.object(cninfo, "_post_json", return_value=payload),
        ):
            items = cninfo.fetch_report_listings("000001")

        assert [it["report_period"] for it in items] == ["2018-12-31"]
        assert items[0]["adjunct_url"] == "finalpage/2.PDF"

    def test_pdf_pages_with_empty_text_are_skipped(self, monkeypatch):
        """PDF 逐页提取：无文本页跳过，有文本页按换行拼接。"""

        class _Page:
            def __init__(self, text: str | None) -> None:
                self._text = text

            def extract_text(self) -> str | None:
                return self._text

        class _Pdf:
            pages = [_Page("第一页正文"), _Page(None), _Page("  "), _Page("第二页正文")]

            def __enter__(self) -> _Pdf:
                return self

            def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
                return False

        fake: Any = types.ModuleType("pdfplumber")
        fake.open = lambda *_a, **_k: _Pdf()
        monkeypatch.setitem(sys.modules, "pdfplumber", fake)
        assert cninfo._parse_pdf_text(b"%PDF-1.4") == "第一页正文\n第二页正文"
