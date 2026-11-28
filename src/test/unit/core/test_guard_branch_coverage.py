"""核心层小缺口分支补齐：守卫/降级/掩码/回退路径。

集中覆盖「每文件仅缺数行」的守卫分支：

  - 阶段超时状态复位、ANSI 着色缺 colorama 的降级
  - 原子拷贝的目录创建失败与临时文件清理失败
  - 熔断状态委派查询、市值分档前缀识别、持仓分档归类
  - 通知渠道：收件人为空即拒绝、URL 掩码、分发异常吞掉返回 False
  - 项目根查找的三条回退（.git 标记 / 走到顶 / 深度回退）
  - 凭据路径与读取的配置层异常回退、非对象 JSON 视为空
  - 实验统计的形状异常与落盘失败降级
  - 日志节流键表满后清空、装饰行判定、tail 限流下限
  - 章节序号未命中返回 0、区块契约按键取值、表驱动退避为 0
"""

from __future__ import annotations

import json
import logging
import os
import sys

import pytest

from src.python.core import (
    ansi_colors,
    atomic_write,
    circuit_breaker,
    code_symbols,
    code_utils,
    completion_notify,
    constants,
    datasource_credential,
    experiment_stats,
    holding_status,
    log_dedupe,
    log_reader,
    report_section_registry,
    retry,
    section_block_registry,
)
from src.python.core._phase_timeout import _phase_timeout

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


# ── 阶段超时 / ANI 着色 ────────────────────────────────


def test_phase_timeout_reset_clears_state():
    _phase_timeout.expired = True
    _phase_timeout.name = "generate"
    _phase_timeout.reset()
    assert _phase_timeout.timer is None
    assert _phase_timeout.expired is False
    assert _phase_timeout.name == ""


def test_ansi_colors_degrades_without_colorama(monkeypatch):
    """缺 colorama 时导入不失败：转义码表仍是完整的契约键集与具体码值。"""
    import importlib

    monkeypatch.setitem(sys.modules, "colorama", None)
    try:
        reloaded = importlib.reload(ansi_colors)
        assert set(reloaded.RAW_CODES) == {
            "GREEN",
            "RED",
            "YELLOW",
            "CYAN",
            "DIM",
            "BLUE",
            "ORANGE",
            "MAGENTA",
            "BOLD",
            "RESET",
        }
        assert reloaded.RAW_CODES["GREEN"] == "\033[92m"
        assert reloaded.RAW_CODES["RESET"] == "\033[0m"
        assert all(value.startswith("\033[") for value in reloaded.RAW_CODES.values())
    finally:
        monkeypatch.undo()
        importlib.reload(ansi_colors)


# ── 原子拷贝失败路径 ──────────────────────────────────


class TestCopyFileAtomicFailures:
    def test_directory_creation_failure_is_wrapped(self, tmp_path, monkeypatch):
        src = tmp_path / "a.txt"
        src.write_text("x", encoding="utf-8")

        def _boom(*args, **kwargs):
            raise OSError("mkfail")

        monkeypatch.setattr(atomic_write.os, "makedirs", _boom)
        with pytest.raises(OSError) as exc:
            atomic_write.copy_file_atomic(str(src), str(tmp_path / "sub" / "b.txt"))
        assert "无法创建目标目录" in str(exc.value)

    def test_copy_failure_swallows_cleanup_error_and_reraises(self, tmp_path, monkeypatch):
        src = tmp_path / "a.txt"
        src.write_text("x", encoding="utf-8")

        def _boom_copy(*args, **kwargs):
            raise OSError("copyfail")

        def _boom_remove(*args, **kwargs):
            raise OSError("removefail")

        monkeypatch.setattr(atomic_write.shutil, "copy2", _boom_copy)
        monkeypatch.setattr(atomic_write.os, "remove", _boom_remove)
        with pytest.raises(OSError) as exc:
            atomic_write.copy_file_atomic(str(src), str(tmp_path / "b.txt"))
        assert "copyfail" in str(exc.value)


# ── 熔断状态委派 / 代码分档 ───────────────────────────


def test_circuit_breaker_status_returns_mapping(monkeypatch):
    provider_sentinel = {"provider_x": {"available": True, "tier": "A", "consecutive_failures": 0}}
    llm_sentinel = {"llm.example.com": {"circuit_broken": False, "consecutive_failures": 0}}
    monkeypatch.setattr(circuit_breaker.gateway, "_get_provider_status", lambda: provider_sentinel)
    monkeypatch.setattr(circuit_breaker.gateway, "_get_llm_status", lambda: llm_sentinel)

    # 契约是「委派给 gateway」，故断言拿到的就是 gateway 的报告而非新造的映射
    assert circuit_breaker.get_provider_breaker_status() is provider_sentinel
    assert circuit_breaker.get_llm_endpoint_status() is llm_sentinel


def test_market_cap_prefix_buckets():
    """4/8 开头（新三板、北交所）→ 小盘；001 开头 → 中大盘；其余 → 其他。"""
    assert code_symbols.estimate_market_cap_by_prefix("430047") == "小盘"
    assert code_symbols.estimate_market_cap_by_prefix("001979") == "中大盘"
    assert code_symbols.estimate_market_cap_by_prefix("999999") == "其他"


def test_mixed_otc_fund_tier():
    """00 开头且名称含基金特征（非 ETF/非债）→（基金，混合）。"""
    assert code_utils.classify_holding_tier("华夏成长混合", "000001", "A") == ("基金", "混合")


# ── 完成通知 ──────────────────────────────────────────


