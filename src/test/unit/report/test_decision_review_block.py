"""决策跨期反思闭环 — 「历史决策复盘」报告区块数据装配单元测试。

覆盖：开关关闭返回 None、空账本返回 None、pending/settled 计数与最近分列表
（含方向文案、settled 结果展示）、命中率门槛（样本不足不给结论值）、免责声明。

运行：
  pytest src/test/unit/report/test_decision_review_block.py -v
"""

from __future__ import annotations

import pytest

from src.python.config.features import set_feature_enabled, reset_feature_flags
from src.python.core import decision_ledger as dl
from src.python.report import decision_review_block as rb

from src.test._relative_dates import day as _d

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]
#: 账本样本日期：复盘区块读决策账本（730 天写侧裁剪）
#: 写死绝对日期会在「日期 + 保留期」之后被 `prune_jsonl_by_age` 当过期记录清掉，
#: 用例静默变成「账本为空 / 键缺失」，失败信息完全看不出是日期过期——故从当天回推派生。


@pytest.fixture(autouse=True)
def _enable_flag():
    set_feature_enabled("decision_reflection", True)
    yield
    reset_feature_flags()


class TestReviewBlock:
    """区块数据装配。"""

    def test_flag_off_returns_none(self, tmp_path):
        reset_feature_flags()
        assert rb.build_review_block(ledger_path=str(tmp_path / "ledger.jsonl")) is None

    def test_empty_ledger_returns_none(self, tmp_path):
        assert rb.build_review_block(ledger_path=str(tmp_path / "ledger.jsonl")) is None

    def test_counts_and_recent_pending(self, tmp_path):
        lp = str(tmp_path / "ledger.jsonl")
        dl.append_decision(
            code="561910",
            name="电池ETF",
            direction=dl.DIRECTION_SHORT,
            carrier=dl.CARRIER_EXPERT_REVIEW,
            report_date=_d(0),
            baseline_close=0.712,
            path=lp,
        )
        block = rb.build_review_block(report_date=_d(8), ledger_path=lp)
        assert block is not None
        assert block["available"] is True
        assert block["pending_count"] == 1
        assert block["settled_count"] == 0
        assert block["disclaimer"]
        assert len(block["recent_pending"]) == 1
        row = block["recent_pending"][0]
        assert row["code"] == "561910"
        assert "看空" in row["direction"]

    def test_settled_in_recent_with_outcome(self, tmp_path):
        lp = str(tmp_path / "ledger.jsonl")
        did = dl.append_decision(
            code="600900",
            name="长江电力",
            direction=dl.DIRECTION_SHORT,
            carrier=dl.CARRIER_DISCIPLINE,
            report_date=_d(-12),
            baseline_close=22.5,
            path=lp,
        )
        dl.append_settlement(
            decision_id=did,
            raw_return=-0.05,
            outcome=dl.OUTCOME_HIT,
            direction_hit=True,
            settle_date=_d(-5),
            horizon_bars=5,
            path=lp,
        )
        block = rb.build_review_block(ledger_path=lp)
        assert block is not None, "装配结果应可读"
        assert block["settled_count"] == 1
        assert block["pending_count"] == 0
        assert len(block["recent_settled"]) == 1
        row = block["recent_settled"][0]
        assert row["outcome"] == dl.OUTCOME_HIT
        assert row["raw_return"] == pytest.approx(-0.05)

    def test_accuracy_none_below_sample(self, tmp_path):
        # 1 个方向样本 < MEANINGFUL_SAMPLE → accuracy None / sample_sufficient False
        lp = str(tmp_path / "ledger.jsonl")
        did = dl.append_decision(
            code="600900",
            name="长江电力",
            direction=dl.DIRECTION_LONG,
            baseline_close=10.0,
            path=lp,
        )
        dl.append_settlement(
            decision_id=did,
            raw_return=0.03,
            outcome=dl.OUTCOME_HIT,
            direction_hit=True,
            bench_return=0.01,  # 提供基准 → alpha 可算（方向性相对基准超额）
            path=lp,
        )
        block = rb.build_review_block(ledger_path=lp)
        assert block is not None, "装配结果应可读"
        assert block["sample_sufficient"] is False
        assert block["direction_accuracy"] is None
        assert block["alpha_mean"] == pytest.approx((0.03 - 0.01))  # (raw-bench)*sign, long=+1

    def test_alpha_none_without_benchmark(self, tmp_path):
        # 无基准 → 无 alpha（alpha 需基准区间涨跌）
        lp = str(tmp_path / "ledger.jsonl")
        did = dl.append_decision(
            code="600900", name="长江电力", direction=dl.DIRECTION_LONG, baseline_close=10.0, path=lp
        )
        dl.append_settlement(decision_id=did, raw_return=0.03, outcome=dl.OUTCOME_HIT, direction_hit=True, path=lp)
        block = rb.build_review_block(ledger_path=lp)
        assert block is not None, "装配结果应可读"
        assert block["alpha_mean"] is None

    def test_recent_limits(self, tmp_path):
        lp = str(tmp_path / "ledger.jsonl")
        for i in range(8):  # 8 pending → recent_pending 只展示最近 5 条
            dl.append_decision(
                code=f"60000{i}",
                name=f"股{i}",
                direction=dl.DIRECTION_SHORT,
                path=lp,
            )
        block = rb.build_review_block(ledger_path=lp)
        assert block is not None, "装配结果应可读"
        assert block["pending_count"] == 8
        assert len(block["recent_pending"]) == 5


