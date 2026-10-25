"""fetcher/fund.py 单元测试。

测试目标：
  - _get_full_benchmark_table 内置库合并
  - _get_benchmark_lock 锁管理
  - _fetch_benchmark_from_api HTML 解析/异常
  - fetch_fund_benchmark 三层策略

运行：
  pytest src/test/unit/fetcher/test_fund.py -v
"""

from __future__ import annotations

import threading
import unittest
from unittest import mock
from unittest.mock import MagicMock, patch

from src.python.fetcher.fund import (
    _BUILTIN_BENCHMARKS,
    _get_benchmark_lock,
    _get_full_benchmark_table,
    fetch_fund_benchmark,
)
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher]


class TestGetFullBenchmarkTable(unittest.TestCase):
    """_get_full_benchmark_table：内置库 + config 合并"""

    def test_returns_builtin_benchmarks(self):
        """无 config 覆盖时返回内置库副本。"""
        with patch("src.python.fetcher.fund.get_config", return_value={}):
            table = _get_full_benchmark_table()
        self.assertEqual(table, _BUILTIN_BENCHMARKS)
        # 确保是副本，修改不影响原字典
        table.clear()
        self.assertTrue(_BUILTIN_BENCHMARKS)  # 原字典不受影响

    def test_merges_user_overrides(self):
        """config.json 的 user_fund_benchmarks 覆盖内置库。"""
        overrides = {"561910": "自定义基准", "999999": "新基金基准"}
        with patch("src.python.fetcher.fund.get_config", return_value={"user_fund_benchmarks": overrides}):
            table = _get_full_benchmark_table()
        self.assertEqual(table["561910"], "自定义基准")  # 覆盖
        self.assertEqual(table["999999"], "新基金基准")  # 新增
        self.assertEqual(table["159941"], "汇率调整后的纳斯达克100指数收益率")  # 未覆盖保留

    def test_handles_none_user_benchmarks(self):
        """user_fund_benchmarks 为 None 时不崩溃（由 or {} 兜底）。"""
        with patch("src.python.fetcher.fund.get_config", return_value={"user_fund_benchmarks": None}):
            table = _get_full_benchmark_table()
        self.assertEqual(table, _BUILTIN_BENCHMARKS)

    def test_handles_config_exception(self):
        """get_config 抛出异常时回退到内置库。"""
        with patch("src.python.fetcher.fund.get_config", side_effect=KeyError("test")):
            table = _get_full_benchmark_table()
        self.assertEqual(table, _BUILTIN_BENCHMARKS)


class TestGetBenchmarkLock(unittest.TestCase):
    """_get_benchmark_lock：per-code 锁管理"""

    def tearDown(self):
        _benchmark_locks = {}  # 清理全局状态
        import src.python.fetcher.fund as _fm

        _fm._benchmark_locks.clear()

    def test_creates_lock_on_first_access(self):
        """首次访问创建新锁。"""
        lock = _get_benchmark_lock("123456")
        # 跨 Python 版本兼容检查：type(threading.Lock()) 而非 threading.Lock（3.10 平台差异）
        self.assertIsInstance(lock, type(threading.Lock()))

    def test_reuses_existing_lock(self):
        """同一 code 返回同一锁对象。"""
        lock1 = _get_benchmark_lock("123456")
        lock2 = _get_benchmark_lock("123456")
        self.assertIs(lock1, lock2)

    def test_different_codes_get_different_locks(self):
        """不同 code 返回不同锁对象。"""
        lock1 = _get_benchmark_lock("111111")
        lock2 = _get_benchmark_lock("222222")
        self.assertIsNot(lock1, lock2)


