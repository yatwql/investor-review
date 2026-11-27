"""测试：`test-perf-report.py` 编排与门禁判定 —— 阶段计时收集 / 样本规模 / `--gate` 退出码。

覆盖：
  - `run_perf_test` 的四阶段编排：数据生成 → basic Excel → both(Excel+HTML) →
    Phase3 大持仓压力 → full 全链路；阶段计时键集完整、样本规模按账户口径统计、
    报告类型与快照命名空间透传给管线（管线本体打桩，不跑真实报告生成）
  - `main` 的目标达标判定与退出码：全达标 0；非门禁未达标 1；`--gate` 未达标 2
    （与检查脚本契约一致）；缺阶段键按 0 计（视为达标）
  - 报告路径回写与判定文案（basic / full 两档各自达标与未达标的四类提示）

桩替换 `_isolate_log_writes` / `_isolate_state_writes` / `_install_offline_network`
（这三个会改全局 socket/time/状态路径，测试内不得执行）与报告生成入口，
`write_perf_report` 重定向到 `tmp_path`——不产生真实报告文件、不发起网络。
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_SCRIPT = "test-perf-report.py"


@pytest.fixture(name="mod")
def fixture_mod():
    """加载 `scripts/test-perf-report.py` 为可测模块。"""
    return load_script(_SCRIPT, module_name="perf_report_main_probe")


class _PhaseRecorder(SimpleNamespace):
    """管线结果桩（`generate_report` 返回契约的最小同构体）。"""


def _stub_environment(mod, monkeypatch, tmp_path):
    """把全局副作用（日志/状态/socket）替换为惰性桩，返回调用记录。"""
    calls: dict[str, list] = {"excel": [], "report": []}
    monkeypatch.setattr(mod, "_isolate_log_writes", lambda: str(tmp_path / "logs"))
    monkeypatch.setattr(mod, "_isolate_state_writes", lambda: str(tmp_path / "state"))
    monkeypatch.setattr(mod, "_install_offline_network", lambda: None)

    def _fake_excel(holdings, **kwargs):
        calls["excel"].append({"holdings": list(holdings), **kwargs})
        return str(tmp_path / "report.xlsx")

    def _fake_generate_report(holdings, config, progress, **kwargs):
        calls["report"].append({"holdings": list(holdings), "config": config, **kwargs})
        return _PhaseRecorder(excel_ok=True, html_ok=True)

    import src.python.report.excel_generator as excel_module
    import src.python.report.orchestrator as orchestrator_module

    monkeypatch.setattr(excel_module, "generate_excel_report", _fake_excel)
    monkeypatch.setattr(orchestrator_module, "generate_report", _fake_generate_report)
    return calls


class TestRunPerfTest:
    def test_phases_timings_and_sample_scale(self, mod, monkeypatch, tmp_path, capsys):
        calls = _stub_environment(mod, monkeypatch, tmp_path)
        timings, phase1, phase3 = mod.run_perf_test()
        out = capsys.readouterr().out

        assert set(timings) == {
            "data_generation",
            "phase1_basic_excel",
            "phase2_both_html_excel",
            "phase3_stress_large",
            "phase4_full_pipeline",
        }
        assert all(seconds >= 0 for seconds in timings.values())
        # 样本规模按账户口径派生：股票数 = 取样数，基金数 = 总数 - 股票数
        assert phase1.stocks == mod._PHASE1_STOCK_COUNT
        assert phase1.holdings == phase1.stocks + phase1.funds
        assert phase3.stocks == mod._PHASE3_STOCK_COUNT
        assert phase3.holdings == phase3.stocks + phase3.funds
        assert "Phase 4: full 模式全链路" in out

        # 两次 Excel 生成（basic + 压力档）都不含新闻、输出到临时目录
        assert [len(call["holdings"]) for call in calls["excel"]] == [
            phase1.holdings,
            phase3.holdings,
        ]
        assert all(call["include_news"] is False for call in calls["excel"])

        # 两次报告分发：both（不含 LLM 之外的全链）→ full，且都进基准快照命名空间
        assert [call["report_type"] for call in calls["report"]] == ["both", "full"]
        assert all(call["snapshot_namespace"] == mod._SNAPSHOT_NAMESPACE for call in calls["report"])
        assert all(call["fetch_history"] is False for call in calls["report"])


class TestMainGate:
    @pytest.mark.parametrize(
        ("timings", "gate", "expected"),
        [
            pytest.param({"phase1_basic_excel": 1.0, "phase4_full_pipeline": 1.0}, False, 0, id="both-pass"),
            pytest.param({"phase1_basic_excel": 1.0, "phase4_full_pipeline": 1.0}, True, 0, id="both-pass-gate"),
            pytest.param({}, False, 0, id="missing-phases-count-as-pass"),
            pytest.param({"phase1_basic_excel": 10**6, "phase4_full_pipeline": 1.0}, False, 1, id="basic-fail"),
            pytest.param({"phase1_basic_excel": 1.0, "phase4_full_pipeline": 10**6}, True, 2, id="full-fail-gate"),
            pytest.param({"phase1_basic_excel": 10**6, "phase4_full_pipeline": 10**6}, True, 2, id="both-fail-gate"),
        ],
    )
    def test_exit_codes(self, mod, monkeypatch, tmp_path, capsys, timings, gate, expected):
        sample = mod.PerfSample(holdings=2, stocks=1, funds=1)
        monkeypatch.setattr(mod, "run_perf_test", lambda: (dict(timings), sample, sample))
        written: list[tuple] = []
        monkeypatch.setattr(
            mod, "write_perf_report", lambda t, p1, p3: written.append((t, p1, p3)) or str(tmp_path / "perf.md")
        )
        monkeypatch.setattr(sys, "argv", [_SCRIPT, *(["--gate"] if gate else [])])

        assert mod.main() == expected
        out = capsys.readouterr().out
        assert str(tmp_path / "perf.md") in out
        assert len(written) == 1

    def test_threshold_verdict_text_matches_targets(self, mod, monkeypatch, capsys):
        """提示文案带上渲染模块声明的目标秒数（单一声明，判定与文案同源）。"""
        basic, full = mod._TARGET_SECONDS, mod._TARGET_FULL_SECONDS
        timings = {"phase1_basic_excel": basic, "phase4_full_pipeline": full}
        sample = mod.PerfSample(holdings=2, stocks=1, funds=1)
        monkeypatch.setattr(mod, "run_perf_test", lambda: (dict(timings), sample, sample))
        monkeypatch.setattr(mod, "write_perf_report", lambda t, p1, p3: "report.md")
        monkeypatch.setattr(sys, "argv", [_SCRIPT])

        assert mod.main() == 0
        out = capsys.readouterr().out
        assert f"basic 模式达标: {basic:.2f}s ≤ {basic}s" in out
        assert f"full 全链路达标: {full:.2f}s ≤ {full}s" in out
        assert "[ERR]" not in out


class TestOfflineStubs:
    """离线桩自身契约：基准的确定性依赖这些桩（无网络、序列可计算、规模可控）。"""

    def test_last_workday_is_weekday(self, mod):
        from datetime import date

        resolved = date.fromisoformat(mod._last_workday_str())
        assert resolved.weekday() < 5
        assert resolved <= date.today()

    def test_trading_calendar_stub_covers_window_of_workdays(self, mod):
        from datetime import date

        dates = mod._stub_trading_calendar()
        assert dates, "日历桩不得为空（日历查询会退化为全降级）"
        assert all(date.fromisoformat(day).weekday() < 5 for day in dates)
        assert date.today().isoformat() in dates or date.today().weekday() >= 5
        assert max(dates) > date.today().isoformat()

    def test_mock_bars_are_ascending_computable_series(self, mod):
        rows = mod._mock_bars("tencent", "600519", days=10)
        assert len(rows) >= 5
        assert [row["date"] for row in rows] == sorted(row["date"] for row in rows)
        assert all(row["code"] == "600519" for row in rows)
        assert all(row["low"] < row["close"] < row["high"] for row in rows)
        assert all(row["volume"] > 0 for row in rows)

    def test_mock_bars_short_window_still_returns_five(self, mod):
        assert len(mod._mock_bars("sina", "00700", days=1)) == 5

    def test_mock_quote_satisfies_detail_row_keys(self, mod):
        quote = mod._mock_quote("600519", "贵州茅台")
        assert quote["name"] == "贵州茅台"
        assert quote["yesterday_close"] < quote["price"]
        assert set(quote) >= {"price", "yesterday_close", "price_date", "source", "source_api", "name"}


class TestGeneratedDetails:
    def test_details_derive_from_holdings(self, mod):
        holdings = mod._generate_holdings(3)
        details = mod._generate_details(holdings)
        assert [row.code for row in details] == [holding.code for holding in holdings]
        for row, holding in zip(details, holdings, strict=True):
            assert row.shares == holding.shares
            assert row.cost == pytest.approx(round(holding.shares * holding.cost_price, 2))
            assert row.profit == pytest.approx(row.market_value - row.cost)
            assert row.profit_rate == pytest.approx(row.profit / row.cost, abs=1e-4)
