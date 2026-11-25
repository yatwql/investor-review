# -*- coding: utf-8 -*-
"""锚点策略层故障注入：保留期/体量维护/压缩的异常与放弃路径。

锁定三类「不该让报告变红」的降级行为：

- 环境变量非法值回落默认保留期；无法解析的时间戳**保留**（不静默丢历史）；
- 压缩期间的文件系统故障（stat 失败、读后被并发删、写盘失败、校验失败）只标
  ``aborted``，不抛异常、不删原分片；
- 维护路径的三种取舍：体积为 0 / 超阈值但维护开关关闭（只告警一次）/
  维护开关开启（就地压缩），以及压缩本身失败只告警。

分片在 ``tmp_path`` 内自建，不触碰真实 ``data/calibration/``。
"""

from __future__ import annotations

import gzip
import json
import os
from datetime import datetime, timedelta

import pytest

from src.python.providers import news_dedup_anchor_policy as policy

pytestmark = [pytest.mark.unit, pytest.mark.unit_news]


def _use_tmp_anchor_dir(tmp_path, monkeypatch) -> str:
    """把锚点基线路径指向 tmp 目录，返回该目录。"""
    from src.python.providers import news_dedup_anchor_store as store

    base = str(tmp_path / "anchors" / "dedup_anchors.jsonl")
    monkeypatch.setattr(store, "_ANCHOR_PATH", base)
    os.makedirs(os.path.dirname(base), exist_ok=True)
    return os.path.dirname(base)


def _write_shard(directory: str, month: str, rows: list, *, raw_lines: list[str] | None = None) -> str:
    path = os.path.join(directory, f"dedup_anchors-{month}.jsonl.gz")
    with gzip.open(path, "wt", encoding="utf-8") as f:
        if raw_lines is not None:
            f.writelines(raw_lines)
        else:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    return path


def _record(title: str, *, ts: str | None = None, version: str | None = None) -> dict:
    """一条锚点记录（默认带当前规则指纹，``version=""`` 即无指纹旧行）。"""
    from src.python.providers.news_dedup_rules import _ANCHOR_RULES_VERSION, ANCHOR_RULES_FIELD

    ts = ts or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record = {
        "ts": ts,
        "title_a": title,
        "title_b": title + "（改）",
        "source_a": "源A",
        "source_b": "源B",
        "ratio": 0.9,
        "bigram_overlap": 9,
        "merged": True,
        "rule": "safe_zone",
        "written_at": ts,
    }
    record[ANCHOR_RULES_FIELD] = _ANCHOR_RULES_VERSION if version is None else version
    return record


class TestRetentionEnv:
    def test_invalid_retention_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("INVEST_DEDUP_ANCHOR_RETENTION_DAYS", "三十天")
        assert policy._anchor_retention_days() == policy._ANCHOR_RETENTION_DAYS

    def test_empty_retention_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("INVEST_DEDUP_ANCHOR_RETENTION_DAYS", "  ")
        assert policy._anchor_retention_days() == policy._ANCHOR_RETENTION_DAYS

    def test_unparsable_ts_is_kept(self, monkeypatch):
        cutoff = datetime.now() - timedelta(days=1)
        recent = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        # 无法解析 / 缺失的时间戳一律保留（宁可留无用行，也不静默丢历史）
        assert policy._anchor_ts_on_or_after("格式未知", cutoff) is True
        assert policy._anchor_ts_on_or_after("", cutoff) is True
        assert policy._anchor_ts_on_or_after(recent, cutoff) is True
        assert policy._anchor_ts_on_or_after(recent, datetime.now() + timedelta(days=1)) is False