class TestFetchBenchmarkFromApi(unittest.TestCase):
    """_fetch_benchmark_from_api：HTML 解析"""

    def _make_html(self, body: str) -> str:
        return f"<!DOCTYPE html><html><head></head><body>{body}</body></html>"

    @patch("src.python.fetcher.fund.make_http_client")
    def test_finds_benchmark_in_html(self, mock_factory):
        """从 HTML 中正确提取业绩比较基准。"""
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_factory.return_value = mock_client

        resp = MagicMock()
        resp.text = self._make_html("业绩比较基准：沪深300指数收益率×80%+中证全债×20%")
        mock_client.get.return_value = resp

        from src.python.fetcher.fund import _fetch_benchmark_from_api

        result = _fetch_benchmark_from_api("000000")
        self.assertIsNotNone(result)
        self.assertIn("沪深300", result)
        self.assertIn("中证全债", result)

    @patch("src.python.fetcher.fund.make_http_client")
    def test_finds_benchmark_with_colon_variant(self, mock_factory):
        """处理中文冒号「：」的业绩比较基准。"""
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_factory.return_value = mock_client

        resp = MagicMock()
        resp.text = self._make_html("业绩比较基准:沪深300指数收益率")
        mock_client.get.return_value = resp

        from src.python.fetcher.fund import _fetch_benchmark_from_api

        result = _fetch_benchmark_from_api("000000")
        self.assertEqual(result, "沪深300指数收益率")

    @patch("src.python.fetcher.fund.make_http_client")
    def test_finds_benchmark_in_script(self, mock_factory):
        """从 script 标签中提取基准"""
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_factory.return_value = mock_client

        resp = MagicMock()
        resp.text = self._make_html('<script>var data = {benchmark: "中证500指数"}; var 基准: 沪深300指数</script>')
        mock_client.get.return_value = resp

        from src.python.fetcher.fund import _fetch_benchmark_from_api

        result = _fetch_benchmark_from_api("000000")
        self.assertIsNotNone(result)

    @patch("src.python.fetcher.fund.make_http_client")
    def test_returns_none_on_no_match(self, mock_factory):
        """无匹配文本时返回 None。"""
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_factory.return_value = mock_client

        resp = MagicMock()
        resp.text = self._make_html("<p>没有基准信息</p>")
        mock_client.get.return_value = resp

        from src.python.fetcher.fund import _fetch_benchmark_from_api

        result = _fetch_benchmark_from_api("000000")
        self.assertIsNone(result)

    @patch("src.python.fetcher.fund.make_http_client")
    def test_handles_http_error(self, mock_factory):
        """HTTP 请求异常时返回 None。"""
        import httpx as _httpx_loc

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_factory.return_value = mock_client

        mock_client.get.side_effect = _httpx_loc.RequestError("timeout")

        from src.python.fetcher.fund import _fetch_benchmark_from_api

        result = _fetch_benchmark_from_api("000000")
        self.assertIsNone(result)

    @patch("src.python.fetcher.fund.make_http_client")
    def test_tries_multiple_urls(self, mock_factory):
        """第一个 URL 失败时尝试第二个 URL。"""
        import httpx as _httpx_loc

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_factory.return_value = mock_client

        # 第一个 URL 超时，第二个返回有效
        resp = MagicMock()
        resp.text = self._make_html("业绩比较基准：中证全债指数")
        mock_client.get.side_effect = [
            _httpx_loc.RequestError("timeout"),
            resp,
        ]

        from src.python.fetcher.fund import _fetch_benchmark_from_api

        result = _fetch_benchmark_from_api("000000")
        self.assertEqual(result, "中证全债指数")


