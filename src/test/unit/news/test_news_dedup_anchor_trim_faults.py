"""锚点压缩的分支配额与备份清扫容错分支。

- 体积裁剪遇到「受配额保护」的行必须原样保留（小分支不被整类裁光）；
- 整月被裁空的分片：``INVEST_DEDUP_KEEP_BACKUP=1`` 下备份失败 / 删除失败都只吞掉，不中断压缩；
- 重写成功后清理 ``.bak`` 时删除失败同样只吞掉（压缩结果已落盘，不因清理失败回滚）。
"""

from __future__ import annotations

import json
import os

import pytest

from src.python.providers import news_dedup, news_dedup_anchor_policy, news_dedup_anchor_store
from src.test._relative_dates import recent_ts as _recent_ts

pytestmark = [pytest.mark.unit, pytest.mark.unit_news]


def _row(branch: str, title: str, ts: str) -> dict:
    from src.python.providers.news_dedup_rules import _ANCHOR_RULES_VERSION

    return {
        "ts": ts,
        "title_a": title,
        "title_b": f"对照-{title}",
        "source_a": "sina",
        "source_b": "eastmoney",
        "ratio": 0.4,
        "bigram_overlap": 2,
        "merged": False,
        "rule": branch,
        "anchor_rules_version": _ANCHOR_RULES_VERSION,
    }


def _write_shard(directory, rows: list[dict], month: str) -> str:
    """把行写入指定月份分片（锚点只认 ``dedup_anchors-YYYYMM.jsonl.gz``）。"""
    import gzip
    import os

    path = os.path.join(directory, f"dedup_anchors-{month}.jsonl.gz")
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    return path


class _ShutilWithFailingCopy:
    """``shutil`` 代理：源路径含指定片段的 ``copy2`` 抛 OSError，其余属性直通真实 shutil。"""

    def __init__(self, src_fragment: str) -> None:
        self._fragment = src_fragment

    def __getattr__(self, name: str):
        import shutil

        return getattr(shutil, name)

    def copy2(self, src, dst):
        if self._fragment in str(src):
            raise OSError("盘满")
        import shutil

        return shutil.copy2(src, dst)


class _OsWithFailingRemove:
    """``os`` 代理：指定后缀的 ``remove`` 抛 OSError，其余属性直通真实 os。"""

    def __init__(self, suffix: str) -> None:
        self._suffix = suffix

    def __getattr__(self, name: str):
        return getattr(os, name)

    def remove(self, path) -> None:
        if str(path).endswith(self._suffix):
            raise OSError("占用")
        os.remove(path)


def _read_shard(path: str) -> list[dict]:
    import gzip

    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_trim_skips_quota_protected_row_and_keeps_it(tmp_path):
    """最旧的行恰是小分支唯一一条（受配额保护）→ 裁剪跳到下一条，该行留存。"""
    rows = [_row("cross_opposite", "唯一小分支", _recent_ts(5))]
    rows += [_row("cross_skip", f"批量{i:03d}", _recent_ts(1)) for i in range(40)]
    path = _write_shard(str(tmp_path), rows, str(rows[0]["ts"])[:7].replace("-", ""))

    stats = news_dedup.compact_anchor_file(str(path), target_bytes=600, branch_min_keep=1)

    assert stats["trimmed"] > 0, "体积上限未触发裁剪（用例前提失效）"
    assert stats["trimmed_by_branch"].get("cross_opposite", 0) == 0
    kept = _read_shard(path)
    assert [r["rule"] for r in kept].count("cross_opposite") == 1
    assert any(r["title_a"] == "唯一小分支" for r in kept), "受配额保护的行不得被裁"


def test_stale_shard_backup_failure_is_swallowed(tmp_path, monkeypatch):
    """``KEEP_BACKUP=1`` 时拷贝过期分片失败 → 只吞掉异常，过期分片仍被删除。"""
    old = _row("cross_skip", "旧样本", "2020-01-05 10:00")
    new = _row("cross_skip", "新样本", _recent_ts(1))
    _write_shard(str(tmp_path), [old], "202001")
    _write_shard(str(tmp_path), [new], str(new["ts"])[:7].replace("-", ""))
    monkeypatch.setenv(news_dedup_anchor_store._ANCHOR_KEEP_BACKUP_ENV, "1")
    monkeypatch.setattr(news_dedup_anchor_policy, "shutil", _ShutilWithFailingCopy("202001"))

    stats = news_dedup.compact_anchor_file(str(tmp_path / "anchors.jsonl"), retention_days=30, target_bytes=10**9)

    assert stats["written"] is True
    assert not (tmp_path / "dedup_anchors-202001.jsonl.gz").exists(), "过期分片须仍被删除"


def test_stale_shard_removal_failure_is_swallowed(tmp_path, monkeypatch):
    """过期分片删除失败（权限/占用）→ 吞掉并继续，压缩结果仍标记已写盘。"""
    old = _row("cross_skip", "旧样本", "2020-01-05 10:00")
    new = _row("cross_skip", "新样本", _recent_ts(1))
    stale = _write_shard(str(tmp_path), [old], "202001")
    _write_shard(str(tmp_path), [new], str(new["ts"])[:7].replace("-", ""))
    monkeypatch.setattr(news_dedup_anchor_policy, "os", _OsWithFailingRemove("202001.jsonl.gz"))

    stats = news_dedup.compact_anchor_file(str(tmp_path / "anchors.jsonl"), retention_days=30, target_bytes=10**9)

    assert stats["written"] is True
    assert os.path.exists(stale), "删除失败时过期分片仍在（异常被吞、压缩结果不回滚）"


def test_backup_cleanup_failure_is_swallowed(tmp_path, monkeypatch):
    """重写分片后清理 ``.bak`` 失败 → 不抛出，统计仍标记已写盘。"""
    rows = [_row("cross_skip", f"样本{i:03d}", _recent_ts(1)) for i in range(3)]
    rows.append(_row("cross_skip", "样本000", _recent_ts(1)))  # 同键重复行 → 触发重写
    path = _write_shard(str(tmp_path), rows, str(rows[0]["ts"])[:7].replace("-", ""))
    monkeypatch.setattr(news_dedup_anchor_policy, "os", _OsWithFailingRemove(".bak"))

    stats = news_dedup.compact_anchor_file(str(path), target_bytes=10**9)

    assert stats["written"] is True
    assert stats["after_lines"] == 3, "重复行仍须被压缩掉（清理备份失败不影响压缩结果）"
