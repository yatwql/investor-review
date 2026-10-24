"""证券代码工具 — 资产类型识别唯一入口。

集中管理 A 股/基金/债券/港股等资产类型的代码前缀和名称关键词知识，
避免多个模块各自维护一套判定规则。**只做「这个代码是什么」的判断**。

派生量（交易所前后缀归一、FMP/东财/cninfo 符号与参数、市值规模粗估）由
:mod:`src.python.core.code_symbols` 单一实现，调用方直接导入该 owner；
本模块只保留资产类型判定逻辑，并复用其中的前缀常量与剥离函数。
"""

from __future__ import annotations

# 本模块内部复用的派生量（owner：code_symbols）
from src.python.core.code_symbols import (
    _INDEX_EXCHANGE_PREFIXES,
    strip_to_digits,
)

# ── 已知代码前缀区间 ────────────────────────────────────────
# A 股股票：
#   60xxxx（上海主板）、68xxxx（科创板）
#   00xxxx（深圳主板/中小板，002xxx/003xxx）、30xxxx（创业板）
#   8xxxxx（北交所）
_A_SHARE_PREFIXES = ("60", "68", "00", "30")


# 场内基金 / ETF 前缀（1 开头含深市 ETF/LOF/Reits/可转债，5 开头含沪市 ETF）
_EXCHANGE_FUND_PREFIXES = ("5", "1")

# ── 名称关键词 ──────────────────────────────────────────────
# 债券基金关键词（用于基金类型识别，不包含过于宽泛的 "债" 以避免
# 可转债等非纯债品种被误判为债券基金）
_BOND_KEYWORDS = ("纯债", "短债", "中短债", "利率债", "信用债", "债券")


# 债券关键词宽松版（含单字"债"，覆盖可转债等含"债"字段的品种）
_BOND_KEYWORDS_BROAD = ("债", "纯债", "短债", "中短债", "利率债", "信用债", "债券")

# 场外基金账户关键词（用于 account 维度的判断）
FUND_ACCOUNT_KEYWORDS = ("基金", "支付宝", "微信", "银行")

# 指数类关键词（用于场外被动基金判定）
INDEX_KEYWORDS = ("指数", "ETF联接", "ETF 联接", "中证", "沪深300", "中证500", "中证1000", "科创50", "创业板", "上证")

# 隐式 QDII 关键词
_OVERSEA_KW = ("纳斯达克", "标普", "纳指", "道琼斯", "日经")

# 货币类关键词
MONEY_KEYWORDS = ("货币", "现金", "增利", "宝")

# ── 指数代码相关常量 ──────────────────────────────────────────

# 美股指数代码前缀
_US_INDEX_PREFIX = "gb_"
# A 股指数原始 6 位码起始数字
_A_INDEX_RAW_PREFIXES = ("000", "399", "932")


# ═══════════════════════════════════════════════════════════════
#  代码前缀型判定（6 位证券代码，可含 sh/sz/bj 前缀）
# ═══════════════════════════════════════════════════════════════


def is_a_share_code(code: str) -> bool:
    """判断 6 位证券代码是否为 A 股股票。

    港股（00700）、基金（161725 等）返回 False。

    Args:
        code: 证券代码，可含 sh/sz/bj 前缀

    Returns:
        True 为 A 股代码
    """
    raw = strip_to_digits(code)
    if not raw:
        return False
    return raw.startswith(_A_SHARE_PREFIXES) or raw.startswith("8")


def is_exchange_fund_code(code: str) -> bool:
    """判断是否为场内基金/ETF 代码（5xxxxx 或 1xxxxx 开头）。

    含沪市 ETF（51/56/58）、深市 ETF（159）、LOF、Reits（18）、
    可转债（12）等场内交易品种。

    Args:
        code: 6 位证券代码

    Returns:
        True 为场内基金/ETF 代码
    """
    raw = strip_to_digits(code)
    if not raw:
        return False
    return raw.startswith(_EXCHANGE_FUND_PREFIXES)


