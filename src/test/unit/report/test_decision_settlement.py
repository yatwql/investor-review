"""决策跨期反思闭环 — 结算服务单元测试。

覆盖：到期判定（bar 数门槛）、hit/miss/flat/gap、基准涨跌计算、幂等（已结不
重结）、开关关闭无感、行情注入失败降级。全部 mock 行情，防真网络。

运行：
  pytest src/test/unit/report/test_decision_settlement.py -v
"""

from __future__ import annotations

import pytest

from src.python.config.features import set_feature_enabled, reset_feature_flags
from src.python.core import decision_ledger as dl
from src.python.report import decision_settlement as ds

from src.test._relative_dates import day as _day

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]
#: 账本样本日期：结算服务写读决策账本（730 天写侧裁剪）
#: 写死绝对日期会在「日期 + 保留期」之后被 `prune_jsonl_by_age` 当过期记录清掉，
#: 用例静默变成「账本为空 / 键缺失」，失败信息完全看不出是日期过期——故从当天回推派生。


def _d(offset: int) -> str:
    """相对锚点（60 天前）的日期串，保留本文件原有的窗口起点。"""
    return _day(offset, shift_days=60)


# 决策日与固定交易日窗口：决策日 08-20，其后 08-21/22/25/26/27 恰好 5 个交易日
_REP = _d(0)
_DATES = [_d(-2), _d(1), _d(2), _d(5), _d(6), _d(7)]


@pytest.fixture(autouse=True)
def _enable_flag():
    set_feature_enabled("decision_reflection", True)
    yield
    reset_feature_flags()


def _bars(dates, closes):
    """构造 {date, close} 升序序列。"""
    return [{"date": d, "close": c} for d, c in zip(dates, closes)]


def _mature(closes):
    """固定成熟窗口序列：含 08-20 决策日之后恰好 5 个交易日的价格。"""
    assert len(closes) == len(_DATES)
    return _bars(_DATES, closes)


class _FakePrices:
    def __init__(self, series):
        self._series = series

    def __call__(self, code, name, days):
        return self._series


class _FakeIndex:
    def __init__(self, series):
        self._series = series

    def __call__(self, code, days):
        return self._series


def _seed_decision(lp, *, code="600000", direction=dl.DIRECTION_SHORT, rep=_REP, baseline=10.0):
    return dl.append_decision(
        code=code,
        name="test",
        direction=direction,
        carrier=dl.CARRIER_DISCIPLINE,
        report_date=rep,
        baseline_close=baseline,
        path=lp,
    )


class TestSettleOneHelpers:
    """内部序列取值 helper。"""

    def test_latest_close(self):
        assert ds._latest_close(_bars(["2026-01-01", "2026-01-02"], [1.0, 1.1])) == 1.1
        assert ds._latest_close([]) is None
        assert ds._latest_close([{"date": "x", "close": 0}]) is None  # 无效 close 跳过

    def test_series_at_date_locf(self):
        s = _bars(["2026-01-01", "2026-01-02", "2026-01-05"], [1.0, 1.1, 1.2])
        assert ds._series_at_date(s, "2026-01-02") == 1.1
        assert ds._series_at_date(s, "2026-01-03") == 1.1  # last-close 对齐
        assert ds._series_at_date(s, "2025-12-31") is None  # 早于首日


class TestSettleMaturity:
    """成熟度：决策日后 bar 数 < horizon 则不结算。"""

    def test_not_mature_deferred(self, tmp_path):
        lp = str(tmp_path / "ledger.jsonl")
        _seed_decision(lp, rep=_d(12), baseline=10.0)  # direction short
        # 决策日 09-01 之后仅 3 个 bar（09-02/03/04 < 5）→ 未到期
        series = _bars([_d(5), _d(13), _d(14), _d(15)], [10.0, 9.8, 9.7, 9.6])
        out = ds.settle_pending_decisions(
            report_date=_d(20),
            horizons=(dl.MIN_SETTLE_BARS,),
            ledger_path=lp,
            price_series_fn=_FakePrices(series),
            index_series_fn=_FakeIndex([]),
        )
        assert out["settled"] == 0
        assert out["deferred"] == 1
        assert dl.fold_ledger(path=lp)["settled_count"] == 0

    def test_mature_hit(self, tmp_path):
        lp = str(tmp_path / "ledger.jsonl")
        _seed_decision(lp, rep=_d(0), baseline=10.0)  # short
        out = ds.settle_pending_decisions(
            report_date=_d(8),
            ledger_path=lp,
            price_series_fn=_FakePrices(_mature([10.0, 9.9, 9.8, 9.7, 9.6, 9.5])),
            index_series_fn=_FakeIndex([]),
        )
        assert out["settled"] == 1
        assert out["summary"][0]["outcome"] == dl.OUTCOME_HIT
        assert out["summary"][0]["raw_return"] == pytest.approx(9.5 / 10.0 - 1)
        # 已结 → 幂等：再次调用不重结
        out2 = ds.settle_pending_decisions(
            report_date=_d(9),
            ledger_path=lp,
            price_series_fn=_FakePrices(_mature([10.0, 9.9, 9.8, 9.7, 9.6, 9.5])),
            index_series_fn=_FakeIndex([]),
        )
        assert out2["settled"] == 0