class TestInactionJudgement:
    """不动作类（持有/观望/不操作）：待结算标「未到期」，已结算按容差带给判对/判偏。"""

    def _seed(self, lp: str, *, direction: int, raw: float | None = None, settle: bool = False) -> str:
        did = dl.append_decision(
            code="561910",
            name="电池ETF",
            direction=direction,
            carrier=dl.CARRIER_EXPERT_REVIEW,
            report_date=_d(-12),
            baseline_close=1.0,
            path=lp,
        )
        if settle and raw is not None:
            dl.append_settlement(
                decision_id=did,
                raw_return=raw,
                outcome=dl.OUTCOME_FLAT,
                settle_date=_d(-5),
                horizon_bars=5,
                flat_hit=dl.classify_flat_hit(raw),
                path=lp,
            )
        return did

    def test_pending_inaction_labelled_not_due(self, tmp_path):
        lp = str(tmp_path / "ledger.jsonl")
        self._seed(lp, direction=dl.DIRECTION_FLAT)
        block = rb.build_review_block(ledger_path=lp)
        assert block is not None
        assert block["recent_pending"][0]["judgement"] == "未到期"

    def test_settled_inaction_hit_and_miss(self, tmp_path):
        lp = str(tmp_path / "ledger.jsonl")
        self._seed(lp, direction=dl.DIRECTION_FLAT, raw=0.01, settle=True)  # 带内
        self._seed(lp, direction=dl.DIRECTION_FLAT, raw=0.05, settle=True)  # 越带
        block = rb.build_review_block(ledger_path=lp)
        assert block is not None
        labels = {row["judgement"] for row in block["recent_settled"]}
        assert labels == {"判对", "判偏"}

    def test_legacy_settlement_without_flat_hit_shows_band(self, tmp_path):
        """旧账本结算无 `flat_hit` ⇒ 按平盘呈现（不臆造判对/判偏）。"""
        lp = str(tmp_path / "ledger.jsonl")
        did = dl.append_decision(
            code="600000",
            name="浦发银行",
            direction=dl.DIRECTION_FLAT,
            carrier=dl.CARRIER_EXPERT_REVIEW,
            report_date=_d(-12),
            baseline_close=10.0,
            path=lp,
        )
        dl.append_settlement(
            decision_id=did,
            raw_return=0.01,
            outcome=dl.OUTCOME_FLAT,
            settle_date=_d(-5),
            horizon_bars=5,
            path=lp,
        )
        block = rb.build_review_block(ledger_path=lp)
        assert block is not None
        assert block["recent_settled"][0]["judgement"] == "平盘"
        assert block["inaction"]["total"] == 0  # 未判不计样本

    def test_directional_rows_have_no_judgement_label(self, tmp_path):
        lp = str(tmp_path / "ledger.jsonl")
        did = self._seed(lp, direction=dl.DIRECTION_LONG)
        dl.append_settlement(
            decision_id=did,
            raw_return=0.05,
            outcome=dl.OUTCOME_HIT,
            direction_hit=True,
            settle_date=_d(-5),
            horizon_bars=5,
            path=lp,
        )
        block = rb.build_review_block(ledger_path=lp)
        assert block is not None
        assert block["recent_settled"][0]["judgement"] == ""
