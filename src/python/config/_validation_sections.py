"""报告章节与内容域配置校验（章节顺序、基准、对比池、再平衡、纪律、历史走势）。"""

from __future__ import annotations

from ._validation_common import (  # noqa: F401 — 共用原语
    _FETCH_MODES,
    _MISSING,
    _section,
)

import logging
import re

from src.python.core.code_utils import is_six_digit_code
from src.python.core.registry import get_report_section_keys
from src.python.analysis.drawdown_events import MIN_SPAN

logger = logging.getLogger("invest")


def _validate_user_fund_benchmarks(config: dict, issues: int) -> int:
    ufb, issues = _section(config, "user_fund_benchmarks", dict, "自定义基准将忽略", issues)
    if ufb is _MISSING:
        return issues
    for code, benchmark in ufb.items():
        if not isinstance(code, str) or not code.strip():
            logger.warning("config.json user_fund_benchmarks 中存在非字符串或空字符串的基金代码 %r，该项将被忽略", code)
            issues += 1
            continue
        if not isinstance(benchmark, str) or not benchmark.strip():
            logger.warning(
                "config.json user_fund_benchmarks.%s = %r 不是有效的基准名称（应为字符串），该项将被忽略",
                code,
                benchmark,
            )
            issues += 1
    return issues


def _validate_fund_fee_fallback(config: dict, issues: int) -> int:
    """校验申赎费率配置兑底表（fund_fee_fallback，非法条目运行期按未知丢弃）。"""
    fb, issues = _section(config, "fund_fee_fallback", dict, "费率兑底将被忽略", issues)
    if fb is _MISSING:
        return issues
    from src.python.analysis.fee_schedule_model import build_config_fee_schedules

    for code, entry in fb.items():
        if not (isinstance(code, str) and is_six_digit_code(code)):
            logger.warning("config.json fund_fee_fallback 键 %r 不是 6 位基金代码，该条忽略", code)
            issues += 1
            continue
        if build_config_fee_schedules(entry) is None:
            logger.warning(
                "config.json fund_fee_fallback.%s 非法（purchase_rate 为 0≤r<1 小数；"
                "redemption_tiers 按交易日上界升序、末档 max_days 为 null、rate 为 0≤r<1 小数），该条忽略",
                code,
            )
            issues += 1
    return issues


def _validate_whatif_benchmark_index(config: dict, issues: int) -> int:
    """What-if 业绩基准指数覆盖值：非空时必须是合法指数代码（否则运行期回落默认）。"""
    value = config.get("whatif_benchmark_index")
    if value is None or value == "":
        return issues
    from src.python.core.code_utils import is_index_code

    if not isinstance(value, str) or not is_index_code(value.strip()):
        logger.warning(
            "config.json whatif_benchmark_index = %r 不是合法指数代码（如 sh000300），将回落自动映射",
            value,
        )
        issues += 1
    return issues


def _validate_report_section_order(config: dict, issues: int) -> int:
    order, issues = _section(config, "report_section_order", dict, "将使用默认顺序", issues)
    if order is _MISSING:
        return issues
    valid_keys = get_report_section_keys()
    seen_numbers: set[int] = set()
    unknown_keys: list[str] = []
    for key, num in order.items():
        if key == "llm_usage":
            logger.warning("config.json report_section_order 中不应包含 llm_usage")
            issues += 1
            continue
        if key not in valid_keys:
            logger.warning("config.json report_section_order 中存在未知的模块标识 %r（已自动清理）", key)
            issues += 1
            unknown_keys.append(key)
            continue
        try:
            n = int(num)
            if n < 1:
                logger.warning("config.json report_section_order.%s = %s 不是正数", key, num)
                issues += 1
                continue
        except (ValueError, TypeError):
            logger.warning("config.json report_section_order.%s = %s 不是有效整数", key, num)
            issues += 1
            continue
        if n in seen_numbers:
            logger.warning("config.json report_section_order 中存在重复序号 %s（%s）", n, key)
            issues += 1
        else:
            seen_numbers.add(n)
    # 未知键从内存配置剔除：注册表没有对应条目时它既不参与排序也不占号，
    # 留着会让「已配置在前/未配置排尾」的合并产生错位预期；文件层漂移仍计 1
    # 问题提示同步 config.json（校验不回写文件）。
    for key in unknown_keys:
        order.pop(key, None)
    return issues


