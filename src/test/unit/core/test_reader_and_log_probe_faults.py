"""持仓读取与日志自检探针的容错分支测试。

覆盖契约（`core/reader.py`）：
  - 文件枚举：目录不可读返回空、文件 mtime 取不到退化为 0
  - 主表解析：单行构造失败（ValueError/TypeError）告警后跳过，不影响同表其它行
  - 流水读取：非 xlsx 转成 ValueError；流水页签空表/空行/缺代码/日期非法逐行跳过
  - `is_holdings_sheet` 对空工作表（max_row 为 None）返回 False

覆盖契约（`core/doctor_logs.py`）：
  - 四项探针各自读取失败时不向上抛，转为「失败行 + 排查提示」
  - 日志体积采样到上限即停；体积超阈值走「日志总量偏大」提示
  - 锚点分片枚举目录不可读按未生成处理；行计数对不可读文件返回 0
  - 运行台账空行/坏行跳过
  - 分组编排对单项抛异常的行内兜底
"""

from __future__ import annotations

import json
from unittest import mock

import pytest
from openpyxl import Workbook

from src.python.core import doctor_logs, reader
from src.python.core.doctor_common import GROUP_LOG_CACHE

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _workbook_with_sheet(title: str, rows: list[list]) -> Workbook:
    """构造单页签工作簿（第一行即表头）。"""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title
    for row in rows:
        sheet.append(row)
    return workbook


# ── 文件枚举 ────────────────────────────────────────────


class TestFileEnumeration:
    def test_unreadable_directory_returns_empty(self, tmp_path, monkeypatch):
        """目录存在但不可读（listdir 抛 OSError）时返回空列表而非抛异常。"""
        monkeypatch.setattr(reader.os, "listdir", mock.Mock(side_effect=OSError("permission denied")))

        assert reader.list_xlsx_files(str(tmp_path)) == []

    def test_missing_mtime_degrades_to_zero(self, tmp_path, monkeypatch):
        """文件 mtime 取不到（并发删除/改名）时退化为 0，枚举仍完成。"""
        monkeypatch.setattr(reader.os.path, "getmtime", mock.Mock(side_effect=OSError("gone")))

        assert reader._file_mtime(str(tmp_path / "gone.xlsx")) == 0.0


# ── 主表解析 ────────────────────────────────────────────


class TestParseWorkbookRowFaults:
    def test_row_construction_failure_is_skipped(self, monkeypatch):
        """单行 Holding 构造抛 TypeError 时告警并跳过，同表后续行照常入库。"""
        workbook = _workbook_with_sheet(
            "主账户", [list(reader.HOLDINGS_HEADER), ["坏行", "600519", 100, 1.0], ["好行", "000001", 200, 2.0]]
        )
        original_init = reader.Holding.__init__

        def _flaky_init(self, *args, **kwargs):
            if kwargs.get("name") == "坏行":
                raise TypeError("构造失败")
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(reader.Holding, "__init__", _flaky_init)

        holdings = reader._parse_workbook(workbook)

        assert [holding.name for holding in holdings] == ["好行"]


# ── 流水页签读取 ────────────────────────────────────────


