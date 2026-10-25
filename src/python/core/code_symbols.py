"""证券代码派生量 — 符号转换 / 接口参数 / 规模粗估（从 code_utils 拆出）。

**职责边界**：`core/code_utils.py` 只做「这个代码是什么（资产类型识别）」；
本模块做「把代码翻译成下游系统要的字符串与数量」——交易所前后缀、FMP 风格符号、
东方财富 push2 的 secid、cninfo 栏目参数、市值规模粗估。两者共用同一套前缀常量
（唯一真值在本模块，`code_utils` 反向引用，避免两处各建一张表）。

**导入口径**：派生量一律从本模块导入（`code_utils` 只做资产类型判定，不转出本模块符号）。
"""

from __future__ import annotations

# ── 交易所前缀（证券代码口径唯一真值来源）──────────────────────
# 交易所代码前缀（证券代码口径的唯一真值来源）：沪 sh / 深 sz / 北 bj。
# 前缀识别一律复用本常量经 strip_exchange_prefix()，不得在各模块自建元组
# ——自建表在新增交易所时会漏改一处，导致同一代码在两处判定口径分叉。
EXCHANGE_PREFIXES = ("sh", "sz", "bj")

# A 股指数交易所前缀
_INDEX_EXCHANGE_PREFIXES = ("sh", "sz")


# ═══════════════════════════════════════════════════════════════
#  前缀归一化 / 符号转换
# ═══════════════════════════════════════════════════════════════

#: 场内 ETF/LOF 交易所后缀（6 位代码段 → 交易所）；判定口径单点维护
_EXCHANGE_FUND_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("5", ".SH"),  # 沪市场内基金/ETF
    ("1", ".SZ"),  # 深市场内基金/ETF（159xxxLOF 等同段）
)


def strip_exchange_prefix(code: str) -> str:
    """去除交易所前缀（sh/sz/bj，大小写不敏感），返回去前缀后的原串。

    与 :func:`_strip_prefix` 的分工：本函数**只剥离前缀、不校验代码位数**，
    供需要自行判定代码形态的调用方（如按 5/6 位区分境内外、容忍 ``.0`` 尾、
    需原样保留非法码以便报错的场景）复用前缀知识，避免各模块自建前缀表。

    Args:
        code: 可带前缀的证券代码（None/空串安全）

    Returns:
        去前缀后的原串（未带前缀时原样返回，不做 trim 以外的规范化）
    """
    raw = (code or "").strip()
    if not raw:
        return ""
    lower = raw.lower()
    for prefix in EXCHANGE_PREFIXES:
        if lower.startswith(prefix):
            return raw[len(prefix) :]
    return raw


def strip_to_digits(code: str) -> str:
    """去除交易所前缀并校验形态：返回 6 位纯数字代码，非 6 位数字时返回空串。

    本函数是**形态判定的底层原语**：`code_utils.is_six_digit_code` 调用本函数，
    故 6 位判定直接在此完成（调用上层判据会互相递归）。

    Args:
        code: 可带前缀的代码

    Returns:
        纯净 6 位数字代码，或空字符串（非 6 位数字时）
    """
    raw = strip_exchange_prefix(code)
    if len(raw) == 6 and raw.isdigit():
        return raw
    return ""


def to_fmp_symbol(code: str) -> str:
    """A 股 6 位代码 → FMP 风格符号；非 A 股代码返回空串。

    沪市（600/601/603/605/688/689）→ ``.SS``；深市（000/001/002/003/300/301）
    → ``.SZ``；北交所（43x/83x/87x/920）→ ``.BJ``。带后缀或前缀的输入原样
    返回（已是符号格式）。

    放在 code_utils 而非某个 provider 内：多个数据源（财报全文、财务指标）
    都需要同一个符号口径，复制两份必然漂移。
    """
    raw = (code or "").strip().upper()
    if not raw:
        return ""
    if "." in raw:
        return raw
    if raw.lower().startswith(EXCHANGE_PREFIXES) and len(raw) == 8:
        return raw
    if not (len(raw) == 6 and raw.isdigit()):
        return ""
    if raw.startswith(("600", "601", "603", "605", "688", "689")):
        return f"{raw}.SS"
    if raw.startswith(("000", "001", "002", "003", "300", "301")):
        return f"{raw}.SZ"
    if raw.startswith(("43", "83", "87", "92")):
        return f"{raw}.BJ"
    return ""