class TestSamplingAndFlush:
    def test_sampling_disabled_returns_false(self, monkeypatch):
        monkeypatch.setattr(policy, "_SAME_SRC_ANCHOR_SAMPLE", 0)
        assert policy._anchor_sampled({"title_a": "a", "title_b": "b"}) is False

    def test_flush_collapses_duplicate_keys_in_batch(self, monkeypatch):
        """同批次同一标题对只写一行（跨轮重复由校准工具去重）。"""
        record = _record("同一条标题")
        monkeypatch.setattr(policy, "_ANCHOR_RECORDS", [record, dict(record)])
        written = []
        monkeypatch.setattr(policy, "_append_anchor_lines", lambda lines: written.append(lines) or True)
        monkeypatch.setattr(policy, "_maybe_maintain_anchor_file", lambda: written.append("maintained"))
        policy._flush_anchors()
        assert len(written[0]) == 1
        assert json.loads(written[0][0])["title_a"] == "同一条标题"
        assert written[1] == "maintained"
        assert policy._ANCHOR_RECORDS == []


class TestMaybeMaintain:
    def test_zero_bytes_returns_without_action(self, monkeypatch):
        called = []
        monkeypatch.setattr(policy, "anchor_total_bytes", lambda *a, **kw: 0)
        monkeypatch.setattr(policy, "_compact_anchor_file", lambda size: called.append(size))
        policy._maybe_maintain_anchor_file()
        assert called == []

    def test_maintenance_enabled_compacts(self, monkeypatch):
        called = []
        monkeypatch.setattr(policy, "anchor_total_bytes", lambda *a, **kw: 40 * 1024 * 1024)
        monkeypatch.setattr(policy, "_compact_anchor_file", lambda size: called.append(size))
        monkeypatch.setenv("INVEST_DEDUP_MAINTENANCE", "1")
        policy._maybe_maintain_anchor_file()
        assert called == [40 * 1024 * 1024]

    def test_warning_only_once(self, monkeypatch, caplog):
        monkeypatch.setattr(policy, "anchor_total_bytes", lambda *a, **kw: 40 * 1024 * 1024)
        monkeypatch.delenv("INVEST_DEDUP_MAINTENANCE", raising=False)
        monkeypatch.setattr(policy, "_ANCHOR_SIZE_WARNED", False)
        with caplog.at_level("INFO"):
            policy._maybe_maintain_anchor_file()
            first = [r for r in caplog.records if "锚点文件" in r.message]
            policy._maybe_maintain_anchor_file()
            second = [r for r in caplog.records if "锚点文件" in r.message]
        assert len(first) == 1
        assert len(second) == 1  # 第二次进「已告警」早退，不再刷日志


