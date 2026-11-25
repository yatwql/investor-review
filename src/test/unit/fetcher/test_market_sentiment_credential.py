"""市场情绪域凭据缺失提示的拼装单元测试。

同花顺凭据登记点只给结构化声明（环境变量名 + 申请入口），上屏文案在本域单点拼装：
就绪 → None（报告照常出），缺失 → 「缺少环境变量 X（申请入口：Y）」。全部离线。
"""

from __future__ import annotations

import types

import pytest

from src.python.fetcher import market_sentiment
from src.python.providers import hithink

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher]


def _spec(env_var: str, apply_url: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(env_var=env_var, apply_url=apply_url)


def test_ready_credentials_yield_no_message(monkeypatch):
    monkeypatch.setattr(hithink, "missing_credential", lambda _source: None)

    assert market_sentiment.credential_missing() is None


def test_missing_credentials_include_apply_url_when_declared(monkeypatch):
    monkeypatch.setattr(
        hithink, "missing_credential", lambda _source: _spec("HITHINK_API_KEY", "https://example.invalid/open")
    )

    assert (
        market_sentiment.credential_missing()
        == "缺少环境变量 HITHINK_API_KEY（申请入口：https://example.invalid/open）"
    )


def test_missing_credentials_without_apply_url(monkeypatch):
    monkeypatch.setattr(hithink, "missing_credential", lambda _source: _spec("HITHINK_API_KEY", ""))

    assert market_sentiment.credential_missing() == "缺少环境变量 HITHINK_API_KEY"
