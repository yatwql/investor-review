"""内置定时生成调度器测试（web/scheduler.py + /api/scheduler 路由 + 前端面板接线）。

覆盖：配置解析（缺省关闭零行为、非法拒绝）/ 触发窗判定（未到点·执行日过滤·
宽限补触发·超窗登记错过·当日去重）/ 活动任务顺延与队列满不登记 / 账本持久化
与损坏兜底 / API 校验与同源守卫 / 前端面板源结构断言。
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

from src.python.config._config_defaults import _DEFAULT_CONFIG
from src.python.web import scheduler as scheduler_mod
from src.python.web.app import create_app
from src.python.web.runs import RunManager
from src.python.web.scheduler import (
    SchedulerService,
    next_fire_at,
    normalize_schedule_block,
    parse_schedule,
    schedule_signature,
    status_payload,
    validate_schedule_block,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_web]

INDEX_HTML = Path("src/static/web/index.html")
MAIN_JS = Path("src/static/web/main.js")
# 真值来源：调度块默认值以 _DEFAULT_CONFIG 为准（不在测试中写死派生量）
DEFAULTS = _DEFAULT_CONFIG["scheduler"]


class _FakeRun:
    def __init__(self, status: str) -> None:
        self.status = status


class _FakeRunManager:
    """记录 submit 调用的假队列（活动状态/队列满可编排）。"""

    def __init__(self, active_status: str | None = None, queue_full: bool = False) -> None:
        self.submitted: list[dict] = []
        self.active_status = active_status
        self.queue_full = queue_full

    def list_runs(self, limit: int = 10):
        return [_FakeRun(self.active_status)] if self.active_status else []

    def submit(self, params: dict):
        if self.queue_full:
            return None
        self.submitted.append(params)
        return "run-fake-1"


def _enabled_config(**overrides) -> dict:
    block = {"enabled": True, "time": "07:30", "weekdays": [0, 1, 2, 3, 4, 5, 6], "report_type": "basic"}
    block.update(overrides)
    return {"scheduler": block}


class TestParseSchedule:
    """配置解析：缺省关闭零行为、非法项拒绝。"""

    def test_absent_or_disabled_returns_none(self) -> None:
        """无 scheduler 块 / enabled 非 True / 配置为空 → 不调度。"""
        assert parse_schedule({}) is None
        assert parse_schedule({"scheduler": {"enabled": False}}) is None
        assert parse_schedule(None) is None

    def test_invalid_fields_rejected(self) -> None:
        """时刻越界 / 执行日空 / 报告格式非法 → 拒绝（记 WARNING 返回 None）。"""
        assert parse_schedule(_enabled_config(time="25:00")) is None
        assert parse_schedule(_enabled_config(weekdays=[])) is None
        assert parse_schedule(_enabled_config(report_type="huge")) is None

    def test_valid_block_parses_to_plan(self) -> None:
        """合法块解析出归一化时刻、分钟数、排序执行日与签名。"""
        schedule = parse_schedule(_enabled_config(time="7:05", weekdays=[6, 0]))
        assert schedule is not None
        assert schedule["time"] == "07:05"
        assert schedule["minutes"] == 7 * 60 + 5
        assert schedule["weekdays"] == [0, 6]
        assert schedule_signature(schedule) == "07:05|0,6|basic"


class TestValidateBlock:
    """接口校验：非法字段抛 ValueError（中文文案直映 400）。"""

    def test_valid_block_normalizes(self) -> None:
        block = validate_schedule_block({"enabled": True, "time": "8:05", "weekdays": [4, 0, 0], "report_type": "full"})
        assert block == {"enabled": True, "time": "08:05", "weekdays": [0, 4], "report_type": "full"}

    @pytest.mark.parametrize(
        "payload",
        [
            "not-a-dict",
            {"enabled": "yes", "time": "07:30", "weekdays": [0], "report_type": "basic"},
            {"enabled": True, "time": "25:00", "weekdays": [0], "report_type": "basic"},
            {"enabled": True, "time": "07:30", "weekdays": [], "report_type": "basic"},
            {"enabled": True, "time": "07:30", "weekdays": [7], "report_type": "basic"},
            {"enabled": True, "time": "07:30", "weekdays": ["x"], "report_type": "basic"},
            {"enabled": True, "time": "07:30", "weekdays": [0], "report_type": "huge"},
        ],
    )
    def test_invalid_payload_raises(self, payload) -> None:
        with pytest.raises(ValueError):
            validate_schedule_block(payload)


class TestNormalizeBlock:
    """面板回显归一化：缺块/非法字段回默认（真值来源 _DEFAULT_CONFIG）。"""

    def test_absent_block_yields_defaults(self) -> None:
        assert normalize_schedule_block(None) == DEFAULTS
        assert normalize_schedule_block("junk") == DEFAULTS

    def test_invalid_fields_fall_back_except_enabled(self) -> None:
        block = normalize_schedule_block({"enabled": True, "time": "99:99", "weekdays": [9], "report_type": "nope"})
        assert block["enabled"] is True
        assert block["time"] == DEFAULTS["time"]
        assert block["weekdays"] == DEFAULTS["weekdays"]
        assert block["report_type"] == DEFAULTS["report_type"]


class TestNextFireEstimate:
    """下次触发预估：今天未到点 → 今天；已过窗 → 下一匹配日；执行日过滤。"""

    def test_today_when_still_ahead(self) -> None:
        schedule = parse_schedule(_enabled_config())
        # 2026-01-06 是周二
        assert next_fire_at(datetime(2026, 1, 6, 6, 0), schedule) == datetime(2026, 1, 6, 7, 30)

    def test_next_day_after_window(self) -> None:
        schedule = parse_schedule(_enabled_config())
        assert next_fire_at(datetime(2026, 1, 6, 8, 0), schedule) == datetime(2026, 1, 7, 7, 30)

    def test_weekday_filter_skips_non_matching_days(self) -> None:
        schedule = parse_schedule(_enabled_config(weekdays=[0]))  # 仅周一
        # 周二 → 下一个周一 2026-01-12
        assert next_fire_at(datetime(2026, 1, 6, 6, 0), schedule) == datetime(2026, 1, 12, 7, 30)


class TestFireDecision:
    """tick 触发判定：时刻窗、执行日、当日去重、活动任务顺延、超窗登记。"""

    def _tick(self, rm: _FakeRunManager, now: datetime, monkeypatch, config: dict) -> str:
        monkeypatch.setattr("src.python.web.scheduler.get_config", lambda: config)
        return SchedulerService(rm).tick(now=now)

    def test_disabled_config_never_fires(self, monkeypatch) -> None:
        assert self._tick(_FakeRunManager(), datetime(2026, 1, 6, 7, 35), monkeypatch, {}) == "disabled"
        assert _FakeRunManager().submitted == []

    def test_due_within_grace_fires_formal_existing_run(self, monkeypatch) -> None:
        """触发窗内提交「正式-用存量」参数（file_id 空、模式锁定）。"""
        rm = _FakeRunManager()
        assert self._tick(rm, datetime(2026, 1, 6, 7, 35), monkeypatch, _enabled_config()) == "fired"
        assert len(rm.submitted) == 1
        params = rm.submitted[0]
        assert params["mode"] == "formal"
        assert params["use_existing"] is True
        assert params["file_id"] is None
        assert params["report_type"] == DEFAULTS["report_type"]

    def test_before_window_waits(self, monkeypatch) -> None:
        rm = _FakeRunManager()
        assert self._tick(rm, datetime(2026, 1, 6, 7, 29), monkeypatch, _enabled_config()) == "waiting"
        assert rm.submitted == []

    def test_non_matching_weekday_waits(self, monkeypatch) -> None:
        rm = _FakeRunManager()
        config = _enabled_config(weekdays=[0])  # 仅周一；2026-01-06 是周二
        assert self._tick(rm, datetime(2026, 1, 6, 7, 35), monkeypatch, config) == "waiting"
        assert rm.submitted == []

    def test_second_tick_same_day_is_duplicate(self, monkeypatch) -> None:
        """当日已触发 → 第二次评估去重（账本按计划签名+日期）。"""
        monkeypatch.setattr("src.python.web.scheduler._LEDGER_RETAIN_DAYS", 36500)  # 测试用远期日期不被剪除
        rm = _FakeRunManager()
        now = datetime(2026, 1, 6, 7, 35)
        monkeypatch.setattr("src.python.web.scheduler.get_config", lambda: _enabled_config())
        service = SchedulerService(rm)
        assert service.tick(now=now) == "fired"
        assert service.tick(now=now) == "duplicate"
        assert len(rm.submitted) == 1

    def test_active_run_defers_then_fires(self, monkeypatch) -> None:
        """存在活动任务（手动生成中）→ 顺延不登记；空闲后补触发。"""
        rm = _FakeRunManager(active_status="running")
        now = datetime(2026, 1, 6, 7, 35)
        assert self._tick(rm, now, monkeypatch, _enabled_config()) == "deferred"
        assert rm.submitted == []
        rm.active_status = None
        assert self._tick(rm, now, monkeypatch, _enabled_config()) == "fired"
        assert len(rm.submitted) == 1

    def test_queue_full_defers_without_ledger(self, monkeypatch) -> None:
        """队列满提交失败 → 不登记；恢复后宽限窗内重试成功。"""
        rm = _FakeRunManager(queue_full=True)
        now = datetime(2026, 1, 6, 7, 35)
        assert self._tick(rm, now, monkeypatch, _enabled_config()) == "deferred"
        rm.queue_full = False
        assert self._tick(rm, now, monkeypatch, _enabled_config()) == "fired"

    def test_grace_expired_marks_missed_without_fire(self, monkeypatch) -> None:
        """超宽限（30 分钟）→ 登记「错过」不补跑，且后续不再重复告警。"""
        monkeypatch.setattr("src.python.web.scheduler._LEDGER_RETAIN_DAYS", 36500)  # 测试用远期日期不被剪除
        rm = _FakeRunManager()
        monkeypatch.setattr("src.python.web.scheduler.get_config", lambda: _enabled_config())
        service = SchedulerService(rm)
        assert service.tick(now=datetime(2026, 1, 6, 8, 1)) == "missed"
        assert rm.submitted == []
        assert service.tick(now=datetime(2026, 1, 6, 8, 5)) == "duplicate"


class TestFiredLedger:
    """触发账本持久化：roundtrip、超保留期剔除、损坏兜底。"""

    def test_roundtrip_and_prune(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        scheduler_mod._save_fired({"sig-old": "2020-01-01", "sig-new": today})
        fired = scheduler_mod._load_fired()
        assert fired == {"sig-new": today}

    def test_corrupt_ledger_treated_as_empty(self) -> None:
        os.makedirs(os.path.dirname(scheduler_mod._FIRED_STATE_FILE), exist_ok=True)
        with open(scheduler_mod._FIRED_STATE_FILE, "w", encoding="utf-8") as f:
            f.write("{not-json")
        assert scheduler_mod._load_fired() == {}


class TestServiceThread:
    """常驻线程：启动幂等、停止收尾。"""

    def test_start_stop_lifecycle(self) -> None:
        service = SchedulerService(_FakeRunManager())
        service.start()
        try:
            assert service._thread is not None and service._thread.is_alive()
            service.start()  # 幂等：不重复建线程
            assert service._thread.is_alive()
        finally:
            service.stop(timeout=2.0)
        assert service._thread is None


class TestSchedulerApi:
    """GET/POST /api/scheduler：默认关闭回显、保存写配置、校验与同源守卫。"""

    def _client(self):
        rm = RunManager(executor=lambda state, params: 0)
        app = create_app(rm)
        app.config["TESTING"] = True
        return app.test_client()

    def test_get_defaults_to_disabled(self) -> None:
        data = self._client().get("/api/scheduler").get_json()["data"]
        assert data["enabled"] is DEFAULTS["enabled"]
        assert data["time"] == DEFAULTS["time"]
        assert data["weekdays"] == DEFAULTS["weekdays"]
        assert data["next_fire"] is None  # 缺省关闭无下次触发

    def test_post_valid_persists_and_enables(self) -> None:
        from src.python.config import get_config

        client = self._client()
        resp = client.post(
            "/api/scheduler",
            json={"enabled": True, "time": "08:05", "weekdays": [0, 2, 4], "report_type": "full"},
        )
        assert resp.status_code == 200
        assert get_config()["scheduler"] == {
            "enabled": True,
            "time": "08:05",
            "weekdays": [0, 2, 4],
            "report_type": "full",
        }
        data = client.get("/api/scheduler").get_json()["data"]
        assert data["enabled"] is True
        assert data["next_fire"]  # 启用后给出下次触发预估

    @pytest.mark.parametrize(
        "payload",
        [
            {"enabled": "yes", "time": "07:30", "weekdays": [0], "report_type": "basic"},
            {"enabled": True, "time": "25:00", "weekdays": [0], "report_type": "basic"},
            {"enabled": True, "time": "07:30", "weekdays": [], "report_type": "basic"},
            {"enabled": True, "time": "07:30", "weekdays": [0], "report_type": "huge"},
        ],
    )
    def test_post_invalid_rejected(self, payload) -> None:
        resp = self._client().post("/api/scheduler", json=payload)
        assert resp.status_code == 400

    def test_post_cross_site_rejected(self) -> None:
        resp = self._client().post(
            "/api/scheduler",
            json={"enabled": True, "time": "07:30", "weekdays": [0], "report_type": "basic"},
            headers={"Sec-Fetch-Site": "cross-site"},
        )
        assert resp.status_code == 403


class TestStatusPayload:
    """状态载荷：关闭无下次触发，启用后给出预估与宽限分钟数。"""

    def test_disabled_config_has_no_next_fire(self) -> None:
        data = status_payload({})
        assert data["enabled"] is False
        assert data["next_fire"] is None
        assert data["grace_minutes"] >= 1


class TestSchedulerPanelWiring:
    """调度面板前端接线（源结构断言，防回退）。"""

    def test_index_card_controls(self) -> None:
        html = INDEX_HTML.read_text(encoding="utf-8")
        for element_id in ("sched-enabled", "sched-time", "sched-type", "sched-save", "sched-status", "sched-next"):
            assert f'id="{element_id}"' in html
        assert html.count('class="sched-weekday-cb"') == len(DEFAULTS["weekdays"])

    def test_main_js_load_save_and_init_wire(self) -> None:
        src = MAIN_JS.read_text(encoding="utf-8")
        assert "function loadScheduler()" in src and "'/api/scheduler'" in src
        assert "function saveScheduler()" in src
        assert "safeRun(loadScheduler" in src
        assert "els.schedSave.addEventListener('click', saveScheduler)" in src
