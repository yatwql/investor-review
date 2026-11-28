"""板块分类原语（关键词表加载与名称判定）。

锁住的契约：
  - 关键词表读盘失败（缺文件 / 损坏 JSON）时降级为空表，判定回落 "--"
  - 空名称 / 未命中关键词 → "--"，命中按关键词表取值
  - 关键词表访问器返回浅拷贝，改动副本不污染进程内单源
  - 热重载替换进程内表（知识库更新与测试注入同一入口）

运行：
  .venv/bin/python -m pytest src/test/unit/core/test_sector.py -v
"""

from __future__ import annotations

import pytest

from src.python.core import sector

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestSectorKeywordTable:
    """行业关键词表的加载与降级。"""

    def test_missing_file_yields_empty_table(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sector, "SECTOR_KEYWORDS_FILE", str(tmp_path / "absent.json"))
        assert sector.load_sector_keywords() == {}

    def test_corrupt_file_yields_empty_table(self, tmp_path, monkeypatch):
        broken = tmp_path / "sector_keywords.json"
        broken.write_text("{not-json", encoding="utf-8")
        monkeypatch.setattr(sector, "SECTOR_KEYWORDS_FILE", str(broken))
        assert sector.load_sector_keywords() == {}

    def test_reload_replaces_process_table(self, tmp_path, monkeypatch):
        table_file = tmp_path / "sector_keywords.json"
        table_file.write_text('{"白酒": "消费"}', encoding="utf-8")
        monkeypatch.setattr(sector, "SECTOR_KEYWORDS_FILE", str(table_file))
        monkeypatch.setattr(sector, "_SECTOR_KEYWORDS", {}, raising=False)

        reloaded = sector.reload_sector_keywords()

        assert reloaded == {"白酒": "消费"}
        assert sector.classify_sector("某白酒基金") == "消费"


class TestClassifySector:
    """名称 → 板块判定。"""

    def test_blank_name_classified_as_unknown_sector(self):
        assert sector.classify_sector("") == "--"

    def test_keyword_hit_returns_its_sector(self, monkeypatch):
        monkeypatch.setattr(sector, "_SECTOR_KEYWORDS", {"芯片": "科技"}, raising=False)
        # 判定前做去空格 + 大写归一，故含空格与小写的名称同样命中
        assert sector.classify_sector(" 某 芯 片 etf ") == "科技"

    def test_unmatched_name_returns_unknown_sector(self, monkeypatch):
        monkeypatch.setattr(sector, "_SECTOR_KEYWORDS", {"芯片": "科技"}, raising=False)
        assert sector.classify_sector("某消费基金") == "--"

    def test_accessor_returns_detached_copy(self, monkeypatch):
        monkeypatch.setattr(sector, "_SECTOR_KEYWORDS", {"白酒": "消费"}, raising=False)
        copy = sector.sector_keywords()
        copy["新增"] = "科技"
        assert "新增" not in sector.sector_keywords()
