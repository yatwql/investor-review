"""`scripts/eval-dedup-threshold.py` 报告各分支与 CLI 编排的补盲测试。

补齐前序用例未覆盖的**渲染分支**：历史指纹分布、cross_skip 边界样本、cross_merge 的
bg 边界、cross_merge_bg2 证据类型、同源未达阈值分布、建议区的漏判/边界告警，以及
`analyze` 的残行与规则时代归类、`load_anchors` 的坏行容忍、`main` 的压缩与空文件路径。

渲染用例以**受控 `analyze` 结果**驱动（`report` 的职责是把判定分布画出来，判定本身由
`classify_pair`/`analyze` 的用例覆盖），断言的是上屏内容与口径而非 mock 属性。
"""

from __future__ import annotations

import gzip
import json
import sys

import pytest

from src.python.providers.news_dedup_rules import (
    ANCHOR_RULES_FIELD,
    _ANCHOR_RULES_VERSION,
    _CROSS_BG2_RATIO,
    _CROSS_BIGRAM_MIN,
    _CROSS_DIRECT_RATIO,
    _CROSS_SAFE_RATIO,
)
from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_SHARD_MONTH = "202601"

#: 共享真专名（`_shared_carries_proper_noun` 为真）的一对标题。
_PROPER_A = "摩根士丹利上调Paypal目标价"
_PROPER_B = "Paypal致股东：“请相信我们”"


@pytest.fixture()
def tool():
    return load_script("eval-dedup-threshold.py")


def _record(title_a: str, title_b: str, *, rule: str = "cross_skip", field: str | None = _ANCHOR_RULES_VERSION) -> dict:
    record = {
        "ts": "",
        "title_a": title_a,
        "title_b": title_b,
        "source_a": "东方财富",
        "source_b": "新浪财经",
        "ratio": 0.4,
        "bigram_overlap": 2,
        "merged": False,
        "rule": rule,
    }
    if field is not None:
        record[ANCHOR_RULES_FIELD] = field
    return record


def _entry(title_a: str, title_b: str, ratio: float, overlap: int) -> dict:
    """`analyze` 产出的分支条目形态（含重算后的当前 ratio / overlap）。"""
    return {**_record(title_a, title_b), "_ratio_now": ratio, "_overlap_now": overlap}


def _write_shard(tmp_path, records: list[dict]) -> str:
    path = tmp_path / f"dedup_anchors-{_SHARD_MONTH}.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    return str(path)


def _analyze_result(branches: dict | None = None, **overrides) -> dict:
    result = {
        "branches": branches or {},
        "era_current": 1,
        "era_skipped": 0,
        "era_legacy": 0,
        "era_unattributed": 0,
        "era_versions": {},
        "drift": 0,
    }
    result.update(overrides)
    return result


class TestAnalyzeClassification:
    """`analyze`：残行跳过、规则时代归类（口径只纳入当前指纹）。"""

    def test_records_without_titles_are_skipped(self, tool):
        """缺标题残行不进判定（空串相似度恒为 1，会误进安全区）。"""
        data = tool.analyze([_record("", "有标题"), _record("有标题", "")])
        assert dict(data["branches"]) == {}
        assert data["era_current"] == 0

    def test_legacy_and_unattributed_eras_are_counted_but_excluded(self, tool):
        data = tool.analyze(
            [
                _record("新闻甲", "新闻乙"),
                _record("新闻丙", "新闻丁", field="旧指纹"),
                _record("新闻戊", "新闻己", field=None),
            ]
        )

        assert data["era_current"] == 1
        assert data["era_skipped"] == 2
        assert data["era_legacy"] == 1, "有指纹但非当前 → 历史时代"
        assert data["era_unattributed"] == 1, "无指纹 → 未标注（旧版遗留）"
        assert data["era_versions"]["旧指纹"] == 1

    def test_stored_rule_mismatch_counts_as_drift(self, tool):
        """记录时 rule 与重判分支口径不同 → drift 计数（仅统计，不影响分布）。"""
        data = tool.analyze([_record("新闻甲", "新闻乙", rule="cross_merge")])
        assert data["drift"] == 1


