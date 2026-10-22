"""测试：端到端性能基准 — test-perf-report.py

覆盖：
  - `_generate_holdings`：股票按请求量取样、场外基金全量追加；样本池覆盖 Phase3 目标量
  - `_sample_of`：按账户口径分列（港股非 6 位代码仍计为股票，不按代码位数误判）
  - `_verdict`：达标/超标边界（≤ 目标值即达标）
  - 报告文案：测试时间随运行时刻动态生成（解析回读、与当前时刻比对）；
    持仓规模按实际数量派生（文案 = 传入样本规模，不写死）
  - LLM mock：patch 目标为包属性（与 `_llm_news` 函数内 import 解析点一致），
    mock 返回值结构与收集器消费契约同构

测试通过脚本 import 方式直接复用，不运行真实 CLI 进程、不执行真实性能基准。
"""

from __future__ import annotations

import ast
import importlib
import inspect
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from src.test._script_loader import load_script


pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
    pytest.mark.usefixtures("offline_external_sources"),
]


@pytest.fixture(scope="module")
def perf_test_report():
    return load_script("test-perf-report.py")


@pytest.fixture()
def report_path(tmp_path, monkeypatch, perf_test_report):
    """把报告输出重定向到临时目录，测试不得写入 docs/tmp。"""
    path = tmp_path / "perf.md"
    monkeypatch.setattr(perf_test_report, "_PERF_REPORT_PATH", str(path))
    return path


def _timings() -> dict:
    return {
        "data_generation": 0.5,
        "phase1_basic_excel": 12.0,
        "phase2_both_html_excel": 25.0,
        "phase3_stress_large": 40.0,
    }


class TestGenerateHoldings:
    """样本规模：请求量 → 实际生成量的关系（含样本池上限）。"""

    def test_stock_count_plus_all_funds(self, perf_test_report):
        count = perf_test_report._PHASE1_STOCK_COUNT
        holdings = perf_test_report._generate_holdings(count)
        stock_part = holdings[: len(perf_test_report.SAMPLE_STOCKS[:count])]
        assert len(holdings) == count + len(perf_test_report.SAMPLE_FUNDS)
        assert all(h.account == "证券账户" for h in stock_part)
        assert all(h.account == "基金账户" for h in holdings[len(stock_part) :])

    def test_phase3_target_covered_by_sample_pool(self, perf_test_report):
        """Phase3 请求量必须被样本池覆盖（否则 [:N] 静默截断、文案与实际不符）。"""
        assert len(perf_test_report.SAMPLE_STOCKS) >= perf_test_report._PHASE3_STOCK_COUNT
        holdings = perf_test_report._generate_holdings(perf_test_report._PHASE3_STOCK_COUNT)
        sample = perf_test_report._sample_of(holdings)
        assert sample.stocks == perf_test_report._PHASE3_STOCK_COUNT
        assert sample.holdings == perf_test_report._PHASE3_STOCK_COUNT + len(perf_test_report.SAMPLE_FUNDS)

    def test_request_over_pool_is_clamped_to_pool(self, perf_test_report):
        """请求量超过样本池 → 以池大小为上限（文档化的实际语义）。"""
        over = len(perf_test_report.SAMPLE_STOCKS) + 10
        holdings = perf_test_report._generate_holdings(over)
        assert len(holdings) == len(perf_test_report.SAMPLE_STOCKS) + len(perf_test_report.SAMPLE_FUNDS)

    def test_stock_and_fund_names_distinct(self, perf_test_report):
        holdings = perf_test_report._generate_holdings(perf_test_report._PHASE1_STOCK_COUNT)
        names = [h.name for h in holdings]
        assert len(names) == len(set(names)), "样本名重复会让去重/覆盖类逻辑测不到"


class TestSampleOf:
    """样本规模统计：账户口径分类（代码位数会把港股误计为基金）。"""

    def test_counts_by_account_not_code_length(self, perf_test_report):
        holdings = perf_test_report._generate_holdings(perf_test_report._PHASE3_STOCK_COUNT)
        hk_stocks = [h for h in holdings if len(h.code) != 6]
        assert hk_stocks, "样本池应含港股（非 6 位代码），否则该分类分支测不到"
        sample = perf_test_report._sample_of(holdings)
        assert sample.stocks == perf_test_report._PHASE3_STOCK_COUNT
        assert all(h.account == "证券账户" for h in hk_stocks)

    def test_partition_is_complete(self, perf_test_report):
        holdings = perf_test_report._generate_holdings(perf_test_report._PHASE1_STOCK_COUNT)
        sample = perf_test_report._sample_of(holdings)
        assert sample.stocks + sample.funds == sample.holdings
        assert sample.funds == len(perf_test_report.SAMPLE_FUNDS)


