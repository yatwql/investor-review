"""调仓 What-if 产物的边角分支（`report/whatif_writer`）。

两处契约：
  - 匿名化装配边（`_anonymize_whatif_data` / `_whatif_anonymization_maps`）：模式解析缺省、
    off 恒等零开销、空身份面直接返回原对象；
  - 归档写出（`write_whatif_html`）：写失败一律**带目标路径**抛 OSError（便于定位权限/
    路径问题），而归档清理失败只告警——清理是尽力而为，不能把已成功的产物判成失败。
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from src.python.report import whatif_writer as writer

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _minimal_whatif() -> dict:
    return {
        "changes": [{"name": "华夏成长", "code": "000001", "action": "买入"}],
        "feasibility": [{"name": "华夏成长", "level": "ok"}],
        "cost": {"trade_cost": {"legs": [{"name": "华夏成长", "cost": 12.0}]}},
    }


class TestAnonymizationModeResolution:
    def test_mode_resolved_when_omitted(self, monkeypatch):
        """未显式传 mode → 走全局匿名模式单源（避免渲染点各自判定）。"""
        from src.python.config import anonymizer

        monkeypatch.setattr(anonymizer, "get_anonymization_mode", lambda: "off")

        assert writer._anonymize_whatif_data(_minimal_whatif()) == _minimal_whatif()

    def test_off_returns_same_object(self):
        """off 模式恒等返回原对象（零拷贝、零开销）。"""
        data = _minimal_whatif()

        assert writer._anonymize_whatif_data(data, mode="off") is data

    def test_summary_mode_leaves_fields_untouched(self):
        """summary 的折叠下沉到渲染层，字段层不得改动（折叠会造出缺失假行）。"""
        data = _minimal_whatif()

        assert writer._anonymize_whatif_data(data, mode="summary") is data

    def test_empty_identity_rows_returns_original(self):
        """无身份面（空 changes）→ 原样返回，不做无意义深拷贝。"""
        data = {"changes": [], "cost": {}}

        assert writer._anonymize_whatif_data(data, mode="code_display") is data

    def test_maps_resolve_mode_when_omitted(self, monkeypatch):
        from src.python.config import anonymizer

        monkeypatch.setattr(anonymizer, "get_anonymization_mode", lambda: "off")

        aliases, codes = writer._whatif_anonymization_maps(_minimal_whatif())

        assert (aliases, codes) == ({}, {})

    def test_derived_containers_without_changes_use_alias_map(self):
        """无 changes 主明细时派生容器只能吃别名映射（不回落到空映射）。"""
        data = {"feasibility": [{"name": "华夏成长", "code": "000001"}], "cost": {}}

        anonymized = writer._anonymize_whatif_data(data, mode="full_anonymous")

        assert anonymized["feasibility"][0]["name"] != "华夏成长", "派生容器须同样匿名"


class TestCostChartTrim:
    def test_none_when_labels_missing(self):
        assert writer._trim_whatif_cost_chart_data({"cost": {"chart": {"labels": []}}}) is None

    def test_none_for_none_payload(self):
        assert writer._trim_whatif_cost_chart_data(None) is None


class TestHtmlWriteFaults:
    def _data(self):
        return _minimal_whatif()

    def test_latest_write_failure_names_target_path(self, tmp_path, monkeypatch):
        """写最新 HTML 失败 → OSError 带目标路径（便于定位权限/路径）。"""

        def _raise(html, path):
            raise OSError("permission denied")

        monkeypatch.setattr(writer, "_write_html_atomic", _raise)

        with pytest.raises(OSError) as exc:
            writer.write_whatif_html(self._data(), str(tmp_path))

        assert "调仓最新 HTML 写入失败" in str(exc.value)
        assert str(tmp_path) in str(exc.value)

    def test_archive_dir_failure_names_target_path(self, tmp_path, monkeypatch):
        def _raise(*args, **kwargs):
            raise OSError("read-only file system")

        monkeypatch.setattr(writer, "_write_html_atomic", lambda html, path: None)
        monkeypatch.setattr(writer, "_ensure_reports_dir", lambda directory: None)
        monkeypatch.setattr(writer.os, "makedirs", _raise)

        with pytest.raises(OSError) as exc:
            writer.write_whatif_html(self._data(), str(tmp_path))

        assert "调仓归档目录创建失败" in str(exc.value)

    def test_archive_write_failure_names_target_path(self, tmp_path, monkeypatch):
        calls: list[str] = []
        real_write = writer._write_html_atomic

        def _fail_second(html, path):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("disk full")
            return real_write(html, path)

        monkeypatch.setattr(writer, "_write_html_atomic", _fail_second)

        with pytest.raises(OSError) as exc:
            writer.write_whatif_html(self._data(), str(tmp_path))

        assert "调仓归档 HTML 写入失败" in str(exc.value)

    def test_archive_cleanup_failure_only_warns(self, tmp_path, monkeypatch, caplog):
        """归档清理失败只告警：本次产物已落盘，不得判为失败。"""

        def _raise(output_dir):
            raise OSError("cleanup failed")

        monkeypatch.setattr(writer, "_cleanup_old_archives", _raise)

        result = writer.write_whatif_html(self._data(), str(tmp_path))

        assert os.path.isabs(result)
        assert "归档清理失败" in caplog.text


class TestWriteWhatsifReportBundle:
    def test_both_outputs_and_progress(self, tmp_path):
        reporter = MagicMock()
        with (
            patch.object(writer, "write_whatif_excel", return_value="/out/a.xlsx") as excel,
            patch.object(writer, "write_whatif_html", return_value="/out/a.html") as html,
        ):
            paths = writer.write_whatif_report(_minimal_whatif(), str(tmp_path), reporter=reporter)

        assert paths == {"excel": "/out/a.xlsx", "html": "/out/a.html"}
        reporter.info.assert_called_once()
        reporter.ok.assert_called_once()
        assert excel.call_args.args[1] == str(tmp_path)
        assert html.call_args.args[1] == str(tmp_path)

    def test_silent_without_reporter(self, tmp_path):
        with (
            patch.object(writer, "write_whatif_excel", return_value="/out/a.xlsx"),
            patch.object(writer, "write_whatif_html", return_value="/out/a.html"),
        ):
            assert writer.write_whatif_report(_minimal_whatif(), str(tmp_path))["html"] == "/out/a.html"
