"""HTML 渲染前置装配（`report/_html_render_context.py`）——阶段契约与降级口径。

`write_html_report` 把派生量装配下沉到本模块后，装配本身的契约（喂了什么、装出什么、
缺席时降级成什么）不再由写出函数的用例隐式覆盖，故在此直测三层：

  - `_build_panel_views`：三个面板视图契约缺席 → `None`（章内区块隐藏，逐字节回退），
    且三槽互不牵连（只给一个契约时另两槽仍为 `None`）；
  - `_build_data_source_bundle`：状态摘要四元组按位序落位，历史状态/矩阵/说明表各取对应构造器；
  - `_prepare_render_context`：可见性三元组、数据源状态、因子名映射、代码掩码一次装齐；
    入参按来源域分组（两组 dataclass + `details`），因子名导入失败降级为空映射且留 debug 记录。
"""

from __future__ import annotations

import logging
import sys
import types

import pytest

from src.python.report import _html_render_context as ctx_mod

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _visibility(**overrides) -> ctx_mod._VisibilityInputs:
    """可见性域入参（默认全缺席/全关，按需覆盖）。"""
    base = {
        "order": [],
        "manager_analysis": None,
        "overlap_matrix": None,
        "concentration_analysis": None,
        "style_analysis": None,
        "include_news": False,
        "llm_enabled_flag": False,
        "enable_llm": False,
        "enable_news": False,
        "enable_fund_deep_analysis": False,
        "enable_history": False,
        "enable_portfolio_evolution": False,
        "enable_action": False,
        "style_factor_data": None,
        "position_relationship_data": None,
        "evolution_data": None,
        "holding_change_data": None,
        "schedule_replay_data": None,
        "enable_fundamental_snapshot": False,
        "financial_report_digest_data": None,
        "financial_indicator_data": None,
    }
    base.update(overrides)
    return ctx_mod._VisibilityInputs(**base)


def _data_source(**overrides) -> ctx_mod._DataSourceInputs:
    """数据源域入参（默认全缺席，按需覆盖）。"""
    base = {
        "a_indices": None,
        "us_indices": None,
        "penetration": None,
        "penetration_profit_ok": False,
        "penetration_dividend_ok": False,
        "perf_data": None,
        "holdings": [],
        "cat_dividend_ok": False,
        "history_data": None,
    }
    base.update(overrides)
    return ctx_mod._DataSourceInputs(**base)


#: 各协作方返回值哨兵（对象以免断言退化成「值相等」）
_VIS_TRIPLE = ({"sec": 1}, {"sec": True}, "sv_fn_sentinel")
_STATUS_QUAD = ("status_summary", "status_penetration", "status_perf", "status_category")
_HISTORY = object()
_MATRIX = object()
_CATALOG = object()
_MASK_MAP = {"600519": "000XXX"}
_DISABLED = {"llm_macro": "关闭"}
_FACTOR_NAMES = {"roe": "净资产收益率"}


@pytest.fixture
def deps(monkeypatch):
    """把 `_prepare_render_context` 的全部协作方换成记录桩，返回调用记录。

    打桩点选在**被导入模块的属性**上（函数内 `from X import f` 于调用时读 `X.f`），
    指向上游 provider 另立同名函数不会生效。
    """
    from src.python.analysis import style_factor_regression
    from src.python.config import anonymizer
    from src.python.llm import skeleton
    from src.python.report import data_source_matrix, html_writer_nav, html_writer_status

    calls: list[tuple[str, tuple, dict]] = []

    def _stub(name: str, ret):
        def _f(*a, **k):
            calls.append((name, a, k))
            return ret

        return _f

    monkeypatch.setattr(html_writer_nav, "_compute_section_visibility", _stub("visibility", _VIS_TRIPLE))
    monkeypatch.setattr(skeleton, "get_llm_chapter_disabled", _stub("disabled", _DISABLED))
    monkeypatch.setattr(html_writer_status, "_build_data_status_sections", _stub("status", _STATUS_QUAD))
    monkeypatch.setattr(html_writer_status, "_build_history_data_status", _stub("history", _HISTORY))
    monkeypatch.setattr(data_source_matrix, "build_data_source_matrix", _stub("matrix", _MATRIX))
    monkeypatch.setattr(data_source_matrix, "build_data_source_catalog", _stub("catalog", _CATALOG))
    monkeypatch.setattr(anonymizer, "get_anonymization_mode", _stub("anon_mode", "summary"))
    monkeypatch.setattr(anonymizer, "build_code_display_map", _stub("display_map", _MASK_MAP))
    monkeypatch.setattr(style_factor_regression, "FACTOR_NAMES", _FACTOR_NAMES)
    return calls


def _calls(calls, name: str) -> list[tuple[tuple, dict]]:
    return [(a, k) for n, a, k in calls if n == name]


def _prepare(calls=None, **kwargs):
    """调用 `_prepare_render_context`：未显式给出分组入参时用默认空组。"""
    kwargs.setdefault("visibility", _visibility())
    kwargs.setdefault("data_source", _data_source())
    return ctx_mod._prepare_render_context(**kwargs)