def is_hk_stock_code(code: str) -> bool:
    """判断是否为港股通标的（5 位纯数字代码，如 00700、03690）。

    港股通标的通过 Stock Connect 在 A 股账户中交易，
    代码格式为 5 位数字，与 A 股的 6 位代码格式不同。

    Args:
        code: 证券代码

    Returns:
        True 为港股通代码
    """
    raw = code.strip()
    return len(raw) == 5 and raw.isdigit()


def is_six_digit_code(code: str) -> bool:
    """判断是否为 6 位纯数字证券代码（各市场通用的代码形态合法性判定）。

    配置键校验、申购状态行校验、基金净值链路兜底等场景统一经本原语判定，
    不再在调用方内联 ``len(code) == 6 and code.isdigit()``（代码形态判定中心化约束）。

    Args:
        code: 证券代码，可含 sh/sz/bj 前缀

    Returns:
        True 为 6 位纯数字代码
    """
    raw = strip_to_digits(code)
    if not raw:
        return False
    return len(raw) == 6 and raw.isdigit()


def is_letter_based_code(code: str) -> bool:
    """判断是否为字母为主的代码形态（美股等外盘字母/字母数字混合代码）。

    纯数字代码（A 股/港股/基金等 5-6 位数字）与含非法字符的代码返回 False。

    Args:
        code: 证券代码

    Returns:
        True 为含字母的字母数字代码
    """
    stripped = (code or "").strip()
    if not stripped:
        return False
    return stripped.isalnum() and any(ch.isalpha() for ch in stripped)


# ═══════════════════════════════════════════════════════════════
#  名称关键词型判定
# ═══════════════════════════════════════════════════════════════


def is_qdii_by_name(name: str) -> bool:
    """判断基金名称是否含 QDII 标识。

    Args:
        name: 基金名称

    Returns:
        True 为 QDII 基金
    """
    return "QDII" in name.upper()


def is_bond_related_by_name(name: str) -> bool:
    """判断名称是否含债券类关键词（严格版）。

    匹配纯债/短债/中短债/利率债/信用债/债券，不含单字"债"，
    因此可转债等品种不会被误判。如需覆盖可转债请使用
    :func:`is_bond_fund_by_name`。

    Args:
        name: 持仓名称

    Returns:
        True 表示名称匹配债券特征
    """
    return any(kw in name for kw in _BOND_KEYWORDS)


def is_etf_by_name(name: str) -> bool:
    """判断名称是否含 ETF 标识。

    Args:
        name: 持仓名称

    Returns:
        True 为 ETF
    """
    return "ETF" in name.upper()


def is_index_link_by_name(name: str) -> bool:
    """判断名称是否含指数联接关键词。

    识别：ETF联接 / ETF链接 / 联接 / 链接

    Args:
        name: 基金名称

    Returns:
        True 表示名称匹配指数联接特征
    """
    clean = name.replace(" ", "").upper()
    if "ETF联接" in clean or "ETF链接" in clean:
        return True
    return any(kw in name for kw in ("联接", "链接"))


def is_etf_by_name_or_code(name: str, code: str = "") -> bool:
    """判断是否为 ETF（名称 + 代码双维度检测）。

    识别依据：
      1. 名称含 "ETF"（大小写不敏感）
      2. 代码以 5（上海 ETF）或 1（深圳 ETF/LOF）开头

    Args:
        name: 持仓名称
        code: 证券代码（可选，提升识别准确率）

    Returns:
        True 表示符合 ETF 特征
    """
    if "ETF" in name.upper():
        return True
    if code:
        raw = strip_to_digits(code)
        if raw.startswith(("5", "1")):
            return True
    return False


def is_bond_fund_by_name(name: str) -> bool:
    """判断名称是否为债券基金（宽松匹配）。

    使用 ``_BOND_KEYWORDS_BROAD``（含"债"）进行匹配，
    覆盖纯债/短债/可转债等含"债"字段的品种。

    Args:
        name: 基金名称

    Returns:
        True 表示名称匹配债券基金特征
    """
    return any(k in name for k in _BOND_KEYWORDS_BROAD)


