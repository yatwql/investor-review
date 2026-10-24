"""code_utils 指数代码与符号映射判定函数单元测试。

覆盖：is_index_code / is_us_index_code / get_index_exchange_prefix /
      is_otc_fund_by_name / is_a_share_stock / is_a_share_code（00 重叠区场外基金辅助判定与 A 股代码判定）/
      to_fmp_symbol（A 股代码 → FMP 风格符号）/
      is_six_digit_code / is_letter_based_code（代码形态原语，含内联判定收编回归守卫）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.python.core.code_utils import (
    is_a_share_code,
    is_letter_based_code,
    is_six_digit_code,
    is_a_share_stock,
    is_index_code,
    is_otc_fund_by_name,
    is_us_index_code,
    otc_redemption_days_default,
)
from src.python.core.code_symbols import (
    get_index_exchange_prefix,
    to_fmp_symbol,
    get_exchange_category,
    to_exchange_symbol,
)
from src.python.core.constants import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestIsIndexCode:
    """is_index_code 判定测试。"""

    def test_a_share_index_with_prefix_sh(self) -> None:
        """sh000300（沪深300）应识别为指数。"""
        assert is_index_code("sh000300") is True

    def test_a_share_index_with_prefix_sz(self) -> None:
        """sz399001（深证成指）应识别为指数。"""
        assert is_index_code("sz399001") is True

    def test_a_share_index_raw_no_prefix(self) -> None:
        """000300（无前缀）也应识别为指数。"""
        assert is_index_code("000300") is True

    def test_a_share_index_932_prefix(self) -> None:
        """932xxx（中证指数系列）应识别为指数。"""
        assert is_index_code("932100") is True

    def test_stock_code_not_index(self) -> None:
        """600900（A 股股票代码）不应识别为指数。"""
        assert is_index_code("600900") is False

    def test_etf_fund_code_not_index(self) -> None:
        """510050（上证50 ETF）不应识别为指数。"""
        assert is_index_code("510050") is False

    def test_hk_stock_code_not_index(self) -> None:
        """00700（港股）不应识别为指数。"""
        assert is_index_code("00700") is False

    def test_us_index_gb_inx(self) -> None:
        """gb_inx（标普500）应识别为指数。"""
        assert is_index_code("gb_inx") is True

    def test_us_index_gb_dji(self) -> None:
        """gb_dji（道琼斯）应识别为指数。"""
        assert is_index_code("gb_dji") is True

    def test_empty_code(self) -> None:
        """空字符串不应识别为指数。"""
        assert is_index_code("") is False


class TestIsUsIndexCode:
    """is_us_index_code 判定测试。"""

    def test_us_index_true(self) -> None:
        """gb_inx 应识别为美股指数。"""
        assert is_us_index_code("gb_inx") is True

    def test_a_share_index_false(self) -> None:
        """sh000300 不应识别为美股指数。"""
        assert is_us_index_code("sh000300") is False

    def test_empty_code(self) -> None:
        """空字符串不应识别为美股指数。"""
        assert is_us_index_code("") is False


class TestGetIndexExchangePrefix:
    """get_index_exchange_prefix 交易所前缀获取测试。"""

    def test_sh_prefix(self) -> None:
        """sh000300 返回 sh。"""
        assert get_index_exchange_prefix("sh000300") == "sh"

    def test_sz_prefix(self) -> None:
        """sz399001 返回 sz。"""
        assert get_index_exchange_prefix("sz399001") == "sz"

    def test_us_index_no_prefix(self) -> None:
        """gb_inx（美股指数）返回空字符串。"""
        assert get_index_exchange_prefix("gb_inx") == ""

    def test_raw_code_no_prefix(self) -> None:
        """000300（无前缀）返回空字符串。"""
        assert get_index_exchange_prefix("000300") == ""

    def test_empty_code(self) -> None:
        """空字符串返回空字符串。"""
        assert get_index_exchange_prefix("") == ""


class TestIsOtcFundByName:
    """is_otc_fund_by_name 00 重叠区场外基金辅助判定测试。

    覆盖 00 前缀 + 基金特征关键词（含债券/指数/股票等细分）→ 判定为场外基金；
    00 前缀 + 股票名（无基金特征词）或非 00 前缀 → 判定为非场外基金。
    """

    def test_bond_fund_with_bare_bond_keyword(self) -> None:
        """00 前缀 + 名称含"债券"（无细分词）→ 场外基金（如 000311 景顺长城景颐双利债券A）。"""
        assert is_otc_fund_by_name("景顺长城景颐双利债券A", "000311") is True

    def test_index_fund_with_index_keyword(self) -> None:
        """00 前缀 + 名称含"指数" → 场外基金（如 001552 天弘中证证券保险指数A）。"""
        assert is_otc_fund_by_name("天弘中证证券保险指数A", "001552") is True

    def test_stock_fund_with_stock_keyword(self) -> None:
        """00 前缀 + 名称含"股票" → 场外基金（如 004851 广发医疗保健股票A）。"""
        assert is_otc_fund_by_name("广发医疗保健股票A", "004851") is True

    def test_a_share_stock_00_prefix_not_fund(self) -> None:
        """00 前缀 + 深市股票名（无基金特征词）→ 非场外基金（如 000651 格力电器）。"""
        assert is_otc_fund_by_name("格力电器", "000651") is False

    def test_non_00_prefix_returns_false(self) -> None:
        """非 00 前缀（A 股/场内基金/港股）→ 非场外基金，与名称无关。"""
        assert is_otc_fund_by_name("招商中证白酒指数A", "161725") is False
        assert is_otc_fund_by_name("沪深300ETF", "510300") is False
        assert is_otc_fund_by_name("腾讯控股", "00700") is False

    def test_empty_name_or_code_returns_false(self) -> None:
        """名称或代码缺失 → 非场外基金（防御性，不抛异常）。"""
        assert is_otc_fund_by_name("", "000311") is False
        assert is_otc_fund_by_name("景顺长城景颐双利债券A", "") is False


class TestIsAShareStock:
    """is_a_share_stock 持仓「按 A 股个股处理」判定（排除 00 重叠区场外基金）。"""

    def test_plain_a_share_is_stock(self) -> None:
        """普通 A 股（含深市 00 前缀股票、沪市、创业板、北交所）→ True。"""
        assert is_a_share_stock("长江电力", "600900") is True
        assert is_a_share_stock("平安银行", "000001") is True
        assert is_a_share_stock("宁德时代", "300750") is True
        assert is_a_share_stock("宇晶股份", "002943") is True

    def test_otc_fund_in_overlap_zone_is_not_stock(self) -> None:
        """00 重叠区场外基金（名称命中基金特征词）→ False。

        回归：002943 既是深市股票「宇晶股份」也是场外基金「广发多因子灵活配置混合」，
        各域路由不得按个股处理该持仓。
        """
        assert is_a_share_stock("广发多因子灵活配置混合", "002943") is False
        assert is_a_share_stock("景顺长城景颐双利债券A", "000311") is False

    def test_non_a_share_code_is_not_stock(self) -> None:
        """非 A 股代码（场内 ETF/场外基金/港股）→ False。"""
        assert is_a_share_stock("招商中证电池主题ETF", "561910") is False
        assert is_a_share_stock("建信高端装备股票A", "011506") is False
        assert is_a_share_stock("腾讯控股", "00700") is False


class TestOtcRedemptionDaysDefault:
    """otc_redemption_days_default 场外基金赎回天数类型默认档（非实测）。"""

    def test_money_fund_tier1(self) -> None:
        assert otc_redemption_days_default("天弘余额宝货币", "000198") == 1

    def test_short_bond_tier1_before_pure_bond(self) -> None:
        """短债先于纯债档命中（短债名称同时含债类关键词）。"""
        assert otc_redemption_days_default("某某短债债券A", "000012") == 1

    def test_pure_bond_tier2(self) -> None:
        assert otc_redemption_days_default("某某纯债债券A", "000013") == 2

    def test_qdii_tier7(self) -> None:
        assert otc_redemption_days_default("某某纳斯达克QDII", "000041") == 7

    def test_generic_equity_otc_tier3(self) -> None:
        """主动权益/混合/指数等场外基金 → T+3 通用档。"""
        assert otc_redemption_days_default("华夏成长混合", "000001") == 3
        assert otc_redemption_days_default("招商中证白酒指数A", "161725") == 3

    def test_unrecognized_returns_none(self) -> None:
        """非场外基金（A 股股票/空名称）→ None，调用方保持「需手动确认」降级。"""
        assert otc_redemption_days_default("格力电器", "000651") is None
        assert otc_redemption_days_default("", "") is None


class TestIsAShareCode:
    """is_a_share_code A 股代码判定测试。"""

    def test_normal_sh(self) -> None:
        """sh 前缀 A 股代码 → True。"""
        assert is_a_share_code("sh600000") is True

    def test_normal_sz(self) -> None:
        """sz 前缀 A 股代码 → True。"""
        assert is_a_share_code("sz000001") is True

    def test_normal_bj(self) -> None:
        """bj 前缀 A 股代码 → True。"""
        assert is_a_share_code("bj830001") is True

    def test_raw_six_digit(self) -> None:
        """纯 6 位数字 → True。"""
        assert is_a_share_code("600900") is True

    def test_us_stock(self) -> None:
        """美股字母代码 → False。"""
        assert is_a_share_code("AAPL") is False

    def test_us_stock_numeric(self) -> None:
        """美股数字代码（无前缀非 6 位）→ False。"""
        assert is_a_share_code("BRK.B") is False

    def test_hk_stock(self) -> None:
        """港股 5 位 → False。"""
        assert is_a_share_code("00700") is False

    def test_empty(self) -> None:
        """空字符串 → False。"""
        assert is_a_share_code("") is False

    def test_whitespace(self) -> None:
        """空格 → False。"""
        assert is_a_share_code("  ") is False

    def test_prefix_is_a_share(self) -> None:
        """带 sh/sz/bj 前缀的 6 位码 → True。"""
        for prefix in ("sh", "sz", "bj"):
            assert is_a_share_code(f"{prefix}600000") is True

    def test_prefix_not_a_share(self) -> None:
        """带 sh/sz/bj 前缀但非 6 位 → False。"""
        assert is_a_share_code("sh60000") is False


class TestFmpSymbol:
    """to_fmp_symbol —— A 股 6 位代码 → FMP 风格符号（多数据源共用的符号口径）。"""

    def test_shanghai(self):
        """沪市 600/688 → .SS。"""
        assert to_fmp_symbol("600519") == "600519.SS"
        assert to_fmp_symbol("688981") == "688981.SS"

    def test_shenzhen(self):
        """深市 000/300 → .SZ。"""
        assert to_fmp_symbol("000001") == "000001.SZ"
        assert to_fmp_symbol("300750") == "300750.SZ"

    def test_beijing(self):
        """北交所 83/92 → .BJ。"""
        assert to_fmp_symbol("830799") == "830799.BJ"
        assert to_fmp_symbol("920002") == "920002.BJ"

    def test_already_symbolic(self):
        """已带后缀的输入原样返回。"""
        assert to_fmp_symbol("600519.SS") == "600519.SS"

    def test_non_a_share_returns_empty(self):
        """非 A 股代码返回空串。"""
        assert to_fmp_symbol("7203") == ""
        assert to_fmp_symbol("AAPL") == ""
        assert to_fmp_symbol("") == ""
        assert to_fmp_symbol("12345") == ""


class TestToExchangeSymbolAndCategory:
    """场内 ETF 交易所后缀与 cninfo 栏目判定（收敛到 code_utils 单点维护）。"""

    def test_to_exchange_symbol_fund_segments(self):
        assert to_exchange_symbol("510300") == "510300.SH"  # 沪市场内 ETF
        assert to_exchange_symbol("159915") == "159915.SZ"  # 深市场内 ETF/LOF
        # 非 6 位/非数字/带后缀的输入不落该判定
        assert to_exchange_symbol("600519") is None
        assert to_exchange_symbol("51030") is None
        assert to_exchange_symbol("") is None

    def test_to_exchange_symbol_symbol_input_passthrough(self):
        # 带后缀视为已是符号格式，原样返回
        assert to_exchange_symbol("510300.SH") == "510300.SH"
        assert to_exchange_symbol("159915.SZ") == "159915.SZ"

    def test_get_exchange_category(self):
        assert get_exchange_category("600519") == "sse"
        assert get_exchange_category("430047") == "third"
        assert get_exchange_category("830799") == "third"
        assert get_exchange_category("000001") == "szse"
        assert get_exchange_category("300750") == "szse"


class TestIsSixDigitCode:
    """6 位纯数字代码形态原语（配置键/申购行校验与基金链路兜底共用）。"""

    def test_plain_six_digits(self):
        assert is_six_digit_code("011506") is True
        assert is_six_digit_code("600036") is True

    def test_prefixed_six_digits(self):
        assert is_six_digit_code("sh600036") is True
        assert is_six_digit_code("sz161725") is True

    def test_five_digit_hk_code_rejected(self):
        assert is_six_digit_code("00700") is False

    def test_seven_digits_rejected(self):
        assert is_six_digit_code("1234567") is False

    def test_letter_code_rejected(self):
        assert is_six_digit_code("AAPL") is False

    def test_empty_rejected(self):
        assert is_six_digit_code("") is False


class TestIsLetterBasedCode:
    """字母为主代码形态原语（外盘字母/混合代码判定）。"""

    def test_pure_letters(self):
        assert is_letter_based_code("AAPL") is True

    def test_mixed_alnum(self):
        assert is_letter_based_code("BRK1") is True

    def test_pure_digits_rejected(self):
        assert is_letter_based_code("600036") is False
        assert is_letter_based_code("00700") is False

    def test_illegal_chars_rejected(self):
        assert is_letter_based_code("BRK.B") is False

    def test_empty_rejected(self):
        assert is_letter_based_code("") is False
        assert is_letter_based_code(None) is False


class TestSixDigitJudgementCentralized:
    """回归守卫：生产模块不得再内联 6 位纯数字判定（判定收敛 `is_six_digit_code` 单源）。"""

    _INLINE_PATTERN = re.compile(r"len\([a-z_]+\) == 6 and [a-z_]+\.isdigit\(\)")
    #: 允许出现该判定的模块：`code_utils.py`（is_six_digit_code 的唯一入口）与
    #: `code_symbols.py`（strip_to_digits 是其底层原语——上层判据反过来调用它，
    #: 调用上层判据会互相递归）
    _ALLOWED = {"code_utils.py", "code_symbols.py"}

    def test_no_inline_six_digit_checks_outside_code_utils(self):
        offenders = []
        src_root = Path(PROJECT_ROOT) / "src" / "python"
        for path in src_root.rglob("*.py"):
            if path.name in self._ALLOWED or "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            if self._INLINE_PATTERN.search(text):
                offenders.append(str(path.relative_to(PROJECT_ROOT)))
        assert offenders == [], f"内联 6 位数字判定应改用 is_six_digit_code()：{offenders}"


class TestStripExchangePrefix:
    """strip_exchange_prefix：交易所前缀剥离（大小写不敏感、不校验位数）。"""

    def test_lowercase_prefix_stripped(self):
        from src.python.core.code_symbols import strip_exchange_prefix

        assert strip_exchange_prefix("sh600519") == "600519"
        assert strip_exchange_prefix("sz000001") == "000001"
        assert strip_exchange_prefix("bj430047") == "430047"

    def test_uppercase_prefix_stripped(self):
        from src.python.core.code_symbols import strip_exchange_prefix

        assert strip_exchange_prefix("SH600519") == "600519"
        assert strip_exchange_prefix("Sz000001") == "000001"
        assert strip_exchange_prefix("BJ430047") == "430047"

    def test_no_prefix_returned_as_is(self):
        from src.python.core.code_symbols import strip_exchange_prefix

        assert strip_exchange_prefix("600519") == "600519"
        assert strip_exchange_prefix("00700") == "00700"

    def test_empty_and_none_safe(self):
        from src.python.core.code_symbols import strip_exchange_prefix

        assert strip_exchange_prefix("") == ""
        assert strip_exchange_prefix(None) == ""
        assert strip_exchange_prefix("   ") == ""

    def test_surrounding_whitespace_trimmed(self):
        from src.python.core.code_symbols import strip_exchange_prefix

        assert strip_exchange_prefix("  sh600519  ") == "600519"

    def test_non_six_digit_kept_for_caller_judgement(self):
        """只剥前缀不校验形态：5 位港股码 / 带 .0 尾原样交给调用方判定。"""
        from src.python.core.code_symbols import strip_exchange_prefix

        assert strip_exchange_prefix("sh00700") == "00700"
        assert strip_exchange_prefix("sz000001.0") == "000001.0"

    def test_not_a_real_prefix_untouched(self):
        from src.python.core.code_symbols import strip_exchange_prefix

        assert strip_exchange_prefix("hk00700") == "hk00700"


class TestExchangePrefixCentralized:
    """回归守卫：交易所前缀元组只允许在 code_utils 单点定义。

    各模块自建 ("sh", "sz", "bj") 元组会在新增交易所前缀时漏改一处，
    导致同一代码在两处判定口径分叉——须改用 strip_exchange_prefix()。
    """

    _PREFIX_TUPLE = re.compile(r"\(\s*[\"']sh[\"']\s*,\s*[\"']sz[\"']|[\"']sz[\"']\s*,\s*[\"']bj[\"']")

    def test_no_module_self_built_prefix_tuple(self):
        offenders = []
        src_root = Path(PROJECT_ROOT) / "src" / "python"
        for path in src_root.rglob("*.py"):
            if path.name in {"code_utils.py", "code_symbols.py"} or "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            if self._PREFIX_TUPLE.search(text):
                offenders.append(str(path.relative_to(PROJECT_ROOT)))
        assert offenders == [], f"交易所前缀元组应复用 code_utils 的单点定义：{offenders}"

    def test_constant_is_single_source(self):
        """判定用常量与剥离函数读同一份前缀表（新增前缀只改一处）。

        派生量拆分后真值只在 `code_symbols.py`；`code_utils.py` 不再转出该常量，
        避免同一符号出现第二条导入路径。
        """
        from src.python.core import code_symbols, code_utils

        assert code_symbols.EXCHANGE_PREFIXES == ("sh", "sz", "bj")
        assert not hasattr(code_utils, "EXCHANGE_PREFIXES")
        for prefix in code_symbols.EXCHANGE_PREFIXES:
            assert code_symbols.strip_exchange_prefix(f"{prefix}600519") == "600519"


class TestFmpSymbolPrefixedInput:
    """to_fmp_symbol 对已带交易所前缀的输入原样返回（符号格式透传）。"""

    def test_lowercase_prefixed_passthrough(self):
        assert to_fmp_symbol("sh600519") == "SH600519"
        assert to_fmp_symbol("sz000001") == "SZ000001"
        assert to_fmp_symbol("bj430047") == "BJ430047"