class TestVerdict:
    """达标判定边界。"""

    def test_at_target_is_pass(self, perf_test_report):
        assert "✅" in perf_test_report._verdict(60.0, 60.0)

    def test_under_and_over_target(self, perf_test_report):
        assert "✅" in perf_test_report._verdict(0.0, 60.0)
        assert "❌" in perf_test_report._verdict(60.01, 60.0)


class TestDottedReferencesResolve:
    """回归：脚本内的 dotted 引用（import 符号 / patch 目标 / 常量目标）必须真实存在。

    防重构后脚本悄然失效——编排层私有函数迁移曾使 Phase 2 运行期才 ImportError，
    仅靠非运行期用例（只测 helper）不会暴露，直到 CI 性能门禁实际跑全流程才红。
    """

    def test_all_dotted_references_resolve(self, perf_test_report):
        tree = ast.parse(inspect.getsource(perf_test_report))
        refs: set[str] = set()

        # ① from A import b / from A import (b, c) → 解析 A.b
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src.python"):
                for alias in node.names:
                    refs.add(f"{node.module}.{alias.name}")

        # ② patch("a.b.c") → mock 目标属性必须存在
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
            if name == "patch" and node.args and isinstance(node.args[0], ast.Constant):
                value = node.args[0].value
                if isinstance(value, str) and value.startswith("src.python"):
                    refs.add(value)

        # ③ 模块级字符串常量（如 LLM mock 目标常量）
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, str) and node.value.value.startswith("src.python"):
                    refs.add(node.value.value)

        broken = sorted(ref for ref in refs if not self._resolve(ref))
        assert refs, "应至少收集到一批 dotted 引用（收集器本身失效时测试无意义）"
        assert not broken, f"以下 dotted 引用无法解析（重构后脚本引用失效）：{broken}"

    @staticmethod
    def _resolve(path: str) -> bool:
        """从左到右逐段尝试 import，支持「模块」与「模块.属性链」两种形态。"""
        parts = path.split(".")
        for split in range(len(parts) - 1, 0, -1):
            try:
                obj = importlib.import_module(".".join(parts[:split]))
            except ImportError:
                continue
            try:
                for attr in parts[split:]:
                    obj = getattr(obj, attr)
            except AttributeError:
                continue
            return True
        return False


class TestOfflineStubs:
    """离线桩：门禁相关的网络咽喉桩与状态隔离。"""

    def test_mock_bars_shape_and_order(self, perf_test_report):
        bars = perf_test_report._mock_bars("history_stock", "600519", days=30)
        assert len(bars) >= 5
        dates = [b["date"] for b in bars]
        assert dates == sorted(dates), "K 线桩必须按日期升序"
        for key in ("open", "high", "low", "close", "volume"):
            assert all(key in b for b in bars)
        closes = {b["close"] for b in bars}
        assert len(closes) > 1, "收盘价必须有波动（否则收益率/流动性计算除零）"
        assert all(b["high"] >= b["close"] >= b["low"] for b in bars)

    def test_mock_bars_scales_with_days(self, perf_test_report):
        short = perf_test_report._mock_bars("history_stock", "600519", days=20)
        long_ = perf_test_report._mock_bars("history_stock", "600519", days=365)
        assert len(long_) > len(short)

    def test_mock_bars_tolerates_extras_kwargs(self, perf_test_report):
        """调用方可能带 diagnostics 等额外参数，桩必须吞下。"""
        bars = perf_test_report._mock_bars("history_stock", "600519", days=30, diagnostics=None)
        assert bars

    def test_calendar_stub_is_weekdays_only(self, perf_test_report):
        from datetime import date as _date

        dates = perf_test_report._stub_trading_calendar()
        assert dates
        assert all(_date.fromisoformat(d).weekday() < 5 for d in dates)
        assert _date.today().isoformat() <= max(dates)

    def test_last_workday_str_is_weekday(self, perf_test_report):
        from datetime import date as _date

        assert _date.fromisoformat(perf_test_report._last_workday_str()).weekday() < 5

    def test_quote_stub_carries_detail_row_keys(self, perf_test_report):
        quote = perf_test_report._mock_quote("600519", "贵州茅台")
        for key in ("price", "yesterday_close", "price_date", "source", "source_api", "name"):
            assert key in quote
        assert quote["price"] > 0 and quote["yesterday_close"] > 0
        assert quote["name"] == "贵州茅台"

    def test_state_isolation_redirects_perf_paths(self, perf_test_report):
        """基准不得写真实 perf 历史/健康快照/熔断状态（防污染统计与真实运行）。"""
        from src.python.core import perf as perf_mod
        from src.python.core import provider_registry as registry_mod

        orig = (perf_mod._PERF_HISTORY_FILE, perf_mod._HEALTH_CHECK_FILE, registry_mod._CIRCUIT_BREAKER_STATE_FILE)
        try:
            iso_dir = perf_test_report._isolate_state_writes()
            assert perf_mod._PERF_HISTORY_FILE.startswith(iso_dir)
            assert perf_mod._HEALTH_CHECK_FILE.startswith(iso_dir)
            # 熔断文件名以绝对路径传入，os.path.join 丢弃前面的目录段 → 落在隔离目录
            assert registry_mod._CIRCUIT_BREAKER_STATE_FILE.startswith(iso_dir)
            assert perf_mod._PERF_HISTORY_FILE != orig[0]
        finally:
            (
                perf_mod._PERF_HISTORY_FILE,
                perf_mod._HEALTH_CHECK_FILE,
                registry_mod._CIRCUIT_BREAKER_STATE_FILE,
            ) = orig

    def test_offline_network_blocks_connect_and_neutralizes_sleep(self, perf_test_report, monkeypatch):
        """传输层离线：建连瞬时 OSError（既有 except 接住走降级）+ 退避不真等。"""
        import socket as socket_mod
        import time as time_mod

        orig = {
            "sleep": time_mod.sleep,
            "connect": socket_mod.socket.connect,
            "connect_ex": socket_mod.socket.connect_ex,
            "create_connection": socket_mod.create_connection,
            "getaddrinfo": socket_mod.getaddrinfo,
        }
        try:
            perf_test_report._install_offline_network()
            # 退避归零：原本要睡 5 秒的调用瞬时返回（5 倍余量，不靠毫秒级精度）
            t0 = time_mod.monotonic()
            time_mod.sleep(5)
            assert time_mod.monotonic() - t0 < 1.0
            # 建连瞬时失败且为常规失败类型（OSError，非 BaseException）
            s = socket_mod.socket()
            try:
                with pytest.raises(OSError):
                    s.connect(("127.0.0.1", 9))
            finally:
                s.close()
        finally:
            for name, value in orig.items():
                if name == "sleep":
                    time_mod.sleep = value
                elif name == "connect":
                    socket_mod.socket.connect = value
                elif name == "connect_ex":
                    socket_mod.socket.connect_ex = value
                elif name == "create_connection":
                    socket_mod.create_connection = value
                else:
                    socket_mod.getaddrinfo = value


