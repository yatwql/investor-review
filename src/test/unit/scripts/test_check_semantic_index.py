"""测试：check-semantic-index.py — 功能语义命名表双向校验

覆盖：
  - 标记区间提取：start/end 标记存在返回正文、缺失返回 None
  - 表行解析：仅取第一列反引号 slug，开关列 enable_portfolio_evolution 不误取
  - 合并章 key 解析：仅取「合并章代码标识符」注，并入说明注（dividend_flow）不误取
  - 权威源 ast 解析：功能开关注册表（features.py）键、registry._REPORT_SECTION_DEFAULT key
    （Assign 与 AnnAssign 两种赋值形态）
  - 注释剔除：tokenize 剔除注释、字符串字面量保留
  - 反向存在性：代码中出现为 True、仅注释提及为 False、__pycache__ 跳过
  - run_checks 三向校验：全通过 / 正向表外键 / 反向僵尸条目 / 合并章 key 缺失 / 标记缺失
  - 真实仓库冒烟：当前 technical.md + _config_defaults.py + report_section_registry.py 一致

测试通过脚本 import 方式直接复用解析函数，不运行真实 CLI。
"""

from __future__ import annotations

import runpy
import sys

import pytest
from src.test._script_loader import SCRIPTS_DIR, load_script


def sem_index_path():
    """`scripts/` 目录（入口冒烟用）。"""
    return SCRIPTS_DIR


@pytest.fixture(scope="module")
def sem_index():
    return load_script("check-semantic-index.py")


pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


# ═══ 标记区间提取 ═══


class TestMarkerRegion:
    def test_returns_body_between_markers(self, sem_index):
        doc = "头\n<!-- semantic-index:start -->\n表正文\n<!-- semantic-index:end -->\n尾"
        assert sem_index.extract_marker_region(doc) == "\n表正文\n"

    def test_none_when_start_missing(self, sem_index):
        doc = "无开始标记\n<!-- semantic-index:end -->\n"
        assert sem_index.extract_marker_region(doc) is None

    def test_none_when_end_missing(self, sem_index):
        doc = "<!-- semantic-index:start -->\n无结束标记\n"
        assert sem_index.extract_marker_region(doc) is None


# ═══ 表行解析 ═══


class TestParseTableSlugs:
    def test_extracts_only_first_cell_slug(self, sem_index):
        doc = (
            "<!-- semantic-index:start -->\n"
            "| 语义 slug | 中文名 | config 开关 |\n"
            "|:--|:--|:--|\n"
            "| `snapshot_diff` | 快照差异 | 随 `enable_portfolio_evolution` |\n"
            "| `cost_lots` | 成本流水 | 功能开关 `cost_lots`（默认关） |\n"
            "<!-- semantic-index:end -->"
        )
        assert sem_index.parse_table_slugs(doc) == ["snapshot_diff", "cost_lots"]

    def test_returns_empty_without_markers(self, sem_index):
        doc = "| `candidate_compare` | 候选基金比较 |\n"
        assert sem_index.parse_table_slugs(doc) == []


# ═══ 合并章 key 解析 ═══


class TestParseMergedSheetKeys:
    def test_only_merged_note_ignores_merged_into_note(self, sem_index):
        doc = (
            "<!-- semantic-index:start -->\n"
            "| `candidate_compare` | 候选基金比较 |\n"
            "\n"
            "> **子功能并入说明**：`dividend_flow`（分红现金流，并入 `fund_flow`）、"
            "`holding_diagnosis`（品种覆盖诊断，并入 `data_quality`）。\n"
            "\n"
            "> **合并章代码标识符**：`position_structure`（持仓结构与集中度，合并 "
            "`fund_overlap` + `correlation_analysis`）、`portfolio_history_drawdown`（组合历史走势与回撤）。\n"
            "<!-- semantic-index:end -->"
        )
        assert sem_index.parse_merged_sheet_keys(doc) == [
            "position_structure",
            "portfolio_history_drawdown",
        ]


# ═══ 权威源 ast 解析 ═══


class TestFeatureSwitchKeys:
    def test_parses_registry_keys(self, sem_index):
        source = (
            "_OTHER: dict = {}\n"
            "feature_switch_registry: dict[str, FeatureSwitchDef] = {\n"
            '    "data_quality": FeatureSwitchDef("数据质量", "d", GROUP_FUND_STYLE, True, True),\n'
            '    "cost_lots": FeatureSwitchDef("成本流水", "d", GROUP_FUND_STYLE, False, True),\n'
            "}\n"
        )
        assert sem_index.feature_switch_keys(source) == ["data_quality", "cost_lots"]

    def test_missing_registry_returns_empty(self, sem_index):
        source = 'feature_switch_registry: dict = {}\n_X = {"a": 1}\n'
        assert sem_index.feature_switch_keys(source) == []