class TestSettleOutcomes:
    """hit/miss/flat 判定。"""

    def _one(self, tmp_path, closes, direction=dl.DIRECTION_SHORT):
        lp = str(tmp_path / "ledger.jsonl")
        _seed_decision(lp, direction=direction, baseline=10.0)
        return ds.settle_pending_decisions(
            report_date=_d(8),
            ledger_path=lp,
            price_series_fn=_FakePrices(_mature(closes)),
            index_series_fn=_FakeIndex([]),
        )

    def test_short_hit_on_decline(self, tmp_path):
        out = self._one(tmp_path, [10.0, 9.9, 9.8, 9.7, 9.6, 9.5])
        assert out["settled"] == 1
        assert out["summary"][0]["outcome"] == dl.OUTCOME_HIT

    def test_short_miss_on_rise(self, tmp_path):
        out = self._one(tmp_path, [10.0, 10.2, 10.4, 10.6, 10.8, 11.0])
        assert out["summary"][0]["outcome"] == dl.OUTCOME_MISS

    def test_flat_below_threshold(self, tmp_path):
        out = self._one(tmp_path, [10.0, 10.0, 10.01, 10.0, 10.01, 10.0])
        assert out["summary"][0]["outcome"] == dl.OUTCOME_FLAT

    def test_long_hit_on_rise(self, tmp_path):
        out = self._one(tmp_path, [10.0, 10.2, 10.4, 10.6, 10.8, 11.0], direction=dl.DIRECTION_LONG)
        assert out["summary"][0]["outcome"] == dl.OUTCOME_HIT

    def test_gap_when_no_price(self, tmp_path):
        lp = str(tmp_path / "ledger.jsonl")
        _seed_decision(lp, rep=_d(0), baseline=10.0)
        out = ds.settle_pending_decisions(
            report_date=_d(8),
            horizons=(dl.MIN_SETTLE_BARS,),
            ledger_path=lp,
            price_series_fn=_FakePrices([]),  # 全链路无行情
            index_series_fn=_FakeIndex([]),
        )
        assert out["settled"] == 0
        assert out["deferred"] == 1

    def test_hold_neutral_settles_with_flat_hit(self, tmp_path):
        """不动作类（持有/观望/不操作）会结算，判定落 `flat_hit`（不占方向性命中率）。

        区间涨跌 +10% 远超 2% 容忍带 ⇒ 判偏（flat_hit=False）；方向性命中率分母不变。
        """
        lp = str(tmp_path / "ledger.jsonl")
        dl.append_decision(
            code="600000",
            name="x",
            direction=dl.DIRECTION_FLAT,
            carrier=dl.CARRIER_EXPERT_REVIEW,
            report_date=_d(0),
            baseline_close=10.0,
            path=lp,
        )
        out = ds.settle_pending_decisions(
            report_date=_d(8),
            ledger_path=lp,
            price_series_fn=_FakePrices(_mature([10.0, 10.2, 10.4, 10.6, 10.8, 11.0])),
            index_series_fn=_FakeIndex([]),
        )
        assert out["settled"] == 1
        assert out["skipped"] == 0
        stats = dl.fold_ledger(path=lp)
        assert stats["inaction"]["total"] == 1
        assert stats["inaction"]["hit"] == 0  # +10% 越带 ⇒ 判偏
        assert stats["directional_total"] == 0  # 不动作类不进方向性分母

    def test_hold_neutral_within_band_counts_as_hit(self, tmp_path):
        """区间涨跌落在容忍带内（<2%）⇒ 不动作判对。"""
        lp = str(tmp_path / "ledger.jsonl")
        dl.append_decision(
            code="600001",
            name="y",
            direction=dl.DIRECTION_FLAT,
            carrier=dl.CARRIER_EXPERT_REVIEW,
            report_date=_d(0),
            baseline_close=10.0,
            path=lp,
        )
        out = ds.settle_pending_decisions(
            report_date=_d(8),
            ledger_path=lp,
            price_series_fn=_FakePrices(_mature([10.0, 10.05, 10.1, 10.05, 10.08, 10.1])),
            index_series_fn=_FakeIndex([]),
        )
        assert out["settled"] == 1
        stats = dl.fold_ledger(path=lp)
        inaction = stats["inaction"]
        assert inaction["total"] == 1
        assert inaction["hit"] == 1
        assert inaction["hit_rate"] == pytest.approx(1.0)
        assert inaction["sample_sufficient"] is False

    def test_illegal_direction_skipped(self, tmp_path):
        """方向值非法（非 ±1/0）仍跳过，不计结算。"""
        lp = str(tmp_path / "ledger.jsonl")
        dl.append_decision(
            code="600002",
            name="z",
            direction=7,
            carrier=dl.CARRIER_EXPERT_REVIEW,
            report_date=_d(0),
            baseline_close=10.0,
            path=lp,
        )
        out = ds.settle_pending_decisions(
            report_date=_d(8),
            ledger_path=lp,
            price_series_fn=_FakePrices(_mature([10.0, 10.2, 10.4, 10.6, 10.8, 11.0])),
            index_series_fn=_FakeIndex([]),
        )
        assert out["settled"] == 0
        assert out["skipped"] == 1


