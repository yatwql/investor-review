"""缓存编排下沉 cache.operations：update_all / warm 预热 / stats 载荷单源。

三处原为渠道内编排（CLI 最大努力聚合、TUI 新资产预热、Web 统计载荷组装），
现下沉共享层——本文件锁定其行为与「渠道只调用不编排」的回归基础。
"""

from __future__ import annotations

import contextlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.python.cache.operations import get_cache_stats_payload, update_all_cache, warm_new_asset_caches

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class _Holder:
    """最小持仓替身（warm 需要 code/name 属性）。"""

    def __init__(self, code: str, name: str):
        self.code = code
        self.name = name


class TestUpdateAllCache:
    """最大努力模式：basic 失败仍执行 position，退出码取最大值。"""

    def test_exit_code_is_max_of_both(self):
        with (
            patch(
                "src.python.cache.operations.update_basic_cache",
                return_value=SimpleNamespace(exit_code=0),
            ) as m_basic,
            patch(
                "src.python.cache.operations.update_position_cache",
                return_value=SimpleNamespace(exit_code=3),
            ) as m_pos,
        ):
            code = update_all_cache([_Holder("1", "x")], MagicMock())
        assert code == 3
        m_basic.assert_called_once()
        m_pos.assert_called_once()

    def test_basic_failure_still_runs_position(self):
        with (
            patch(
                "src.python.cache.operations.update_basic_cache",
                return_value=SimpleNamespace(exit_code=3),
            ) as m_basic,
            patch(
                "src.python.cache.operations.update_position_cache",
                return_value=SimpleNamespace(exit_code=0),
            ) as m_pos,
        ):
            code = update_all_cache([], MagicMock())
        assert code == 3
        m_basic.assert_called_once()
        m_pos.assert_called_once()


class TestUpdateBasicCacheScope:
    """「刷新基础缓存」只作废本流程会回填的缓存域。

    回归：原先 clear_by_group("refresh") 清整组，把不回填的财报索引/正文与财务
    指标一并作废——实测一次刷新后紧接的报告多付 267 次请求、墙钟翻倍。
    """

    def test_clears_only_refilled_domains(self):
        from src.python.cache.operations import update_basic_cache

        with (
            patch("src.python.cache.clear_by_group") as m_clear,
            patch("src.python.cache.operations._refresh_common_caches", return_value=(1, 1, 1, 1)),
            patch("src.python.cache.operations._refresh_extended_caches"),
            patch("src.python.report.fund_performance.is_fund", return_value=False),
        ):
            update_basic_cache([], MagicMock())

        only = set(m_clear.call_args.kwargs["only"])
        assert {"news_", "industry_", "fund_perf_"} <= only, "本流程会回填的域必须清（否则刷新无效）"
        leaked = {"report_datasink_doc_", "report_datasink_index_", "fin_indicator_"} & only
        assert leaked == set(), f"财报/财务指标由报告管线回填，不得随刷新作废：{leaked}"

    def test_declared_keys_all_registered(self):
        """声明的域名必须都能在缓存注册表里找到（防前缀改名后静默失效）。

        `_BASIC_REFRESHED_CACHE_KEYS` 是手写清单，与注册表之间没有类型约束：某个前缀或
        精确键换了名，清缓存会静默变成空操作（刷新不再生效，且无任何报错），故逐项
        断言登记存在。
        """
        from src.python.cache.operations import _BASIC_REFRESHED_CACHE_KEYS
        from src.python.core.registry import get_cache_registry

        registered: set[str] = set()
        for module in get_cache_registry():
            registered |= set(module.cache_prefixes) | set(module.exact_cache_keys)
        assert not (set(_BASIC_REFRESHED_CACHE_KEYS) - registered), (
            "以下域名未在缓存注册表登记（前缀/精确键改名后需同步本清单）"
        )


