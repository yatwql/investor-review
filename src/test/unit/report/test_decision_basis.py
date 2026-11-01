"""判断依据章内块（形态 A）数据契约与双端同源测试。

覆盖：骨架空契约字段（available=false 规范空契约 + 五节键先立）、开关关闭
仅返回 enabled=False（回滚通道）、零参数签名（零 LLM 依赖的结构断言）、
双端同源（同一份 decision_basis_data 在 HTML/Excel 渲染出的标题与 summary
文案一致，防一处写死）。全部离线，不触网。
"""

from __future__ import annotations

import inspect

import pytest

from src.python.config.features import reset_feature_flags, set_feature_enabled
from src.python.report.decision_basis import (
    BLOCK_TITLE,
    FEATURE_FLAG,
    build_decision_basis_data,
    is_decision_basis_enabled,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


@pytest.fixture(autouse=True)
def _reset_features():
    reset_feature_flags()
    yield
    reset_feature_flags()


class TestSkeletonContract:
    """骨架期：规范空契约。"""

    def test_empty_contract_shape(self):
        d = build_decision_basis_data()
        assert d["enabled"] is True  # 缺省开（纯事实块）
        assert d["available"] is False  # 骨架期未接数据源
        assert d["reason"]  # 不可用原因非空（Data States 口径前缀）
        assert d["title"] == BLOCK_TITLE == "判断依据"
        assert BLOCK_TITLE in d["summary"]  # summary 自带块名（双端同源文案）
        for key in ("confidence", "risk_budget", "discipline", "settlement"):
            assert isinstance(d[key], dict)
            assert d[key] == {}  # 字段先立：后续轮次逐节填充
        assert d["signals"] == []

    def test_flag_off_returns_disabled_only(self):
        set_feature_enabled(FEATURE_FLAG, False)
        assert is_decision_basis_enabled() is False
        assert build_decision_basis_data() == {"enabled": False}

    def test_zero_parameter_signature(self):
        """零 LLM 依赖的结构断言：装配函数无参数（不接上下文/模型/LLM 客户端）。"""
        assert list(inspect.signature(build_decision_basis_data).parameters) == []


class TestBothEndsSameSource:
    """双端同源：同一份契约在 HTML/Excel 渲染出的标题与 summary 一致。"""

    def test_title_and_summary_in_both_channels(self):
        from openpyxl import Workbook

        from src.python.report.action_sheet import write_action_sheet
        from src.test.unit.report.test_action_html import _action_data, _render

        data = build_decision_basis_data()
        # HTML 端：#decision-basis 块内含标题与 summary
        block = _render(_action_data(), decision_basis_data=data).find(id="decision-basis")
        assert block is not None
        html_text = block.get_text()
        # Excel 端：顶部子块含同一标题与 summary
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        write_action_sheet(ws, _action_data(), decision_basis_data=data)
        excel_text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
        for text in (html_text, excel_text):
            assert data["title"] in text
            assert data["summary"] in text
            assert data["reason"] in text  # 空态行「数据不可用：<原因>」两端一致
