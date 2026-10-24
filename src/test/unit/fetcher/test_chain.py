"""Provider Chain 回退机制单元测试。

测试目标：
  - _get_chain — 默认顺序、preferred_provider 前置
  - fetch_with_fallback — 缓存命中、Provider 遍历、验证、转换、降级

运行：
  pytest src/test/unit/fetcher/test_chain.py -v"""

from __future__ import annotations
import unittest
from unittest.mock import MagicMock, patch
from src.python.fetcher import chain
from src.python.fetcher.chain import (
    _call_history_provider,
    fetch_with_incremental_fallback,
    _get_chain,
    reset_provider_skip,
)
from src.python.fetcher.chain_incremental import _missing_trading_days
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher]


class TestGetChain(unittest.TestCase):
    """Provider Chain 顺序获取测试。"""

    def test_default_chain(self):
        """无 preferred_provider → 返回默认顺序。"""
        chain = _get_chain("price")
        self.assertEqual(chain, ["tencent", "eastmoney"])

    def test_default_chain_unknown_type(self):
        """未知 data_type → 返回空列表。"""
        chain = _get_chain("nonexistent")
        self.assertEqual(chain, [])

    @patch("src.python.fetcher.chain_config.get_config")
    def test_preferred_moves_to_front(self, mock_config):
        """preferred_provider.price = eastmoney → eastmoney 前置。"""
        mock_config.return_value = {"preferred_provider": {"price": "eastmoney"}}
        chain = _get_chain("price")
        self.assertEqual(chain[0], "eastmoney")
        self.assertEqual(chain, ["eastmoney", "tencent"])

    @patch("src.python.fetcher.chain_config.get_config")
    def test_preferred_already_first(self, mock_config):
        """preferred 已在首位 → 顺序不变。"""
        mock_config.return_value = {"preferred_provider": {"price": "tencent"}}
        chain = _get_chain("price")
        self.assertEqual(chain, ["tencent", "eastmoney"])

    @patch("src.python.fetcher.chain_config.get_config")
    def test_preferred_not_in_chain(self, mock_config):
        """preferred 不在默认 chain 中 → 忽略，返回原顺序。"""
        mock_config.return_value = {"preferred_provider": {"price": "alibaba"}}
        chain = _get_chain("price")
        self.assertEqual(chain, ["tencent", "eastmoney"])

    @patch("src.python.fetcher.chain_config.get_config")
    def test_no_preferred_provider_key(self, mock_config):
        """config 中没有 preferred_provider 键 → 返回默认。"""
        mock_config.return_value = {}
        chain = _get_chain("price")
        self.assertEqual(chain, ["tencent", "eastmoney"])

    @patch("src.python.fetcher.chain_config.get_config")
    def test_config_raises_key_error(self, mock_config):
        """get_config 抛出异常 → 安全返回默认 chain。"""
        mock_config.side_effect = KeyError("test")
        chain = _get_chain("price")
        self.assertEqual(chain, ["tencent", "eastmoney"])


