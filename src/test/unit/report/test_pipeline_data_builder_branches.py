"""pipeline_data 构建器的注册/校验分支（`report/pipeline_data_builder`）。

契约面：未知键必须告警并自注册（否则报告消费端静默丢字段），类型不符只告警不抛
（生产容错），`merge_pipeline_data` 的四条合并路径各有明确返回值。本文件补齐
`build` / `build_prep` / `_validate_diff` / `merge_pipeline_data` 的未覆盖分支。
"""

from __future__ import annotations

import logging

import pytest

from src.python.report import pipeline_data_builder as pdb

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _known_keys():
    """已知键集合的快照与恢复（`build`/`merge` 会往全局集合里补注册键）。"""
    return set(pdb._PIPELINE_DATA_KNOWN_KEYS), set(pdb._PREP_KNOWN_KEYS)


@pytest.fixture(autouse=True)
def _restore_known_keys():
    pipeline_snapshot, prep_snapshot = _known_keys()
    yield
    pdb._PIPELINE_DATA_KNOWN_KEYS.clear()
    pdb._PIPELINE_DATA_KNOWN_KEYS.update(pipeline_snapshot)
    pdb._PREP_KNOWN_KEYS.clear()
    pdb._PREP_KNOWN_KEYS.update(prep_snapshot)


class TestBuildRegistration:
    def test_unregistered_extra_key_warns_and_registers(self, caplog):
        """未登记键经 extra 注入 → 告警 + 自动补注册（后续同类注入不再刷告警）。"""
        with caplog.at_level(logging.WARNING, logger="invest"):
            pdb.build(probe_unregistered_key={"v": 1})

        assert "probe_unregistered_key" in caplog.text
        assert "probe_unregistered_key" in pdb._PIPELINE_DATA_KNOWN_KEYS

    def test_registered_extra_key_is_silent(self, caplog):
        key = next(iter(pdb._PIPELINE_DATA_KNOWN_KEYS))
        with caplog.at_level(logging.WARNING, logger="invest"):
            pdb.build(**{key: {"v": 1}})

        assert "未注册键" not in caplog.text

    def test_validate_keys_warns_on_unknown_key(self, caplog):
        """`_validate_keys` 是最后一道闸：集合外的键必须告警（提示去附录 H 注册）。"""
        with caplog.at_level(logging.WARNING, logger="invest"):
            pdb._validate_keys({"ghost_key": 1}, {"known_key"}, "probe")

        assert "ghost_key" in caplog.text
        assert "附录 H" in caplog.text


class TestBuildTypeCheck:
    def test_wrong_type_only_warns(self, caplog):
        """类型不符只告警不抛异常（生产容错：内存形状异常不应中断报告）。"""
        key, expected = next(iter(pdb._PIPELINE_DATA_TYPE_MAP.items()))
        bad_value = object() if not isinstance(None, expected) else object()

        with caplog.at_level(logging.WARNING, logger="invest"):
            result = pdb.build(**{key: bad_value})

        assert result[key] is bad_value, "异常值原样透传，不做静默改写"
        assert "[checkpoint] pipeline_data." in caplog.text


class TestValidateDiff:
    def test_diff_subkeys_are_type_checked(self, caplog):
        """diff 子键深层校验：类型不符逐一告警，但整体 diff 仍原样返回。"""
        diff = {"is_first_check": "yes", "added": "not-a-list", "unknown_subkey": 1}
        with caplog.at_level(logging.WARNING, logger="invest"):
            result = pdb.build(diff=diff)

        assert result["diff"] == diff
        assert "diff.is_first_check" in caplog.text
        assert "diff.added" in caplog.text

    def test_well_typed_diff_is_silent(self, caplog):
        diff = {"is_first_check": True, "days_since_last_report": 3, "added": [], "removed": []}
        with caplog.at_level(logging.WARNING, logger="invest"):
            pdb.build(diff=diff)

        assert "diff." not in caplog.text


class TestBuildPrep:
    def test_defaults_and_extra_key(self):
        """缺省值齐备（列表/字典不为 None），extra 键合并并登记。"""
        prep = pdb.build_prep(probe_prep_extra={"v": 1})

        assert prep["details"] == []
        assert prep["categories"] == {}
        assert prep["a_indices"] == {}
        assert prep["penetrated_assets"] == []
        assert prep["output_dir"] == "reports"
        assert prep["probe_prep_extra"] == {"v": 1}
        assert "probe_prep_extra" in pdb._PREP_KNOWN_KEYS

    def test_today_str_defaults_to_current_date(self):
        prep = pdb.build_prep()

        assert prep["today_str"], "缺省日期必须填充，否则模板会渲染空日期"

    def test_explicit_values_pass_through(self):
        prep = pdb.build_prep(
            total_mv=1000.0,
            categories={"股票": 2},
            today_str="2024-01-05",
            news_top_count=50,
        )

        assert prep["total_mv"] == pytest.approx(1000.0)
        assert prep["categories"] == {"股票": 2}
        assert prep["today_str"] == "2024-01-05"
        assert prep["news_top_count"] == 50

    def test_wrong_type_only_warns(self, caplog):
        with caplog.at_level(logging.WARNING, logger="invest"):
            prep = pdb.build_prep(total_mv="not-a-number")

        assert prep["total_mv"] == "not-a-number"
        assert "prep.total_mv" in caplog.text


class TestMergePipelineData:
    def test_none_without_extra_returns_none(self):
        assert pdb.merge_pipeline_data(None) is None

    def test_none_base_builds_from_extra(self):
        merged = pdb.merge_pipeline_data(None, data_degradation=[{"src": "x"}])

        assert merged["data_degradation"] == [{"src": "x"}]
        assert merged["diff"] is None

    def test_no_extra_returns_base_unchanged(self):
        base = {"diff": None, "data_degradation": []}

        assert pdb.merge_pipeline_data(base) is base

    def test_extra_overrides_existing_key(self, caplog):
        """覆盖已有键走 DEBUG（不是「未注册键」告警），值以新值为准。"""
        base = {"diff": None, "data_degradation": [], "snapshot_diff_data": {"old": 1}}

        with caplog.at_level(logging.DEBUG, logger="invest"):
            merged = pdb.merge_pipeline_data(base, snapshot_diff_data={"new": 2})

        assert merged["snapshot_diff_data"] == {"new": 2}
        assert base["snapshot_diff_data"] == {"old": 1}, "不得就地修改调用方的 dict"

    def test_unregistered_merge_key_warns_and_registers(self, caplog):
        base = {"diff": None, "data_degradation": []}

        with caplog.at_level(logging.WARNING, logger="invest"):
            merged = pdb.merge_pipeline_data(base, probe_merge_key=1)

        assert merged["probe_merge_key"] == 1
        assert "probe_merge_key" in caplog.text
        assert "probe_merge_key" in pdb._PIPELINE_DATA_KNOWN_KEYS
