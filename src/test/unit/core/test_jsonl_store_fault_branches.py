"""JSONL 原语的故障降级：不可读文件、按龄裁剪的非对象行与空批量追加。

JSONL 原语的契约是「读侧永不因单点故障中途中止」：不可读即当空/当不可裁，
非对象行（合法 JSON 但不是账本记录）由裁剪侧原样保留交给读侧告警。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.core import jsonl_store as js

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def test_append_many_with_no_lines_skips_disk(tmp_path):
    """空批量追加直接返回成功且不落盘（不凭空造出空账本文件）。"""
    target = tmp_path / "ledger.jsonl"

    assert js.append_jsonl_atomic_many(str(target), []) is True
    assert not target.exists()


def test_append_many_unreadable_existing_file_recreates(tmp_path):
    """既有文件不可读 → 告警后按新内容重建（不让旧内容阻塞本次追加）。"""
    target = tmp_path / "ledger.jsonl"

    with patch("src.python.core.jsonl_store.os.path.isfile", return_value=True):
        ok = js.append_jsonl_atomic_many(str(target), ['{"a": 1}\n'])

    assert ok is True
    assert target.read_text(encoding="utf-8") == '{"a": 1}\n'


def test_read_jsonl_unreadable_file_returns_empty(tmp_path):
    """读取抛 ``OSError`` → 返回空列表（调用方按无记录处理）。"""
    with patch("src.python.core.jsonl_store.os.path.isfile", return_value=True):
        assert js.read_jsonl(str(tmp_path / "missing.jsonl")) == []


def test_prune_unreadable_file_reports_nothing_pruned(tmp_path):
    """裁剪时文件不可读 → 返回 (0, 0)，不向上抛异常。"""
    with patch("src.python.core.jsonl_store.os.path.isfile", return_value=True):
        result = js.prune_jsonl_by_age(str(tmp_path / "missing.jsonl"), retention_days=7, date_key="date")

    assert result == (0, 0)


def test_prune_keeps_non_object_lines(tmp_path):
    """合法 JSON 但非对象的行原样保留（裁剪不做读侧的语义判断）。"""
    target = tmp_path / "ledger.jsonl"
    target.write_text('[1, 2]\n{"date": "2020-01-01"}\n', encoding="utf-8")

    kept, dropped = js.prune_jsonl_by_age(str(target), retention_days=1, date_key="date")

    assert (kept, dropped) == (1, 1)
    assert "[1, 2]" in target.read_text(encoding="utf-8"), "非对象行必须留给读侧告警"