class TestBranchMatchesStored:
    """历史时代的 rule 命名粗对齐。"""

    def test_prefix_families_align(self, tool):
        assert tool._branch_matches_stored("cross_safe_merged", "cross_safe") is True
        assert tool._branch_matches_stored("cross_safe_kept", "cross_safe") is True
        assert tool._branch_matches_stored("cross_merge", "cross_safe") is False
        assert tool._branch_matches_stored("same_src_kept", "same_src") is True
        assert tool._branch_matches_stored("cross_skip", "same_src") is False

    def test_exact_names_require_equality(self, tool):
        assert tool._branch_matches_stored("cross_merge_bg2", "cross_merge_bg2") is True
        assert tool._branch_matches_stored("cross_merge", "cross_merge_bg2") is False
        assert tool._branch_matches_stored("cross_skip", "cross_skip") is True


class TestLoadAnchorsTolerance:
    """坏行容忍：空行与非法 JSON 行跳过，不当成记录。"""

    def test_blank_and_broken_lines_are_ignored(self, tool, tmp_path):
        path = tmp_path / f"dedup_anchors-{_SHARD_MONTH}.jsonl.gz"
        good = json.dumps(_record("新闻甲", "新闻乙"), ensure_ascii=False)
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write("\n")
            f.write("{ 不是合法 JSON\n")
            f.write(good + "\n")

        records = tool.load_anchors(str(path))

        assert len(records) == 1
        assert records[0]["title_a"] == "新闻甲"


class TestReportSectionRendering:
    """报告各节在**非汇总模式**下的样本渲染。"""

    def _report(self, tool, monkeypatch, capsys, branches: dict, **overrides) -> str:
        monkeypatch.setattr(tool, "analyze", lambda records: _analyze_result(branches, **overrides))
        monkeypatch.setattr(tool, "anchor_total_bytes", lambda _p: 0)
        tool.report([{"title_a": "x", "title_b": "y"}], summary_only=False, sample=2)
        return capsys.readouterr().out

    def test_legacy_fingerprint_top3_is_printed(self, tool, monkeypatch, capsys):
        out = self._report(
            tool,
            monkeypatch,
            capsys,
            {},
            era_versions={_ANCHOR_RULES_VERSION: 5, "指纹乙": 3, "指纹甲": 1},
        )
        assert "历史指纹分布（Top3）" in out
        assert "指纹乙=3、指纹甲=1" in out
        assert f"{_ANCHOR_RULES_VERSION}=" not in out, "当前指纹不应出现在「历史」分布里"

    def test_cross_skip_prints_high_ratio_samples(self, tool, monkeypatch, capsys):
        """bg≤1 且 ratio≥0.40 的样本逐条列出（非汇总模式）。"""
        out = self._report(
            tool,
            monkeypatch,
            capsys,
            {"cross_skip": [_entry("新闻甲", "新闻乙", 0.42, 1)]},
        )
        assert "bg≤1 且 ratio≥0.40: 1 条" in out
        assert "r=0.420 bg=1" in out

    def test_cross_skip_below_bg2_lists_proper_noun_candidates(self, tool, monkeypatch, capsys):
        out = self._report(
            tool,
            monkeypatch,
            capsys,
            {"cross_skip": [_entry(_PROPER_A, _PROPER_B, _CROSS_BG2_RATIO - 0.01, 2)]},
        )
        assert "其中含真专名证据: 1 条" in out
        assert "shared=" in out

    def test_cross_merge_bg3_edge_is_printed(self, tool, monkeypatch, capsys):
        out = self._report(
            tool,
            monkeypatch,
            capsys,
            {"cross_merge": [_entry("新闻甲", "新闻乙", 0.43, _CROSS_BIGRAM_MIN)]},
        )
        assert f"bg={_CROSS_BIGRAM_MIN} 边界: 1 条" in out
        assert "r=0.430" in out

    def test_cross_merge_bg2_samples_are_printed(self, tool, monkeypatch, capsys):
        out = self._report(
            tool,
            monkeypatch,
            capsys,
            {"cross_merge_bg2": [_entry(_PROPER_A, _PROPER_B, _CROSS_BG2_RATIO, 2)]},
        )
        assert "cross_merge_bg2（bg=2" in out
        assert "Paypal" in out

    def test_same_source_kept_distribution_is_printed(self, tool, monkeypatch, capsys):
        out = self._report(
            tool,
            monkeypatch,
            capsys,
            {
                "same_src_kept": [_entry("新闻甲", "新闻乙", 0.3, 1), _entry("新闻丙", "新闻丁", 0.3, 5)],
                "same_src_merged": [_entry("新闻戊", "新闻己", 0.9, 9)],
            },
        )
        assert "已合并: 1 条；未达阈值: 2 条" in out
        assert "未达阈值的重叠分布: bg=1:1  bg=3+:1" in out

    def test_safe_merged_edge_zone_counted(self, tool, monkeypatch, capsys):
        out = self._report(
            tool,
            monkeypatch,
            capsys,
            {
                "cross_safe_merged": [
                    _entry("新闻甲", "新闻乙", _CROSS_SAFE_RATIO, 2),
                    _entry("新闻丙", "新闻丁", _CROSS_DIRECT_RATIO, 1),
                ]
            },
        )
        assert f"擦边区（{_CROSS_SAFE_RATIO}~{_CROSS_DIRECT_RATIO} 且 bg<3）: 1 条" in out