class TestCompletionNotifyGuards:
    def test_email_without_recipients_rejected_before_send(self):
        with pytest.raises(ValueError) as exc:
            completion_notify._send_email({"to": " , ;"}, "s", "b", 1)
        assert "notify.email.to 为空" in str(exc.value)

    def test_mask_url_without_scheme_or_host(self):
        assert completion_notify._mask_url("dummy-webhook-token") == "***"
        assert completion_notify._mask_url("https://example.com/path?k=v") == "https://example.com/***"

    def test_dispatch_exception_is_swallowed(self, monkeypatch):
        """通知渠道抛异常不得影响退出码：吞掉并返回 False。"""
        monkeypatch.setattr(completion_notify, "should_notify", lambda cfg, ok: True)
        monkeypatch.setattr(completion_notify, "_configured_channels", lambda cfg: {"desktop"})
        monkeypatch.setattr(
            completion_notify,
            "_attempt",
            lambda channel, fn, secret="": (_ for _ in ()).throw(RuntimeError("boom")),
        )
        assert completion_notify.dispatch_completion_notification({"ok": True}, {}) is False


# ── 项目根查找回退 ────────────────────────────────────


class TestProjectRootFallbacks:
    def test_git_marker_without_pyproject(self, monkeypatch):
        monkeypatch.setattr(constants.os.path, "isfile", lambda path: False)
        monkeypatch.setattr(constants.os.path, "isdir", lambda path: True)
        assert constants._find_project_root() == os.path.dirname(os.path.abspath(constants.__file__))

    def test_no_marker_anywhere_falls_back_to_depth(self, monkeypatch):
        monkeypatch.setattr(constants.os.path, "isfile", lambda path: False)
        monkeypatch.setattr(constants.os.path, "isdir", lambda path: False)
        expected = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(constants.__file__))))
        assert constants._find_project_root() == expected


# ── 数据源凭据 ────────────────────────────────────────


class TestDatasourceCredentialGuards:
    def test_config_layer_failure_falls_back_to_declared_path(self, monkeypatch):
        import src.python.config as config_pkg

        monkeypatch.setattr(
            config_pkg,
            "get_config",
            lambda: (_ for _ in ()).throw(RuntimeError("config unavailable")),
        )
        spec = datasource_credential.CredentialSpec(
            source_id="tushare",
            display_name="Tushare",
            env_var="TUSHARE_TOKEN",
            key_file="data/config/tushare_key.txt",
            key_file_setting="tushare_key_file",
        )
        path = datasource_credential._key_file_path(spec)
        assert path.endswith("tushare_key.txt")

    def test_non_object_json_reads_as_empty(self, tmp_path):
        path = tmp_path / "key.json"
        path.write_text(json.dumps([1, 2]), encoding="utf-8")
        assert datasource_credential._read_key_file(str(path), "token") == ""


# ── 实验统计 ──────────────────────────────────────────


class TestExperimentStatsGuards:
    def test_non_object_stats_file_is_empty(self, tmp_path):
        path = tmp_path / "stats.json"
        path.write_text(json.dumps(["bad"]), encoding="utf-8")
        assert experiment_stats.load_experiment_usage(str(path)) == {}

    def test_write_failure_is_logged_not_raised(self, tmp_path, monkeypatch, caplog):
        """落盘原语返回 False → 只记告警（不影响报告产出）。"""
        from src.python.core import experiment_stats as es

        monkeypatch.setattr(es, "write_json_atomic", lambda *a, **kw: False)
        with caplog.at_level(logging.WARNING):
            experiment_stats.record_experiment_usage(["flag_a"], str(tmp_path / "stats.json"))
        assert any("使用统计落盘失败" in rec.message for rec in caplog.records)


# ── 名称匹配 / 日志工具 ───────────────────────────────


def test_names_match_long_market_name_contains_holding_name():
    """反向包含（市场名更长且含持仓名，长度≥2）也算同一品种。"""
    assert holding_status.names_match("茅台", "贵州茅台") is True
    assert holding_status.names_match("茅台", "五粮液") is False


class TestLogUtilities:
    def test_throttle_key_table_cleared_when_full(self):
        log_dedupe._last_logged.clear()
        for i in range(log_dedupe._MAX_KEYS):
            log_dedupe.log_throttled(logging.getLogger("t"), f"k{i}", "m", window_secs=0.0)
        log_dedupe.log_throttled(logging.getLogger("t"), "fresh", "m", window_secs=0.0)
        assert set(log_dedupe._last_logged) == {"fresh"}

    def test_blank_message_counts_as_decorative(self):
        assert log_reader._is_decorative("   ") is True
        assert log_reader._is_decorative("内容") is False

    def test_tail_log_non_positive_limit_reads_one_line(self, tmp_path):
        path = tmp_path / "app.log"
        path.write_text("first\nsecond\n", encoding="utf-8")
        assert log_reader.tail_log(str(path), limit=0).strip() == "second"


# ── 章节注册与退避表 ──────────────────────────────────


def test_section_number_unregistered_key_returns_zero():
    assert report_section_registry.get_report_section_number("no_such_section") == 0


def test_section_block_spec_lookup_by_key():
    key = next(iter(section_block_registry.SECTION_BLOCK_SPECS))
    assert section_block_registry.get_section_block_spec(key) is section_block_registry.SECTION_BLOCK_SPECS[key]


def test_table_backoff_with_zero_delay_returns_zero():
    """表驱动退避的首档为 0 → 立即重试（不加抖动）。"""
    policy = retry.RetryPolicy(strategy=retry.STRATEGY_TABLE, delays=(0.0, 1.0))
    assert policy.delay_for(1) == 0.0
