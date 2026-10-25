"""财报章节探测的负缓存 —— 已确认缺失的（文档, 章节）不再反复发请求。

财报全文按候选章节名逐个探测，每次 404 都是一个网络往返（实测 7 只标的 × 多章节
约十余秒/份报告），而「源侧确实没有该章节」的结论跨报告稳定。负缓存让同一天的
后续报告直接走降级路径，同时不影响新增文档/章节的可见性（TTL 12h）。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.python.providers import datasink

pytestmark = [pytest.mark.unit, pytest.mark.unit_providers]


def _resp(status: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = {"ok": True}
    return r


@pytest.fixture()
def _credential(monkeypatch):
    monkeypatch.setattr(datasink, "missing_credential", lambda _sid: None)
    monkeypatch.setattr(datasink, "credential_value", lambda _sid: "k")
    monkeypatch.setattr(datasink, "_consume_quota", lambda: True)


class TestProbeMissNegativeCache:
    def test_second_probe_skips_http(self, _credential):
        with (
            patch.object(datasink, "_get_with_transient_retry", return_value=_resp(404)) as http,
            patch.object(datasink, "cache_get", return_value=None),
            patch.object(datasink, "cache_set") as miss_set,
        ):
            assert datasink._request("/documents/1", {"section": "管理层讨论与分析"}) is None
            first_calls = http.call_count
            # 模拟负缓存生效
            with patch.object(datasink, "cache_get", return_value=True):
                assert datasink._request("/documents/1", {"section": "管理层讨论与分析"}) is None
        assert first_calls == 1
        assert http.call_count == first_calls, "命中负缓存后不得再发请求"
        miss_set.assert_called()  # 首次 404 已写入负缓存

    def test_negative_cache_written_only_for_probe_404(self, _credential):
        with (
            patch.object(datasink, "_get_with_transient_retry", return_value=_resp(404)),
            patch.object(datasink, "cache_get", return_value=None),
            patch.object(datasink, "cache_set") as miss_set,
        ):
            datasink._request("/documents/1", {"section": "经营情况"})
        key = miss_set.call_args[0][0]
        assert key.startswith("datasink_probe_miss_")

    def test_document_level_404_is_not_negative_cached(self, _credential):
        """不带 section 的文档级 404 属真缺失（WARNING 级），不进探测负缓存。"""
        with (
            patch.object(datasink, "_get_with_transient_retry", return_value=_resp(404)),
            patch.object(datasink, "cache_get", return_value=None),
            patch.object(datasink, "cache_set") as miss_set,
        ):
            datasink._request("/documents/1", {})
        assert not miss_set.called

    def test_success_path_ignores_negative_cache_key(self, _credential):
        """成功响应流程不受负缓存影响，也不写负缓存。"""
        with (
            patch.object(datasink, "_get_with_transient_retry", return_value=_resp(200)),
            patch.object(datasink, "cache_get", return_value=None),
            patch.object(datasink, "cache_set") as miss_set,
        ):
            assert datasink._request("/documents/1", {"section": "经营情况"}) == {"ok": True}
        assert not miss_set.called
