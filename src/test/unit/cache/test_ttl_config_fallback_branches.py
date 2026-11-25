"""缓存 TTL 的配置降级分支（cache/_ttl.py）。

测试场景：
  1. ``profit_forecast`` 走动态指纹键（不按 prefix+identifier 拼接）
  2. 未注册数据类型 / 无标识符 → 年龄不可得（None）
  3. 静态 TTL：config 覆盖优先，非正值回落注册表默认
  4. 配置读取异常 → 清理侧 TTL 回落注册表默认（不中断清理）
"""

from __future__ import annotations

from typing import Any

import pytest

from src.python.cache import _ttl as ttl
from src.python.core.constants import CACHE_DAILY
from src.python.core.registry import get_cache_ttl_defaults

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestCacheAgeByDataType:
    """按数据类型取缓存年龄的两条路径。"""

    def test_profit_forecast_uses_dynamic_fingerprint_key(self, monkeypatch):
        """``profit_forecast`` → 委托动态指纹键，年龄取该键。"""
        seen: list[str] = []

        def _age(key: str) -> float:
            seen.append(key)
            return 42.0

        monkeypatch.setattr("src.python.fetcher.akshare.get_profit_forecast_cache_key", lambda: "profit_forecast_abc123")
        monkeypatch.setattr(ttl, "get_cache_age", _age)
        assert ttl.get_cache_age_by_data_type("profit_forecast") == 42.0
        assert seen == ["profit_forecast_abc123"]

    @pytest.mark.parametrize(("data_type", "identifier"), [("no_such_type", "000001"), ("index", None)])
    def test_unregistered_type_or_missing_identifier_returns_none(self, data_type: str, identifier: str | None):
        """未注册类型 / 无标识符 → 无法拼键，年龄不可得。"""
        assert ttl.get_cache_age_by_data_type(data_type, identifier) is None


class TestStaticTtlBranches:
    """``_static_ttl`` 的覆盖与回落。"""

    def test_positive_config_override_wins(self):
        """config_ttl 正值 → 覆盖注册表默认。"""
        assert ttl._static_ttl("fund", {"cache_ttl": {"fund": 123}}, {"fund": 456.0}) == pytest.approx(123.0)

    def test_nonpositive_override_falls_back_to_default(self):
        """非正覆盖值视为无效 → 回落注册表默认。"""
        assert ttl._static_ttl("fund", {"cache_ttl": {"fund": 0}}, {"fund": 456.0}) == pytest.approx(456.0)

    def test_unlisted_type_falls_back_to_daily(self):
        """既无覆盖也无默认 → 兜底日级 TTL。"""
        assert ttl._static_ttl("未知类型", {}, {}) == pytest.approx(CACHE_DAILY)


class TestCleanupTtlConfigFailure:
    """``get_cleanup_ttl`` 在配置读取异常时仍给出可用 TTL。"""

    def test_config_read_exception_uses_registry_default(self, monkeypatch):
        """配置读取抛异常 → 记录 debug 并回落注册表默认（清理不因此停摆）。"""

        def _boom() -> dict[str, Any]:
            raise RuntimeError("配置读取失败")

        monkeypatch.setattr("src.python.config.get_config", _boom)
        expected = get_cache_ttl_defaults().get("fund", CACHE_DAILY)
        assert ttl.get_cleanup_ttl("fund") == pytest.approx(expected)
