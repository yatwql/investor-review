# -*- coding: utf-8 -*-
"""自检（doctor）逐项降级分支：异常 → 失败项、缺失/落后两态、账本与适配器概览。

自检的契约是「任何一项出错都只变成一条失败 item，不抛出、不中断其余检查」，以及
信息性项的三种规模态。本文件按检查函数逐条注入异常/空值，锁定 `available` 与
`message` 文案，避免降级分支被静默改写成抛出。

全部走注入替身，零网络、零真实写盘。
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.python.core import doctor

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _by_label(items: list[dict], label: str) -> dict:
    return next(item for item in items if item["label"] == label)


class TestEnvAndConfig:
    def test_project_root_missing_marker(self):
        with patch.object(doctor.os.path, "isfile", return_value=False):
            item = doctor._check_project_root()
        assert item["ok"] is False
        assert "未找到 pyproject.toml" in item["message"]

    def test_config_missing_key_paths(self):
        with (
            patch("src.python.config.init_config"),
            patch("src.python.config.get_config", return_value={"holdings_dir": "", "output_dir": ""}),
            patch.object(doctor, "_check_llm_credentials", return_value=[]),
            patch.object(doctor, "_check_config_freshness", return_value=[]),
        ):
            items = doctor._check_config()
        key_item = _by_label(items, "关键路径字段")
        assert key_item["ok"] is False
        assert key_item["message"] == "缺少: holdings_dir、output_dir"

    def test_freshness_parse_error_names_file(self):
        stale = [{"path": "/data/config/config.json", "parse_error": True}]
        with patch("src.python.config.check_config_freshness", return_value=stale):
            items = doctor._check_config_freshness()
        assert items[0]["ok"] is False
        assert "config.json" in items[0]["message"]
        assert "无法解析" in items[0]["message"]

    def test_freshness_missing_keys_and_missing_comments(self):
        stale = [
            {"path": "/data/config/config.json", "missing_keys": ["a", "b", "c", "d", "e"], "missing_comments": []}
        ]
        with patch("src.python.config.check_config_freshness", return_value=stale):
            items = doctor._check_config_freshness()
        assert items[0]["ok"] is False
        assert "缺 5 个新键" in items[0]["message"]
        assert "a、b、c、d 等" in items[0]["message"]

        only_comments = [{"path": "/data/config/llm_settings.json", "missing_keys": [], "missing_comments": ["x"]}]
        with patch("src.python.config.check_config_freshness", return_value=only_comments):
            items = doctor._check_config_freshness()
        assert items[0]["ok"] is True
        assert "注释落后于当前版本" in items[0]["message"]


class TestLlmCredentials:
    def test_read_failure(self):
        with patch("src.python.config.get_llm_config", side_effect=RuntimeError("json 坏了")):
            items = doctor._check_llm_credentials()
        assert items[0]["ok"] is False
        assert "读取失败: RuntimeError: json 坏了" == items[0]["message"]

    def test_empty_config(self):
        with patch("src.python.config.get_llm_config", return_value={}):
            items = doctor._check_llm_credentials()
        assert items[0]["ok"] is False
        assert "未配置（LLM 相关模块将跳过）" == items[0]["message"]

    def test_provider_chain_mode(self):
        cfg = {"_strategy": "round_robin", "_provider_list": [{"name": "主链"}, {"name": "备用链"}]}
        with patch("src.python.config.get_llm_config", return_value=cfg):
            items = doctor._check_llm_credentials()
        assert items[0]["ok"] is True
        assert items[0]["message"] == "多链模式（策略 round_robin）：主链、备用链"

    def test_no_provider_list(self):
        with patch("src.python.config.get_llm_config", return_value={"api_key": ""}):
            items = doctor._check_llm_credentials()
        assert items[0]["ok"] is False
        assert "未配置 provider 链" in items[0]["message"]


class TestProbeTargets:
    def test_config_failure_falls_back_to_default_output_dir(self):
        with patch("src.python.config.get_config", side_effect=RuntimeError("配置损坏")):
            targets = doctor._probe_targets()
        assert targets[0][0] == "输出目录"
        assert targets[0][1].endswith(os.path.join("doctor_probe0", "reports"))
        assert [label for label, _ in targets[1:]] == ["缓存目录", "日志目录"]


class TestDirectories:
    def test_config_failure_returns_empty(self):
        with patch("src.python.config.get_config", side_effect=RuntimeError("配置损坏")):
            assert doctor._check_directories() == []

    def test_holdings_dir_unconfigured(self, tmp_path):
        with (
            patch("src.python.config.get_config", return_value={"holdings_dir": ""}),
            patch.object(doctor, "_probe_targets", return_value=[]),
        ):
            items = doctor._check_directories()
        assert items[0]["ok"] is False
        assert items[0]["message"] == "未配置 holdings_dir"

    def test_holdings_dir_unreadable(self, tmp_path):
        holdings = tmp_path / "holdings"
        holdings.mkdir()
        with (
            patch("src.python.config.get_config", return_value={"holdings_dir": str(holdings)}),
            patch.object(doctor, "_probe_targets", return_value=[]),
            patch.object(doctor.os, "listdir", side_effect=PermissionError(13, "拒绝访问")),
        ):
            items = doctor._check_directories()
        assert items[0]["ok"] is False
        assert items[0]["message"].startswith("读取失败: ")


class TestInfoChecksDegrade:
    def test_eval_status_failure(self):
        with patch("src.python.core.eval_status.format_eval_hint", side_effect=RuntimeError("状态文件坏了")):
            items = doctor._check_eval_status()
        assert items[0]["ok"] is False
        assert items[0]["message"] == "读取失败: RuntimeError: 状态文件坏了"

    def test_report_qa_usage_failure(self):
        with patch("src.python.qa.telemetry.summarize_qa_usage", side_effect=RuntimeError("账本损坏")):
            items = doctor._check_report_qa_usage()
        assert items[0]["ok"] is False
        assert items[0]["message"] == "读取失败: RuntimeError: 账本损坏"

    def test_experiment_verdicts_failure(self):
        with patch("src.python.core.experiment_verdicts.collect_verdicts", side_effect=RuntimeError("裁决不可用")):
            items = doctor._check_experiment_verdicts()
        assert items[0]["ok"] is False
        assert "裁决不可用" in items[0]["message"]


class TestReviewLedgerOverview:
    def _fold(self, **overrides) -> dict:
        fold = {
            "pending_count": 2,
            "settled_count": 5,
            "direction_accuracy": 0.6,
            "sample_sufficient": True,
            "by_horizon": {},
            "inaction": {},
        }
        fold.update(overrides)
        return fold

    def test_multi_horizon_and_signal_window(self):
        from src.python.core.decision_ledger import MIN_SETTLE_BARS

        fold = self._fold(by_horizon={MIN_SETTLE_BARS: {"settled": 5}, 10: {"settled": 3}, 20: {"settled": 0}})
        signals = {"live_count": 7, "demo_count": 3, "first_date": "2026-10-01", "last_date": "2026-11-20"}
        with (
            patch("src.python.core.decision_ledger.fold_ledger", return_value=fold),
            patch("src.python.core.signal_ledger.fold_signals", return_value=signals),
            patch("src.python.core.experiment_stats.load_experiment_usage", return_value={}),
        ):
            items = doctor._check_review_ledger_overview()
        ledger = _by_label(items, "决策复盘账本")
        assert "10 日视界已结 3 条" in ledger["message"]
        signal = _by_label(items, "确定性信号账本")
        assert signal["message"] == "累计 10 条（实时 7 / 非实时 3）— 统计窗口 2026-10-01 ~ 2026-11-20"
        assert _by_label(items, "实验功能使用统计")["message"] == "暂无统计（尚未有带实验功能生成报告的记录）"

    def test_signal_ledger_failure_and_usage_failure(self):
        with (
            patch("src.python.core.decision_ledger.fold_ledger", return_value=self._fold()),
            patch("src.python.core.signal_ledger.fold_signals", side_effect=RuntimeError("信号账本损坏")),
            patch("src.python.core.experiment_stats.load_experiment_usage", side_effect=RuntimeError("统计损坏")),
        ):
            items = doctor._check_review_ledger_overview()
        assert _by_label(items, "确定性信号账本")["message"] == "读取失败: RuntimeError: 信号账本损坏"
        assert _by_label(items, "实验功能使用统计")["message"] == "读取失败: RuntimeError: 统计损坏"


class TestSourceAdapters:
    def test_survey_exception(self):
        doctor.register_adapter_survey(lambda: (_ for _ in ()).throw(RuntimeError("巡检崩了")))
        try:
            items = doctor._check_source_adapters()
        finally:
            doctor.reset_adapter_survey()
        assert items[0]["ok"] is False
        assert items[0]["message"] == "执行失败: RuntimeError: 巡检崩了"

    def test_no_adapter_registered(self):
        doctor.register_adapter_survey(lambda: [])
        try:
            items = doctor._check_source_adapters()
        finally:
            doctor.reset_adapter_survey()
        assert items[0]["ok"] is False
        assert items[0]["message"] == "未登记任何适配器"

    def test_survey_with_failed_adapters(self):
        reports = [
            {"domain": "行情", "display_name": "行情A", "ok": False, "message": "缺 defaults"},
            {"domain": "新闻", "display_name": "新闻B", "ok": True, "message": ""},
        ]
        doctor.register_adapter_survey(lambda: reports)
        try:
            items = doctor._check_source_adapters()
        finally:
            doctor.reset_adapter_survey()
        assert items[0]["ok"] is False
        assert "行情A：缺 defaults" in items[0]["message"]
        assert "1 个未通过自检" in items[0]["message"]