class TestWarmNewAssetCaches:
    """预热编排在共享层：变更检测 → 行情/基金 → 行业；异常不阻断。"""

    @patch("src.python.report.fund_performance.is_fund", return_value=False)
    @patch("src.python.fetcher.industry.batch_fetch_industry_data", return_value={"SH510300": {"industry": "指数"}})
    @patch("src.python.fetcher.price.fetch_market_data", return_value={"price": 4.2})
    @patch("src.python.cache.check_and_refresh_caches", return_value=["SH510300"])
    def test_warms_new_code(self, mock_refresh, mock_price, mock_industry, mock_is_fund):
        reporter = MagicMock()
        holders = [_Holder("SH510300", "沪深300ETF")]
        result = warm_new_asset_caches(holders, reporter)
        assert result == ["SH510300"]
        mock_refresh.assert_called_once_with(holders)
        mock_price.assert_called_once_with("SH510300", "沪深300ETF")
        mock_industry.assert_called_once_with(["SH510300"])

    @patch("src.python.cache.check_and_refresh_caches", return_value=[])
    def test_no_new_codes_returns_empty(self, mock_refresh):
        reporter = MagicMock()
        assert warm_new_asset_caches([], reporter) == []
        mock_refresh.assert_called_once()
        reporter.info.assert_not_called()

    @patch("src.python.fetcher.price.fetch_market_data", side_effect=RuntimeError("net down"))
    @patch("src.python.cache.check_and_refresh_caches", return_value=["SH1"])
    def test_fetcher_exception_does_not_block(self, mock_refresh, mock_price):
        reporter = MagicMock()
        result = warm_new_asset_caches([_Holder("SH1", "x")], reporter)
        # 异常被吞（不阻断后续生成），返回已检测到的新增码
        assert result == ["SH1"]


class TestStatsPayload:
    """GET /api/cache 载荷单源组装：契约键、保序数组、top 截断。"""

    @patch("src.python.cache.cleanup_expired", return_value=7)
    @patch("src.python.cache.get_cache_hit_rate", return_value={"hit": 5, "miss": 1, "hit_rate": 0.83})
    @patch(
        "src.python.cache.get_cache_stats",
        return_value={
            "total_files": 42,
            "total_size_bytes": 1024,
            "by_prefix": {"price": 3, "fund": 10, "industry": 5},
            "top_by_size": [{"name": f"f{i}", "size": i} for i in range(10)],
        },
    )
    def test_payload_contract(self, mock_stats, mock_rate, mock_expired):
        payload = get_cache_stats_payload()
        assert payload["total_files"] == 42
        assert payload["total_size_bytes"] == 1024
        # by_prefix = 二维数组、按文件数降序（保序下发，防 Flask sort_keys 重排）
        assert payload["by_prefix"] == [["fund", 10], ["industry", 5], ["price", 3]]
        # top_by_size 截断前 5
        assert len(payload["top_by_size"]) == 5
        assert payload["hit_rate"] == {"hit": 5, "miss": 1, "hit_rate": 0.83}
        assert payload["expired_count"] == 7
        # 契约键完整（双向相等，不写死新增键）
        assert set(payload) == {
            "total_files",
            "total_size_bytes",
            "by_prefix",
            "top_by_size",
            "hit_rate",
            "expired_count",
        }

    @patch("src.python.cache.cleanup_expired", return_value=0)
    @patch("src.python.cache.get_cache_hit_rate", return_value={})
    @patch("src.python.cache.get_cache_stats", return_value={})
    def test_payload_defaults_on_empty_stats(self, mock_stats, mock_rate, mock_expired):
        payload = get_cache_stats_payload()
        assert payload["total_files"] == 0
        assert payload["by_prefix"] == []
        assert payload["top_by_size"] == []
        # json 可序列化（前端契约）
        assert json.dumps(payload, ensure_ascii=False)


