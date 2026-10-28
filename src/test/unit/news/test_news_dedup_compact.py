"""锚点文件压缩（显式维护触发，原子替换 + 校验后清理备份 + 可关闭）。

背景：锚点文件可达数十 MB；常态报告只追加、不读全文，压缩改由
`eval-dedup-threshold.py --compact` 或 `INVEST_DEDUP_MAINTENANCE=1`
显式触发，避免每轮报告为几十行新锚点重写几十 MB。
默认不保留 `.bak`（与主文件等大，白占磁盘）：新文件经解析校验 + `os.replace`
原子替换后才删备份；`INVEST_DEDUP_KEEP_BACKUP=1` 可要求保留。
"""

from __future__ import annotations

import json

from pathlib import Path

import pytest

from src.python.providers import news_dedup, news_dedup_anchor_policy, news_dedup_anchor_store

pytestmark = [pytest.mark.unit, pytest.mark.unit_news]


def _rows(directory) -> list[dict]:
    """读取锚点目录下全部分片与未分片单文件（gzip 分片透明解压）。"""
    import gzip
    import os

    rows: list[dict] = []
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if name.endswith(".jsonl.gz"):
            with gzip.open(path, "rt", encoding="utf-8") as f:
                rows.extend(json.loads(line) for line in f if line.strip())
        elif name.endswith(".jsonl"):
            with open(path, encoding="utf-8") as f:
                rows.extend(json.loads(line) for line in f if line.strip())
    return rows


def _raw(directory) -> str:
    """锚点目录下全部内容拼成一个字符串（断言子串/体积时用）。"""
    import gzip
    import os

    chunks: list[str] = []
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if name.endswith(".jsonl.gz"):
            with gzip.open(path, "rt", encoding="utf-8") as f:
                chunks.append(f.read())
        elif name.endswith(".jsonl"):
            with open(path, encoding="utf-8") as f:
                chunks.append(f.read())
    return "".join(chunks)


def _record(source: str, title: str, ratio: float) -> str:
    return json.dumps(
        {
            "source_a": source,
            "title_a": title,
            "source_b": "src-b",
            "title_b": f"对照-{title}",
            "ratio": ratio,
        },
        ensure_ascii=False,
    )


