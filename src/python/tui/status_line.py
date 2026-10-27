"""主菜单页头状态行 — 五项常驻紧凑状态的组装与渲染。

每项指标全部取自本地既有单源（不新增任何外部网络调用）：

  - 上次报告时间  ← ``core/perf`` 的 ``perf_history.jsonl`` 末条记录
  - 缓存过期数    ← ``cache`` 的 ``get_cache_stats().expired``（清单预估）
  - 数据新鲜度    ← 最新价格缓存的 ``price_date``（数据日期 + 自然日龄；
    页头不引入交易日历取数——日历缓存未命中时会走 akshare 触网）
  - 数据源失败数  ← ``core/perf`` 的 ``datasource_health.jsonl`` 末条 ``fail_count``
    （**取数源**的失败个数，与 LLM 多链无关——后者见 LLM 段的链首线路名）
  - 缓存过期数    ← ``cache`` 的 ``get_cache_stats().expired``（清单预估；
    **仅在 >0 时上屏**——启动已自动清理，常态的 0 只会引人发问）
  - LLM 状态点    ← ``core/system_info.llm_status``（● 已配置 / ○ 未配置；
    多链时携带链首线路名——换序/手改优先级后回首页即见新链首）

状态行只报事实；需要用户动手时，异常段自带一句动作提示（含菜单键，见
``ACTION_TEMPLATES``），汇总为第二行缩进提示（``└ [3] 清理过期缓存 · …``）。
正常态（缓存新鲜 / 数据源失败 0 / LLM ●）不出现提示行——不向「一切正常」喊话。

契约：

  - 逐项独立容错——单项取数异常降级为「—」，不影响其余项；
  - 整行组装异常降级为 ``状态 │ —``，永不向调用方抛出；
  - TTL 记忆化（页头随主循环重绘，重取限频），配置变更与 [R] 刷新时经
    ``reset_status_memo`` 清记忆（回首页即重绘新值；亦供测试）。
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Any

from src.python.core.ansi_colors import DIM, GREEN, RESET, YELLOW
from src.python.tui.text_layout import terminal_columns, wrap_with_prefix

logger = logging.getLogger("invest")

_STATUS_TTL = 45.0  # 页头重绘频繁，缓存/健康历史等重取限频（秒）
# 数据新鲜度告警阈值（自然日）：超过则在页头用黄色提示「数据偏旧」

_memo: dict[str, Any] = {}

#: 异常态动作提示（含菜单键）：键 = 语义名，值 = 上屏短语。
#: 短语的首个括号键必须是主菜单顶层键（``[G]→L`` 这类二级入口只校验首键），
#: 由 ``test_tui_menu_status`` 对主菜单键做子集校验——菜单改键即红。
ACTION_TEMPLATES: dict[str, str] = {
    "report_missing": "[B] 生成标准报告",
    "report_interrupted": "[B] 重新生成",
    "cache_expired": "[3] 清理过期缓存",
    "freshness": "[2] 更新行情缓存",
    "degraded_sources": "[D]→V 看数据源记录",
    "llm_unconfigured": "[G]→L 配置 LLM",
}

#: 动作提示行的缩进与续行对齐（首行带 ``└`` 标记，续行对齐到正文起始列）
_ACTION_INDENT = "   └ "


class _Segment(str):
    """状态段文本：``str`` 子类，附带异常态动作短语 ``action``（正常态为空串）。

    沿用 ``str`` 是为了段文本能直接 ``" · ".join(...)`` 上屏、逐段断言（测试
    与既有单源口径不变），同时让动作与判定同处一个函数——异常条件只写一次，
    不再另设一张与取数逻辑并行的「哪个指标该按哪个键」映射表。
    """

    action: str

    def __new__(cls, text: str, action: str = "") -> "_Segment":
        segment = super().__new__(cls, text)
        segment.action = action
        return segment


def _last_report_part() -> _Segment:
    """上次报告时间（perf 历史末条时间戳）。"""
    try:
        from src.python.core.perf import load_history

        records = load_history()
        if not records:
            return _Segment("上次报告 —", ACTION_TEMPLATES["report_missing"])
        ts = str(records[-1].get("timestamp") or "")
        stamp = f"{datetime.fromisoformat(ts):%m-%d %H:%M}"
        # 中断收口落的 status=interrupted 记录：下次启动明确显示，不误判为成功
        if str(records[-1].get("status") or "") == "interrupted":
            return _Segment(f"上次报告 {stamp}（已中断）", ACTION_TEMPLATES["report_interrupted"])
        return _Segment(f"上次报告 {stamp}")
    except Exception:
        logger.debug("状态行「上次报告」取数失败，降级为 —", exc_info=True)
        return _Segment("上次报告 —")


def _cache_expired_part() -> _Segment:
    """缓存过期数（与菜单 [3] 缓存管理同一统计口径）；**仅在 >0 时上屏**。

    启动已自动清理过期缓存，常态必然是 0——把「无事可做」的 0 常驻在页头
    只会引入疑问（“为何是 0，难道没清理？”），故 0 与取数失败均不上屏，
    出现即意味着本轮运行期间确实积了过期文件。
    """
    try:
        from src.python.cache.operations import get_cache_stats
        from src.python.report.progress import SilentProgressReporter

        stats = get_cache_stats(SilentProgressReporter())
        if stats.expired:
            return _Segment(f"缓存过期 {stats.expired}", ACTION_TEMPLATES["cache_expired"])
        return _Segment("")
    except Exception:
        logger.debug("状态行「缓存过期」取数失败，本段不上屏", exc_info=True)
        return _Segment("")


def _freshness_part() -> _Segment:
    """数据新鲜度（最新一条价格缓存的数据日期与自然日龄，纯本地读数）。"""
    try:
        from src.python.cache import cache_key_from_file_name, get, get_cache_dir

        cache_dir = get_cache_dir()
        if not os.path.isdir(cache_dir):
            return _Segment("新鲜度 —", ACTION_TEMPLATES["freshness"])
        newest_key, newest_mtime = "", 0.0
        for fname in os.listdir(cache_dir):
            # 文件名带缓存键版本戳，逻辑键由 cache 包单源转换（.json / .json.gz 均收）
            key = cache_key_from_file_name(fname)
            if key is None or not key.startswith("price_"):
                continue
            try:
                mtime = os.path.getmtime(os.path.join(cache_dir, fname))
            except OSError:
                continue
            if mtime > newest_mtime:
                newest_mtime, newest_key = mtime, key
        if not newest_key:
            return _Segment("新鲜度 —", ACTION_TEMPLATES["freshness"])
        # 数据日期本地可读、日龄由本函数自算，故不按 TTL 过滤（过期的价格缓存
        # 恰是「数据偏旧」要报的对象）；`get` 的 max_age_seconds 必填，传 inf。
        payload = get(newest_key, float("inf"))
        detail = payload.get("_data") if isinstance(payload, dict) and "_data" in payload else payload
        if not isinstance(detail, dict):
            return _Segment("新鲜度 —", ACTION_TEMPLATES["freshness"])
        raw_date = detail.get("nav_date") or detail.get("price_date")
        if not raw_date:
            return _Segment("新鲜度 —", ACTION_TEMPLATES["freshness"])
        # 阈值与「偏旧」判定单源在 core.data_freshness（配置分层阈值 + 交易日口径）：
        # 页头与报告内数据质量对同一份数据给出同一结论；日历只读缓存，不触发联网
        from src.python.core.data_freshness import header_freshness

        summary = header_freshness(raw_date)
        if summary is None:
            return _Segment("新鲜度 —", ACTION_TEMPLATES["freshness"])
        date_obj = datetime.strptime(summary["date"], "%Y-%m-%d").date()
        text = f"新鲜度 {date_obj:%m-%d}（{summary['age_days']}天）"
        if summary["stale"]:
            return _Segment(f"{YELLOW}{text}{RESET}", ACTION_TEMPLATES["freshness"])
        return _Segment(text)
    except Exception:
        logger.debug("状态行「新鲜度」取数失败，降级为 —", exc_info=True)
        return _Segment("新鲜度 —")


def _degraded_part() -> _Segment:
    """数据源失败数（最近一次健康历史的失败取数源计数，无记录显示 —；与 LLM 链无关）。"""
    try:
        from src.python.core.perf import summarize_health_history

        rows = summarize_health_history(limit=1)
        if not rows:
            return _Segment("数据源失败 —")
        fails = int(rows[-1].get("fail_count") or 0)
        if fails:
            return _Segment(f"{YELLOW}数据源失败 {fails}{RESET}", ACTION_TEMPLATES["degraded_sources"])
        return _Segment("数据源失败 0")
    except Exception:
        logger.debug("状态行「数据源失败」取数失败，降级为 —", exc_info=True)
        return _Segment("数据源失败 —")


def _llm_part() -> _Segment:
    """LLM 状态点（● 已配置 / ○ 未配置，判定与 [G] → [L] LLM 设置同源）+ 多链链首线路名。

    链首名来自 llm_status()["chain_head"]（单源，仅 priority/fallback_only
    策略存在）——换序/手改优先级后回首页即见新链首，一眼验证配置已生效。
    """
    try:
        from src.python.core.system_info import llm_status

        status = llm_status()
        if status.get("configured"):
            head = status.get("chain_head")
            return _Segment(f"LLM {GREEN}●{RESET}" + (f" {head}" if head else ""))
        return _Segment(f"LLM {YELLOW}○{RESET}", ACTION_TEMPLATES["llm_unconfigured"])
    except Exception:
        logger.debug("状态行「LLM」取数失败，降级为 —", exc_info=True)
        return _Segment("LLM —")


def _render_actions(actions: list[str]) -> str:
    """异常态动作提示行（缩进的第二行；正常态不出现）。

    单行放得下就一行，超宽按显示列折行并悬挂缩进——窄终端上动作提示既不
    丢菜单键、也不硬折成锯齿；首行 ``└`` 标记取弱化层，动作正文保持正色
    （要用户动手的那句话不该比状态值更淡）。
    """
    prefix = f"{DIM}{_ACTION_INDENT}{RESET}"
    lines = wrap_with_prefix(prefix, " · ".join(actions), terminal_columns() - 2)
    return "\n" + "\n".join(lines)


def build_status_line(*, now: float | None = None) -> str:
    """组装页头状态（TTL 内复用记忆；任何异常降级为 ``状态 │ —``）。

    Args:
        now: 时间戳注入（测试用）；None 取当前时间。

    Returns:
        首行形如 ``状态 │ 上次报告 10-07 09:55 · 新鲜度 10-07（0天）·
        数据源失败 0 · LLM ● kimi-k3``（``缓存过期 N`` 只在 N>0 时出现）；
        有异常段时追加第二行动作提示（``└ [3] 清理过期缓存 · [2] 更新行情缓存``，
        按终端宽度折行），全部正常时行尾干净、无第二行。
    """
    ts = time.time() if now is None else float(now)
    cached = _memo.get("line")
    if cached is not None and ts - float(_memo.get("ts", 0.0)) < _STATUS_TTL:
        return str(cached)
    try:
        parts: list[_Segment] = [
            _last_report_part(),
            _cache_expired_part(),
            _freshness_part(),
            _degraded_part(),
            _llm_part(),
        ]
        line = "状态 │ " + " · ".join(part for part in parts if part)
        # 动作提示只在需要动作时出现。语义段按需上屏（缓存过期段仅异常时出现），
        # 上屏的段不截断——ANSI 截断风险与语义损失均高于版式收益；提示行按宽度折行。
        actions = [part.action for part in parts if part.action]
        if actions:
            line += _render_actions(actions)
    except Exception:
        logger.debug("状态行组装失败，降级显示", exc_info=True)
        line = "状态 │ —"
    _memo["line"] = line
    _memo["ts"] = ts
    return line


def reset_status_memo() -> None:
    """清空状态行记忆（配置变更 / [R] 刷新后回首页即重绘；亦供测试用）。"""
    _memo.clear()
