"""适配器注册表/自检的异常与未登记分支（source_adapter.py）。

测试场景：
  1. ``typing.Optional`` 形式的注解同样被识别为可选/数值
  2. 数据域未登记时标准字段为空、合成样本为空
  3. 自检遇到 transform_data 返回非 dict / 输出含非标准字段时逐项报告
  4. 适配器模块导入失败只告警、不中断注册表加载
  5. 单个适配器自检抛异常时只落在该条报告里
"""

from __future__ import annotations

import logging
import typing
from typing import Any, ClassVar

import pytest

from src.python.fetcher import source_adapter as sa
from src.python.schemas.datasource_fields import DOMAIN_QUOTE

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher]

#: 未在 DOMAIN_RECORDS 登记的数据域名
_UNREGISTERED_DOMAIN = "no_such_domain"


class _QuoteAdapter(sa.SourceAdapter):
    """最小可用适配器（注册到报价域），供注册表分支复用。"""

    domain: ClassVar[str] = DOMAIN_QUOTE
    source_id: ClassVar[str] = "branch_probe"
    display_name: ClassVar[str] = "分支探针源"

    def extract_data(self, query: dict[str, Any]) -> Any:
        return None

    def transform_data(self, raw: Any, source: str = "") -> dict[str, Any] | None:
        return super().transform_data(raw, source)


class TestTypeAnnotationDetection:
    """注解识别：``types.UnionType`` 与 ``typing.Union`` 两条路径同义。"""

    def test_optional_typing_union_detected(self):
        """``Optional[float]``（typing.Union 形态）判为可选数值。"""
        assert sa._is_optional(typing.Optional[float]) is True
        assert sa._is_numeric(typing.Optional[float]) is True

    def test_plain_str_is_neither_numeric_nor_optional(self):
        """``str`` 既非数值也非可选（对照，确认上例不是恒真）。"""
        assert sa._is_optional(str) is False
        assert sa._is_numeric(str) is False


class TestUnregisteredDomain:
    """数据域未登记：标准字段与合成样本均为空。"""

    def test_standard_fields_and_sample_raw_empty(self):
        """未登记域 → standard_record 为 None，标准字段/样本退化为空。"""

        class _Adapter(_QuoteAdapter):
            domain: ClassVar[str] = _UNREGISTERED_DOMAIN
            source_id: ClassVar[str] = "unregistered"

        adapter = _Adapter()
        assert adapter.standard_record() is None
        assert adapter.standard_fields() == ()
        assert adapter._sample_raw() == {}


class TestSelfTestProbeBranches:
    """自检对 transform_data 输出的形状校验。"""

    def test_probe_not_mapping_reported(self):
        """transform_data 返回 None → 报告「未返回 dict」。"""

        class _Adapter(_QuoteAdapter):
            source_id: ClassVar[str] = "returns_none"

            def transform_data(self, raw: Any, source: str = "") -> dict[str, Any] | None:
                return None

        problems = _Adapter().self_test()
        assert any("未返回 dict" in p for p in problems), problems

    def test_probe_extra_fields_reported(self):
        """transform_data 多输出非标准字段 → 报告多余字段。"""

        class _Adapter(_QuoteAdapter):
            source_id: ClassVar[str] = "extra_field"

            def transform_data(self, raw: Any, source: str = "") -> dict[str, Any] | None:
                out = super().transform_data(raw, source) or {}
                out["额外字段"] = 1
                return out

        problems = _Adapter().self_test()
        assert any("非标准字段" in p for p in problems), problems


class TestAdapterLoadingAndSurvey:
    """惰性加载与巡检的异常收口。"""

    def test_module_import_failure_only_warns(self, monkeypatch, caplog):
        """适配器模块导入失败 → 告警一条，注册表加载标记照常置位。"""
        monkeypatch.setattr(sa, "ADAPTER_MODULES", ("src.python.fetcher.no_such_adapter_module",))
        monkeypatch.setattr(sa, "_ADAPTERS_LOADED", False)
        with caplog.at_level(logging.WARNING):
            reports = sa.survey_adapters()
        assert isinstance(reports, list)
        assert any("导入失败" in rec.message for rec in caplog.records), [r.message for r in caplog.records]
        assert sa._ADAPTERS_LOADED is True

    def test_self_test_exception_is_captured_in_report(self):
        """某个适配器 self_test 抛异常 → 该项报告 ok=False 且带异常类型。"""

        class _Boom(_QuoteAdapter):
            source_id: ClassVar[str] = "boom_self_test"
            display_name: ClassVar[str] = "自检爆炸源"

            def self_test(self) -> list[str]:
                raise RuntimeError("自检崩了")

        snapshot = sa.snapshot_adapters()
        try:
            sa.register_adapter(_Boom())
            reports = sa.survey_adapters()
        finally:
            sa.restore_adapters(snapshot)
        row = next(r for r in reports if r["source_id"] == "boom_self_test")
        assert row["ok"] is False
        assert "RuntimeError" in row["message"]