class TestRegistrySectionKeys:
    def test_annassign_form(self, sem_index):
        source = (
            "_REPORT_SECTION_DEFAULT: list[dict] = [\n"
            '    {"key": "summary", "name": "投资分析汇总", "number": 1},\n'
            '    {"key": "position_structure", "name": "持仓结构与集中度", "number": 5},\n'
            "]\n"
        )
        assert sem_index.registry_section_keys(source) == ["summary", "position_structure"]

    def test_plain_assign_form(self, sem_index):
        source = '_REPORT_SECTION_DEFAULT = [{"key": "action", "name": "行动建议", "number": 17}]\n'
        assert sem_index.registry_section_keys(source) == ["action"]

    def test_other_assign_ignored(self, sem_index):
        source = '_OTHER = [{"key": "x"}]\n'
        assert sem_index.registry_section_keys(source) == []


# ═══ 注释剔除与反向存在性 ═══


class TestCodeWithoutComments:
    def test_strips_comments_keeps_strings(self, sem_index):
        source = '# 顶部注释\nx = 1  # 行尾注释\ny = "rebalance_advice"  # 字符串保留\n'
        stripped = sem_index._code_without_comments(source)
        assert "顶部注释" not in stripped
        assert "行尾注释" not in stripped
        assert "rebalance_advice" in stripped
        assert "x" in stripped and "y" in stripped

    def test_comment_only_file_yields_empty(self, sem_index):
        source = "# rebalance_advice 已删除，仅注释提及\n"
        assert sem_index._code_without_comments(source) == ""