@contextlib.contextmanager
def _report_rules(monkeypatch: pytest.MonkeyPatch, trading_day: str = "2026-11-05", prev: str = "2026-11-04"):
    """把报告侧与历法的判定点全部钉死（只需交易日 / 收市状态）。"""
    monkeypatch.setattr("src.python.core.trading_calendar.get_last_trading_day", lambda: trading_day)
    monkeypatch.setattr("src.python.core.trading_calendar.get_prev_trading_day", lambda day="": prev)
    monkeypatch.setattr("src.python.report.market_value.is_market_open", lambda: False)
    monkeypatch.setattr("src.python.report.market_value.is_midday_break", lambda: False)
    monkeypatch.setattr("src.python.report.market_value.get_last_trading_day", lambda: trading_day)
    monkeypatch.setattr("src.python.report.market_value.get_prev_trading_day", lambda day="": prev)
    yield


class TestJudgeAfterRefresh:
    """刷新后单次判定：分组 / 是否最新 / 口径标签全引用 report.market_value。"""

    def test_groups_and_latest_follow_report_rules(self, monkeypatch: pytest.MonkeyPatch):
        """场内取收市价(T)、国内场外取 T 日净值、QDII 以 T-1 为最新。"""
        from src.python.cache.operations import _judge_after_refresh

        holdings = [
            SimpleNamespace(code="600900", name="长江电力", account="A股账户"),
            SimpleNamespace(code="011506", name="建信高端装备股票A", account="基金账户"),
            SimpleNamespace(code="017730", name="嘉实全球产业升级股票(QDII)A", account="基金账户"),
        ]
        details = [
            {"code": "600900", "name": "长江电力", "price": 29.0, "price_date": "2026-11-05", "source_api": "tencent"},
            {
                "code": "011506",
                "name": "建信高端装备A",
                "price": 1.38,
                "price_date": "2026-11-05",
                "source_api": "eastmoney",
            },
            {
                "code": "017730",
                "name": "嘉实全球(QDII)A",
                "price": 3.15,
                "price_date": "2026-11-04",
                "source_api": "eastmoney",
            },
        ]
        with _report_rules(monkeypatch):
            trading_day, breakdown = _judge_after_refresh(holdings, details)

        assert trading_day == "2026-11-05"
        assert breakdown is not None
        by_group = {slot["group"]: slot for slot in breakdown}
        assert by_group["场内"]["latest"] == 1
        assert by_group["场内"]["labels"]["场内收盘价(T)"] == 1
        assert by_group["国内场外"]["latest"] == 1
        assert by_group["国内场外"]["labels"]["官方净值(T)"] == 1
        assert by_group["QDII"]["latest"] == 1
        assert by_group["QDII"]["labels"]["官方净值(T-1)"] == 1

    def test_stale_item_lands_in_pending(self, monkeypatch: pytest.MonkeyPatch):
        """T-1 的国内场外净值不算最新（只有 QDII 才把 T-1 当最新）。"""
        from src.python.cache.operations import _judge_after_refresh

        holdings = [SimpleNamespace(code="011506", name="建信高端装备A", account="基金账户")]
        details = [
            {
                "code": "011506",
                "name": "建信高端装备A",
                "price": 1.38,
                "price_date": "2026-11-04",
                "source_api": "eastmoney",
            }
        ]
        with _report_rules(monkeypatch):
            _, breakdown = _judge_after_refresh(holdings, details)

        assert breakdown is not None
        slot = breakdown[0]
        assert slot["latest"] == 0
        assert slot["pending"][0]["code"] == "011506"
        assert slot["pending"][0]["label"] == "官方净值(T-1)"

    def test_name_falls_back_to_holding_for_qdii(self, monkeypatch: pytest.MonkeyPatch):
        """场外净值接口不回名称：QDII 要靠持仓名识别，否则 T-1 会被误判未更新。"""
        from src.python.cache.operations import _judge_after_refresh

        holdings = [SimpleNamespace(code="017730", name="嘉实全球产业升级股票(QDII)A", account="基金账户")]
        details = [{"code": "017730", "name": "", "price": 3.15, "price_date": "2026-11-04", "source_api": "eastmoney"}]
        with _report_rules(monkeypatch):
            _, breakdown = _judge_after_refresh(holdings, details)

        assert breakdown is not None
        assert breakdown[0]["group"] == "QDII"
        assert breakdown[0]["latest"] == 1
        assert breakdown[0]["pending"] == []

    def test_calendar_failure_returns_empty_without_raising(self, monkeypatch: pytest.MonkeyPatch):
        """交易日历不可得时只丢判定，不得把刷新结果带崩。"""
        from src.python.cache.operations import _judge_after_refresh

        def _boom():
            raise RuntimeError("日历不可用")

        monkeypatch.setattr("src.python.core.trading_calendar.get_last_trading_day", _boom)
        assert _judge_after_refresh([SimpleNamespace(code="600900", name="长江电力", account="A")], []) == ("", None)

    def test_update_position_cache_carries_trading_day_and_breakdown(self, monkeypatch: pytest.MonkeyPatch):
        """刷新流程把属交易日与分市场判定一起回传，且不再回传原始明细。"""
        from src.python.cache import operations

        monkeypatch.setattr("src.python.cache.clear_by_group", lambda *a, **kw: {})
        monkeypatch.setattr(
            "src.python.fetcher.price.fetch_market_data",
            lambda code, name="": {
                "code": code,
                "name": name,
                "price": 20.0,
                "price_date": "2026-11-05",
                "source_api": "tencent",
            },
        )
        monkeypatch.setattr("src.python.fetcher.index.fetch_indices", lambda: {})
        monkeypatch.setattr("src.python.fetcher.index.fetch_us_indices", lambda: {})
        with _report_rules(monkeypatch):
            result = operations.update_position_cache(
                [SimpleNamespace(code="600900", name="长江电力", account="A股账户")], MagicMock()
            )

        assert result.price_ok == 1
        assert result.trading_day == "2026-11-05"
        assert result.market_breakdown is not None
        assert result.market_breakdown[0]["latest"] == 1
        assert not hasattr(result, "price_details")