class TestFetchFundBenchmark(unittest.TestCase):
    """fetch_fund_benchmark：三层策略集成"""

    def tearDown(self):
        import src.python.fetcher.fund as _fm

        _fm._benchmark_locks.clear()

    @patch("src.python.fetcher.fund.cache_get")
    def test_returns_from_cache(self, mock_cache_get):
        """缓存命中时直接返回。"""
        mock_cache_get.return_value = {"000000": "缓存基准"}
        result = fetch_fund_benchmark("000000")
        self.assertEqual(result, "缓存基准")

    @patch("src.python.fetcher.fund.cache_get")
    def test_returns_dash_for_missing_code_in_cache(self, mock_cache_get):
        """缓存命中但 code 不在表中时返回 '--'。"""
        mock_cache_get.return_value = {"111111": "某基准"}
        result = fetch_fund_benchmark("000000")
        self.assertEqual(result, "--")

    @patch("src.python.fetcher.fund.cache_get")
    @patch("src.python.fetcher.fund.cache_set")
    @patch("src.python.fetcher.fund._fetch_benchmark_from_api")
    def test_uses_api_result_when_cache_misses(
        self,
        mock_api,
        mock_set,
        mock_get,
    ):
        """缓存未命中且 API 成功时，基准来自 API 并写入缓存表。"""
        mock_get.return_value = None
        mock_get.return_value = None  # 双重检查锁
        mock_api.return_value = "沪深300"

        result = fetch_fund_benchmark("000000")
        self.assertEqual(result, "沪深300")
        mock_set.assert_called_once()
        table = mock_set.call_args[0][1]
        self.assertIn("000000", table)

    @patch("src.python.fetcher.fund.cache_get")
    @patch("src.python.fetcher.fund.cache_set")
    @patch("src.python.fetcher.fund._fetch_benchmark_from_api")
    def test_falls_back_to_builtin_when_api_fails(
        self,
        mock_api,
        mock_set,
        mock_get,
    ):
        """API 失败时使用内置知识库。"""
        mock_get.return_value = None
        mock_api.return_value = None  # API 失败

        result = fetch_fund_benchmark("561910")  # 内置库有
        self.assertEqual(result, "中证电池主题指数收益率")

    @patch("src.python.fetcher.fund.cache_get")
    @patch("src.python.fetcher.fund.cache_set")
    @patch("src.python.fetcher.fund._fetch_benchmark_from_api")
    def test_returns_dash_when_all_layers_fail(
        self,
        mock_api,
        mock_set,
        mock_get,
    ):
        """全部三层失败时返回 '--'。"""
        mock_get.return_value = None
        mock_api.return_value = None  # API 失败

        result = fetch_fund_benchmark("000000")  # 内置库也没有
        self.assertEqual(result, "--")

    @patch("src.python.fetcher.fund.cache_get")
    @patch("src.python.fetcher.fund.cache_set")
    @patch("src.python.fetcher.fund._fetch_benchmark_from_api")
    def test_double_check_locking(self, mock_api, mock_set, mock_get):
        """双重检查锁：只有第一个进入的线程调 API，第二个线程复用结果。"""
        # 用 Event 控制：API 调用前 cache_get 返回 None，调用后返回有效数据
        api_called = threading.Event()

        def _side(*args, **kwargs):
            # 第 1 次调用（任意线程首次检查）：返回 None → 进入锁
            if not api_called.is_set():
                return None
            # API 已调用后：返回有效数据（模拟缓存生效）
            return {"000000": "沪深300"}

        mock_get.side_effect = _side
        mock_api.side_effect = lambda code: api_called.set() or "沪深300"

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(fetch_fund_benchmark, "000000")
            f2 = ex.submit(fetch_fund_benchmark, "000000")
            r1 = f1.result()
            r2 = f2.result()

        self.assertEqual(r1, "沪深300")
        self.assertEqual(r2, "沪深300")
        # API 仅调用一次（锁+双重检查确保）
        self.assertEqual(mock_api.call_count, 1)


if __name__ == "__main__":
    unittest.main()


# ═══════════════════════════════════════════════════════════
#  批量接口测试
# ═══════════════════════════════════════════════════════════


