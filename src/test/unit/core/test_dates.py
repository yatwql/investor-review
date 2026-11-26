"""日期解析统一口径单元测试 — ``core/dates.py`` 三个口径函数的失败语义。

断言即「替换前各调用点的原语义」：
  - ``parse_datetime_ymd``：``%Y-%m-%d`` 严格解析；非法/非字符串 → None
    （原 ``except (ValueError, TypeError): return None``）
  - ``parse_iso_date``：ISO 纯日期；非法/非字符串 → None
    （原 ``except (TypeError, ValueError): return None``）
  - ``parse_datetime_iso``：ISO 日期时间；非法 → None，非字符串仍抛 TypeError
    （原调用点只捕 ``except ValueError``，故类型错误不在吞没范围）

运行：
  python -m pytest src/test/unit/core/test_dates.py -v
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from src.python.core.dates import parse_datetime_iso, parse_datetime_ymd, parse_iso_date

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestParseDatetimeYmd:
    """``%Y-%m-%d`` → datetime；失败返回 None。"""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("2024-03-01", datetime(2024, 3, 1)),
            ("2024-02-29", datetime(2024, 2, 29)),
            ("1999-12-31", datetime(1999, 12, 31)),
            # strptime 对月/日零填充宽容（与 parse_iso_date 的严格 ISO 口径不同）
            ("2024-3-1", datetime(2024, 3, 1)),
        ],
    )
    def test_valid_input_returns_datetime(self, text, expected):
        assert parse_datetime_ymd(text) == expected

    @pytest.mark.parametrize(
        "text",
        ["", "2024-13-01", "2023-02-29", "2024/03/01", " 2024-03-01 "],
    )
    def test_invalid_input_returns_none(self, text):
        assert parse_datetime_ymd(text) is None

    @pytest.mark.parametrize("value", [None, 20240301, date(2024, 3, 1)])
    def test_non_str_input_returns_none(self, value):
        # 原调用点用 except (ValueError, TypeError)，TypeError 同样返回 None
        assert parse_datetime_ymd(value) is None


class TestParseIsoDate:
    """ISO 纯日期 → date；失败返回 None。"""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("2024-03-01", date(2024, 3, 1)),
            ("2024-02-29", date(2024, 2, 29)),
            ("2015-06-12", date(2015, 6, 12)),
        ],
    )
    def test_valid_input_returns_date(self, text, expected):
        assert parse_iso_date(text) == expected

    @pytest.mark.parametrize(
        "text",
        ["", "2024-03-01T10:00:00", "2024-13-01", "2024/03/01", " 2024-03-01 "],
    )
    def test_invalid_input_returns_none(self, text):
        assert parse_iso_date(text) is None

    @pytest.mark.parametrize("value", [None, 20240301])
    def test_non_str_input_returns_none(self, value):
        # 原调用点用 except (TypeError, ValueError)，TypeError 同样返回 None
        assert parse_iso_date(value) is None


class TestParseDatetimeIso:
    """ISO 日期时间 → datetime；ValueError 返回 None，非字符串抛 TypeError。"""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("2024-03-01T10:00:00", datetime(2024, 3, 1, 10, 0, 0)),
            ("2024-03-01", datetime(2024, 3, 1)),
            ("20240301T100000", datetime(2024, 3, 1, 10, 0, 0)),
        ],
    )
    def test_valid_input_returns_datetime(self, text, expected):
        assert parse_datetime_iso(text) == expected

    def test_timezone_offset_is_preserved(self):
        parsed = parse_datetime_iso("2024-03-01T10:00:00+08:00")
        assert parsed == datetime(2024, 3, 1, 2, 0, 0, tzinfo=timezone.utc)
        assert parsed.utcoffset() == timezone(timedelta(hours=8)).utcoffset(None)

    @pytest.mark.parametrize("text", ["", "not-a-timestamp", "2024-13-01T00:00:00"])
    def test_invalid_input_returns_none(self, text):
        assert parse_datetime_iso(text) is None

    def test_non_str_input_raises_type_error(self):
        # 原调用点只捕 ValueError：非字符串入参的 TypeError 语义保持不吞
        with pytest.raises(TypeError):
            parse_datetime_iso(None)
