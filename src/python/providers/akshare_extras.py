"""akshare 扩展数据源 — 盈利预测 + 行业资金流向 + 分红历史。

通过 akshare 获取以下数据：
  1. stock_profit_forecast_em — 机构盈利预测（全量股票，含预测 EPS）
  2. stock_sector_fund_flow_rank — 行业资金流向排名（含主力净流入）
  3. stock_history_dividend — 全量股票历史分红（akshare 无参调用，按代码过滤）

各函数独立，使用指数变化/代码列表指纹 + TTL 双因子缓存失效策略。
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading as _threading
import time as _time
from typing import Any

from src.python.cache import clear as cache_clear
from src.python.cache import get as cache_get
from src.python.cache import set as cache_set
from src.python.core.code_utils import is_a_share_code
from src.python.core.data_registry import (
    SECTOR_FLOW_NEG_KEY,
    SECTOR_FLOW_STALE_KEY,
    get_exact_ttl_map,
)
from src.python.core.num_utils import safe_num
from src.python.providers.utils import run_with_timeout

logger = logging.getLogger("invest")

# akshare 是可选依赖，统一在模块级加载一次
try:
    import akshare as ak
except ImportError:
    ak = None
    logger.info("akshare 模块未安装，akshare_extras 功能将跳过")

# ── 进程级内存 TTL 缓存（位于文件缓存之上） ──
_MEMO_CACHE: dict[str, tuple[Any, float]] = {}
_MEMO_LOCK = _threading.Lock()
_MEMO_MAX = 100
_MEMO_TTL: dict[str, float] = {
    "profit_forecast": 300,  # 5 min — 指纹驱动，短期 memo 足够
    "sector_flow": 60,  # 1 min — 行业资金流向变化快
    "dividend": 600,  # 10 min — 分红数据会话内极少变化
    # 行业资金流向**失败**的负缓存：源不可达/返回空时，同一天内多份报告不必
    # 各自再撞一次超时（akshare 内部还会重试 2 次）；失败结论只用于「本会话内
    # 先不再试」，状态仍经 ``sector_flow_failure()`` 如实上报，不会被当成成功。
    "sector_flow_fail": 300,  # 5 min
}


def _memo_key(name: str, *args_hashes: str) -> str:
    return f"{name}:{':'.join(args_hashes)}" if args_hashes else name


def _memo_get(key: str) -> Any:
    with _MEMO_LOCK:
        entry = _MEMO_CACHE.get(key)
        if entry is not None:
            age = _time.time() - entry[1]
            prefix = key.split(":")[0] if ":" in key else key
            ttl = _MEMO_TTL.get(prefix, 60)
            if age < ttl:
                return entry[0]
            # 过期条目延迟删除
            del _MEMO_CACHE[key]
    return None


def _memo_set(key: str, value: Any) -> None:
    with _MEMO_LOCK:
        # LRU 淘汰：超过 _MEMO_MAX 条时删除最旧条目
        if len(_MEMO_CACHE) >= _MEMO_MAX and key not in _MEMO_CACHE:
            oldest_key = min(_MEMO_CACHE, key=lambda k: _MEMO_CACHE[k][1])
            del _MEMO_CACHE[oldest_key]
        _MEMO_CACHE[key] = (value, _time.time())


def _memo_clear() -> None:
    """测试用：清空全部内存缓存。"""
    with _MEMO_LOCK:
        _MEMO_CACHE.clear()


# ── 指数数据内存缓存（避免重复文件读取） ──
_INDEX_MEMO: dict[str, tuple[Any, float]] = {}
_INDEX_MEMO_TTL = 60  # 60 秒
_INDEX_MEMO_LOCK = _threading.Lock()

_CACHE_PROFIT_PREFIX = "profit_forecast_"
_CACHE_FLOW_PREFIX = "sector_flow_"
_CACHE_DIVIDEND_PREFIX = "dividend_"
_TTL = 86400  # 盈利预测：1天
_SECTOR_FLOW_TTL = 900  # 行业资金流向：15分钟
_DIVIDEND_TTL = 2592000  # 分红：1个月

#: 行业资金流向两个衍生键的 TTL 与键名统一取自注册表（`exact_key_ttls` 单源）：
#: 清理器与取数侧同源读取，两处数值不得各自写死。
_SECTOR_FLOW_EXACT_TTLS = get_exact_ttl_map()

#: 行业资金流向**失败**的跨进程负缓存键（无指纹，稳定键）：源不可达时，同机后续
#: 报告各自是独立进程，内存 memo 管不到——每份报告都会再撞一次超时（实测 30 次真实
#: 运行 38 次 akshare 异常）。落盘后在窗口内不再试，恢复后自动重新尝试。
_SECTOR_FLOW_NEG_KEY = SECTOR_FLOW_NEG_KEY
_SECTOR_FLOW_NEG_TTL = _SECTOR_FLOW_EXACT_TTLS[SECTOR_FLOW_NEG_KEY]

#: 最近一次**成功**的行业资金流向载荷（无指纹，稳定键）：源不可达时回退陈旧数据，
#: 不让「今日资金流向」整块从报告和 LLM 提示词里消失。
_SECTOR_FLOW_LAST_KEY = SECTOR_FLOW_STALE_KEY
_SECTOR_FLOW_STALE_TTL = _SECTOR_FLOW_EXACT_TTLS[SECTOR_FLOW_STALE_KEY]

#: 行业资金流向取数通道（按序尝试）。主通道东财 `push2` 在本机出口被配额型限流
#: （实测连续 20 次 0 成功、仅罕见短窗口放行），同花顺行业资金流实测 0.5s 返回 90 个
#: 行业——两通道输出同一结构契约，下游（报告/LLM 提示词）不感知来源。
_SECTOR_FLOW_CHANNELS: tuple[str, ...] = ("em_push2", "ths_industry")
_SECTOR_FLOW_CHANNEL_LABELS: dict[str, str] = {"em_push2": "东财 push2", "ths_industry": "同花顺"}

#: 同花顺行业资金流的金额单位是**亿元**，下游（`prompts_signals._fmt_amount` 等）
#: 按东财口径的**元**消费，契约层统一换算。
_THS_YI_TO_YUAN = 1e8


class _SectorFlowUnavailable(RuntimeError):
    """单个取数通道不可用（`kind` 与现有失败类型同词：connection / empty）。"""

    def __init__(self, kind: str, channel: str) -> None:
        super().__init__(f"{channel}:{kind}")
        self.kind = kind
        self.channel = channel


def _fetch_sector_flow_em_push2() -> list[dict[str, Any]]:
    """主通道：东财 push2 板块资金流排行（`ak.stock_sector_fund_flow_rank`）。"""
    _ak = ak
    if _ak is None:
        raise _SectorFlowUnavailable("connection", "em_push2")
    df = run_with_timeout(lambda: _ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流"))
    if df is None:
        raise _SectorFlowUnavailable("connection", "em_push2")
    if df.empty:
        raise _SectorFlowUnavailable("empty", "em_push2")
    return _struct_sector_flow_rows(df, _EM_SECTOR_FIELDS, "em_push2")


def _fetch_sector_flow_ths_industry() -> list[dict[str, Any]]:
    """备用通道：同花顺行业资金流（`ak.stock_fund_flow_industry("即时")`）。

    差异归一：金额由亿元换算为元；同花顺没有「主力净占比」字段，改由
    ``净额 / (流入+流出) * 100`` 派生（分母不可用时留空，不编造 0）。
    """
    _ak = ak
    if _ak is None:
        raise _SectorFlowUnavailable("connection", "ths_industry")
    df = run_with_timeout(lambda: _ak.stock_fund_flow_industry(symbol="即时"))
    if df is None:
        raise _SectorFlowUnavailable("connection", "ths_industry")
    if df.empty:
        raise _SectorFlowUnavailable("empty", "ths_industry")

    result: list[dict[str, Any]] = []
    try:
        for _, row in df.iterrows():  # noqa: PERF203 —— 逐行容错，单行脏数据不弃整榜
            _in = _safe_float(row.get("流入资金"))
            _out = _safe_float(row.get("流出资金"))
            _net = _safe_float(row.get("净额"))
            _turnover = (abs(_in) if _in is not None else 0.0) + (abs(_out) if _out is not None else 0.0)
            result.append(
                {
                    "name": str(row.get("行业", "") or "").strip(),
                    "change_pct": _safe_float(row.get("行业-涨跌幅")),
                    "main_net_inflow": None if _net is None else round(_net * _THS_YI_TO_YUAN, 2),
                    "main_net_inflow_pct": (
                        round(_net / _turnover * 100, 2) if _net is not None and _turnover > 0 else None
                    ),
                    "top_stock": str(row.get("领涨股", "") or "").strip(),
                }
            )
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise _SectorFlowUnavailable("connection", "ths_industry") from exc
    return result


#: 东财 push2 行字段 → 契约字段（列名由 akshare 定义，变更时只需改这张表）。
_EM_SECTOR_FIELDS: tuple[tuple[str, str], ...] = (
    ("name", "名称"),
    ("change_pct", "今日涨跌幅"),
    ("main_net_inflow", "今日主力净流入-净额"),
    ("main_net_inflow_pct", "今日主力净流入-净占比"),
    ("top_stock", "今日主力净流入最大股"),
)


#: 通道名 → 取数函数（顺序即优先级，由 `_SECTOR_FLOW_CHANNELS` 决定）。
_SECTOR_FLOW_FETCHERS: dict[str, Any] = {
    "em_push2": _fetch_sector_flow_em_push2,
    "ths_industry": _fetch_sector_flow_ths_industry,
}


def _struct_sector_flow_rows(df: Any, fields: tuple[tuple[str, str], ...], channel: str) -> list[dict[str, Any]]:
    """按字段表把 DataFrame 归一到契约结构；解析异常规整为通道不可用。"""
    result: list[dict[str, Any]] = []
    try:
        for _, row in df.iterrows():  # noqa: PERF203 —— 逐行容错，单行脏数据不弃整榜
            item: dict[str, Any] = {}
            for key, col in fields:
                item[key] = (
                    _safe_float(row.get(col))
                    if key != "name" and key != "top_stock"
                    else str(row.get(col) or "").strip()
                )
            result.append(item)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise _SectorFlowUnavailable("connection", channel) from exc
    return result


def _channel_failures() -> dict[str, str]:
    """读取各通道的失败态（进程内 memo → 跨进程负缓存）。"""
    raw = _memo_get(_memo_key("sector_flow_fail"))
    if not isinstance(raw, dict):
        raw = cache_get(_SECTOR_FLOW_NEG_KEY, _SECTOR_FLOW_NEG_TTL)
    if isinstance(raw, dict):
        return {str(ch): str(kind) for ch, kind in raw.items() if ch in _SECTOR_FLOW_CHANNELS and kind}
    if isinstance(raw, str) and raw:
        # 旧形态（整源单一字符串）：等同“全部通道同源失败”，升级后不立即重撞一轮。
        return {ch: raw for ch in _SECTOR_FLOW_CHANNELS}
    return {}


def _save_channel_failures(failures: dict[str, str]) -> None:
    """写回各通道失败态；全部恢复时清掉跨进程负缓存。"""
    _memo_set(_memo_key("sector_flow_fail"), dict(failures))
    if failures:
        cache_set(_SECTOR_FLOW_NEG_KEY, dict(failures))
    else:
        cache_clear(_SECTOR_FLOW_NEG_KEY)


def _sector_flow_stale_fallback(failure: str) -> list[dict[str, Any]]:
    """源不可达/空结果时的降级：回退最近一次成功载荷（≤3 天），拿不到才留空。"""
    global _SECTOR_FLOW_FAILURE, _SECTOR_FLOW_DEGRADED
    stale = cache_get(_SECTOR_FLOW_LAST_KEY, _SECTOR_FLOW_STALE_TTL)
    if isinstance(stale, list) and stale:
        _SECTOR_FLOW_FAILURE = "stale"
        _SECTOR_FLOW_DEGRADED = "stale"
        logger.info("行业资金流向回退陈旧数据（%d 个行业，源状态=%s）", len(stale), failure)
        return stale
    _SECTOR_FLOW_FAILURE = failure
    _SECTOR_FLOW_DEGRADED = "no_baseline"
    logger.info("行业资金流向无可用历史基准（源状态=%s），本次留空", failure)
    return []


def _note_sector_flow_failure(failure: str) -> list[dict[str, Any]]:
    """失败回调：回退陈旧数据或返回空列表（各通道负缓存已由调用方写入）。"""
    return _sector_flow_stale_fallback(failure)


def _compute_index_fingerprint() -> str:
    """计算市场指数数据的指纹，用于缓存键。

    从 fetcher 获取 A 股 + 美股指数数据 → MD5 前 12 位。
    指数变化时指纹改变 → 缓存自动失效，无需等待 TTL 过期。

    使用进程级内存缓存避免同一会话内重复文件读取。

    Returns:
        12 字符十六进制指纹；获取失败时返回空字符串（降级到纯 TTL 缓存）
    """
    try:
        from src.python.fetcher.index import fetch_indices, fetch_us_indices

        with _INDEX_MEMO_LOCK:
            cached = _INDEX_MEMO.get("indices")
            if cached is not None and _time.time() - cached[1] < _INDEX_MEMO_TTL:
                a_indices, us_indices = cached[0]
            else:
                a_indices = fetch_indices()
                us_indices = fetch_us_indices()
                _INDEX_MEMO["indices"] = ((a_indices, us_indices), _time.time())

        raw = json.dumps([a_indices, us_indices], ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.md5(raw.encode()).hexdigest()[:12]
    except (TypeError, ValueError):
        logger.debug("指数指纹计算失败（降级到纯 TTL 缓存）", exc_info=True)
        return ""


def _cache_key(prefix: str, fingerprint: str) -> str:
    """生成缓存键：有指纹时使用前缀+指纹，否则使用前缀+fallback。"""
    if fingerprint:
        return f"{prefix}{fingerprint}"
    return f"{prefix}nofp"


def get_profit_forecast() -> dict[str, dict]:
    """获取全量机构盈利预测数据。

    调用 ak.stock_profit_forecast_em() 获取所有股票的
    研报覆盖、预测 EPS、机构评级等数据。

    缓存策略：指数指纹 + 1天 TTL 双因子失效。
      指数变化 → 指纹改变 → 缓存键不同 → 自动取新数据

    Returns:
        {code: {name, reports, eps_2026e, eps_2027e, buy, sell}, ...}
        失败时返回空 dict
    """
    # ── 内存缓存 ──
    _memo_key_str = _memo_key("profit_forecast")
    _memo_val = _memo_get(_memo_key_str)
    if _memo_val is not None:
        return _memo_val

    # ── 指纹 + 读文件缓存 ──
    _fp = _compute_index_fingerprint()
    _key = _cache_key(_CACHE_PROFIT_PREFIX, _fp)
    cached = cache_get(_key, _TTL)
    if cached is not None:
        _memo_set(_memo_key_str, cached)
        return cached

    # ── 取数 ──
    if ak is None:
        logger.warning("akshare 模块未安装，跳过盈利预测")
        return {}
    _ak = ak  # 局部绑定：全局 ak 为可空（可选依赖），静态检查需要非空视图

    def _fetch():
        return _ak.stock_profit_forecast_em()

    df = run_with_timeout(_fetch, timeout=30.0)
    if df is None:
        logger.warning("盈利预测获取失败（超时或网络错误）")
        return {}
    if df.empty:
        logger.debug("盈利预测: 结果为空")
        return {}

    # ── 转为 code→data 字典 ──
    result: dict[str, dict] = {}
    for _, row in df.iterrows():
        code = str(row.get("代码", "")).strip()
        if not code:
            continue
        try:
            result[code] = {
                "name": str(row.get("名称", "") or "").strip(),
                "reports": int(row.get("研报数", 0) or 0),
                "eps_2026e": _safe_float(row.get("2026预测每股收益")),
                "eps_2027e": _safe_float(row.get("2027预测每股收益")),
                "buy": int(row.get("机构投资评级(近六个月)-买入", 0) or 0),
                "sell": int(row.get("机构投资评级(近六个月)-卖出", 0) or 0),
                "hold": int(row.get("机构投资评级(近六个月)-中性", 0) or 0),
            }
        except (ValueError, TypeError):
            continue

    logger.info("盈利预测加载完成: %d 只股票", len(result))
    cache_set(_key, result)
    _memo_set(_memo_key_str, result)
    return result


def get_profit_forecast_cache_key() -> str:
    """获取盈利预测数据的文件缓存键名（含指数指纹）。

    键名包含指数指纹，指数变化时指纹改变 → 缓存自动失效。
    供外部模块（如 fund_performance.py）获取正确键名后调 get_cache_age()。

    Returns:
        完整缓存键名（如 ``"profit_forecast_a1b2c3d4e5f6"``）
    """
    fp = _compute_index_fingerprint()
    return _cache_key(_CACHE_PROFIT_PREFIX, fp)


# 行业资金流向最近失败类型: "" / "connection" / "empty"
_SECTOR_FLOW_FAILURE: str = ""

# 行业资金流向最近降级态: "" / "stale"（回退到历史成功载荷）/ "no_baseline"（连基准都没有）
_SECTOR_FLOW_DEGRADED: str = ""


def sector_flow_failure() -> str:
    """返回行业资金流向最近一次失败类型（公开只读访问器；空串=最近成功）。"""
    return _SECTOR_FLOW_FAILURE


def sector_flow_degraded_state() -> str:
    """返回最近一次降级态（公开只读访问器）。

    ``""`` = 本次取数正常；``"stale"`` = 源不可达、已回退历史成功载荷；
    ``"no_baseline"`` = 源不可达且本机没有可回退的历史载荷（该区块只能留空）。
    下游据它区分两种降级表现，避免把「本机从未取到过」误述成「暂时取不到」。
    """
    return _SECTOR_FLOW_DEGRADED


# 分红数据最近失败类型: "" / "connection" / "empty"——供报告层如实登记分红
# 数据状态（与 _SECTOR_FLOW_FAILURE 同习语：区分「源不可达」与「本无分红」）。
_DIVIDEND_FAILURE: str = ""


def dividend_failure() -> str:
    """返回分红数据最近一次失败类型（公开只读访问器；空串=最近成功）。"""
    return _DIVIDEND_FAILURE


def get_sector_fund_flow() -> list[dict[str, Any]]:
    """获取行业资金流向排名（今日）。

    调用 ak.stock_sector_fund_flow_rank() 获取行业资金流向，
    含主力净流入/净额、涨跌幅等。

    缓存策略：指数指纹 + 1天 TTL 双因子失效。
      指数变化 → 指纹改变 → 缓存键不同 → 自动取新数据

    Returns:
        [{name, change_pct, main_net_inflow, main_net_inflow_pct, top_stock}, ...]
        失败时返回空列表
    """
    global _SECTOR_FLOW_FAILURE, _SECTOR_FLOW_DEGRADED

    # ── 内存缓存 ──
    _memo_key_str = _memo_key("sector_flow")
    _memo_val = _memo_get(_memo_key_str)
    if _memo_val is not None:
        return _memo_val

    # ── 指纹 + 读文件缓存 ──
    _fp = _compute_index_fingerprint()
    _key = _cache_key(_CACHE_FLOW_PREFIX, _fp)
    cached = cache_get(_key, _SECTOR_FLOW_TTL)
    if cached is not None:
        _SECTOR_FLOW_FAILURE = ""
        _SECTOR_FLOW_DEGRADED = ""
        _memo_set(_memo_key_str, cached)
        cache_set(_SECTOR_FLOW_LAST_KEY, cached)  # 保住「陈旧回退」窗口的新鲜度
        return cached

    # ── 失败负缓存（进程内 → 跨进程，**按通道分别记录**）：主通道被限流不得连带
    #    锚死备用通道，否则一通道抖动就把整源钉死整个窗口 ──
    failures = _channel_failures()
    if all(ch in failures for ch in _SECTOR_FLOW_CHANNELS):
        _kind = failures.get(_SECTOR_FLOW_CHANNELS[0], "connection")
        logger.info("行业资金流向全部通道近期已失败（%s），本次跳过取数", _kind)
        return _sector_flow_stale_fallback(_kind)

    # ── 取数：按通道优先级依次尝试，先成功者胜 ──
    if ak is None:
        logger.warning("akshare 模块未安装，跳过行业资金流向")
        return []

    result: list[dict[str, Any]] = []
    for channel in _SECTOR_FLOW_CHANNELS:
        _label = _SECTOR_FLOW_CHANNEL_LABELS.get(channel, channel)
        if channel in failures:
            logger.debug("行业资金流向跳过通道 %s（近期已失败: %s）", _label, failures[channel])
            continue
        try:
            result = _SECTOR_FLOW_FETCHERS[channel]()
        except _SectorFlowUnavailable as exc:
            failures[channel] = exc.kind
            logger.warning("行业资金流向通道 %s 不可用（%s），尝试下一通道", _label, exc.kind)
            continue
        if not result:
            # 取数通了但一行业也没解析出来：对下游等同取不到数，交给下一通道
            failures[channel] = "empty"
            logger.warning("行业资金流向通道 %s 返回空榜，尝试下一通道", _label)
            continue
        failures.pop(channel, None)
        break

    _save_channel_failures(failures)
    if not result:
        _kind = failures.get(_SECTOR_FLOW_CHANNELS[0], "connection")
        logger.warning("行业资金流向获取失败（全部通道不可用）")
        return _note_sector_flow_failure(_kind)

    _SECTOR_FLOW_FAILURE = ""
    _SECTOR_FLOW_DEGRADED = ""
    logger.info("行业资金流向加载完成: %d 个行业", len(result))
    cache_set(_key, result)
    cache_set(_SECTOR_FLOW_LAST_KEY, result)  # 陈旧回退基准
    _memo_set(_memo_key_str, result)
    return result


def _compute_dividend_fingerprint(codes: list[str]) -> str:
    """计算股票代码列表的指纹，用于分红数据缓存键。

    Args:
        codes: 要查询的股票代码列表

    Returns:
        12 字符十六进制指纹；空列表时返回 "empty"
    """
    if not codes:
        return "empty"
    try:
        raw = json.dumps(sorted(set(codes)), ensure_ascii=False, sort_keys=True)
        return hashlib.md5(raw.encode()).hexdigest()[:12]
    except (TypeError, ValueError):
        logger.debug("分红指纹计算失败，降级到无指纹缓存", exc_info=True)
        return "nofp"


def _calc_dividend_summary(df_data) -> dict | None:
    """从股票分红汇总 DataFrame 提取年度平均分红。

    akshare 的 stock_history_dividend() 返回聚合数据（每只股票一行），
    列包含：代码、名称、上市日期、累计股息、年均股息、分红次数 等。

    Args:
        df_data: ak.stock_history_dividend 返回的 DataFrame 子集（单只股票的一行）

    Returns:
        {avg_dividend: float, record_count: int} 或 None
    """
    if df_data is None or df_data.empty:
        return None

    try:
        # 定位"年均股息"列
        div_col = next((c for c in df_data.columns if "年均股息" in c or "每股股息" in c or "每股股利" in c), None)
        if not div_col:
            return None

        avg_div = _safe_float(df_data.iloc[0].get(div_col))
        if avg_div is None or avg_div <= 0:
            return None

        # 定位"分红次数"列
        cnt_col = next((c for c in df_data.columns if "分红次数" in c), None)
        record_count = int(df_data.iloc[0].get(cnt_col, 0)) if cnt_col else 0

        return {
            "avg_dividend": round(avg_div, 4),
            "record_count": record_count,
        }
    except (TypeError, ValueError, IndexError, KeyError):
        logger.debug("分红数据解析失败", exc_info=True)
        return None


def _fetch_all_dividends(a_codes: list[str]) -> dict[str, dict]:
    """获取多只股票的分红数据，返回 {code: summary}。

    akshare 的 stock_history_dividend() 不接受参数，返回全量数据。
    一次拉取后按代码过滤。
    """
    result: dict[str, dict] = {}

    if ak is None:
        logger.warning("akshare 模块未安装，跳过分红取数")
        return result
    _ak = ak  # 局部绑定：全局 ak 为可空（可选依赖），静态检查需要非空视图

    try:
        full_df = _ak.stock_history_dividend()
    except Exception as e:
        logger.warning("分红全量数据拉取失败: %s", e)
        return result

    if full_df is None or full_df.empty:
        logger.warning("分红全量数据为空")
        return result

    # 定位"代码"列（akshare 列名）
    code_col = next((c for c in full_df.columns if "代码" in c or c.lower() in ("code", "symbol")), None)
    name_col = next((c for c in full_df.columns if "名称" in c or "简称" in c), None)
    if code_col is None:
        logger.warning("分红数据缺少代码列，无法过滤")
        return result

    for code in a_codes:
        sub = full_df[full_df[code_col] == code]
        summary = _calc_dividend_summary(sub)
        if summary and name_col is not None:
            summary["name"] = str(sub.iloc[0].get(name_col, "")) if not sub.empty else ""
        if summary:
            result[code] = summary

    failed = len(a_codes) - len(result)
    logger.info("分红数据加载完成: %d 只成功, %d 只无数据", len(result), failed)
    return result


def get_dividend_data(codes: list[str]) -> dict[str, dict]:
    """获取股票历史分红数据，计算年均每股分红。

    调用 ak.stock_history_dividend()（全量拉取，akshare 无参数）
    获取所有股票历年分红记录，按代码过滤后汇总为年均每股股利。

    缓存策略：代码列表指纹 + 1 月 TTL 双因子失效。
      持仓/穿透代码变更 → 指纹改变 → 缓存自动失效

    Args:
        codes: 要查询的股票代码列表

    Returns:
        {code: {name: str, avg_dividend: float, years: int, record_count: int}, ...}
        失败时返回空 dict

    注意：
        - 仅对 A 股（6/0/3 开头）有意义，基金/债券代码会跳过
        - akshare 未安装或 API 超时时自动降级返回空 dict
    """
    global _DIVIDEND_FAILURE

    # ── 内存缓存 ──
    _codes_hash = hashlib.md5(json.dumps(sorted(codes), ensure_ascii=False).encode()).hexdigest()[:12]
    _memo_key_str = _memo_key("dividend", _codes_hash)
    _memo_val = _memo_get(_memo_key_str)
    if _memo_val is not None:
        _DIVIDEND_FAILURE = ""  # 缓存命中不属故障（复位模块级状态）
        return _memo_val

    # ── 指纹 + 读文件缓存 ──
    _fp = _compute_dividend_fingerprint(codes)
    _key = _cache_key(_CACHE_DIVIDEND_PREFIX, _fp)
    cached = cache_get(_key, _DIVIDEND_TTL)
    if cached is not None:
        _memo_set(_memo_key_str, cached)
        _DIVIDEND_FAILURE = ""  # 缓存命中不属故障
        return cached

    # ── lazily import akshare ──
    if ak is None:
        logger.warning("akshare 模块未安装，跳过分红数据")
        _DIVIDEND_FAILURE = "connection"
        return {}

    # ── 只处理 A 股代码 ──
    a_codes = [c for c in codes if is_a_share_code(c)]
    if not a_codes:
        logger.debug("分红数据: 无 A 股代码，跳过")
        _DIVIDEND_FAILURE = ""  # 无标的属预期内空结果，不算源故障
        return {}

    logger.info("正在获取 %d 只股票的分红历史...", len(a_codes))

    def _fetch_div():
        return _fetch_all_dividends(a_codes)

    raw = run_with_timeout(_fetch_div, timeout=60.0)
    if raw is None:
        _DIVIDEND_FAILURE = "connection"
        logger.warning("分红数据获取失败（超时/异常）")
        result: dict[str, dict] = {}
    else:
        result = raw
        _DIVIDEND_FAILURE = "" if result else "empty"
    if result:
        cache_set(_key, result)
    _memo_set(_memo_key_str, result)
    return result


def _safe_float(val: Any) -> float | None:
    """安全转 float，None/NaN/±inf/花式入参 → None。

    归一收敛于 :func:`core.num_utils.safe_num`，由它统一拦下 NaN/±inf/花式入参，
    本层不再各自判空。
    """
    v = safe_num(val, default=None)
    return float(v) if v is not None else None