class TestFetchFundRankingsBatch(unittest.TestCase):
    """fetch_fund_rankings_batch 批量并行获取。"""

    def test_empty_list_returns_empty_dict(self):
        """空列表 → 空 dict。"""
        from src.python.fetcher.fund import fetch_fund_rankings_batch

        result = fetch_fund_rankings_batch([])
        self.assertEqual(result, {})

    @patch("src.python.fetcher.batch.BatchDispatcher")
    def test_single_fund(self, mock_dispatcher_cls):
        """单基金返回正确映射。"""
        mock_disp = MagicMock()
        mock_disp.execute_with_cache_check.return_value = [
            type("R", (), {"success": True, "result": {"rank": 1}})(),
        ]
        mock_dispatcher_cls.return_value = mock_disp

        from src.python.fetcher.fund import fetch_fund_rankings_batch

        result = fetch_fund_rankings_batch(["000001"])
        self.assertIn("000001", result)
        self.assertEqual(result["000001"]["rank"], 1)

    @patch("src.python.fetcher.batch.BatchDispatcher")
    def test_partial_failures(self, mock_dispatcher_cls):
        """部分失败 → 缺失项为 None。"""
        mock_disp = MagicMock()
        mock_disp.execute_with_cache_check.return_value = [
            type("R", (), {"success": True, "result": {"rank": 1}})(),
            type("R", (), {"success": False, "result": None, "error": "err"})(),
            type("R", (), {"success": True, "result": {"rank": 3}})(),
        ]
        mock_dispatcher_cls.return_value = mock_disp

        from src.python.fetcher.fund import fetch_fund_rankings_batch

        result = fetch_fund_rankings_batch(["000001", "000002", "000003"])
        self.assertIsNotNone(result["000001"])
        self.assertIsNone(result["000002"])
        self.assertIsNotNone(result["000003"])

    @patch("src.python.fetcher.batch.BatchDispatcher")
    def test_uses_cache_check(self, mock_dispatcher_cls):
        """使用 execute_with_cache_check（非 execute）。"""
        mock_disp = MagicMock()
        mock_disp.execute_with_cache_check.return_value = []
        mock_dispatcher_cls.return_value = mock_disp

        from src.python.fetcher.fund import fetch_fund_rankings_batch

        fetch_fund_rankings_batch(["000001"])
        mock_disp.execute_with_cache_check.assert_called_once()

    def test_external_dispatcher_no_shutdown(self):
        """传入外部 dispatcher 时不 shutdown。"""
        from unittest.mock import MagicMock

        mock_disp = MagicMock()
        mock_disp.execute_with_cache_check.return_value = [
            type("R", (), {"success": True, "result": {"rank": 1}})(),
        ]

        from src.python.fetcher.fund import fetch_fund_rankings_batch

        result = fetch_fund_rankings_batch(["000001"], dispatcher=mock_disp)
        self.assertIn("000001", result)
        mock_disp.shutdown.assert_not_called()