class TestIsProviderChainBroken(unittest.TestCase):
    """is_provider_chain_broken 全链健康查询测试。"""

    def setUp(self):
        reset_provider_skip()

    @patch("src.python.fetcher.chain_config._get_chain")
    def test_all_skipped(self, mock_chain):
        """全部 provider 在熔断中 → True。"""
        from src.python.fetcher.chain import is_provider_chain_broken
        from src.python.core.provider_registry import get_registry

        mock_chain.return_value = ["p1", "p2"]
        reg = get_registry()
        reg.register_provider("p1", 2)
        reg.register_provider("p2", 2)
        reg.record_failure("p1", "test")
        reg.record_failure("p1", "test")
        reg.record_failure("p1", "test")
        reg.record_failure("p2", "test")
        reg.record_failure("p2", "test")
        reg.record_failure("p2", "test")
        self.assertTrue(is_provider_chain_broken("test"))

    @patch("src.python.fetcher.chain_config._get_chain")
    def test_partial_skipped(self, mock_chain):
        """仅部分 provider 熔断 → False。"""
        from src.python.fetcher.chain import is_provider_chain_broken
        from src.python.core.provider_registry import get_registry

        mock_chain.return_value = ["p1", "p2"]
        reg = get_registry()
        reg.register_provider("p1", 2)
        reg.register_provider("p2", 2)
        # 仅 p1 触发熔断
        reg.record_failure("p1", "test")
        reg.record_failure("p1", "test")
        reg.record_failure("p1", "test")
        self.assertFalse(is_provider_chain_broken("test"))

    @patch("src.python.fetcher.chain_config._get_chain")
    def test_none_skipped(self, mock_chain):
        """无 provider 熔断 → False。"""
        from src.python.fetcher.chain import is_provider_chain_broken
        from src.python.core.provider_registry import get_registry

        mock_chain.return_value = ["p1", "p2"]
        reg = get_registry()
        reg.register_provider("p1", 2)
        reg.register_provider("p2", 2)
        self.assertFalse(is_provider_chain_broken("test"))

    @patch("src.python.fetcher.chain_config._get_chain")
    def test_empty_chain(self, mock_chain):
        """空链 → True（无可用 provider）。"""
        from src.python.fetcher.chain import is_provider_chain_broken

        mock_chain.return_value = []
        self.assertTrue(is_provider_chain_broken("test"))

    @patch("src.python.fetcher.chain_config._get_chain")
    def test_single_provider_skipped(self, mock_chain):
        """单 provider 链且已熔断 → True。"""
        from src.python.fetcher.chain import is_provider_chain_broken
        from src.python.core.provider_registry import get_registry

        mock_chain.return_value = ["p1"]
        reg = get_registry()
        reg.register_provider("p1", 2)
        reg.record_failure("p1", "test")
        reg.record_failure("p1", "test")
        reg.record_failure("p1", "test")
        self.assertTrue(is_provider_chain_broken("test"))


