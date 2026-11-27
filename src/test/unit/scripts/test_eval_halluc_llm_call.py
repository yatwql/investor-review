"""`_eval_halluc_sampler.llm_call`（模块映射 / prompt 构建 / 真实调用骨架）单元测试。

本模块是评测机里唯一会**花钱**的一层，因此测试纪律是：dry-run 走真实提示词
构建器（验证拼装），真实调用一律把 `llm/generators` 与 HTTP 客户端换成假对象
（验证参数转发、缓存标记与异常兜底）。任何用例都不触网、不调 LLM。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    # sampler 包内部是扁平 import（`_eval_halluc_sampler.*`），注入 scripts/ 才能加载
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _eval_halluc_sampler import llm_call  # noqa: E402

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_HOLDINGS = [
    {"name": "贵州茅台", "code": "600519", "market_value": 12000.0, "cost": 10000.0, "profit": 2000.0},
    {"name": "沪深300ETF", "code": "510300", "market_value": 8000.0, "cost": 9000.0, "profit": -1000.0},
]
_VALUES = {"total_mv": 20000.0, "total_cost": 19000.0, "total_profit": 1000.0, "total_today_profit": 50.0}
_CATEGORIES = {"stock": 2}


@pytest.fixture(autouse=True)
def _reset_http_client(monkeypatch):
    """`_HTTP_CLIENT` 是模块级单例：用例之间必须重置，否则会串到上一个用例的假客户端。"""
    monkeypatch.setattr(llm_call, "_HTTP_CLIENT", None)


@pytest.fixture
def generator_mocks(monkeypatch):
    """把 4 个 LLM 生成器换成可断言的 Mock（默认返回 (正文, 未命中缓存)）。"""
    import src.python.llm.generators as generators

    mocks = {}
    for fn_name in set(llm_call._MODULE_FNS.values()):
        mock = Mock(name=fn_name, return_value=("分析正文", False))
        monkeypatch.setattr(generators, fn_name, mock)
        mocks[fn_name] = mock
    monkeypatch.setattr("src.python.config.get_llm_config", lambda: {"provider": "claude", "model": "fake"})
    return mocks


# ── HTTP 客户端工厂 ─────────────────────────────────────────


def test_http_client_is_created_once(monkeypatch):
    """客户端按需创建且进程内复用（每次采样新建连接池会拖慢评测并泄漏句柄）。"""
    import src.python.core.http_client as http_client

    created = []

    def _make(**kwargs):
        created.append(kwargs)
        return Mock(name="client")

    monkeypatch.setattr(http_client, "make_http_client", _make)

    first = llm_call._get_http_client()
    second = llm_call._get_http_client()

    assert first is second
    assert created == [{"timeout": 120.0, "http2": False}]


# ── dry-run：走真实提示词构建 ───────────────────────────────


@pytest.mark.parametrize("module_name", sorted(llm_call._MODULE_FNS))
def test_dry_run_builds_system_and_user_prompt(module_name):
    """dry-run 每个模块都产出「[SYSTEM]…[USER]…」两段提示词，且不返回 usage。"""
    prompt, meta = llm_call._call_llm_module(module_name, _HOLDINGS, _VALUES, _CATEGORIES, dry_run=True)

    assert meta == {"dry_run": True}
    assert prompt.startswith("[SYSTEM]\n")
    system_part, user_part = prompt.split("\n\n[USER]\n", 1)
    assert system_part.strip() != "[SYSTEM]"
    assert user_part.strip(), "用户提示词不得为空（数值/持仓应已注入）"


def test_dry_run_prompt_carries_portfolio_numbers():
    """数值真值确实注入提示词（否则抽样出来的「幻觉」会全是提示词缺数据导致的误判）。"""
    prompt, _meta = llm_call._call_llm_module("health_check", _HOLDINGS, _VALUES, _CATEGORIES, dry_run=True)

    assert "20,000" in prompt or "20000" in prompt


# ── 分支：未知模块 / 无配置 ─────────────────────────────────


def test_unknown_module_returns_none():
    assert llm_call._call_llm_module("no_such_module", _HOLDINGS, _VALUES, _CATEGORIES) == (None, None)


def test_missing_llm_config_skips_real_call(monkeypatch, generator_mocks):
    """无 LLM 配置时返回 (None, None) 且**不**调用生成器（不浪费一次调用）。"""
    monkeypatch.setattr("src.python.config.get_llm_config", lambda: None)

    assert llm_call._call_llm_module("expert_review", _HOLDINGS, _VALUES, _CATEGORIES) == (None, None)
    assert not generator_mocks["generate_expert_review"].called


# ── 真实调用的参数转发与结果映射 ─────────────────────────────


@pytest.mark.parametrize("module_name", sorted(llm_call._MODULE_FNS))
def test_real_call_forwards_portfolio_and_client(module_name, generator_mocks):
    """四个模块都按各自签名转发真值与共享客户端，返回 (正文, {"cached": 是否命中})。"""
    client = Mock(name="client")
    llm_call._HTTP_CLIENT = client

    content, meta = llm_call._call_llm_module(module_name, _HOLDINGS, _VALUES, _CATEGORIES, force=True)

    assert content == "分析正文"
    assert meta == {"cached": False}
    mock = generator_mocks[llm_call._MODULE_FNS[module_name]]
    mock.assert_called_once()
    kwargs = mock.call_args.kwargs
    assert kwargs["force"] is True
    assert kwargs["http_client"] is client
    assert kwargs["llm_config"] == {"provider": "claude", "model": "fake"}
    assert _VALUES["total_mv"] in mock.call_args.args
    assert _VALUES["total_cost"] in mock.call_args.args
    assert _CATEGORIES in mock.call_args.args


def test_cache_hit_is_reflected_in_usage(generator_mocks):
    """生成器报 cached=True 时如实透传（缓存命中率是评测成本口径的一部分）。"""
    generator_mocks["generate_expert_review"].return_value = ("缓存正文", True)

    content, meta = llm_call._call_llm_module("expert_review", _HOLDINGS, _VALUES, _CATEGORIES)

    assert content == "缓存正文"
    assert meta == {"cached": True}


def test_empty_content_is_never_reported_as_cached(generator_mocks):
    """空产出时 cached 一律 False（否则「未生成」会被统计成「命中缓存」）。"""
    generator_mocks["generate_health_check"].return_value = (None, True)

    content, meta = llm_call._call_llm_module("health_check", _HOLDINGS, _VALUES, _CATEGORIES)

    assert content is None
    assert meta == {"cached": False}


def test_generator_exception_is_captured_as_error(generator_mocks):
    """单模块调用失败只记 error 并返回 None，让其余模块的采样继续。"""
    generator_mocks["generate_penetration_deep_analysis"].side_effect = RuntimeError("上游 502")

    content, meta = llm_call._call_llm_module("penetration_deep", _HOLDINGS, _VALUES, _CATEGORIES)

    assert content is None
    assert meta == {"error": "上游 502"}
