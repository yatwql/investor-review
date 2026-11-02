"""投资决策质量待验证项回测工具（非生产代码；评测产物落 docs/tmp/decision-quality/）。

承接归档讨论稿 `docs/archive/v0.16.x/investment-decision-quality/investment-decision-quality.md` §2.2 的预注册口径，三个阶段：

  horizon     决策建议在 5/20/60 交易日视界的命中率与超额（讨论稿 §8「视界」项）
  factor-ic   因子目录单因子 IC（组合级因子 × 沪深300 前向收益代理口径）
  valuation   估值信号「价格代理 / 真实 PE·PB」两口径区分度（同窗对比）
  all         依序执行全部阶段

预注册判据（跑完不得回改；改判据须改本段并全量重跑）：
  - 样本量门槛：每类统计 ≥100 个可结算样本才下结论，否则「样本不足，仅记录不裁决」
  - 信号区分度判据：①三分位组均值单调 ②Spearman 秩相关 |IC| ≥ 0.05（满足其一）
  - 拒绝标准：|IC| < 0.05 且无单调性 →「叙述性维度」（记录在案，不进方向轴）

已知陷阱（结论不得外推，产物脚注必须带）：
  - 样本期约 3 个月、单一市场状态，任何结论都不能外推到其他市场状态
  - 同一份报告的多个品种收益高度相关（共同 β），有效独立样本远小于记录条数
  - 报告盘后生成，信号与结算价之间存在延迟

口径说明：
  - 固定视界结算：取「报告日之后第 N 个交易日收盘」对比决策登记的 baseline_close；
    账本生产结算（decision_settlement）用「最新收盘」动态视界，两者基线同源、终点不同，
    本工具用于回测对比，不替代账本结算。
  - 估值两口径同窗：价格代理与真实估值均用「报告日及之前」同一窗口 bars 重算，
    隔离口径定义差异；账本内展示值另行记录（ledger_percentile）供对照，不参与分组统计。

纪律：
  - 取数只经既有能力（decision_settlement 行情/指数序列 + valuation_percentile 口径函数 +
    financial_indicator 缓存链），不裸调 provider；
  - 只读账本与缓存，不写 data/ 生产状态；产物只落 docs/tmp/（git 忽略）；
  - 不 import report 管线与 llm，生产侧零改动。
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

# ── 项目路径（脚本独立运行 / 动态加载时先把仓库根加入 sys.path） ──
_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.python.core import decision_ledger as dl  # noqa: E402

# ── 预注册常量（讨论稿 §2.2；改动即口径变更，须全量重跑） ──
HORIZONS = (5, 20, 60)  # 结算视界（交易日）
BENCHMARK_INDEX = "sh000300"  # 组合/因子层基准代理
MIN_SAMPLES = 100  # 样本量门槛：低于此只记录不裁决
IC_THRESHOLD = 0.05  # |IC| 拒绝线
TERCILE_BUCKETS = 3  # 分组单调性桶数
MONO_MIN_N = 6  # 单调性判定最少样本（每桶 ≥2）
# 交易纪律止损口径对照（固定线 vs 波动率归一化线，跑完不回改）
DISCIPLINE_VOL_WINDOW = 60  # 波动率窗口：报告日之前 60 个交易日
DISCIPLINE_VOL_MULTIPLE = 2.5  # 归一化止损线 = −k·σ（σ 为日收益率总体标准差，未年化）
DISCIPLINE_FIXED_STOP_PCT = -0.15  # 固定止损线（`discipline.stop_loss_pct` 默认值）
DISCIPLINE_TRIGGER_HORIZON = 5  # 触发窗口：报告日后第 5 个交易日累计收益
DISCIPLINE_EFFECT_HORIZON = 20  # 效果窗口终点：报告日后第 20 个交易日（第 6~20 日收益）
DISCIPLINE_MIN_EDGE = -0.01  # 归一化组效果均值须比固定组更负至少 1 个百分点才算更优
# 相关性↔回撤口径（持仓相关性矩阵与最大回撤的关系，跑完不回改）
CORRELATION_WINDOW = 60  # 滚动窗口（交易日）
CORRELATION_STEP = 20  # 窗口步长（交易日，降低窗口间重叠带来的自相关）
CORRELATION_MIN_SPAN = 250  # 样本期门槛（交易日）：不足一年不裁决（短样本相关性不稳）
CORRELATION_EXPECTED_SIGN = 1  # 预注册方向：相关性↑ → 回撤↑（正相关）

DEFAULT_DAYS = 120  # 取数窗口（交易日 bar 数）
DEFAULT_OUT_DIR = _PROJECT_ROOT / "docs" / "tmp" / "decision-quality"
DEFAULT_LEDGER_DIR = _PROJECT_ROOT / "data" / "state"

SIGNAL_VALUATION = "valuation_percentile"
SIGNAL_FACTOR = "factor_catalog"

CAVEATS = [
    "样本期约 3 个月、单一市场状态，结论不得外推到其他市场状态",
    "同报告多品种收益高度相关（共同 β），有效独立样本远小于记录条数",
    "报告盘后生成，信号与结算价之间存在延迟",
]


# ═══════════════════════════════════════════════════════════════
#  账本读取（只读）
# ═══════════════════════════════════════════════════════════════


def load_events(path: str | Path) -> list[dict[str, Any]]:
    """读取 jsonl 账本事件（一行一条 JSON）；读取/解析失败即中止（评测不猜数据）。"""
    events: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    except OSError as exc:
        raise SystemExit(f"账本读取失败: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"账本格式错误（非合法 JSON 行）: {path}: {exc}") from exc
    return events


def load_decisions(path: str | Path) -> list[dict[str, Any]]:
    """取有方向、有基线、有报告日的决策事件（可结算候选全集）。"""
    out: list[dict[str, Any]] = []
    for e in load_events(path):
        if e.get("event") != "decision":
            continue
        direction = int(e.get("direction") or 0)
        if direction not in (dl.DIRECTION_LONG, dl.DIRECTION_SHORT):
            continue
        if float(e.get("baseline_close") or 0) <= 0 or not e.get("report_date"):
            continue
        out.append(e)
    return out


def load_signals(path: str | Path, signal_type: str) -> list[dict[str, Any]]:
    """取 signal_ledger 中指定类型的信号事件。"""
    return [e for e in load_events(path) if e.get("event") == "signal" and e.get("signal_type") == signal_type]


# ═══════════════════════════════════════════════════════════════
#  纯计算原语（可单测）
# ═══════════════════════════════════════════════════════════════


def bars_after(series: list[dict[str, Any]] | None, rep_date: str) -> list[dict[str, Any]]:
    """报告日之后的交易日 bar（严格大于报告日）。"""
    return [b for b in (series or []) if str(b.get("date") or "") > rep_date]


def forward_close(
    series: list[dict[str, Any]] | None,
    rep_date: str,
    horizon: int,
) -> tuple[float | None, int]:
    """固定视界收盘：报告日之后第 horizon 个交易日的 close。

    Returns:
        (close, bars_after 数)；未满视界或该 bar 无有效 close → (None, bars_after 数)。
    """
    after = bars_after(series, rep_date)
    if len(after) < max(horizon, 1):
        return None, len(after)
    bar = after[horizon - 1]
    close = bar.get("close") or bar.get("nav")
    try:
        close_f = float(close) if close is not None else 0.0
    except (TypeError, ValueError):
        close_f = 0.0
    return (close_f if close_f > 0 else None), len(after)


def _mean(values: list[float]) -> float | None:
    """算术均值（空列表 → None，便于区分「无样本」与「均值恰为 0」）。"""
    return statistics.fmean(values) if values else None


def _ranks(xs: list[float]) -> list[float]:
    """平均秩（并列取均值），Spearman 用。"""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Spearman 秩相关；样本 <3 或任一侧零方差 → None。"""
    n = len(xs)
    if n < 3 or len(ys) != n:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 4)