class TestHistoryIndexChain(unittest.TestCase):
    """history_index Provider Chain 路由测试。"""

    def test_chain_defined(self):
        """_DEFAULT_CHAINS 中包含 history_index，且补入两个独立备源。

        腾讯（主）→ 东方财富 push2his（免 key 独立厂商备源）→ 新浪（代码级备用）
        → 同花顺官方（需 key）。新浪指数端点实测不可用，故东方财富是唯一可用的
        第二源——防止整链退化为事实单源后「抖动即整链空」。
        """
        chain = _get_chain("history_index")
        self.assertEqual(chain, ["tencent", "eastmoney", "sina", "hithink"])
        # 结构性断言：两个免 key 源同列（腾讯 + 东方财富）——守住「非单源」不受链序变动影响
        self.assertLessEqual({"tencent", "eastmoney"}, set(chain))

    def test_history_stock_unaffected(self):
        """history_stock 链固定为三段（腾讯 → 新浪 → 同花顺官方），不被指数链改动波及。"""
        chain = _get_chain("history_stock")
        self.assertEqual(chain, ["tencent", "sina", "hithink"])

    def test_call_history_provider_dispatches_index(self):
        """_call_history_provider("tencent", "history_index", ...) 调用 fetch_index_kline。"""
        mock_mod = MagicMock()
        mock_mod.fetch_index_kline = MagicMock(return_value=[{"date": "2026-07-01", "close": 4000.0}])

        with patch("importlib.import_module", return_value=mock_mod):
            result = _call_history_provider("tencent", "history_index", "sh000300", 30, None)
            self.assertEqual(len(result), 1)
            mock_mod.fetch_index_kline.assert_called_once_with("sh000300", days=30, start_from=None)

    def test_call_history_provider_dispatches_us_index(self):
        """history_index_us 与 history_index 同走 fetch_index_kline。

        回归：该链名此前不在 `_call_history_provider` 的任何分支里，直接落到
        「无 未知函数 函数」告警并恒返回 []——链路看似配了 [sina, tencent]，实际
        一个 provider 都不会被调用。
        """
        mock_mod = MagicMock()
        mock_mod.fetch_index_kline = MagicMock(return_value=[{"date": "2026-07-01", "close": 5000.0}])

        with patch("importlib.import_module", return_value=mock_mod):
            result = _call_history_provider("tencent", "history_index_us", "gb_inx", 30, None)

        self.assertEqual(len(result), 1)
        mock_mod.fetch_index_kline.assert_called_once_with("gb_inx", days=30, start_from=None)

    def test_call_history_provider_stock_unaffected(self):
        """history_stock 仍调用 fetch_kline，不受历史指数分支影响。"""
        mock_mod = MagicMock()
        mock_mod.fetch_kline = MagicMock(return_value=[{"date": "2026-07-01", "close": 25.0}])

        with patch("importlib.import_module", return_value=mock_mod):
            result = _call_history_provider("tencent", "history_stock", "600900", 30, None)
            self.assertEqual(len(result), 1)
            mock_mod.fetch_kline.assert_called_once_with("600900", days=30, start_from=None)

    def test_call_history_provider_fund_unaffected(self):
        """history_fund_otc 仍调用 fetch_fund_nav_history，不受影响。"""
        mock_mod = MagicMock()
        mock_mod.fetch_fund_nav_history = MagicMock(return_value=[{"date": "2026-07-01", "nav": 1.5}])

        with patch("importlib.import_module", return_value=mock_mod):
            result = _call_history_provider("tiantian", "history_fund_otc", "161725", 30, None)
            self.assertEqual(len(result), 1)
            mock_mod.fetch_fund_nav_history.assert_called_once_with("161725")

    def test_call_history_provider_index_unknown_provider(self):
        """history_index 在未知 provider 上 → 返回空列表（不崩溃）。"""
        mock_mod = MagicMock()
        mock_mod.fetch_index_kline = None  # 没有该函数

        with patch("importlib.import_module", return_value=mock_mod):
            result = _call_history_provider("unknown_provider", "history_index", "sh000300", 30, None)
            self.assertEqual(result, [])

    def test_double_failure_returns_empty(self):
        """history_index 全链路失败 → 空列表（不缓存空结果）。"""

        # mock 所有 provider 返回空
        with (
            patch("src.python.fetcher.chain_incremental.cache_get") as mock_cache_get,
            patch("src.python.fetcher.chain_incremental.cache_set") as mock_cache_set,
            patch("src.python.fetcher.chain_incremental._try_providers") as mock_try,
        ):
            mock_cache_get.return_value = []
            mock_try.return_value = []  # 全链路失败

            result = fetch_with_incremental_fallback("history_index", "sh000300", 30)

            self.assertEqual(result, [])
            # 全链失败时不写缓存（空数据不缓存）
            mock_cache_set.assert_not_called()


class TestRunHistoryMemo:
    """单轮窗口复用：同一份报告内多个消费方按不同窗口取同一代码时只取一次。

    实测一轮报告上百次重复历史请求（多窗口 × 多模块），全部重走缓存合并与
    provider 链路；按（chain, code）记住本轮已取到的最大窗口即可消除。
    """

    def _bars(self, n: int, start_day: int = 1) -> list[dict]:
        return [{"date": f"2026-09-{start_day + i:02d}", "close": 100.0 + i} for i in range(n)]

    def test_smaller_window_served_from_memo(self):
        from src.python.fetcher import chain_incremental as ci

        ci.reset_run_history_state()
        bars = self._bars(90)
        with (
            patch.object(ci, "cache_get", return_value=[]),
            patch.object(ci, "cache_set"),
            patch.object(ci, "_try_providers", return_value=bars) as mock_try,
        ):
            assert len(ci.fetch_with_incremental_fallback("history_stock", "600900", 90)) == 90
            # 同代码更小窗口 → 直接截尾，不再取数
            assert len(ci.fetch_with_incremental_fallback("history_stock", "600900", 35)) == 35
            assert mock_try.call_count == 1

    def test_larger_window_refetches_once(self):
        from src.python.fetcher import chain_incremental as ci

        ci.reset_run_history_state()
        small, large = self._bars(30), self._bars(120)
        with (
            patch.object(ci, "cache_get", return_value=[]),
            patch.object(ci, "cache_set"),
            patch.object(ci, "_try_providers", side_effect=[small, large]) as mock_try,
        ):
            assert len(ci.fetch_with_incremental_fallback("history_stock", "601398", 30)) == 30
            assert len(ci.fetch_with_incremental_fallback("history_stock", "601398", 120)) == 120
            # 再要小窗口时已由 120 窗口截尾供给
            assert len(ci.fetch_with_incremental_fallback("history_stock", "601398", 60)) == 60
            assert mock_try.call_count == 2

    def test_reset_clears_memo(self):
        from src.python.fetcher import chain_incremental as ci

        ci.reset_run_history_state()
        with (
            patch.object(ci, "cache_get", return_value=[]),
            patch.object(ci, "cache_set"),
            patch.object(ci, "_try_providers", return_value=[]),
        ):
            ci.fetch_with_incremental_fallback("history_stock", "600900", 90)
        ci.reset_run_history_state()
        assert ci._RUN_HISTORY_MEMO == {}


