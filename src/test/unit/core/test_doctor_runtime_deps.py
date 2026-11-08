"""启动前置检查：解释器能否支撑出报告（缺重依赖即拦截，而非跑到中途崩）。

本文件锁定契约：解释器缺重依赖时，TUI/Web 入口**启动即拦截**，错误文本须给出
缺失包名、当前解释器路径与修复命令（错误即 UX）；自检报告同时给出「关键依赖」行。
若放行，失败点会深到 full 报告的数据准备阶段（``ModuleNotFoundError``）。
"""

from __future__ import annotations

import sys

import pytest

from src.python.core import doctor

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestInterpreterPreflight:
    def test_returns_none_when_all_required_packages_importable(self, monkeypatch):
        monkeypatch.setattr(doctor, "missing_runtime_packages", lambda: [])
        assert doctor.interpreter_preflight_error() is None

    def test_error_names_missing_package_interpreter_and_fix(self, monkeypatch):
        """错误文本三要素：缺什么、当前解释器、怎么修（错误即 UX）。"""
        monkeypatch.setattr(doctor, "missing_runtime_packages", lambda: ["pandas"])
        message = doctor.interpreter_preflight_error()

        assert message is not None
        assert "pandas" in message
        assert sys.executable in message
        assert "pip install -r requirements.txt" in message
        assert "scripts/launch.sh" in message

    def test_missing_runtime_packages_reflects_find_spec(self, monkeypatch):
        """真实探测路径：find_spec 返回 None 的包计入缺失。"""
        monkeypatch.setattr(doctor, "REQUIRED_RUNTIME_PACKAGES", {"definitely_absent_pkg_xyz": "探针"})
        assert doctor.missing_runtime_packages() == ["definitely_absent_pkg_xyz"]


class TestRuntimeDepsCheckItem:
    def test_ok_item_when_dependencies_present(self, monkeypatch):
        monkeypatch.setattr(doctor, "missing_runtime_packages", lambda: [])
        item = doctor._check_runtime_deps()
        assert item["ok"] is True
        assert item["group"] == doctor.GROUP_ENV

    def test_failed_item_carries_hint(self, monkeypatch):
        monkeypatch.setattr(doctor, "missing_runtime_packages", lambda: ["numpy"])
        item = doctor._check_runtime_deps()
        assert item["ok"] is False
        assert "numpy" in item["message"]
        assert ".venv/bin/python -m pip install" in item["hint"]

    def test_doctor_report_includes_runtime_deps_row(self):
        """自检报告须带上该行（环境组），缺依赖时才可能被用户看到。"""
        labels = [r["label"] for r in doctor.run_doctor_checks(include_network=False)]
        assert "关键依赖" in labels
