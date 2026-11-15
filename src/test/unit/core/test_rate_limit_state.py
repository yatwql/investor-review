"""东财 push2 限流观测（`core/rate_limit_state.py`）单元测试。

覆盖：特征文案识别、计数与首条留存、提示文案格式、重置。
"""

from __future__ import annotations

import pytest

from src.python.core import rate_limit_state as rs

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestDetection:
    """按文案识别限流/断连（不需要异常类型）。"""

    @pytest.mark.parametrize(
        "message",
        [
            "东方财富 push2 行情服务器断开了连接，通常是短时间内请求过多，当前 IP 被临时限流。",
            "('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))",
            "push2 行情服务器断连（RemoteProtocolError）: 600900",
        ],
    )
    def test_limited_texts(self, message):
        assert rs.is_push2_limited(message) is True

    @pytest.mark.parametrize("message", ["", None, "JSON 解析失败", "no data"])
    def test_non_limited_texts(self, message):
        assert rs.is_push2_limited(message) is False


class TestCounters:
    """计数与提示文案：无命中不出行；命中累计并按本轮次数出文案。"""

    def test_note_increments_and_keeps_first(self):
        rs.reset_push2_limit_state()
        assert rs.note_failure("JSON 解析失败，跳过该代码") is False  # 不含特征词
        assert rs.note_failure("push2 行情服务器断开了连接") is True
        assert rs.note_failure("RemoteDisconnected") is True
        state = rs.push2_limited()
        assert state["count"] == 2
        assert "push2" in str(state["first"])
        assert rs.notice_line() == rs.NOTICE_TEMPLATE.format(n=2)

    def test_empty_notice_when_no_hit(self):
        rs.reset_push2_limit_state()
        assert rs.notice_line() == ""

    def test_reset_clears_state(self):
        rs.note_failure("临时限流")
        rs.reset_push2_limit_state()
        assert rs.push2_limited()["count"] == 0


class TestProvidersHook:
    """akshare 传输侧（`run_with_timeout` 重试回调）命中即计数。"""

    def test_retry_callback_records_limiter(self):
        from src.python.providers.utils import run_with_timeout

        rs.reset_push2_limit_state()

        def _boom():
            raise RuntimeError("东方财富 push2 行情服务器断开了连接，当前 IP 被临时限流")

        # retries=1 → 两次尝试，首次失败即触发重试回调（计数点）
        assert run_with_timeout(_boom, timeout=5.0, retries=1) is None
        assert rs.push2_limited()["count"] >= 1
