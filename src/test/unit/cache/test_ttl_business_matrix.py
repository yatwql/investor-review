"""缓存 TTL 业务矩阵 —— 时段 × 数据类型 × 覆盖层的组合契约（intraday 敏感性是重点）。

为什么要有这份矩阵：TTL 同时承担两个互相拉扯的目标——

- **数据敏感性**：盘中价格/指数分钟级变化，缓存过期太慢会把盘中价当成收盘价
  （"本日盈亏/快照环比"系统性偏离，属已修复过的真实故障）；
- **性能与上游负担**：盘后/夜里/周末价格不再变化，若仍按秒级过期，每份报告都会
  白打一次上游；非行情数据（新闻、情绪、财报）更不该被盘中降频。

本文件把「时段 × 类型 × 覆盖层」的期望值钉成矩阵，并额外验证**读了能命中/过期即未命中**
（get_ttl 与实际读路径一致）与**清理侧按同一 TTL 判定**。这样后续任何 TTL 重构只要
跑这组用例，就能立刻看出"哪一格变松/变紧"。

业务时段语义按 A 股：09:30–11:30、13:00–15:00；午间休市（11:30–13:00）、盘前、盘后、
夜间、周末与法定节假日都按非交易时段处理。
"""

from __future__ import annotations

import json
import time
from datetime import datetime

import pytest

from src.python.core.registry import get_cache_ttl_defaults, get_market_ttl_map

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


# ── 会话场景表：业务语义 → is_market_open 判定 ─────────────────────

#: (场景标签, 是否交易时段, 说明)
SESSION_CASES = [
    ("pre_open", False, "盘前 09:00，价格仍是上一交易日收盘"),
    ("morning", True, "上午盘中 10:00"),
    ("lunch_break", False, "午间休市 12:00，拿到的是上午收盘价"),
    ("afternoon", True, "下午盘中 14:00"),
    ("post_close", False, "收盘后 15:30，收盘价已定型"),
    ("night", False, "夜间 21:00"),
    ("weekend", False, "周六 10:00"),
    ("holiday", False, "法定节假日 10:00"),
]

#: 关键类型：盘中敏感（价/指）与各类静态 TTL（新闻/情绪/财报/负缓存/LLM）
TYPE_CASES = ["price", "index", "news", "sentiment", "report", "datasink_probe_miss", "report_symbol_miss"]


