"""LLM 链与策略的降级分支（llm/strategy, llm/api, llm/api_base）。

测试场景：
  1. 代理偏好：检测到代理但无 proxy_preferred 标记 → 保持原序
  2. 计价表不可导入 → 按价排序退化为原序；定价缺价（非标量）→ 排末尾
  3. 链路解析异常 / 链为空 → 模型端点与调用统一返回 None 占位
  4. 思考耗尽标志未设置时清除 → 静默跳过（重试前复位不抛异常）
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from src.python.llm import api, api_base, strategy

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]


class TestProxyPreferred:
    """代理偏好注入的「无标记」分支。"""

    def test_proxy_detected_without_flagged_provider_keeps_order(self, monkeypatch):
        """检测到代理但无 proxy_preferred=True → 顺序不变。"""
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:7890")
        providers = [{"name": "a", "priority": 2}, {"name": "b", "priority": 1}]
        chain = strategy.resolve_provider_chain(providers, "priority")
        assert [p["name"] for p in chain] == ["b", "a"]


class TestCostFirstFallbacks:
    """按价排序的计价表不可用 / 缺价分支。"""

    def test_missing_pricing_module_keeps_original_order(self, monkeypatch):
        """计价表模块不可导入 → 不抛异常且保持原序。"""
        monkeypatch.setitem(sys.modules, "src.python.llm.pricing", None)
        providers = [{"name": "贵", "model": "m1"}, {"name": "便宜", "model": "m2"}]
        chain = strategy.resolve_provider_chain(providers, "cost_first")
        assert [p["name"] for p in chain] == ["贵", "便宜"]

    def test_non_scalar_price_sorts_last(self, monkeypatch):
        """定价条目缺价（非标量）→ cost_score=inf，排在已知价之后。"""
        monkeypatch.setattr(
            "src.python.llm.pricing.PRICING_MERGED",
            {"m1": {"input": "按字符计费", "output": 1}, "m2": {"input": 1.0, "output": 1.0}},
        )
        providers = [{"name": "未知价", "model": "m1"}, {"name": "已知价", "model": "m2"}]
        chain = strategy.resolve_provider_chain(providers, "cost_first")
        assert [p["name"] for p in chain] == ["已知价", "未知价"]


class TestApiChainFallbacks:
    """``_resolve_first_provider_model_endpoint`` 与 ``call_llm`` 的空链/异常收口。"""

    def test_first_provider_resolution_exception_returns_placeholder(self):
        """链路解析抛异常 → (None, "") 占位（不向调用方冒）。"""
        llm_config = {"_provider_list": [{"name": "p1"}], "_strategy": "priority"}
        with patch("src.python.llm.strategy.resolve_provider_chain", side_effect=RuntimeError("策略崩了")):
            model, endpoint = api._resolve_first_provider_model_endpoint(llm_config, "summary")
        assert (model, endpoint) == (None, "")

    def test_call_llm_with_empty_chain_returns_all_none(self, caplog):
        """provider 链解析为空 → 三元组全 None，并留一条 warning。"""
        llm_config = {"_provider_list": [{"name": "p1"}]}
        with (
            patch.object(api, "resolve_provider_chain", return_value=[]),
            caplog.at_level("WARNING"),
        ):
            result = api.call_llm("系统提示", "用户提示", llm_config)
        assert result == (None, None, None)
        assert any("空列表" in rec.message for rec in caplog.records)


class TestThinkingFlagReset:
    """思考耗尽标志的复位入口。"""

    def test_clear_without_flag_is_noop(self):
        """当前线程从未设置标志 → 复位静默通过（重试路径可无条件调用）。"""
        api_base.clear_last_thinking_exhausted()
        api_base.clear_last_thinking_exhausted()
        assert api_base._get_last_thinking_exhausted() is False