def to_exchange_symbol(code: str) -> str | None:
    """场内 ETF/LOF 6 位代码 → 带交易所后缀符号（``5xxxxx``→``.SH``、``1xxxxx``→``.SZ``）。

    :func:`to_fmp_symbol` 只覆盖 A 股股票段；场内基金段的判定同样需要单点维护，
    供同花顺 thscode 转换与后缀候选解析复用。非该两段（或非 6 位纯数字）返回
    ``None``，调用方继续走自己的降级路径。

    Args:
        code: 待判定的代码（可含前缀/后缀，带 ``.`` 视为已是符号格式直接返回自身）

    Returns:
        ``f"{code}.SH/.SZ"``；不属于场内基金段 → ``None``
    """
    raw = (code or "").strip().upper()
    if not raw:
        return None
    if "." in raw:
        return raw
    if len(raw) != 6 or not raw.isdigit():
        return None
    for prefix, suffix in _EXCHANGE_FUND_SUFFIXES:
        if raw.startswith(prefix):
            return f"{raw}{suffix}"
    return None


# ═══════════════════════════════════════════════════════════════
#  数据源接口参数（交易所前缀 / push2 secid / cninfo 栏目）
# ═══════════════════════════════════════════════════════════════


def get_exchange_prefix(code: str) -> str:
    """根据 6 位代码返回东方财富行情页所需的交易所前缀。

    Args:
        code: 6 位证券代码

    Returns:
        "sh" | "sz" | "bj"
    """
    raw = code.strip()
    if raw.startswith(("5", "6")):
        return "sh"
    if raw.startswith(("0", "1", "2", "3", "9")):
        return "sz"
    return "bj"


def get_index_exchange_prefix(code: str) -> str:
    """获取 A 股指数代码的交易所前缀。

    如 ``"sh000300"`` → ``"sh"``，非 A 股指数（如 ``"gb_inx"``）返回空字符串。

    Args:
        code: 指数代码

    Returns:
        ``"sh"`` | ``"sz"`` | ``""``
    """
    raw = code.strip()
    for prefix in _INDEX_EXCHANGE_PREFIXES:
        if raw.startswith(prefix):
            return prefix
    return ""


def index_exchange_of(code: str) -> str:
    """A 股指数代码 → 交易所（``"sh"`` / ``"sz"`` / ``""``）——唯一判定点。

    判据：显式前缀优先（``sh``/``sz``）；裸 6 位码按段归属——``399``/``932`` 属深市，
    其余 A 股指数（``000``/``930`` 等）归沪市。该规则只在本模块声明；provider 侧
    一律调用本函数，不得自建段前缀表。
    """
    raw = (code or "").strip().lower()
    prefix = get_index_exchange_prefix(raw)
    if prefix:
        return prefix
    digits = raw
    if not digits.isdigit() or len(digits) != 6:
        return ""
    return "sz" if digits.startswith(("399", "932")) else "sh"


def get_push2_secid(code: str) -> str:
    """生成东方财富 push2 API 所需的 secid 参数。

    - 沪市（6/5/8/4 开头）：1.{code}
    - 深市（0/1/2/3 开头）：0.{code}

    Args:
        code: 6 位证券代码

    Returns:
        "0.xxx" 或 "1.xxx"
    """
    raw = code.strip()
    if raw.startswith(("0", "1", "2", "3")):
        return f"0.{raw}"
    return f"1.{raw}"


def get_exchange_category(code: str) -> str:
    """6 位 A 股代码 → cninfo 栏目参数（``sse``/``szse``/``third``）。

    上交所（``6`` 开头）→ ``sse``；北交所（``4``/``8`` 开头）→ ``third``；
    其余（深市主板/创业板）→ ``szse``。栏目映射原散落在 cninfo provider 内，
    收敛到 code_utils 与其余代码类型判定同表维护。
    """
    raw = (code or "").strip()
    if raw.startswith("6"):
        return "sse"
    if raw.startswith(("4", "8")):
        return "third"
    return "szse"


# ═══════════════════════════════════════════════════════════════
#  规模粗估
# ═══════════════════════════════════════════════════════════════


def estimate_market_cap_by_prefix(code: str) -> str:
    """按代码前缀粗略估算市值规模。

    Args:
        code: 6 位证券代码

    Returns:
        "大盘" | "中盘" | "中小盘" | "小盘" | "中大盘" | "其他"
    """
    raw = strip_to_digits(code)
    if not raw:
        return "其他"
    if raw.startswith(("60",)):
        return "大盘"
    elif raw.startswith(("000",)) or raw.startswith(("002",)):
        return "中盘"
    elif raw.startswith(("300",)) or raw.startswith(("688",)):
        return "中小盘"
    elif raw.startswith(("4", "8")):
        return "小盘"
    elif raw.startswith(("001",)):
        return "中大盘"
    return "其他"
