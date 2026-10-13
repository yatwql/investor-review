"""fetcher/news.py 的抓取预算单源算式（news_fetch_limits）单元测试。

验证 per_source 与 top_n 的解耦算式关系，并守卫「调用方不得各自内联」——
src/python 下不得再现第二处 `max(500, top_n*2)` 形态的内联计算。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import pytest

from src.python.core.constants import PROJECT_ROOT
from src.python.fetcher.news import news_fetch_limits

pytestmark = [pytest.mark.unit, pytest.mark.unit_news]


class TestNewsFetchLimits(unittest.TestCase):
    """news_fetch_limits 算式关系。"""

    def test_top_n_passthrough(self) -> None:
        """返回元组首项即入参 top_n（原样透传，类型归一 int）。"""
        for top_n in (1, 10, 42, 999):
            assert news_fetch_limits(top_n)[0] == top_n
        assert news_fetch_limits(7.0)[0] == 7

    def test_per_source_scales_with_top_n_and_floor(self) -> None:
        """per_source = max(保底, top_n×2)——放大关系与保底关系分别断言。"""
        from src.python.fetcher.news import _NEWS_PER_SOURCE_FLOOR

        for top_n in (1, 50, 200, 400, 10000):
            _, per_source = news_fetch_limits(top_n)
            assert per_source == max(_NEWS_PER_SOURCE_FLOOR, top_n * 2)
        # 保底生效区：放大值低于保底时取保底
        assert news_fetch_limits(10)[1] == _NEWS_PER_SOURCE_FLOOR
        # 放大生效区：高于保底后随 top_n 线性放大
        assert news_fetch_limits(1000)[1] == 2000

    def test_no_inline_formula_outside_single_source(self) -> None:
        """单源守卫：src/python 其余位置不得内联 per_source 的 max(500, …×2) 算式。"""
        root = Path(PROJECT_ROOT) / "src" / "python"
        offenders = []
        for py in root.rglob("*.py"):
            if py.name == "news.py":
                continue
            text = py.read_text(encoding="utf-8")
            if re.search(r"per_source\s*=\s*max\s*\(\s*500\s*,", text):
                offenders.append(str(py.relative_to(PROJECT_ROOT)))
        assert offenders == [], f"per_source 算式出现内联复制：{offenders}"

    def test_call_sites_use_single_source(self) -> None:
        """接线守卫：两处调用方（缓存层/报告层）均经 news_fetch_limits 取参。"""
        for rel in ("src/python/cache/operations.py", "src/python/report/news_correlation.py"):
            text = (Path(PROJECT_ROOT) / rel).read_text(encoding="utf-8")
            assert "news_fetch_limits" in text, f"{rel} 未接入抓取预算单源算式"
