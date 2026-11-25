"""OpenAI 载荷装配 / 新闻关联安全入口 / 事实校验工具的残差分支测试。

覆盖：
  - `_api_openai.call_openai`：temperature 覆盖进 payload、缺 HTTP 客户端即拒、
    `_extract_openai` 面对畸形响应回 None
  - `_llm_news_correlation.run_news_correlation_safe`：无 LLM 配置、
    `enabled_llm.news_correlation=false` 两态短路，以及下游异常时的失败原因登记
  - `fact_checker._utils`：空 HTML、长度不同的代码编辑距离、空名称核心名
  - `fact_checker._cross_module._entity_mentions`：非 dict 条目与无名称无代码条目跳过
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]


@pytest.fixture()
def clean_module_failure():
    """隔离 LLM 失败原因登记表（断言依赖空起点，退出时复位）。"""
    from src.python.llm.prompts import LLM_MODULE_FAILURE

    LLM_MODULE_FAILURE.pop("news_correlation", None)
    yield LLM_MODULE_FAILURE
    LLM_MODULE_FAILURE.pop("news_correlation", None)


def test_call_openai_puts_temperature_into_payload(monkeypatch):
    """显式 temperature 覆盖时写进 payload，并由 retry 层装配的成功路径返回原文。"""
    from src.python.llm import _api_openai

    captured: dict = {}

    def _fake_retry(**kwargs):
        captured.update(kwargs)
        return "回答正文", {"total_tokens": 7}

    monkeypatch.setattr(_api_openai, "call_llm_with_retry", _fake_retry)

    content, usage = _api_openai.call_openai(
        system="系统",
        user="提问",
        api_key="sk-test",
        model="gpt-test",
        endpoint="",
        max_tokens=256,
        http_client=object(),  # 类型收窄只校验非 None，真实 POST 由 fake retry 层承担
        temperature=0.2,
    )

    assert content == "回答正文"
    assert usage == {"total_tokens": 7}
    assert captured["payload"]["temperature"] == pytest.approx(0.2)
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"


def test_call_openai_requires_http_client():
    """缺 HTTP 客户端时在入口即拒（不留到请求处才炸）。"""
    from src.python.llm._api_openai import call_openai

    with pytest.raises(ValueError, match="http_client"):
        call_openai(
            system="系统",
            user="提问",
            api_key="sk-test",
            model="gpt-test",
            endpoint="",
            max_tokens=64,
            http_client=None,
        )


def test_openai_extractor_returns_none_on_malformed_response(monkeypatch):
    """响应缺 choices/message 时抽取器回 None（交由 retry 层判失败并重试）。"""
    from src.python.llm import _api_openai

    captured: dict = {}

    def _fake_retry(**kwargs):
        captured.update(kwargs)
        return kwargs["extract_fn"]({"choices": []}), None

    monkeypatch.setattr(_api_openai, "call_llm_with_retry", _fake_retry)

    content, _usage = _api_openai.call_openai(
        system="系统",
        user="提问",
        api_key="sk-test",
        model="gpt-test",
        endpoint="",
        max_tokens=64,
        http_client=object(),
    )

    assert content is None
    assert "temperature" not in captured["payload"]


def test_news_correlation_safe_returns_inputs_without_llm_config(monkeypatch, clean_module_failure):
    """无 LLM 配置时原样返回新闻（不改数据、不标失败原因）。"""
    from src.python.llm import _llm_news_correlation as module

    monkeypatch.setattr(module, "get_llm_config", lambda: {})
    news = [{"title": "新闻一"}]

    result, cached, usage = module.run_news_correlation_safe(news, [{"code": "000001"}])

    assert result is news
    assert cached is False
    assert usage == {}
    assert "news_correlation" not in clean_module_failure


def test_news_correlation_safe_marks_disabled_when_switch_off(monkeypatch, clean_module_failure):
    """`enabled_llm.news_correlation=false` 时短路并登记「已禁用」。"""
    from src.python.llm import _llm_news_correlation as module
    from src.python.llm.prompts import FAIL_REASON_DISABLED

    monkeypatch.setattr(module, "get_llm_config", lambda: {"enabled_llm": {"news_correlation": False}})
    news = [{"title": "新闻二"}]

    result, cached, usage = module.run_news_correlation_safe(news, [])

    assert result is news
    assert cached is False
    assert usage == {}
    assert clean_module_failure["news_correlation"] == FAIL_REASON_DISABLED


def test_news_correlation_safe_swallows_downstream_exception(monkeypatch, clean_module_failure):
    """下游富化抛异常时返回原新闻并登记 API 失败原因（不向上抛）。"""
    import src.python.llm.generators_news as generators_news
    from src.python.llm import _llm_news_correlation as module
    from src.python.llm.prompts import FAIL_REASON_API_ERROR

    monkeypatch.setattr(module, "get_llm_config", lambda: {"enabled_llm": {"news_correlation": True}})

    def _boom(*_args, **_kwargs):
        raise RuntimeError("上游 LLM 不可用")

    monkeypatch.setattr(generators_news, "enhance_news_correlation", _boom)
    news = [{"title": "新闻三"}]

    result, cached, usage = module.run_news_correlation_safe(news, [])

    assert result is news
    assert cached is False
    assert usage == {}
    assert clean_module_failure["news_correlation"] == FAIL_REASON_API_ERROR


def test_strip_html_returns_empty_for_empty_input():
    """空 HTML 直接回空串（regex 去掉标签不适用）。"""
    from src.python.llm.fact_checker._utils import _strip_html

    assert _strip_html("") == ""


def test_edit_distance_le_one_false_on_length_mismatch():
    """代码长度不同即判「不是一位之差」，不再逐位比较。"""
    from src.python.llm.fact_checker._utils import _edit_distance_le_one

    assert _edit_distance_le_one("561910", "56191") is False
    assert _edit_distance_le_one("561910", "561920") is True


def test_extract_core_name_empty_for_blank_name():
    """空名称没有核心名。"""
    from src.python.llm.fact_checker._utils import _extract_core_name

    assert _extract_core_name("") == ""


def test_entity_mentions_skips_non_dict_and_blank_entries():
    """持仓明细里的非 dict 条目与「无名称且无代码」条目都不产生实体命中。"""
    from src.python.llm.fact_checker._cross_module import _entity_mentions

    mentions = _entity_mentions(
        "贵州茅台今日回撤",
        ["不是字典", {"name": "  ", "code": ""}, {"name": "贵州茅台", "code": "600519"}],
    )

    assert mentions == [("贵州茅台(600519)", "600519", 0)]