class TestGateMode:
    """门禁模式：退出码契约（0 达标 / 2 未达标，与检查脚本一致）。"""

    def _run_main(self, perf_test_report, monkeypatch, basic_time: float, gate: bool) -> int:
        monkeypatch.setattr(perf_test_report, "run_perf_test", lambda: ({}, None, None))
        monkeypatch.setattr(perf_test_report, "write_perf_report", lambda *a, **k: "report.md")
        monkeypatch.setattr(
            perf_test_report,
            "run_perf_test",
            lambda: ({"phase1_basic_excel": basic_time}, None, None),
        )
        argv = ["test-perf-report.py"] + (["--gate"] if gate else [])
        monkeypatch.setattr("sys.argv", argv)
        return perf_test_report.main()

    def test_gate_passes_at_target(self, perf_test_report, monkeypatch):
        assert self._run_main(perf_test_report, monkeypatch, 60.0, gate=True) == 0

    def test_gate_fails_above_target_with_exit_2(self, perf_test_report, monkeypatch):
        """门禁模式未达标退出 2（与检查脚本「发现 finding」契约一致）。"""
        assert self._run_main(perf_test_report, monkeypatch, 60.01, gate=True) == 2

    def test_non_gate_mode_keeps_exit_1(self, perf_test_report, monkeypatch):
        """非门禁模式保持原有退出码 1（人工运行语义不变）。"""
        assert self._run_main(perf_test_report, monkeypatch, 60.01, gate=False) == 1

    def test_non_gate_mode_passes_at_target(self, perf_test_report, monkeypatch):
        assert self._run_main(perf_test_report, monkeypatch, 10.0, gate=False) == 0


class TestTestTimeText:
    """测试时间文案：按时刻动态生成。"""

    def test_formats_given_moment(self, perf_test_report):
        assert perf_test_report._test_time_text(datetime(2026, 7, 20, 8, 30, 15)) == "2026-07-20 08:30:15"

    def test_defaults_to_now(self, perf_test_report):
        text = perf_test_report._test_time_text()
        reported = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        assert abs((datetime.now() - reported).total_seconds()) < 60