class TestRefreshKeepsTrackingBaseline:
    """「刷新基础缓存」只清不重建，不得连坐作废跨报告对比基线。

    回归：刷新流程把 `fund_manager_snapshot` 一并清掉（前缀命中 + 无回填路径），
    刷完紧接着出报告即退化成「首次运行」。
    """

    def test_update_basic_cache_passes_preserve_list(self):
        from src.python.cache.operations import update_basic_cache
        from src.python.core.registry import TRACKING_SNAPSHOT_KEYS

        with (
            patch("src.python.cache.clear_by_group") as m_clear,
            patch("src.python.cache.operations._refresh_common_caches", return_value=(1, 1, 1, 1)),
            patch("src.python.cache.operations._refresh_extended_caches"),
            patch("src.python.report.fund_performance.is_fund", return_value=False),
        ):
            update_basic_cache([], MagicMock())

        assert set(m_clear.call_args.kwargs["exclude_keys"]) == set(TRACKING_SNAPSHOT_KEYS)

    def test_snapshot_file_kept_payload_files_cleared(self, tmp_path, monkeypatch):
        from src.python.cache import _groups, _paths
        from src.python.cache._paths import _CACHE_KEY_VERSION

        monkeypatch.setattr(_paths, "_CACHE_DIR", str(tmp_path))
        monkeypatch.setattr(_groups, "_CACHE_DIR", str(tmp_path))
        snapshot = tmp_path / f"fund_manager_snapshot_{_CACHE_KEY_VERSION}.json"
        payload = tmp_path / f"fund_manager_110011_{_CACHE_KEY_VERSION}.json"
        snapshot.write_text('{"_ts": 0, "_data": {}}', encoding="utf-8")
        payload.write_text('{"_ts": 0, "_data": {}}', encoding="utf-8")

        from src.python.cache import clear_by_group
        from src.python.cache.operations import _BASIC_REFRESHED_CACHE_KEYS
        from src.python.core.registry import TRACKING_SNAPSHOT_KEYS

        clear_by_group("refresh", only=_BASIC_REFRESHED_CACHE_KEYS, exclude_keys=TRACKING_SNAPSHOT_KEYS)

        assert snapshot.exists(), "跟踪基线被刷新流程误删 → 下次报告必「首检」"
        assert not payload.exists(), "本流程会回填的域必须清（否则刷新无效）"
