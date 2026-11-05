"""事件窗对照表数据编排（event_impact_panel 数据侧）。

职责（迭代「事件表编排」）：既有新闻关联链路输出（只读）→ ``event_item`` 组装 →
窗口行情经注入的 chain 网关取数 → ``analysis.event_window_impact.compute_event_impact``
纯计算 → 事件行（available）+ 降级清单（告警计数）。

纪律：
- 只读 ``build_news_data`` 落盘字段（title/intro/url/ctime/matched_keywords/
  llm_analysis），不新建第二份新闻元数据存储；文本极性从 ``llm_analysis``
  标记解析（与新闻表着色同口径）。
- 行情/基准取数全部由调用方注入（chain 网关），本模块零直连、零缓存直写。
- 数据不足 → 该事件入降级清单不出行（reason 呈现），事件表空 →
  ``available=False`` 供上层隐藏章节。
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Any, Callable

from src.python.analysis.event_window_impact import (
    WINDOW_AFTER,
    WINDOW_BEFORE,
    compute_event_impact,
)
from src.python.core.code_utils import is_a_share_code, is_a_share_stock
from src.python.core.log_dedupe import log_throttled
from src.python.core.perf import SLOW_SPAN_WARN_SECONDS

logger = logging.getLogger("invest")

__all__ = [
    "extract_text_polarity",
    "parse_event_date",
    "build_event_rows",
    "build_event_impact_panel",
    "build_event_impact_view",
    "write_event_impact_footer",
    "EVENT_TABLE_HEADER",
    "LIMITATIONS_NOTE",
]

#: 新闻发布时间可解析格式（按上游聚合源实测：秒级 / 分钟级 / 仅日期）
_CTIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")

#: 单次事件表行数上限（防极端召回爆炸，超出计入 skipped）
MAX_EVENT_ROWS = 50


def extract_text_polarity(item: dict[str, Any]) -> str | None:
    """从 llm_analysis 文本解析文本极性（与新闻表着色标记同口径）。

    Returns:
        利好 / 利空 / 中性（有关联判定但无方向标记）/ None（未判定）。
    """
    text = item.get("llm_analysis")
    if not isinstance(text, str) or not text.strip():
        return None
    if "[利好]" in text:
        return "利好"
    if "[利空]" in text:
        return "利空"
    return "中性"


def parse_event_date(ctime: Any) -> str | None:
    """新闻发布时间 → YYYY-MM-DD 事件日期；不可解析返回 None（先决门槛口径）。"""
    raw = str(ctime or "").strip()
    if not raw:
        return None
    for fmt in _CTIME_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


#: 名称里可安全剥离的产品后缀（去后缀后的剩余名才作为别名，避免把 ETF/基金当个股）
_NAME_SUFFIXES = ("ETF", "LOF", "QDII", "基金", "指数", "联接", "增强", "发起式", "场内", "场外")

#: 代码市场前缀（指数/行情链两种写法都会出现在新闻与关联关键词里）
_CODE_MARKET_PREFIX = {"6": "sh", "9": "sh", "0": "sz", "3": "sz", "2": "sz"}


def _code_variants(code: str) -> list[str]:
    """代码写法变体：裸码 + 小写市场前缀（``600519`` / ``sh600519``）。"""
    bare = str(code or "").strip()
    if not bare:
        return []
    prefix = _CODE_MARKET_PREFIX.get(bare[0])
    return [bare, f"{prefix}{bare}"] if prefix else [bare]


def _name_alias(name: str) -> str:
    """名称 → 常用简称（去掉 ETF/基金/指数/联接 等产品后缀与全角括号段）。"""
    alias = str(name or "").strip()
    for sep in ("（", "("):
        if sep in alias:
            alias = alias.split(sep)[0]
    for suffix in _NAME_SUFFIXES:
        if alias.upper().endswith(suffix.upper()):
            alias = alias[: -len(suffix)]
    alias = alias.strip()
    return alias if len(alias) >= 2 else ""


def _build_keyword_index(holdings: list[Any], penetrated_assets: list[dict] | None) -> dict[str, list[tuple[str, str]]]:
    """关键词 → [(可取行情的 A 股代码, 命中层级)]；层级 ∈ {"品种", "行业"}。

    索引三类键（同一代码可经多条键命中，按层级保序去重）：
      1. **品种直指**：持仓/穿透资产的名称与简称、代码裸码与带市场前缀写法；
      2. **行业直指**：该品种所属板块名（``classify_sector``）；
      3. **行业关键词**：``sector_keywords()`` 中指向同一板块的词（如「白酒」「芯片」），
         命中即视为行业级关联——把「新闻讲行业、组合正好暴露在该行业」的情形纳入事件窗，
         这类新闻此前整条计入 unmatched。

    仅收录名称+代码双维判定为 A 股的直接持仓与穿透 A 股代码；基金等无日频股票
    行情的品种不入索引（其命中计入 unmatched，不硬算）。
    """
    from src.python.report.penetration import classify_sector, sector_keywords

    lookup: dict[str, list[tuple[str, str]]] = {}
    sector_kw = sector_keywords()

    def _add(key: str | None, code: str, level: str) -> None:
        entries = lookup.setdefault(key, []) if key else None
        if entries is None:
            return
        if (code, level) not in entries:
            entries.append((code, level))

    def _index(code: str, name: str) -> None:
        """登记一个 A 股代码：品种名/简称/代码变体 + 所属板块与板块关键词。"""
        _add(name, code, "品种")
        _add(_name_alias(name), code, "品种")
        for variant in _code_variants(code):
            _add(variant, code, "品种")
        sector = classify_sector(name, code)
        if not sector or sector == "--":
            return
        _add(sector, code, "行业")
        for keyword, target in sector_kw.items():
            if target == sector:
                _add(keyword, code, "行业")

    for holding in holdings or []:
        name = str(getattr(holding, "name", "") or "")
        code = str(getattr(holding, "code", "") or "")
        if name and code and is_a_share_stock(name, code):
            _index(code, name)
    for asset in penetrated_assets or []:
        if not isinstance(asset, dict):
            continue
        codes = [c for c in (asset.get("codes") or []) if isinstance(c, str) and is_a_share_code(c)]
        if codes:
            _index(codes[0], str(asset.get("name") or ""))
    return lookup


def build_event_rows(
    holdings: list[Any],
    news_data: list[dict[str, Any]],
    penetrated_assets: list[dict] | None = None,
    *,
    fetch_bars: Callable[[str], list[dict] | Any | None],
    fetch_index: Callable[[str], list[dict] | Any | None],
    benchmark_code_for: Callable[[dict[str, Any]], str | None],
    max_rows: int = MAX_EVENT_ROWS,
) -> dict[str, Any]:
    """新闻关联输出 → 事件窗行（经注入取数 + 纯计算，全离线可测）。

    Args:
        holdings: 持仓清单（Holding 或等价属性对象）。
        news_data: ``build_news_data`` 输出（只读）。
        penetrated_assets: 穿透资产 [{name, codes}]（可选）。
        fetch_bars: 品种窗口行情获取（生产接 chain 网关；测试注入替身）。
        fetch_index: 基准指数行情获取（同上）。
        benchmark_code_for: 品种 → 基准指数码（生产接三阶基准映射）。

    Returns:
        {"available": bool, "events": [...], "degraded": [...], "skipped": {...}}

        ``skipped`` 口径：``unmatched`` 是「未匹配到品种」的**合计**（口径兼容），
        ``not_in_holdings``（关键词不在持仓/穿透索引）与 ``no_keywords``
        （新闻关联环节召回为 0）是它的两个成因细分，二者之和即 ``unmatched``。
    """
    skipped = {"bad_date": 0, "unmatched": 0, "no_keywords": 0, "not_in_holdings": 0, "capped": 0}
    events: list[dict[str, Any]] = []
    degraded: list[dict[str, Any]] = []
    index = _build_keyword_index(holdings, penetrated_assets)
    # 同一批事件反复命中同一代码/基准时只取一次；失败不缓存，保留下次重试语义。
    bars_memo: dict[str, Any] = {}
    index_memo: dict[str, Any] = {}

    for item in news_data or []:
        if len(events) >= max_rows:
            skipped["capped"] += 1
            continue
        event_date = parse_event_date(item.get("ctime"))
        if event_date is None:
            skipped["bad_date"] += 1
            continue
        keywords = [k for k in (item.get("matched_keywords") or []) if isinstance(k, str)]
        if not keywords:
            # 「未关联到任何关键词」与「关联了但不在持仓索引」是两类不同问题：
            # 前者是新闻关联环节召回为 0，后者是索引（持仓/穿透关键词）没覆盖到。
            skipped["no_keywords"] += 1
            continue
        hit_codes: list[tuple[str, str]] = []  # (code, 命中关键词展示文案)
        for kw in keywords:
            for code, level in index.get(kw, []):
                # 行业级关联在关键词后缀标注，读者能分辨「新闻讲的是该品种」还是「讲它所在行业」
                label = f"{kw}（行业）" if level == "行业" else kw
                if (code, label) not in hit_codes:
                    hit_codes.append((code, label))
        if not hit_codes:
            skipped["unmatched"] += 1
            skipped["not_in_holdings"] += 1
            continue

        polarity = extract_text_polarity(item)
        for code, keyword in hit_codes:
            if len(events) >= max_rows:
                skipped["capped"] += 1
                continue
            index_code = benchmark_code_for({"code": code})
            try:
                if code not in bars_memo:
                    bars_memo[code] = fetch_bars(code)
                asset_bars = bars_memo[code]
                if index_code:
                    if index_code not in index_memo:
                        index_memo[index_code] = fetch_index(index_code)
                    index_bars = index_memo[index_code]
                else:
                    index_bars = None
                impact = compute_event_impact(
                    event_date,
                    asset_bars,
                    index_bars,
                    text_polarity=polarity,
                    asset_code=code,
                )
            except Exception as exc:  # 取数/计算异常 → 降级不出行（不阻塞报告）
                logger.warning("事件窗行降级 [%s %s]: %s", code, event_date, exc)
                degraded.append({"code": code, "event_date": event_date, "reason": f"取数异常: {type(exc).__name__}"})
                continue
            if not impact.get("available"):
                degraded.append({"code": code, "event_date": event_date, "reason": impact.get("reason") or "不可用"})
                continue
            events.append(
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "ctime": item.get("ctime"),
                    "media_name": item.get("media_name"),
                    "intro": item.get("intro"),
                    "matched_keyword": keyword,
                    "polarity": polarity,
                    "code": code,
                    **impact,
                }
            )

    result = {
        "available": bool(events),
        "events": events,
        "degraded": degraded,
        "skipped": skipped,
        "degraded_count": len(degraded),
    }
    log_throttled(
        logger,
        "event_rows_ready",
        "事件窗事件表: 可出行 %d 条、降级 %d 条、跳过 %s",
        len(events),
        len(degraded),
        skipped,
    )
    return result


# ── 契约装配 / 双端单源视图 / 分歧例提示词块（report 双端 + LLM 注入） ─────

#: 事件对照表列头（HTML partial 与 Excel 页签共用，双端逐字节同文）
EVENT_TABLE_HEADER = (
    "事件日",
    "交易日",
    "新闻标题",
    "品种",
    "关键词",
    "文本极性",
    "品种收益",
    "超额收益",
    "方向",
    "比对",
)

#: 口径常驻标注（视图与提示词块同源渲染，双端同现）
LIMITATIONS_NOTE = (
    "口径：事件日为交易日取当日、否则顺延至其后首个交易日；窗口 = 映射交易日 ±5 交易日，"
    "收益 = 前 1 日收盘 → 后 5 日收盘；行情轴右端不足 5 个交易日时（盘中运行常态）按实际可用"
    "交易日截断计算并在行摘要标注「未满窗」；窗口内停牌/缺失按 LOCF 前向填充（缺失超限该事件降级不出行）；"
    "超额收益 = 品种收益 − 基准指数收益；文本极性取新闻 LLM 关联判定标记（利好/利空/中性），"
    "中性与未判定不参与方向比对。"
)


def _fmt_pct(value: Any) -> str:
    """收益 → 带符号百分比字符串（视图与提示词块共用，双端同文）。"""
    try:
        return f"{float(value) * 100:+.2f}%"
    except (TypeError, ValueError):
        return "—"


def _short_title(title: str, limit: int = 32) -> str:
    return title if len(title) <= limit else title[: limit - 1] + "…"


#: 无 K 线数据的基准（债券指数）：中证全债等在本项目 K 线链三源皆空
#: （实测 tencent SSL 握手 10s 超时 + 东方财富/新浪 0 条），事件窗对其不取 K 线，
#: 直接按缺基准降级——每轮省一次 10s 白等；数据源能力变化时可从集合移除恢复。
_NO_KLINE_BENCHMARKS = frozenset({"sh000012"})


#: 事件窗行情取数窗口下限（自然日）：与历史行为一致，短窗新闻不额外拉数
HISTORY_DAYS_FLOOR = 365
#: 上限：老新闻再多也只拉三年，避免单轮把取数预算打穿
HISTORY_DAYS_CAP = 1095


def history_days_for(news_data: list[dict[str, Any]] | None, today: date | None = None) -> int:
    """按最早事件日推导行情取数窗口（自然日），保证事件日落在行情轴内。

    固定 365 天的旧口径在「新闻比窗口更早」时会让事件日落在行情轴之外，
    整条按「映射交易日不在行情轴」降级——索引扩面后这类降级占到降级总数的大部分。
    这里按最早事件日回推：窗口 = 事件日回看天数 + 后窗余量（``WINDOW_AFTER`` 两手数）
    + 30 天缓冲，再夹在 [``HISTORY_DAYS_FLOOR``, ``HISTORY_DAYS_CAP``] 内。

    Args:
        news_data: 新闻列表（取 ``ctime`` 解析出的最早事件日；不可解析的忽略）。
        today: 基准日（缺省今天），测试注入用。

    Returns:
        取数窗口天数（自然日），恒 ≥ ``HISTORY_DAYS_FLOOR``。
    """
    base = today or date.today()
    event_dates: list[date] = []
    for item in news_data or []:
        parsed = parse_event_date(item.get("ctime"))
        if not parsed:
            continue
        try:
            event_dates.append(datetime.strptime(parsed, "%Y-%m-%d").date())
        except ValueError:
            continue
    if not event_dates:
        return HISTORY_DAYS_FLOOR
    span = (base - min(event_dates)).days + WINDOW_AFTER * 2 + 30
    return max(HISTORY_DAYS_FLOOR, min(HISTORY_DAYS_CAP, span))


def _make_default_index_fetcher(days: int = HISTORY_DAYS_FLOOR) -> Callable[[str], Any]:
    """事件窗默认基准取数：同码 memo + 无 K 线品种跳过 + 单路慢告警。"""
    from src.python.fetcher.index import fetch_index_history

    memo: dict[str, Any] = {}

    def _fetch(code: str) -> Any:
        if code in _NO_KLINE_BENCHMARKS:
            logger.info("[event_impact] 基准 %s 无 K 线数据（债券指数），按缺基准降级、不取数", code)
            return []
        if code not in memo:
            started = time.perf_counter()
            memo[code] = fetch_index_history(code, days=days)
            elapsed = time.perf_counter() - started
            if elapsed >= SLOW_SPAN_WARN_SECONDS:
                logger.warning(
                    "[event_impact] 基准指数取数偏慢：%s %.2fs（阈值 %.0fs）——慢/空的基准会拖住事件窗表",
                    code,
                    elapsed,
                    SLOW_SPAN_WARN_SECONDS,
                )
        return memo[code]

    return _fetch


def build_event_impact_view(contract: dict[str, Any] | None) -> dict[str, Any]:
    """契约 → 双端共用展示视图（全部字段为预格式化字符串，双端逐字节同文）。

    Returns:
        {"available", "reason", "title_summary", "summary_lines",
         "event_header", "event_rows", "degraded_line",
         "limitations_note", "hint_line"}
    """
    view: dict[str, Any] = {
        "available": False,
        "reason": "",
        "title_summary": "事件窗对照数据不足",
        "summary_lines": [],
        "event_header": list(EVENT_TABLE_HEADER),
        "event_rows": [],
        "degraded_line": "",
        "limitations_note": LIMITATIONS_NOTE,
        "hint_line": (
            "开关开启且新闻获取成功后自动装配；行情或基准缺失、"
            "无品种关联的事件会降级/跳过；行情轴右端不足 5 个交易日时按实际可用日截断（摘要标注未满窗条数）。"
        ),
    }
    if not contract or not contract.get("available"):
        view["reason"] = (contract or {}).get("reason") or "新闻事件与持仓的事件窗对照数据不足"
        return view

    events = list(contract.get("events") or [])
    counts = dict(contract.get("match_counts") or {})
    bench = contract.get("benchmark") or {}
    window = contract.get("window") or {}
    skipped = contract.get("skipped") or {}
    view["available"] = True
    view["title_summary"] = (
        f"{len(events)} 个事件（一致 {counts.get('一致', 0)} / 分歧 {counts.get('分歧', 0)}"
        f" / 中性不判 {counts.get('中性不判', 0)}）"
    )
    bench_label = "—"
    if bench.get("code"):
        bench_label = f"{bench.get('name')}（{bench.get('code')}，来源 {bench.get('source')}）"
    view["summary_lines"] = [
        (
            f"事件窗口 = 映射交易日 ±{window.get('before', WINDOW_BEFORE)} 交易日"
            f"（后窗 {window.get('after', WINDOW_AFTER)} 交易日）；基准：{bench_label}"
        ),
        (
            f"新闻 {contract.get('news_total', 0)} 条（极性已判定 "
            f"{contract.get('polarity_known', 0)} 条） → 可出行 {len(events)} 条；"
            f"降级 {contract.get('degraded_count', 0)} 条"
            f"（跳过：无品种关联 {skipped.get('not_in_holdings', 0)} 条、"
            f"无关键词召回 {skipped.get('no_keywords', 0)} 条、"
            f"日期不可解析 {skipped.get('bad_date', 0)} 条）"
        ),
    ]
    shifted_events = [e for e in events if e.get("anchor_shifted")]
    if shifted_events:
        view["summary_lines"].append(
            f"其中 {len(shifted_events)} 条事件日（多为当日）行情尚未落地，已按行情轴末日对齐后计算，"
            "读数请按「事件日顺延至最近交易日」理解。"
        )
    partial_events = [e for e in events if e.get("window_partial")]
    if partial_events:
        shortest = min(int(e.get("window_after_actual") or 0) for e in partial_events)
        view["summary_lines"].append(
            f"其中 {len(partial_events)} 条后窗未满（行情轴止于最近交易日，最短 {shortest}/{window.get('after', WINDOW_AFTER)} 日），"
            "按实际可用交易日截断计算"
        )
    for event in events:
        view["event_rows"].append(
            [
                str(event.get("event_date") or ""),
                str(event.get("anchor_date") or ""),
                _short_title(str(event.get("title") or "")),
                str(event.get("code") or ""),
                str(event.get("matched_keyword") or ""),
                str(event.get("polarity") or "—"),
                _fmt_pct(event.get("asset_return")),
                _fmt_pct(event.get("excess_return")),
                str(event.get("direction") or "—"),
                str(event.get("match") or "—"),
            ]
        )
    degraded = contract.get("degraded") or []
    if degraded:
        reasons: dict[str, int] = {}
        for item in degraded:
            reason = str(item.get("reason") or "未知")
            reasons[reason] = reasons.get(reason, 0) + 1
        parts = "、".join(f"{r}×{c}" for r, c in sorted(reasons.items(), key=lambda x: (-x[1], x[0])))
        view["degraded_line"] = f"降级 {len(degraded)} 条（该事件不出行）：{parts}"
    return view


def _build_prompt_block(view: dict[str, Any]) -> str:
    """分歧例提示词块（契约构建期渲染一次，报告展示与 LLM 提示词同源）。

    只收「比对 = 分歧」行——召回判据是事件表中全部分歧例 100% 进块；
    无分歧/视图不可用 → 空串（附录零贡献，逐字节回退，指纹条件并入）。
    """
    if not view.get("available"):
        return ""
    divergent = [row for row in (view.get("event_rows") or []) if row and row[-1] == "分歧"]
    if not divergent:
        return ""
    lines = ["【事件窗对照·分歧例（文本判定 vs 事件窗方向）】"]
    lines.extend(view.get("summary_lines") or [])
    lines.append(f"分歧例（{len(divergent)} 条，与报告事件表同源）：")
    for row in divergent:
        lines.append(
            f"  {row[0]}（交易日 {row[1]}） {row[3]} 关键词 {row[4]}"
            f" 文本={row[5]} 方向={row[8]} 收益 {row[6]} 超额 {row[7]}｜{row[2]}"
        )
    lines.append(str(view.get("limitations_note") or ""))
    return "\n".join(lines)


def build_event_impact_panel(
    holdings: list[Any],
    news_data: list[dict[str, Any]],
    penetrated_assets: list[dict] | None = None,
    *,
    comparison_indices: dict[str, str] | None = None,
    benchmark_override: str | None = None,
    benchmark_text_getter: Callable[[str], Any] | None = None,
    fetch_bars: Callable[[str], Any] | None = None,
    fetch_index: Callable[[str], Any] | None = None,
    max_rows: int = MAX_EVENT_ROWS,
) -> dict[str, Any]:
    """装配「事件窗对照」数据契约（只读新闻关联输出，绝不回写）。

    取数默认接生产网关（chain 增量历史 + 指数双链路，测试注入替身）；
    基准经 ``resolve_benchmark_index`` 三阶映射（配置覆盖 → 持仓基准文本 →
    宽基默认），解析失败不阻断——逐事件按缺基准降级不出行。

    Returns:
        契约 dict（``pipeline_data["event_impact_data"]`` 形状）：
          - available / reason / events / degraded / degraded_count / skipped
          - news_total / polarity_known / match_counts / benchmark / window
          - limitations_note / prompt_block（分歧例块，空 = 附录零贡献）
    """
    from src.python.analysis.benchmark_index_resolver import resolve_benchmark_index

    # 行情窗口按「最早事件日」自适应：固定 365 天会把更早的新闻整条判成
    # 「映射交易日不在行情轴」而降级（索引扩面后这是降级的主因）
    history_days = history_days_for(news_data)
    if fetch_bars is None:
        from src.python.fetcher.chain_incremental import fetch_with_incremental_fallback

        _bars_memo: dict[str, Any] = {}

        def _default_fetch_bars(code: str) -> Any:
            if code not in _bars_memo:
                _bars_memo[code] = fetch_with_incremental_fallback("history_stock", code, days=history_days)
            return _bars_memo[code]

        fetch_bars = _default_fetch_bars

    if fetch_index is None:
        fetch_index = _make_default_index_fetcher(history_days)

    if benchmark_text_getter is None:
        from src.python.fetcher.fund import fetch_fund_benchmark

        _benchmark_memo: dict[str, Any] = {}

        def _default_benchmark_text(code: str) -> Any:
            if code not in _benchmark_memo:
                _benchmark_memo[code] = fetch_fund_benchmark(code)
            return _benchmark_memo[code]

        benchmark_text_getter = _default_benchmark_text

    holdings_map = [
        {
            "code": str(getattr(h, "code", "") or ""),
            "name": str(getattr(h, "name", "") or ""),
            "cost": float(getattr(h, "shares", 0) or 0) * float(getattr(h, "cost_price", 0) or 0),
        }
        for h in (holdings or [])
    ]
    resolved: dict[str, Any] | None
    try:
        resolved = resolve_benchmark_index(
            holdings_map,
            override=benchmark_override,
            comparison_indices=comparison_indices,
            benchmark_text_getter=benchmark_text_getter,
        )
    except Exception:
        logger.warning("[event_impact] 基准指数映射失败，事件按缺基准逐条降级", exc_info=True)
        resolved = None

    raw = build_event_rows(
        holdings,
        news_data,
        penetrated_assets,
        fetch_bars=fetch_bars,
        fetch_index=fetch_index,
        benchmark_code_for=(lambda _row: str(resolved["code"])) if resolved else (lambda _row: None),
        max_rows=max_rows,
    )
    events = raw["events"]
    match_counts: dict[str, int] = {}
    for event in events:
        key = str(event.get("match") or "—")
        match_counts[key] = match_counts.get(key, 0) + 1
    news_list = list(news_data or [])
    contract: dict[str, Any] = {
        **raw,
        "available": bool(events),
        "reason": "" if events else "无可用事件（新闻为空/窗口未走完/行情或基准缺失）",
        "news_total": len(news_list),
        "polarity_known": sum(1 for item in news_list if extract_text_polarity(item)),
        "match_counts": match_counts,
        "benchmark": resolved,
        "window": {"before": WINDOW_BEFORE, "after": WINDOW_AFTER},
        "limitations_note": LIMITATIONS_NOTE,
        "prompt_block": "",
    }
    view = build_event_impact_view(contract)
    contract["prompt_block"] = _build_prompt_block(view)
    log_throttled(
        logger,
        "event_impact_assembled",
        "[event_impact] 事件表装配完成: 可出行 %d / 降级 %d / 跳过 %s / 比对 %s / 分歧例块 %d 字符",
        len(events),
        contract["degraded_count"],
        contract["skipped"],
        contract["match_counts"],
        len(contract["prompt_block"]),
    )
    return contract


def write_event_impact_footer(ws: Any, event_impact_data: dict[str, Any] | None, *, start_row: int) -> None:
    """在财经新闻页签尾部写入「事件窗对照」区块（与 HTML partial 消费同一份 view 字符串）。

    事件窗对照已并入财经新闻章（注册表不占独立条目、不消耗连续编号），
    Excel 端对应为财经新闻页签尾部区块而非独立页签；``start_row`` 为区块首行
    （新闻内容之后留一空行）。区块标题与 partial 章内标题同为「事件窗对照」。
    """
    from src.python.report.excel_writer import (
        write_block_title,
        _write_placeholder,
        auto_width,
        write_data_row,
        write_header_row,
    )

    view = build_event_impact_view(event_impact_data)
    _ncols = len(EVENT_TABLE_HEADER)
    row = write_block_title(ws, start_row, "事件窗对照", ncols=_ncols)

    if not view["available"]:
        _write_placeholder(ws, view["reason"], row=row + 1, max_cols=_ncols)
        auto_width(ws)
        logger.info("事件窗对照区块：数据不足，写入占位")
        return

    # ── 1. 口径摘要 ──
    for line in view["summary_lines"]:
        row = write_data_row(ws, row, [line] + [""] * (_ncols - 1))

    # ── 2. 事件窗对照表（一致/分歧列）+ 口径标注（同现） ──
    row += 1
    row = write_block_title(ws, row, "事件窗对照表", ncols=_ncols)
    row = write_header_row(ws, row, view["event_header"])
    for cells in view["event_rows"]:
        row = write_data_row(ws, row, cells)
    if view["degraded_line"]:
        row = write_data_row(ws, row, [view["degraded_line"]] + [""] * (_ncols - 1))
    row = write_data_row(ws, row, [view["limitations_note"]] + [""] * (_ncols - 1))

    auto_width(ws)