class TestSettleBenchmark:
    """基准（沪深300）区间涨跌。"""

    def test_benchmark_computed(self, tmp_path):
        lp = str(tmp_path / "ledger.jsonl")
        _seed_decision(lp, rep=_d(0), baseline=10.0)  # short
        # 基准：决策日(LOCF 08-18) close=4000，末 08-27 close=3800 → -5%
        idx = _bars([_d(-2), _d(5), _d(7)], [4000.0, 3900.0, 3800.0])
        out = ds.settle_pending_decisions(
            report_date=_d(8),
            ledger_path=lp,
            price_series_fn=_FakePrices(_mature([10.0, 9.9, 9.8, 9.7, 9.6, 9.5])),
            index_series_fn=_FakeIndex(idx),
        )
        assert out["settled"] == 1
        s = out["summary"][0]
        assert s["bench_return"] == pytest.approx(3800.0 / 4000.0 - 1)
        assert s["outcome"] == dl.OUTCOME_HIT

    def test_benchmark_missing_is_none(self, tmp_path):
        # 基准拉取失败 → bench_return None，方向判定不受影响
        lp = str(tmp_path / "ledger.jsonl")
        _seed_decision(lp, rep=_d(0), baseline=10.0)
        out = ds.settle_pending_decisions(
            report_date=_d(8),
            ledger_path=lp,
            price_series_fn=_FakePrices(_mature([10.0, 9.9, 9.8, 9.7, 9.6, 9.5])),
            index_series_fn=_FakeIndex([]),
        )
        assert out["settled"] == 1
        assert out["summary"][0]["bench_return"] is None
        assert out["summary"][0]["outcome"] == dl.OUTCOME_HIT


