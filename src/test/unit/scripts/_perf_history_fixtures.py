"""`perf-history.py` 测试共用夹具（模块加载 fixture + 记录构造器）。

`test_perf_history.py`（统计工具/分组聚合）与 `test_perf_history_sections.py`
（趋势报告段落）按职责分片，但两侧原先各复制一份 `fixture_mod` 与 `_records`——
同一份记录形状改一处要改两遍，且容易漂移出只在一个文件里存在的差异（分片文件
结构相同、字段相同，差异只可能是漏改）。集中在此，各分片只保留自己的断言。

导入即生效：各分片顶部 ``from src.test.unit.scripts._perf_history_fixtures import
fixture_mod, _records  # noqa: F401``（`fixture_mod` 的夹具名为 ``mod``）。
"""

from __future__ import annotations

import pytest


@pytest.fixture(name="mod")
def fixture_mod():
    """加载 `scripts/perf-history.py` 为可测模块。"""
    from src.test._script_loader import load_script

    return load_script("perf-history.py")


def _records(count: int = 3, version: str = "0.1.0", report_type: str = "full", start: int = 0) -> list[dict]:
    """构造 count 条连续日期的性能记录（默认 full/basic 通用最小形状）。"""
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