class TestEmptyResultStreak:
    """结构性不覆盖的 provider（如 hithink 对 A 股历史）连续空结果后本轮不再尝试。"""

    def _run(self, ci, results):
        from unittest.mock import MagicMock

        registry = MagicMock()
        registry.is_circuit_broken.return_value = False
        calls: list[str] = []

        def _call(provider_name, *_a, **_k):
            calls.append(provider_name)
            return results.get(provider_name, [])

        with (
            patch.object(ci, "missing_credential", return_value=None),
            patch.object(ci, "_call_history_provider", side_effect=_call),
        ):
            for code in ("600900", "601398", "601939", "601988", "601288", "601328"):
                ci._try_providers(["hithink"], registry, "history_stock", code, 90, None)
        return calls

    def test_empty_provider_skipped_after_streak(self):
        from src.python.fetcher import chain_incremental as ci

        ci.reset_run_history_state()
        calls = self._run(ci, {"hithink": []})
        # 前 5 次尝试计入 streak，第 6 个代码起直接跳过
        assert len(calls) == ci._EMPTY_STREAK_SKIP

    def test_success_resets_streak(self):
        from src.python.fetcher import chain_incremental as ci

        ci.reset_run_history_state()
        calls = self._run(ci, {"hithink": [{"date": "2026-09-30", "close": 1.0}]})
        assert len(calls) == 6  # 每次都有数据 → 从不跳过
        assert ci._EMPTY_STREAK[("history_stock", "hithink")] == 0


_TEST_CALENDAR = {
    "2026-09-08",
    "2026-09-09",
    "2026-09-10",
    "2026-09-11",
    "2026-09-14",
    "2026-09-15",
    "2026-09-28",
    "2026-09-29",
    "2026-09-30",
    "2026-10-08",
    "2026-10-09",
    "2026-10-12",
}


class TestMissingTradingDays(unittest.TestCase):
    """K 线缺口统计（缺失的交易日数，不含两端）。"""

    def _calendar(self):
        return patch(
            "src.python.core.trading_calendar._get_trading_calendar",
            return_value=_TEST_CALENDAR,
        )

    def test_adjacent_trading_days_no_gap(self):
        """相邻交易日 → 0 个缺失。"""
        with self._calendar():
            self.assertEqual(_missing_trading_days("2026-09-10", "2026-09-11"), 0)

    def test_weekend_not_a_gap(self):
        """周五 → 下周一：跨越周末但无缺失（回归：自然日差为 3）。"""
        with self._calendar():
            self.assertEqual(_missing_trading_days("2026-09-11", "2026-09-14"), 0)

    def test_long_holiday_not_a_gap(self):
        """长假前后相邻交易日：8 个自然日但无缺失（回归：自然日差为 8）。"""
        with self._calendar():
            self.assertEqual(_missing_trading_days("2026-09-30", "2026-10-08"), 0)

    def test_counts_missing_sessions(self):
        """区间内缺失的交易日逐一计数（09-11/09-14/09-15 三个交易日的 K 线缺失）。"""
        with self._calendar():
            self.assertEqual(_missing_trading_days("2026-09-10", "2026-09-28"), 3)

    def test_large_gap_counts_up(self):
        """长区间缺口按交易日累计（用于 >5 交易日告警阈值判定）。"""
        with self._calendar():
            self.assertEqual(_missing_trading_days("2026-09-08", "2026-10-12"), 10)

    def test_invalid_or_missing_dates(self):
        """空值 / 格式非法 / 逆序 → 0（不告警）。"""
        with self._calendar():
            self.assertEqual(_missing_trading_days(None, "2026-09-11"), 0)
            self.assertEqual(_missing_trading_days("2026-09-11", None), 0)
            self.assertEqual(_missing_trading_days("bad", "2026-09-11"), 0)
            self.assertEqual(_missing_trading_days("2026-09-11", "2026-09-10"), 0)