class TestWritePerfReport:
    """报告文案：测试时间随运行更新、持仓规模按实际数量派生。"""

    def test_report_time_tracks_run_time(self, perf_test_report, report_path):
        perf_test_report.write_perf_report(
            _timings(), _sample(perf_test_report, 20, 3), _sample(perf_test_report, 50, 3)
        )
        text = Path(report_path).read_text(encoding="utf-8")
        matched = re.search(r"\*\*测试时间\*\*: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", text)
        assert matched, f"测试时间行缺失或格式非动态: {text!r}"
        reported = datetime.strptime(matched.group(1), "%Y-%m-%d %H:%M:%S")
        assert abs((datetime.now() - reported).total_seconds()) < 60

    def test_size_copy_derived_from_samples(self, perf_test_report, report_path):
        phase1 = _sample(perf_test_report, 20, 3)
        phase3 = _sample(perf_test_report, 50, 3)
        perf_test_report.write_perf_report(_timings(), phase1, phase3)
        text = Path(report_path).read_text(encoding="utf-8")
        expected_phase1 = f"Phase1/2: {phase1.holdings} 品种（{phase1.stocks} 股票 + {phase1.funds} 场外基金）"
        expected_phase3 = f"Phase3: {phase3.holdings} 品种（{phase3.stocks} 股票 + {phase3.funds} 场外基金）"
        assert expected_phase1 in text, "Phase1/2 规模文案与实际不符"
        assert expected_phase3 in text, "Phase3 规模文案与实际不符"
        assert f"{phase3.holdings}品种压力测试" in text
        # 结论文案（basic/压力测试段）同样按实际数量出
        assert f"{phase1.holdings} 品种（{phase1.stocks} 股票 + {phase1.funds} 场外基金）basic" in text
        assert f"{phase3.holdings} 品种（{phase3.stocks} 股票 + {phase3.funds} 场外基金）basic Excel" in text

    def test_size_copy_reflects_smaller_actual_sample(self, perf_test_report, report_path):
        """样本变小 → 文案随之变小（文案不写死的直接证据）。"""
        phase1 = _sample(perf_test_report, 7, 2)
        phase3 = _sample(perf_test_report, 9, 1)
        perf_test_report.write_perf_report(_timings(), phase1, phase3)
        text = Path(report_path).read_text(encoding="utf-8")
        assert f"Phase1/2: {phase1.holdings} 品种" in text
        assert f"Phase3: {phase3.holdings} 品种" in text
        assert "20 品种" not in text
        assert "50 品种" not in text

    def test_verdict_column_follows_basic_time(self, perf_test_report, report_path):
        timings = dict(_timings(), phase1_basic_excel=100.0)
        perf_test_report.write_perf_report(timings, _sample(perf_test_report, 20, 3), _sample(perf_test_report, 50, 3))
        text = Path(report_path).read_text(encoding="utf-8")
        assert "❌ 超标" in text

    def test_writes_to_configured_path(self, perf_test_report, report_path):
        ret = perf_test_report.write_perf_report(
            _timings(), _sample(perf_test_report, 20, 3), _sample(perf_test_report, 50, 3)
        )
        assert ret == str(report_path)
        assert report_path.exists()


class TestLlmMock:
    """LLM mock：patch 目标 = 包属性；返回值结构与收集器契约同构。"""

    def test_patch_target_is_package_attribute(self, perf_test_report):
        """调用点在函数内 `from src.python.llm import generate_all_llm` 读包属性。"""
        import src.python.report._llm_news as news_mod

        source = inspect.getsource(news_mod._submit_llm_future)
        assert "from src.python.llm import generate_all_llm" in source

        assert perf_test_report._LLM_MOCK_TARGET == "src.python.llm.generate_all_llm"
        # 指向子模块属性的写法不会覆盖该读取点
        assert not perf_test_report._LLM_MOCK_TARGET.startswith("src.python.llm.generators_orchestrator")

    def test_patch_shadows_call_site_read(self, perf_test_report):
        """patch 目标生效后，与调用点同款的包属性读取拿到 mock。"""
        from unittest.mock import sentinel

        with patch(perf_test_report._LLM_MOCK_TARGET, sentinel.perf_llm) as mocked:
            from src.python.llm import generate_all_llm as resolved_at_call_time

            assert resolved_at_call_time is mocked
            assert mocked is sentinel.perf_llm

    def test_mock_value_matches_collector_contract(self, perf_test_report):
        """mock 返回值经真实收集器解析：4 模块内容 + 无辩论信息、无异常登记。"""
        from src.python.report._llm_news import _collect_llm_future_result

        class _FakeFuture:
            def result(self):
                return perf_test_report._LLM_MOCK_VALUE

        reporter = MagicMock()
        llm_content, debate_info = _collect_llm_future_result(_FakeFuture(), reporter)
        assert len(llm_content) == 4
        assert all(isinstance(c, str) and c for c in llm_content)
        assert debate_info is None
        reporter.add_error.assert_not_called()


def _sample(module, stocks: int, funds: int):
    """构造样本规模（总品种数由分量派生，不写死）。"""
    return module.PerfSample(holdings=stocks + funds, stocks=stocks, funds=funds)