def is_convertible_bond_by_name(name: str) -> bool:
    """判断名称是否为可转债（含"转债"关键词）。

    可转债虽以 1 开头代码上市交易（与 ETF/LOF 同区间），
    但其股债混合性质不属于基金/ETF/股票穿透分类，
    需在 ``classify_penetration`` 的 ETF 判定前单独排除。

    Args:
        name: 持仓名称

    Returns:
        True 表示名称匹配可转债特征
    """
    return "转债" in name


def is_offsite_fund(account: str) -> bool:
    """判断账户是否为场外基金渠道。

    场外渠道指通过基金公司、支付宝、微信、银行购买的基金。

    Args:
        account: 账户名称

    Returns:
        True 表示为场外基金账户
    """
    return any(kw in account for kw in FUND_ACCOUNT_KEYWORDS)


def is_qdii_extended(name: str | None) -> bool:
    """判断是否为 QDII 基金（含隐式海外基金识别）。

    显式 QDII：名称含 "QDII"（大小写不敏感）。
    隐式 QDII：名称含海外指数关键词（纳斯达克、标普、纳指、道琼斯、日经）。

    Args:
        name: 基金名称

    Returns:
        True 表示 QDII 基金（含隐式海外）
    """
    if not name:
        return False
    if is_qdii_by_name(name):
        return True
    return any(kw in name for kw in _OVERSEA_KW)


def is_money_fund_by_name(name: str) -> bool:
    """判断名称是否为货币类基金。

    识别关键词：货币、现金、增利、宝。

    Args:
        name: 基金名称

    Returns:
        True 表示名称匹配货币基金特征
    """
    return any(kw in name for kw in MONEY_KEYWORDS)


def is_index_fund_by_name(name: str) -> bool:
    """判断名称是否为场外指数/被动型基金。

    通过 INDEX_KEYWORDS（指数/ETF联接/中证/沪深300/中证500/
    中证1000/科创50/创业板/上证）进行匹配，用于区分场外
    被动基金与场外主动基金。

    Args:
        name: 基金名称

    Returns:
        True 表示名称匹配指数/被动基金特征
    """
    return any(kw in name for kw in INDEX_KEYWORDS)


# 场外基金名称关键词（用于 00 代码重叠区辅助判断）
# 00 前缀与深市主板股票区间重叠；A 股股票名不含"债券/指数/股票/混合"等基金特征词，
# 因此 00 前缀 + 命中关键词即可安全判定为场外基金。
_OTC_FUND_NAME_KW = (
    "混合",  # XX灵活配置混合/偏股混合/偏债混合
    "纯债",  # 纯债债券
    "短债",  # 短债债券
    "中短债",  # 中短债债券
    "利率债",  # 利率债债券
    "信用债",  # 信用债债券
    "债券",  # 债券型基金（如 XX双利债券A，不含上述细分词）
    "指数",  # 指数型基金（如 XX中证XXX指数A）
    "股票",  # 股票型基金（如 XX医疗保健股票A）
    "货币",  # 货币市场基金
    "联接",  # ETF联接
    "增利",  # 增利货币
)


def is_otc_fund_by_name(name: str, code: str) -> bool:
    """判断 00 代码是否为场外基金（名称 + 代码双维度）。

    OTC 基金代码以 00 开头，与深市主板股票代码区间重叠，
    单纯靠前缀 `is_a_share_code()` 无法区分。本函数利用
    名称中的基金特征关键词辅助判定。

    Args:
        name: 持仓名称
        code: 6 位证券代码（可为空，仅非 00 开头时提前返回）

    Returns:
        True 表示确认为场外基金
    """
    raw = strip_to_digits(code) if code else ""
    if not raw or not raw.startswith("00"):
        return False
    return any(kw in name for kw in _OTC_FUND_NAME_KW)


