"""新闻去重锚点存储层的容错面（`providers/news_dedup_anchor_store`）。

锚点文件是**可重建的校准语料**，因此这一层的契约统一是「宁可少几行，也不让整份历史
不可读、不让采集失败拖累去重主流程」：分片读失败跳过、追加失败返回 False、压缩产物
自检不通过即拒绝。本文件锁这些降级路径的具体返回值。
"""

from __future__ import annotations

import gzip
import json

import pytest

from src.python.providers import news_dedup_anchor_store as store

pytestmark = [pytest.mark.unit, pytest.mark.unit_news]


def _write_shard(path, records):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


class TestShardListing:
    def test_unreadable_directory_returns_no_shards(self, tmp_path):
        """目录不存在/不可读 → 空列表（采集与压缩都按「无分片」处理）。"""
        assert store.anchor_shard_paths(str(tmp_path / "absent" / "dedup_anchors.jsonl")) == []

    def test_only_monthly_shards_are_listed(self, tmp_path):
        """未分片的早期单文件不参与读取/压缩/清理。"""
        _write_shard(tmp_path / "dedup_anchors-202401.jsonl.gz", [{"ts": "2024-01-05"}])
        (tmp_path / "dedup_anchors.jsonl").write_text('{"ts": "2023-01-05"}\n', encoding="utf-8")

        paths = store.anchor_shard_paths(str(tmp_path / "dedup_anchors.jsonl"))

        assert [p.rsplit("/", 1)[-1] for p in paths] == ["dedup_anchors-202401.jsonl.gz"]

    def test_vanished_shard_contributes_zero_bytes(self, tmp_path, monkeypatch):
        """统计体积时文件被并发删除 → 该分片计 0，不影响其余分片。"""
        _write_shard(tmp_path / "dedup_anchors-202401.jsonl.gz", [{"ts": "2024-01-05"}])

        def _raise(*args, **kwargs):
            raise OSError("vanished")

        monkeypatch.setattr(store.os.path, "getsize", _raise)

        assert store.anchor_total_bytes(str(tmp_path / "dedup_anchors.jsonl")) == 0


class TestReadLines:
    def test_corrupt_shard_is_skipped_others_read(self, tmp_path):
        """单个分片损坏（截断 gzip）只丢该分片，其它月份仍可读。"""
        _write_shard(tmp_path / "dedup_anchors-202401.jsonl.gz", [{"ts": "2024-01-05"}, {"ts": "2024-01-06"}])
        (tmp_path / "dedup_anchors-202402.jsonl.gz").write_bytes(b"\x1f\x8b\x08 truncated")

        lines = store.read_anchor_lines(str(tmp_path / "dedup_anchors.jsonl"))

        assert len(lines) == 2, "损坏分片不得连带丢弃已读出的行"

    def test_plain_text_shard_fallback(self, tmp_path, monkeypatch):
        """非 gz 路径走明文读取分支（历史产物/人工导出文件）。"""
        plain = tmp_path / "dedup_anchors-202312.jsonl"
        plain.write_text('{"ts": "2023-12-01"}\n', encoding="utf-8")
        monkeypatch.setattr(store, "anchor_shard_paths", lambda base=None: [str(plain)])

        assert store.read_anchor_lines() == ['{"ts": "2023-12-01"}\n']

    def test_plain_text_shard_read_error_is_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(store, "anchor_shard_paths", lambda base=None: [str(tmp_path / "gone.jsonl")])

        assert store.read_anchor_lines() == []


class TestAppend:
    def test_empty_batch_is_success_noop(self, tmp_path, monkeypatch):
        """空批次视为成功且不落盘（调用方据此保持「已登记 key 不撤回」）。"""
        monkeypatch.setattr(store, "_ANCHOR_PATH", str(tmp_path / "dedup_anchors.jsonl"))

        assert store._append_anchor_lines([]) is True
        assert not list(tmp_path.glob("dedup_anchors-*.jsonl.gz"))

    def test_append_failure_returns_false(self, tmp_path, monkeypatch):
        """写盘失败（磁盘满）→ False，由调用方撤回本次登记的 key。"""
        monkeypatch.setattr(store, "_ANCHOR_PATH", str(tmp_path / "dedup_anchors.jsonl"))

        def _raise(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(store.gzip, "open", _raise)

        assert store._append_anchor_lines([json.dumps({"ts": "2024-01-05"})]) is False

    def test_append_success_is_readable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(store, "_ANCHOR_PATH", str(tmp_path / "dedup_anchors.jsonl"))
        record = {"ts": "2024-01-05 10:00:00", "title_a": "a", "title_b": "b"}

        assert store._append_anchor_lines([json.dumps(record, ensure_ascii=False)]) is True

        lines = store.read_anchor_lines()
        assert [json.loads(line) for line in lines] == [record]


class TestCompactVerified:
    def test_empty_file_rejected(self, tmp_path):
        target = tmp_path / "dedup_anchors-202401.jsonl.gz"
        target.write_bytes(b"")

        assert store._compact_verified(str(target)) is False

    def test_plain_jsonl_accepted(self, tmp_path):
        target = tmp_path / "dedup_anchors-202401.jsonl"
        target.write_text('{"ts": "2024-01-05"}\n', encoding="utf-8")

        assert store._compact_verified(str(target)) is True

    def test_blank_first_line_rejected(self, tmp_path):
        target = tmp_path / "dedup_anchors-202401.jsonl"
        target.write_text('\n{"ts": "2024-01-05"}\n', encoding="utf-8")

        assert store._compact_verified(str(target)) is False

    @pytest.mark.parametrize("payload", [b"not-json\n", b"\x1f\x8b\x08 truncated"])
    def test_unparsable_payload_rejected(self, tmp_path, payload):
        """首行不可解析 / 截断 gzip 都要拒绝，否则删备份后只剩半截文件。"""
        suffix = ".jsonl.gz" if payload.startswith(b"\x1f\x8b") else ".jsonl"
        target = tmp_path / f"dedup_anchors-202401{suffix}"
        target.write_bytes(payload)

        assert store._compact_verified(str(target)) is False


class TestParseTs:
    @pytest.mark.parametrize("raw", ["", None, "not-a-timestamp", "2024/01/05"])
    def test_invalid_values_return_none(self, raw):
        """时间字段缺失/非法一律 None（分片名回退到 written_at 或当前月）。"""
        assert store._anchor_parse_ts(raw) is None

    @pytest.mark.parametrize("raw", ["2024-01-05", "2024-01-05 10:00", "2024-01-05 10:00:00"])
    def test_supported_formats_parse(self, raw):
        parsed = store._anchor_parse_ts(raw)

        assert parsed is not None
        assert (parsed.year, parsed.month, parsed.day) == (2024, 1, 5)