class TestCompactAnchorFileFaults:
    def test_stat_failure_leaves_stats_empty(self, monkeypatch, tmp_path):
        directory = _use_tmp_anchor_dir(tmp_path, monkeypatch)
        _write_shard(directory, "202610", [_record("标题")])

        def boom(_path):
            raise OSError("stat 不可用")

        monkeypatch.setattr(policy.os, "stat", boom)
        stats = policy.compact_anchor_file()
        assert stats["before_lines"] == 0
        assert stats["written"] is False
        assert stats["aborted"] is None

    def test_shard_vanished_after_read_aborts(self, monkeypatch, tmp_path):
        directory = _use_tmp_anchor_dir(tmp_path, monkeypatch)
        _write_shard(directory, "202610", [_record("标题")])
        real_stat = os.stat
        calls = {"n": 0}

        def flaky_stat(path):
            calls["n"] += 1
            if calls["n"] == 1:
                return real_stat(path)
            raise OSError("并发删除")

        monkeypatch.setattr(policy.os, "stat", flaky_stat)
        stats = policy.compact_anchor_file()
        assert stats["aborted"] == "vanished-after-read"
        assert stats["written"] is False

    def test_blank_bad_json_and_unattributed_rows_are_dropped(self, monkeypatch, tmp_path):
        directory = _use_tmp_anchor_dir(tmp_path, monkeypatch)
        good = _record("保留的标题")
        legacy = _record("无指纹旧行")
        legacy = {k: v for k, v in legacy.items() if k != "anchor_rules_version"}
        legacy["rule"] = "legacy_rule"
        lines = [
            "\n",
            "{不是 JSON}\n",
            json.dumps(good, ensure_ascii=False) + "\n",
            json.dumps(legacy, ensure_ascii=False) + "\n",
        ]
        _write_shard(directory, "202610", [], raw_lines=lines)
        stats = policy.compact_anchor_file()
        # 空行与坏行不计入 before_lines；无指纹行计入 unattributed 并触发重写
        assert stats["before_lines"] == 3  # 坏 JSON 行计入读取行数，空行不计
        assert stats["unattributed"] == 1
        assert stats["written"] is True
        assert stats["after_lines"] == 1

    def test_verify_failed_removes_tmp_and_keeps_original(self, monkeypatch, tmp_path):
        directory = _use_tmp_anchor_dir(tmp_path, monkeypatch)
        legacy = _record("无指纹旧行")
        legacy = {k: v for k, v in legacy.items() if k != "anchor_rules_version"}
        shard = _write_shard(directory, "202610", [_record("保留的标题"), legacy])
        monkeypatch.setattr(policy, "_compact_verified", lambda path: False)
        stats = policy.compact_anchor_file()
        assert stats["aborted"] == "verify-failed"
        assert stats["written"] is False
        assert os.path.exists(shard)
        assert not os.path.exists(shard + ".compact.tmp")

    def test_write_failure_aborts_without_raising(self, monkeypatch, tmp_path):
        directory = _use_tmp_anchor_dir(tmp_path, monkeypatch)
        _write_shard(directory, "202610", [_record("保留的标题"), _record("保留的标题")])
        monkeypatch.setattr(
            policy, "anchor_shard_paths", lambda base=None: [os.path.join(directory, "dedup_anchors-202610.jsonl.gz")]
        )

        def boom(*_a, **_kw):
            raise OSError("磁盘满")

        # 只打写侧入口（gzip.open 同时被读侧复用，patch 它会连读都进不去）
        monkeypatch.setattr(policy.os, "makedirs", boom)
        stats = policy.compact_anchor_file()
        assert stats["aborted"].startswith("write-failed: ")
        assert "磁盘满" in stats["aborted"]
        assert stats["written"] is False


class TestCompactAnchorFileMaintenance:
    def test_exception_from_compact_degrades_to_false(self, monkeypatch, tmp_path, caplog):
        directory = _use_tmp_anchor_dir(tmp_path, monkeypatch)
        _write_shard(directory, "202610", [_record("标题")])
        monkeypatch.setattr(
            policy, "compact_anchor_file", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("压缩炸了"))
        )
        with caplog.at_level("WARNING"):
            assert policy._compact_anchor_file(policy._ANCHOR_SIZE_WARN_BYTES + 1) is False
        assert any("维护压缩失败" in rec.message for rec in caplog.records)

    def test_aborted_skips_and_logs(self, monkeypatch, caplog):
        monkeypatch.setattr(policy, "anchor_shard_paths", lambda base=None: ["/tmp/x.jsonl.gz"])
        monkeypatch.setattr(
            policy, "compact_anchor_file", lambda *a, **kw: {"aborted": "concurrent-write", "written": False}
        )
        with caplog.at_level("INFO"):
            assert policy._compact_anchor_file(policy._ANCHOR_SIZE_WARN_BYTES + 1) is False
        assert any("本轮跳过（concurrent-write）" in rec.message for rec in caplog.records)

    def test_not_written_returns_false(self, monkeypatch):
        monkeypatch.setattr(policy, "anchor_shard_paths", lambda base=None: ["/tmp/x.jsonl.gz"])
        monkeypatch.setattr(
            policy,
            "compact_anchor_file",
            lambda *a, **kw: {"aborted": None, "written": False, "trimmed_by_branch": {}},
        )
        assert policy._compact_anchor_file(policy._ANCHOR_SIZE_WARN_BYTES + 1) is False