class TestFetchFundHoldingsBatch(unittest.TestCase):
    """fetch_fund_holdings_batch 批量并行获取。"""

    def test_empty_list_returns_empty_dict(self):
        """空列表 → 空 dict。"""
        from src.python.fetcher.fund import fetch_fund_holdings_batch

        result = fetch_fund_holdings_batch([])
        self.assertEqual(result, {})

    @patch("src.python.fetcher.batch.BatchDispatcher")
    def test_uses_cache_check_method(self, mock_dispatcher_cls):
        """使用 execute_with_cache_check（缓存优先）。"""
        mock_disp = MagicMock()
        mock_disp.execute_with_cache_check.return_value = [
            type("R", (), {"success": True, "result": {"holdings": []}})(),
        ]
        mock_dispatcher_cls.return_value = mock_disp

        from src.python.fetcher.fund import fetch_fund_holdings_batch

        result = fetch_fund_holdings_batch(["000001"])
        self.assertEqual(len(result), 1)

    @patch("src.python.fetcher.batch.BatchDispatcher")
    def test_partial_failures(self, mock_dispatcher_cls):
        """部分失败 → 缺失项为 None。"""
        mock_disp = MagicMock()
        mock_disp.execute_with_cache_check.return_value = [
            type("R", (), {"success": True, "result": {"holdings": []}})(),
            type("R", (), {"success": False, "result": None, "error": "err"})(),
        ]
        mock_dispatcher_cls.return_value = mock_disp

        from src.python.fetcher.fund import fetch_fund_holdings_batch

        result = fetch_fund_holdings_batch(["000001", "000002"])
        self.assertIsNotNone(result["000001"])
        self.assertIsNone(result["000002"])

    def test_calls_fetch_fund_holdings_cached_internally(self):
        """内部使用 fetch_fund_holdings_cached（含 session_cache）。"""
        from src.python.fetcher.fund import fetch_fund_holdings_batch

        # Verify the batch function uses the cached variant
        import inspect

        # Check that the source references fetch_fund_holdings_cached
        src = inspect.getsource(fetch_fund_holdings_batch)
        self.assertIn("fetch_fund_holdings_cached", src)

    @patch("src.python.fetcher.fund.fetch_fund_holdings_cached")
    @patch("src.python.fetcher.batch.BatchDispatcher")
    def test_penetration_applied_on_cache_hit(self, mock_dispatcher_cls, mock_cached):
        """**缓存预检命中**时穿透仍须生效。

        回归防线：``execute_with_cache_check`` 命中文件缓存会直接返回缓存值而
        **不执行任务**（无网络、无 provider 调用），若穿透只挂在单条取数链路内，
        缓存一热就整段被跳过——修复只在冷缓存下有效。本用例模拟该命中路径
        （result 由 dispatcher 直接给出，任务未跑），断言穿透在后处理处补做。
        """
        mock_disp = MagicMock()
        mock_disp.execute_with_cache_check.return_value = [
            type(
                "R",
                (),
                {
                    "success": True,
                    "result": {"code": "016055", "name": "某联接基金", "holdings": [], "feeder_target_code": "513390"},
                },
            )(),
        ]
        mock_dispatcher_cls.return_value = mock_disp
        mock_cached.return_value = {
            "code": "513390",
            "name": "纳指100ETF博时",
            "date": "2026-06-30",
            "holdings": [{"name": "苹果", "code": "AAPL", "ratio": 9.0}],
        }

        from src.python.fetcher.fund import fetch_fund_holdings_batch

        result = fetch_fund_holdings_batch(["016055"])

        entry = result["016055"]
        self.assertEqual(entry["code"], "016055")
        self.assertEqual(entry["feeder_penetration"]["target_code"], "513390")
        self.assertEqual(len(entry["holdings"]), 1)


