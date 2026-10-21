"""Web 路由 handler 测试（handlers.py，Flask test_client）。

覆盖：上传→生成→轮询→产物 URL 全链路（管线 mock）/ _run_generation 退出码
映射（generate_report mock）/ 错误信封格式 / 参数枚举校验 / file_id 过期 /
路径穿越与扩展名白名单拒绝。"""

from __future__ import annotations
import os
import time
from io import BytesIO
from unittest.mock import patch
from urllib.parse import quote
import pytest
from openpyxl import Workbook
from unittest.mock import MagicMock
import src.python.web.upload as upload
from src.python.config import _config_defaults
from src.python.config._core import invalidate_config_cache
from src.python.report.orchestrator import ReportResult
from src.python.web.app import create_app
from src.python.web.handlers import _build_artifacts, _run_generation
from src.python.web.runs import RunManager, RunState

pytestmark = [pytest.mark.unit, pytest.mark.unit_web, pytest.mark.usefixtures("offline_external_sources")]


def _make_holdings_xlsx() -> bytes:
    """构造标准四列最小持仓 xlsx 字节流。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "账户一"
    ws.append(["名称", "代码", "持仓份额", "每份成本"])
    ws.append(["测试基金", "000001", 1000, 1.0])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _fake_executor(tmp_path):
    """全链路用 fake executor：记录 output_dir + 推送事件 + 成功返回。"""

    def _exec(state, params):
        state.output_dir = str(tmp_path)
        state.push_event("info", "正在获取行情数据...")
        state.push_event("ok", "报告生成完成")
        return 0

    return _exec


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """构造 Flask test_client：config output_dir 重定向到 tmp_path + fake executor。"""
    monkeypatch.setitem(_config_defaults._DEFAULT_CONFIG, "output_dir", str(tmp_path))
    invalidate_config_cache()

    rm = RunManager(executor=_fake_executor(tmp_path))
    app = create_app(rm)
    app.config["TESTING"] = True
    return app.test_client()


class TestFullChain:
    """上传→生成→轮询→产物 URL 全链路（管线 mock）。"""

    def test_upload_then_run_then_poll_then_artifact(self, app_client, tmp_path):
        client = app_client

        # 1. 上传
        resp = client.post("/api/upload", data={"file": (BytesIO(_make_holdings_xlsx()), "持仓.xlsx")})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ok"] is True
        file_id = body["data"]["file_id"]
        assert body["data"]["count"] == 1

        # 2. 生成
        resp = client.post(
            "/api/runs",
            json={"file_id": file_id, "report_type": "basic", "fetch_history": None, "force_llm": False},
        )
        assert resp.status_code == 202
        run_id = resp.get_json()["data"]["run_id"]

        # 3. 轮询至完成（fake executor 立即完成）
        for _ in range(200):
            detail = client.get(f"/api/runs/{run_id}").get_json()["data"]
            if detail["status"] in ("done", "failed"):
                break
            time.sleep(0.01)
        assert detail["status"] == "done"
        assert detail["exit_code"] == 0

        # 事件增量轮询
        events_resp = client.get(f"/api/runs/{run_id}/events?after=0")
        events = events_resp.get_json()["data"]["events"]
        assert len(events) == 2

        # 4. 产物 URL（basic → 仅 Excel）
        artifacts = detail["artifacts"]
        assert [a["kind"] for a in artifacts] == ["xlsx"]

        # 往 tmp_path 写一个产物文件供 send_from_directory
        with open(os.path.join(str(tmp_path), "个人投资分析报告.xlsx"), "wb") as f:
            f.write(_make_holdings_xlsx())
        url = "/api/reports/" + quote("个人投资分析报告.xlsx")
        artifact_resp = client.get(url)
        assert artifact_resp.status_code == 200
        assert artifact_resp.data[:2] == b"PK"

    def test_both_type_artifacts(self, app_client, tmp_path):
        client = app_client
        resp = client.post("/api/upload", data={"file": (BytesIO(_make_holdings_xlsx()), "持仓.xlsx")})
        file_id = resp.get_json()["data"]["file_id"]

        resp = client.post("/api/runs", json={"file_id": file_id, "report_type": "both"})
        run_id = resp.get_json()["data"]["run_id"]
        detail = None
        for _ in range(200):
            detail = client.get(f"/api/runs/{run_id}").get_json()["data"]
            if detail["status"] in ("done", "failed"):
                break
            time.sleep(0.01)
        assert detail["status"] == "done"
        assert [a["kind"] for a in detail["artifacts"]] == ["html", "xlsx"]


class TestErrorEnvelope:
    """统一错误信封：{ok:false, error_code, error:中文}。"""

    def test_missing_file_id(self, app_client):
        resp = app_client.post("/api/runs", json={"report_type": "basic"})
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["ok"] is False
        assert body["error_code"] == "BAD_PARAM"
        assert body["error"]  # 中文文案

    def test_invalid_report_type(self, app_client):
        resp = app_client.post("/api/runs", json={"file_id": "x", "report_type": "weird"})
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_PARAM"

    def test_invalid_fetch_history_type(self, app_client):
        resp = app_client.post("/api/runs", json={"file_id": "x", "fetch_history": "yes"})
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_PARAM"

    def test_expired_file_id(self, app_client):
        resp = app_client.post("/api/runs", json={"file_id": "nonexistent"})
        assert resp.status_code == 404
        body = resp.get_json()
        assert body["error_code"] == "FILE_EXPIRED"

    def test_unknown_run_404(self, app_client):
        resp = app_client.get("/api/runs/no-such-run")
        assert resp.status_code == 404
        assert resp.get_json()["error_code"] == "NOT_FOUND"

    def test_queue_full_429(self, tmp_path, monkeypatch):
        monkeypatch.setitem(_config_defaults._DEFAULT_CONFIG, "output_dir", str(tmp_path))
        invalidate_config_cache()

        slow_calls = {"active": 0}

        def slow_exec(_state, _params):
            slow_calls["active"] += 1
            time.sleep(0.2)
            slow_calls["active"] -= 1
            return 0

        rm = RunManager(executor=slow_exec)
        app = create_app(rm)
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.post("/api/upload", data={"file": (BytesIO(_make_holdings_xlsx()), "持仓.xlsx")})
        file_id = resp.get_json()["data"]["file_id"]

        import src.python.web.runs as runs_mod

        # 塞满队列（容量 = _QUEUE_LIMIT）
        for _ in range(runs_mod._QUEUE_LIMIT):
            client.post("/api/runs", json={"file_id": file_id, "report_type": "basic"})
        overflow = client.post("/api/runs", json={"file_id": file_id, "report_type": "basic"})
        assert overflow.status_code == 429
        assert overflow.get_json()["error_code"] == "RUN_QUEUE_FULL"

    def test_upload_rejects_bad_file(self, app_client):
        resp = app_client.post(
            "/api/upload",
            data={"file": (BytesIO(b"NOTAZIP" + b"\x00" * 32), "伪装.xlsx")},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["ok"] is False
        assert body["error_code"] == "UPLOAD_BAD_FILE"
        assert body["error"]


class TestServeReportSecurity:
    """预览/下载防路径穿越与扩展名白名单（§6.2）。"""

    def test_extension_whitelist_rejects_py(self, app_client):
        resp = app_client.get("/api/reports/evil.py")
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_PARAM"

    def test_path_traversal_rejected(self, app_client):
        """.. 穿越：send_from_directory 内置净化拒绝（非 200 + JSON 信封）。"""
        resp = app_client.get("/api/reports/../data/config/config.json")
        # 400（扩展名/净化）或 404（NotFound）均可 —— 关键是不可泄露文件内容
        assert resp.status_code in (400, 404)
        body = resp.get_json()
        assert body["ok"] is False


class TestRunGeneration:
    """_run_generation 执行体（generate_report mock，真实上传预检 + 清理）。"""

    @patch("src.python.report.orchestrator.generate_report")
    def test_maps_exit_code_and_cleans_upload(self, mock_gen, monkeypatch):
        # 真实上传（预检通过）
        result = upload.save_upload(BytesIO(_make_holdings_xlsx()), "持仓.xlsx")
        file_id = result["file_id"]
        params = {"file_id": file_id, "report_type": "basic"}

        mock_gen.return_value = ReportResult(report_generated=True, excel_ok=True)
        state = RunState("r1", params)
        code = _run_generation(state, params)

        assert code == 0
        mock_gen.assert_called_once()
        # 产物 output_dir 取配置快照
        assert state.output_dir == _config_defaults._DEFAULT_CONFIG["output_dir"]
        # 上传临时文件立即清理
        assert upload.resolve_file(file_id) is None

    @patch("src.python.report.orchestrator.generate_report")
    def test_generate_report_error_mapping(self, mock_gen, monkeypatch):
        result = upload.save_upload(BytesIO(_make_holdings_xlsx()), "持仓.xlsx")
        file_id = result["file_id"]
        params = {"file_id": file_id, "report_type": "basic"}

        # 部分失败（errors 非空）→ exit_code 1
        mock_gen.return_value = ReportResult(report_generated=True, excel_ok=True, errors=["某模块失败"])
        state = RunState("r2", params)
        code = _run_generation(state, params)
        assert code == 1
        assert state.errors == ["某模块失败"]

    def test_missing_file_returns_severe(self):
        """file_id 已失效：返回严重退出码 + 错误提示。"""
        state = RunState("r3", {"file_id": "gone", "report_type": "basic"})
        code = _run_generation(state, {"file_id": "gone", "report_type": "basic"})
        assert code == 2
        assert state.errors == ["上传文件已过期，请重新上传"]

    def test_empty_holdings_gate_returns_severe(self, monkeypatch):
        """空持仓门（读取域单源）：run 读到空持仓 → 严重退出 + 统一四列提示，且不泄漏服务端路径。"""
        from types import SimpleNamespace

        result = upload.save_upload(BytesIO(_make_holdings_xlsx()), "持仓.xlsx")
        file_id = result["file_id"]
        params = {"file_id": file_id, "report_type": "basic"}
        monkeypatch.setattr(
            "src.python.core.reader.read_holdings_with_flows",
            lambda _p: SimpleNamespace(holdings=[], transactions=[], dividends=[]),
        )
        state = RunState("r-empty", params)
        code = _run_generation(state, params)
        assert code == 2
        assert state.errors and "持仓文件为空" in state.errors[0] and "四列" in state.errors[0]
        assert "/" not in state.errors[0]


class TestArtifactsExitCode:
    """产物清单按 exit_code/状态裁剪（错误处理完善）。"""

    def test_severe_no_artifacts(self):
        state = RunState("r", {"report_type": "both"})
        state.output_dir = "/tmp"
        state.exit_code = 2
        assert _build_artifacts(state.params, state) == []

    def test_failed_no_artifacts(self):
        state = RunState("r", {"report_type": "both"})
        state.output_dir = "/tmp"
        state.status = "failed"
        assert _build_artifacts(state.params, state) == []

    def test_partial_keeps_artifacts(self):
        """exit_code 1（部分失败）：产物仍可用。"""
        state = RunState("r", {"report_type": "both"})
        state.output_dir = "/tmp"
        state.exit_code = 1
        assert [a["kind"] for a in _build_artifacts(state.params, state)] == ["html", "xlsx"]

    def test_success_basic_only_xlsx(self):
        state = RunState("r", {"report_type": "basic"})
        state.output_dir = "/tmp"
        state.exit_code = 0
        assert [a["kind"] for a in _build_artifacts(state.params, state)] == ["xlsx"]


class TestCreateRunBoolParams:
    """阶段 2 表单显式提交布尔参数（历史走势/强制 LLM）。"""

    def test_fetch_history_bool_accepted(self, app_client):
        resp = app_client.post("/api/upload", data={"file": (BytesIO(_make_holdings_xlsx()), "持仓.xlsx")})
        file_id = resp.get_json()["data"]["file_id"]
        for value in (True, False):
            resp = app_client.post(
                "/api/runs", json={"file_id": file_id, "report_type": "basic", "fetch_history": value}
            )
            assert resp.status_code == 202, resp.get_json()

    def test_force_llm_bool_accepted(self, app_client):
        resp = app_client.post("/api/upload", data={"file": (BytesIO(_make_holdings_xlsx()), "持仓.xlsx")})
        file_id = resp.get_json()["data"]["file_id"]
        resp = app_client.post("/api/runs", json={"file_id": file_id, "report_type": "basic", "force_llm": True})
        assert resp.status_code == 202, resp.get_json()


class TestInputModeDispatch:
    """输入模式分派：试算隔离 vs 正式共享。

    执行体（_run_generation）直接调用 + generate_report mock；快照落盘用
    真实 capture_snapshot 副作用验证域隔离（而非仅参数断言）。
    正式覆盖类用例使用 `holdings_path_isolated`（conftest）避免触碰真实
    data/holdings/。
    """

    @staticmethod
    def _capture_side_effect(holdings, config, reporter, **kwargs):
        """generate_report mock 副作用：用真实 capture_snapshot 落快照（验证域隔离）。"""
        from src.python.report._snapshot import capture_snapshot

        capture_snapshot(
            holdings,
            [],
            config,
            MagicMock(),
            snapshot_namespace=kwargs.get("snapshot_namespace"),
        )
        return ReportResult(report_generated=True, excel_ok=True, history_ok=True)

    # ── 试算默认（快照隔离 web/ 域）──
    @patch("src.python.report.orchestrator.generate_report")
    def test_trial_default_snapshot_web(self, mock_gen, tmp_path):
        """试算默认：上传→run（不带 mode）→ 快照落 web/，主目录零新增，temp 清理。"""
        import src.python.report.history_snapshot as hs

        mock_gen.side_effect = self._capture_side_effect
        result = upload.save_upload(BytesIO(_make_holdings_xlsx()), "持仓.xlsx")
        file_id = result["file_id"]
        params = {"file_id": file_id, "report_type": "both"}
        state = RunState("r-trial-default", params)
        code = _run_generation(state, params)

        assert code == 0
        # 默认 mode=trial → namespace web
        assert mock_gen.call_args.kwargs.get("snapshot_namespace") == "web"
        # 快照落 web/ 域，主目录零新增（试算与共享时间线互不污染）
        assert len(hs.load_all("web")) >= 1
        assert len(hs.load_all()) == 0
        # temp 文件 finally 清理
        assert upload.resolve_file(file_id) is None

    # ── 正式 + 上传（提升正式文件 + 共享快照）──
    @patch("src.python.report.orchestrator.generate_report")
    def test_formal_upload_promotes_and_shared_snapshot(self, mock_gen, tmp_path, holdings_path_isolated, monkeypatch):
        """正式+上传：正式文件被覆盖、.bak 生成、快照落共享、temp 清理。"""
        # 持仓源守卫按真实 data/holdings/ 判定；本用例以 tmp 隔离目录模拟正式
        # 持仓目录，显式声明正式源以验证 web 正式模式的共享快照接线
        monkeypatch.setattr("src.python.config.is_formal_holdings_source", lambda _cfg=None: True)
        import src.python.report.history_snapshot as hs

        mock_gen.side_effect = self._capture_side_effect
        formal_path = os.path.join(holdings_path_isolated["holdings_dir"], holdings_path_isolated["holdings_filename"])
        os.makedirs(holdings_path_isolated["holdings_dir"], exist_ok=True)
        # 旧正式文件（任意字节即可，仅用于 .bak 断言）
        with open(formal_path, "wb") as f:
            f.write(b"OLD-FORMAL-CONTENT")

        new_bytes = _make_holdings_xlsx()
        result = upload.save_upload(BytesIO(new_bytes), "持仓.xlsx")
        file_id = result["file_id"]
        params = {"file_id": file_id, "report_type": "both", "mode": "formal"}
        state = RunState("r-formal-upload", params)
        code = _run_generation(state, params)

        assert code == 0
        # 正式文件被覆盖为上传内容
        with open(formal_path, "rb") as f:
            assert f.read() == new_bytes
        # 旧正式文件备份为 .bak
        with open(formal_path + ".bak", "rb") as f:
            assert f.read() == b"OLD-FORMAL-CONTENT"
        # 快照落共享主目录（namespace=None）
        assert mock_gen.call_args.kwargs.get("snapshot_namespace") is None
        assert len(hs.load_all()) >= 1
        # temp 上传文件清理（copy 提升后仍清理）
        assert upload.resolve_file(file_id) is None

    # ── 正式 + 用存量（直接读正式文件）──
    @patch("src.python.report.orchestrator.generate_report")
    def test_formal_use_existing_reads_formal_file(self, mock_gen, tmp_path, holdings_path_isolated, monkeypatch):
        """正式+用存量（无 file_id）：读正式文件、快照共享、无需上传。"""
        # 持仓源守卫按真实 data/holdings/ 判定；本用例以 tmp 隔离目录模拟正式
        # 持仓目录，显式声明正式源以验证 web 正式模式的共享快照接线
        monkeypatch.setattr("src.python.config.is_formal_holdings_source", lambda _cfg=None: True)
        import src.python.report.history_snapshot as hs

        mock_gen.side_effect = self._capture_side_effect
        formal_dir = holdings_path_isolated["holdings_dir"]
        formal_name = holdings_path_isolated["holdings_filename"]
        os.makedirs(formal_dir, exist_ok=True)
        with open(os.path.join(formal_dir, formal_name), "wb") as f:
            f.write(_make_holdings_xlsx())

        params = {"report_type": "both", "mode": "formal", "use_existing": True}
        state = RunState("r-formal-existing", params)
        code = _run_generation(state, params)

        assert code == 0
        assert mock_gen.call_args.kwargs.get("snapshot_namespace") is None
        assert len(hs.load_all()) >= 1
        # 无 file_id → 无临时文件清理需求
        assert upload.resolve_file("") is None

    def test_formal_use_existing_missing_file(self, tmp_path, holdings_path_isolated):
        """正式+用存量但正式文件不存在 → 严重退出码 + 友好错误。"""
        params = {"report_type": "both", "mode": "formal", "use_existing": True}
        state = RunState("r-formal-existing-missing", params)
        code = _run_generation(state, params)
        assert code == 2
        assert any("正式持仓文件不存在" in e for e in state.errors)

    # ── 参数组合校验（HTTP 层）──
    def test_trial_no_file_id_bad_param(self, app_client):
        resp = app_client.post("/api/runs", json={"report_type": "basic", "mode": "trial"})
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_PARAM"

    def test_formal_use_existing_with_file_id_bad_param(self, app_client):
        resp = app_client.post(
            "/api/runs",
            json={"file_id": "x", "report_type": "basic", "mode": "formal", "use_existing": True},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_PARAM"

    def test_invalid_mode_bad_param(self, app_client):
        resp = app_client.post("/api/runs", json={"report_type": "basic", "mode": "weird"})
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_PARAM"

    def test_invalid_use_existing_bad_param(self, app_client):
        resp = app_client.post("/api/runs", json={"report_type": "basic", "use_existing": "yes"})
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_PARAM"

    def test_formal_use_existing_submits_without_file_id(self, app_client):
        """正式+用存量：body 无 file_id 放行（202 提交成功，执行期才读正式文件）。"""
        resp = app_client.post(
            "/api/runs",
            json={"report_type": "basic", "mode": "formal", "use_existing": True},
        )
        assert resp.status_code == 202, resp.get_json()
        assert resp.get_json()["ok"] is True
