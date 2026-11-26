"""akshare 扩展数据源的分支/降级补齐测试。

覆盖点（按接口族）：
  - 模块级可选依赖缺失：akshare 未安装时模块仍可导入且 ``ak is None``
  - 内存 memo 的 LRU 淘汰与命中
  - 行业资金流向：单通道取数失败/空榜/脏行、探针的未注册通道、文件缓存命中
  - 盈利预测：全字段解析、脏行跳过、空结果、缓存命中/未安装/缓存键
  - 分红：指纹降级、汇总解析异常、全量拉取失败/缺代码列、取数超时
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.python.core import v8_subprocess
from src.python.providers import akshare_extras as ae

pytestmark = [pytest.mark.unit, pytest.mark.unit_providers]


class _FakeRowsDF:
    """最小 DataFrame 替身：只实现 `empty` / `iterrows` / `columns`。"""

    def __init__(self, rows: list[dict], columns: list[str] | None = None) -> None:
        self._rows = rows
        self.empty = not rows
        self.columns = columns if columns is not None else sorted({k for r in rows for k in r})

    def iterrows(self):
        return list(enumerate(self._rows))


@pytest.fixture(autouse=True)
def _reset_akshare_extras_state():
    ae.reset_failure_state()
    ae._INDEX_MEMO.clear()
    yield
    ae.reset_failure_state()
    ae._INDEX_MEMO.clear()


# ── 模块级可选依赖 ────────────────────────────────────────────────


def test_module_imports_without_akshare(monkeypatch: pytest.MonkeyPatch) -> None:
    """akshare 缺失时模块导入降级为 ``ak is None``，不抛 ImportError。"""
    monkeypatch.setitem(sys.modules, "akshare", None)
    try:
        reloaded = importlib.reload(ae)
        assert reloaded.ak is None
        assert reloaded._MEMO_CACHE == {}
        assert reloaded._SECTOR_FLOW_CHANNELS == ae._SECTOR_FLOW_CHANNELS
    finally:
        monkeypatch.undo()
        importlib.reload(ae)


# ── 内存 memo ───────────────────────────────────────────────────


def test_memo_set_evicts_oldest_when_full(monkeypatch: pytest.MonkeyPatch) -> None:
    """超出 `_MEMO_MAX` 时淘汰最早写入的条目，新件仍可命中。"""
    monkeypatch.setattr(ae, "_MEMO_MAX", 2)
    now = [100.0]
    monkeypatch.setattr(ae._time, "time", lambda: now[0])

    ae._memo_set("profit_forecast:a", 1)
    now[0] = 200.0
    ae._memo_set("profit_forecast:b", 2)
    now[0] = 300.0
    ae._memo_set("profit_forecast:c", 3)

    assert set(ae._MEMO_CACHE) == {"profit_forecast:b", "profit_forecast:c"}
    assert ae._memo_get("profit_forecast:c") == 3


# ── 行业资金流向：通道层 ─────────────────────────────────────────


def test_em_channel_reports_connection_when_akshare_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ae, "ak", None)
    with pytest.raises(ae._SectorFlowUnavailable) as exc_info:
        ae._fetch_sector_flow_em_push2()
    assert (exc_info.value.kind, exc_info.value.channel) == ("connection", "em_push2")
    assert str(exc_info.value) == "em_push2:connection"


def test_ths_channel_reports_empty_when_no_records() -> None:
    with patch.object(v8_subprocess, "run_akshare_v8", return_value=[]):
        with pytest.raises(ae._SectorFlowUnavailable) as exc_info:
            ae._fetch_sector_flow_ths_industry()
    assert (exc_info.value.kind, exc_info.value.channel) == ("empty", "ths_industry")


def test_ths_channel_reports_connection_when_row_is_not_mapping() -> None:
    """单行非映射结构（无 `.get`）→ 规整为连接不可用，不向上抛裸异常。"""
    with patch.object(v8_subprocess, "run_akshare_v8", return_value=[object()]):
        with pytest.raises(ae._SectorFlowUnavailable) as exc_info:
            ae._fetch_sector_flow_ths_industry()
    assert (exc_info.value.kind, exc_info.value.channel) == ("connection", "ths_industry")


def test_ths_channel_converts_yi_to_yuan_and_derives_pct() -> None:
    """同花顺金额单位为亿元 → 换算成元；净占比由净额/成交额派生。"""
    records = [{"行业": "银行", "行业-涨跌幅": 1.5, "流入资金": 3.0, "流出资金": 1.0, "净额": 2.0, "领涨股": " X "}]
    with patch.object(v8_subprocess, "run_akshare_v8", return_value=records):
        rows = ae._fetch_sector_flow_ths_industry()
    assert rows == [
        {
            "name": "银行",
            "change_pct": 1.5,
            "main_net_inflow": 2.0 * ae._THS_YI_TO_YUAN,
            "main_net_inflow_pct": 50.0,
            "top_stock": "X",
        }
    ]


def test_struct_rows_reports_connection_when_iterrows_raises() -> None:
    """DataFrame 迭代异常（列结构变更等）→ 规整为通道不可用。"""
    df = MagicMock()
    df.iterrows.side_effect = ValueError("bad frame")
    with pytest.raises(ae._SectorFlowUnavailable) as exc_info:
        ae._struct_sector_flow_rows(df, ae._EM_SECTOR_FIELDS, "em_push2")
    assert (exc_info.value.kind, exc_info.value.channel) == ("connection", "em_push2")


def test_probe_reports_unregistered_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    """通道名未在取数表中注册 → 探针如实报不可用且不中断整表。"""
    monkeypatch.setattr(ae, "_SECTOR_FLOW_CHANNELS", ("ghost",))
    assert ae.probe_sector_flow_channels() == [("ghost", False, "未注册取数函数")]


def test_probe_reports_channel_failure_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    """通道自报不可用 → 探针直接回其失败类型（不带异常类名前缀）。"""

    def _unavailable() -> list[dict]:
        raise ae._SectorFlowUnavailable("empty", "em_push2")

    monkeypatch.setitem(ae._SECTOR_FLOW_FETCHERS, "em_push2", _unavailable)
    monkeypatch.setitem(ae._SECTOR_FLOW_FETCHERS, "ths_industry", lambda: [dict(_SECTOR_ROW)])
    results = ae.probe_sector_flow_channels()
    assert results[0][:2] == (ae._SECTOR_FLOW_CHANNEL_LABELS["em_push2"], False)
    assert results[0][2] == "empty"
    assert results[1][1] is True
    assert results[1][2].endswith("1 行业")


def test_probe_isolates_unexpected_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """单通道抛裸异常 → 探针记异常摘要，后续通道仍被探测。"""

    def _boom() -> list[dict]:
        raise RuntimeError("quota exceeded")

    def _empty() -> list[dict]:
        raise ae._SectorFlowUnavailable("empty", "ths_industry")

    monkeypatch.setitem(ae._SECTOR_FLOW_FETCHERS, "em_push2", _boom)
    monkeypatch.setitem(ae._SECTOR_FLOW_FETCHERS, "ths_industry", _empty)
    results = ae.probe_sector_flow_channels()
    assert results[0][:2] == (ae._SECTOR_FLOW_CHANNEL_LABELS["em_push2"], False)
    assert results[0][2] == "RuntimeError: quota exceeded"
    assert results[1] == (ae._SECTOR_FLOW_CHANNEL_LABELS["ths_industry"], False, "empty")


# ── 指数指纹 ────────────────────────────────────────────────────


def test_index_fingerprint_degrades_on_type_error() -> None:
    """取指数时出现类型/取值异常 → 空指纹（下游降级为纯 TTL 缓存键）。"""
    with patch("src.python.fetcher.index.fetch_indices", side_effect=ValueError("bad")):
        assert ae._compute_index_fingerprint() == ""
    assert ae._cache_key(ae._CACHE_FLOW_PREFIX, "") == "sector_flow_nofp"


def test_index_fingerprint_hashes_both_markets() -> None:
    with (
        patch("src.python.fetcher.index.fetch_indices", return_value=[{"code": "sh000001"}]),
        patch("src.python.fetcher.index.fetch_us_indices", return_value=[{"code": "DJI"}]),
    ):
        first = ae._compute_index_fingerprint()
    assert len(first) == 12
    assert ae._INDEX_MEMO["indices"][0] == ([{"code": "sh000001"}], [{"code": "DJI"}])


def test_index_fingerprint_uses_memo_within_ttl() -> None:
    """TTL 内的第二次调用不重取指数（避免同一会话反复拉全市场指数）。"""
    ae._INDEX_MEMO["indices"] = (([{"code": "sh000001"}], [{"code": "DJI"}]), ae._time.time())
    with (
        patch("src.python.fetcher.index.fetch_indices") as fetch_a,
        patch("src.python.fetcher.index.fetch_us_indices") as fetch_us,
    ):
        assert len(ae._compute_index_fingerprint()) == 12
    fetch_a.assert_not_called()
    fetch_us.assert_not_called()


# ── 盈利预测 ────────────────────────────────────────────────────


_FORECAST_ROW = {
    "代码": "600519",
    "名称": "贵州茅台",
    "研报数": 18,
    "2026预测每股收益": 68.5,
    "2027预测每股收益": 75.2,
    "机构投资评级(近六个月)-买入": 12,
    "机构投资评级(近六个月)-卖出": 1,
    "机构投资评级(近六个月)-中性": 3,
}


def _patch_forecast(fetch_result):
    return (
        patch.object(ae, "ak", MagicMock()),
        patch.object(ae, "run_with_timeout", return_value=fetch_result),
        patch.object(ae, "cache_get", return_value=None),
        patch.object(ae, "cache_set"),
        patch.object(ae, "_compute_index_fingerprint", return_value="fp1"),
    )


def test_profit_forecast_parses_all_fields_and_skips_dirty_rows() -> None:
    """空代码行与无法转 int 的行被跳过，其余行按契约字段落库。"""
    df = _FakeRowsDF(
        [
            _FORECAST_ROW,
            {**_FORECAST_ROW, "代码": ""},
            {**_FORECAST_ROW, "代码": "000001", "研报数": "未知"},
        ]
    )
    patches = _patch_forecast(df)
    with patches[0], patches[1], patches[2], patches[3] as cache_set, patches[4]:
        result = ae.get_profit_forecast()
    assert set(result) == {"600519"}
    assert result["600519"] == {
        "name": "贵州茅台",
        "reports": 18,
        "eps_2026e": pytest.approx(68.5),
        "eps_2027e": pytest.approx(75.2),
        "buy": 12,
        "sell": 1,
        "hold": 3,
    }
    cache_set.assert_called_once()
    assert cache_set.call_args.args[0] == "profit_forecast_fp1"


def test_profit_forecast_empty_frame_returns_empty() -> None:
    patches = _patch_forecast(_FakeRowsDF([]))
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        assert ae.get_profit_forecast() == {}
    assert ae._memo_get(ae._memo_key("profit_forecast")) is None


def test_profit_forecast_timeout_returns_empty() -> None:
    """`run_with_timeout` 返回 None（超时/取数异常）→ 空结果且不写缓存。"""
    patches = _patch_forecast(None)
    with patches[0], patches[1], patches[2], patches[3] as cache_set, patches[4]:
        assert ae.get_profit_forecast() == {}
    cache_set.assert_not_called()


def test_profit_forecast_fetch_calls_akshare_function() -> None:
    """取数闭包直接调 ``ak.stock_profit_forecast_em()``（含列名变更时的空结果降级）。"""
    fake_ak = MagicMock()
    fake_ak.stock_profit_forecast_em.return_value = _FakeRowsDF([_FORECAST_ROW])
    with (
        patch.object(ae, "ak", fake_ak),
        patch.object(ae, "cache_get", return_value=None),
        patch.object(ae, "cache_set"),
        patch.object(ae, "_compute_index_fingerprint", return_value=""),
        patch.object(ae, "run_with_timeout", side_effect=lambda fn, timeout=None: fn()),
    ):
        result = ae.get_profit_forecast()
    fake_ak.stock_profit_forecast_em.assert_called_once_with()
    assert result["600519"]["reports"] == 18


def test_profit_forecast_without_akshare_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ae, "ak", None)
    with (
        patch.object(ae, "cache_get", return_value=None),
        patch.object(ae, "_compute_index_fingerprint", return_value=""),
    ):
        assert ae.get_profit_forecast() == {}


def test_profit_forecast_memo_hit_skips_fetch() -> None:
    df = _FakeRowsDF([_FORECAST_ROW])
    patches = _patch_forecast(df)
    with patches[0], patches[1] as run, patches[2], patches[3], patches[4]:
        ae.get_profit_forecast()
        assert ae.get_profit_forecast() == {"600519": ae.get_profit_forecast()["600519"]}
    assert run.call_count == 1


def test_profit_forecast_file_cache_hit_skips_fetch() -> None:
    payload = {"600519": {"name": "贵州茅台", "reports": 1}}
    patches = _patch_forecast(_FakeRowsDF([_FORECAST_ROW]))
    with patches[0], patches[1] as run, patch.object(ae, "cache_get", return_value=payload), patches[4]:
        assert ae.get_profit_forecast() == payload
    assert run.call_count == 0


def test_profit_forecast_cache_key_uses_index_fingerprint() -> None:
    with patch.object(ae, "_compute_index_fingerprint", return_value="abc123"):
        assert ae.get_profit_forecast_cache_key() == "profit_forecast_abc123"
    with patch.object(ae, "_compute_index_fingerprint", return_value=""):
        assert ae.get_profit_forecast_cache_key() == "profit_forecast_nofp"


# ── 行业资金流向：入口层 ────────────────────────────────────────


_SECTOR_ROW = {
    "name": "银行",
    "change_pct": 1.2,
    "main_net_inflow": 5e8,
    "main_net_inflow_pct": 3.1,
    "top_stock": "招商银行",
}


def test_sector_flow_memo_hit_skips_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def _fetch() -> list[dict]:
        calls.append("em")
        return [dict(_SECTOR_ROW)]

    monkeypatch.setitem(ae._SECTOR_FLOW_FETCHERS, "em_push2", _fetch)
    with (
        patch.object(ae, "cache_get", return_value=None),
        patch.object(ae, "cache_set"),
        patch.object(ae, "_compute_index_fingerprint", return_value=""),
    ):
        first = ae.get_sector_fund_flow()
        second = ae.get_sector_fund_flow()
    assert first == second == [_SECTOR_ROW]
    assert calls == ["em"]


def test_sector_flow_file_cache_hit_refreshes_stale_baseline() -> None:
    """文件缓存命中即视为成功：清失败态、写 memo、并把载荷续作陈旧回退基准。"""
    cached = [dict(_SECTOR_ROW)]
    with (
        patch.object(ae, "cache_get", return_value=cached),
        patch.object(ae, "cache_set") as cache_set,
        patch.object(ae, "_compute_index_fingerprint", return_value="fp1"),
    ):
        assert ae.get_sector_fund_flow() == cached
    cache_set.assert_called_once_with(ae._SECTOR_FLOW_LAST_KEY, cached)
    assert (ae.sector_flow_failure(), ae.sector_flow_degraded_state()) == ("", "")
    assert ae._memo_get(ae._memo_key("sector_flow")) == cached


def test_sector_flow_without_akshare_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ae, "ak", None)
    with (
        patch.object(ae, "cache_get", return_value=None),
        patch.object(ae, "_compute_index_fingerprint", return_value=""),
    ):
        assert ae.get_sector_fund_flow() == []


def test_sector_flow_empty_channel_falls_through_to_next(monkeypatch: pytest.MonkeyPatch) -> None:
    """通道返回空榜等同于取不到数 → 记 empty 失败态并继续下一通道。"""
    monkeypatch.setitem(ae._SECTOR_FLOW_FETCHERS, "em_push2", lambda: [])
    monkeypatch.setitem(ae._SECTOR_FLOW_FETCHERS, "ths_industry", lambda: [dict(_SECTOR_ROW)])
    with (
        patch.object(ae, "cache_get", return_value=None),
        patch.object(ae, "cache_set"),
        patch.object(ae, "_compute_index_fingerprint", return_value=""),
    ):
        assert ae.get_sector_fund_flow() == [_SECTOR_ROW]
        assert ae._channel_failures() == {"em_push2": "empty"}


# ── 分红 ────────────────────────────────────────────────────────


def test_dividend_fingerprint_degrades_when_codes_unserializable() -> None:
    """不可 JSON 序列化的代码列表 → "nofp"（降级为无指纹缓存键）。"""
    assert ae._compute_dividend_fingerprint([object()]) == "nofp"  # type: ignore[list-item]


def _agg_div_df(avg, cnt, columns=("代码", "名称", "年均股息", "分红次数")) -> MagicMock:
    row = {"年均股息": avg, "分红次数": cnt, "代码": "600519", "名称": "贵州茅台"}
    df = MagicMock()
    df.empty = False
    df.columns = list(columns)
    df.iloc.__getitem__.return_value = row
    return df


def test_dividend_summary_ignores_non_positive_average() -> None:
    assert ae._calc_dividend_summary(_agg_div_df(0, 3)) is None
    assert ae._calc_dividend_summary(_agg_div_df(-1.2, 3)) is None


def test_dividend_summary_returns_none_on_unparsable_count() -> None:
    """分红次数非数值 → 解析异常被吞，返回 None 而非抛给调用方。"""
    assert ae._calc_dividend_summary(_agg_div_df(2.5, "多次")) is None


def test_fetch_all_dividends_without_akshare(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ae, "ak", None)
    assert ae._fetch_all_dividends(["600519"]) == {}


def test_fetch_all_dividends_swallows_source_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ak = MagicMock()
    fake_ak.stock_history_dividend.side_effect = ConnectionError("boom")
    monkeypatch.setattr(ae, "ak", fake_ak)
    assert ae._fetch_all_dividends(["600519"]) == {}


def test_fetch_all_dividends_without_code_column(monkeypatch: pytest.MonkeyPatch) -> None:
    """缺「代码」列时无法按代码过滤 → 空结果（不猜测列名）。"""
    fake_ak = MagicMock()
    fake_ak.stock_history_dividend.return_value = _FakeRowsDF(
        [{"名称": "贵州茅台", "年均股息": 20.0}], columns=["名称", "年均股息"]
    )
    monkeypatch.setattr(ae, "ak", fake_ak)
    assert ae._fetch_all_dividends(["600519"]) == {}


def test_fetch_all_dividends_empty_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """全量快照为空 → 直接返回空结果，不做逐代码过滤。"""
    fake_ak = MagicMock()
    fake_ak.stock_history_dividend.return_value = _FakeRowsDF([])
    monkeypatch.setattr(ae, "ak", fake_ak)
    assert ae._fetch_all_dividends(["600519"]) == {}


def test_fetch_all_dividends_filters_by_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """全量数据按代码过滤后只剩目标股票，并带出名称。"""
    import pandas as pd

    fake_ak = MagicMock()
    fake_ak.stock_history_dividend.return_value = pd.DataFrame(
        [
            {"代码": "600519", "名称": "贵州茅台", "年均股息": 20.0, "分红次数": 5},
            {"代码": "000858", "名称": "五粮液", "年均股息": 1.5, "分红次数": 2},
        ]
    )
    monkeypatch.setattr(ae, "ak", fake_ak)
    assert ae._fetch_all_dividends(["600519"]) == {
        "600519": {"avg_dividend": 20.0, "record_count": 5, "name": "贵州茅台"}
    }


def test_dividend_data_without_akshare_reports_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ae, "ak", None)
    with (
        patch.object(ae, "cache_get", return_value=None),
        patch.object(ae, "_compute_dividend_fingerprint", return_value=""),
    ):
        assert ae.get_dividend_data(["600519"]) == {}
    assert ae.dividend_failure() == "connection"


def test_dividend_data_timeout_marks_connection_failure() -> None:
    """取数超时（`run_with_timeout` 返回 None）→ 连接失败态且不写缓存。"""
    with (
        patch.object(ae, "ak", MagicMock()),
        patch.object(ae, "cache_get", return_value=None),
        patch.object(ae, "cache_set") as cache_set,
        patch.object(ae, "run_with_timeout", return_value=None),
    ):
        assert ae.get_dividend_data(["600519"]) == {}
    assert ae.dividend_failure() == "connection"
    cache_set.assert_not_called()


def test_dividend_data_empty_result_marks_empty() -> None:
    """取数通了但一只都没有 → "empty"（区分源不可达与本无分红）。"""
    with (
        patch.object(ae, "ak", MagicMock()),
        patch.object(ae, "cache_get", return_value=None),
        patch.object(ae, "cache_set") as cache_set,
        patch.object(ae, "run_with_timeout", return_value={}),
    ):
        assert ae.get_dividend_data(["600519"]) == {}
    assert ae.dividend_failure() == "empty"
    cache_set.assert_not_called()
