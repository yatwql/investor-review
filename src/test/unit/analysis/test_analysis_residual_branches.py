"""analysis 域残余分支：港股代码归类为股票费率 / 目标权重非映射的入参校验。"""

from __future__ import annotations

import pytest

from src.python.analysis._fee_estimation import _STOCK_FEE_RATE, _classify_fund_type
from src.python.schemas.replay_schedule import _validate_target_weights

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]


class TestHongKongCodeClassification:
    def test_five_digit_code_classified_as_stock(self):
        # 名称里没有基金特征词，落入代码特征识别；5 位纯数字即港股通标的
        assert _classify_fund_type("腾讯控股", "00700") == ("stock", _STOCK_FEE_RATE)


class TestTargetWeightsValidation:
    def test_non_mapping_target_weights_rejected(self):
        with pytest.raises(ValueError, match="target_weights"):
            _validate_target_weights([0.5, 0.5])