class TestMultiHorizon:
    """多视界结算（5/20/60）：同决策多行落账、逐视界幂等、旧记录兼容。"""

    @staticmethod
    def _long_mature(bars_after: int, base: float = 10.0, step: float = -0.01):
        """决策日（_d(0)）后恰好 bars_after 根 bar 的长序列（单调涨跌由 step 定）。"""
        closes = [base] + [base + step * i for i in range(1, bars_after + 1)]
        dates = [_d(0)] + [_d(i) for i in range(1, bars_after + 1)]
        return _bars(dates, closes)

    @staticmethod
    def _settle(lp, series, horizons, report_date):
        return ds.settle_pending_decisions(
            report_date=report_date,
            ledger_path=lp,
            horizons=horizons,
            price_series_fn=_FakePrices(series),
            index_series_fn=_FakeIndex([]),
        )

    def test_three_horizons_one_run_and_idempotent(self, tmp_path):
        lp = str(tmp_path / "ledger.jsonl")
        _seed_decision(lp, rep=_REP, baseline=10.0)
        series = self._long_mature(65)
        out = self._settle(lp, series, dl.SETTLE_HORIZONS, _d(70))
        assert out["settled"] == 3  # 同一决策产出 3 条结算（验收①）
        assert sorted(s["target_horizon"] for s in out["summary"]) == [5, 20, 60]
        fold = dl.fold_ledger(path=lp)
        [d] = fold["decisions"]
        assert set(d["settlements"]) == {5, 20, 60}
        assert d["settlement"]["target_horizon"] == 5  # 口径基准仍是 5 日
        assert fold["by_horizon"][60]["settled"] == 1
        # 逐视界幂等：同视界不重结（验收②）
        out2 = self._settle(lp, series, dl.SETTLE_HORIZONS, _d(71))
        assert out2["settled"] == 0

    def test_partial_maturity_then_backfill(self, tmp_path):
        lp = str(tmp_path / "ledger.jsonl")
        _seed_decision(lp, rep=_REP, baseline=10.0)
        out = self._settle(lp, self._long_mature(25), dl.SETTLE_HORIZONS, _d(26))
        assert out["settled"] == 2  # 5/20 成熟，60 未到期
        assert sorted(s["target_horizon"] for s in out["summary"]) == [5, 20]
        assert out["deferred"] == 1
        # 序列增长 → 只回补 60，已结视界不认领不重结（验收③）
        out2 = self._settle(lp, self._long_mature(65), dl.SETTLE_HORIZONS, _d(70))
        assert out2["settled"] == 1
        assert out2["summary"][0]["target_horizon"] == 60
        fold = dl.fold_ledger(path=lp)
        [d] = fold["decisions"]
        assert set(d["settlements"]) == {5, 20, 60}

    def test_legacy_five_day_record_backfills_long_horizons(self, tmp_path):
        lp = str(tmp_path / "ledger.jsonl")
        did = _seed_decision(lp, rep=_REP, baseline=10.0)
        # 旧数据：无 target_horizon 的 5 日结算事件（历史事件不改写，验收④）
        dl.append_settlement(
            decision_id=did,
            raw_return=-0.05,
            outcome=dl.OUTCOME_HIT,
            direction_hit=True,
            horizon_bars=7,
            path=lp,
        )
        out = self._settle(lp, self._long_mature(65), dl.SETTLE_HORIZONS, _d(70))
        assert out["settled"] == 2  # 20/60 回补，5 不重结
        assert sorted(s["target_horizon"] for s in out["summary"]) == [20, 60]
        fold = dl.fold_ledger(path=lp)
        [d] = fold["decisions"]
        assert set(d["settlements"]) == {5, 20, 60}
        assert d["settlement"]["horizon_bars"] == 7  # 结算 bar 数沿用事件本身
        assert d["settlement"]["target_horizon"] == dl.MIN_SETTLE_BARS, (
            "缺字段的历史结算事件由写侧回填目标视界（否则 fold 与判重键两套口径）"
        )

    def test_default_targets_follow_ledger_horizons(self, tmp_path):
        """缺省 `horizons=None` → 取 `SETTLE_HORIZONS`（唯一口径，不再是单视界缺省）。"""
        lp = str(tmp_path / "ledger.jsonl")
        _seed_decision(lp, rep=_REP, baseline=10.0)
        out = ds.settle_pending_decisions(
            report_date=_d(8),
            ledger_path=lp,
            price_series_fn=_FakePrices(_mature([10.0, 9.9, 9.8, 9.7, 9.6, 9.5])),
            index_series_fn=_FakeIndex([]),
        )
        # 样本只够 5 日：5 日落账，20/60 各暂缓一次 → 三条口径都在跑
        assert out["settled"] == 1
        assert out["deferred"] == len(dl.SETTLE_HORIZONS) - 1
        fold = dl.fold_ledger(path=lp)
        [d] = fold["decisions"]
        assert set(d["settlements"]) == {5}


class TestSettleGating:
    """开关与幂等。"""

    def test_flag_off_noop(self, tmp_path):
        reset_feature_flags()
        lp = str(tmp_path / "ledger.jsonl")
        _seed_decision(lp, rep=_d(0), baseline=10.0)
        out = ds.settle_pending_decisions(report_date=_d(8), ledger_path=lp)
        assert out == {"settled": 0, "ids": [], "deferred": 0, "skipped": 0, "summary": []}

    def test_already_settled_idempotent(self, tmp_path):
        lp = str(tmp_path / "ledger.jsonl")
        _seed_decision(lp, rep=_d(0), baseline=10.0, code="600001")
        _seed_decision(lp, rep=_d(0), baseline=10.0, code="600002")
        price = _mature([10.0, 9.9, 9.8, 9.7, 9.6, 9.5])
        out1 = ds.settle_pending_decisions(
            report_date=_d(8),
            ledger_path=lp,
            price_series_fn=_FakePrices(price),
            index_series_fn=_FakeIndex([]),
        )
        assert out1["settled"] == 2
        # 两个已结 → 再次调用 settled=0
        out2 = ds.settle_pending_decisions(
            report_date=_d(9),
            ledger_path=lp,
            price_series_fn=_FakePrices(price),
            index_series_fn=_FakeIndex([]),
        )
        assert out2["settled"] == 0
        assert dl.fold_ledger(path=lp)["settled_count"] == 2
