"""CLI `settle-decisions` 子命令处理器测试。

覆盖：开关关闭无感、默认视界透传、显式视界解析、非法视界输入退出码、
结算摘要打印。全程 mock 结算服务，不触网、不写真实账本。
"""

from __future__ import annotations

import argparse
from unittest.mock import patch

import pytest

from src.python.cli.cli import _EXIT_SEVERE, _EXIT_SUCCESS, _build_parser, _handle_settle_decisions

pytestmark = [pytest.mark.unit, pytest.mark.unit_cli]


def _args(*, report_date=None, horizons=None):
    return argparse.Namespace(report_date=report_date, horizons=horizons)


class TestSettleDecisionsParser:
    """子命令接线与参数面。"""

    def test_parser_exposes_subcommand(self):
        parser = _build_parser()
        args = parser.parse_args(["settle-decisions"])
        assert args.command == "settle-decisions"
        assert args.report_date is None
        assert args.horizons is None

    def test_parser_accepts_options(self):
        args = _build_parser().parse_args(["settle-decisions", "--report-date", "2026-11-02", "--horizons", "5,20"])
        assert args.report_date == "2026-11-02"
        assert args.horizons == "5,20"


class TestHandleSettleDecisions:
    """_handle_settle_decisions 委托。"""

    def test_flag_off_is_inert(self, capsys):
        with patch("src.python.core.decision_ledger.is_active", return_value=False):
            code = _handle_settle_decisions(_args(), {})
        assert code == _EXIT_SUCCESS
        assert "未开启" in capsys.readouterr().out

    def test_default_horizons_passed_through(self, capsys):
        captured: dict = {}

        def _fake(*, report_date, horizons=None, **kwargs):
            captured["report_date"] = report_date
            captured["horizons"] = horizons
            return {
                "settled": 2,
                "ids": ["a"],
                "deferred": 1,
                "skipped": 0,
                "summary": [
                    {"target_horizon": 5},
                    {"target_horizon": 20},
                ],
            }

        with (
            patch("src.python.core.decision_ledger.is_active", return_value=True),
            patch("src.python.report.decision_settlement.settle_pending_decisions", side_effect=_fake),
        ):
            code = _handle_settle_decisions(_args(report_date="2026-11-02"), {})
        assert code == _EXIT_SUCCESS
        from src.python.core import decision_ledger

        assert captured["report_date"] == "2026-11-02"
        assert captured["horizons"] == list(decision_ledger.SETTLE_HORIZONS)
        out = capsys.readouterr().out
        assert "[OK]" in out and "结算事件 2 条" in out and "[5, 20]" in out

    def test_explicit_horizons_parsed(self, capsys):
        captured: dict = {}

        def _fake(**kw):
            captured.update(kw)
            return {"settled": 0, "ids": [], "deferred": 0, "skipped": 0, "summary": []}

        with (
            patch("src.python.core.decision_ledger.is_active", return_value=True),
            patch("src.python.report.decision_settlement.settle_pending_decisions", side_effect=_fake),
        ):
            code = _handle_settle_decisions(_args(report_date="2026-11-02", horizons="5, 20"), {})
        assert code == _EXIT_SUCCESS
        assert captured["horizons"] == [5, 20]

    def test_invalid_horizons_exit_severe(self, capsys):
        with patch("src.python.core.decision_ledger.is_active", return_value=True):
            assert _handle_settle_decisions(_args(horizons="a,b"), {}) == _EXIT_SEVERE
            assert "--horizons 格式错误" in capsys.readouterr().out
            assert _handle_settle_decisions(_args(horizons=" , "), {}) == _EXIT_SEVERE
            assert "--horizons 为空" in capsys.readouterr().out
