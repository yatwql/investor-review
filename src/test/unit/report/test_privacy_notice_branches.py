"""report/privacy_notice.py 的本地状态读写失败降级分支。

锁住的契约：
  - 首次运行标记读取失败时按「首次运行」处理（提示必现，不因状态文件不可读而静默吞掉）；
  - 标记写入失败只记 debug，不向上抛（隐私提示非关键路径）。
"""

from __future__ import annotations

import pytest

from src.python.report import privacy_notice as pn

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def test_is_first_run_true_when_flag_read_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(_key: str) -> bool:
        raise OSError("local_state 不可读")

    monkeypatch.setattr(pn, "get_local_flag", _boom)
    assert pn.is_first_run() is True


def test_mark_shown_swallows_write_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[tuple[str, bool]] = []

    def _fail(key: str, value: bool) -> None:
        attempts.append((key, value))
        raise OSError("local_state 只读")

    monkeypatch.setattr(pn, "get_local_flag", lambda _key: False)
    monkeypatch.setattr(pn, "set_local_flag", _fail)
    pn.mark_privacy_notice_shown()
    assert attempts == [("_privacy_notice_shown", True)]