class TestProviderEmptyReasonSurfaced(unittest.TestCase):
    """provider 通过 ``_utils.set_last_reason`` 自陈原因时，链路日志与诊断原因如实透传。

    回归：``返回空`` 把「源故障」与「该文档确实没这一节」混为一谈——前者要排查网络/凭据，
    后者是正常业务结果（实测：DataSinking 对没有「管理层讨论与分析」的季报返回 404，
    日志只记「返回空」，排查时被误读为源不可用）。
    """

    def tearDown(self):
        from src.python.providers.utils import take_last_reason

        take_last_reason()  # 清残留，避免污染同进程其他用例

    def test_custom_reason_used_in_log_and_diag(self):
        from src.python.providers.utils import set_last_reason

        def _fn(**_kw):
            set_last_reason("该文档无「管理层讨论与分析」章节")
            return None

        with patch.object(chain.logger, "info") as mock_info:
            result, reason = chain._try_provider_fetch(
                "financial_report", "datasink", "DataSinking", _fn, {}, None, None
            )
        self.assertIsNone(result)
        self.assertEqual(reason, "该文档无「管理层讨论与分析」章节")
        self.assertTrue(
            any("该文档无「管理层讨论与分析」章节" in str(c.args) for c in mock_info.call_args_list),
            "链路日志须带上 provider 自陈的原因",
        )

    def test_default_reason_when_provider_silent(self):
        """provider 未自陈原因 → 保持既有「返回空」措辞（行为逐字不变）。"""
        with patch.object(chain.logger, "info"):
            result, reason = chain._try_provider_fetch(
                "financial_report", "datasink", "DataSinking", lambda **_kw: None, {}, None, None
            )
        self.assertIsNone(result)
        self.assertEqual(reason, "返回空")


class TestDocIdLogTag(unittest.TestCase):
    """失败日志定位标识：无 code 的链路（财报 doc 维度）以 doc_id 入日志。"""

    def test_full_chain_failure_log_carries_doc_id(self):
        """fn_kwargs 无 code 时以 doc_id 定位：全链路失败日志带 [doc_id]，可反查文档。"""
        provider_map = {"fake": ("FakeSource", lambda **_kw: None)}

        with self.assertLogs(chain.logger, level="WARNING") as cm:
            result = chain.fetch_with_fallback(
                "financial_report",
                provider_map,
                "ut_doc_tag_cache_key",
                60.0,
                fn_kwargs={"doc_id": "999001"},
            )

        self.assertIsNone(result)
        self.assertTrue(any("[999001]" in m for m in cm.output), "\n".join(cm.output))

    def test_code_takes_precedence_over_doc_id(self):
        """code 与 doc_id 同在时以 code 优先（有 code 的链路日志语义不变）。"""
        provider_map = {"fake": ("FakeSource", lambda **_kw: None)}

        with self.assertLogs(chain.logger, level="WARNING") as cm:
            result = chain.fetch_with_fallback(
                "financial_report",
                provider_map,
                "ut_doc_tag_cache_key_2",
                60.0,
                fn_kwargs={"code": "600000", "doc_id": "999001"},
            )

        self.assertIsNone(result)
        joined = "\n".join(cm.output)
        self.assertIn("[600000]", joined)
        self.assertNotIn("[999001]", joined)


if __name__ == "__main__":
    unittest.main()