def tercile_monotonic(xs: list[float], ys: list[float]) -> bool:
    """按 x 排序三分组，y 组均值单调（升或降）；样本不足或空桶 → False。"""
    n = len(xs)
    if n < MONO_MIN_N or len(ys) != n:
        return False
    pairs = sorted(zip(xs, ys))
    size = n // TERCILE_BUCKETS
    means: list[float] = []
    for b in range(TERCILE_BUCKETS):
        chunk = [y for _, y in pairs[b * size : n if b == TERCILE_BUCKETS - 1 else (b + 1) * size]]
        if not chunk:
            return False
        means.append(sum(chunk) / len(chunk))
    if len(set(means)) == 1:  # 组均值无差异（零区分度）不算单调
        return False
    asc = all(a <= b for a, b in zip(means, means[1:]))
    desc = all(a >= b for a, b in zip(means, means[1:]))
    return asc or desc


def verdict_discrimination(n: int, ic: float | None, monotonic: bool) -> dict[str, Any]:
    """信号区分度三态判定（预注册：样本门槛 → 区分度 → 叙述性维度）。"""
    if n < MIN_SAMPLES:
        return {"verdict": "样本不足，仅记录不裁决", "passed": None}
    if (ic is not None and abs(ic) >= IC_THRESHOLD) or monotonic:
        return {"verdict": "有区分度", "passed": True}
    return {"verdict": "叙述性维度（不进方向轴）", "passed": False}


def verdict_sample_gate(n: int) -> dict[str, Any]:
    """命中率可信度判定（只看样本量门槛，不做 IC 判据）。"""
    if n < MIN_SAMPLES:
        return {"verdict": "样本不足，仅记录不裁决", "credible": False}
    return {"verdict": "达到采信门槛（记录命中率）", "credible": True}


# ═══════════════════════════════════════════════════════════════
#  阶段一：决策建议视界命中率
# ═══════════════════════════════════════════════════════════════


def _aggregate_horizon(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    """按视界聚合决策行：成熟数 / 命中率 / 均值收益 / 超额 / 方向拆分。"""
    key = str(horizon)
    matured = [r["horizons"][key] for r in rows if r["horizons"][key]["matured"]]
    hits = [m["direction_hit"] for m in matured if m["direction_hit"] is not None]
    raws = [m["raw_return"] for m in matured]
    excess = [m["excess"] for m in matured if m["excess"] is not None]
    by_dir: dict[str, dict[str, Any]] = {}
    for d, label in ((dl.DIRECTION_LONG, "long"), (dl.DIRECTION_SHORT, "short")):
        sub = [r["horizons"][key] for r in rows if int(r["direction"]) == d and r["horizons"][key]["matured"]]
        sub_hits = [m["direction_hit"] for m in sub if m["direction_hit"] is not None]
        by_dir[label] = {
            "n": len(sub),
            "hit_rate": round(sum(sub_hits) / len(sub_hits), 4) if sub_hits else None,
        }
    n = len(matured)
    n_hit = len(hits)
    return {
        "n_decisions": len(rows),
        "n_matured": n,
        "n_unmatured": len(rows) - n,
        "hit_rate": round(sum(hits) / n_hit, 4) if n_hit else None,
        "mean_raw_return": round(sum(raws) / n, 6) if n else None,
        "mean_excess": round(sum(excess) / len(excess), 6) if excess else None,
        "n_with_bench": len(excess),
        "by_direction": by_dir,
        **verdict_sample_gate(n),
    }
