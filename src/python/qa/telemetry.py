"""报告追问（`report_qa`）的埋点与效果汇总——转正判据的数据底座。

为什么需要：`report_qa` 是唯一**新增 LLM 费用**的实验项（详见功能开关注册表），
转正与否不能靠「看起来稳定了」拍板，需要可核对的实测数据：提问量、无回答占比、
事实核对降级率、平均轮数与 token 成本。

三条设计约束：

1. **不落问题正文**：只记问题**字数**。报告追问涉及用户的投资判断，正文一旦落盘就会
   随日志/备份/截图外泄，而判断「够不够稳」并不需要正文（需要时看轮数与错误码即可）。
2. **埋点绝不阻断主流程**：写盘失败、目录不可写、行格式异常一律吞掉并记 debug——
   追问功能本身不能因为埋点而失败。
3. **滚动上限**：账本按行数滚动（默认 5000 条），避免长期运行无限增长；聚合按
   `days` 过滤，滚动上限只影响窗口外的历史细节。

账本位置：`data/state/qa_usage.jsonl`（与 `perf_history` / `datasource_health`
同目录、同原子追加原语）。汇总入口 :func:`summarize_qa_usage` 供 `doctor` 上屏。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.python.core.constants import PROJECT_ROOT
from src.python.core.jsonl_store import append_jsonl_atomic

logger = logging.getLogger("invest")

#: 账本路径（测试可 monkeypatch 本变量重定向到 tmp）
_QA_USAGE_PATH = Path(PROJECT_ROOT) / "data" / "state" / "qa_usage.jsonl"

#: 滚动保留行数（约数：覆盖半年的日常使用）
_QA_USAGE_MAX_LINES = 5000

#: 会话 id 保留前缀长度（完整 uuid 无必要且更像标识符，短前缀足够按会话聚合）
_SESSION_PREFIX = 8

#: 转正判据阈值（可在 `doctor` 输出中逐条看到是否满足）
PROMOTION_MIN_ATTEMPTS = 30
PROMOTION_MAX_NO_ANSWER_RATE = 0.15
PROMOTION_MAX_FACT_WARNING_RATE = 0.30


def record_attempt(
    *,
    channel: str,
    report: str | None,
    ok: bool,
    session_id: str | None = None,
    rounds: int = 0,
    error_code: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    model: str | None = None,
    provider: str | None = None,
    latency_ms: float = 0.0,
    fact_warning: bool = False,
    question_chars: int = 0,
) -> None:
    """追加一条追问尝试记录（成功或失败都记，失败带 `error_code`）。

    失败语义由调用方决定（本函数只负责落盘）：一次「服务不可用」「会话轮数耗尽」
    与「成功回答」在效果统计里权重不同，因此 `ok` 与 `error_code` 都必须记录。

    Args:
        channel: 渠道标识（``web`` / ``tui`` / 其它调用方自定）。
        report: 报告文件名（只取 basename，不落目录）。
        ok: 本次是否成功交付回答。
        session_id: 会话 id（只保留前 8 位）。
        rounds: 该会话当前累计轮数（成功时 = 交付后的轮数）。
        error_code: 失败时的错误码（见 ``qa.error_codes``）。
        input_tokens / output_tokens: 本次调用的 token 数（失败为 0）。
        model / provider: 本次路由命中的模型与线路名（未知留空）。
        latency_ms: 端到端耗时（毫秒）。
        fact_warning: 是否命中事实核对降级（回答中的数值未能与报告完全对上）。
        question_chars: 问题字数（**不记正文**）。
    """
    try:
        cost = _cost_of(model, input_tokens, output_tokens)
        payload: dict[str, Any] = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "channel": channel or "unknown",
            "report": _basename(report),
            "session": (session_id or "")[:_SESSION_PREFIX],
            "rounds": int(rounds or 0),
            "ok": bool(ok),
            "code": error_code or "",
            "in": int(input_tokens or 0),
            "out": int(output_tokens or 0),
            "model": model or "",
            "provider": provider or "",
            "cost": cost,
            "latency_ms": round(float(latency_ms or 0.0), 1),
            "fact_warning": bool(fact_warning),
            "q_chars": int(question_chars or 0),
        }
        _QA_USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        append_jsonl_atomic(
            str(_QA_USAGE_PATH),
            json.dumps(payload, ensure_ascii=False) + "\n",
            log_tag="qa_usage",
            noun="报告追问账本",
            max_lines=_QA_USAGE_MAX_LINES,
        )
    except Exception:  # 埋点不得影响追问主链路（含只读文件系统/磁盘满）
        logger.debug("[qa_telemetry] 记录失败，忽略", exc_info=True)


def _cost_of(model: str | None, input_tokens: int, output_tokens: int) -> float | None:
    """按同一计费单源估算本次费用（未知模型返回 None，不猜价格）。"""
    if not model or (not input_tokens and not output_tokens):
        return None
    try:
        from src.python.llm.pricing import compute_cost_value

        value = compute_cost_value(model, input_tokens, output_tokens)
        return round(value, 6) if value is not None else None
    except Exception:
        logger.debug("[qa_telemetry] 费用估算失败", exc_info=True)
        return None


def _basename(report: str | None) -> str:
    if not report:
        return ""
    try:
        return Path(str(report)).name
    except Exception:
        return ""


def summarize_qa_usage(days: int = 30, *, path: Path | None = None) -> dict[str, Any]:
    """汇总最近 `days` 天的追问效果，并给出转正判据的逐条结论。

    Returns:
        ``{"attempts", "answered", "no_answer_rate", "by_code", "by_channel",
        "avg_rounds", "max_rounds", "avg_input_tokens", "avg_output_tokens",
        "total_tokens", "total_cost", "currency_mixed", "avg_cost",
        "fact_warning_rate", "verdict": {"ready": bool, "checks": [...]}}``；
        账本不存在或为空时各项为 0 / 空，``verdict.ready`` 为 False（样本不足）。
    """
    records = _load_records(days=days, path=path)
    attempts = len(records)
    answered = [r for r in records if r.get("ok")]
    failed = [r for r in records if not r.get("ok")]

    by_code: dict[str, int] = {}
    for row in failed:
        code = str(row.get("code") or "unknown")
        by_code[code] = by_code.get(code, 0) + 1

    by_channel: dict[str, dict[str, int]] = {}
    for row in records:
        bucket = by_channel.setdefault(str(row.get("channel") or "unknown"), {"attempts": 0, "ok": 0})
        bucket["attempts"] += 1
        bucket["ok"] += 1 if row.get("ok") else 0

    in_total = sum(int(r.get("in") or 0) for r in records)
    out_total = sum(int(r.get("out") or 0) for r in records)
    costs = [float(r["cost"]) for r in records if isinstance(r.get("cost"), (int, float))]
    warning_count = sum(1 for r in answered if r.get("fact_warning"))
    rounds = [int(r.get("rounds") or 0) for r in answered]

    no_answer_rate = round(len(failed) / attempts, 3) if attempts else 0.0
    fact_warning_rate = round(warning_count / len(answered), 3) if answered else 0.0

    checks = [
        {
            "name": f"提问量 ≥ {PROMOTION_MIN_ATTEMPTS}",
            "passed": attempts >= PROMOTION_MIN_ATTEMPTS,
            "actual": attempts,
        },
        {
            "name": f"无回答占比 ≤ {PROMOTION_MAX_NO_ANSWER_RATE:.0%}",
            "passed": attempts > 0 and no_answer_rate <= PROMOTION_MAX_NO_ANSWER_RATE,
            "actual": no_answer_rate,
        },
        {
            "name": f"事实核对降级率 ≤ {PROMOTION_MAX_FACT_WARNING_RATE:.0%}",
            "passed": bool(answered) and fact_warning_rate <= PROMOTION_MAX_FACT_WARNING_RATE,
            "actual": fact_warning_rate,
        },
    ]

    return {
        "attempts": attempts,
        "answered": len(answered),
        "failed": len(failed),
        "no_answer_rate": no_answer_rate,
        "by_code": dict(sorted(by_code.items(), key=lambda kv: -kv[1])),
        "by_channel": by_channel,
        "avg_rounds": round(sum(rounds) / len(rounds), 2) if rounds else 0.0,
        "max_rounds": max(rounds) if rounds else 0,
        "avg_input_tokens": int(in_total / attempts) if attempts else 0,
        "avg_output_tokens": int(out_total / attempts) if attempts else 0,
        "total_tokens": in_total + out_total,
        "total_cost": round(sum(costs), 4) if costs else 0.0,
        "currency_mixed": _currency_mixed(records),
        "avg_cost": round(sum(costs) / len(costs), 4) if costs else 0.0,
        "fact_warning_rate": fact_warning_rate,
        "verdict": {"ready": all(c["passed"] for c in checks), "checks": checks},
    }


def _currency_mixed(records: list[dict[str, Any]]) -> bool:
    """账本内是否混用多种计价币种（混合时总费用不可直接相加，仅作参考）。"""
    currencies = set()
    for row in records:
        model = row.get("model")
        if not model:
            continue
        try:
            from src.python.llm.pricing import model_currency

            currencies.add(model_currency(str(model)))
        except Exception:
            continue
    return len(currencies) > 1


def _load_records(days: int, path: Path | None = None) -> list[dict[str, Any]]:
    """读取账本并过滤最近 `days` 天；坏行/非对象行静默跳过（账本可手工编辑）。"""
    target = path or _QA_USAGE_PATH
    if not target.exists():
        return []
    cutoff = datetime.now() - timedelta(days=max(int(days or 0), 0))
    rows: list[dict[str, Any]] = []
    for raw in target.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        ts = row.get("ts")
        if isinstance(ts, str):
            try:
                if datetime.fromisoformat(ts) < cutoff:
                    continue
            except ValueError:
                pass
        rows.append(row)
    return rows


def format_summary_block(summary: dict[str, Any], *, days: int = 30) -> list[str]:
    """把汇总渲染成 `doctor` 上屏的多行文本（纯展示，不含判定逻辑）。"""
    lines = [f"报告追问（实验项）最近 {days} 天："]
    if not summary.get("attempts"):
        lines.append("  尚无记录（开启后提问一次即可产生第一行埋点，不影响当前结论）")
        return lines
    lines.append(
        f"  提问 {summary['attempts']} 次（成功 {summary['answered']} / 失败 {summary['failed']}，"
        f"无回答占比 {summary['no_answer_rate']:.1%}）"
    )
    if summary.get("by_channel"):
        detail = "、".join(f"{ch} {v['ok']}/{v['attempts']}" for ch, v in sorted(summary["by_channel"].items()))
        lines.append(f"  渠道（成功/总数）：{detail}")
    if summary.get("by_code"):
        detail = "、".join(f"{code} ×{n}" for code, n in list(summary["by_code"].items())[:4])
        lines.append(f"  失败码：{detail}")
    cost_note = "（多币种混合，总费用仅供参考）" if summary.get("currency_mixed") else ""
    lines.append(
        f"  平均 {summary['avg_rounds']} 轮（最长 {summary['max_rounds']}）· "
        f"平均 tokens {summary['avg_input_tokens']}/{summary['avg_output_tokens']}（入/出）· "
        f"累计 {summary['total_tokens']} tokens · 费用合计 {summary['total_cost']}{cost_note}"
    )
    lines.append(f"  事实核对降级率 {summary['fact_warning_rate']:.1%}")
    verdict = summary.get("verdict") or {}
    for check in verdict.get("checks") or []:
        mark = "[OK]" if check["passed"] else "[!]"
        lines.append(f"  {mark} 转正判据：{check['name']} —— 实测 {check['actual']}")
    lines.append("  结论：可评估转正" if verdict.get("ready") else "  结论：样本或质量未达判据，维持实验状态")
    return lines


__all__ = [
    "PROMOTION_MAX_FACT_WARNING_RATE",
    "PROMOTION_MAX_NO_ANSWER_RATE",
    "PROMOTION_MIN_ATTEMPTS",
    "format_summary_block",
    "record_attempt",
    "summarize_qa_usage",
]