class TestWithFeederPenetration(unittest.TestCase):
    """with_feeder_penetration — 联接基金以目标 ETF 的持仓代理底层暴露。

    必须是**幂等**的后处理：单条取数与批量两条路径都要过一遍，重复调用无副作用。
    """

    _FEEDER = {"code": "016055", "name": "某联接基金", "date": "", "holdings": [], "feeder_target_code": "513390"}
    _TARGET = {
        "code": "513390",
        "name": "纳指100ETF博时",
        "date": "2026-06-30",
        "holdings": [{"name": "苹果", "code": "AAPL", "ratio": 9.0}],
    }

    def test_none_result_passthrough(self):
        from src.python.fetcher.fund import with_feeder_penetration

        self.assertIsNone(with_feeder_penetration("016055", None))

    def test_non_feeder_passthrough(self):
        """非联接基金（无目标 ETF）原样返回。"""
        from src.python.fetcher.fund import with_feeder_penetration

        plain = {"code": "110022", "name": "易方达消费行业", "date": "2026-06-30", "holdings": [{"name": "贵州茅台"}]}
        self.assertIs(with_feeder_penetration("110022", plain), plain)

    def test_idempotent(self):
        """已穿透的结果原样返回（不重复取目标 ETF、不覆盖来源标注）。"""
        from src.python.fetcher.fund import with_feeder_penetration

        done = {
            **self._TARGET,
            "code": "016055",
            "feeder_penetration": {"target_code": "513390", "target_name": "纳指100ETF博时"},
        }
        with patch("src.python.fetcher.fund.fetch_fund_holdings_cached") as mock_cached:
            self.assertIs(with_feeder_penetration("016055", done), done)
        mock_cached.assert_not_called()

    @patch("src.python.fetcher.fund.fetch_fund_holdings_cached")
    def test_penetrates_and_labels_source(self, mock_cached):
        """穿透后保留本基金代码/名称，并记录目标 ETF 供报告层标注来源。"""
        from src.python.fetcher.fund import with_feeder_penetration

        mock_cached.return_value = self._TARGET
        result = with_feeder_penetration("016055", dict(self._FEEDER))

        self.assertEqual(result["code"], "016055")
        self.assertEqual(result["name"], "某联接基金")
        self.assertEqual(result["date"], "2026-06-30")
        self.assertEqual(result["holdings"], self._TARGET["holdings"])
        self.assertEqual(result["feeder_penetration"], {"target_code": "513390", "target_name": "纳指100ETF博时"})

    @patch("src.python.fetcher.fund.fetch_fund_holdings_cached")
    def test_target_unavailable_returns_original(self, mock_cached):
        """目标 ETF 亦取不到时原样返回，交由既有「持仓不可用」路径降级。"""
        from src.python.fetcher.fund import with_feeder_penetration

        mock_cached.return_value = None
        result = with_feeder_penetration("016055", dict(self._FEEDER))
        self.assertEqual(result["holdings"], [])
        self.assertNotIn("feeder_penetration", result)

    @patch("src.python.fetcher.fund.fetch_fund_holdings_cached")
    def test_target_without_holdings_returns_original(self, mock_cached):
        """目标 ETF 有响应但持仓为空，同样不产生穿透结果。"""
        from src.python.fetcher.fund import with_feeder_penetration

        mock_cached.return_value = {"code": "513390", "name": "纳指100ETF博时", "date": "", "holdings": []}
        result = with_feeder_penetration("016055", dict(self._FEEDER))
        self.assertNotIn("feeder_penetration", result)

    @patch("src.python.fetcher.fund.fetch_fund_holdings_cached")
    def test_penetrates_unconditionally(self, mock_cached):
        """穿透内置恒开：不受任何功能开关影响（防开关分支回潮回归）。

        缺陷场景：本函数早期以 `feeder_penetration` 开关把关，置 false 即穿透
        整体失效（联接基金底层暴露恒空）。开关已移除——即便把全仓开关置为
        False，穿透照常发生。
        """
        from src.python.fetcher.fund import with_feeder_penetration

        mock_cached.return_value = self._TARGET
        with patch("src.python.config.features.is_feature_enabled", return_value=False):
            result = with_feeder_penetration("016055", dict(self._FEEDER))
        self.assertIn("feeder_penetration", result)
        mock_cached.assert_called_once()


