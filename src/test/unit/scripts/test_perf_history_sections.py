"""perf-history.py 趋势报告段落渲染测试（时间桶 / LLM 段落 / 版本对比 / 机器可读 / 异常与漂移段）。

从 `test_perf_history.py` 分出（按被测职责分片）：本文件覆盖趋势报告的各段落
渲染与机器可读载荷，统计工具与分组聚合留在主分片。
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts, pytest.mark.usefixtures("offline_external_sources")]


@pytest.fixture(name="mod")
def fixture_mod():
    """加载 `scripts/perf-history.py` 为可测模块。"""
    from src.test._script_loader import load_script

    return load_script("perf-history.py")


def _records(count: int = 3, version: str = "0.1.0", report_type: str = "full", start: int = 0) -> list[dict]:
    return [
        {
            "version": version,
            "report_type": report_type,
            "timestamp": f"2026-01-{start + i:02d} 10:00:00",
            "total_seconds": 10.0 + i,
            "holdings_count": 20,
            "phases": {"采集": 1.0 + i},
            "errors": [],
        }
        for i in range(count)
    ]


class TestTimeBuckets:
    """时段聚合（day/week/hour）。"""

    def test_bucket_key_shapes(self, mod):
        assert mod._bucket_key("2026-10-15T12:50:59", "day") == "2026-10-15"
        assert mod._bucket_key("2026-10-15T12:50:59", "hour") == "12"
        assert mod._bucket_key("2026-10-15T12:50:59", "week").startswith("2026-W")

    def test_bucket_key_malformed_timestamp(self, mod):
        assert mod._bucket_key("", "day") == "?"
        assert mod._bucket_key("not-a-date", "week") == "?"

    def test_bucket_lines_group_by_day(self, mod):
        """按日分桶：桶数 = 不同日期数，样本数合计 = 记录数。"""
        records = _records(2, start=1) + _records(2, start=1)
        lines = mod._bucket_lines(records, "day")
        assert "## 时段聚合（按日期）" in lines[0]
        rows = [ln for ln in lines if ln.startswith("| 2026-01-")]
        distinct_days = {r["timestamp"][:10] for r in records}
        assert len(rows) == len(distinct_days)
        assert sum(int(ln.split("|")[2]) for ln in rows) == len(records)

    def test_by_option_renders_bucket_section(self, mod):
        text = mod.build_trend_report(_records(3), by="hour")
        assert "## 时段聚合（按小时）" in text

    def test_no_by_option_skips_bucket_section(self, mod):
        assert "时段聚合" not in mod.build_trend_report(_records(3))


class TestLlmContextSection:
    """LLM 运行上下文段：等待/重试/降级/缓存/用量汇总。"""

    def _records_with_llm(self) -> list[dict]:
        records = _records(2)
        records[0]["llm"] = {
            "retry_count": 2,
            "retry_wait_seconds": 3.0,
            "pacing_wait_seconds": 1.5,
            "fallbacks": 1,
            "cache_hits": 3,
            "cache_misses": 1,
            "total_cost": 0.42,
            "providers": {"deepseek-main": 4},
            "models": {"deepseek-v4-flash": 4},
        }
        return records

    def test_context_section_rendered(self, mod):
        text = mod.build_trend_report(self._records_with_llm())
        assert "## LLM 运行上下文" in text
        assert "重试退避等待" in text
        assert "端点节流等待" in text
        assert "deepseek-main×4" in text

    def test_context_section_absent_without_data(self, mod):
        """无 llm 字段：完整报告范围明示缺数据提示，basic 范围无 LLM 语境不渲染段。"""
        text = mod.build_trend_report(_records(3))
        assert "暂无 LLM 上下文" in text
        basic_text = mod.build_trend_report(_records(3, report_type="basic"))
        assert "LLM 运行上下文" not in basic_text

    def test_context_aggregates_across_records(self, mod):
        records = self._records_with_llm()
        records[1]["llm"] = {"retry_count": 1, "retry_wait_seconds": 1.0}
        lines = mod._llm_context_lines(records)
        retry_row = next(ln for ln in lines if ln.startswith("| 重试次数 |"))
        assert "3" in retry_row

    def test_context_ignores_malformed_llm_field(self, mod):
        records = _records(2)
        records[0]["llm"] = "not-a-dict"
        assert mod._llm_context_lines(records) == []


class TestVersionCompare:
    """版本间对比：阶段级 delta 与变异系数判显著。"""

    def _two_versions(self) -> list[dict]:
        old = _records(4, version="0.1.0")
        new = _records(4, version="0.2.0")
        for r in new:
            r["phases"] = {"采集": 30.0}
            r["total_seconds"] = 30.0
        return old + new

    def test_compare_reports_both_versions(self, mod):
        cmp = mod._compare_versions(self._two_versions(), "0.1.0", "0.2.0")
        assert cmp["a"]["count"] == 4
        assert cmp["b"]["count"] == 4
        assert cmp["a"]["version"] == "0.1.0"
        assert cmp["b"]["version"] == "0.2.0"

    def test_compare_phase_delta_and_ratio(self, mod):
        cmp = mod._compare_versions(self._two_versions(), "0.1.0", "0.2.0")
        row = next(r for r in cmp["phases"] if r["name"] == "采集")
        # 基准版本阶段值为 1.0+i（i=0..3）→ 最近秩中位取第 2 位 = 2.0；对照版本固定 30.0
        assert row["a_median"] == pytest.approx(2.0)
        assert row["b_median"] == pytest.approx(30.0)
        assert row["delta"] == pytest.approx(28.0)
        assert row["ratio"] > 1

    def test_compare_marks_significant_beyond_noise(self, mod):
        """对照版本阶段耗时稳定且大幅上升 → 判显著。"""
        cmp = mod._compare_versions(self._two_versions(), "0.1.0", "0.2.0")
        row = next(r for r in cmp["phases"] if r["name"] == "采集")
        assert row["significant"] is True

    def test_compare_ignores_noise_band(self, mod):
        """两版本耗时分布重叠（差异在噪声带内）→ 不判显著。"""
        records = _records(4, version="0.1.0") + _records(4, version="0.2.0")
        cmp = mod._compare_versions(records, "0.1.0", "0.2.0")
        row = next(r for r in cmp["phases"] if r["name"] == "采集")
        assert row["significant"] is False

    def test_compare_unknown_version_yields_empty(self, mod):
        cmp = mod._compare_versions(_records(3), "9.9.9", "8.8.8")
        assert cmp["a"]["count"] == 0
        assert cmp["phases"] == []

    def test_compare_section_rendered(self, mod):
        text = mod.build_trend_report(self._two_versions(), compare=("0.1.0", "0.2.0"))
        assert "## 版本对比：0.1.0 → 0.2.0" in text
        assert "| 阶段 | 旧版中位 | 新版中位 | 变化 | 倍数 | 显著 |" in text

    def test_compare_section_absent_by_default(self, mod):
        assert "版本对比" not in mod.build_trend_report(_records(3))


class TestMachineReadable:
    """机读输出：JSON 与 CSV。"""

    def test_json_round_trips_records(self, mod):
        import json as _json

        records = _records(2)
        parsed = _json.loads(mod._machine_readable(records, "json"))
        assert parsed["records"] == records
        assert parsed["record_count"] == len(records)

    def test_json_summary_carries_computed_stats(self, mod):
        """信封 summary 与 Markdown 段同源：分位/归一/演进/漂移/离群/异常。"""
        import json as _json

        summary = _json.loads(mod._machine_readable(_records(3), "json"))["summary"]
        assert summary["total_seconds"]["count"] == 3
        assert summary["per_holding_median"] == pytest.approx(0.55)  # 10/20、11/20、12/20 的中位
        assert summary["version_evolution"][0]["count"] == 3
        assert summary["drift"] == []  # 样本 <6 不参与漂移
        assert summary["outliers"] == []
        assert summary["abnormal"] == []

    def test_csv_header_carries_new_dimensions(self, mod):
        header = mod._machine_readable(_records(1), "csv").strip().splitlines()[0]
        assert header.startswith("timestamp,version,report_type")
        for col in ("per_holding_seconds", "outlier", "slowest_phase", "errors_count"):
            assert col in header

    def test_csv_row_normalizes_and_flags_outlier(self, mod):
        records = _records(6)
        records[-1]["total_seconds"] = 6636.0
        lines = mod._machine_readable(records, "csv").strip().splitlines()
        outlier_cells = next(ln for ln in lines[1:] if "6636.0" in ln).split(",")
        assert outlier_cells[6] == "331.800"  # 秒/品种 = 6636 / 20
        assert outlier_cells[7] == "1"  # 离群标记
        assert outlier_cells[8] == "采集"  # 最慢阶段
        normal_cells = next(ln for ln in lines[1:] if "6636.0" not in ln).split(",")
        assert normal_cells[7] == "0"

    def test_csv_has_header_and_one_row_per_record(self, mod):
        records = _records(3)
        lines = mod._machine_readable(records, "csv").strip().splitlines()
        assert lines[0].startswith("timestamp,version,report_type")
        assert len(lines) == len(records) + 1

    def test_csv_row_carries_total_seconds(self, mod):
        records = _records(1)
        row = mod._machine_readable(records, "csv").strip().splitlines()[1]
        assert str(records[0]["total_seconds"]) in row


class TestSummaryAndOutlierK:
    """概览模式与可调离群系数。"""

    def test_summary_omits_group_details(self, mod):
        text = mod.build_trend_report(_records(4), summary=True)
        assert "## 总体分位概览（跨版本）" in text
        assert "概览模式" in text
        assert "## 0.1.0 / full" not in text

    def test_summary_keeps_outlier_and_tail_sections(self, mod):
        records = _records(6)
        records[-1]["total_seconds"] = 6636.0
        text = mod.build_trend_report(records, summary=True)
        assert "## 离群运行（稳健口径）" in text
        assert "## 尾部归因（最慢一次运行）" in text

    def test_default_mode_keeps_group_details(self, mod):
        assert "## 0.1.0 / full" in mod.build_trend_report(_records(3))

    def test_outlier_k_controls_sensitivity(self, mod):
        """系数越小越敏感：同一批样本在 k=1.0 下比 k=3.5 下标出更多离群。"""
        records = _records(10)
        records[-1]["total_seconds"] = 200.0
        strict = mod._outlier_records(records, 1.0)
        loose = mod._outlier_records(records, 3.5)
        assert len(strict) >= len(loose)

    def test_outlier_k_flows_into_report(self, mod):
        records = _records(10)
        records[-1]["total_seconds"] = 200.0
        text = mod.build_trend_report(records, outlier_k=1.0)
        assert "1.0 × 1.4826 × MAD" in text

    def test_robust_mean_only_shown_when_outlier_present(self, mod):
        """无离群时稳健均值与普通均值相同，不并列展示（避免冗余）。"""
        assert "稳健均值" not in mod.build_trend_report(_records(4))
        records = _records(6)
        records[-1]["total_seconds"] = 6636.0
        assert "稳健均值" in mod.build_trend_report(records)


class TestVersionEvolutionSection:
    """版本演进总表：首现时间排序、较上一版 delta/警示、归一化列。"""

    def _two_versions(self) -> list[dict]:
        old = _records(3, version="0.1.0")
        new = _records(3, version="0.2.0", start=10)
        for r in new:
            r["total_seconds"] = 40.0
        return old + new

    def test_rows_ordered_by_first_seen_with_empty_delta_for_first(self, mod):
        text = mod.build_trend_report(self._two_versions())
        assert "## 版本演进总表" in text
        lines = text.splitlines()
        i_old = next(i for i, ln in enumerate(lines) if ln.startswith("| 0.1.0 | full"))
        i_new = next(i for i, ln in enumerate(lines) if ln.startswith("| 0.2.0 | full"))
        assert i_old < i_new
        assert lines[i_old].rstrip().endswith("| — |")  # 同类型首版无对比

    def test_large_regression_marked_with_delta(self, mod):
        text = mod.build_trend_report(self._two_versions())
        line = next(ln for ln in text.splitlines() if "⚠变慢" in ln)
        assert "+29.0s" in line  # 中位 40.0 - 11.0
        assert "⚠变慢" in line

    def test_per_holding_column_rendered(self, mod):
        text = mod.build_trend_report(self._two_versions())
        line = next(ln for ln in text.splitlines() if ln.startswith("| 0.2.0 | full"))
        assert "2.000" in line  # 40s / 20 品种

    def test_single_report_type_keeps_type_column(self, mod):
        text = mod.build_trend_report(_records(3))
        assert "| 版本 | 报告类型 | 样本数 | 中位 | P95 | 中位秒/品种 | 较上一版中位 |" in text


class TestAbnormalSection:
    """异常运行专区：中断/非完成/带错误；干净数据整段省略。"""

    def test_absent_for_clean_records(self, mod):
        assert "异常运行" not in mod.build_trend_report(_records(4))

    def test_is_abnormal_record_rules(self, mod):
        assert not mod._is_abnormal_record({"status": "completed"})
        assert not mod._is_abnormal_record({})
        assert mod._is_abnormal_record({"interrupted_stage": "Excel 生成"})
        assert mod._is_abnormal_record({"status": "failed"})
        assert mod._is_abnormal_record({"errors": ["行情超时"]})

    def test_lists_interrupted_and_errored_runs(self, mod):
        records = _records(3)
        records[1]["status"] = "interrupted"
        records[1]["interrupted_stage"] = "Excel 生成"
        records[2]["errors"] = ["行情超时"]
        text = mod.build_trend_report(records)
        assert "## 异常运行" in text
        assert "| interrupted |" in text
        assert "| Excel 生成 |" in text
        assert "行情超时" in text


class TestDriftSection:
    """同版本漂移：时间对半中位差 + 噪声带显著性。"""

    def _drifting(self) -> list[dict]:
        records = _records(8)
        for i, r in enumerate(records):
            r["total_seconds"] = 20.0 if i < 4 else 60.0
        return records

    def test_absent_below_min_samples(self, mod):
        assert "同版本漂移" not in mod.build_trend_report(_records(5))

    def test_flags_within_version_regression(self, mod):
        text = mod.build_trend_report(self._drifting())
        assert "## 同版本漂移（渐进劣化检测）" in text
        row = next(ln for ln in text.splitlines() if "+40.0s" in ln)
        assert "| 是 |" in row  # 两半零方差 → 零噪声带 → 显著

    def test_flat_series_not_significant(self, mod):
        records = _records(8)
        for r in records:
            r["total_seconds"] = 20.0
        text = mod.build_trend_report(records)
        assert "否（噪声带内）" in text  # delta=0 不显著

    def test_drift_kept_in_summary_mode(self, mod):
        assert "同版本漂移" in mod.build_trend_report(self._drifting(), summary=True)


class TestGroupPercentileLines:
    """分组段内的「95% / 99% 完成时间」直给行。"""

    def test_group_renders_p95_p99_line(self, mod):
        text = mod.build_trend_report(_records(5))
        line = next(ln for ln in text.splitlines() if ln.startswith("- 95% 的报告在"))
        # 统一句式：两段都带全主语「N% 的报告在 … 内完成」（不省略第二段主语）
        assert "99% 的报告在" in line
        values = [float(part.split("**")[1].rstrip("s")) for part in line.split("，")]
        assert len(values) == 2
        assert values[0] <= values[1]

    def test_overview_wording_unified(self, mod):
        """概览口径行与分组行句式统一（95%/99% 各自带全主语与「该耗时内完成」）。"""
        text = mod.build_trend_report(_records(3))
        assert "P95 即 95% 的报告在该耗时内完成，P99 即 99% 的报告在该耗时内完成" in text

    def test_group_percentiles_within_group_range(self, mod):
        records = _records(7)
        text = mod.build_trend_report(records)
        line = next(ln for ln in text.splitlines() if ln.startswith("- 95% 的报告在"))
        p95, p99 = [float(part.split("**")[1].rstrip("s")) for part in line.split("，")]
        totals = [r["total_seconds"] for r in records]
        assert min(totals) <= p95 <= p99 <= max(totals)


def _cost_records() -> list[dict]:
    """跨三天含/不含 llm 费用的样本（day/hour 聚合共用）。"""
    return [
        {
            "version": "0.1.0",
            "report_type": "full",
            "timestamp": "2026-01-01 10:00:00",
            "total_seconds": 10.0,
            "llm": {"total_cost": 0.10},
        },
        {
            "version": "0.1.0",
            "report_type": "full",
            "timestamp": "2026-01-01 11:00:00",
            "total_seconds": 12.0,
            "llm": {"total_cost": 0.15},
        },
        {
            "version": "0.1.0",
            "report_type": "full",
            "timestamp": "2026-01-02 10:00:00",
            "total_seconds": 9.0,
            "llm": {"total_cost": 0.05},
        },
        {
            "version": "0.1.0",
            "report_type": "basic",
            "timestamp": "2026-01-03 10:00:00",
            "total_seconds": 11.0,
        },
    ]


class TestBucketCostAggregation:
    """--by 时段聚合的费用列与环比（费用趋势视图核心）。"""

    def test_cost_columns_and_per_bucket_sums(self, mod):
        """有费用样本时出费用合计/环比列，各时段求和、首档环比为破折号。"""
        text = "\n".join(mod._bucket_lines(_cost_records(), "day"))
        assert "费用合计" in text and "费用环比" in text
        day1 = next(ln for ln in text.splitlines() if ln.startswith("| 2026-01-01 "))
        day2 = next(ln for ln in text.splitlines() if ln.startswith("| 2026-01-02 "))
        day3 = next(ln for ln in text.splitlines() if ln.startswith("| 2026-01-03 "))
        assert "0.2500 | —" in day1, "首档无上期，费用合计为 0.10+0.15、环比为 —"
        assert "0.0500 | -0.2000" in day2, "环比 = 0.05 − 0.25"
        assert "0.0000 | -0.0500" in day3, "无 llm 记录的时段计零并参与环比"

    def test_last_bucket_delta_footer(self, mod):
        """末档 vs 前档提示行给出当期环比（趋势一眼可读）。"""
        text = "\n".join(mod._bucket_lines(_cost_records(), "day"))
        assert "**费用环比（末档 vs 前档）**：0.0500 → 0.0000（-0.0500）" in text

    def test_cost_columns_absent_without_cost_samples(self, mod):
        """范围内无费用样本时省略费用列（不制造全列噪音）。"""
        text = "\n".join(mod._bucket_lines(_records(3), "day"))
        assert "费用合计" not in text and "费用环比" not in text
        assert "| 时段 | 样本数 | 中位 | P95 | 最长 |" in text

    def test_hour_bucket_keeps_cost_crossing(self, mod):
        """hour 口径同样交叉费用（同一代码路径，覆盖键分支）。"""
        text = "\n".join(mod._bucket_lines(_cost_records(), "hour"))
        assert "费用合计" in text
        hour10 = next(ln for ln in text.splitlines() if ln.startswith("| 10 "))
        assert "0.1500" in hour10, "10 点档 = 0.10 + 0.05"


class TestLlmCostMachineData:
    """--json 费用字段：llm_cost 汇总与 --by 时段费用序列。"""

    def test_summary_carries_llm_cost_block(self, mod):
        import json as _json

        payload = _json.loads(mod._machine_readable(_cost_records(), "json"))
        cost = payload["summary"]["llm_cost"]
        assert cost["runs"] == 3
        assert cost["total"] == pytest.approx(0.30, abs=1e-6)
        assert cost["mean"] == pytest.approx(0.10, abs=1e-6)
        assert 0 < cost["median"] <= cost["max"]

    def test_summary_llm_cost_null_without_samples(self, mod):
        import json as _json

        payload = _json.loads(mod._machine_readable(_records(2), "json"))
        assert payload["summary"]["llm_cost"] is None

    def test_by_period_series_sorted_with_costs(self, mod):
        import json as _json

        payload = _json.loads(mod._machine_readable(_cost_records(), "json", by="day"))
        series = payload["summary"]["by_period"]
        buckets = [p["bucket"] for p in series]
        assert buckets == sorted(buckets), "时段键升序即时间序，可直接相邻差分"
        assert [p["total_cost"] for p in series] == pytest.approx([0.25, 0.05, 0.0])
        assert [p["runs"] for p in series] == [2, 1, 1]

    def test_by_period_null_without_by(self, mod):
        import json as _json

        payload = _json.loads(mod._machine_readable(_records(2), "json"))
        assert payload["summary"]["by_period"] is None

    def test_report_by_day_shows_cost_columns(self, mod):
        """整链：build_trend_report(--by day) 输出含费用列与环比的时段表。"""
        text = mod.build_trend_report(_cost_records(), by="day")
        assert "## 时段聚合（按日期）" in text
        assert "费用合计" in text and "费用环比（末档 vs 前档）" in text