class TestSlugExistsInCode:
    def test_true_when_substring_in_identifier(self, sem_index, tmp_path):
        (tmp_path / "a.py").write_text("def build_rebalance_advice(): pass\n", encoding="utf-8")
        assert sem_index.slug_exists_in_code(tmp_path, "rebalance_advice") is True

    def test_true_when_string_literal(self, sem_index, tmp_path):
        (tmp_path / "a.py").write_text('data = {"rebalance_advice": []}\n', encoding="utf-8")
        assert sem_index.slug_exists_in_code(tmp_path, "rebalance_advice") is True

    def test_false_when_comment_only(self, sem_index, tmp_path):
        (tmp_path / "a.py").write_text("# rebalance_advice 已删除\n", encoding="utf-8")
        assert sem_index.slug_exists_in_code(tmp_path, "rebalance_advice") is False

    def test_false_when_missing(self, sem_index, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        assert sem_index.slug_exists_in_code(tmp_path, "ghost_slug") is False

    def test_skips_pycache(self, sem_index, tmp_path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "a.py").write_text("zombie_slug = 1\n", encoding="utf-8")
        assert sem_index.slug_exists_in_code(tmp_path, "zombie_slug") is False


# ═══ run_checks 三向校验 ═══


def _valid_doc() -> str:
    return (
        "<!-- semantic-index:start -->\n"
        "| 语义 slug | 中文名 |\n"
        "|:--|:--|\n"
        "| `candidate_compare` | 候选基金比较 |\n"
        "| `cost_lots` | 成本流水 |\n"
        "\n"
        "> **合并章代码标识符**：`position_structure`（持仓结构与集中度，合并 `fund_overlap`）。\n"
        "<!-- semantic-index:end -->\n"
    )


def _valid_features() -> str:
    return (
        "feature_switch_registry: dict[str, FeatureSwitchDef] = {\n"
        '    "candidate_compare": FeatureSwitchDef("候选基金比较", "d", GROUP_FUND_STYLE, False, True),\n'
        '    "cost_lots": FeatureSwitchDef("成本流水", "d", GROUP_FUND_STYLE, False, True),\n'
        "}\n"
    )


def _valid_registry() -> str:
    return (
        "_REPORT_SECTION_DEFAULT: list[dict] = [\n"
        '    {"key": "summary", "name": "投资分析汇总", "number": 1},\n'
        '    {"key": "position_structure", "name": "持仓结构与集中度", "number": 5},\n'
        "]\n"
    )


class TestRunChecks:
    def test_all_pass(self, sem_index, tmp_path):
        (tmp_path / "a.py").write_text(
            'def build_candidate_compare(): pass\nd = {"cost_lots": False}\ndef build_position_relationship(): pass\n',
            encoding="utf-8",
        )
        assert sem_index.run_checks(_valid_doc(), _valid_features(), _valid_registry(), tmp_path) == []

    def test_forward_finds_unregistered_key(self, sem_index, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        features = (
            "feature_switch_registry: dict = {\n"
            '    "market_temperature": FeatureSwitchDef("市场温度", "d", 1, False, True),\n'
            "}\n"
        )
        findings = sem_index.run_checks(_valid_doc(), features, _valid_registry(), tmp_path)
        assert any("功能开关 market_temperature" in f for f in findings)

    def test_reverse_finds_zombie(self, sem_index, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        doc = (
            "<!-- semantic-index:start -->\n"
            "| 语义 slug | 中文名 |\n"
            "|:--|:--|\n"
            "| `ghost_slug` | 幽灵条目 |\n"
            "<!-- semantic-index:end -->\n"
        )
        findings = sem_index.run_checks(doc, _valid_features(), _valid_registry(), tmp_path)
        assert any("`ghost_slug`" in f for f in findings)

    def test_merged_key_missing_from_registry(self, sem_index, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        doc = (
            "<!-- semantic-index:start -->\n"
            "| `candidate_compare` | 候选基金比较 |\n"
            "\n"
            "> **合并章代码标识符**：`ghost_sheet`（幽灵合并章，合并 `old_key`）。\n"
            "<!-- semantic-index:end -->\n"
        )
        findings = sem_index.run_checks(doc, _valid_features(), _valid_registry(), tmp_path)
        assert any("`ghost_sheet`" in f for f in findings)

    def test_missing_markers_short_circuits(self, sem_index, tmp_path):
        doc = "| `candidate_compare` | 候选基金比较 |\n"
        findings = sem_index.run_checks(doc, _valid_features(), _valid_registry(), tmp_path)
        assert len(findings) == 1
        assert "semantic-index" in findings[0]


# ═══ 真实仓库冒烟 ═══


class TestRealRepoSmoke:
    def test_current_repo_passes(self, sem_index):
        doc_text = sem_index._TECHNICAL_MD.read_text(encoding="utf-8")
        defaults_source = sem_index._CONFIG_DEFAULTS.read_text(encoding="utf-8")
        registry_source = sem_index._SECTION_REGISTRY_PY.read_text(encoding="utf-8")
        findings = sem_index.run_checks(doc_text, defaults_source, registry_source, sem_index._CODE_ROOT)
        assert findings == []


# ═══ 解析/收集的降级分支 ═══


class TestParseAndCollectDegrades:
    """畸形输入下的降级：缺标记回空、权威源形态不符回空、不可读文件跳过。"""

    def test_merged_keys_empty_without_markers(self, sem_index):
        assert sem_index.parse_merged_sheet_keys("> **合并章代码标识符**：`only_outside`（区间外）\n") == []

    def test_registry_value_not_list_returns_empty(self, sem_index):
        assert sem_index.registry_section_keys('_REPORT_SECTION_DEFAULT = {"key": "summary"}\n') == []

    def test_registry_skips_non_dict_elements(self, sem_index):
        source = '_REPORT_SECTION_DEFAULT = ["not_a_dict", {"key": "summary"}]\n'
        assert sem_index.registry_section_keys(source) == ["summary"]

    def test_keeps_original_text_when_source_unparsable(self, sem_index):
        source = "x = (\n# 未闭合括号：tokenize 中途报错\n"
        assert sem_index._code_without_comments(source) == source, "语法异常文件须降级为原始文本（不中断检查）"

    def test_collect_returns_empty_when_code_root_absent(self, sem_index, tmp_path):
        assert sem_index.collect_code_texts(tmp_path / "absent") == []

    def test_collect_skips_undecodable_file(self, sem_index, tmp_path):
        (tmp_path / "good.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "bad.py").write_bytes(b"\xff\xfe\x00broken")
        collected = sem_index.collect_code_texts(tmp_path)
        assert [path.name for path, _text in collected] == ["good.py"], "解码失败的文件整体跳过，不半途中断"


# ═══ CLI 入口 ═══


class TestCliEntry:
    """`main()`：参数解析 → 结论缓存 → 校验/回写 → 退出码，路径全部指向临时输入。"""

    @pytest.fixture(name="cli")
    def _cli(self, sem_index, monkeypatch, tmp_path):
        from types import SimpleNamespace

        doc = tmp_path / "technical.md"
        doc.write_text(_valid_doc(), encoding="utf-8")
        features = tmp_path / "features.py"
        features.write_text(_valid_features(), encoding="utf-8")
        registry = tmp_path / "report_section_registry.py"
        registry.write_text(_valid_registry(), encoding="utf-8")
        code_root = tmp_path / "python"
        code_root.mkdir()
        calls: dict[str, list] = {"report": [], "saved": [], "loaded": []}

        def _write_code(text: str) -> None:
            (code_root / "a.py").write_text(text, encoding="utf-8")

        monkeypatch.setattr(sem_index, "_TECHNICAL_MD", doc)
        monkeypatch.setattr(sem_index, "_FEATURES_PY", features)
        monkeypatch.setattr(sem_index, "_SECTION_REGISTRY_PY", registry)
        monkeypatch.setattr(sem_index, "_CODE_ROOT", code_root)
        monkeypatch.setattr(
            sem_index,
            "conclusion_cache_load",
            lambda key, scripts, inputs: calls["loaded"].append((key, len(scripts), len(inputs))),
        )
        monkeypatch.setattr(
            sem_index,
            "conclusion_cache_save",
            lambda key, _scripts, _inputs, payload: calls["saved"].append((key, payload)),
        )

        def _report(findings, ok_message, *, ci=False, fail_message=None, details=None):
            calls["report"].append({"findings": findings, "ci": ci, "ok": ok_message, "fail": fail_message})
            return 2 if findings else 0

        monkeypatch.setattr(sem_index, "report", _report)
        return SimpleNamespace(index=sem_index, calls=calls, code_root=code_root, doc=doc, write_code=_write_code)

    def test_clean_run_reports_ok_and_saves_conclusion(self, cli, monkeypatch):
        cli.write_code(
            'def build_candidate_compare(): pass\nd = {"cost_lots": False}\ndef build_position_relationship(): pass\n'
        )
        monkeypatch.setattr(sys, "argv", ["check-semantic-index.py"])
        with pytest.raises(SystemExit) as excinfo:
            cli.index.main()
        assert excinfo.value.code == 0
        assert cli.calls["report"][0]["findings"] == []
        assert cli.calls["report"][0]["ci"] is False
        assert cli.calls["saved"] == [("semantic_index", {"findings": []})], "无 --ci 不回放，但结论照常回写"
        assert cli.calls["loaded"] == [], "非 --ci 不读缓存"

    def test_findings_drive_exit_code_two(self, cli, monkeypatch):
        cli.write_code("x = 1\n")
        monkeypatch.setattr(sys, "argv", ["check-semantic-index.py"])
        with pytest.raises(SystemExit) as excinfo:
            cli.index.main()
        assert excinfo.value.code == 2
        findings = cli.calls["report"][0]["findings"]
        assert findings and all("无代码引用" in item for item in findings), "表内 slug 均无代码引用 → 僵尸条目"

    def test_ci_cache_hit_replays_without_reading_inputs(self, cli, monkeypatch, tmp_path):
        monkeypatch.setattr(cli.index, "conclusion_cache_load", lambda *_a, **_k: {"findings": ["缓存回放的旧结论"]})
        monkeypatch.setattr(cli.index, "_TECHNICAL_MD", tmp_path / "absent.md")
        monkeypatch.setattr(sys, "argv", ["check-semantic-index.py", "--ci"])
        with pytest.raises(SystemExit) as excinfo:
            cli.index.main()
        assert excinfo.value.code == 2
        assert cli.calls["report"][0]["findings"] == ["缓存回放的旧结论"]
        assert cli.calls["report"][0]["ci"] is True
        assert cli.calls["saved"] == [], "命中缓存不回写"

    def test_ci_cache_miss_falls_through_to_checks(self, cli, monkeypatch):
        cli.write_code(
            'def build_candidate_compare(): pass\nd = {"cost_lots": False}\ndef build_position_relationship(): pass\n'
        )
        monkeypatch.setattr(sys, "argv", ["check-semantic-index.py", "--ci"])
        with pytest.raises(SystemExit) as excinfo:
            cli.index.main()
        assert excinfo.value.code == 0
        assert len(cli.calls["loaded"]) == 1
        assert cli.calls["loaded"][0][0] == "semantic_index"
        assert len(cli.calls["saved"]) == 1

    def test_verbose_prints_parsed_keys(self, cli, monkeypatch, capsys):
        cli.write_code(
            'def build_candidate_compare(): pass\nd = {"cost_lots": False}\ndef build_position_relationship(): pass\n'
        )
        monkeypatch.setattr(sys, "argv", ["check-semantic-index.py", "-v"])
        with pytest.raises(SystemExit):
            cli.index.main()
        out = capsys.readouterr().out
        assert "表内 slug" in out and "candidate_compare" in out
        assert "功能开关" in out and "cost_lots" in out
        assert "合并章 sheet key" in out and "position_structure" in out
        assert "registry 章节 key" in out and "summary" in out

    def test_main_guard_exits_with_repo_verdict(self, monkeypatch, tmp_path):
        """`if __name__ == "__main__"` 入口：跑真实仓库输入，结论经 sys.exit 传出。"""
        monkeypatch.setenv("CHECK_CONCLUSION_CACHE_DIR", str(tmp_path))
        monkeypatch.setattr(sys, "argv", ["check-semantic-index.py"])
        if str(sem_index_path()) not in sys.path:
            sys.path.insert(0, str(sem_index_path()))
        with pytest.raises(SystemExit) as excinfo:
            runpy.run_path(str(sem_index_path() / "check-semantic-index.py"), run_name="__main__")
        assert excinfo.value.code == 0
