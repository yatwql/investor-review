"""因子动物园探针的降级分支：单标的取数失败不中断整批。

四个探针（日 K / 基准指数 / 估值 / 财务指标）各自捕获取数异常并打印一行
`[!]` 提示后返回空值——这是跨标的批量评测「单点失败不毁整批」的契约。
另覆盖股票池穿透成功路径（穿透代码并入池）。
"""

from __future__ import annotations

import pytest
from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="probe", scope="module")
def fixture_probe():
    """先加载薄入口（导入期把 `scripts/` 接入 sys.path），再取探针子模块。"""
    load_script("eval-factor-zoo.py")
    from _eval_factor_zoo import probe as probe_module

    return probe_module


def _raising(*_args, **_kwargs):
    raise RuntimeError("数据源不可用")


class TestProbeDegradation:
    def test_bars_failure_returns_empty(self, probe, monkeypatch, capsys):
        from src.python.fetcher import chain_incremental

        monkeypatch.setattr(chain_incremental, "fetch_with_incremental_fallback", _raising)
        assert probe.probe_bars("600519") == []
        assert "日K失败" in capsys.readouterr().out

    def test_index_failure_returns_empty(self, probe, monkeypatch, capsys):
        from src.python.fetcher import index

        monkeypatch.setattr(index, "fetch_index_history", _raising)
        assert probe.probe_index() == []
        assert "指数历史失败" in capsys.readouterr().out

    def test_valuation_failure_returns_none(self, probe, monkeypatch, capsys):
        from src.python.fetcher import industry

        monkeypatch.setattr(industry, "fetch_valuation_fields", _raising)
        assert probe.probe_valuation("600519") is None
        assert "估值失败" in capsys.readouterr().out

    def test_fin_indicator_failure_returns_none(self, probe, monkeypatch, capsys):
        from src.python.fetcher import financial_indicator

        monkeypatch.setattr(financial_indicator, "fetch_latest_indicator", _raising)
        assert probe.probe_fin_indicator("600519") is None
        assert "财务指标失败" in capsys.readouterr().out


class TestStockPoolPenetration:
    def test_penetration_codes_join_pool(self, probe, monkeypatch):
        from src.python.core import reader
        from src.python.core.models import Holding
        from src.python.report import penetration

        monkeypatch.setattr(reader, "read_holdings", lambda _p: [Holding("证券", "贵州茅台", "600519", 100, 1500.0)])
        monkeypatch.setattr(
            penetration,
            "compute_penetration_top10",
            lambda *_a, **_k: {"top10": [{"code": "000858"}]},
        )

        pool = probe.build_stock_pool("ignored.xlsx")

        assert pool["penetration_stocks"] == ["000858"]
        assert pool["penetration_note"] == ""
        assert pool["codes"] == ["000858", "600519"]
