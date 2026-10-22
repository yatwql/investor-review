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
        """接线守卫：凡是**调用** `aggregate_news` 的位置都必须经 `news_fetch_limits` 取预算。

        判据按「AST 调用关系」派生而非写死文件路径——新闻刷新曾从 `cache/operations.py`
        拆到 `cache/_cache_refresh.py`，写死路径的守卫会静默失效（CI portability 档才暴露）；
        另按文本匹配会把注释里的 `aggregate_news()` 也误算成调用点，故改用 AST Call。
        定义体模块（`fetcher/news.py` 包装器 / `providers/news_aggregator.py`）豁免：
        预算由调用方解析后传入。
        """
        import ast

        root = Path(PROJECT_ROOT) / "src" / "python"
        call_sites: list[str] = []
        for py in root.rglob("*.py"):
            rel = py.relative_to(PROJECT_ROOT).as_posix()
            text = py.read_text(encoding="utf-8")
            if "def aggregate_news(" in text:  # 聚合器定义体：预算由调用方传入
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError:  # pragma: no cover - 生产代码不应有语法错误
                continue
            calls = any(
                isinstance(node, ast.Call)
                and (node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", ""))
                in {"aggregate_news", "_aggregate_news"}
                for node in ast.walk(tree)
            )
            if not calls:
                continue
            call_sites.append(rel)
            assert "news_fetch_limits" in text, f"{rel} 调用聚合新闻但未接入抓取预算单源算式"
        assert call_sites, "未发现任何聚合新闻调用点（判据可能已失效：检查 aggregate_news 是否改名）"
