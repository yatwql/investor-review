"""HTML 报告内容渲染器的降级与开关分支。

覆盖每个子渲染器「失败只降级本块」的兜底语义（数据面异常不得中断整份报告）、
候选基金比较的无候选告警，以及 LLM 契约折叠块与模块状态的装配：

- `_render_*` 系列异常 → 返回空结构并写 warning，不向上抛
- 候选基金比较：available=False → prog.warn 点名 comparison_candidates
- 新闻无数据 → 空列表 + 默认 meta；有数据 → 透传条数
- `_with_contract_blocks` / `_render_llm_content_section`：正文剥离契约行 + 追折叠块
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from src.python.report import html_renderers as hr

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class _RecordingProgress:
    """记录 info/ok/warn 文本的进度报告器替身。"""

    def __init__(self) -> None:
        self.infos: list[str] = []
        self.oks: list[str] = []
        self.warns: list[str] = []

    def info(self, message: str) -> None:
        self.infos.append(message)

    def ok(self, message: str) -> None:
        self.oks.append(message)

    def warn(self, message: str) -> None:
        self.warns.append(message)


class _Holding:
    """最小持仓替身（is_fund 只看 name/code/account）。"""

    def __init__(self, code: str, name: str, account: str = "主账户") -> None:
        self.code = code
        self.name = name
        self.account = account


def _detail(code: str, market_value: float):
    from src.python.report.market_value import DetailRow

    return DetailRow(
        account="主账户",
        name=code,
        code=code,
        price=1.0,
        shares=market_value,
        market_value=market_value,
        cost=market_value,
        profit=0.0,
        profit_rate=0.0,
        today_profit=0.0,
    )


def _fund_payload(name: str) -> dict:
    from src.test.helpers import recent_holdings_period

    return {
        "name": name,
        "holdings": [{"name": "贵州茅台", "code": "600519", "ratio": 9.0}],
        "date": recent_holdings_period(),
    }


def test_index_section_reuses_prefetched_indices() -> None:
    """预取指数存在 → 不再发起行情请求，列表按固定指数顺序产出。"""
    prog = _RecordingProgress()
    a_idx = {"sh000001": {"name": "上证指数", "price": 3100, "change_pct": 0.5}}
    us_idx = {"dji": {"name": "道琼斯", "price": 38000, "change_pct": -0.2}}

    with patch.object(hr, "fetch_indices", side_effect=AssertionError("不应重复取数")):
        a_indices, us_indices, a_list, us_list = hr._render_index_section(prog, a_idx, us_idx)

    assert a_indices == a_idx
    assert us_indices == us_idx
    assert len(a_list) == 1
    assert a_list[0] == {"name": "上证指数", "price": 3100, "change": 0, "change_pct": 0.5}
    assert us_list == []  # 美股固定代码是 gb_* 前缀，dji 不在取数域内
    assert "正在获取市场指数..." not in prog.infos


class TestFundPerformanceSection:
    """候选基金比较三态：available / 无候选（warn） / 开关关闭（None）。"""

    def test_available_candidate_marks_ok(self) -> None:
        prog = _RecordingProgress()
        with (
            patch.object(hr, "_build_perf_data", return_value=[{"code": "110020"}]),
            patch.object(hr, "build_candidate_compare_data", return_value={"available": True, "rows": []}),
        ):
            perf, candidate = hr._render_fund_performance_section([], [], prog)

        assert perf == [{"code": "110020"}]
        assert candidate == {"available": True, "rows": []}
        assert prog.oks == ["候选基金比较数据构建完成"]
        assert prog.warns == []

    def test_switch_on_without_candidates_warns_config_key(self) -> None:
        prog = _RecordingProgress()
        with (
            patch.object(hr, "_build_perf_data", return_value=[]),
            patch.object(hr, "build_candidate_compare_data", return_value={"available": False}),
        ):
            _perf, candidate = hr._render_fund_performance_section([], [], prog)

        assert candidate == {"available": False}
        assert len(prog.warns) == 1
        assert "config.comparison_candidates 为空" in prog.warns[0]
        assert prog.oks == []

    def test_switch_off_returns_none_silently(self) -> None:
        prog = _RecordingProgress()
        with (
            patch.object(hr, "_build_perf_data", return_value=[]),
            patch.object(hr, "build_candidate_compare_data", return_value=None),
        ):
            _perf, candidate = hr._render_fund_performance_section([], [], prog)

        assert candidate is None
        assert prog.oks == [] and prog.warns == []


class TestManagerAnalysis:
    """基金经理变更监控：开关关闭 / 无结果 / 首次确认摘要 / 异常兜底。"""

    def test_disabled_returns_none(self) -> None:
        assert hr._render_manager_analysis([], False, _RecordingProgress()) is None

    def test_empty_results_returns_empty_block(self) -> None:
        prog = _RecordingProgress()
        with patch.object(hr, "detect_manager_changes", return_value=[]):
            assert hr._render_manager_analysis([_Holding("110020", "当代基金")], True, prog) == {
                "results": [],
                "first_check_summary": None,
            }
        assert prog.oks == []

    def test_first_check_summary_attached(self) -> None:
        prog = _RecordingProgress()
        with (
            patch.object(hr, "detect_manager_changes", return_value=[{"code": "110020", "is_first_check": True}]),
            patch.object(hr, "build_first_check_summary", return_value="首次确认 1 只"),
        ):
            block = hr._render_manager_analysis([_Holding("110020", "当代基金")], True, prog)

        assert block == {
            "results": [{"code": "110020", "is_first_check": True}],
            "first_check_summary": "首次确认 1 只",
        }
        assert prog.oks == ["基金经理变更分析完成"]

    def test_no_first_check_leaves_summary_none(self) -> None:
        with patch.object(hr, "detect_manager_changes", return_value=[{"code": "110020", "is_first_check": False}]):
            block = hr._render_manager_analysis([_Holding("110020", "当代基金")], True, _RecordingProgress())

        assert block["first_check_summary"] is None

    def test_failure_degrades_to_empty_block(self, caplog) -> None:
        with patch.object(hr, "detect_manager_changes", side_effect=RuntimeError("接口超时")):
            with caplog.at_level("WARNING", logger="invest"):
                block = hr._render_manager_analysis([_Holding("110020", "当代基金")], True, _RecordingProgress())

        assert block == {"results": [], "first_check_summary": None}
        assert "基金经理变更分析失败: 接口超时" in caplog.text


class TestOverlapMatrix:
    """持仓重合度矩阵：市值按基金聚合 / 计算异常降级为空结构。"""

    def test_fund_market_value_aggregated_from_details(self) -> None:
        prog = _RecordingProgress()
        holdings = [_Holding("110020", "当代基金"), _Holding("110021", "华宝基金")]
        details = [_detail("110020", 1000.0), _detail("110020", 250.0), _detail("600900", 999.0)]
        with (
            patch.object(hr, "_fetch_fund_holdings_with_period", return_value={"110020": _fund_payload("当代基金")}),
            patch.object(hr, "_split_stale_funds", return_value=({"110020": {}, "110021": {}}, {"110020": "当代"}, [])),
            patch.object(hr, "compute_overlap_matrix", return_value={"pairs": []}) as matrix,
        ):
            result = hr._render_overlap_matrix(holdings, details, True, prog)

        assert matrix.call_args.kwargs["fund_mv_map"] == {"110020": 1250.0}
        assert result["fund_names"] == {"110020": "当代"}
        assert result["pairs"] == []
        assert prog.oks == ["持仓重合度矩阵计算完成"]

    def test_failure_degrades_to_empty_structure(self, caplog) -> None:
        holdings = [_Holding("110020", "当代基金"), _Holding("110021", "华宝基金")]
        with (
            patch.object(hr, "_fetch_fund_holdings_with_period", return_value={"110020": _fund_payload("当代基金")}),
            patch.object(hr, "_split_stale_funds", side_effect=RuntimeError("前端不可用")),
        ):
            with caplog.at_level("WARNING", logger="invest"):
                result = hr._render_overlap_matrix(holdings, [], True, _RecordingProgress())

        assert result["matrix"] == [] and result["funds"] == []
        assert "持仓重合度矩阵计算失败: 前端不可用" in caplog.text


class TestConcentrationAndStyle:
    """集中度 / 风格分析：计算异常各自降级为空结果集。"""

    def test_concentration_failure_degrades(self, caplog) -> None:
        with patch.object(hr, "_fetch_fund_holdings_with_period", return_value={"110020": _fund_payload("当代基金")}):
            with patch.object(hr, "compute_concentration", side_effect=RuntimeError("解析失败")):
                with caplog.at_level("WARNING", logger="invest"):
                    result = hr._render_concentration([_Holding("110020", "当代基金")], True, _RecordingProgress())

        assert result == {"results": []}
        assert "持仓集中度计算失败: 解析失败" in caplog.text

    def test_style_failure_degrades(self, caplog) -> None:
        with patch.object(hr, "_fetch_fund_holdings_with_period", return_value={"110020": _fund_payload("当代基金")}):
            with patch.object(hr, "analyze_style_for_all_funds", side_effect=RuntimeError("样本不足")):
                with caplog.at_level("WARNING", logger="invest"):
                    result = hr._render_style_analysis([_Holding("110020", "当代基金")], True, _RecordingProgress())

        assert result == {"results": []}
        assert "风格与因子分析失败: 样本不足" in caplog.text


class TestNewsSection:
    """新闻区块：无数据走空结构，取数异常降级不抛。"""

    def test_throttled_log_on_news_ready(self, caplog) -> None:
        news = [{"title": "降准", "date": "2025-01-02"}]
        meta = {"llm_enabled": True}
        with patch("src.python.report.news_correlation.build_news_data", return_value=(news, meta)):
            with caplog.at_level("INFO", logger="invest"):
                data, got_meta = hr._render_news_section(
                    True, None, None, [_Holding("600900", "长江电力")], 10, {"top10": []}, _RecordingProgress()
                )

        assert data == news and got_meta == meta
        assert "财经热点关联分析完成，1 条" in caplog.text

    def test_fetch_failure_returns_default_meta(self, caplog) -> None:
        with patch("src.python.report.news_correlation.build_news_data", side_effect=RuntimeError("新闻源全部降级")):
            with caplog.at_level("WARNING", logger="invest"):
                data, meta = hr._render_news_section(
                    True, None, None, [_Holding("600900", "长江电力")], 10, None, _RecordingProgress()
                )

        assert data == []
        assert meta == {
            "llm_enabled": False,
            "llm_cached": False,
            "token_usage": {},
            "cost_estimation": "-",
            "thinking_enabled": False,
        }
        assert "新闻获取失败: 新闻源全部降级" in caplog.text


class TestContractBlocks:
    """LLM 正文契约折叠块：非空模块追加折叠块，空模块原样保留。"""

    def test_empty_modules_pass_through_untouched(self) -> None:
        """无正文的模块原样返回 None/空串（不凭空生成折叠块）。"""
        gm, er, hc, pd = hr._with_contract_blocks("全局正文", None, None, "")

        assert gm == "全局正文"
        assert (er, hc) == (None, None)
        assert pd == ""

    def test_contract_data_appends_fold_block_and_strips_header(self) -> None:
        """有契约载体 → 正文剥离契约头并追加「主张与证据」折叠块。"""
        from src.python.llm import research_contract

        payload = {
            "claims": [{"statement": "盈利改善", "evidence": ["毛利率回升"], "invalidations": []}],
            "verdict_label": "成立",
        }
        research_contract.record_module_contract("global_macro", payload)
        try:
            gm, er, _hc, _pd = hr._with_contract_blocks('全局正文\n主张契约：{"claims":[]}', None, None, None)
        finally:
            research_contract._MODULE_CONTRACTS.clear()

        assert gm.startswith("全局正文")
        assert "主张契约：" not in gm.split("<details")[0]
        assert "主张与证据" in gm
        assert "盈利改善" in gm
        assert er is None

    def test_llm_content_section_with_prebuilt_content(self) -> None:
        flag, gm, er, hc, pd = hr._render_llm_content_section(True, ("宏观", None, None, None))

        assert flag is True
        assert gm.startswith("宏观")
        assert (er, hc, pd) == (None, None, None)

    def test_llm_content_section_all_empty_flags_false(self) -> None:
        flag, *_rest = hr._render_llm_content_section(True, (None, None, None, None))

        assert flag is False


def test_module_info_survives_missing_prompts_module(caplog) -> None:
    """llm/prompts 不可导入 → 模块失败原因按空表处理，只记 info 不抛。"""
    with patch.dict(sys.modules, {"src.python.llm.prompts": None}):
        with caplog.at_level("INFO", logger="invest"):
            info, endpoint, disabled, usage = hr._render_llm_module_info(False)

    assert "llm/session 模块未就绪，略过用量统计" in caplog.text
    assert usage is None
    assert set(disabled) >= {"global_macro", "expert_review", "health_check", "penetration_deep", "news_correlation"}
    assert all(v is False for v in disabled.values())
    assert isinstance(info, list) and isinstance(endpoint, str)
