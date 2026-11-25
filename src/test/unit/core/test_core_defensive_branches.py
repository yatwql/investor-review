"""core 层防御分支：交易日历 memo/冷却、系统信息兜底、日志配置降级。

测试场景：
  1. 日历 memo 过期 / TTL 不可用（非数值、非正）→ 退化为未命中、memo 置空
  2. 日历失败冷却与缓存读异常 → ``cached_trading_days`` 返回空表且不触网
  3. 取数锁内二次 memo 命中（并发线程已填 memo）→ 直接复用
  4. 交易日不可解析 → 自然日差兜底并保证非负
  5. 系统信息：跨盘符路径原样、探测被中断时向上抛出、配置形态异常/解析异常兜底
  6. 日志配置：文件缺失 / JSONC 损坏 / 非对象 / 版本不符 → 全默认（后者告警）
"""

from __future__ import annotations

import os
import time
from typing import Any

import pytest

from src.python.core import logger as lg
from src.python.core import system_info as si
from src.python.core import trading_calendar as tc

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


@pytest.fixture
def clean_calendar_state():
    """每个用例前后清空 memo 与失败冷却，避免模块级状态串联。"""
    tc._reset_calendar_memo()
    yield
    tc._reset_calendar_memo()


class TestCalendarMemoBranches:
    """进程内 calendar memo 的过期与写入降级。"""

    def test_expired_memo_treated_as_miss(self, clean_calendar_state, monkeypatch):
        """到期 memo → 未命中（不回落到旧日期集合）。"""
        monkeypatch.setattr(tc, "_CAL_MEMO", (None, time.monotonic() - 1.0, frozenset({"2025-01-02"})))
        assert tc._calendar_memo_lookup() is None

    def test_store_with_unavailable_ttl_clears_memo(self, clean_calendar_state, monkeypatch):
        """缓存剩余 TTL 不可用（None → float 抛 TypeError）→ memo 置空不写入。"""
        monkeypatch.setattr(tc, "_CAL_MEMO", (None, time.monotonic() + 600.0, frozenset({"2025-01-02"})))
        monkeypatch.setattr(tc.cache, "get_ttl", lambda _t: None)
        tc._calendar_memo_store({"2025-01-02"})
        assert tc._CAL_MEMO is None

    def test_store_with_nonpositive_ttl_clears_memo(self, clean_calendar_state, monkeypatch):
        """TTL 非正 → 不留 memo（避免写入随即过期的条目）。"""
        monkeypatch.setattr(tc.cache, "get_ttl", lambda _t: 0)
        tc._calendar_memo_store({"2025-01-02"})
        assert tc._CAL_MEMO is None


class TestCachedTradingDaysBranches:
    """``cached_trading_days`` 的冷却与缓存异常分支。"""

    def test_failure_cooldown_returns_empty_without_reading_cache(self, clean_calendar_state, monkeypatch):
        """失败冷却生效 → 返回空表且完全不读缓存。"""
        monkeypatch.setattr(tc, "_CAL_FAILURE_UNTIL", time.monotonic() + 100.0)

        def _boom(*_a: Any, **_k: Any) -> None:
            raise AssertionError("冷却期内不得读缓存")

        monkeypatch.setattr(tc.cache, "get", _boom)
        assert tc.cached_trading_days() == []

    def test_cache_read_exception_returns_empty(self, clean_calendar_state, monkeypatch):
        """缓存读异常 → 按「无日历」处理，回落自然日阈值。"""
        monkeypatch.setattr(tc.cache, "get", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("缓存坏了")))
        assert tc.cached_trading_days() == []

    def test_memo_filled_by_concurrent_thread_inside_lock(self, clean_calendar_state, monkeypatch):
        """锁内二次检查命中 memo → 直接复用（模拟并发线程已装载）。"""
        calls = iter([None, {"2025-01-02"}])
        monkeypatch.setattr(tc, "_calendar_memo_lookup", lambda: next(calls))
        assert tc._get_trading_calendar() == {"2025-01-02"}


class TestNaturalFallbackBranches:
    """交易日数与自然日差兜底的非负契约。"""

    def test_negative_natural_span_floored_to_zero(self, monkeypatch):
        """日历不可用且 end 早于 start → 自然日为负，出口钳到 0。"""
        monkeypatch.setattr(tc, "count_trading_days_elapsed", lambda *_a, **_k: None)
        assert tc.elapsed_trading_days_with_natural_fallback("2025-03-10", "2025-03-01") == 0

    def test_positive_natural_span_returned(self, monkeypatch):
        """日历不可用且 end 晚于 start → 返回自然日差。"""
        monkeypatch.setattr(tc, "count_trading_days_elapsed", lambda *_a, **_k: None)
        assert tc.elapsed_trading_days_with_natural_fallback("2025-03-01", "2025-03-11") == 10


