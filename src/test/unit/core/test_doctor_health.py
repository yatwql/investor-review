"""doctor「日志与缓存」自检组（日志级别/体积/锚点/运行台账）。

审计驱动：默认日志 DEBUG 占比 91%、锚点文件 38MB、每 run 告警 11 条——本组把
这三类「看得见的历史债」变成一键自检项，避免每次都要人工翻日志判断。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.python.core import doctor, doctor_logs

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


@pytest.fixture(autouse=True)
def _redirect_paths(tmp_path, monkeypatch):
    """全部探针路径重定向到临时目录（自检读的是真实日志/台账，测试不得读用户数据）。

    探针实现已下沉 `core/doctor_logs`（调用点即该模块），故 patch 指向 `doctor_logs`；
    仅断言「入口仍可经 doctor 引用」时才用 doctor 名。
    """
    monkeypatch.setattr(doctor_logs, "_APP_LOG_PATH", str(tmp_path / "app.log"))
    monkeypatch.setattr(doctor_logs, "_DEDUP_ANCHOR_PATH", str(tmp_path / "dedup_anchors.jsonl"))
    monkeypatch.setattr(doctor_logs, "_PERF_LEDGER_PATH", str(tmp_path / "perf_history.jsonl"))
    monkeypatch.setattr(doctor_logs, "_LOGS_DIR", str(tmp_path))
    return tmp_path


class TestLogLevel:
    def test_default_info(self, monkeypatch):
        monkeypatch.delenv("INVEST_LOG_FILE_LEVEL", raising=False)
        item = doctor._check_log_level()
        assert item["ok"] is True
        assert "INFO" in item["message"]

    def test_debug_mode_hints_restore(self, monkeypatch):
        monkeypatch.setenv("INVEST_LOG_FILE_LEVEL", "debug")
        item = doctor._check_log_level()
        assert "DEBUG" in item["message"]
        assert "unset INVEST_LOG_FILE_LEVEL" in item["hint"]


class TestLogVolume:
    def _write_log(self, path, debug_ratio: float, lines: int = 200):
        debug_count = int(lines * debug_ratio)
        body = []
        for i in range(lines):
            level = "DEBUG" if i < debug_count else "INFO"
            body.append(f"2026-10-22 10:00:00,000 [{level}] line {i}")
        path.write_text("\n".join(body) + "\n", encoding="utf-8")

    def test_debug_heavy_log_flagged(self, tmp_path):
        self._write_log(tmp_path / "app.log", 0.9)
        item = doctor._check_log_volume()
        assert item["ok"] is False
        assert "DEBUG 占比" in item["message"]
        assert "INVEST_LOG_FILE_LEVEL" in item["hint"]

    def test_info_dominant_log_passes(self, tmp_path):
        self._write_log(tmp_path / "app.log", 0.1)
        assert doctor._check_log_volume()["ok"] is True


class TestDedupAnchor:
    def test_missing_anchor_is_fine(self):
        item = doctor._check_dedup_anchor()
        assert item["ok"] is True
        assert "未生成" in item["message"]

    def test_oversized_anchor_flagged_with_compact_hint(self, monkeypatch):
        import pathlib

        tmp = pathlib.Path(doctor_logs._DEDUP_ANCHOR_PATH)
        tmp.write_text("{}\n" * 10, encoding="utf-8")
        monkeypatch.setattr(doctor_logs, "_ANCHOR_COMPACT_BYTES", 10)
        item = doctor._check_dedup_anchor()
        assert item["ok"] is False
        assert "eval-dedup-threshold.py --compact" in item["hint"]


class TestPerfLedger:
    def _write_ledger(self, path, warnings: int, errors: list[str] | None = None, n: int = 10):
        rows = [{"status": "completed", "counters": {"warnings": warnings}, "errors": errors or []} for _ in range(n)]
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    def test_low_warnings_pass(self, tmp_path):
        self._write_ledger(tmp_path / "perf_history.jsonl", 1)
        item = doctor._check_perf_ledger_health()
        assert item["ok"] is True
        assert "告警中位 1" in item["message"]

    def test_high_warnings_or_errors_flagged(self, tmp_path):
        self._write_ledger(tmp_path / "perf_history.jsonl", 12, ["boom"])
        item = doctor._check_perf_ledger_health()
        assert item["ok"] is False
        assert "累计错误 10" in item["message"]

    def test_small_sample_not_judged(self, tmp_path):
        self._write_ledger(tmp_path / "perf_history.jsonl", 99, n=2)
        item = doctor._check_perf_ledger_health()
        assert item["ok"] is True
        assert "样本不足" in item["message"]


class TestPerfLedgerFactFix:
    """事实校验自动修正中位可见：计数进得了 perf_history，也要看得见。"""

    def test_fact_fix_median_surfaced(self, tmp_path):
        rows = [
            {"status": "completed", "counters": {"warnings": 1, "fact_fix_total": n}, "errors": []} for n in (2, 4, 9)
        ]
        (tmp_path / "perf_history.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        item = doctor._check_perf_ledger_health()
        assert "事实校验自动修正中位 4 处" in item["message"]

    def test_no_fact_fix_keeps_message_short(self, tmp_path):
        rows = [{"status": "completed", "counters": {"warnings": 1}, "errors": []} for _ in range(5)]
        (tmp_path / "perf_history.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        item = doctor._check_perf_ledger_health()
        assert "事实校验自动修正" not in item["message"]


class TestAnchorPathSource:
    """doctor 与采集侧必须指向同一个锚点文件（曾误指 data/cache 下的陈旧副本）。"""

    def test_path_matches_producer(self):
        import os

        from src.python.providers import news_dedup

        # 两边都可能被测试隔离重定向，比较相对尾部（data/calibration/dedup_anchors.jsonl）
        tail = os.path.join(*Path(news_dedup._ANCHOR_PATH).parts[-3:])
        assert doctor._DEDUP_ANCHOR_REL == tail


class TestGroupWiring:
    def test_group_registered_in_order(self):
        assert doctor.GROUP_LOG_CACHE in doctor.GROUP_ORDER

    def test_run_checks_includes_group(self):
        results = doctor.run_doctor_checks(include_network=False)
        groups = {r["group"] for r in results}
        assert doctor.GROUP_LOG_CACHE in groups


class TestNetworkTimeoutSingleSource:
    """网络检查预算三渠道同源（此前 CLI 8s / Web 12s / TUI 6s 各写一份字面量）。"""

    def test_defaults_declared_in_core(self):
        from src.python.core import doctor

        assert doctor.NETWORK_TIMEOUT_DEFAULT > 0
        assert doctor.NETWORK_TIMEOUT_WEB >= doctor.NETWORK_TIMEOUT_DEFAULT
        assert doctor.NETWORK_TIMEOUT_MIN > 0

    @pytest.mark.parametrize(
        ("value", "expected"),
        [(None, 8.0), ("", 8.0), ("abc", 8.0), (0, 8.0), (-3, 8.0), (0.2, 1.0), (12, 12.0), ("6.5", 6.5)],
    )
    def test_normalize(self, value, expected):
        from src.python.core.doctor import normalize_network_timeout

        assert normalize_network_timeout(value) == pytest.approx(expected)

    def test_web_and_cli_budgets_come_from_core(self):
        """CLI 默认与 TUI 预算都取 core 常量（改预算只改一处）。"""
        from src.python.cli._parser import _build_parser
        from src.python.core import doctor
        from src.python.tui import handlers_log

        args = _build_parser().parse_args(["doctor"])
        assert args.timeout == pytest.approx(doctor.NETWORK_TIMEOUT_DEFAULT)
        assert handlers_log._DOCTOR_NETWORK_TIMEOUT == pytest.approx(doctor.NETWORK_TIMEOUT_DEFAULT)
