"""测试：akshare 接口名兼容层 — `core/akshare_compat.py`

回归背景：akshare 会**就地重命名**导出接口且不留别名（已观测到四个：
（`tool_trade_date_hist_sina`→`calendar_trade_date_hist_sina`、
`stock_fund_flow_industry`→`stock_fund_flow_industry_ths`、
`news_cctv`→`alternative_news_cctv`、
`stock_sector_fund_flow_rank`→`stock_fund_flow_sector_rank_em`）。依赖声明是区间，
所以同一份代码必须同时跑在两种名字上；写死单一名字会让依赖解析到另一种名字的机器上该数据源
静默降级（CI 实测交易日历与行业资金流两条链路整条失效）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.python.core.akshare_compat import candidate_names, resolve

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

_SRC_PYTHON = Path(__file__).resolve().parents[3] / "src" / "python"


class _FakeAkshare:
    """akshare 替身：只带指定接口名，用于验证按候选链解析。"""

    def __init__(self, *names: str) -> None:
        for name in names:
            setattr(self, name, lambda _name=name, **_kw: f"called:{_name}")

    def __getattr__(self, name: str):  # 未设置的属性按真实模块语义抛 AttributeError
        raise AttributeError(name)


class TestCandidateNames:
    @pytest.mark.parametrize(
        "logical",
        [
            "tool_trade_date_hist_sina",
            "stock_fund_flow_industry",
            "news_cctv",
            "stock_sector_fund_flow_rank",
        ],
    )
    def test_renamed_interfaces_list_both_names(self, logical):
        """四个已改名接口的候选链都含旧名与新名，且旧名在首位（可用时行为不变）。"""
        names = candidate_names(logical)
        assert names[0] == logical
        assert len(names) >= 2, "改名后的接口必须同时登记新名"

    def test_unknown_name_passes_through(self):
        """未登记的接口名原样返回（不是白名单，只是别名表）。"""
        assert candidate_names("stock_financial_abstract") == ("stock_financial_abstract",)


class TestResolve:
    def test_prefers_old_name_when_both_exist(self):
        """新旧名并存时走旧名：同一函数的改名，优先保持既有行为。"""
        ak = _FakeAkshare("news_cctv", "alternative_news_cctv")
        assert resolve(ak, "news_cctv")() == "called:news_cctv"

    def test_falls_back_to_renamed_interface(self):
        """旧名不存在（改名后的 akshare）时解析到候选链里的下一个名字——不得因此让数据源静默失效。"""
        ak = _FakeAkshare("calendar_trade_date_hist_sina")
        assert resolve(ak, "tool_trade_date_hist_sina")() == "called:calendar_trade_date_hist_sina"

    def test_missing_everywhere_names_all_candidates(self):
        """候选链全缺时抛 AttributeError，并点名试过的名字（改名的可诊断信号）。"""
        ak = _FakeAkshare()
        with pytest.raises(AttributeError) as excinfo:
            resolve(ak, "stock_sector_fund_flow_rank")
        message = str(excinfo.value)
        for name in candidate_names("stock_sector_fund_flow_rank"):
            assert name in message

    def test_non_callable_attribute_is_skipped(self):
        """同名属性存在但不可调用（如模块常量）时继续沿候选链找可调用接口。"""
        ak = _FakeAkshare("stock_fund_flow_industry_ths")
        setattr(ak, "stock_fund_flow_industry", "not-callable")
        assert resolve(ak, "stock_fund_flow_industry")() == "called:stock_fund_flow_industry_ths"


class TestCallSitesUseCompatLayer:
    def test_no_direct_calls_to_renamed_interfaces(self):
        """已改名接口不得在调用点直接 `ak.<名>(` 硬引用（必须经 `resolve`）。

        回归面：直接写名时，在只有候选链另一个名字的机器上该行以 `AttributeError`
        被 `except Exception` 吞掉 → 数据源静默变空，报告照出、只是少了数据。
        """
        renamed = [
            name
            for logical in (
                "tool_trade_date_hist_sina",
                "stock_fund_flow_industry",
                "news_cctv",
                "stock_sector_fund_flow_rank",
            )
            for name in candidate_names(logical)
        ]
        offenders: list[str] = []
        for path in _SRC_PYTHON.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            for name in renamed:
                if re.search(rf"\bak\s*\.\s*{name}\s*\(", source):
                    offenders.append(f"{path.relative_to(_SRC_PYTHON.parents[1])}: ak.{name}(...)")
        assert not offenders, "以下调用点直接写死了可能被 akshare 改名的接口，应改用 resolve()：\n" + "\n".join(
            offenders
        )