class TestSystemInfoFallbacks:
    """系统信息组装的路径/配置/探测兜底。"""

    def test_display_path_cross_drive_keeps_absolute(self, monkeypatch):
        """跨盘符无法算相对路径（relpath 抛 ValueError）→ 原样返回绝对路径。"""
        monkeypatch.setattr(si.os.path, "relpath", lambda *_a, **_k: (_ for _ in ()).throw(ValueError("跨盘")))
        assert si.display_path("/data/holdings") == "/data/holdings"

    def test_machine_ip_probe_interrupt_propagates(self, monkeypatch):
        """出口探测被中断（KeyboardInterrupt）→ 向上抛出，不吞成 unknown。"""

        def _interrupt(*_a: Any, **_k: Any) -> Any:
            raise KeyboardInterrupt

        monkeypatch.setattr(si.socket, "socket", _interrupt)
        with pytest.raises(KeyboardInterrupt):
            si.get_machine_ip()

    def test_machine_ip_hostname_interrupt_propagates(self, monkeypatch):
        """主机名解析被中断 → 向上抛出（探测失败与用户中断区别对待）。"""

        class _Probe:
            def __enter__(self) -> _Probe:
                return self

            def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
                return False

            def connect(self, _addr: tuple[str, int]) -> None:
                raise OSError("无默认路由")

        monkeypatch.setattr(si.socket, "socket", lambda *_a, **_k: _Probe())

        def _interrupt() -> str:
            raise KeyboardInterrupt

        monkeypatch.setattr(si.socket, "gethostname", _interrupt)
        with pytest.raises(KeyboardInterrupt):
            si.get_machine_ip()

    def test_build_system_info_non_mapping_config(self, monkeypatch):
        """配置读取返回非映射 → 按空配置摘要展示（不抛属性异常）。"""
        monkeypatch.setattr("src.python.config.get_config", lambda: ["不是字典"])
        info = si.build_system_info()
        assert info["holdings_dir"] == "未设置"
        assert info["holdings_filename"] == "未设置"

    def test_build_system_info_holdings_path_resolution_failure(self, monkeypatch):
        """持仓路径解析异常 → 未就绪展示（不让异常冒成启动失败）。"""
        monkeypatch.setattr("src.python.config.get_config", lambda: {})
        monkeypatch.setattr(
            "src.python.config.resolve_holdings_path",
            lambda _cfg: (_ for _ in ()).throw(RuntimeError("路径解析崩了")),
        )
        info = si.build_system_info()
        assert info["holdings_ready"] is False

    def test_llm_status_read_failure_reports_unconfigured(self, monkeypatch, caplog):
        """LLM 配置读取异常 → configured=False 并留一条告警。"""
        monkeypatch.setattr(
            "src.python.config.get_llm_config",
            lambda: (_ for _ in ()).throw(RuntimeError("配置读取失败")),
        )
        with caplog.at_level("WARNING"):
            status = si.llm_status()
        assert status == {"configured": False}
        assert any("LLM 配置" in rec.message for rec in caplog.records)


class TestLoggerConfigFallbacks:
    """logger.json 读取的四类降级。"""

    def test_missing_file_returns_defaults(self, tmp_path, monkeypatch):
        """配置文件不存在 → 全默认（默认日志路径）。"""
        monkeypatch.setattr(lg, "_LOGGER_CONFIG_PATH", str(tmp_path / "absent.json"))
        assert lg._read_logger_config_file()["path"] == os.path.join("logs", "app.log")

    def test_corrupt_json_returns_defaults(self, tmp_path, monkeypatch):
        """JSONC 解析失败 → 全默认，不阻断日志初始化。"""
        path = tmp_path / "logger.json"
        path.write_text("{不是合法 JSON", encoding="utf-8")
        monkeypatch.setattr(lg, "_LOGGER_CONFIG_PATH", str(path))
        assert lg._read_logger_config_file()["level"] == "INFO"

    def test_non_object_document_returns_defaults(self, tmp_path, monkeypatch):
        """顶层不是对象 → 全默认。"""
        path = tmp_path / "logger.json"
        path.write_text("[1, 2]", encoding="utf-8")
        monkeypatch.setattr(lg, "_LOGGER_CONFIG_PATH", str(path))
        assert lg._read_logger_config_file()["backup_count"] == lg._DEFAULT_BACKUP_COUNT

    def test_version_mismatch_warns_and_returns_defaults(self, tmp_path, monkeypatch):
        """version 不受支持 → 告警后全默认（面板侧据此提示重新生成）。"""
        path = tmp_path / "logger.json"
        path.write_text('{"version": 2, "file": {"level": "ERROR"}}', encoding="utf-8")
        monkeypatch.setattr(lg, "_LOGGER_CONFIG_PATH", str(path))
        with pytest.warns(RuntimeWarning, match="version"):
            config = lg._read_logger_config_file()
        assert config["level"] == "INFO"
