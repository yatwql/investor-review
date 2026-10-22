"""test_check_doc_drift 兄弟分片（tree）：目录树解析、说明计数与版本目录顺序。"""
# ruff: noqa: F811 — 夹具以参数名注入（与模块级同名导入非重定义）

from __future__ import annotations
import pytest

# 夹具按名注入（由测试签名消费），代码里无引用

from src.test.unit.scripts.test_check_doc_drift import (
    drift,  # noqa: F401
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
    pytest.mark.usefixtures("offline_external_sources"),
]


class TestTreeParsing:
    def test_reconstructs_nested_paths(self, drift):
        doc = (
            "```\n"
            "investor-review/\n"
            "├── src/                              # 源代码\n"
            "│   ├── __init__.py                   #   包标记\n"
            "│   └── python/                       # 主程序\n"
            "│       └── cache.py                  #   缓存\n"
            "└── scripts/                          # 脚本\n"
            "    └── test-runner.py                #   测试驱动\n"
            "```\n"
        )
        paths = drift.parse_tree_paths(doc)
        assert "src/__init__.py" in paths
        assert "src/python/cache.py" in paths
        assert "scripts/test-runner.py" in paths

    def test_outside_code_fence_ignored(self, drift):
        assert drift.parse_tree_paths("├── ghost.py  # 不在代码块内\n") == set()


class TestTreeDescCounts:
    """folders.md 树描述计数禁令：阿拉伯数字+量词禁写（docs/archive 记录域豁免）。"""

    def test_flags_arabic_count(self, drift):
        """文件条目描述含数字+量词 → 报出。"""
        doc = "```\nroot/\n├── a.py # 工具（3 项检查）\n```\n"
        findings = drift.check_tree_desc_counts(doc)
        assert any("a.py" in f and "3 项" in f for f in findings)

    def test_flags_dir_line_count(self, drift):
        """目录条目行同样入检（目录描述也会写文件计数）。"""
        doc = "```\nroot/\n├── llm/ # 场景测试（9 个测试文件）\n```\n"
        assert any("`llm`" in f for f in drift.check_tree_desc_counts(doc))

    def test_archive_domain_exempt(self, drift):
        """docs/archive/ 记录域描述豁免（归档文档的固有数字属记录内容）。"""
        doc = "```\nroot/\n├── docs/\n│   └── archive/\n│       └── x.md # 记录（10 项分析）\n```\n"
        assert drift.check_tree_desc_counts(doc) == []

    def test_chinese_numeral_allowed(self, drift):
        """中文数词形态（设计常量/分类名）不在扫描面。"""
        doc = "```\nroot/\n├── b.py # 合成（三因子/四类路由/多层防御）\n```\n"
        assert drift.check_tree_desc_counts(doc) == []

    def test_real_repo_passes(self, drift):
        """真实仓库树描述无违规计数（结构关系断言，不写死条数）。"""
        text = drift._FOLDERS_MD.read_text(encoding="utf-8")
        assert drift.check_tree_desc_counts(text) == []


class TestTreeVersionOrder:
    """版本目录块升序禁令：同父目录 vN.N.x/ 条目按版本号升序（集合比对不看先后的盲区补位）。"""

    def test_ascending_passes(self, drift):
        """升序版本块 → 无 finding。"""
        doc = (
            "```\nroot/\n├── archive/\n│   ├── v0.1.x/\n│   │   └── a.md # 记录\n"
            "│   ├── v0.9.x/\n│   │   └── b.md # 记录\n"
            "│   └── v0.10.x/\n│       └── c.md # 记录\n```\n"
        )
        assert drift.check_tree_version_order(doc) == []

    def test_descending_reported(self, drift):
        """新块插到组首（真实缺陷形态：0.9 后接 0.13→0.10 倒序）→ 报出乱序。"""
        doc = (
            "```\nroot/\n├── archive/\n│   ├── v0.9.x/\n│   │   └── a.md # 记录\n"
            "│   ├── v0.13.x/\n│   │   └── b.md # 记录\n"
            "│   └── v0.10.x/\n│       └── c.md # 记录\n```\n"
        )
        findings = drift.check_tree_version_order(doc)
        assert any("v0.10.x" in f and "v0.13.x" in f and "乱序" in f for f in findings)

    def test_lexicographic_trap_numeric_order(self, drift):
        """数值序而非字典序：v0.9.x → v0.10.x 合法（字典序会误报）。"""
        doc = (
            "```\nroot/\n├── archive/\n│   ├── v0.9.x/\n│   │   └── a.md # 记录\n"
            "│   └── v0.10.x/\n│       └── b.md # 记录\n```\n"
        )
        assert drift.check_tree_version_order(doc) == []

    def test_independent_parents(self, drift):
        """不同父目录独立判定（a 乱序报出、b 升序不牵连）。"""
        doc = (
            "```\nroot/\n├── a/\n│   ├── v0.2.x/\n│   │   └── x.md # 记录\n"
            "│   └── v0.1.x/\n│       └── y.md # 记录\n└── b/\n"
            "    ├── v0.1.x/\n    │   └── p.md # 记录\n"
            "    └── v0.2.x/\n        └── q.md # 记录\n```\n"
        )
        findings = drift.check_tree_version_order(doc)
        assert len(findings) == 1 and "a/v0.1.x" in findings[0]

    def test_real_repo_passes(self, drift):
        """真实仓库版本块升序（结构关系断言，不写死条数）。"""
        text = drift._FOLDERS_MD.read_text(encoding="utf-8")
        assert drift.check_tree_version_order(text) == []