@pytest.fixture()
def cache_env(tmp_path, monkeypatch):
    """缓存目录隔离（`_paths` 与 `_cleanup` 各有一份模块级绑定）。"""
    from src.python.cache import _cleanup, _paths, _store

    monkeypatch.setattr(_paths, "_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(_cleanup, "_CACHE_DIR", str(tmp_path))
    _store.reset_debug_log_state()
    yield tmp_path
    _store.reset_debug_log_state()


@pytest.fixture()
def ttl_env(monkeypatch, cache_env):
    """TTL 解析环境：可注入配置与盘中判定，返回设置函数。"""

    def _setup(config: dict, is_open: bool) -> None:
        from src.python.cache import _ttl

        monkeypatch.setattr(_ttl, "_is_market_open", lambda: is_open)
        monkeypatch.setattr("src.python.config.get_config", lambda: config)

    return _setup


def _write_cache(cache_dir, key: str, age_seconds: float) -> None:
    from src.python.cache._paths import _CACHE_KEY_VERSION

    payload = {"_ts": time.time() - age_seconds, "_data": {"v": 1}}
    (cache_dir / f"{key}_{_CACHE_KEY_VERSION}.json").write_text(json.dumps(payload), encoding="utf-8")


def _expected_ttl(data_type: str, is_open: bool, config: dict) -> float:
    """矩阵期望值：盘中敏感类型在交易时段走盘中 TTL，其余走静态覆盖/注册表默认。"""
    registry_default = get_cache_ttl_defaults()[data_type]
    market_ttl = get_market_ttl_map().get(data_type)
    if market_ttl is not None and is_open:
        raw = config.get("market_hour_ttl", market_ttl)
        try:
            return max(30.0, min(86400.0, float(raw)))
        except (TypeError, ValueError):
            return max(30.0, min(86400.0, float(market_ttl)))
    overrides = config.get("cache_ttl") or {}
    if data_type in overrides and float(overrides[data_type]) > 0:
        return float(overrides[data_type])
    return float(registry_default)


@pytest.mark.parametrize("label,is_open,_desc", SESSION_CASES, ids=[c[0] for c in SESSION_CASES])
@pytest.mark.parametrize("data_type", TYPE_CASES)
def test_ttl_matrix_matches_business_semantics(ttl_env, label, is_open, _desc, data_type):
    """时段 × 类型矩阵：盘中敏感类型仅交易时段降频，其余类型始终静态 TTL。"""
    ttl_env({}, is_open)
    from src.python.cache import get_ttl

    expected = _expected_ttl(data_type, is_open, {})
    assert get_ttl(data_type) == expected, f"{data_type} @ {label} 期望 {expected}s"


@pytest.mark.parametrize("label,is_open,_desc", SESSION_CASES, ids=[c[0] for c in SESSION_CASES])
def test_cache_read_uses_same_ttl_as_resolver(ttl_env, cache_env, label, is_open, _desc):
    """读路径与 `get_ttl` 同口径：写入一份「刚过期 1 秒」的价格缓存，盘中必不命中。"""
    ttl_env({}, is_open)
    from src.python.cache import get as cache_get, get_ttl

    ttl = get_ttl("price")
    _write_cache(cache_env, "price_600519", age_seconds=ttl + 1)
    assert cache_get("price_600519", ttl) is None, f"{label}: 超过 TTL 必须判未命中"
    _write_cache(cache_env, "price_601398", age_seconds=max(ttl - 1, 0))
    assert cache_get("price_601398", ttl) == {"v": 1}, f"{label}: TTL 之内必须命中"


@pytest.mark.parametrize("label,is_open,_desc", SESSION_CASES, ids=[c[0] for c in SESSION_CASES])
def test_cleanup_uses_same_ttl_as_resolver(ttl_env, cache_env, label, is_open, _desc):
    """清理路径与读路径同口径：同一份缓存不能出现「读未命中但清理保留」或反之。"""
    from src.python.cache import get_ttl

    ttl_env({}, is_open)
    ttl = get_ttl("price")
    _write_cache(cache_env, "price_600519", age_seconds=ttl + 1)
    from src.python.cache._cleanup import cleanup_expired

    assert cleanup_expired(dry_run=False) == 1, f"{label}: 超过 TTL 的价必须被清理"
    _write_cache(cache_env, "price_601398", age_seconds=max(ttl - 1, 0))
    assert cleanup_expired(dry_run=True) == 0, f"{label}: TTL 内的价不得被清理"


class TestOverrideLayers:
    """覆盖层组合：cache_ttl（静态） / market_hour_ttl（盘中） / 非法值 / 退役键。"""

    def test_cache_ttl_override_applies_to_static_types(self, ttl_env):
        ttl_env({"cache_ttl": {"news": 300}}, is_open=True)
        from src.python.cache import get_ttl

        assert get_ttl("news") == 300, "非盘中敏感类型按 cache_ttl 覆盖（盘中也不降频）"

    def test_cache_ttl_override_applies_to_intraday_type_after_close(self, ttl_env):
        ttl_env({"cache_ttl": {"price": 43200}}, is_open=False)
        from src.python.cache import get_ttl

        assert get_ttl("price") == 43200, "盘后价格走静态覆盖，不为实时白打上游"

    def test_market_hour_ttl_override_applies_intraday(self, ttl_env):
        ttl_env({"market_hour_ttl": 60}, is_open=True)
        from src.python.cache import get_ttl

        assert get_ttl("price") == 60
        assert get_ttl("index") == 60

    @pytest.mark.parametrize("bad_value", [0, -5, "abc"])
    def test_invalid_market_hour_ttl_falls_back_to_registry(self, ttl_env, bad_value):
        ttl_env({"market_hour_ttl": bad_value}, is_open=True)
        from src.python.cache import get_ttl

        assert get_ttl("price") == get_market_ttl_map()["price"]

    @pytest.mark.parametrize("bad_value", [0, -1, "abc"])
    def test_invalid_cache_ttl_override_falls_back_to_registry(self, ttl_env, bad_value):
        ttl_env({"cache_ttl": {"news": bad_value}}, is_open=False)
        from src.python.cache import get_ttl

        assert get_ttl("news") == get_cache_ttl_defaults()["news"]

    def test_retired_market_hour_aware_cannot_make_news_intraday(self, ttl_env):
        """退役键即使还写着 news，新闻也不能被降频（数据敏感性的反向保护）。"""
        ttl_env({"market_hour_aware": ["news"], "market_hour_ttl": 30, "cache_ttl": {"news": 900}}, is_open=True)
        from src.python.cache import get_ttl

        assert get_ttl("news") == 900


class TestBusinessScenarios:
    """业务场景级断言：同一天多次报告、收盘后、负缓存、LLM 模块 TTL。"""

    def test_same_day_second_run_reuses_price_within_30s(self, ttl_env, cache_env):
        """盘中 30 秒内第二份报告复用行情（避免同分钟连打上游）。"""
        ttl_env({}, is_open=True)
        from src.python.cache import get as cache_get, get_ttl

        _write_cache(cache_env, "price_600519", age_seconds=20)
        assert cache_get("price_600519", get_ttl("price")) == {"v": 1}

    def test_same_day_second_run_refetches_after_30s(self, ttl_env, cache_env):
        """超过 30 秒必须重新取价（敏感性优先于省请求）。"""
        ttl_env({}, is_open=True)
        from src.python.cache import get as cache_get, get_ttl

        _write_cache(cache_env, "price_600519", age_seconds=31)
        assert cache_get("price_600519", get_ttl("price")) is None

    def test_after_close_price_survives_overnight(self, ttl_env, cache_env):
        """收盘后到次日盘前的报告复用收盘价（24h 静态 TTL，不白打上游）。"""
        ttl_env({}, is_open=False)
        from src.python.cache import get as cache_get, get_ttl

        _write_cache(cache_env, "price_600519", age_seconds=18 * 3600)
        assert cache_get("price_600519", get_ttl("price")) == {"v": 1}

    def test_negative_probe_cache_lasts_twelve_hours(self, ttl_env, cache_env):
        """财报章节 404 负缓存：11h 内不再重试，13h 后允许重试。"""
        ttl_env({}, is_open=False)
        from src.python.cache import get as cache_get, get_ttl

        ttl = get_ttl("datasink_probe_miss")
        _write_cache(cache_env, "datasink_probe_miss_abc123", age_seconds=11 * 3600)
        assert cache_get("datasink_probe_miss_abc123", ttl) is not None
        _write_cache(cache_env, "datasink_probe_miss_def456", age_seconds=13 * 3600)
        assert cache_get("datasink_probe_miss_def456", ttl) is None

    def test_symbol_miss_cache_shorter_than_probe_cache(self, ttl_env):
        """标的正文缺失（6h）比章节探测（12h）更短：结论越粗，越早允许重试。"""
        ttl_env({}, is_open=False)
        from src.python.cache import get_ttl

        assert get_ttl("report_symbol_miss") < get_ttl("datasink_probe_miss")

    def test_llm_module_ttl_boundary(self, ttl_env, cache_env):
        """LLM 模块（expert_review 4h）：3h59 命中、4h01 未命中（成本与时效边界）。"""
        ttl_env({}, is_open=False)
        from src.python.cache import get as cache_get, get_ttl

        ttl = get_ttl("llm_expert_review")
        _write_cache(cache_env, "llm_expert_review_abc", age_seconds=ttl - 60)
        assert cache_get("llm_expert_review_abc", ttl) is not None
        _write_cache(cache_env, "llm_expert_review_def", age_seconds=ttl + 60)
        assert cache_get("llm_expert_review_def", ttl) is None


class TestSessionSemantics:
    """时段语义本身：默认时段边界、午休、周末（法定节假日由交易日历在别处判定）。"""

    @pytest.mark.parametrize(
        "hour,minute,expected",
        [
            (9, 29, False),
            (9, 30, True),
            (11, 30, True),
            (11, 31, False),
            (12, 59, False),
            (13, 0, True),
            (15, 0, True),
            (15, 1, False),
        ],
    )
    def test_market_open_fallback_boundaries(self, monkeypatch, hour, minute, expected):
        """默认时段边界：09:30–11:30 / 13:00–15:00（含端点），午休与盘后为非交易时段。"""
        from src.python.core import market_hours

        fixed = datetime(2026, 10, 23, hour, minute)  # 周五
        monkeypatch.setattr(market_hours, "datetime", _FrozenDatetime(fixed))
        market_hours.reset_memo_state()
        current_min = hour * 60 + minute
        assert market_hours._is_market_open_fallback(current_min) is expected

    def test_market_open_fallback_weekend_closed(self, monkeypatch):
        """周末全天非交易时段（周六 10:00 仍是收盘价）。"""
        from src.python.core import market_hours

        fixed = datetime(2026, 10, 24, 10, 0)  # 周六
        monkeypatch.setattr(market_hours, "datetime", _FrozenDatetime(fixed))
        market_hours.reset_memo_state()
        assert market_hours._is_market_open_fallback(10 * 60) is False


class _FrozenDatetime(datetime):
    """固定 `now()` 的 datetime 替身（仅替换 market_hours 模块内引用）。"""

    _fixed: datetime | None = None

    def __new__(cls, fixed: datetime):  # noqa: D102 — 测试替身
        instance = super().__new__(cls, fixed.year, fixed.month, fixed.day, fixed.hour, fixed.minute)
        cls._fixed = fixed
        return instance

    @classmethod
    def now(cls, tz=None):  # noqa: D102 — 测试替身
        fixed = cls._fixed or datetime.now(tz)
        return fixed.replace(tzinfo=tz) if tz else fixed
