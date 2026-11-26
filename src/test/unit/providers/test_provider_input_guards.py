"""数据源侧的输入防御分支：限购数值解析、DataSink 配置/配额降级。

断言落在「畸形载荷 → 声明的缺省值/放行」这一具体结果上，不校验实现细节。
"""

from __future__ import annotations

import pytest

import src.python.providers.datasink as datasink
from src.python.providers.tiantian_purchase import _limit_to_float, _optional_float, parse_purchase_table

pytestmark = [pytest.mark.unit, pytest.mark.unit_providers]


class TestLimitParsing:
    """限购金额解析：缺失/空白 → None（不当作 0 元限购）。"""

    def test_missing_limit_is_none(self):
        assert _limit_to_float(None) is None

    def test_blank_limit_is_none(self):
        assert _limit_to_float("   ") is None


class TestOptionalFloat:
    """可选浮点（费率等）：空白 → None，不兜底成 0。"""

    def test_blank_optional_float_is_none(self):
        assert _optional_float("") is None


class TestPurchaseTableTypeGuard:
    """非字符串载荷（上游返回 None/字典）→ None，不进正则解析。"""

    def test_non_string_payload_returns_none(self):
        assert parse_purchase_table(None) is None


class TestDatasinkConfigDegradation:
    """配置不可读 → 空节（按套餐默认），不抛错。"""

    def test_unreadable_config_returns_empty_section(self, monkeypatch):
        def _boom():
            raise RuntimeError("配置不可用")

        monkeypatch.setattr("src.python.config.get_config", _boom)

        assert datasink._datasink_config() == {}


class TestQuotaGuard:
    """配额解析为 0（不限用）时直接放行，不读计数文件。"""

    def test_zero_quota_allows_request(self, monkeypatch):
        monkeypatch.setattr(datasink, "resolve_daily_quota", lambda cfg=None: 0)

        assert datasink._consume_quota() is True