class TestReadFlowSheets:
    def test_non_xlsx_file_raises_value_error(self, tmp_path):
        """文件不是有效 xlsx 时报 ValueError（提示用户确认文件类型）。"""
        broken = tmp_path / "holdings.xlsx"
        broken.write_text("not a zip", encoding="utf-8")

        with pytest.raises(ValueError, match="文件格式错误"):
            reader.read_flow_sheets(str(broken))

    def test_trade_sheet_skips_blank_and_codeless_rows(self):
        """交易流水页签跳过全空行与缺代码行，只保留合法记录。"""
        workbook = _workbook_with_sheet(
            reader._TRADE_SHEET_NAME,
            [
                list(reader.TRADE_HEADER),
                [None, None, None, None, None],
                ["2026-01-05", None, "买入", 100, 1.0],
                ["2026-01-06", "600519", "买入", 100, 1.0],
            ],
        )

        records = reader._parse_trade_sheet(workbook.active)

        assert [(record.code, record.date) for record in records] == [("600519", "2026-01-06")]

    def test_empty_dividend_sheet_returns_no_record(self):
        """分红流水页签只有表头（max_row < 2）时告警并返回空列表。"""
        workbook = _workbook_with_sheet(reader._DIVIDEND_SHEET_NAME, [list(reader._DIVIDEND_HEADER)])

        assert reader._parse_dividend_sheet(workbook.active) == []

    def test_dividend_sheet_skips_blank_codeless_and_invalid_date_rows(self):
        """分红流水页签逐行跳过：全空行、缺代码行、日期非法行都不入记录。"""
        workbook = _workbook_with_sheet(
            reader._DIVIDEND_SHEET_NAME,
            [
                list(reader._DIVIDEND_HEADER),
                [None, None, None],
                ["2026-01-05", None, 0.5],
                ["not-a-date", "600519", 0.5],
                ["2026-01-07", "600519", 0.5],
            ],
        )

        records = reader._parse_dividend_sheet(workbook.active)

        assert [(record.code, record.date) for record in records] == [("600519", "2026-01-07")]


# ── 主表判定 ────────────────────────────────────────────


class TestIsHoldingsSheet:
    def test_sheet_without_rows_is_not_holdings(self, monkeypatch):
        """工作表行数为 None（空表）时不判为持仓主表。"""
        sheet = mock.Mock()
        sheet.title = "主账户"
        sheet.max_row = None

        assert reader.is_holdings_sheet(sheet) is False


# ── 日志自检：日志体积 ──────────────────────────────────


class TestLogVolumeProbe:
    def test_scan_stops_at_sample_limit(self, tmp_path, monkeypatch):
        """日志行数超过采样上限即停，采样行数不超过上限。"""
        app_log = tmp_path / "app.log"
        app_log.write_text("[DEBUG] noise\n" * 20, encoding="utf-8")
        monkeypatch.setattr(doctor_logs, "_APP_LOG_PATH", str(app_log))
        monkeypatch.setattr(doctor_logs, "_LOG_SCAN_MAX_LINES", 5)

        item = doctor_logs._check_log_volume()

        assert "采样 5 行" in item["message"]

    def test_oversized_log_hints_cleanup(self, tmp_path, monkeypatch):
        """总量超阈值但 DEBUG 占比正常时给出「删除旧轮转」提示。"""
        app_log = tmp_path / "app.log"
        app_log.write_text("[INFO] ok\n", encoding="utf-8")
        monkeypatch.setattr(doctor_logs, "_APP_LOG_PATH", str(app_log))
        monkeypatch.setattr(doctor_logs, "_LOG_SCAN_MAX_LINES", 10)
        monkeypatch.setattr(
            doctor_logs,
            "glob",
            mock.Mock(glob=mock.Mock(return_value=[str(app_log)])),
        )
        real_getsize = doctor_logs.os.path.getsize

        def _getsize(path):
            return 400 * 1_000_000 if str(path) == str(app_log) else real_getsize(path)

        monkeypatch.setattr(doctor_logs.os.path, "getsize", _getsize)

        item = doctor_logs._check_log_volume()

        assert item["ok"] is False
        assert "日志总量偏大" in item["hint"]

    def test_unreadable_app_log_reports_failure(self, monkeypatch):
        """读取日志体积抛 OSError 时转成失败行并给出目录权限提示。"""
        monkeypatch.setattr(doctor_logs.os.path, "exists", mock.Mock(side_effect=OSError("denied")))

        item = doctor_logs._check_log_volume()

        assert item["ok"] is False
        assert "logs/ 目录权限" in item["hint"]


# ── 日志自检：去重锚点 ──────────────────────────────────


