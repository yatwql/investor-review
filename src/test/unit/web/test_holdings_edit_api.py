# -*- coding: utf-8 -*-
"""Web 持仓录入接口（``/api/holdings*``）契约测试。

覆盖：总览读取、变更清单重放（预览不写文件）、确认写回（.bak + 可选交易流水）、
mtime 闸门（他人改动时 409 且不写）、参数校验与同源守卫、场外按金额折算份额。

网络取数（净值/行情）全部 mock；持仓文件用 tmp 目录里的合成工作簿，
绝不触碰真实持仓。
"""

from __future__ import annotations

import os
from pathlib import Path

import openpyxl
import pytest

from src.python.config import _config_defaults
from src.python.config._core import invalidate_config_cache
from src.python.core.reader import read_flow_sheets, read_holdings
from src.python.web.app import create_app
from src.python.web.runs import RunManager

pytestmark = [pytest.mark.unit, pytest.mark.unit_web, pytest.mark.usefixtures("offline_external_sources")]


def _make_holdings_file(path: Path) -> Path:
    """两账户持仓（一个 A 股、一个场外基金），无流水页签。"""
    wb = openpyxl.Workbook()
    stock = wb.worksheets[0]
    stock.title = "股票账户"
    stock.append(["名称", "代码", "持仓份额", "每份成本"])
    stock.append(["长江电力", "600900", 1000, 20.0])
    fund = wb.create_sheet("基金账户")
    fund.append(["名称", "代码", "持仓份额", "每份成本"])
    fund.append(["易方达蓝筹精选混合", "005827", 200, 2.0])
    wb.save(path)
    return path


@pytest.fixture
def holdings_path(tmp_path, monkeypatch) -> Path:
    """把正式持仓路径重定向到 tmp 下的合成文件（不读真实持仓）。"""
    path = _make_holdings_file(tmp_path / "持仓.xlsx")
    monkeypatch.setitem(_config_defaults._DEFAULT_CONFIG, "holdings_dir", str(tmp_path))
    monkeypatch.setitem(_config_defaults._DEFAULT_CONFIG, "holdings_filename", "持仓.xlsx")
    invalidate_config_cache()
    return path


@pytest.fixture
def client(holdings_path):
    app = create_app(RunManager(executor=lambda state, params: 0))
    app.config["TESTING"] = True
    return app.test_client()


def _buy_intent(**overrides) -> dict:
    intent = {
        "account": "股票账户",
        "code": "600900",
        "name": "长江电力",
        "side": "buy",
        "shares": 500,
        "price": 22.0,
        "trade_date": "2026-10-29",
    }
    intent.update(overrides)
    return intent


def test_overview_lists_accounts_and_rows(client):
    payload = client.get("/api/holdings").get_json()

    assert payload["ok"] is True
    data = payload["data"]
    assert data["file"] == "持仓.xlsx"
    assert [(a["account"], len(a["rows"])) for a in data["accounts"]] == [("股票账户", 1), ("基金账户", 1)]
    assert data["rows_total"] == 2
    assert data["accounts"][0]["rows"][0]["code"] == "600900"


def test_overview_reports_missing_file(tmp_path, monkeypatch):
    monkeypatch.setitem(_config_defaults._DEFAULT_CONFIG, "holdings_dir", str(tmp_path))
    monkeypatch.setitem(_config_defaults._DEFAULT_CONFIG, "holdings_filename", "不存在.xlsx")
    invalidate_config_cache()
    app = create_app(RunManager(executor=lambda state, params: 0))
    payload = app.test_client().get("/api/holdings").get_json()

    assert payload["ok"] is False
    assert payload["error_code"] == "HOLDINGS_UNAVAILABLE"


def test_preview_replays_without_writing(client, holdings_path):
    before = holdings_path.read_bytes()

    payload = client.post("/api/holdings/preview", json={"intents": [_buy_intent()]}).get_json()

    assert payload["ok"] is True
    data = payload["data"]
    assert data["diff"] == {"added": 0, "updated": 1, "removed": 0}
    row = next(r for a in data["accounts"] for r in a["rows"] if r["code"] == "600900")
    assert row["shares"] == pytest.approx(1500)
    assert row["dirty"] is True
    assert holdings_path.read_bytes() == before  # 预览不落盘


def test_save_writes_rows_and_backup(client, holdings_path):
    payload = client.post("/api/holdings/save", json={"intents": [_buy_intent()]}).get_json()

    assert payload["ok"] is True
    assert payload["data"]["saved"] == 1
    row = next(item for item in read_holdings(str(holdings_path)) if item.code == "600900")
    assert row.shares == pytest.approx(1500)
    assert row.cost_price == pytest.approx((1000 * 20.0 + 500 * 22.0) / 1500)
    assert holdings_path.with_name("持仓.xlsx.bak").exists()


def test_save_appends_trade_flow_when_requested(client, holdings_path):
    payload = client.post(
        "/api/holdings/save",
        json={"intents": [_buy_intent(shares=100, price=21.0)], "append_flows": True},
    ).get_json()

    assert payload["ok"] is True
    transactions, _dividends = read_flow_sheets(str(holdings_path))
    assert [t.code for t in transactions] == ["600900"]
    assert transactions[0].action == "buy"
    assert transactions[0].shares == pytest.approx(100)


def test_save_rejects_stale_base_mtime(client, holdings_path):
    before = holdings_path.read_bytes()
    stale = os.path.getmtime(holdings_path) - 60

    resp = client.post("/api/holdings/save", json={"intents": [_buy_intent()], "base_mtime": stale})

    assert resp.status_code == 409
    assert resp.get_json()["error_code"] == "HOLDINGS_STALE"
    assert holdings_path.read_bytes() == before


def test_preview_requires_non_empty_intents(client):
    resp = client.post("/api/holdings/preview", json={"intents": []})

    assert resp.status_code == 400
    assert "变更清单为空" in resp.get_json()["error"]


def test_preview_rejects_ambiguous_00_code_without_asset_kind(client):
    resp = client.post(
        "/api/holdings/preview",
        json={"intents": [_buy_intent(code="005827", name="易方达蓝筹")]},
    )

    assert resp.status_code == 400
    assert "品种属性" in resp.get_json()["error"]


def test_otc_buy_by_amount_derives_shares(client, holdings_path, monkeypatch):
    monkeypatch.setattr(
        "src.python.fetcher.nav_lookup.resolve_purchase_shares",
        lambda code, trade_date, amount: {
            "shares": amount / 1.25,
            "nav": 1.25,
            "nav_date": trade_date,
            "exact_date": True,
        },
    )
    intent = _buy_intent(
        account="基金账户",
        code="005827",
        name="易方达蓝筹精选混合",
        shares=None,
        amount=1000,
        price=None,
        asset_kind="otc",
    )

    payload = client.post("/api/holdings/preview", json={"intents": [intent]}).get_json()

    assert payload["ok"] is True
    row = next(r for a in payload["data"]["accounts"] for r in a["rows"] if r["code"] == "005827")
    assert row["shares"] == pytest.approx(1000)


def test_preview_rejects_cross_origin(client):
    resp = client.post(
        "/api/holdings/preview",
        json={"intents": [_buy_intent()]},
        headers={"Origin": "https://evil.example.com"},
    )

    assert resp.status_code == 403
