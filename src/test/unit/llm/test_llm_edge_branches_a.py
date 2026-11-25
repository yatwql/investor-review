"""熔断状态展示 / 盘中复用归因 / 证据索引 / 档位解析的残差分支测试。

覆盖四类契约：
  - `get_circuit_status` + `circuit_status_snapshot`：核心网关取用的展示面
    （中文状态词、冷却剩余、阈值/恢复秒数回显、非熔断端点 `circuit_broken=False`）
  - `intraday_reuse_blocked`：盘中档 + 观测汇聚器时写 `note_cache(False)` 与
    `note_recompute_reason`
  - `build_evidence_index`：非数值收益率不出「收益率」段、带价格出报价证据行
  - `resolve_depth_profile`：配置读取异常时按默认档降级
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]


@pytest.fixture()
def clean_circuit_state():
    """隔离熔断器模块级状态（快照断言依赖空起点）。"""
    from src.python.llm import circuit_breaker

    with circuit_breaker._circuit_lock:
        circuit_breaker._circuit_failures.clear()
        circuit_breaker._circuit_open_until.clear()
    yield circuit_breaker
    with circuit_breaker._circuit_lock:
        circuit_breaker._circuit_failures.clear()
        circuit_breaker._circuit_open_until.clear()


def test_get_circuit_status_reports_open_and_normal(clean_circuit_state):
    """熔断中返回「熔断中」，冷却期满自动半开返回「正常」。"""
    cb = clean_circuit_state
    url = "https://api.example.com/v1/messages"
    cb._cb_record_failure(url, cooldown=600.0, force=True)

    assert cb.get_circuit_status(url) == "熔断中"
    assert cb.get_circuit_status("https://other.example.com/v1") == "正常"


def test_circuit_status_snapshot_reports_both_endpoint_kinds(clean_circuit_state, monkeypatch):
    """快照逐端点回显：熔断中的带冷却剩余，仅记失败未熔断的 `circuit_broken=False`。"""
    cb = clean_circuit_state
    opened_url = "https://api.opened.com/v1/messages"
    failing_url = "https://api.failing.com/v1/messages"
    opened, failing = cb._cb_endpoint(opened_url), cb._cb_endpoint(failing_url)

    cb._cb_record_failure(opened_url, cooldown=600.0, force=True)
    cb._cb_record_failure(failing_url, cooldown=600.0, force=False)

    snapshot = cb.circuit_status_snapshot()

    assert set(snapshot) == {opened, failing}
    assert snapshot[opened]["circuit_broken"] is True
    assert snapshot[opened]["cooldown_remaining"] == pytest.approx(600.0, abs=5.0)
    assert snapshot[failing]["circuit_broken"] is False
    assert snapshot[failing]["consecutive_failures"] == 1
    assert snapshot[failing]["threshold"] == cb._CIRCUIT_BREAKER_THRESHOLD
    assert snapshot[failing]["recovery_secs"] == cb._CIRCUIT_BREAKER_RECOVERY


def test_intraday_block_records_reason_on_sink(monkeypatch):
    """盘中档不复用价格相关模块时，归因与缓存标记一并写入观测汇聚器。"""
    from src.python.core import market_hours
    from src.python.llm.cache_policy import intraday_reuse_blocked
    from src.python.llm.observation import RECOMPUTE_INTRADAY_NO_REUSE

    class _Sink:
        def __init__(self):
            self.cache_flags = []
            self.reasons = []

        def note_cache(self, hit):
            self.cache_flags.append(hit)

        def note_recompute_reason(self, module_key, reason):
            self.reasons.append((module_key, reason))

    monkeypatch.setattr(
        market_hours,
        "market_snapshot_bucket",
        lambda now=None: market_hours.MarketSnapshot(
            key="intraday:2026-11-06", label="盘中", as_of="2026-11-06", intraday=True
        ),
    )
    sink = _Sink()

    assert intraday_reuse_blocked("expert_review", sink) is True
    assert sink.cache_flags == [False]
    assert sink.reasons == [("expert_review", RECOMPUTE_INTRADAY_NO_REUSE)]


def test_intraday_block_skips_sink_when_module_is_price_independent(monkeypatch):
    """价格无关模块盘中照常复用：不写归因（避免白算一次）。"""
    from src.python.core import market_hours
    from src.python.llm.cache_policy import intraday_reuse_blocked

    class _Sink:
        def __init__(self):
            self.cache_flags = []

        def note_cache(self, hit):
            self.cache_flags.append(hit)

        def note_recompute_reason(self, module_key, reason):  # pragma: no cover - 不应被调用
            raise AssertionError("价格无关模块不应写不复用归因")

    monkeypatch.setattr(
        market_hours,
        "market_snapshot_bucket",
        lambda now=None: market_hours.MarketSnapshot(
            key="intraday:2026-11-06", label="盘中", as_of="2026-11-06", intraday=True
        ),
    )
    sink = _Sink()

    assert intraday_reuse_blocked("global_macro", sink) is False
    assert sink.cache_flags == []


def test_evidence_index_skips_rate_when_value_not_numeric():
    """非数值收益率不出「收益率」段；带价格的持仓另出报价证据行。"""
    from src.python.llm.evidence_index import build_evidence_index

    index = build_evidence_index(
        holdings_details=[
            {"code": "000001", "name": "华夏成长", "profit_rate": "暂无", "price": 1.234},
            {"code": "   ", "name": "无代码持仓"},
        ]
    )

    assert index["ev:hold:000001"] == "华夏成长（000001）持仓"
    assert index["ev:quote:000001"] == "华夏成长（000001）最新价 1.234"
    assert len(index) == 2, "无代码持仓不入索引"


def test_evidence_index_penetrated_assets_need_name_and_codes():
    """穿透资产仅在有名称且有代码时入索引，代码列表去空白后取首个作 id。"""
    from src.python.llm.evidence_index import build_evidence_index

    index = build_evidence_index(
        penetrated_assets=[
            {"name": "白酒 ETF", "codes": [" 512690 ", "000858"]},
            {"name": "缺代码资产", "codes": ["  "]},
            {"name": "  ", "codes": ["600519"]},
        ]
    )

    assert index == {"ev:pen:512690": "穿透资产 白酒 ETF（512690/000858）"}


def test_evidence_index_includes_metric_and_skips_non_numeric():
    """量化指标仅数值型入索引（bool 与非数值键忽略）。"""
    from src.python.llm.evidence_index import build_evidence_index

    index = build_evidence_index(metrics={"beta": 0.87, "sharpe": None, "flag": True})

    assert index["ev:metric:beta"] == "组合指标 beta = 0.87"
    assert "ev:metric:sharpe" not in index
    assert "ev:metric:flag" not in index


def test_resolve_depth_profile_falls_back_when_config_unreadable(monkeypatch):
    """配置读取抛异常时按默认档继续（非致命降级）。"""
    import src.python.config as config_module
    from src.python.llm.depth_profile import REPORT_DEPTH_DEFAULT, resolve_depth_profile

    def _boom(*_args, **_kwargs):
        raise RuntimeError("config.json 不可读")

    monkeypatch.setattr(config_module, "get_config", _boom)

    assert resolve_depth_profile().key == REPORT_DEPTH_DEFAULT