class TestDedupAnchorProbe:
    def test_unreadable_anchor_directory_means_not_generated(self, tmp_path, monkeypatch):
        """锚点目录不可枚举时按「未生成」处理（不报失败）。"""
        monkeypatch.setattr(doctor_logs, "_DEDUP_ANCHOR_PATH", str(tmp_path / "missing" / "dedup_anchors.jsonl"))
        monkeypatch.setattr(doctor_logs.os, "listdir", mock.Mock(side_effect=OSError("denied")))

        item = doctor_logs._check_dedup_anchor()

        assert item["ok"] is True
        assert "未生成" in item["message"]

    def test_unreadable_anchor_file_counts_zero_lines(self, tmp_path):
        """锚点行计数对不可读文件返回 0（不抛异常）。"""
        anchor = tmp_path / "dedup_anchors-202601.jsonl"
        anchor.write_text("{}\n", encoding="utf-8")
        assert doctor_logs._count_anchor_lines(str(anchor)) == 1

        assert doctor_logs._count_anchor_lines(str(tmp_path / "gone.jsonl")) == 0

    def test_anchor_size_failure_reports_group_row(self, tmp_path, monkeypatch):
        """锚点体积统计抛 OSError 时转成失败行并指向校准目录权限。"""
        anchor_dir = tmp_path / "calibration"
        anchor_dir.mkdir()
        (anchor_dir / "dedup_anchors-202601.jsonl.gz").write_bytes(b"")
        monkeypatch.setattr(doctor_logs, "_DEDUP_ANCHOR_PATH", str(anchor_dir / "dedup_anchors.jsonl"))
        monkeypatch.setattr(doctor_logs.os.path, "getsize", mock.Mock(side_effect=OSError("denied")))

        item = doctor_logs._check_dedup_anchor()

        assert item["ok"] is False
        assert "data/calibration/ 权限" in item["hint"]


# ── 日志自检：运行台账 ──────────────────────────────────


class TestPerfLedgerProbe:
    def test_blank_and_corrupt_lines_are_skipped(self, tmp_path, monkeypatch):
        """台账空行与坏行跳过；剩余记录不足 3 条时按样本不足放行。"""
        ledger = tmp_path / "perf_history.jsonl"
        ledger.write_text("\n{not json\n" + json.dumps({"counters": {"warnings": 1}}) + "\n", encoding="utf-8")
        monkeypatch.setattr(doctor_logs, "_PERF_LEDGER_PATH", str(ledger))

        item = doctor_logs._check_perf_ledger_health()

        assert item["ok"] is True
        assert "样本不足" in item["message"]

    def test_unreadable_ledger_reports_failure(self, tmp_path, monkeypatch):
        """台账存在但读取抛 OSError 时转成失败行并指向 state 目录权限。"""
        ledger = tmp_path / "perf_history.jsonl"
        ledger.write_text("{}\n", encoding="utf-8")
        monkeypatch.setattr(doctor_logs, "_PERF_LEDGER_PATH", str(ledger))
        monkeypatch.setattr("builtins.open", mock.Mock(side_effect=OSError("denied")))

        item = doctor_logs._check_perf_ledger_health()

        assert item["ok"] is False
        assert "data/state/ 权限" in item["hint"]


# ── 分组编排 ────────────────────────────────────────────


class TestLogsAndCacheGroup:
    def test_probe_exception_becomes_failure_row(self, monkeypatch):
        """任一探针抛异常时该行记失败，其余探针结果照常返回。"""

        def _boom() -> dict:
            raise RuntimeError("boom")

        monkeypatch.setattr(doctor_logs, "_check_log_level", _boom)

        items = doctor_logs._check_logs_and_cache()

        assert len(items) == 4, "四项探针各出一行，单项异常不吞掉其它行"
        failed = [item for item in items if not item["ok"]]
        assert failed and failed[0]["label"] == "_boom"
        assert failed[0]["group"] == GROUP_LOG_CACHE
