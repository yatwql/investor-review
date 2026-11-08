"""tiantian_holdings 季报探测：空季度负缓存与 jjcc 对冲并发。

回归场景（2026-11-01 运行日志）：穿透阶段 15.3s，其中超短债基金 012325 的 jjcc
空回前挂了 6.9s 才改用 zqcc；无数据的基金每轮都重走 4 个季度 × 2 通道。
"""

from __future__ import annotations


import pytest

from src.python.providers import tiantian_holdings as th

pytestmark = [pytest.mark.unit, pytest.mark.unit_providers]


class TestQuarterMissCache:
    """空季度（jjcc/zqcc 双通道均无）写入负缓存，后续运行不再重探。"""

    def test_empty_quarters_are_not_reprobed(self, monkeypatch):
        calls: list[tuple[str, int | None, int | None]] = []

        def _fake(code, api_type, year=None, month=None):
            calls.append((api_type, year, month))
            return None

        monkeypatch.setattr(th, "_request_quarterly_api", _fake)
        monkeypatch.setattr(th, "_request_fund_html", lambda code: None)

        assert th.fetch_fund_holdings("000001") is None
        first_round = len(calls)
        assert first_round == th._QUARTER_LOOKBACK * 2, calls

        assert th.fetch_fund_holdings("000001") is None
        assert len(calls) == first_round, f"空季度应命中负缓存，第二次仍发请求：{calls[first_round:]}"


class TestJjccHedge:
    """jjcc 慢时对冲并发 zqcc；jjcc 快时不多发请求。"""

    @staticmethod
    def _stub_parse(monkeypatch):
        monkeypatch.setattr(th, "_extract_quarterly_meta", lambda html: ("某基金", "2026-09-30"))
        monkeypatch.setattr(
            th,
            "_parse_quarterly_holdings",
            lambda html: [{"name": html, "code": "", "ratio": 5.0}],
        )

    def test_slow_jjcc_hedges_to_zqcc(self, monkeypatch):
        """jjcc 挂起时按对冲阈值并发发出 zqcc——用事件同步判定，不靠墙钟。

        判据是「zqcc 起跳时 jjcc 仍未返回」：jjcc 阻塞在事件上，zqcc 起跳即记录，
        用例等「zqcc 已起跳」后校验此刻 jjcc 尚未返回，再放行两者。刻意不按耗时阈值
        判定——耗时把「是否并发」与 runner 调度快慢混在一起，慢机器上会红成假阳性。
        """
        import threading

        order: list[str] = []
        release_jjcc = threading.Event()
        jjcc_returned = threading.Event()
        zqcc_started = threading.Event()

        def _fake(code, api_type, year=None, month=None):
            order.append(api_type)
            if api_type == "jjcc":
                release_jjcc.wait(timeout=10)  # 模拟挂起：由用例放行，不靠 sleep
                jjcc_returned.set()
                return None
            zqcc_started.set()
            return "zq"

        monkeypatch.setattr(th, "_request_quarterly_api", _fake)
        self._stub_parse(monkeypatch)

        outcome: dict[str, object] = {}

        def _run() -> None:
            outcome["result"] = th._fetch_single_quarter("012325", 2026, 9)

        worker = threading.Thread(target=_run, name="fund-hold-test", daemon=True)
        worker.start()
        try:
            assert zqcc_started.wait(timeout=10), "jjcc 未返回时未发出 zqcc（对冲没生效）"
            assert not jjcc_returned.is_set(), "对冲必须与挂起的 jjcc 并发，而不是等它返回后才发"
        finally:
            release_jjcc.set()
            worker.join(timeout=10)

        result = outcome["result"]
        assert isinstance(result, dict) and result["holdings"], "对冲后应取到 zqcc 的持仓"
        assert result["holdings"][0]["name"] == "zq"
        assert order[0] == "jjcc" and "zqcc" in order, order

    def test_fast_jjcc_sends_no_extra_request(self, monkeypatch):
        order: list[str] = []

        def _fake(code, api_type, year=None, month=None):
            order.append(api_type)
            return "jj" if api_type == "jjcc" else "zq"

        monkeypatch.setattr(th, "_request_quarterly_api", _fake)
        self._stub_parse(monkeypatch)

        result = th._fetch_single_quarter("011506", 2026, 9)

        assert result is not None
        assert result["holdings"][0]["name"] == "jj", "jjcc 有数据时应优先采用"
        assert order == ["jjcc"], f"jjcc 快速返回时不应多发 zqcc：{order}"
