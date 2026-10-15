"""perf-view.py 性能趋势查看测试（阶段统计合并 / 分组聚合 / 分位概览 / 趋势报告渲染）。

覆盖 `_mean`/`_min_max`/`_percentile` 的空输入降级与最近秩口径、`_total_summary`
的汇总字段、`_merge_phase_stats` 的跨记录聚合、`_group_records` 的类型过滤 + 截尾
+ 按时间排序，以及 `build_trend_report` 的空数据文案、总体分位概览（P95/P99）、
分组表头、阶段表与「最近 5 次」明细截断。
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts, pytest.mark.usefixtures("offline_external_sources")]


@pytest.fixture(name="mod")
def fixture_mod():
    """加载 `scripts/perf-view.py` 为可测模块。"""
    from src.test._script_loader import load_script

    return load_script("perf-view.py")


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


# ── 统计工具 ──


class TestStatsHelpers:
    """均值 / 极值的正常与空输入。"""

    def test_mean_of_values(self, mod):
        assert mod._mean([1.0, 2.0, 6.0]) == pytest.approx(3.0)

    def test_mean_of_empty_is_zero(self, mod):
        assert mod._mean([]) == 0.0

    def test_min_max(self, mod):
        assert mod._min_max([3.0, 1.0, 2.0]) == (1.0, 3.0)

    def test_min_max_of_empty_is_zero_pair(self, mod):
        assert mod._min_max([]) == (0.0, 0.0)


class TestPercentile:
    """最近秩分位数：口径（≥pct% 样本 ≤ 返回值）与边界。"""

    def test_nearest_rank_on_twenty_samples(self, mod):
        values = [float(i) for i in range(1, 21)]  # 1..20
        assert mod._percentile(values, 50) == 10.0
        assert mod._percentile(values, 95) == 19.0
        assert mod._percentile(values, 99) == 20.0

    @pytest.mark.parametrize("pct", [50, 90, 95, 99])
    def test_covers_at_least_pct_of_samples(self, mod, pct):
        """分位值必须让 ≥pct% 的样本落在其内（口径本身的可验证表述）。"""
        values = [float(i) for i in range(1, 101)]
        covered = sum(v <= mod._percentile(values, pct) for v in values)
        assert covered * 100 >= pct * len(values)

    @pytest.mark.parametrize("pct", [-10.0, 0.0, 100.0, 150.0])
    def test_out_of_range_pct_stays_within_min_max(self, mod, pct):
        values = [3.0, 1.0, 2.0]
        assert min(values) <= mod._percentile(values, pct) <= max(values)

    def test_empty_returns_zero(self, mod):
        assert mod._percentile([], 95) == 0.0

    def test_input_order_irrelevant(self, mod):
        values = [30.0, 10.0, 40.0, 20.0]
        assert mod._percentile(values, 95) == mod._percentile(sorted(values), 95) == 40.0


class TestTotalSummary:
    """总耗时汇总字段：平均/中位/分位/极值与空输入降级。"""

    def test_summary_of_known_totals(self, mod):
        records = [{"total_seconds": v} for v in (10.0, 20.0, 30.0, 40.0)]
        stat = mod._total_summary(records)
        assert stat["count"] == 4
        assert stat["avg"] == pytest.approx(25.0)
        assert stat["p50"] == 20.0
        assert stat["p95"] == 40.0
        assert stat["p99"] == 40.0
        assert stat["max"] == 40.0

    def test_percentiles_never_below_median(self, mod):
        records = [{"total_seconds": 10.0 + i} for i in range(10)]
        stat = mod._total_summary(records)
        assert stat["p50"] <= stat["p95"] <= stat["p99"] <= stat["max"]

    @pytest.mark.parametrize("records", [[], [{"total_seconds": None}, {}]])
    def test_empty_or_missing_totals_degrade_to_zero(self, mod, records):
        stat = mod._total_summary(records)
        assert stat["count"] == 0 or stat["p95"] == 0.0


class TestMergeBreakdownStats:
    """`_merge_breakdown_stats` 跨记录合并阶段细分。"""

    def test_merges_spans_across_records(self, mod):
        records = [
            {"breakdown": {"LLM+新闻": {"持仓体检报告": 10.0, "新闻获取": 4.0}}},
            {"breakdown": {"LLM+新闻": {"持仓体检报告": 20.0}}},
        ]
        stats = mod._merge_breakdown_stats(records)
        assert stats["LLM+新闻"]["持仓体检报告"]["avg"] == pytest.approx(15.0)
        assert stats["LLM+新闻"]["持仓体检报告"]["max"] == pytest.approx(20.0)
        assert stats["LLM+新闻"]["持仓体检报告"]["count"] == 2
        assert stats["LLM+新闻"]["新闻获取"]["count"] == 1

    @pytest.mark.parametrize(
        "records",
        [
            [],
            [{}],
            [{"breakdown": None}],
            [{"breakdown": "not-a-dict"}],
            [{"breakdown": {"LLM+新闻": "not-a-dict"}}],
            [{"breakdown": {"LLM+新闻": {"模块": "abc"}}}],
        ],
    )
    def test_missing_or_malformed_breakdown_ignored(self, mod, records):
        """旧记录（无 breakdown）与脏数据均不得报错。"""
        assert mod._merge_breakdown_stats(records) == {}

    def test_span_names_sorted_within_parent(self, mod):
        """子项按名称排序（与阶段表同口径，输出稳定可 diff）。"""
        records = [{"breakdown": {"LLM+新闻": {"新闻获取": 1.0, "持仓体检报告": 2.0}}}]
        names = list(mod._merge_breakdown_stats(records)["LLM+新闻"])
        assert names == sorted(names)


class TestRobustStats:
    """稳健统计：中位/MAD/离群判定/稳健均值/z 分数。"""

    def test_median_and_mad_of_known_values(self, mod):
        values = [1.0, 2.0, 3.0, 4.0, 100.0]
        assert mod._median(values) == 3.0
        assert mod._mad(values) == pytest.approx(1.0)

    def test_mad_is_robust_to_single_outlier(self, mod):
        """单条极端值对 MAD 的影响远小于对标准差的影响（选它做基准的理由）。"""
        base = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0]
        with_outlier = base + [6636.0]
        mad_shift = abs(mod._mad(with_outlier) - mod._mad(base))
        sd_shift = abs(mod._stdev(with_outlier) - mod._stdev(base))
        assert mad_shift < sd_shift / 100

    def test_outlier_detected_above_threshold(self, mod):
        values = [10.0, 11.0, 12.0, 13.0, 14.0, 6636.0]
        assert mod._is_outlier(6636.0, values) is True
        assert mod._is_outlier(14.0, values) is False

    def test_uniform_samples_never_flagged(self, mod):
        """MAD 为 0（样本高度一致）时不判离群，避免把正常抖动误标。"""
        values = [100.0, 100.0, 100.0, 100.0]
        assert mod._outlier_threshold(values) is None
        assert mod._is_outlier(100.0, values) is False

    def test_robust_mean_drops_outlier(self, mod):
        values = [10.0, 11.0, 12.0, 13.0, 14.0, 6636.0]
        assert mod._robust_mean(values) < mod._mean(values)
        assert mod._robust_mean(values) == pytest.approx(mod._mean([10.0, 11.0, 12.0, 13.0, 14.0]))

    def test_robust_mean_equals_mean_without_outlier(self, mod):
        values = [10.0, 11.0, 12.0, 13.0]
        assert mod._robust_mean(values) == pytest.approx(mod._mean(values))

    def test_z_scores_center_and_scale(self, mod):
        zs = mod._z_scores([1.0, 2.0, 3.0])
        assert sum(zs) == pytest.approx(0.0)
        assert zs[-1] > zs[0]

    def test_z_scores_of_constant_series_are_zero(self, mod):
        assert mod._z_scores([5.0, 5.0, 5.0]) == [0.0, 0.0, 0.0]

    def test_empty_inputs_degrade_to_zero(self, mod):
        assert mod._median([]) == 0.0
        assert mod._mad([]) == 0.0
        assert mod._outlier_threshold([]) is None
        assert mod._z_scores([]) == []


class TestOutlierFiltering:
    """`--exclude-outlier` 口径：剔除离群后统计。"""

    def _records_with_outlier(self) -> list[dict]:
        records = _records(6)
        records[-1]["total_seconds"] = 6636.0
        return records

    def test_filter_drops_outlier_record(self, mod):
        records = self._records_with_outlier()
        kept = mod._filter_records(records, None, None, exclude_outlier=True)
        assert len(kept) == len(records) - 1
        assert all(r["total_seconds"] < 1000 for r in kept)

    def test_filter_keeps_all_when_no_outlier(self, mod):
        records = _records(5)
        assert mod._filter_records(records, None, None, exclude_outlier=True) == records

    def test_outlier_records_lists_flagged_runs(self, mod):
        records = self._records_with_outlier()
        flagged = mod._outlier_records(records)
        assert [r["total_seconds"] for r in flagged] == [6636.0]


class TestMergePhaseStats:
    """`_merge_phase_stats` 跨记录合并。"""

    def test_merges_phase_values_across_records(self, mod):
        records = [
            {"phases": {"采集": 1.0, "渲染": 4.0}},
            {"phases": {"采集": 3.0}},
        ]
        stats = mod._merge_phase_stats(records)
        assert stats["采集"]["avg"] == pytest.approx(2.0)
        assert stats["采集"]["min"] == pytest.approx(1.0)
        assert stats["采集"]["max"] == pytest.approx(3.0)
        assert stats["采集"]["count"] == 2
        assert stats["渲染"]["count"] == 1

    def test_phase_names_sorted(self, mod):
        records = [{"phases": {"渲染": 1.0, "采集": 2.0, "LLM": 3.0}}]
        assert list(mod._merge_phase_stats(records)) == ["LLM", "渲染", "采集"]

    @pytest.mark.parametrize("phases", [{}, "not-a-dict"])
    def test_missing_or_malformed_phases_ignored(self, mod, phases):
        assert mod._merge_phase_stats([{"phases": phases}, {}]) == {}


# ── 分组聚合 ──


class TestGroupRecords:
    """`_group_records` 的过滤、截尾、排序与键。"""

    def test_groups_by_version_and_report_type(self, mod):
        records = _records(2, version="0.1.0") + _records(2, version="0.2.0", report_type="basic")
        groups = mod._group_records(records, None, None)
        assert set(groups) == {"0.1.0 / full", "0.2.0 / basic"}
        assert len(groups["0.1.0 / full"]) == 2

    def test_filters_by_report_type(self, mod):
        records = _records(2, report_type="full") + _records(3, report_type="basic")
        groups = mod._group_records(records, "basic", None)
        assert list(groups) == ["0.1.0 / basic"]
        assert len(groups["0.1.0 / basic"]) == 3

    def test_last_n_slices_before_grouping(self, mod):
        records = _records(5)
        groups = mod._group_records(records, None, 2)
        assert len(groups["0.1.0 / full"]) == 2
        assert [r["timestamp"] for r in groups["0.1.0 / full"]][-1] == records[-1]["timestamp"]

    def test_records_sorted_by_timestamp_within_group(self, mod):
        records = [
            {"version": "0.1.0", "report_type": "full", "timestamp": "2026-01-03 00:00:00"},
            {"version": "0.1.0", "report_type": "full", "timestamp": "2026-01-01 00:00:00"},
            {"version": "0.1.0", "report_type": "full", "timestamp": "2026-01-02 00:00:00"},
        ]
        groups = mod._group_records(records, None, None)
        stamps = [r["timestamp"] for r in groups["0.1.0 / full"]]
        assert stamps == sorted(stamps)

    def test_group_keys_sorted(self, mod):
        records = _records(1, version="0.9.0") + _records(1, version="0.10.0")
        assert list(mod._group_records(records, None, None)) == sorted(["0.9.0 / full", "0.10.0 / full"])

    def test_missing_fields_default_to_question_mark(self, mod):
        groups = mod._group_records([{"phases": {}}], None, None)
        assert list(groups) == ["? / ?"]


# ── 趋势报告 ──


class TestBuildTrendReport:
    """`build_trend_report` 的 Markdown 输出结构。"""

    def test_empty_records_render_placeholder(self, mod):
        text = mod.build_trend_report([])
        assert "**分组数**：0 组" in text
        assert "暂无性能历史数据" in text

    def test_header_counts_derived_from_input(self, mod):
        records = _records(4) + _records(2, report_type="basic")
        text = mod.build_trend_report(records)
        assert "**总记录数**：6 条" in text
        assert "**分组数**：2 组" in text

    def test_group_section_contains_counts_and_phase_table(self, mod):
        text = mod.build_trend_report(_records(3))
        assert "## 0.1.0 / full" in text
        assert "运行次数：**3**" in text
        assert "| 阶段 | 平均耗时 | 中位 | P95 | 最短 | 最长 | 次数 |" in text
        assert "| 采集 |" in text

    def test_detail_table_capped_at_five_runs(self, mod):
        text = mod.build_trend_report(_records(8))
        assert "最近 5 次运行明细" in text
        detail_rows = [ln for ln in text.splitlines() if ln.startswith("| 2026-01-")]
        assert len(detail_rows) == 5

    def test_detail_timestamp_keeps_whole_date_and_minute(self, mod):
        """时间列取前 16 位（日期+时:分），年份首位不得被截掉。"""
        text = mod.build_trend_report(_records(2))
        cells = [ln.split("|")[1].strip() for ln in text.splitlines() if ln.startswith("| 2026-")]
        assert cells
        assert all(len(cell) == 16 for cell in cells)
        assert not any(ln.startswith("| 6-") for ln in text.splitlines())

    def test_report_type_and_last_n_applied(self, mod):
        records = _records(4, report_type="full") + _records(4, report_type="basic")
        text = mod.build_trend_report(records, report_type="basic", last_n=2)
        assert f"**总记录数**：{len(records)} 条" in text  # 头部计数是输入总量，分组按过滤后
        assert "0.1.0 / basic" in text
        assert "0.1.0 / full" not in text
        assert "运行次数：**2**" in text


# ── 总体分位概览（P95/P99） ──


def _overview_row(text: str, label: str) -> list[str]:
    """取出分位概览表中指定口径的行单元格（无则返回空列表）。"""
    for line in text.splitlines():
        if line.startswith(f"| {label} |"):
            return [cell.strip() for cell in line.strip().strip("|").split("|")]
    return []


class TestOverviewSection:
    """总体分位概览：P95/P99 报告生成耗时的表结构、行拆分与过滤口径。"""

    def test_percentile_columns_rendered(self, mod):
        text = mod.build_trend_report(_records(4))
        assert "## 总体分位概览（跨版本）" in text
        assert "| 口径 | 样本数 | 平均 | 中位 | P95 | P99 | 最长 |" in text

    def test_total_row_count_and_percentile_ordering(self, mod):
        records = _records(6)
        row = _overview_row(mod.build_trend_report(records), "合计（当前口径）")
        assert len(row) == 8  # 口径/样本数/平均/中位/P95/P99/最长/中位秒品种
        assert int(row[1]) == len(records)
        seconds = [float(cell.rstrip("s")) for cell in row[3:7]]  # 中位/P95/P99/最长
        assert seconds == sorted(seconds)
        assert float(row[7]) > 0  # 中位秒/品种（规模归一化）

    def test_single_report_type_renders_only_total_row(self, mod):
        text = mod.build_trend_report(_records(3, report_type="full"))
        assert _overview_row(text, "full") == []
        assert _overview_row(text, "合计（当前口径）")

    def test_rows_split_by_report_type_when_multiple(self, mod):
        records = _records(2, report_type="full") + _records(3, report_type="basic")
        text = mod.build_trend_report(records)
        assert int(_overview_row(text, "full")[1]) == 2
        assert int(_overview_row(text, "basic")[1]) == 3
        assert int(_overview_row(text, "合计（当前口径）")[1]) == len(records)

    def test_overview_follows_report_type_and_last_n(self, mod):
        records = _records(4, report_type="full") + _records(4, report_type="basic")
        text = mod.build_trend_report(records, report_type="basic", last_n=2)
        assert int(_overview_row(text, "合计（当前口径）")[1]) == 2
        assert _overview_row(text, "full") == []

    def test_empty_records_skip_overview(self, mod):
        assert "总体分位概览" not in mod.build_trend_report([])

    def test_small_sample_note_rendered_for_low_n(self, mod):
        """小样本提示：n<20 时告知最近秩分位趋近最大值。"""
        text = mod.build_trend_report(_records(4))
        assert "参考性有限" in text
        assert "样本数 <20" in text

    def test_no_small_sample_note_at_sufficient_n(self, mod):
        assert "参考性有限" not in mod.build_trend_report(_records(21))


class TestBreakdownSection:
    """分组段的「阶段细分」表：新观测面可见，旧记录不渲染。"""

    def test_breakdown_table_rendered_when_present(self, mod):
        records = _records(2)
        records[0]["breakdown"] = {"LLM+新闻": {"持仓体检报告": 40.0}}
        text = mod.build_trend_report(records)
        assert "**阶段细分**" in text
        assert "| 父阶段 | 子项 | 平均耗时 | 最长 | 次数 |" in text
        assert "| LLM+新闻 | 持仓体检报告 |" in text

    def test_breakdown_table_absent_for_legacy_records(self, mod):
        """无 breakdown 的历史记录：不出现空表（保持旧输出形状）。"""
        assert "阶段细分" not in mod.build_trend_report(_records(3))


class TestOutlierAndTailSections:
    """离群段与尾部归因段：渲染与口径。"""

    def _records_with_outlier(self) -> list[dict]:
        records = _records(6)
        records[-1]["total_seconds"] = 6636.0
        records[-1]["phases"] = {"采集": 6600.0}
        return records

    def test_outlier_section_lists_flagged_run(self, mod):
        text = mod.build_trend_report(self._records_with_outlier())
        assert "## 离群运行（稳健口径）" in text
        assert "6636.0s" in text

    def test_outlier_section_absent_without_outlier(self, mod):
        assert "离群运行" not in mod.build_trend_report(_records(5))

    def test_tail_attribution_ranks_slowest_phase_first(self, mod):
        text = mod.build_trend_report(self._records_with_outlier())
        assert "## 尾部归因（最慢一次运行）" in text
        rows = [ln for ln in text.splitlines() if ln.startswith("| 采集 |")]
        assert rows, "尾部归因表应含最慢阶段行"
        assert "6600.0s" in rows[0]

    def test_tail_attribution_needs_enough_samples(self, mod):
        """样本过少（<3）时不做归因（z 分数无意义）。"""
        assert "尾部归因" not in mod.build_trend_report(_records(2))

    def test_exclude_outlier_changes_overview_sample_count(self, mod):
        records = self._records_with_outlier()
        with_outlier = _overview_row(mod.build_trend_report(records), "合计（当前口径）")
        without = _overview_row(mod.build_trend_report(records, exclude_outlier=True), "合计（当前口径）")
        assert int(without[1]) == int(with_outlier[1]) - 1


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
        """旧记录无 llm 字段：不渲染空段。"""
        assert "LLM 运行上下文" not in mod.build_trend_report(_records(3))

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
        values = [float(part.split("**")[1].rstrip("s")) for part in line.split("，")]
        assert len(values) == 2
        assert values[0] <= values[1]

    def test_group_percentiles_within_group_range(self, mod):
        records = _records(7)
        text = mod.build_trend_report(records)
        line = next(ln for ln in text.splitlines() if ln.startswith("- 95% 的报告在"))
        p95, p99 = [float(part.split("**")[1].rstrip("s")) for part in line.split("，")]
        totals = [r["total_seconds"] for r in records]
        assert min(totals) <= p95 <= p99 <= max(totals)
