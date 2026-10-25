"""业务账本的按龄保留 —— 决策/信号账本不得无界增长，又不许裁掉反思样本。

业务约束（与遥测历史不同）：

- **决策账本**：一行一份状态（`decision` 登记 / `settlement` 结算）。按**行数**截断
  会连最旧的已结算样本一起裁掉，跨期反思随即失样本——所以按**龄**裁剪，
  且**已结算事件永久保留**（结算样本是反思链路的核心证据）。
- **信号账本**：折叠统计要看跨年同期，同样按龄（730 天）而非行数。
- **坏行不吞**：解析失败的行不由裁剪静默丢弃，留给读取侧告警。
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _line(day: str, **extra) -> str:
    payload = {"report_date": day, **extra}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"


def _write(path, lines: list[str]) -> None:
    path.write_text("".join(lines), encoding="utf-8")


def _read(path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class TestPruneByAge:
    """按龄裁剪原语：窗口内保留、窗口外丢弃、`keep` 命中永远保留。"""

    def test_drops_rows_older_than_window(self, tmp_path):
        from src.python.core.jsonl_store import prune_jsonl_by_age

        path = tmp_path / "ledger.jsonl"
        old = (date.today() - timedelta(days=800)).isoformat()
        recent = (date.today() - timedelta(days=10)).isoformat()
        _write(path, [_line(old, id="old"), _line(recent, id="new")])

        kept, dropped = prune_jsonl_by_age(path, retention_days=730, date_key="report_date")

        assert (kept, dropped) == (1, 1)
        assert [r["id"] for r in _read(path)] == ["new"]

    def test_keep_predicate_protects_old_rows(self, tmp_path):
        """已结算事件即使超龄也必须保留（反思样本）。"""
        from src.python.core.jsonl_store import prune_jsonl_by_age

        path = tmp_path / "ledger.jsonl"
        old = (date.today() - timedelta(days=900)).isoformat()
        _write(
            path,
            [
                _line(old, id="settled", event="settlement"),
                _line(old, id="stale-decision", event="decision"),
            ],
        )

        kept, dropped = prune_jsonl_by_age(
            path,
            retention_days=730,
            date_key="report_date",
            keep=lambda rec: rec.get("event") == "settlement",
        )

        assert (kept, dropped) == (1, 1)
        assert [r["id"] for r in _read(path)] == ["settled"]

    def test_malformed_line_is_kept_not_silently_dropped(self, tmp_path):
        """坏行保留：裁剪不得替读取侧吞掉损坏证据。"""
        from src.python.core.jsonl_store import prune_jsonl_by_age

        path = tmp_path / "ledger.jsonl"
        _write(path, ["{not json\n"])

        kept, dropped = prune_jsonl_by_age(path, retention_days=1, date_key="report_date")
        assert (kept, dropped) == (1, 0)
        assert path.read_text(encoding="utf-8").strip() == "{not json"

    def test_missing_file_is_noop(self, tmp_path):
        from src.python.core.jsonl_store import prune_jsonl_by_age

        assert prune_jsonl_by_age(str(tmp_path / "none.jsonl"), retention_days=10, date_key="report_date") == (0, 0)

    def test_zero_retention_disables_pruning(self, tmp_path):
        from src.python.core.jsonl_store import prune_jsonl_by_age

        path = tmp_path / "ledger.jsonl"
        old = (date.today() - timedelta(days=5000)).isoformat()
        _write(path, [_line(old, id="ancient")])
        assert prune_jsonl_by_age(path, retention_days=0, date_key="report_date") == (0, 0)
        assert _read(path), "0 表示不裁剪，文件不得被清空"

    def test_row_without_date_is_kept(self, tmp_path):
        """缺日期字段的行无法判龄 → 保留（宁留不误删）。"""
        from src.python.core.jsonl_store import prune_jsonl_by_age

        path = tmp_path / "ledger.jsonl"
        _write(path, [json.dumps({"id": "no-date"}) + "\n"])
        kept, dropped = prune_jsonl_by_age(path, retention_days=1, date_key="report_date")
        assert (kept, dropped) == (1, 0)


class TestDecisionLedgerRetention:
    """决策账本集成：写入路径触发裁剪，已结算事件不被裁掉。"""

    def test_retention_constant_is_two_years(self):
        from src.python.core.decision_ledger import DECISION_LEDGER_RETENTION_DAYS

        assert DECISION_LEDGER_RETENTION_DAYS == 730

    def test_append_prunes_stale_pending_decision(self, tmp_path):
        from src.python.core import decision_ledger as dl

        path = tmp_path / "decision_ledger.jsonl"
        old = (date.today() - timedelta(days=800)).isoformat()
        _write(path, [_line(old, event="decision", decision_id="old", status="pending")])

        dl.append_decision(code="600519", name="贵州茅台", direction=1, path=str(path))

        ids = [r.get("decision_id") for r in _read(path)]
        assert "old" not in ids, "超龄且未结算的决策应被裁掉"
        assert len(ids) == 1, "新决策必须写入"

    def test_append_keeps_settled_decision_beyond_window(self, tmp_path):
        from src.python.core import decision_ledger as dl

        path = tmp_path / "decision_ledger.jsonl"
        old = (date.today() - timedelta(days=1200)).isoformat()
        _write(path, [_line(old, event="settlement", decision_id="settled-old")])

        dl.append_decision(code="600519", name="贵州茅台", direction=1, path=str(path))

        events = _read(path)
        assert any(r.get("decision_id") == "settled-old" for r in events), "已结算样本必须保留"


class TestSignalLedgerRetention:
    """信号账本集成：按龄裁剪，幂等去重不受影响。"""

    def test_retention_constant_two_years(self):
        from src.python.core.signal_ledger import SIGNAL_LEDGER_RETENTION_DAYS

        assert SIGNAL_LEDGER_RETENTION_DAYS == 730

    def test_append_drops_over_age_signal(self, tmp_path):
        from src.python.core import signal_ledger as sl

        path = tmp_path / "signal_ledger.jsonl"
        old = (date.today() - timedelta(days=900)).isoformat()
        _write(path, [_line(old, id="old-sig", signal_type="t")])

        sl.append_signals([{"id": "new-sig", "report_date": date.today().isoformat()}], path=str(path))

        ids = [r.get("id") for r in _read(path)]
        assert "old-sig" not in ids
        assert "new-sig" in ids

    def test_idempotent_dedup_still_works_after_prune(self, tmp_path):
        """裁剪不影响幂等：同一 id 重复登记仍只写一次。"""
        from src.python.core import signal_ledger as sl

        path = tmp_path / "signal_ledger.jsonl"
        today = date.today().isoformat()
        first = sl.append_signals([{"id": "sig-1", "report_date": today}], path=str(path))
        second = sl.append_signals([{"id": "sig-1", "report_date": today}], path=str(path))
        assert len(first) == 1 and second == []
        assert len(_read(path)) == 1
