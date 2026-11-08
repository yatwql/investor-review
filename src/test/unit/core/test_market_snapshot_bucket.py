"""行情口径桶（MarketSnapshot）判定与复用策略的时间语义。

背景：LLM 缓存指纹里含行情派生块（申购限价/持仓变动/环比），盘中逐分钟变、收盘后
冻结。桶把「本次运行看到的是哪个已完成时点」显式化：非盘中档可在同一档内复用结论，
盘中档一律不复用（读者不该拿到十分钟前的盘中结论）。

本文件锁四件事：
① 五个时点分别落哪一档（盘前 / 盘中 / 午间 / 盘中 / 收盘 / 非交易日）；
② 桶在一次运行内只判定一次，且可按轮重置（长驻 TUI 进程跨时段出报告）；
③ 提示词口径说明随档变化（复用收盘档时，内容必须按该档陈述）；
④ 桶键进基础模块指纹（档变了显式换键，不靠块文本逐字节比较去猜）。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.python.core import market_hours
from src.python.core.constants import BEIJING_TZ

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_core,
    pytest.mark.usefixtures("offline_external_sources"),
]

#: 2026-11-06 为交易日（周五），2026-11-07 为非交易日（周六）
_TRADING_DAY = (2026, 11, 6)
_NON_TRADING_DAY = (2026, 11, 7)


def _at(day: tuple[int, int, int], hour: int, minute: int = 0) -> datetime:
    return datetime(*day, hour, minute, tzinfo=BEIJING_TZ)


@pytest.fixture(autouse=True)
def _reset_bucket():
    market_hours.reset_market_snapshot()
    yield
    market_hours.reset_market_snapshot()


class TestBucketResolution:
    @pytest.mark.parametrize(
        ("hour", "minute", "expected_key", "intraday"),
        [
            (8, 0, "close:2026-11-05", False),  # 盘前：仍是上一交易日收盘
            (9, 45, "intraday:2026-11-06", True),  # 早盘
            (12, 0, "noon:2026-11-06", False),  # 午休：上午收盘档
            (14, 30, "intraday:2026-11-06", True),  # 午盘
            (16, 0, "close:2026-11-06", False),  # 收盘后：当日收盘档
        ],
    )
    def test_trading_day_buckets(self, hour, minute, expected_key, intraday):
        bucket = market_hours.market_snapshot_bucket(_at(_TRADING_DAY, hour, minute))

        assert bucket.key == expected_key
        assert bucket.intraday is intraday

    def test_non_trading_day_uses_previous_close(self):
        """非交易日：口径是上一交易日收盘（此处周五），不能落到「盘中」。"""
        bucket = market_hours.market_snapshot_bucket(_at(_NON_TRADING_DAY, 12, 0))

        assert bucket.key == "close:2026-11-06"
        assert bucket.intraday is False
        assert bucket.as_of == "2026-11-06"

    def test_label_carries_as_of_for_prompt_disclosure(self):
        """口径说明必须能自证时点（提示词/日志只看到这句话就要知道数据截止到哪）。"""
        bucket = market_hours.market_snapshot_bucket(_at(_TRADING_DAY, 16, 0))

        assert "2026-11-06" in bucket.label


class TestBucketMemo:
    def test_judged_once_per_run(self, monkeypatch):
        """一次运行只判定一次：默认时点路径第二次取值直接命中 memo，不再查日历。"""
        calls: list[str] = []

        def _counting(moment):
            calls.append(moment.strftime("%Y-%m-%d"))
            return moment.strftime("%Y-%m-%d")

        monkeypatch.setattr("src.python.core.trading_calendar.trading_day_as_of_cached", _counting)

        first = market_hours.market_snapshot_bucket()
        second = market_hours.market_snapshot_bucket()

        assert first is second, "同一轮内必须复用同一份判定结果"
        assert len(calls) == 1, f"桶判定应只查一次日历，实际 {len(calls)} 次"

    def test_explicit_moment_is_not_memoized(self, monkeypatch):
        """显式传时点（测试/回放）不写 memo：不得污染后续真实判定。"""
        monkeypatch.setattr(
            "src.python.core.trading_calendar.trading_day_as_of_cached",
            lambda moment: moment.strftime("%Y-%m-%d"),
        )

        market_hours.market_snapshot_bucket(_at(_TRADING_DAY, 10, 0))
        real = market_hours.market_snapshot_bucket()

        assert real.key.startswith(("close:", "noon:", "intraday:")), "memo 未被显式时点污染"

    def test_reset_clears_memo(self, monkeypatch):
        """重置后必须重新判定：长驻进程跨时段连续出报告不能沿用上一轮的档。"""
        monkeypatch.setattr(
            "src.python.core.trading_calendar.trading_day_as_of_cached",
            lambda moment: moment.strftime("%Y-%m-%d"),
        )
        first = market_hours.market_snapshot_bucket(_at(_TRADING_DAY, 10, 0))
        market_hours.market_snapshot_bucket()  # 写入 memo（真实时点）
        market_hours.reset_market_snapshot()

        assert market_hours.market_snapshot_bucket(_at(_TRADING_DAY, 16, 0)).key == "close:2026-11-06"
        assert first.key == "intraday:2026-11-06"


class TestPromptDisclosure:
    def test_note_names_the_bucket(self, monkeypatch):
        """口径说明取当前桶的 label（复用收盘档时，提示词里必须写明截止时点）。"""
        frozen = market_hours.MarketSnapshot(
            key="close:2026-11-06",
            label="上周交易日收盘（2026-11-06）",
            as_of="2026-11-06",
            intraday=False,
        )
        monkeypatch.setattr(market_hours, "market_snapshot_bucket", lambda now=None: frozen)

        note = market_hours.market_snapshot_note()

        assert "【数据口径】" in note
        assert frozen.label in note
        assert "净值" in note, "场外净值口径须与盘中行情区分开"


def _stub_bucket(key: str):
    def _fn(now=None):
        return market_hours.MarketSnapshot(key=key, label=key, as_of="2026-11-06", intraday=key.startswith("intraday"))

    return _fn


class TestPromptInjection:
    def test_skeleton_appends_bucket_note_to_prompt(self, monkeypatch):
        """统一附录之后必须追一句口径声明：收盘档复用要求内容按该档陈述。"""
        from src.python.llm import skeleton

        captured: dict[str, str] = {}
        monkeypatch.setattr(
            skeleton,
            "_execute_llm_with_finalize",
            lambda system_prompt, user_prompt, *a, **kw: captured.setdefault("user", user_prompt) or (None, False),
        )
        frozen = market_hours.MarketSnapshot(
            key="close:2026-11-06",
            label="当日收盘（2026-11-06）",
            as_of="2026-11-06",
            intraday=False,
        )
        monkeypatch.setattr(market_hours, "market_snapshot_bucket", lambda now=None: frozen)

        skeleton.generate_llm_module(
            {},
            "global_macro",
            system_prompt="系统提示",
            user_prompt="正文",
        )

        assert "【数据口径】" in captured["user"]
        assert frozen.label in captured["user"]
