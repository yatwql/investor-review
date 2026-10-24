"""锚点文件压缩（显式维护触发，原子替换 + 校验后清理备份 + 可关闭）。

背景：锚点文件可达数十 MB；常态报告只追加、不读全文，压缩改由
`eval-dedup-threshold.py --compact` 或 `INVEST_DEDUP_MAINTENANCE=1`
显式触发，避免每轮报告为几十行新锚点重写几十 MB。
默认不保留 `.bak`（与主文件等大，白占磁盘）：新文件经解析校验 + `os.replace`
原子替换后才删备份；`INVEST_DEDUP_KEEP_BACKUP=1` 可要求保留。
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

    def test_keeps_latest_per_title_pair(self, tmp_path, monkeypatch):
        path = self._anchor_file(tmp_path, monkeypatch)
        assert news_dedup._auto_compact_anchor_file(path.stat().st_size) is True
        lines = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 2  # 3 行 → 2 个唯一标题对
        kept = {(r["source_a"], r["title_a"]): r["ratio"] for r in lines}
        assert kept[("sina", "标题A")] == 0.9  # 保留最新一条

    def test_backup_cleaned_after_verified_replace(self, tmp_path, monkeypatch):
        """默认不留下与主文件等大的 `.bak`（实测 37.9 MB 白占磁盘）。"""
        path = self._anchor_file(tmp_path, monkeypatch)
        news_dedup._auto_compact_anchor_file(path.stat().st_size)
        assert not (tmp_path / "anchors.jsonl.bak").exists()

    def test_backup_kept_on_request(self, tmp_path, monkeypatch):
        """`INVEST_DEDUP_KEEP_BACKUP=1` 时保留备份（回滚需要时用）。"""
        path = self._anchor_file(tmp_path, monkeypatch)
        monkeypatch.setenv(news_dedup._ANCHOR_KEEP_BACKUP_ENV, "1")
        news_dedup._auto_compact_anchor_file(path.stat().st_size)
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
