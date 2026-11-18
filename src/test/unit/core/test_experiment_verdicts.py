"""实验项自动裁决（`core/experiment_verdicts.py`）——读数汇编、结论与提醒口径。

守四条契约：
  - **项清单派生**：裁决覆盖注册表 `experimental_flags()` 的全部实验项（新增项自动纳入，
    不写字面量项数）；
  - **判据不新造**：`report_qa` 的判据条目来自 `qa/telemetry.py`，本模块只判决不改阈值；
  - **无读数不臆造**：未登记读数适配器的项输出「判据未接读数源」，不冒充达标；
  - **撤销优先于观察**：账本长期不增长的项不该继续挂在「继续观察」。
"""

from __future__ import annotations

import pytest

from src.python.core import experiment_verdicts as verdicts_mod
from src.python.core.experiment_verdicts import (
    STATE_NO_READING,
    STATE_OBSERVING,
    STATE_PROMOTE_ELIGIBLE,
    STATE_REVOKE_CANDIDATE,
    action_notices,
    collect_verdicts,
    format_verdict_lines,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _flags() -> list[str]:
    from src.python.config.features import experimental_flags

    return [flag for flag, _declaration in experimental_flags()]


def _by_flag(flag: str) -> dict:
    return next(item for item in collect_verdicts() if item["flag"] == flag)


class TestCoverage:
    def test_every_registry_experiment_gets_a_verdict(self):
        """裁决项集合 = 注册表实验项集合（新增实验项不需要改本用例）。"""
        assert {item["flag"] for item in collect_verdicts()} == set(_flags())

    def test_unknown_flag_reports_no_reading(self, monkeypatch):
        """注册表新增但未接读数适配器 → 明说「无读数」，不伪造判据结论。"""
        from src.python.config import features as features_mod

        class _Decl:
            label = "假想实验项"

        monkeypatch.setattr(features_mod, "experimental_flags", lambda: [("brand_new_experiment", _Decl())])
        monkeypatch.setattr(verdicts_mod, "_READERS", dict(verdicts_mod._READERS))

        verdict = _by_flag("brand_new_experiment")
        assert verdict["state"] == STATE_NO_READING
        assert "未接读数源" in verdict["reason"]
        assert verdict["checks"] == []

    def test_reader_failure_degrades_to_no_reading(self, monkeypatch, caplog):
        def _boom() -> dict:
            raise RuntimeError("账本损坏")

        monkeypatch.setattr(verdicts_mod, "_READERS", {**_flags_dict(), "decision_reflection": _boom})
        verdict = _by_flag("decision_reflection")
        assert verdict["state"] == STATE_NO_READING
        assert "账本损坏" in verdict["reason"]


def _flags_dict() -> dict:
    return dict(verdicts_mod._READERS)


class TestDecisionReflectionVerdict:
    def _patch_fold(self, monkeypatch, *, total: int, alpha: float | None):
        from src.python.core import decision_ledger

        monkeypatch.setattr(
            decision_ledger,
            "fold_ledger",
            lambda *a, **k: {"directional_total": total, "alpha_mean": alpha},
        )

    def test_promote_when_sample_and_alpha_pass(self, monkeypatch):
        self._patch_fold(monkeypatch, total=verdicts_mod.PROMOTE_DIRECTIONAL_SAMPLE + 1, alpha=0.012)
        verdict = _by_flag("decision_reflection")
        assert verdict["state"] == STATE_PROMOTE_ELIGIBLE
        assert all(check["passed"] for check in verdict["checks"])

    def test_observing_when_alpha_negative(self, monkeypatch):
        """样本够但超额为负 → 不得判可转正（摘 experimental 会给出虚高能力暗示）。"""
        self._patch_fold(monkeypatch, total=verdicts_mod.PROMOTE_DIRECTIONAL_SAMPLE + 40, alpha=-0.004)
        verdict = _by_flag("decision_reflection")
        assert verdict["state"] == STATE_OBSERVING
        assert any(not check["passed"] for check in verdict["checks"])

    def test_observing_when_alpha_missing(self, monkeypatch):
        self._patch_fold(monkeypatch, total=verdicts_mod.PROMOTE_DIRECTIONAL_SAMPLE, alpha=None)
        assert _by_flag("decision_reflection")["state"] == STATE_OBSERVING


class TestReportQaVerdict:
    def _patch_summary(self, monkeypatch, *, checks: list[dict], idle_attempts: int):
        from src.python.qa import telemetry

        def _summary(days: int = 30, **_kwargs) -> dict:
            if days >= verdicts_mod.QA_REVOKE_IDLE_DAYS:
                return {"attempts": idle_attempts, "verdict": {"ready": False, "checks": []}}
            return {"attempts": 40, "verdict": {"ready": all(c["passed"] for c in checks), "checks": checks}}

        monkeypatch.setattr(telemetry, "summarize_qa_usage", _summary)

    def test_promote_when_all_telemetry_checks_pass(self, monkeypatch):
        self._patch_summary(
            monkeypatch,
            checks=[
                {"name": "提问量", "passed": True, "actual": 40},
                {"name": "无回答占比", "passed": True, "actual": 0.05},
            ],
            idle_attempts=25,
        )
        verdict = _by_flag("report_qa")
        assert verdict["state"] == STATE_PROMOTE_ELIGIBLE
        assert [check["name"] for check in verdict["checks"]] == ["提问量", "无回答占比"]

    def test_revoke_candidate_overrides_observing(self, monkeypatch):
        """转正判据未达标 + 近 90 天的新增提问低于死线 → 撤销候选（不是继续观察）。"""
        self._patch_summary(
            monkeypatch,
            checks=[{"name": "提问量", "passed": False, "actual": 0}],
            idle_attempts=verdicts_mod.QA_REVOKE_IDLE_ATTEMPTS - 1,
        )
        verdict = _by_flag("report_qa")
        assert verdict["state"] == STATE_REVOKE_CANDIDATE
        assert "新增提问" in verdict["reason"]

    def test_revoke_candidate_even_when_checks_pass_but_idle(self, monkeypatch):
        self._patch_summary(
            monkeypatch,
            checks=[{"name": "提问量", "passed": True, "actual": 30}],
            idle_attempts=0,
        )
        assert _by_flag("report_qa")["state"] == STATE_REVOKE_CANDIDATE


class TestRendering:
    def test_lines_include_check_name_and_actual(self, monkeypatch):
        from src.python.core import decision_ledger

        monkeypatch.setattr(
            decision_ledger,
            "fold_ledger",
            lambda *a, **k: {"directional_total": verdicts_mod.PROMOTE_DIRECTIONAL_SAMPLE, "alpha_mean": 0.02},
        )
        verdict = _by_flag("decision_reflection")
        (line,) = [item for item in format_verdict_lines([verdict]) if "decision_reflection" in item]
        for check in verdict["checks"]:
            assert check["name"] in line
            assert str(check["actual"]) in line

    def test_notices_empty_when_nothing_actionable(self):
        observing = [
            {"flag": "x", "label": "X", "state": STATE_OBSERVING, "reason": "", "checks": []},
            {"flag": "y", "label": "Y", "state": STATE_NO_READING, "reason": "", "checks": []},
        ]
        assert action_notices(observing) == []

    def test_notices_call_out_actionable_states(self):
        actionable = [
            {"flag": "x", "label": "X", "state": STATE_PROMOTE_ELIGIBLE, "reason": "", "checks": []},
            {"flag": "y", "label": "Y", "state": STATE_REVOKE_CANDIDATE, "reason": "", "checks": []},
            {"flag": "z", "label": "Z", "state": STATE_OBSERVING, "reason": "", "checks": []},
        ]
        notices = action_notices(actionable)
        assert len(notices) == 2
        assert any("可转正" in notice and "X" in notice for notice in notices)
        assert any("撤销候选" in notice and "Y" in notice for notice in notices)
        assert not any("Z" in notice for notice in notices)


class TestDoctorWiring:
    def test_doctor_prints_one_verdict_row(self):
        from src.python.core.doctor import GROUP_FEATURES
        from src.python.core.doctor import _check_experiment_verdicts

        (item,) = _check_experiment_verdicts()
        assert item["group"] == GROUP_FEATURES
        assert item["ok"] is True
        for flag in _flags():
            assert flag in item["message"]
