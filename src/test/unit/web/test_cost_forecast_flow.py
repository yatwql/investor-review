"""Web 事前费用预估与日预算硬闸测试（preflight / create_run 409 / 执行体兜底 / main.js 接线）。

覆盖：
  - GET /api/runs/cost-preflight：forecast+budget 结构、非 full 模式不给 forecast
  - POST /api/runs：超限且无 budget_ack → 409 BUDGET_EXCEEDED；显式 ack 放行；
    非 full 不受预算闸约束；budget_ack 类型校验
  - ``_run_generation_impl`` 执行体权威兜底（覆盖定时调度等不经弹层链路）
  - main.js 生成按钮：full 分支先弹层、取消复位、ack/降级字段注入
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest

from src.python.config import _config_defaults
from src.python.config._core import invalidate_config_cache
from src.python.web.app import create_app
from src.python.web.runs import RunManager, RunState

pytestmark = [pytest.mark.unit, pytest.mark.unit_web, pytest.mark.usefixtures("offline_external_sources")]

MAIN_JS = Path("src/static/web/main.js")


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setitem(_config_defaults._DEFAULT_CONFIG, "output_dir", str(tmp_path))
    invalidate_config_cache()
    app = create_app(RunManager(executor=lambda state, params: 0))
    app.config["TESTING"] = True
    return app.test_client()


def _fc(**over):
    base = {"ok": True, "module_count": 3, "low": 0.1, "high": 0.9, "basis": "static", "symbol": "¥", "reason": None}
    base.update(over)
    return base


def _budget(**over):
    base = {"enabled": False, "limit": 0.0, "spent": 0.0, "exceeded": False, "currency": "CNY", "symbol": "¥"}
    base.update(over)
    return base


class TestCostPreflight:
    """GET /api/runs/cost-preflight：弹层数据源契约。"""

    def test_full_mode_returns_forecast_and_budget(self, app_client):
        with (
            patch("src.python.llm.cost_forecast.forecast_run_cost", return_value=_fc()),
            patch("src.python.llm.cost_forecast.budget_status", return_value=_budget()),
        ):
            resp = app_client.get("/api/runs/cost-preflight?report_type=full")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["relevant"] is True
        assert data["forecast"]["ok"] is True
        assert data["forecast"]["module_count"] == 3
        assert set(data["budget"]) == {"enabled", "limit", "spent", "exceeded", "currency", "symbol"}

    def test_non_full_mode_omits_forecast(self, app_client):
        with patch("src.python.llm.cost_forecast.budget_status", return_value=_budget()):
            resp = app_client.get("/api/runs/cost-preflight?report_type=basic")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["relevant"] is False
        assert "forecast" not in data
        assert "budget" in data, "预算状态恒给（超限提示与报告类型无关时不适用，但契约保留）"

    def test_unavailable_forecast_still_200_nonblocking(self, app_client):
        with (
            patch("src.python.llm.cost_forecast.forecast_run_cost", return_value=_fc(ok=False, reason="模型未知")),
            patch("src.python.llm.cost_forecast.budget_status", return_value=_budget()),
        ):
            resp = app_client.get("/api/runs/cost-preflight?report_type=full")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["forecast"]["ok"] is False, "预估失败以数据面表达，不报错"

    def test_preflight_passes_force_scope(self, app_client):
        with (
            patch("src.python.llm.cost_forecast.forecast_run_cost", return_value=_fc()) as m,
            patch("src.python.llm.cost_forecast.budget_status", return_value=_budget()),
        ):
            resp = app_client.get("/api/runs/cost-preflight?report_type=full&llm_modules=expert_review")
        assert resp.status_code == 200
        assert m.call_args.kwargs["force_modules"] == ["expert_review"], "重新生成范围须透传预检"

    def test_preflight_invalid_module_key_data_degrades(self, app_client):
        with patch("src.python.llm.cost_forecast.budget_status", return_value=_budget()):
            resp = app_client.get("/api/runs/cost-preflight?report_type=full&llm_modules=no_such_module")
        assert resp.status_code == 200, "非法模块键不 500"
        assert resp.get_json()["data"]["forecast"]["ok"] is False


class TestCreateRunBudgetGate:
    """POST /api/runs 日预算硬闸（full 模式；显式 budget_ack 放行）。"""

    @staticmethod
    def _payload(**over):
        base = {"report_type": "full", "mode": "formal", "use_existing": True, "force_llm": False}
        base.update(over)
        return base

    def test_exceeded_without_ack_returns_409(self, app_client):
        with patch(
            "src.python.llm.cost_forecast.budget_status",
            return_value=_budget(enabled=True, limit=1.0, spent=1.5, exceeded=True),
        ):
            resp = app_client.post("/api/runs", json=self._payload())
        assert resp.status_code == 409
        body = resp.get_json()
        assert body["error_code"] == "BUDGET_EXCEEDED"
        assert "日预算上限" in body["error"]

    def test_exceeded_with_ack_proceeds(self, app_client):
        with patch(
            "src.python.llm.cost_forecast.budget_status",
            return_value=_budget(enabled=True, limit=1.0, spent=1.5, exceeded=True),
        ):
            resp = app_client.post("/api/runs", json=self._payload(budget_ack=True))
        assert resp.status_code == 202, f"显式确认后应放行，实际 {resp.status_code}: {resp.get_json()}"
        assert resp.get_json()["data"]["run_id"]

    def test_not_exceeded_needs_no_ack(self, app_client):
        with patch(
            "src.python.llm.cost_forecast.budget_status",
            return_value=_budget(enabled=True, limit=10.0, spent=0.1, exceeded=False),
        ):
            resp = app_client.post("/api/runs", json=self._payload())
        assert resp.status_code == 202

    def test_budget_gate_only_applies_to_full(self, app_client):
        with patch(
            "src.python.llm.cost_forecast.budget_status",
            return_value=_budget(enabled=True, limit=1.0, spent=1.5, exceeded=True),
        ):
            resp = app_client.post("/api/runs", json=self._payload(report_type="basic"))
        assert resp.status_code == 202, "非 full 模式无 LLM 调用，不受日预算闸约束"

    def test_budget_ack_type_validated(self, app_client):
        resp = app_client.post("/api/runs", json=self._payload(budget_ack="yes"))
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_PARAM"


class TestRunImplBudgetBackstop:
    """执行体权威兜底：不经弹层的链路（定时调度/直连）同样被硬闸拦下。"""

    @staticmethod
    def _state(**params):
        base = {"report_type": "full", "mode": "formal", "use_existing": True}
        base.update(params)
        return RunState("budget-test-run", base), base

    def test_exceeded_without_ack_fails_run(self, tmp_path):
        from src.python.web.handlers import _run_generation_impl

        state, params = self._state()
        with patch(
            "src.python.llm.cost_forecast.budget_status",
            return_value=_budget(enabled=True, limit=1.0, spent=1.5, exceeded=True),
        ):
            code = _run_generation_impl(state, params)
        assert code == 2
        assert any("日预算上限" in e for e in state.errors), "中止原因须进入 run 错误面"

    def test_ack_skips_gate_then_runs_normal_flow(self, tmp_path):
        """ack 放行后进入正常流（此处以持仓缺失错误证明已越过硬闸）。"""
        from src.python.web.handlers import _run_generation_impl

        state, params = self._state(budget_ack=True)
        cfg = {"holdings_dir": str(tmp_path), "holdings_filename": "missing.xlsx"}
        with (
            patch(
                "src.python.llm.cost_forecast.budget_status",
                return_value=_budget(enabled=True, limit=1.0, spent=1.5, exceeded=True),
            ),
            patch("src.python.config.get_config", return_value=cfg),
        ):
            code = _run_generation_impl(state, params)
        assert code == 2
        assert not any("日预算上限" in e for e in state.errors), "ack 后不得再被硬闸拦截"
        assert any("正式持仓文件不存在" in e for e in state.errors), "已越过硬闸进入正常持仓校验流"

    def test_non_full_params_untouched_by_gate(self, tmp_path):
        from src.python.web.handlers import _run_generation_impl

        state, params = self._state(report_type="basic")
        cfg = {"holdings_dir": str(tmp_path), "holdings_filename": "missing.xlsx"}
        with (
            patch(
                "src.python.llm.cost_forecast.budget_status",
                return_value=_budget(enabled=True, limit=1.0, spent=1.5, exceeded=True),
            ),
            patch("src.python.config.get_config", return_value=cfg),
        ):
            code = _run_generation_impl(state, params)
        assert code == 2
        assert not any("日预算上限" in e for e in state.errors), "非 full 不触发预算闸"


class TestMainJsCostForecastWiring:
    """main.js 源结构断言：full 分支弹层 → 取消复位 → ack/降级字段注入提交。"""

    @staticmethod
    def _src() -> str:
        return MAIN_JS.read_text(encoding="utf-8")

    def test_full_branch_calls_preflight_confirm(self) -> None:
        src = self._src()
        block = re.search(r"if \(body\.report_type === 'full'\) \{.*?\n    \}", src, re.S)
        assert block, "full 分支须先走费用预估确认"
        body = block.group(0)
        assert "confirmCostForecast(body.llm_modules)" in body
        assert "submitRun(body)" in body, "确认通过才提交"
        assert "resetGenerateBtn()" in body, "取消须复位按钮"
        assert body.index("confirmCostForecast(body.llm_modules)") < body.index("submitRun(body)"), "先确认后提交"

    def test_ack_and_downgrade_injected(self) -> None:
        src = self._src()
        assert re.search(r"decision\.budgetAck[\s\S]{0,120}body\.budget_ack = true", src), "超限确认须注入 budget_ack"
        down = re.search(r"decision\.forceDowngraded[\s\S]{0,200}body\.llm_modules = null", src)
        assert down, "降级须清空强刷与模块级强刷"
        assert "body.force_llm = false" in down.group(0), "降级须清空全量强刷"

    def test_preflight_network_failure_nonblocking(self) -> None:
        src = self._src()
        fn = re.search(r"function confirmCostForecast\(modules\) \{.*?\n  \}", src, re.S)
        assert fn, "confirmCostForecast 定义缺失"
        body = fn.group(0)
        assert "/api/runs/cost-preflight" in body
        assert "llm_modules=" in body, "模块级重新生成范围须进预检查询串"
        assert "proceed: true" in body, "预检失败/预估不可用须放行（服务端硬闸兜底）"
        assert "budgetAck: true" in body, "超限确认分支须产出 ack"

    def test_preflight_dialog_shows_forced_breakdown(self) -> None:
        src = self._src()
        assert re.search(r"f\.forced_count[\s\S]{0,200}个模块重新生成", src), "弹层文案须显示重新生成拆行"