def _validate_benchmark_indices(config: dict, issues: int) -> int:
    """验证 history.benchmark_indices 配置。"""
    history = config.get("history", {})
    if not isinstance(history, dict):
        return issues
    bm = history.get("benchmark_indices")
    if bm is None:
        return issues  # 缺失时使用默认值，正常
    if not isinstance(bm, dict):
        logger.warning("config.json history.benchmark_indices = %r 不是对象(dict)，将使用默认值", bm)
        return issues + 1
    for key, val in bm.items():
        if not isinstance(key, str) or len(key) < 3:
            logger.warning("config.json history.benchmark_indices 中存在无效键 %r，将被忽略", key)
            issues += 1
        if not isinstance(val, str):
            logger.warning("config.json history.benchmark_indices.%s = %r 不是字符串", key, val)
            issues += 1
    return issues


def _validate_history_fetch_mode(config: dict, issues: int) -> int:
    """验证 history.fetch_mode 配置（历史走势获取模式三态）。"""
    history = config.get("history", {})
    if not isinstance(history, dict):
        return issues
    mode = history.get("fetch_mode")
    if mode is None:
        return issues  # 缺失时使用默认值，正常
    if not isinstance(mode, str) or mode not in _FETCH_MODES:
        logger.warning(
            "config.json history.fetch_mode = %r 非法（应为 off/prompt/auto），将使用默认值 auto",
            mode,
        )
        return issues + 1
    return issues


def _validate_history_lookback_days(config: dict, issues: int) -> int:
    """验证 history.lookback_days 配置（历史走势取数窗口天数）。

    下限绑定 MIN_SPAN（回撤分析所需最少交易日），低于下限时回撤分析
    将判定数据不足；上限 365 对齐历史 K 线数据源最多返回条数。
    """
    history = config.get("history", {})
    if not isinstance(history, dict):
        return issues
    lookback = history.get("lookback_days")
    if lookback is None:
        return issues  # 缺失时使用默认值 90，正常
    try:
        days = int(lookback)
    except (ValueError, TypeError):
        logger.warning("config.json history.lookback_days = %r 不是有效整数，将使用默认值 90", lookback)
        return issues + 1
    if days < MIN_SPAN:
        logger.warning(
            "config.json history.lookback_days = %s 低于回撤分析所需最少 %d 个交易日，回撤分析将判定数据不足",
            days,
            MIN_SPAN,
        )
        issues += 1
    if days > 365:
        logger.warning("config.json history.lookback_days = %s 超过上限 365，历史 K 线数据源最多返回 365 条", days)
        issues += 1
    return issues


def _validate_comparison_indices(config: dict, issues: int) -> int:
    """验证 comparison_indices 配置。"""
    ci, issues = _section(config, "comparison_indices", dict, "对比指数池将使用默认值", issues)
    if ci is _MISSING:
        return issues
    for key, val in ci.items():
        if not isinstance(key, str) or len(key) < 3:
            logger.warning("config.json comparison_indices 中存在无效键 %r，将被忽略", key)
            issues += 1
        if not isinstance(val, str):
            logger.warning("config.json comparison_indices.%s = %r 不是字符串", key, val)
            issues += 1
    return issues


def _validate_comparison_candidates(config: dict, issues: int) -> int:
    """验证 comparison_candidates 候选基金代码列表。

    - 非列表 → 告警（候选比较子表按空处理）
    - 项非 6 位数字 → 告警（该项忽略）
    - 超过 10 只 → 告警（运行期截断前 10）
    """
    raw = config.get("comparison_candidates")
    if raw is None:
        return issues
    if not isinstance(raw, list):
        logger.warning("config.json comparison_candidates = %r 不是列表，将按空处理", raw)
        return issues + 1
    code_re = re.compile(r"^\d{6}$")
    for idx, item in enumerate(raw):
        if isinstance(item, str) and code_re.match(item.strip()):
            continue
        if isinstance(item, (int, float)):
            continue  # 数值型可经 get_comparison_candidates 归一化为 6 位码
        logger.warning("config.json comparison_candidates[%d] = %r 非法（应为 6 位基金代码），忽略", idx, item)
        issues += 1
    if len(raw) > 10:
        logger.warning("config.json comparison_candidates 超过 10 只上限，运行期仅比较前 10 只")
        issues += 1
    return issues