def is_a_share_stock(name: str, code: str) -> bool:
    """持仓是否应按「A 股个股」处理（排除 00 前缀重叠区的场外基金）。

    A 股代码前缀与场外基金代码在 00 区间重叠；仅凭代码前缀会把
    「广发多因子灵活配置混合(002943)」这类场外基金误当个股，进而取到
    同代码深市股票（如「宇晶股份」）的行情/历史/分红/行业/估值数据。
    本判据在代码前缀之外叠加名称维度，供报告各域路由统一复用。

    Args:
        name: 持仓名称
        code: 6 位证券代码

    Returns:
        True 表示按 A 股个股处理；重叠区内名称命中基金特征词返回 False
    """
    return is_a_share_code(code) and not is_otc_fund_by_name(name, code)


def classify_holding_tier(name: str, code: str, account: str) -> tuple[str, str]:
    """持仓分类单源：将持仓映射到 (资产属性, 投资分类) 二元组。

    报告持仓分类页签与行动建议收益归因的大类分解共用本实现（分类判定唯一
    事实来源，关键词原语与判定规则同居本模块；消费方不得自行复制规则）。

    分类逻辑（按优先级）：
      1. QDII（名称含 QDII）→ 基金 / QDII
      2. 名称含固收关键词 → 债券 / 纯债
      3. 名称含货币关键词 → 现金 / 货币
      4. 场外渠道且名称含指数关键词 → 基金 / 被动
      5. 场外渠道 → 基金 / 主动
      6. 场内ETF（名称含ETF或代码5/1开头）→ 基金 / 指数
      7. 场内股票（代码6/0/3开头）→ 股票 / A股
      8. 其余 → 基金 / 混合

    Args:
        name: 持仓名称
        code: 6 位证券代码
        account: 账户/渠道名（场外渠道判定依据；空串按未命中场外处理）

    Returns:
        (资产属性, 投资分类)
    """
    name = name.strip()
    code = code.strip()
    account = account.strip()

    # 1) QDII
    if is_qdii_extended(name):
        return ("基金", "QDII")

    # 2) 固收类
    if is_bond_fund_by_name(name):
        return ("债券", "纯债")

    # 3) 货币类
    if is_money_fund_by_name(name):
        return ("现金", "货币")

    # 4) 场外渠道
    if is_offsite_fund(account):
        if is_index_fund_by_name(name):
            return ("基金", "被动")
        return ("基金", "主动")

    # 5) 场内 ETF（名称含ETF或代码5/1开头）
    if is_etf_by_name_or_code(name, code):
        return ("基金", "指数")

    # 5b) 00 代码场外基金（名称匹配基金特征，与 A 股 00 前缀重叠区）
    if is_otc_fund_by_name(name, code):
        return ("基金", "混合")

    # 6) 场内股票（A股或港股通）
    if is_a_share_code(code) or is_hk_stock_code(code):
        return ("股票", "A股")

    # 7) 其余归为基金/混合
    return ("基金", "混合")


# ── 场外基金赎回天数类型默认档（非实测）──
# 供流动性维在场外品种未配置单日赎回上限（config.json `redemption_limits`）时给出
# 类型分级默认档，使场外为主的组合在流动性维有区分度。档位为经验口径而非实测：
# 证据/标签一律标注「类型默认档（非实测）」，用户配置实测上限后优先采用配置值。
OTC_REDEMPTION_TIER_MONEY = 1  # 货币基金/短债基金：T+0~T+1
OTC_REDEMPTION_TIER_BOND = 2  # 纯债基金：T+2
OTC_REDEMPTION_TIER_EQUITY = 3  # 其他场外基金（主动权益/混合/指数/联接等）：T+3
OTC_REDEMPTION_TIER_QDII = 7  # QDII/海外基金：T+3~T+7，取保守上沿


