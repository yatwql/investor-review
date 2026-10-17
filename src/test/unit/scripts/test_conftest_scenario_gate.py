# -*- coding: utf-8 -*-
"""conftest scenario 门禁 marker 双向校验的回归测试。

背景（全仓测试语义审计发现）：scenario/regression（P2 门禁）/integration 三模式
按裸 `scenario` marker 筛选，而仓内裸 scenario 靠基类/模块级佩戴隐式继承、此前无
收集期硬校验——只带子域 marker 的新场景文件会静默漏出回归门禁。conftest 的
`pytest_collection_modifyitems` 增加双向拦截后，本文件直接驱动该钩子函数验证四类
判定（目录内缺基础 marker / 目录外带基础 marker / 合规通过 / Windows 反斜杠路径
归一），不 mock 钩子本体，断言其真实抛射行为。

运行：
  pytest src/test/unit/scripts/test_conftest_scenario_gate.py -v
"""

from __future__ import annotations

import pytest

from src.test import conftest

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


class _StubItem:
    """pytest Collection 项的最小替身：仅需 fspath/name/marker 查询三接口。"""

    def __init__(self, path: str, name: str, markers: list[str]) -> None:
        self.fspath = path
        self.name = name
        self._markers = markers

    def get_closest_marker(self, marker: str):
        return object() if marker in self._markers else None

    def iter_markers(self):
        return [type("_M", (), {"name": m})() for m in self._markers]


def _run(items: list[_StubItem]) -> None:
    conftest.pytest_collection_modifyitems(config=None, items=items)  # type: ignore[arg-type]


class TestScenarioGateEnforcement:
    """双向校验：目录内必带裸 scenario；带裸 scenario 必属 scenario 目录。"""

    def test_scenario_dir_item_without_base_marker_raises(self):
        item = _StubItem(
            "/repo/src/test/scenario/security/test_flows.py",
            "test_only_subdomain",
            ["scenario_security"],
        )
        with pytest.raises(pytest.UsageError, match="scenario 门禁 marker 违规"):
            _run([item])

    def test_base_marker_outside_scenario_dir_raises(self):
        item = _StubItem(
            "/repo/src/test/unit/report/test_stray.py",
            "test_stray_base_marker",
            ["unit_report", "scenario"],
        )
        with pytest.raises(pytest.UsageError, match="scenario 门禁 marker 违规"):
            _run([item])

    def test_compliant_pairs_pass(self):
        in_dir = _StubItem(
            "/repo/src/test/scenario/basic/test_core.py",
            "test_ok_in_dir",
            ["scenario", "scenario_basic"],
        )
        elsewhere = _StubItem(
            "/repo/src/test/unit/core/test_models.py",
            "test_ok_unit",
            ["unit_core"],
        )
        assert _run([in_dir, elsewhere]) is None

    def test_win_path_separators_are_normalized(self):
        # Windows 采集路径为反斜杠：归一后仍识别 scenario 目录 → 合规不抛
        item = _StubItem(
            "C:\\repo\\src\\test\\scenario\\perf\\test_e2e_perf.py",
            "test_win_path",
            ["scenario", "scenario_perf"],
        )
        assert _run([item]) is None

    def test_subdomain_marker_alone_does_not_satisfy_base(self):
        # 子域 marker 不豁免基础要求（防「只挂 scenario_* 即入子域报表、
        # 却被门禁选择器漏收」的原始漂移形态）
        item = _StubItem(
            "/repo/src/test/scenario/resilience/test_zero_cost.py",
            "test_zero_cost",
            ["scenario_zero_cost", "scenario_resilience"],
        )
        with pytest.raises(pytest.UsageError, match="scenario 门禁 marker 违规"):
            _run([item])
