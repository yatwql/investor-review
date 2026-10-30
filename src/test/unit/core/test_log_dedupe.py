"""`core/log_dedupe` 单元测试。

覆盖：同键窗口内折叠、窗口外再上屏、不同键互不影响、重置、参数透传。
"""

from __future__ import annotations

import logging

import pytest

from src.python.core import log_dedupe

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


@pytest.fixture(autouse=True)
def _reset_windows():
    """每个用例从空窗口开始，避免用例间互相折叠。"""
    log_dedupe.reset()
    yield
    log_dedupe.reset()


def test_first_call_logs_at_info(caplog):
    logger = logging.getLogger("invest")
    with caplog.at_level(logging.DEBUG, logger="invest"):
        assert log_dedupe.log_throttled(logger, "k", "批量就绪: %d/%d", 3, 3) is True
    assert "批量就绪: 3/3" in caplog.text
    assert any(record.levelno == logging.INFO for record in caplog.records)


def test_repeat_in_window_folds_to_debug(caplog, monkeypatch):
    logger = logging.getLogger("invest")
    monkeypatch.setattr(log_dedupe.time, "monotonic", lambda: 100.0)
    log_dedupe.log_throttled(logger, "k", "同一行 %d", 1)
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="invest"):
        assert log_dedupe.log_throttled(logger, "k", "同一行 %d", 2) is False
    assert [r.levelno for r in caplog.records if r.name == "invest"] == [logging.DEBUG]
    assert "已折叠" in caplog.text


def test_after_window_logs_again(caplog, monkeypatch):
    logger = logging.getLogger("invest")
    clock = {"now": 0.0}
    monkeypatch.setattr(log_dedupe.time, "monotonic", lambda: clock["now"])
    log_dedupe.log_throttled(logger, "k", "行", window_secs=10.0)
    clock["now"] = 11.0
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="invest"):
        assert log_dedupe.log_throttled(logger, "k", "行", window_secs=10.0) is True
    assert "同窗口重复" not in caplog.text


def test_different_keys_independent(caplog, monkeypatch):
    logger = logging.getLogger("invest")
    monkeypatch.setattr(log_dedupe.time, "monotonic", lambda: 50.0)
    with caplog.at_level(logging.INFO, logger="invest"):
        assert log_dedupe.log_throttled(logger, "a", "甲") is True
        assert log_dedupe.log_throttled(logger, "b", "乙") is True
    assert "甲" in caplog.text
    assert "乙" in caplog.text


def test_reset_clears_window(monkeypatch):
    logger = logging.getLogger("invest")
    monkeypatch.setattr(log_dedupe.time, "monotonic", lambda: 70.0)
    assert log_dedupe.log_throttled(logger, "k", "行") is True
    assert log_dedupe.log_throttled(logger, "k", "行") is False
    log_dedupe.reset()
    assert log_dedupe.log_throttled(logger, "k", "行") is True


def test_level_override_used_on_first_call(caplog):
    logger = logging.getLogger("invest")
    with caplog.at_level(logging.WARNING, logger="invest"):
        log_dedupe.log_throttled(logger, "k", "告警行", level=logging.WARNING)
    assert any(r.levelno == logging.WARNING for r in caplog.records)