class TestAdviceWarnings:
    """建议区的三类告警：梯度漏判（规则异常）、bg 边界误合并风险。"""

    def _advice(self, tool, capsys, branches: dict) -> str:
        tool._print_advice(branches)
        return capsys.readouterr().out

    def test_missed_merge_is_flagged_as_rule_anomaly(self, tool, capsys):
        """满足 bg=2 梯度条件（含真专名）却仍在 skip 分支 → 规则异常告警。"""
        out = self._advice(tool, capsys, {"cross_skip": [_entry(_PROPER_A, _PROPER_B, _CROSS_BG2_RATIO, 2)]})
        assert "[!!] 规则异常" in out
        assert "无漏判" not in out

    def test_bg3_boundary_is_flagged(self, tool, capsys):
        out = self._advice(tool, capsys, {"cross_merge": [_entry("新闻甲", "新闻乙", 0.43, _CROSS_BIGRAM_MIN)]})
        assert f"跨源 bg={_CROSS_BIGRAM_MIN} 边界 1 条" in out

    def test_quiet_when_no_samples_hit_either_branch(self, tool, capsys):
        """无 bg=2 漏判、无 bg=3 边界 → 只出 [OK] 与样本量提示。"""
        out = self._advice(tool, capsys, {"cross_merge": [_entry("新闻甲", "新闻乙", 0.9, 9)]})
        assert "无漏判" in out
        assert "[!!]" not in out and "[!]" not in out


class TestMainBranches:
    """`main()` 的压缩模式与空样本路径。"""

    def test_compact_missing_file_reports_and_returns(self, tool, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(
            sys, "argv", ["eval-dedup-threshold.py", "--compact", "--file", str(tmp_path / "none.jsonl")]
        )
        tool.main()

        assert "锚点文件不存在或为空" in capsys.readouterr().out

    def test_compact_existing_file_prints_result(self, tool, monkeypatch, tmp_path, capsys):
        path = _write_shard(tmp_path, [_record("新闻甲", "新闻乙")])
        monkeypatch.setattr(sys, "argv", ["eval-dedup-threshold.py", "--compact", "--file", path])
        tool.main()

        out = capsys.readouterr().out
        assert "锚点文件:" in out
        assert "压缩前: 1 行" in out

    def test_no_records_exits_zero_with_guidance(self, tool, monkeypatch, tmp_path, capsys):
        """空锚点 → 提示先积累数据，退出码 0（不是失败）。"""
        monkeypatch.setattr(sys, "argv", ["eval-dedup-threshold.py", "--file", str(tmp_path / "none.jsonl")])
        with pytest.raises(SystemExit) as excinfo:
            tool.main()

        assert excinfo.value.code == 0
        assert "请先运行一次报告生成" in capsys.readouterr().out

    def test_maintenance_compaction_failure_keeps_evaluation(self, tool, monkeypatch, tmp_path, capsys):
        """维护压缩抛 OSError 不得吞掉评估结论（先出报告，再给失败提示）。"""
        path = _write_shard(tmp_path, [_record("新闻甲", "新闻乙")])
        monkeypatch.setattr(sys, "argv", ["eval-dedup-threshold.py", "--file", path, "--summary"])

        def _boom(*_a, **_k):
            raise OSError("磁盘只读")

        monkeypatch.setattr(tool, "compact_anchors", _boom)
        tool.main()

        out = capsys.readouterr().out
        assert "当前阈值规则" in out
        assert "维护压缩失败" in out
        assert "磁盘只读" in out