class TestPanelViews:
    """面板视图装配：契约缺席即隐藏区块，槽位互不牵连。"""

    def test_absent_contracts_yield_none_triplet(self):
        assert ctx_mod._build_panel_views(None, None, None) == (None, None, None)

    def test_each_slot_builds_independently(self, monkeypatch):
        from src.python.report import event_impact_panel, holding_change_panel, schedule_replay_panel

        sentinels = {"holding": object(), "event": object(), "replay": object()}
        monkeypatch.setattr(holding_change_panel, "build_holding_change_view", lambda data: sentinels["holding"])
        monkeypatch.setattr(event_impact_panel, "build_event_impact_view", lambda data: sentinels["event"])
        monkeypatch.setattr(schedule_replay_panel, "build_schedule_replay_view", lambda data: sentinels["replay"])

        only_replay = ctx_mod._build_panel_views(None, None, {"days": 5})
        assert only_replay == (None, None, sentinels["replay"])

        all_three = ctx_mod._build_panel_views({"a": 1}, {"b": 2}, {"c": 3})
        assert all_three == (sentinels["holding"], sentinels["event"], sentinels["replay"])


class TestDataSourceBundle:
    """数据源状态装配：四元组按位序落位，其余三项各取对应构造器。"""

    def test_bundle_packs_status_history_matrix_catalog(self, deps):
        bundle = ctx_mod._build_data_source_bundle(
            _data_source(
                a_indices=["000001"],
                us_indices=["DJI"],
                penetration={"p": 1},
                penetration_profit_ok=True,
                penetration_dividend_ok=False,
                perf_data={"perf": 1},
                holdings=[{"code": "600519"}],
                cat_dividend_ok=True,
                history_data={"points": []},
            )
        )

        assert bundle.status == _STATUS_QUAD
        assert bundle.history is _HISTORY
        assert bundle.matrix is _MATRIX
        assert bundle.catalog is _CATALOG

    def test_status_sections_receive_forwarded_inputs(self, deps):
        holdings = [{"code": "600519"}]
        ctx_mod._build_data_source_bundle(
            _data_source(
                a_indices=["000001"],
                us_indices=["DJI"],
                penetration={"p": 1},
                penetration_profit_ok=True,
                penetration_dividend_ok=False,
                perf_data={"perf": 1},
                holdings=holdings,
                cat_dividend_ok=True,
                history_data={"points": []},
            )
        )

        (args, _kwargs_seen) = _calls(deps, "status")[0]
        assert args == (["000001"], ["DJI"], {"p": 1}, True, False, {"perf": 1}, holdings, True)
        assert _calls(deps, "history")[0][0] == ({"points": []},)


class TestRenderContext:
    """渲染上下文：四类派生量一次装齐，任一环节失败按原语义降级。"""

    def test_context_fields_assembled(self, deps):
        ctx = _prepare(visibility=_visibility(style_factor_data={"rows": []}))

        assert isinstance(ctx, ctx_mod._RenderContext)
        assert (ctx.section_numbers, ctx.section_visible_dict, ctx.sv_fn) == _VIS_TRIPLE
        assert ctx.status == _STATUS_QUAD
        assert ctx.data_status_history is _HISTORY
        assert ctx.data_source_matrix is _MATRIX
        assert ctx.data_source_catalog is _CATALOG
        assert ctx.factor_names == _FACTOR_NAMES
        assert ctx.code_display_map == _MASK_MAP
        assert _calls(deps, "anon_mode")[0][1] == {}

    def test_visibility_inputs_forwarded_positionally_and_by_keyword(self, deps):
        order = [{"key": "summary"}]
        _prepare(
            visibility=_visibility(
                order=order,
                manager_analysis={"m": 1},
                style_analysis={"s": 1},
                include_news=True,
                llm_enabled_flag=True,
                enable_action=True,
            )
        )

        (args, kwargs_seen) = _calls(deps, "visibility")[0]
        assert args == (order, {"m": 1}, None, None, {"s": 1}, True, True)
        assert kwargs_seen["enable_action"] is True

    def test_code_display_map_prefers_details_over_holdings(self, deps):
        details = [{"code": "600519", "name": "贵州茅台"}]
        _prepare(
            visibility=_visibility(),
            data_source=_data_source(holdings=[{"code": "000001"}]),
            details=details,
        )

        (args, _kw) = _calls(deps, "display_map")[0]
        assert args[0] is details
        assert args[1] == "summary"

    def test_code_display_map_falls_back_to_holdings(self, deps):
        holdings = [{"code": "000001"}]
        _prepare(data_source=_data_source(holdings=holdings), details=None)

        (args, _kw) = _calls(deps, "display_map")[0]
        assert args[0] is holdings

    def test_factor_names_skipped_without_style_data(self, deps):
        ctx = _prepare(visibility=_visibility(style_factor_data=None))

        assert ctx.factor_names == {}
        # 无风格因子数据 → 不装配因子名，但其余装配不受影响
        assert ctx.code_display_map == _MASK_MAP

    def test_factor_names_import_failure_degrades_with_debug_log(self, deps, monkeypatch, caplog):
        stub = types.ModuleType("src.python.analysis.style_factor_regression")  # 无 FACTOR_NAMES
        monkeypatch.setitem(sys.modules, "src.python.analysis.style_factor_regression", stub)

        with caplog.at_level(logging.DEBUG, logger="invest"):
            ctx = _prepare(visibility=_visibility(style_factor_data={"rows": []}))

        assert ctx.factor_names == {}
        assert any("因子中文名映射不可用" in rec.getMessage() for rec in caplog.records)

    def test_llm_chapter_disabled_forwarded_only_when_llm_enabled(self, deps):
        _prepare(visibility=_visibility(enable_llm=True, llm_enabled_flag=True))
        assert _calls(deps, "disabled")[0][1] == {}
        assert _calls(deps, "visibility")[0][1]["llm_module_disabled"] == _DISABLED

        deps.clear()
        _prepare(visibility=_visibility(enable_llm=False))
        assert _calls(deps, "disabled") == []
        assert _calls(deps, "visibility")[0][1]["llm_module_disabled"] is None