class TestHithinkHoldingsNormalization(unittest.TestCase):
    """同花顺披露持仓 → 规范化持仓契约（阶段 3 两源链的备源归一）。"""

    def _hithink_raw(self, **extra):
        raw = {
            "_thscode": "011506.OF",
            "total_stock_ratio_pct": 57.7,
            "timestamp": 0,
            "item": [
                {"ticker": "688200", "stock_name": "华峰测控", "hold_ratio": 9.53, "asset_type": "stock"},
                {"ticker": "300308", "stock_name": "中际旭创", "hold_ratio": 7.39, "asset_type": "stock"},
                # 债券/基金资产必须被剔除：穿透层是股票层，混入会污染占比分母
                {"ticker": "2120089", "stock_name": "21北京银行永续债01", "hold_ratio": 4.94, "asset_type": "bond"},
                {"ticker": "513390", "stock_name": "博时纳斯达克100ETF", "hold_ratio": 93.5, "asset_type": "fund"},
                {"ticker": "999999", "stock_name": "无占比项", "hold_ratio": None, "asset_type": "stock"},
                {"ticker": "888888", "stock_name": "超限项", "hold_ratio": 120.0, "asset_type": "stock"},
            ],
            "end_date_ms": 1782748800000,
        }
        raw.update(extra)
        return raw

    def test_maps_items_to_canonical_holdings(self):
        from src.python.fetcher.fund import _normalize_hold_payload

        out = _normalize_hold_payload(self._hithink_raw(), "同花顺金融数据")
        self.assertEqual([h["code"] for h in out["holdings"]], ["688200", "300308"])
        self.assertEqual(out["holdings"][0], {"name": "华峰测控", "code": "688200", "ratio": 9.53})
        self.assertEqual(out["date"], "2026-06-30")  # end_date_ms → YYYY-MM-DD（Asia/Shanghai）
        self.assertEqual(out["name"], "")  # 上游该端点不提供基金名

    def test_publish_date_fallback_and_invalid_ts(self):
        from src.python.fetcher.fund import _normalize_hold_payload

        pub = _normalize_hold_payload(self._hithink_raw(end_date_ms=None, publish_date_ms=1782748800000))
        self.assertEqual(pub["date"], "2026-06-30")
        bad = _normalize_hold_payload(self._hithink_raw(end_date_ms=None, publish_date_ms="bad"))
        self.assertEqual(bad["date"], "")

    def test_feeder_target_code_preserved(self):
        """联接基金：provider 带回的目标 ETF 代码必须原样保留（既有穿透链路依赖它）。"""
        from src.python.fetcher.fund import _normalize_hold_payload

        out = _normalize_hold_payload(self._hithink_raw(feeder_target_code="513390"), "同花顺金融数据")
        self.assertEqual(out["feeder_target_code"], "513390")

    def test_tiantian_shape_passes_through_unchanged(self):
        """主源（天天基金）形态逐字透传——保证主源可用时输出不变。"""
        from src.python.fetcher.fund import _normalize_hold_payload

        raw = {
            "code": "011506",
            "name": "建信高端装备股票A",
            "date": "2026-03-31",
            "holdings": [{"name": "x", "code": "1", "ratio": 1.0}],
        }
        out = _normalize_hold_payload(raw, "天天基金")
        self.assertEqual(out, raw)


class TestFundHoldProviderChain(unittest.TestCase):
    """两源链：天天基金为主、同花顺官方源为备（顺序即链路顺序）。"""

    def test_provider_order_and_identity(self):
        from src.python.fetcher.fund import _FUND_HOLD_PROVIDERS

        self.assertEqual(list(_FUND_HOLD_PROVIDERS), ["tiantian", "hithink"])
        self.assertEqual(_FUND_HOLD_PROVIDERS["hithink"][0], "同花顺金融数据")
        self.assertTrue(callable(_FUND_HOLD_PROVIDERS["hithink"][1]))

    def test_hithink_used_when_tiantian_fails(self):
        """主源返回空 → 链路切到同花顺备源并归一为规范形态。"""
        from src.python.fetcher import fund as fund_mod

        calls: list[tuple[str, str]] = []

        def _tia(code):
            calls.append(("tiantian", code))
            return None

        def _hit(code):
            calls.append(("hithink", code))
            return {
                "_thscode": "561910.SH",
                "item": [{"ticker": "300274", "stock_name": "阳光电源", "hold_ratio": 10.19, "asset_type": "stock"}],
                "end_date_ms": 1782748800000,
            }

        with (
            mock.patch.dict(
                fund_mod._FUND_HOLD_PROVIDERS,
                {"tiantian": ("天天基金", _tia), "hithink": ("同花顺金融数据", _hit)},
            ),
            mock.patch("src.python.fetcher.chain.cache_get", return_value=None),
            mock.patch("src.python.fetcher.chain.cache_set"),
            # 同花顺为需凭据源：测试环境无 key，显式放行凭据预检，否则备源会被跳过
            mock.patch("src.python.fetcher.chain.missing_credential", return_value=None),
            mock.patch.object(fund_mod, "with_feeder_penetration", side_effect=lambda _c, r: r),
        ):
            out = fund_mod.fetch_fund_holdings("561910")

        self.assertEqual([c[0] for c in calls], ["tiantian", "hithink"])
        self.assertEqual(out["holdings"][0]["name"], "阳光电源")
        self.assertEqual(out["date"], "2026-06-30")


