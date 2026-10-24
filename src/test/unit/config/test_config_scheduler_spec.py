"""``config._scheduler`` 调度块归一化/严格校验（Web 面板与 CLI 共用）。

覆盖宽松回显（缺省/非法项回默认）与严格写入（非法字段报错，不静默改正）两个口径，
以及真值来源 ``_DEFAULT_CONFIG["scheduler"]``。
"""

from __future__ import annotations

import pytest

from src.python.config._config_defaults import _DEFAULT_CONFIG
from src.python.config._scheduler import (
    DEFAULT_BLOCK,
    REPORT_TYPES,
    normalize_block,
    validate_block,
    validate_field,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]


class TestNormalizeBlock:
    """宽松归一化：面板回显不应因脏配置罢工。"""

    def test_defaults_come_from_config_defaults(self):
        assert DEFAULT_BLOCK == _DEFAULT_CONFIG["scheduler"]
        assert normalize_block(None) == DEFAULT_BLOCK

    def test_invalid_fields_fall_back_but_enabled_kept(self):
        block = normalize_block({"enabled": True, "time": "9:5", "weekdays": [9], "report_type": "huge"})
        assert block["enabled"] is True
        assert block["time"] == DEFAULT_BLOCK["time"]
        assert block["weekdays"] == DEFAULT_BLOCK["weekdays"]
        assert block["report_type"] == DEFAULT_BLOCK["report_type"]


class TestValidateBlock:
    """严格校验：接口/命令行的非法取值必须报错。"""

    def test_valid_block_normalizes(self):
        block = validate_block({"enabled": False, "time": "8:05", "weekdays": [6, 0, 0], "report_type": "full"})
        assert block == {"enabled": False, "time": "08:05", "weekdays": [0, 6], "report_type": "full"}

    @pytest.mark.parametrize(
        "payload",
        [
            "not-a-dict",
            {"enabled": "yes", "time": "07:30", "weekdays": [0], "report_type": "basic"},
            {"enabled": True, "time": "24:00", "weekdays": [0], "report_type": "basic"},
            {"enabled": True, "time": "07:30", "weekdays": [], "report_type": "basic"},
            {"enabled": True, "time": "07:30", "weekdays": [7], "report_type": "basic"},
            {"enabled": True, "time": "07:30", "weekdays": [0], "report_type": "huge"},
        ],
    )
    def test_invalid_payload_raises(self, payload):
        with pytest.raises(ValueError):
            validate_block(payload)

    def test_report_types_are_the_cli_subset(self):
        assert REPORT_TYPES == ("basic", "both", "full")


class TestValidateField:
    """单字段校验（CLI ``config set scheduler.<字段>``）。"""

    def test_time_normalized(self):
        assert validate_field("time", "8:05") == "08:05"

    def test_weekdays_sorted_unique(self):
        assert validate_field("weekdays", [6, 0, 0]) == [0, 6]

    def test_unknown_field_raises(self):
        with pytest.raises(ValueError, match="未知调度字段"):
            validate_field("nope", "x")

    @pytest.mark.parametrize(
        ("field", "value"),
        [("enabled", "yes"), ("time", "25:00"), ("weekdays", []), ("weekdays", [7]), ("report_type", "huge")],
    )
    def test_invalid_values_raise(self, field, value):
        with pytest.raises(ValueError):
            validate_field(field, value)