class TestAnchorCompaction:
    def _anchor_file(self, tmp_path, monkeypatch):
        path = tmp_path / "anchors.jsonl"
        path.write_text(
            "\n".join(
                [
                    _record("sina", "标题A", 0.5),  # 旧
                    _record("sina", "标题B", 0.5),
                    _record("sina", "标题A", 0.9),  # 新 → 应保留这条
                    "",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(news_dedup_anchor_store, "_ANCHOR_PATH", str(path))
        monkeypatch.setattr(news_dedup_anchor_policy, "_ANCHOR_SIZE_WARN_BYTES", 1)  # 强制超阈值
        monkeypatch.delenv(news_dedup._ANCHOR_COMPACT_ENV, raising=False)
        return path

    def test_keeps_latest_per_title_pair(self, tmp_path, monkeypatch):
        path = self._anchor_file(tmp_path, monkeypatch)
        assert news_dedup_anchor_policy._compact_anchor_file(path.stat().st_size) is True
        lines = _rows(tmp_path)
        assert len(lines) == 2  # 3 行 → 2 个唯一标题对
        kept = {(r["source_a"], r["title_a"]): r["ratio"] for r in lines}
        assert kept[("sina", "标题A")] == 0.9  # 保留最新一条

    def test_backup_cleaned_after_verified_replace(self, tmp_path, monkeypatch):
        """默认不留下与主文件等大的 `.bak`（实测 37.9 MB 白占磁盘）。"""
        self._anchor_file(tmp_path, monkeypatch)
        news_dedup_anchor_policy._compact_anchor_file(news_dedup.anchor_total_bytes(str(tmp_path / "anchors.jsonl")))
        assert not list(tmp_path.glob("*.bak")), "默认不保留与主文件等大的 .bak"

    def test_backup_kept_on_request(self, tmp_path, monkeypatch):
        """`INVEST_DEDUP_KEEP_BACKUP=1` 时保留备份（回滚需要时用）。"""
        base = str(tmp_path / "anchors.jsonl")
        self._anchor_file(tmp_path, monkeypatch)
        news_dedup_anchor_policy._compact_anchor_file(news_dedup.anchor_total_bytes(base))  # 先建分片（无 .bak）
        rows = _rows(tmp_path)
        assert rows and not list(tmp_path.glob("*.bak"))

        monkeypatch.setenv(news_dedup_anchor_store._ANCHOR_KEEP_BACKUP_ENV, "1")
        news_dedup.compact_anchor_file(base, target_bytes=10, branch_min_keep=0)  # 强制裁剪 → 重写分片
        assert list(tmp_path.glob("*.bak")), "KEEP_BACKUP=1 时应保留分片备份"

    def test_env_disables_compaction(self, tmp_path, monkeypatch):
        path = self._anchor_file(tmp_path, monkeypatch)
        monkeypatch.setenv(news_dedup._ANCHOR_COMPACT_ENV, "0")
        before = path.read_text(encoding="utf-8")
        news_dedup_anchor_policy._compact_anchor_file(path.stat().st_size)
        assert path.read_text(encoding="utf-8") == before
        assert not list(tmp_path.glob("*.bak"))

    def test_below_threshold_is_noop(self, tmp_path, monkeypatch):
        path = self._anchor_file(tmp_path, monkeypatch)
        monkeypatch.setattr(news_dedup_anchor_policy, "_ANCHOR_SIZE_WARN_BYTES", 10**9)
        before = path.read_text(encoding="utf-8")
        news_dedup_anchor_policy._compact_anchor_file(path.stat().st_size)
        assert path.read_text(encoding="utf-8") == before

    def test_marks_unattributed_rows_as_legacy(self, tmp_path, monkeypatch):
        """无规则指纹的早期行补 legacy 标注后保留（不丢历史，也不与在用指纹混算）。"""
        from src.python.providers.news_dedup_rules import ANCHOR_LEGACY_ERA, ANCHOR_RULES_FIELD

        path = self._anchor_file(tmp_path, monkeypatch)
        news_dedup_anchor_policy._compact_anchor_file(path.stat().st_size)
        rows = _rows(tmp_path)
        assert rows
        assert {r[ANCHOR_RULES_FIELD] for r in rows} == {ANCHOR_LEGACY_ERA}
        kept = {(r["source_a"], r["title_a"]): r["ratio"] for r in rows}
        assert kept[("sina", "标题A")] == 0.9, "补标注只加字段，不改原记录内容"


class TestSizeCap:
    """体积上限：最旧优先裁剪，但每分支留配额、并发写入让路、无事不重写。"""

    def _row(self, branch: str, title: str, ts: str) -> dict:
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

    def _write(self, tmp_path, rows):
        path = tmp_path / "anchors.jsonl"
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        return path

    def test_branch_quota_protects_small_branch(self, tmp_path):
        """体积裁剪不得把小分支整类裁光（否则校准报告会误报「该规则没生效」）。"""
        rows = [self._row("cross_skip", f"旧样本{i:03d}", "2026-10-01 10:00") for i in range(300)]
        rows += [self._row("cross_opposite", f"稀{branch}", "2026-10-02 10:00") for branch in "ABC"]
        path = self._write(tmp_path, rows)

        result = news_dedup.compact_anchor_file(str(path), target_bytes=20_000, branch_min_keep=3)

        assert result["trimmed"] > 0
        assert result["trimmed_by_branch"].get("cross_opposite", 0) == 0
        kept = _rows(tmp_path)
        assert sum(1 for r in kept if r["rule"] == "cross_opposite") == 3

    def test_aborts_when_file_changes_during_read(self, tmp_path, monkeypatch):
        """读取期间被并发追加 → 放弃本次压缩（不吞掉另一个进程写入的行）。"""
        path = self._write(tmp_path, [self._row("cross_skip", "甲", "2026-10-01 10:00")])
        real_read = news_dedup.read_anchor_lines

        def racing_read(base=None):
            lines = real_read(base)
            # 读取完成、写回之前，另一个进程追加了一行
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(self._row("cross_skip", "并发写入", "2026-10-02 10:00"), ensure_ascii=False) + "\n")
            return lines

        monkeypatch.setattr(news_dedup_anchor_policy, "read_anchor_lines", racing_read)
        result = news_dedup.compact_anchor_file(str(path), target_bytes=1)

        assert result["aborted"] == "concurrent-write"
        assert result["written"] is False
        assert "并发写入" in path.read_text(encoding="utf-8"), "并发写入的行必须保留"

    def test_no_rewrite_when_nothing_to_trim(self, tmp_path):
        """无行可裁、无需补标注时不重写文件（避免几十 MB 的空转重写）。"""
        rows = [self._row("cross_skip", "甲", "2026-10-28 10:00"), self._row("cross_skip", "乙", "2026-10-28 11:00")]
        path = self._write(tmp_path, rows)
        news_dedup.compact_anchor_file(str(path), target_bytes=10**9)  # 首次：旧单文件迁入分片
        shard = next(tmp_path.glob("dedup_anchors-*.jsonl.gz"))
        before = shard.stat().st_mtime_ns

        result = news_dedup.compact_anchor_file(str(path), target_bytes=10**9)

        assert result["written"] is False, "无行可裁且已是分片形态 → 不重写"
        assert shard.stat().st_mtime_ns == before


class TestSharding:
    """按月 gzip 分片：写侧压缩、旧单文件兼容、跨月重分片、空月份清理。"""

    def _row(self, title: str, ts: str) -> dict:
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
            "rule": "cross_skip",
            "anchor_rules_version": _ANCHOR_RULES_VERSION,
        }

    def _base(self, tmp_path, monkeypatch) -> str:
        base = str(tmp_path / "anchors.jsonl")
        monkeypatch.setattr(news_dedup_anchor_store, "_ANCHOR_PATH", base)
        monkeypatch.delenv(news_dedup._ANCHOR_COMPACT_ENV, raising=False)
        return base

    def test_flush_writes_gzip_shard(self, tmp_path, monkeypatch):
        """写侧落在当月 gzip 分片，不再生成未压缩单文件。"""
        import datetime as dt

        self._base(tmp_path, monkeypatch)
        news_dedup_anchor_policy._ANCHOR_RECORDS = [self._row("新闻甲", "")]
        news_dedup_anchor_policy._flush_anchors()

        shards = sorted(tmp_path.glob("dedup_anchors-*.jsonl.gz"))
        assert len(shards) == 1
        assert shards[0].name == f"dedup_anchors-{dt.datetime.now():%Y%m}.jsonl.gz"
        assert shards[0].read_bytes()[:2] == b"\x1f\x8b", "分片必须是 gzip"
        assert not (tmp_path / "anchors.jsonl").exists(), "不再写未压缩单文件"
        assert len(_rows(tmp_path)) == 1

    def test_cross_month_rows_split_into_shards(self, tmp_path, monkeypatch):
        """压缩按记录的月份重新分片（跨月数据落两个分片）。"""
        import datetime as dt

        base = self._base(tmp_path, monkeypatch)
        old_month = (dt.datetime.now() - dt.timedelta(days=70)).strftime("%Y-%m")
        this_month = dt.datetime.now().strftime("%Y-%m")
        old_row = self._row("旧月新闻", f"{old_month}-05 10:00")
        new_row = self._row("本月新闻", f"{this_month}-05 10:00")
        Path(base).write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in (old_row, new_row)), encoding="utf-8"
        )

        result = news_dedup.compact_anchor_file(base, retention_days=0, target_bytes=10**9)

        names = sorted(p.name for p in tmp_path.glob("dedup_anchors-*.jsonl.gz"))
        assert names == sorted(
            [
                f"dedup_anchors-{old_month.replace('-', '')}.jsonl.gz",
                f"dedup_anchors-{this_month.replace('-', '')}.jsonl.gz",
            ]
        )
        assert result["shards"] and not Path(base).exists(), "旧单文件已并入分片并删除"

    def test_expired_month_shard_is_removed(self, tmp_path, monkeypatch):
        """整月样本全部超出保留期 → 该月分片被删，读侧不再返回。"""
        import datetime as dt

        base = self._base(tmp_path, monkeypatch)
        stale_ts = (dt.datetime.now() - dt.timedelta(days=70)).strftime("%Y-%m-%d %H:%M")
        fresh_ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        Path(base).write_text(
            "".join(
                json.dumps(r, ensure_ascii=False) + "\n"
                for r in (self._row("过期新闻", stale_ts), self._row("新鲜新闻", fresh_ts))
            ),
            encoding="utf-8",
        )
        news_dedup.compact_anchor_file(base, retention_days=0, target_bytes=10**9)  # 先分成两个月
        assert len(list(tmp_path.glob("dedup_anchors-*.jsonl.gz"))) == 2

        news_dedup.compact_anchor_file(base, retention_days=30, target_bytes=10**9)

        assert len(list(tmp_path.glob("dedup_anchors-*.jsonl.gz"))) == 1
        assert [r["title_a"] for r in _rows(tmp_path)] == ["新鲜新闻"]

    def test_legacy_single_file_still_readable(self, tmp_path, monkeypatch):
        """未压缩单文件仍可读（分片共存期不丢历史）。"""
        base = self._base(tmp_path, monkeypatch)
        Path(base).write_text(
            json.dumps(self._row("旧版新闻", "2026-10-01 10:00"), ensure_ascii=False) + "\n", encoding="utf-8"
        )

        lines = news_dedup.read_anchor_lines(base)

        assert len(lines) == 1 and "旧版新闻" in lines[0]
        assert news_dedup.anchor_total_bytes(base) == Path(base).stat().st_size
