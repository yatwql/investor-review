"""测试：`_perf_history/report.py` 分支面 — 导入期路径自助修补、时段聚合缩容列、
跨币种费用环比省略、尾部归因样本不足跳过、版本对比空阶段段、数据新鲜度档位。

共享夹具与记录形状见 `_perf_history_fixtures`（同目录分片共用，避免漂移）。
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

import pytest
from src.test._script_loader import SCRIPTS_DIR, load_script
from src.test.unit.scripts._perf_history_fixtures import (  # noqa: F401 — 分片共享夹具
    _records,
    fixture_mod,
)


@pytest.fixture(name="report")
def fixture_report():
    """直接加载 `report.py`（`_format_bucket`/`_cost_delta` 是渲染内部件，不经入口再导出）。"""
    return load_script("_perf_history/report.py", module_name="_perf_history_report_branches")


pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


class TestImportPathSelfPatch:
    """`report.py` 导入期把项目根与自身目录补进 sys.path（脚本直跑时的导入面垫片）。"""

    def test_reload_inserts_project_root_and_own_dir(self):
        report_dir = SCRIPTS_DIR / "_perf_history"
        wanted = [str(SCRIPTS_DIR), str(report_dir)]
        saved = list(sys.path)
        try:
            sys.path[:] = [entry for entry in sys.path if entry not in wanted]
            module = load_script("_perf_history/report.py", module_name="_perf_history_report_path_probe")
            assert str(SCRIPTS_DIR) in sys.path, "缺项目根时须自行补入（`_perf_history.*` 导入面）"
            assert str(report_dir) in sys.path, "缺自身目录时须自行补入（同级模块导入面）"
            assert module._PROJECT_ROOT == str(SCRIPTS_DIR)
        finally:
            sys.path[:] = saved


class TestBucketClampColumn:
    """时段聚合的缩容列：只在范围内有并发计数样本时出现。"""

    @staticmethod
    def _with_clamp(count: int = 2, *, with_cost: bool = False) -> list[dict]:
        records = _records(count)
        for record in records:
            record["counters"] = {"concurrency_clamps": 2}
            if with_cost:
                record["llm"] = {"cost_by_currency": {"CNY": 0.10}}
        return records

    def test_clamp_column_rendered_without_cost_samples(self, mod):
        text = "\n".join(mod._bucket_lines(self._with_clamp(), "day"))
        assert "缩容" in text, "有并发计数样本时须出缩容列"
        assert "费用合计" not in text, "无费用样本时不制造费用列"
        rows = [ln for ln in text.splitlines() if ln.startswith("| 2026-01-")]
        assert rows and all(ln.endswith("| 2 |") for ln in rows), "各时段缩容次数落在末列"

    def test_empty_records_yield_no_bucket_section(self, mod):
        assert mod._bucket_lines([], "day") == []


class TestCostDeltaBranches:
    """费用单元格/环比的跨币种与零值降级。"""

    def test_all_zero_bucket_shows_local_cost_unit(self, report):
        cell = report._format_bucket({"CNY": 0.0})
        assert cell.endswith("0.0000") and "—" not in cell

    def test_cross_currency_delta_omitted(self, report):
        assert report._cost_delta({"CNY": 1.0}, {"USD": 2.0}) == "—"

    def test_cross_currency_footer_explains_omission(self, mod):
        records = _records(2)
        records[0]["llm"] = {"cost_by_currency": {"CNY": 0.10}}
        records[1]["llm"] = {"cost_by_currency": {"USD": 0.20}}
        text = "\n".join(mod._bucket_lines(records, "day"))
        assert "跨币种不可直接相减，已省略数值环比" in text


class TestTailAttributionSamples:
    """尾部归因的阶段样本门槛：阶段序列不足 3 次不参与 z 分数。"""

    def test_rare_phase_skipped_while_common_phase_kept(self, mod):
        records = _records(3)
        records[2]["phases"]["罕见阶段"] = 99.0
        lines = mod._tail_attribution_lines(records)
        text = "\n".join(lines)
        assert "罕见阶段" not in text, "只出现过 1 次的阶段无基线，必须跳过"
        assert "采集" in text

    def test_no_comparable_phase_returns_empty(self, mod):
        records = _records(3)
        for record in records[:2]:
            del record["phases"]
        assert mod._tail_attribution_lines(records) == []


class TestCompareLinesWithoutPhases:
    """两版本都无阶段样本时给出明示占位段，不渲染空表。"""

    def test_placeholder_when_both_versions_lack_phases(self, mod):
        records = _records(2, version="0.1.0") + _records(2, version="0.2.0", start=5)
        for record in records:
            del record["phases"]
        text = "\n".join(mod._compare_lines(records, "0.1.0", "0.2.0"))
        assert "_两版本均无阶段样本。_" in text
        assert "| 阶段 |" not in text


class TestFreshnessBranches:
    """数据新鲜度：解析失败降级原值；相对时长按分钟/小时分档。"""

    def test_unparsable_timestamp_shows_raw_value(self, mod):
        line = mod._freshness_line([{"timestamp": "2026-13-45 ???"}])
        assert line is not None
        assert "时间解析失败" in line and "2026-13-45" in line

    def test_just_now_within_a_minute(self, mod):
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        assert "（刚刚）" in mod._freshness_line([{"timestamp": stamp}])

    def test_minutes_bucket(self, mod):
        stamp = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        line = mod._freshness_line([{"timestamp": stamp}])
        assert "分钟前" in line and "小时前" not in line

    def test_hours_bucket(self, mod):
        stamp = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        assert "小时前" in mod._freshness_line([{"timestamp": stamp}])


class TestVersionEvolutionEmpty:
    """无记录时不渲染版本演进总表（避免空表标题）。"""

    def test_returns_empty_for_no_records(self, mod):
        assert mod._version_evolution_lines([]) == []
