# -*- coding: utf-8 -*-
"""Web HTTP 处理层错误信封：同源守卫、参数枚举、payload 形状与内部异常兜底。

覆盖面：
  - 同源校验的两种拒绝（跨站 Origin / Origin 无法解析）+ 放行三方（无头/同源/none）
  - 上传缺文件、生成请求的 force_llm / llm_modules 枚举校验
  - 任务列表/详情/事件流的 404 与 `after` 非法回落
  - 持仓预览/写回的 400（含 HOLDINGS_STALE→409 映射）与 500 兜底
  - 调度配置的 payload 形状校验与写入失败兜底

全部走 Flask test_client + 替身注入，零真实上传、零真实写盘。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.web.app import create_app
from src.python.web.runs import RunManager

pytestmark = [pytest.mark.unit, pytest.mark.unit_web]


@pytest.fixture
def run_manager():
    return RunManager(executor=lambda state, params: 0)


@pytest.fixture
def client(run_manager):
    app = create_app(run_manager)
    app.config["TESTING"] = True
    return app.test_client()


class TestSameOrigin:
    def test_cross_site_header_rejected(self, client):
        resp = client.post("/api/holdings/preview", json={"intents": []}, headers={"Sec-Fetch-Site": "cross-site"})
        assert resp.status_code == 403
        assert resp.get_json()["error_code"] == "BAD_PARAM"

    def test_unparsable_origin_rejected(self, client):
        resp = client.post("/api/holdings/preview", json={"intents": []}, headers={"Origin": "http://[::1"})
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "同源校验失败，拒绝提交"

    def test_same_origin_allowed(self, client):
        with patch("src.python.web.holdings_edit.preview", return_value={"accounts": []}):
            resp = client.post(
                "/api/holdings/preview",
                json={"intents": []},
                headers={"Origin": "http://localhost", "Sec-Fetch-Site": "same-origin"},
            )
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True


class TestUploadAndCreateRun:
    def test_upload_without_file(self, client):
        resp = client.post("/api/upload", data={})
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "UPLOAD_BAD_FILE"

    def test_force_llm_must_be_bool(self, client):
        resp = client.post("/api/runs", json={"file_id": "f1", "force_llm": "yes"})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "强制 LLM 参数不合法"

    def test_llm_modules_must_be_string_list(self, client):
        resp = client.post("/api/runs", json={"file_id": "f1", "llm_modules": [1, 2]})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "LLM 模块列表参数不合法"

    def test_unknown_llm_module_rejected(self, client):
        resp = client.post("/api/runs", json={"file_id": "f1", "llm_modules": ["不存在的模块"]})
        assert resp.status_code == 400
        assert "不存在的模块" in resp.get_json()["error"]

    def test_create_run_cross_site_rejected(self, client):
        with patch("src.python.web.upload.resolve_file", return_value="/tmp/holdings.xlsx"):
            resp = client.post(
                "/api/runs",
                json={"file_id": "f1", "report_type": "basic"},
                headers={"Sec-Fetch-Site": "cross-site"},
            )
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "同源校验失败，拒绝提交"


class TestRunsEndpoints:
    def test_list_runs_returns_snapshots(self, client):
        resp = client.get("/api/runs")
        assert resp.status_code == 200
        assert isinstance(resp.get_json()["data"], list)

    def test_unknown_run_detail_404(self, client):
        resp = client.get("/api/runs/nope")
        assert resp.status_code == 404
        assert resp.get_json()["error_code"] == "NOT_FOUND"

    def test_unknown_run_events_404(self, client):
        resp = client.get("/api/runs/nope/events")
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "任务不存在"

    def test_events_invalid_after_falls_back_to_zero(self, client, run_manager):
        from src.python.web.runs import RunState

        state = RunState("r1", {})
        state.push_event("progress", "已开始", phase="collect")
        run_manager._runs["r1"] = state
        resp = client.get("/api/runs/r1/events?after=abc")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        # 非法 after 回落 0 → 全量返回
        assert [e["message"] for e in data["events"]] == ["已开始"]
        assert data["last_seq"] == 1
        assert data["first_seq"] == 1


class TestHoldingsEndpoints:
    def test_preview_payload_must_be_object(self, client):
        resp = client.post("/api/holdings/preview", json=["not-an-object"])
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "请求体格式不合法"

    def test_preview_validation_error_envelope(self, client):
        from src.python.web.holdings_edit import HoldingsEditError

        with patch("src.python.web.holdings_edit.preview", side_effect=HoldingsEditError("变更清单为空")):
            resp = client.post("/api/holdings/preview", json={"intents": []})
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_PARAM"
        assert resp.get_json()["error"] == "变更清单为空"

    def test_preview_unexpected_error_500(self, client):
        with patch("src.python.web.holdings_edit.preview", side_effect=RuntimeError("内部炸了")):
            resp = client.post("/api/holdings/preview", json={"intents": [{"code": "600900"}]})
        assert resp.status_code == 500
        assert resp.get_json()["error_code"] == "HOLDINGS_PREVIEW_FAILED"

    def test_save_stale_maps_to_409(self, client):
        from src.python.web.holdings_edit import HoldingsEditError

        stale = HoldingsEditError("持仓文件已被其他程序修改", code="HOLDINGS_STALE")
        with patch("src.python.web.holdings_edit.save", side_effect=stale):
            resp = client.post("/api/holdings/save", json={"intents": [{"code": "600900"}]})
        assert resp.status_code == 409
        assert resp.get_json()["error_code"] == "HOLDINGS_STALE"

    def test_save_unexpected_error_500(self, client):
        with patch("src.python.web.holdings_edit.save", side_effect=OSError("磁盘满")):
            resp = client.post("/api/holdings/save", json={"intents": [{"code": "600900"}]})
        assert resp.status_code == 500
        assert resp.get_json()["error"] == "写回失败（详情请查看日志）"


class TestSchedulerEndpoint:
    def test_payload_must_be_object(self, client):
        resp = client.post("/api/scheduler", json=["bad"])
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "请求体格式不合法"

    def test_write_failure_500(self, client):
        with (
            patch("src.python.config.validate_schedule_block", return_value={"enabled": True}),
            patch("src.python.config.edit_ops.apply_scheduler_block", side_effect=OSError("只读文件系统")),
        ):
            resp = client.post("/api/scheduler", json={"enabled": True})
        assert resp.status_code == 500
        assert resp.get_json()["error_code"] == "CONFIG_WRITE_FAILED"