class TestHoldPayloadShapeAdmission(unittest.TestCase):
    """``fund_hold_*`` 载荷的**形状**准入（版本字段已随缓存键版本整体作废机制移除）。

    载荷语义变更由缓存键版本号（``_CACHE_KEY_VERSION``）整体作废旧条目，
    不再为单个数据类型维护 ``*_schema`` 字段；此处只锁「形状不合即视为未命中」。
    """

    def test_normalize_does_not_stamp_schema(self):
        """归一化只产出规范契约，不再盖版本字段。"""
        from src.python.fetcher.fund import _normalize_hold_payload

        out = _normalize_hold_payload(
            {"code": "016055", "name": "某基金", "date": "2026-03-31", "holdings": []}, "天天基金"
        )
        self.assertNotIn("hold_schema", out)
        self.assertEqual(out["code"], "016055")

    def test_shape_admission(self):
        """含 ``holdings`` 列表的 dict 才准入；空壳/非 dict 一律拒收。"""
        from src.python.fetcher.fund import _is_current_hold_payload

        self.assertTrue(_is_current_hold_payload({"code": "016055", "holdings": []}))
        self.assertFalse(_is_current_hold_payload({"code": "016055"}))
        self.assertFalse(_is_current_hold_payload({"holdings": "broken"}))
        self.assertFalse(_is_current_hold_payload(None))

    def test_shape_ok_cached_payload_returns_without_refetch(self):
        """形状合规的缓存条目 → 直接命中，不调 provider。"""
        from src.python.fetcher import fund as fm

        cached = {
            "code": "016055",
            "name": "某联接基金",
            "date": "2026-06-30",
            "holdings": [{"name": "苹果", "code": "AAPL", "ratio": 9.0}],
        }
        provider = MagicMock(return_value={"code": "016055", "holdings": []})

        with (
            patch("src.python.fetcher.chain.cache_get", return_value=cached),
            patch.dict(fm._FUND_HOLD_PROVIDERS, {"tiantian": ("天天基金", provider)}),
            patch("src.python.fetcher.fund.with_feeder_penetration", side_effect=lambda _c, r: r),
        ):
            result = fm.fetch_fund_holdings("016055")

        provider.assert_not_called()
        self.assertEqual(result["holdings"], cached["holdings"])

    @patch("src.python.fetcher.batch.BatchDispatcher")
    def test_batch_cache_check_uses_shape(self, mock_dispatcher_cls):
        """批量预检按形状判定：空壳载荷视为未命中，合规载荷直接返回。"""
        from src.python.fetcher import fund as fm

        captured: dict = {}
        mock_disp = MagicMock()

        def _fake_exec(items, cache_check_fn, **_kw):
            captured["fn"] = cache_check_fn
            return [type("R", (), {"success": True, "result": {"holdings": []}})()]

        mock_disp.execute_with_cache_check.side_effect = _fake_exec
        mock_dispatcher_cls.return_value = mock_disp

        with patch("src.python.fetcher.fund.cache_get", return_value={"code": "016055"}):
            fm.fetch_fund_holdings_batch(["016055"])
            self.assertIsNone(captured["fn"]("fund_hold_016055"))

        current = {"code": "016055", "holdings": []}
        with patch("src.python.fetcher.fund.cache_get", return_value=current):
            fm.fetch_fund_holdings_batch(["016055"])
            self.assertEqual(captured["fn"]("fund_hold_016055"), current)