def _validate_rebalance_config(config: dict, issues: int) -> int:
    """验证 rebalance 配置段。"""
    rb, issues = _section(config, "rebalance", dict, "再平衡配置无效，将使用默认值", issues)
    if rb is _MISSING:
        return issues
    threshold = rb.get("threshold")
    if threshold is not None:
        try:
            t = float(threshold)
            if t <= 0 or t >= 1:
                logger.warning("config.json rebalance.threshold = %s 应在 0~1 之间，将使用默认值 0.15", t)
                issues += 1
        except (ValueError, TypeError):
            logger.warning("config.json rebalance.threshold = %r 不是有效数字，将使用默认值 0.15", threshold)
            issues += 1
    deviation = rb.get("deviation_threshold")
    if deviation is not None:
        try:
            d = float(deviation)
            if d <= 0 or d >= 1:
                logger.warning("config.json rebalance.deviation_threshold = %s 应在 0~1 之间，将使用默认值 0.05", d)
                issues += 1
        except (ValueError, TypeError):
            logger.warning("config.json rebalance.deviation_threshold = %r 不是有效数字，将使用默认值 0.05", deviation)
            issues += 1
    profile = rb.get("profile")
    if profile is not None:
        valid_profiles = ("conservative", "moderate", "aggressive", "custom")
        if profile not in valid_profiles:
            logger.warning(
                "config.json rebalance.profile = %r 无效，有效值: %s，将使用 moderate", profile, valid_profiles
            )
            issues += 1
    silence = rb.get("silence_days")
    if silence is not None:
        try:
            s = int(silence)
            if s < 0:
                logger.warning("config.json rebalance.silence_days = %s 不能为负数，将使用默认值 30", s)
                issues += 1
        except (ValueError, TypeError):
            logger.warning("config.json rebalance.silence_days = %r 不是有效整数，将使用默认值 30", silence)
            issues += 1
    target = rb.get("target_allocation")
    if target is not None:
        if not isinstance(target, dict):
            logger.warning("config.json rebalance.target_allocation = %r 不是对象(dict)，将忽略", target)
            issues += 1
        else:
            for key, val in target.items():
                if not isinstance(val, dict):
                    logger.warning("config.json rebalance.target_allocation.%s 不是对象，将忽略该项", key)
                    issues += 1
                    continue
                for f in ("min", "max", "target"):
                    fv = val.get(f)
                    if fv is not None and not isinstance(fv, (int, float)):
                        logger.warning("config.json rebalance.target_allocation.%s.%s = %r 不是数字", key, f, fv)
                        issues += 1
    efi = rb.get("equity_fixed_income")
    if efi is not None:
        if not isinstance(efi, dict):
            logger.warning("config.json rebalance.equity_fixed_income = %r 不是对象(dict)，将忽略", efi)
            issues += 1
        else:
            for key, val in efi.items():
                if key not in ("equity", "fixed_income"):
                    logger.warning(
                        "config.json rebalance.equity_fixed_income.%s 未知，有效键: equity, fixed_income", key
                    )
                    issues += 1
                if not isinstance(val, dict):
                    logger.warning("config.json rebalance.equity_fixed_income.%s 不是对象，将忽略该项", key)
                    issues += 1
                    continue
                for f in ("min", "max", "target"):
                    fv = val.get(f)
                    if fv is not None and not isinstance(fv, (int, float)):
                        logger.warning("config.json rebalance.equity_fixed_income.%s.%s = %r 不是数字", key, f, fv)
                        issues += 1
    return issues


def _validate_discipline_config(config: dict, issues: int) -> int:
    """验证 discipline 配置段（交易纪律：止盈/止损/回撤线 + 静默期）。

    数值语义约束：
      - 三类阈值必须为数字
      - 止盈线应为正数、止损线应为负数（符号约束同时保证「止盈线 > 止损线」，
        杜绝同一品种同时触发止盈与止损的误配）
    """
    ds, issues = _section(config, "discipline", dict, "交易纪律配置无效，将使用默认值", issues)
    if ds is _MISSING:
        return issues
    pcts: dict[str, float] = {}
    for key, default in (("take_profit_pct", 20.0), ("stop_loss_pct", -15.0), ("drawdown_pct", -10.0)):
        val = ds.get(key)
        if val is None:
            continue
        try:
            pcts[key] = float(val)
        except (ValueError, TypeError):
            logger.warning("config.json discipline.%s = %r 不是数字，将使用默认值 %s", key, val, default)
            issues += 1
    take_profit = pcts.get("take_profit_pct")
    if take_profit is not None and take_profit <= 0:
        logger.warning("config.json discipline.take_profit_pct = %s 应为正数，将使用默认值 20.0", take_profit)
        issues += 1
    stop_loss = pcts.get("stop_loss_pct")
    if stop_loss is not None and stop_loss >= 0:
        logger.warning("config.json discipline.stop_loss_pct = %s 应为负数，将使用默认值 -15.0", stop_loss)
        issues += 1
    # 符号约束（take_profit > 0 且 stop_loss < 0）已自动保证 take_profit > stop_loss，
    # 无需单独交叉校验，避免同一误配重复告警。
    silence = ds.get("silence_days")
    if silence is not None:
        try:
            s = int(silence)
            if s < 0:
                logger.warning("config.json discipline.silence_days = %s 不能为负数，将使用默认值 30", s)
                issues += 1
        except (ValueError, TypeError):
            logger.warning("config.json discipline.silence_days = %r 不是有效整数，将使用默认值 30", silence)
            issues += 1
    return issues
