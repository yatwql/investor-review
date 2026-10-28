"""perf-history.py 性能趋势查看测试（阶段统计合并 / 分组聚合 / 分位概览 / 趋势报告渲染）。

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
        """子项按平均耗时降序（最慢在前；此 fixture 下字母序恰为相反序，口径可区分）。"""
        records = [{"breakdown": {"LLM+新闻": {"新闻获取": 3.0, "持仓体检报告": 2.0}}}]
        names = list(mod._merge_breakdown_stats(records)["LLM+新闻"])
        assert names == ["新闻获取", "持仓体检报告"]

    def test_legacy_merged_span_is_renamed_not_mixed(self, mod):
        """跨版本键名：旧「合并段」带显式标记单列，不与拆分后的新子项混算。

        判定口径：合并段（一次计时覆盖两个子项）与后续逐个新子项量级不等价，
        静默并名会让拆前后对拍的均值失去意义。
        """
        records = [
            {"breakdown": {"数据准备": {"财报摘要与指标": 6.4}}},
            {"breakdown": {"数据准备": {"财报摘要": 0.2, "财务指标": 0.1}}},
        ]
        stats = mod._merge_breakdown_stats(records)["数据准备"]
        legacy_name = mod._LEGACY_BREAKDOWN_ALIASES["财报摘要与指标"]
        assert legacy_name in stats, "旧键必须有明确可见的别名，不能静默消失"
        assert stats[legacy_name]["avg"] == pytest.approx(6.4)
        assert stats["财报摘要"]["avg"] == pytest.approx(0.2), "新子项均值只取自身样本"
        assert "财报摘要与指标" not in stats


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
        """阶段按中位降序（最慢在前；字母序为 LLM/渲染/采集，与降序可区分）。"""
        records = [{"phases": {"渲染": 1.0, "采集": 2.0, "LLM": 3.0}}]
        assert list(mod._merge_phase_stats(records)) == ["LLM", "采集", "渲染"]

    @pytest.mark.parametrize("phases", [{}, "not-a-dict"])
    def test_missing_or_malformed_phases_ignored(self, mod, phases):
        assert mod._merge_phase_stats([{"phases": phases}, {}]) == {}


# ── 分组聚合 ──


class TestVersionFilter:
    """`version` 前缀过滤（CLI `--version` 参数的实现层）。"""

    def test_filter_by_version_prefix(self, mod):
        records = [
            {"version": "0.13.4-dev", "report_type": "full"},
            {"version": "0.13.3", "report_type": "full"},
            {"version": "0.9.9", "report_type": "full"},
        ]
        hit = mod._filter_records(records, None, None, version="0.13.4")
        assert [r["version"] for r in hit] == ["0.13.4-dev"]
        prefix2 = mod._filter_records(records, None, None, version="0.13")
        assert [r["version"] for r in prefix2] == ["0.13.4-dev", "0.13.3"]
        assert mod._filter_records(records, None, None, version="9") == []

    def test_filter_version_applies_after_report_type(self, mod):
        records = [
            {"version": "0.1.0", "report_type": "full"},
            {"version": "0.1.0", "report_type": "basic"},
            {"version": "0.2.0", "report_type": "basic"},
        ]
        kept = mod._filter_records(records, "basic", None, version="0.1.0")
        assert [r["report_type"] for r in kept] == ["basic"]

    def test_group_records_transmits_version(self, mod):
        records = _records(2, version="0.1.0") + _records(2, version="0.2.0")
        groups = mod._group_records(records, None, None, version="0.2.0")
        assert list(groups) == ["0.2.0 / full"]


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

    def test_group_order_follows_first_run_time_not_version_string(self, mod):
        """组间按首次运行时间升序（最新组在末）；版本号字符串序不作数（0.9 > 0.10）。"""
        records = [
            {"version": "0.9.0", "report_type": "full", "timestamp": "2026-01-05 00:00:00"},
            {"version": "0.10.0", "report_type": "full", "timestamp": "2026-01-01 00:00:00"},
        ]
        assert list(mod._group_records(records, None, None)) == ["0.10.0 / full", "0.9.0 / full"]

    def test_group_order_stable_tiebreak_by_key(self, mod):
        """首次运行时间相同（同批写入）时按组键字典序稳定排序。"""
        records = _records(1, version="0.9.0") + _records(1, version="0.10.0")
        assert list(mod._group_records(records, None, None)) == ["0.10.0 / full", "0.9.0 / full"]

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
        assert "| 阶段 | 平均耗时 | 中位 | P95 | 最短 | 最长 | 次数 | 占比 |" in text
        assert "| 采集 |" in text
        assert "占比 = 阶段均值 ÷ 组平均总耗时" in text

    def test_version_filter_scopes_groups_and_header(self, mod):
        """`--version` 前缀过滤：头部明示筛选条件，组范围随之收窄。"""
        records = _records(2, version="0.1.0") + _records(2, version="0.2.0")
        text = mod.build_trend_report(records, version="0.2")
        assert "**版本筛选**：0.2（前缀匹配）" in text
        assert "0.1.0 / full" not in text
        assert "0.2.0 / full" in text

    def test_freshness_line_from_latest_timestamp(self, mod):
        """头部数据新鲜度：最新记录时间戳原值必在；相对时长随当下演进，不断言具体值。"""
        text = mod.build_trend_report(_records(2))
        line = next(ln for ln in text.splitlines() if "数据新鲜度" in ln)
        assert line.startswith("**数据新鲜度**：最新记录 2026-01")
        assert "（" in line

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
        """无 breakdown 的完整报告组：不出现空表，渲染缺数据提示行。"""
        text = mod.build_trend_report(_records(3))
        assert "| 父阶段 |" not in text
        assert "暂无阶段细分" in text

    def test_breakdown_hint_skipped_for_non_full_group(self, mod):
        """basic 组本无 LLM/新闻细分：不显示缺数据提示。"""
        assert "暂无阶段细分" not in mod.build_trend_report(_records(3, report_type="basic"))


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
