"""锚点采集语料的测试隔离（conftest `_isolate_sensitive_paths`）。

`data/calibration/dedup_anchors-*.jsonl.gz` 是**阈值校准语料**：采集默认开启，任一用例
触发 `_flush_anchors()` 就会追加进真实分片。此处锁两条：
  - 用例运行期锚点基路径必须已被重定向到 tmp（不在仓库 `data/` 下）；
  - 采集落盘走的是重定向后的路径，不碰真实分片。
"""

from __future__ import annotations

import pathlib
import unittest
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_news]


class TestAnchorPathIsolation(unittest.TestCase):
    def test_anchor_base_path_is_redirected(self):
        from src.python.providers import news_dedup_anchor_store

        repo_data = (pathlib.Path(__file__).resolve().parents[4] / "data").resolve()
        base = pathlib.Path(news_dedup_anchor_store._ANCHOR_PATH).resolve()
        assert repo_data not in base.parents, f"锚点路径未隔离，仍指向仓库 data/：{base}"

    def test_flush_writes_to_isolated_path(self):
        """落盘位置 = 隔离目录下的当月分片（不碰仓库 data/calibration）。"""
        from datetime import datetime

        from src.python.providers import news_dedup_anchor_policy as policy, news_dedup_anchor_store as store

        base = pathlib.Path(store._ANCHOR_PATH)
        shard = base.parent / f"{store._ANCHOR_SHARD_PREFIX}{datetime.now():%Y%m}{store._ANCHOR_SHARD_SUFFIX}"
        assert not shard.exists(), "用例前提：隔离分片初始不存在"

        with (
            patch.object(policy, "_anchor_collection_enabled", lambda: True),
            patch.object(policy, "_SAME_SRC_ANCHOR_SAMPLE", 1),
        ):
            policy._record_anchor(
                {
                    "ts": "2026-01-01 00:00:00",
                    "title_a": "隔离验证标题甲",
                    "title_b": "隔离验证标题乙",
                    "source_a": "sina",
                    "source_b": "sina",
                    "ratio": 0.5,
                    "bigram_overlap": 1,
                    "merged": False,
                    "rule": "cross_merge",
                }
            )
            policy._flush_anchors()

        assert shard.exists(), f"未写入隔离分片：{shard}"
        import gzip

        with gzip.open(shard, "rt", encoding="utf-8") as handle:
            payload = handle.read()
        assert "隔离验证标题甲" in payload
