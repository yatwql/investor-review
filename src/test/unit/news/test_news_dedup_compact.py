"""锚点文件超限自动压缩（读侧触发，备份 + 原子替换 + 可关闭）。

背景：日志审计发现锚点文件已达 38.4 MB / 119,654 行，每轮报告都要全量读写，
而压缩此前只有手工命令入口。读侧超阈值自动压缩，避免把手工步骤留成长期债。
"""

from __future__ import annotations

import json

import pytest

from src.python.providers import news_dedup

pytestmark = [pytest.mark.unit, pytest.mark.unit_news]


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


class TestAutoCompact:
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
        monkeypatch.setattr(news_dedup, "_ANCHOR_PATH", str(path))
        monkeypatch.setattr(news_dedup, "_ANCHOR_SIZE_WARN_BYTES", 1)  # 强制超阈值
        monkeypatch.delenv(news_dedup._ANCHOR_AUTO_COMPACT_ENV, raising=False)
        return path

    def test_keeps_latest_per_title_pair_and_backs_up(self, tmp_path, monkeypatch):
        path = self._anchor_file(tmp_path, monkeypatch)
        news_dedup._auto_compact_anchor_file(path.stat().st_size)
        lines = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 2  # 3 行 → 2 个唯一标题对
        kept = {(r["source_a"], r["title_a"]): r["ratio"] for r in lines}
        assert kept[("sina", "标题A")] == 0.9  # 保留最新一条
        assert (tmp_path / "anchors.jsonl.bak").exists()

    def test_env_disables_auto_compact(self, tmp_path, monkeypatch):
        path = self._anchor_file(tmp_path, monkeypatch)
        monkeypatch.setenv(news_dedup._ANCHOR_AUTO_COMPACT_ENV, "0")
        before = path.read_text(encoding="utf-8")
        news_dedup._auto_compact_anchor_file(path.stat().st_size)
        assert path.read_text(encoding="utf-8") == before
        assert not (tmp_path / "anchors.jsonl.bak").exists()

    def test_below_threshold_is_noop(self, tmp_path, monkeypatch):
        path = self._anchor_file(tmp_path, monkeypatch)
        monkeypatch.setattr(news_dedup, "_ANCHOR_SIZE_WARN_BYTES", 10**9)
        before = path.read_text(encoding="utf-8")
        news_dedup._auto_compact_anchor_file(path.stat().st_size)
        assert path.read_text(encoding="utf-8") == before
