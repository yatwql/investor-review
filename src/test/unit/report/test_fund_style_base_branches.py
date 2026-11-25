"""report/fund_style_base.py 的 Provider 惰性注册幂等分支。

锁住的契约：``tencent_style`` Provider 只注册一次，重复调用不再触发注册（避免重复登记同一 tier）。
"""

from __future__ import annotations

import pytest

from src.python.report import fund_style_base as fsb

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def test_tencent_provider_registered_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, int, float]] = []

    class _Registry:
        def register_provider(self, name: str, tier: int = 0, timeout: float = 0.0) -> None:
            calls.append((name, tier, timeout))

    monkeypatch.setattr("src.python.core.provider_registry.get_registry", lambda: _Registry())
    monkeypatch.setattr(fsb, "_tencent_registered", False)

    fsb._ensure_tencent_provider_registered()
    fsb._ensure_tencent_provider_registered()

    assert calls == [("tencent_style", 4, 15.0)]
