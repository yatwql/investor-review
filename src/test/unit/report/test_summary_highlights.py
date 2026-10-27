"""摘要区「首页执行摘要卡」单元测试。

覆盖三面：
  1. ``report/summary_highlights.py::build_summary_highlights`` 派生契约
     （无上期快照降级 / 指标环比派生 / 关键变化 Top N 排序与截断 / 集中度行级降级）
  2. ``fetcher/history_diff.py`` 总盈亏率环比计算与 ``report/_snapshot.py`` diff 透传
  3. ``partials/summary_section.html`` 渲染开/关态（开关关闭时块零输出——关态产物逐字节不变）

需求 ``R-OUT-15``（摘要区首页执行摘要卡）。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.fetcher.history_diff import HistoryDiff
from src.python.report.html_jinja_env import _ENV
from src.python.report.summary_highlights import build_summary_highlights
from src.python.schemas.history import AccountSnapshot, SnapshotData, SnapshotHolding

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _diff_dict(**overrides) -> dict:
    """构造 capture_snapshot 注入的 diff 契约 dict（含常见字段默认值）。"""
    base = {
        "is_first_check": False,
        "days_since_last_report": 7,
        "baseline_timestamp": "20260109T213000",
        "baseline_trading_day": "2026-01-09",
        "baseline_generated_at": "2026-01-09 21:30",
        "total_value_diff": 1000.0,
        "total_value_diff_pct": 1.5,
        "total_pnl_diff": 500.0,
        "total_pnl_pct_diff": 0.8,
        "added": [],
        "removed": [],
        "increased": [],
        "decreased": [],
    }
    base.update(overrides)
    return base


def _item(name: str, code: str, action: str, value_diff: float, shares_diff: float = 100.0) -> dict:
    return {"name": name, "code": code, "action": action, "shares_diff": shares_diff, "value_diff": value_diff}


class TestBuildSummaryHighlights:
    """派生契约：降级判据 / 指标环比 / Top N 排序。"""

    def test_none_pipeline_returns_none(self):
        """无管线数据（首次运行/非正式持仓源）→ None，渲染层整块隐藏。"""
        assert build_summary_highlights(None) is None

    def test_first_check_returns_none(self):
        """is_first_check（无上期快照可对比）→ None。"""
        assert build_summary_highlights({"diff": _diff_dict(is_first_check=True)}) is None

    def test_missing_diff_key_returns_none(self):
        """diff 键缺席（首次运行快照路径不注入）→ None。"""
        assert build_summary_highlights({"other": 1}) is None

    def test_metric_rows_derived(self):
        """指标环比行：总市值/总收益率直通，持仓数环比 = 新增数 - 清仓数。"""
        pd = {
            "diff": _diff_dict(
                added=[_item("新A", "110011", "新增", 15000.0)],
                removed=[_item("旧B", "161725", "清仓", -8000.0), _item("旧C", "000001", "清仓", -2000.0)],
            )
        }
        h = build_summary_highlights(pd)
        assert h is not None
        assert h["total_value_diff"] == 1000.0
        assert h["total_value_diff_pct"] == 1.5
        assert h["total_pnl_pct_diff"] == 0.8
        assert h["holding_count_delta"] == 1 - 2
        assert h["added_count"] == 1
        assert h["removed_count"] == 2
        assert h["days_since_last_report"] == 7

    def test_changes_sorted_by_abs_value(self):
        """关键变化按 |value_diff| 降序（新增/清仓/大幅加减仓自然靠前）。"""
        pd = {
            "diff": _diff_dict(
                added=[_item("新A", "110011", "新增", 5000.0)],
                removed=[_item("旧B", "161725", "清仓", -30000.0)],
                increased=[_item("基金C", "510300", "加仓", 800.0)],
                decreased=[_item("基金D", "159915", "减仓", -20000.0)],
            )
        }
        h = build_summary_highlights(pd)
        assert [c["name"] for c in h["changes"]] == ["旧B", "基金D", "新A", "基金C"]
        assert h["change_total"] == 4

    def test_changes_capped_and_total_kept(self):
        """超过上限时 changes 截断、change_total 保留全量条数（渲染层写「等 N 项」）。"""
        pd = {
            "diff": _diff_dict(
                increased=[_item(f"基金{i}", f"5103{i}", "加仓", float(i * 100)) for i in range(8)],
            )
        }
        h = build_summary_highlights(pd, max_changes=5)
        assert len(h["changes"]) == 5
        assert h["change_total"] == 8
        assert h["changes"][0]["name"] == "基金7"  # 最大 |value_diff| 排首

    def test_hhi_row_level_degradation(self):
        """快照差异摘要缺席/不可得 → hhi_change=None（行级降级，整块仍渲染）。"""
        diff_only = {"diff": _diff_dict()}
        assert build_summary_highlights(diff_only)["hhi_change"] is None
        unavailable = {"diff": _diff_dict(), "snapshot_diff_data": {"available": False}}
        assert build_summary_highlights(unavailable)["hhi_change"] is None
        available = {"diff": _diff_dict(), "snapshot_diff_data": {"available": True, "hhi_change": 0.01}}
        assert build_summary_highlights(available)["hhi_change"] == 0.01

    def test_baseline_labels_passed_through(self):
        """对比基准标注（所属交易日 + 生成时间）从 diff 透传到契约（比对对象可见）。"""
        h = build_summary_highlights({"diff": _diff_dict()})
        assert h is not None
        assert h["baseline_trading_day"] == "2026-01-09"
        assert h["baseline_generated_at"] == "2026-01-09 21:30"

    def test_baseline_labels_default_empty(self):
        """diff 缺少基线标注键（旧口径/异常降级）→ 默认空串，渲染层省略该行。"""
        diff = _diff_dict(baseline_trading_day="", baseline_generated_at="")
        h = build_summary_highlights({"diff": diff})
        assert h is not None
        assert h["baseline_trading_day"] == ""
        assert h["baseline_generated_at"] == ""

    def test_qdii_note_fields_passthrough(self):
        """QDII 口径注字段（金额 / 是否滞后）从 diff 透传到契约。"""
        h = build_summary_highlights({"diff": _diff_dict(qdii_value_diff=-557.29, qdii_lagged=True)})
        assert h is not None
        assert h["qdii_value_diff"] == -557.29
        assert h["qdii_lagged"] is True

    def test_qdii_note_fields_default_when_absent(self):
        """diff 无 QDII 键（旧口径）→ 金额 0 且非滞后，渲染层据此省略该注。"""
        h = build_summary_highlights({"diff": _diff_dict()})
        assert h is not None
        assert h["qdii_value_diff"] == 0.0
        assert h["qdii_lagged"] is False


class TestPnlPctDiffChain:
    """总盈亏率环比：HistoryDiff.compute 计算 → capture_snapshot diff dict 透传。"""

    @staticmethod
    def _snap(pnl: float, pnl_pct: float, value: float) -> SnapshotData:
        holding = SnapshotHolding(code="110011", name="基金A", shares=100.0, cost_price=10.0, market_value=value)
        account = AccountSnapshot(account_name="账户1", holdings=(holding,))
        return SnapshotData(
            accounts=(account,),
            total_value=value,
            total_cost=1000.0,
            total_pnl=pnl,
            total_pnl_pct=pnl_pct,
            timestamp="2026-01-10T15:00:00",
        )

    def test_compute_total_pnl_pct_diff(self):
        """总盈亏率环比 = 本期 total_pnl_pct - 上期（百分点口径，四舍五入 4 位）。"""
        new = self._snap(pnl=200.0, pnl_pct=20.0, value=1200.0)
        old = self._snap(pnl=100.0, pnl_pct=10.0, value=1100.0)
        diff = HistoryDiff.compute(new, old)
        assert diff.total_pnl_pct_diff == pytest.approx(10.0)

    def test_snapshot_diff_dict_passthrough(self):
        """capture_snapshot 注入的 diff dict 含 total_pnl_pct_diff 键（渲染数据源单点）。"""
        import inspect

        from src.python.report import _snapshot

        src = inspect.getsource(_snapshot.capture_snapshot)
        assert '"total_pnl_pct_diff"' in src


class TestSummarySectionTemplate:
    """模板渲染：开关开态渲染 / 关态零输出 / 集中度行级省略。"""

    @staticmethod
    def _render(highlights: dict | None) -> str:
        tpl = _ENV.get_template("partials/summary_section.html")
        return tpl.render(
            summary_highlights_data=highlights,
            section_numbers={"summary": 1},
            now="2026-01-10 15:00",
            trading_day="2026-01-10",
            categories={},
            update_status=None,
            total_mv=1100.0,
            total_cost=1000.0,
            total_profit=100.0,
            total_profit_rate=10.0,
            total_today_profit=0.0,
            today_profit_rate=0.0,
            a_indices=[],
            us_indices=[],
            data_unavailable=False,
            flow_display=None,
            market_temperature=None,
            data_status_summary=None,
            render_data_status=lambda _d: "",
            render_back_to_top=lambda: "",
        )

    def test_highlights_rendered_when_present(self):
        """契约存在 → 本期要点块渲染，含环比行与关键变化条目。"""
        h = build_summary_highlights(
            {
                "diff": _diff_dict(added=[_item("新A", "110011", "新增", 15000.0)]),
                "snapshot_diff_data": {"available": True, "hhi_change": -0.0123},
            }
        )
        html = self._render(h)
        assert "本期要点" in html
        assert "新A" in html
        assert "集中度环比（HHI）" in html
        assert "距上次报告 7 天" in html
        assert "对比基准：交易日 2026-01-09 · 报告生成 2026-01-09 21:30" in html

    def test_baseline_line_omitted_when_labels_absent(self):
        """基线标注缺失（空串）→ 对比基准行省略，其余照常渲染。"""
        diff = _diff_dict(baseline_trading_day="", baseline_generated_at="")
        html = self._render(build_summary_highlights({"diff": diff}))
        assert "本期要点" in html
        assert "对比基准" not in html

    def test_off_state_renders_nothing(self):
        """开关关闭（契约 None）→ 块零输出，首屏与既有产物逐字节一致。"""
        html = self._render(None)
        assert "本期要点" not in html
        assert "环比" not in html

    def test_hhi_row_omitted_when_unavailable(self):
        """hhi_change=None → 集中度行省略，其余环比行照常。"""
        h = build_summary_highlights({"diff": _diff_dict()})
        html = self._render(h)
        assert "本期要点" in html
        assert "集中度环比（HHI）" not in html

    def test_overflow_note_rendered(self):
        """变化条数超上限 → 渲染「等共 N 项变动」提示。"""
        pd = {
            "diff": _diff_dict(
                increased=[_item(f"基金{i}", f"5103{i}", "加仓", float(i * 100)) for i in range(7)],
            )
        }
        html = self._render(build_summary_highlights(pd, max_changes=5))
        assert "等共 7 项变动" in html

    def test_qdii_note_rendered_when_present(self):
        """环比含 QDII 净值变动 → 渲染口径注（金额 + T-1 滞后标注）。"""
        diff = _diff_dict(qdii_value_diff=-557.29, qdii_lagged=True)
        html = self._render(build_summary_highlights({"diff": diff}))
        assert "含 QDII 官方净值变动 -557.29 元" in html
        assert "T-1 口径，滞后一个交易日" in html

    def test_qdii_note_omitted_when_absent(self):
        """无 QDII 变动（键缺席/金额 0）→ 口径注省略，其余照常渲染。"""
        html = self._render(build_summary_highlights({"diff": _diff_dict()}))
        assert "本期要点" in html
        assert "QDII 官方净值变动" not in html


class TestQdiiLaggedValueDiff:
    """环比中 QDII 净值变动分项（``_snapshot._classify_qdii_value_diff``）。"""

    @staticmethod
    def _detail(code: str, name: str, mv: float, nav_date: str):
        from types import SimpleNamespace

        return SimpleNamespace(code=code, name=name, market_value=mv, nav_date=nav_date)

    @staticmethod
    def _old(holdings) -> SnapshotData:
        return SnapshotData(
            accounts=(AccountSnapshot(account_name="全部", holdings=tuple(holdings)),),
            total_value=sum(h.market_value for h in holdings),
            total_cost=0.0,
            total_pnl=0.0,
            timestamp="2026-01-09T15:00:00",
        )

    @patch("src.python.core.trading_calendar.get_last_trading_day", return_value="2026-01-12")
    def test_qdii_subtotal_and_lagged_flag(self, mock_td):
        """QDII 分项 = 各 QDII 品种市值差之和；净值日期早于 T → 滞后口径 True。"""
        from src.python.report._snapshot import _classify_qdii_value_diff

        old = self._old(
            [
                SnapshotHolding(
                    code="017730", name="嘉实全球产业升级股票(QDII)A", shares=1.0, cost_price=1.0, market_value=29044.75
                ),
                SnapshotHolding(code="600900", name="长江电力", shares=1.0, cost_price=1.0, market_value=26415.0),
            ]
        )
        details = [
            self._detail("017730", "嘉实全球产业升级股票(QDII)A", 28373.06, "2026-01-09"),
            self._detail("600900", "长江电力", 26442.0, "2026-01-12"),
        ]
        diff, lagged = _classify_qdii_value_diff(details, old)
        assert diff == pytest.approx(-671.69)
        assert lagged is True

    @patch("src.python.core.trading_calendar.get_last_trading_day", return_value="2026-01-12")
    def test_no_qdii_returns_zero(self, mock_td):
        """无 QDII 持仓 → (0.0, False)，渲染层据此省略口径注。"""
        from src.python.report._snapshot import _classify_qdii_value_diff

        details = [self._detail("600900", "长江电力", 26442.0, "2026-01-12")]
        assert _classify_qdii_value_diff(details, None) == (0.0, False)