def otc_redemption_days_default(name: str, code: str = "") -> int | None:
    """场外基金赎回天数的类型默认档（非实测）。

    分级（命中即返回）：货币基金/短债 → T+1；纯债 → T+2；QDII/海外 → T+7；
    其余可识别场外基金（主动权益/混合/指数/联接等）→ T+3。
    无法识别为场外基金时返回 None（调用方保持「需手动确认」降级）。

    Args:
        name: 基金名称
        code: 证券代码（可选，用于 00 重叠区辅助判定）

    Returns:
        赎回天数默认档（整数）；无法识别返回 None。
    """
    if is_money_fund_by_name(name) or "短债" in name:
        return OTC_REDEMPTION_TIER_MONEY
    if is_bond_fund_by_name(name):
        return OTC_REDEMPTION_TIER_BOND
    if is_qdii_extended(name):
        return OTC_REDEMPTION_TIER_QDII
    if is_index_link_by_name(name) or is_index_fund_by_name(name) or is_otc_fund_by_name(name, code):
        return OTC_REDEMPTION_TIER_EQUITY
    return None


def is_otc_code_overlap(code: str) -> bool:
    """判断 6 位代码是否处于 A 股/OTC 基金代码重叠区（00 开头）。

    OTC 基金代码以 00 开头，与深市主板（000~004）和中小板（002/003）
    股票代码区间重叠。本函数仅检测前缀，不验证名称，
    用于降级路由中判断"是否值得尝试基金净值 API"的快速预筛。

    Args:
        code: 6 位证券代码

    Returns:
        True 表示代码处于重叠区间（00 开头）
    """
    raw = strip_to_digits(code)
    return bool(raw and raw.startswith("00"))


def is_fund_holding(name: str, code: str, account: str) -> bool:
    """判断持仓是否需要基金业绩分析。

    识别逻辑：纯 A 股/港股通（代码前缀匹配且名称不含 ETF）
    且不在场外基金账户中 → 非基金，其余全部视为基金。

    对 00 代码重叠区，优先通过 ``is_otc_fund_by_name()`` 确认。

    Args:
        name: 持仓名称
        code: 证券代码
        account: 账户名称

    Returns:
        True 表示需要基金业绩分析
    """
    if is_otc_fund_by_name(name, code):
        return True
    return not (
        (is_a_share_code(code) or is_hk_stock_code(code)) and "ETF" not in name.upper() and not is_offsite_fund(account)
    )


# ═══════════════════════════════════════════════════════════════
#  交易所 / API 前缀
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
#  指数代码判定（基准指数比对功能）
# ═══════════════════════════════════════════════════════════════


def is_index_code(code: str) -> bool:
    """判断代码是否为指数代码（A 股/美股通用）。

    识别依据：
      - 美股指数：``gb_`` 开头（如 ``gb_inx``）
      - A 股指数：``sh``/``sz`` 前缀 + 6 位码（以 000/399/932 开头）
      - 纯 6 位 000/399/932 开头代码（无前缀时也识别）

    Args:
        code: 指数代码

    Returns:
        True 表示该代码为指数代码
    """
    raw = code.strip()
    if not raw:
        return False
    # 美股指数
    if raw.startswith(_US_INDEX_PREFIX):
        return True
    # 去除交易所前缀
    stripped = raw
    for prefix in _INDEX_EXCHANGE_PREFIXES:
        if raw.startswith(prefix):
            stripped = raw[len(prefix) :]
            break
    # A 股指数：6 位数字码以特定前缀开头
    return len(stripped) == 6 and stripped.isdigit() and stripped.startswith(_A_INDEX_RAW_PREFIXES)


def is_us_index_code(code: str) -> bool:
    """判断是否为美股指数代码（``gb_`` 开头）。

    Args:
        code: 指数代码

    Returns:
        True 表示该代码为美股指数
    """
    return bool(code and code.strip().startswith(_US_INDEX_PREFIX))


# ═══════════════════════════════════════════════════════════════
#  内部工具
# ═══════════════════════════════════════════════════════════════


def get_currency_by_code(name: str, code: str) -> str:
    """根据证券名称和代码判定交易币种。

    港股通（5 位纯数字代码）→ HKD，
    QDII/海外基金/美股指数 → USD，
    其余 A 股/基金 → CNY。

    Args:
        name: 证券名称
        code: 证券代码

    Returns:
        "CNY" | "HKD" | "USD"
    """
    if is_hk_stock_code(code):
        return "HKD"
    if is_qdii_extended(name):
        return "USD"
    return "CNY"
