"""决策依据章的章头与绩效呈现：``build_headline`` 摘要文案、分持有期绩效
（``build_performance``）、样本不足时的结论口径，以及**双端同源**（同一份
``decision_basis_data`` 在 HTML 与 Excel 渲染出的标题/summary 一致，防一处写死）。

全部离线，账本一律指向 tmp_path。
"""

from __future__ import annotations


import pytest

from src.python.config.features import (
    reset_feature_flags,
)

from src.python.core import signal_ledger as sl
from src.python.report.decision_basis import (
    build_settlement_summary,
    BLOCK_HEADLINE_EMPTY,
    build_decision_basis_data,
    build_headline,
    build_performance,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


@pytest.fixture(autouse=True)
def _reset_features():
    reset_feature_flags()
    yield
    reset_feature_flags()


@pytest.fixture(autouse=True)
def _isolate_decision_ledger(tmp_path, monkeypatch):
    """决策账本隔离：结算摘要默认读账本，测试一律指向 tmp_path。"""
    import src.python.core.decision_ledger as dl

    monkeypatch.setattr(dl, "_DECISION_LEDGER_FILE", str(tmp_path / "decision_ledger.jsonl"))
    return str(tmp_path / "decision_ledger.jsonl")


@pytest.fixture
def ledger_path(tmp_path, monkeypatch):
    """信号账本隔离：读写一律指向 tmp_path，不碰真实 data/state/。"""
    path = str(tmp_path / "signal_ledger.jsonl")
    monkeypatch.setattr(sl, "_SIGNAL_LEDGER_FILE", path)
    return path


def _append(signal_type: str, *, report_date: str = "2026-11-01", **kwargs) -> None:
    sl.append_signal(
        signal_type=signal_type,
        report_date=report_date,
        rating=kwargs.pop("rating", "低估"),
        **kwargs,
    )


def _decision(settlements: dict[int, dict], **overrides) -> dict:
    """构造 fold_ledger 形态的决策行（仅结算摘要消费的字段）。"""
    base = {"decision_id": overrides.pop("decision_id", "d1"), "settlements": settlements}
    base.update(overrides)
    return base


class TestDecisionBasisHeadline:
    """章首三行摘要（`build_headline`）：可见性保障 + 双端同文 + 空态压缩。"""

    @staticmethod
    def _signals(*rows):
        base = {"name": "市场温度", "in_axis": True, "direction": 1, "basis": "price"}
        return [{**base, **r} for r in rows]

    def test_empty_contract_compresses_to_single_line(self):
        """信号/风险预算/纪律三者全不可用 → 压成一行空态（不留三行未就绪噪音）。"""
        lines = build_headline([], {"level_label": "无信号"}, {"available": False}, {"available": False})
        assert lines == [BLOCK_HEADLINE_EMPTY]
        assert "暂无可用数据" in lines[0]

    def test_three_lines_cover_signal_risk_discipline(self):
        """三行固定含义：有效信号+可信度 / 风险预算 / 纪律。"""
        lines = build_headline(
            self._signals({"direction": 1}, {"direction": 1}),
            {"level_label": "低"},
            {"available": True, "breached_count": 2},
            {"available": True, "items": [{"rule": "止盈"}], "regime_label": "正常"},
        )
        assert len(lines) == 3
        assert "有效 2/2" in lines[0] and "可信度 低" in lines[0]
        assert "超限 2 项" in lines[1]
        assert "触发 1 条" in lines[2] and "正常" in lines[2]

    def test_no_breach_and_no_trigger_use_negative_state_wording(self):
        """无超限/无触发用否定态文案，不写 0 项 0 条（与块内空态口径一致）。"""
        lines = build_headline(
            self._signals({"direction": 1}),
            {"level_label": "低"},
            {"available": True, "breached_count": 0},
            {"available": True, "items": [], "regime_label": "正常"},
        )
        assert lines[1] == "风险预算：未超限"
        assert lines[2] == "纪律：未触发"

    def test_unavailable_states_are_labelled(self):
        """未接入/未评估必须显式标注，不能留空行或伪造 0 值。"""
        lines = build_headline(
            self._signals({"direction": 1}),
            {"level_label": "低"},
            {"available": False},
            {"available": False, "items": []},
        )
        assert lines[1] == "风险预算：未评估"
        assert lines[2] == "纪律：未接入"

    def test_headline_enters_contract_and_html_renders_it(self, ledger_path):
        """契约带 headline，HTML 章首在折叠块之前渲染同一批行。"""
        from src.test.unit.report.test_action_html import _action_data, _render

        data = build_decision_basis_data()
        assert data["headline"]
        html = str(_render(_action_data(), decision_basis_data=data))
        assert 'id="decision-basis-headline"' in html
        head_start = html.index('id="decision-basis-headline"')
        fold_start = html.index('id="decision-basis"')
        assert head_start < fold_start, "章首摘要必须在折叠块之前（不展开也能读到）"
        for line in data["headline"]:
            assert line in html[head_start:fold_start]


class TestPerformanceByHorizon:
    """「我的建议历史表现」按视界聚合：计数、命中率门槛、均值超额、双端渲染。"""

    @staticmethod
    def _decision(direction, settlements, code="600519"):
        return {"code": code, "name": "演示品种", "direction": direction, "settlements": settlements}

    def test_empty_ledger_returns_no_rows(self):
        """账本为空 → 不造行（渲染层按无数据显示空态）。"""
        assert build_performance([]) == []

    def test_counts_hit_miss_flat_gap_by_horizon(self):
        """5 日：命中 1、未命中 1、平盘 1、缺口 1；方向性 = 命中 + 未命中。"""
        decisions = [
            self._decision(1, {"5": {"settle_date": "2026-11-01", "raw_return": 0.05, "bench_return": 0.02}}),
            self._decision(1, {"5": {"settle_date": "2026-11-01", "raw_return": -0.03, "bench_return": -0.01}}),
            self._decision(1, {"5": {"settle_date": "2026-11-01", "raw_return": 0.001, "bench_return": 0.0}}),
            self._decision(1, {"5": {"settle_date": "2026-11-01"}}),
        ]
        rows = {row["horizon"]: row for row in build_performance(decisions)}
        five = rows[5]
        assert five["settled"] == 4
        assert five["directional"] == 2
        assert five["hit"] == 1 and five["miss"] == 1
        assert five["flat"] == 1 and five["gap"] == 1

    def test_accuracy_label_requires_meaningful_sample(self):
        """方向性样本 < 20 → 「命中/方向性（样本不足）」；足够 → 百分比结论。"""
        small = self._decision(1, {"20": {"settle_date": "2026-11-01", "raw_return": 0.04}})
        assert build_performance([small])[0]["accuracy_label"] == "1/1（样本不足）"

        enough = [
            self._decision(1, {"60": {"settle_date": f"2026-10-{d:02d}", "raw_return": 0.04 if d % 2 else -0.04}})
            for d in range(1, 21)
        ]
        row = build_performance(enough)[0]
        assert row["directional"] == 20
        assert row["sample_sufficient"] is True
        assert row["accuracy_label"] == "50%"

    def test_mean_excess_ignores_missing_benchmark(self):
        """基准缺失的条目不入超额均值，但计入收益样本（口径与结算摘要一致）。"""
        decisions = [
            self._decision(1, {"5": {"settle_date": "2026-11-01", "raw_return": 0.10, "bench_return": 0.02}}),
            self._decision(1, {"5": {"settle_date": "2026-11-02", "raw_return": 0.50}}),
        ]
        row = build_performance(decisions)[0]
        assert row["settled"] == 2
        assert row["mean_excess_label"] == "+8.00%"

    def test_performance_enters_contract_and_both_channels(self):
        """契约带 performance 表并在 HTML 与 Excel 双端渲染同一批行。"""
        from openpyxl import Workbook

        from src.python.report.action_sheet import write_action_sheet
        from src.test.unit.report.test_action_html import _action_data, _render

        decisions = [self._decision(1, {"5": {"settle_date": "2026-11-01", "raw_return": 0.05, "bench_return": 0.02}})]
        settlement = build_settlement_summary(decisions)
        assert settlement["performance"] and settlement["performance_title"]

        data = build_decision_basis_data(settlement_decisions=decisions)
        assert data["settlement"]["performance"]

        html = str(_render(_action_data(), decision_basis_data=data))
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        write_action_sheet(ws, _action_data(), decision_basis_data=data)
        excel_text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
        for text in (html, excel_text):
            assert "我的建议历史表现（按视界）" in text
            assert "命中率" in text
        # 表头列数受页签可用列宽约束，超额列只保证在 HTML 端出现
        assert "均值超额" in html
        assert "settle-decisions" in html and "settle-decisions" in excel_text


class TestPerformanceVerdict:
    """按视界结论句：命中率 × 均值超额四象限 + 缺轴降级 + 样本不足标注。"""

    def test_four_quadrants(self):
        from src.python.report.decision_basis import performance_verdict

        assert performance_verdict(0.72, -0.65) == "方向命中但跑输基准"
        assert performance_verdict(0.72, 0.40) == "方向有效且跑赢基准"
        assert performance_verdict(0.40, 0.30) == "方向偏错但选品仍跑赢基准"
        assert performance_verdict(0.40, -0.20) == "方向与超额双弱"

    def test_missing_axis_downgrades_not_guesses(self):
        """任一轴缺数据时只说可得的那一轴，不拿单项冒充整体结论。"""
        from src.python.report.decision_basis import performance_verdict

        assert performance_verdict(None, 0.5) == "仅有超额：跑赢基准"
        assert performance_verdict(None, -0.5) == "仅有超额：跑输基准"
        assert "缺基准" in performance_verdict(0.6, None)
        assert performance_verdict(None, None) == "—"

    def test_small_sample_marked_as_reference_only(self, ledger_path):
        """方向性样本不足 → 结论后缀「样本不足，仅参考」，不把小样本当定论。"""
        decisions = [
            {
                "code": "600519",
                "name": "演示品种",
                "direction": 1,
                "settlements": {"5": {"settle_date": "2026-11-01", "raw_return": 0.05, "bench_return": 0.02}},
            }
        ]
        from src.python.report.decision_basis import build_performance

        row = build_performance(decisions)[0]
        assert row["sample_sufficient"] is False
        assert row["verdict_label"].endswith("（样本不足，仅参考）")

    def test_verdict_rendered_both_channels(self):
        """结论列在 HTML 与 Excel 双端同文出现。"""
        from openpyxl import Workbook

        from src.python.report.action_sheet import write_action_sheet
        from src.test.unit.report.test_action_html import _action_data, _render

        decisions = [
            {
                "code": "600519",
                "name": "演示品种",
                "direction": 1,
                "settlements": {"5": {"settle_date": "2026-11-01", "raw_return": 0.05, "bench_return": 0.08}},
            }
        ]
        data = build_decision_basis_data(settlement_decisions=decisions)
        verdict = data["settlement"]["performance"][0]["verdict_label"]
        html = str(_render(_action_data(), decision_basis_data=data))
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        write_action_sheet(ws, _action_data(), decision_basis_data=data)
        excel_text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
        for text in (html, excel_text):
            assert verdict in text
        assert "结论" in html  # HTML 单列
        assert "均值超额（结论）" in excel_text  # Excel 列宽 5，结论并入超额列


class TestBothEndsSameSource:
    """双端同源：同一份契约在 HTML/Excel 渲染出的标题与 summary 一致。"""

    def test_title_and_summary_in_both_channels(self, ledger_path):
        from openpyxl import Workbook

        from src.python.report.action_sheet import write_action_sheet
        from src.test.unit.report.test_action_html import _action_data, _render

        _append(sl.SIGNAL_MARKET_TEMPERATURE, subject="sh000300", detail={"sample_count": 90})
        data = build_decision_basis_data()
        html = _render(_action_data(), decision_basis_data=data)
        # HTML 端：#decision-basis 折叠块内含标题与单行 summary；章首摘要行在块外（上方）
        block = html.find(id="decision-basis")
        assert block is not None
        html_text = block.get_text()
        html_headline_span = str(html)[
            str(html).index('id="decision-basis-headline"') : str(html).index('id="decision-basis"')
        ]
        # Excel 端：顶部子块写同一份章首 headline（双端逐字一致）
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        write_action_sheet(ws, _action_data(), decision_basis_data=data)
        excel_text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
        for text in (html_text, excel_text):
            assert data["title"] in text
            assert "信号清单" in text
            assert "信号可信度" in text
        for line in data["headline"]:
            assert line in excel_text, f"Excel 章首摘要缺行：{line}"
            assert line in html_headline_span, f"HTML 章首摘要缺行：{line}"
        # HTML 折叠块自身的单行 summary 仍保留（点击标题）
        assert data["summary"] in html_text
        for text in (html_text, excel_text):
            assert "市场温度" in text  # 账本记录双端同现

    def test_risk_budget_rendered_both_channels(self, ledger_path):
        """风险预算三行字段双端同现，且与再平衡块文案互引不重复动作。"""
        from openpyxl import Workbook

        from src.python.report.action_sheet import write_action_sheet
        from src.test.unit.report.test_action_html import _action_data, _render

        data = build_decision_basis_data([{"name": "纳指ETF", "code": "513100", "market_value": 600.0}], 1000.0)
        block = _render(_action_data(), decision_basis_data=data).find(id="decision-basis")
        assert block is not None
        html_text = block.get_text()
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        write_action_sheet(ws, _action_data(), decision_basis_data=data)
        excel_text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
        for text in (html_text, excel_text):
            assert "风险预算" in text
            assert "单品种权重" in text and "行业权重" in text and "组合回撤" in text
            assert "未配置上限" in text  # 行业无配置键 → 显式标注，不按 0 显示
            assert "超限" in text
            assert "再平衡信号" in text  # 分工互引：超限动作不在本块

    def test_discipline_detail_rendered_both_channels(self, ledger_path):
        """纪律明细双端同现，且与交易纪律块文案互引不重复动作。"""
        from openpyxl import Workbook

        from src.python.report.action_sheet import write_action_sheet
        from src.test.unit.report.test_action_html import _action_data, _render

        data = build_decision_basis_data(
            [{"name": "纳指ETF", "code": "513100", "market_value": 900.0}],
            900.0,
            1000.0,
            discipline_signals=[
                {"rule": "止损线 -15%", "name": "纳指ETF", "code": "513100", "value": "-16.0%", "distance_pct": 1.0}
            ],
        )
        block = _render(_action_data(), decision_basis_data=data).find(id="decision-basis")
        assert block is not None
        html_text = block.get_text()
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        write_action_sheet(ws, _action_data(), decision_basis_data=data)
        excel_text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
        for text in (html_text, excel_text):
            assert "纪律明细" in text
            assert "止损线 -15%" in text
            assert "超线 1.00%" in text
            assert "下跌段" in text
            assert "交易纪律" in text  # 分工互引：动作不在本块

    def test_settlement_summary_rendered_both_channels(self, ledger_path):
        """结算摘要双端同现：批次/条数/未到期/超额，且指向历史决策复盘块。"""
        from openpyxl import Workbook

        from src.python.report.action_sheet import write_action_sheet
        from src.test.unit.report.test_action_html import _action_data, _render

        data = build_decision_basis_data(
            settlement_decisions=[
                _decision({5: {"settle_date": "2026-10-27", "raw_return": -0.02, "bench_return": -0.015}})
            ]
        )
        block = _render(_action_data(), decision_basis_data=data).find(id="decision-basis")
        assert block is not None
        html_text = block.get_text()
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        write_action_sheet(ws, _action_data(), decision_basis_data=data)
        excel_text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
        for text in (html_text, excel_text):
            assert "结算摘要" in text
            assert "2026-10-27" in text
            assert "-2.00%" in text and "-0.50%" in text
            assert "未到期" in text
            assert "历史决策复盘" in text

    def test_confidence_rendered_both_channels(self, ledger_path):
        from openpyxl import Workbook

        from src.python.report.action_sheet import write_action_sheet
        from src.test.unit.report.test_action_html import _action_data, _render

        data = build_decision_basis_data()  # 空账本 → unknown/no_signal
        block = _render(_action_data(), decision_basis_data=data).find(id="decision-basis")
        assert block is not None and "暂不可判" in block.get_text()
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        write_action_sheet(ws, _action_data(), decision_basis_data=data)
        excel_text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
        assert "暂不可判" in excel_text
