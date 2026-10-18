"""报告生成管线性能收集 —— 轻量阶段计时、持久化、趋势查看。

三层体系：
    Layer 1 — 本模块（PerfCollector）+ orchestrator.py 埋点
    Layer 2 — scripts/perf-test-report.py（独立基准，mock 外部数据源）
    Layer 3 — scripts/perf-view.py（历史趋势可视化）

设计约束遵从（详见 technical.md §8）：
    缓存原子写入  — 原子写入：tempfile.mkstemp + os.replace
    日志统一  — 统一日志：logging.getLogger("invest")
    PerfCollector 为普通局部对象，非模块级单例
    路径从 PROJECT_ROOT 绝对化

数据收集策略：
    - 每次 generate_report() 自动收集各阶段耗时
    - 阶段开始时可经 stage_announcer 向进度通道广播状态行（当前阶段 / 已耗时 /
      预计剩余，ETA 基于本文件历史同阶段中位数，计算失败静默降级）
    - 粗粒度阶段进 `phases`（**唯一**参与 total_seconds 的集合，保证跨版本可比）；
      阶段内细分进 `breakdown`，运行期诊断计数进 `counters`（不参与 total_seconds）
    - 写入 data/state/perf_history.jsonl（JSONL 格式，一行一次运行）
    - 同时通过 logging 输出 INFO 级计时日志
    - 结果包含版本号，支持跨版本性能趋势追踪

观测面分层（见 docs/archive/v0.13.x/perf-observability-design.md）：
    phases   — 粗粒度阶段墙钟（ETA 预估与历史对比的基准口径）
    breakdown— 父阶段下的子项自身耗时（子项可并行，之和可大于父阶段墙钟）
    counters — 诊断计数（warnings/errors 等；由日志采集与调用点登记共同填充）
"""

from __future__ import annotations

import json
import logging
import os
import statistics
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from src.python.core.constants import APP_VERSION, PROJECT_ROOT
from src.python.core.jsonl_store import append_jsonl_atomic

logger = logging.getLogger("invest")

# ── 持久化路径 ──────────────────────────────────────────
# module-level 变量，测试时可通过 setattr 重定向（测试隔离模式）
_PERF_HISTORY_DIR = os.path.join(PROJECT_ROOT, "data", "state")
_PERF_HISTORY_FILE = os.path.join(_PERF_HISTORY_DIR, "perf_history.jsonl")
# 遥测保留上限（防只增文件无界增长；超出后追加时丢最旧行，
# 见 core/jsonl_store.append_jsonl_atomic_many 的 max_lines——
# 5000 条 ≈ 每日 4 次生成的三年余，远超 perf-view 趋势分析所需）
_PERF_HISTORY_KEEP_LINES = 5000


# ── 数据结构 ────────────────────────────────────────────


@dataclass
class _PhaseRecord:
    """单个阶段的耗时记录。"""

    name: str
    seconds: float


#: errors 列表最多保留的条数（日志采集可能持续产出，避免异常百出时字段膨胀）
_MAX_CAPTURED_ERRORS = 20
#: 单条错误消息最长保留字符数
_MAX_ERROR_MESSAGE_CHARS = 200


class PhaseBreakdownRecorder:
    """父阶段绑定的子项耗时与诊断计数记录器（线程安全）。

    由 :meth:`PerfCollector.recorder` 创建并归其所有——`PerfCollector` 仍为
    普通局部对象、非模块级单例（沿用既有设计约束）。LLM 四模块在线程池中
    并发写，故内部以 `threading.Lock` 保护。

    口径：记录的是**子项自身耗时**；父阶段内子项可能并行（LLM 与新闻并行、
    四模块并发），故子项之和可大于父阶段墙钟时长，且**不参与** `total_seconds`。

    用法::

        rec = perf.recorder("LLM+新闻")
        rec.record("持仓体检报告", 40.1)   # 子项耗时
        rec.count("retry")                # 诊断计数
    """

    def __init__(self, parent_phase: str) -> None:
        self._parent_phase = parent_phase
        self._lock = threading.Lock()
        self._spans: dict[str, float] = {}
        self._counters: dict[str, int] = {}

    @property
    def parent_phase(self) -> str:
        """所绑定的父阶段名（与 `PerfCollector.start` 传入一致）。"""
        return self._parent_phase

    def record(self, name: str, seconds: float) -> None:
        """记录一个子项耗时（同名子项多次调用则累加，非数值输入静默忽略）。"""
        try:
            sec = float(seconds)
        except (TypeError, ValueError):
            return
        if sec < 0 or sec != sec or sec == float("inf"):  # 负值/NaN/inf 视为无效
            return
        with self._lock:
            self._spans[name] = round(self._spans.get(name, 0.0) + sec, 3)

    def count(self, key: str, n: int = 1) -> None:
        """累加一个诊断计数（如 retry/fallback）。"""
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + int(n)

    def spans(self) -> dict[str, float]:
        """子项耗时快照（副本）。"""
        with self._lock:
            return dict(self._spans)

    def counters(self) -> dict[str, int]:
        """诊断计数快照（副本）。"""
        with self._lock:
            return dict(self._counters)


class _LogCounterHandler(logging.Handler):
    """只计数不输出的日志 handler：把运行期 WARNING/ERROR 计入诊断面。

    由 `PerfCollector` 在首个阶段计时时挂到 `invest` logger、`save()` 时摘除。
    集中采集优于逐点改造：告警来源分散在 `reporter.add_error` / `logger.warning`
    多处，且新增链路无需再手工登记。计数失败绝不打断生成（emit 内全覆盖异常）。
    """

    def __init__(self, collector: "PerfCollector") -> None:
        super().__init__(level=logging.WARNING)
        self._collector = collector

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - 异常分支不构造
        try:
            if record.levelno >= logging.ERROR:
                self._collector.note_error(str(record.getMessage()))
            else:
                self._collector.count("warnings")
        except Exception:
            pass


@dataclass
class ReportRunSnapshot:
    """一次报告生成运行的完整耗时快照。"""

    version: str
    timestamp: str
    report_type: str  # basic / both / full
    holdings_count: int
    phases: list[_PhaseRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings_count: int = 0
    status: str = "completed"  # 运行状态：completed / interrupted（中断收口写入）
    interrupted_stage: str | None = None  # 中断时活跃阶段名（仅 status=interrupted）
    #: 父阶段 → {子项名: 自身耗时秒}（子项可并行，之和不参与 total_seconds）
    breakdown: dict[str, dict[str, float]] = field(default_factory=dict)
    #: 运行期诊断计数（warnings/errors/retry/degrade:<来源> 等）
    counters: dict[str, int] = field(default_factory=dict)
    #: LLM 运行上下文（provider/model/thinking/重试与节流等待/缓存命中/用量）
    llm: dict[str, Any] = field(default_factory=dict)

    @property
    def total_seconds(self) -> float:
        return sum(p.seconds for p in self.phases)

    def to_json(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "report_type": self.report_type,
            "holdings_count": self.holdings_count,
            "phases": {p.name: round(p.seconds, 3) for p in self.phases},
            "total_seconds": round(self.total_seconds, 3),
            "breakdown": {parent: spans for parent, spans in self.breakdown.items() if spans},
            "counters": self.counters,
            "llm": self.llm,
            "errors": self.errors,
            "warnings_count": self.warnings_count,
            "status": self.status,
            "interrupted_stage": self.interrupted_stage,
        }


# ── PerfCollector ──────────────────────────────────────


class PerfCollector:
    """一次报告生成会话内的阶段计时收集器。

    用法::

        perf = PerfCollector(report_type="both", holdings=holdings)
        perf.start("行情获取")
        ...
        perf.stop()
        ...
        perf.save()  # 持久化到 perf_history.jsonl

    设计原则:
    - 非单例、非模块级全局
    - 所有时间基于 time.perf_counter()
    - start/stop 成对调用；嵌套时自动关闭前一个并记录警告
    - stage_announcer 为可选的阶段状态广播回调（进度通道显示当前阶段/
      预计剩余），回调异常静默吞掉，不影响计时与生成流程
    """

    def __init__(
        self,
        report_type: str,
        holdings: list,
        *,
        stage_announcer: Callable[["PerfCollector"], None] | None = None,
    ) -> None:
        self._report_type = report_type
        self._holdings_count = len(holdings)
        self._phases: list[_PhaseRecord] = []
        self._errors: list[str] = []
        self._counters: dict[str, int] = {}
        self._recorders: dict[str, PhaseBreakdownRecorder] = {}
        self._lock = threading.Lock()
        self._current_name: str | None = None
        self._current_start: float | None = None
        self._stage_announcer = stage_announcer
        self._interrupted = False
        self._interrupted_stage: str | None = None
        self._saved = False
        self._log_handler: logging.Handler | None = None
        self._llm_context: dict[str, Any] = {}

    @property
    def report_type(self) -> str:
        """本次运行的报告类型（basic/both/full，供 ETA 预估按类型筛样本）。"""
        return self._report_type

    # ── 阶段计时 ──

    def start(self, phase_name: str) -> None:
        """开始一个新阶段计时。若前一阶段尚未关闭，自动关闭并记录警告。"""
        self._ensure_log_capture()
        if self._current_name is not None:
            logger.warning(
                "[perf] 阶段 '%s' 未结束即启动 '%s'，自动关闭前一阶段",
                self._current_name,
                phase_name,
            )
            self.stop()
        self._current_name = phase_name
        self._current_start = time.perf_counter()
        self._announce_stage()

    def stage_status(self) -> dict[str, Any] | None:
        """当前活跃阶段状态 {"phase": 阶段名, "elapsed": 已耗时秒}；无活跃阶段时 None。"""
        if self._current_name is None or self._current_start is None:
            return None
        return {
            "phase": self._current_name,
            "elapsed": round(time.perf_counter() - self._current_start, 1),
        }

    def _announce_stage(self) -> None:
        """阶段开始时向进度通道广播状态行（回调异常静默，不影响计时）。"""
        if self._stage_announcer is None:
            return
        try:
            self._stage_announcer(self)
        except Exception:
            logger.debug("[perf] 阶段状态广播失败，已忽略", exc_info=True)

    def stop(self) -> float | None:
        """结束当前阶段计时。

        Returns:
            耗时秒数（已四舍五入到 3 位小数），无活跃阶段时返回 None。
        """
        if self._current_name is None or self._current_start is None:
            return None
        elapsed = round(time.perf_counter() - self._current_start, 3)
        self._phases.append(_PhaseRecord(name=self._current_name, seconds=elapsed))
        logger.info("[perf] %s: %.3fs", self._current_name, elapsed)
        self._current_name = None
        self._current_start = None
        return elapsed

    # ── 辅助记录 ──

    def mark_interrupted(self) -> None:
        """标记本次运行为「已中断」（快照 status=interrupted，随附活跃阶段名）。

        由 run_integrity 中断收口调用；阶段间隙中断时活跃阶段为 None。
        """
        self._interrupted = True
        self._interrupted_stage = self._current_name

    def add_error(self, message: str) -> None:
        """记录一条错误（同时计入 `counters["errors"]`）。"""
        self.note_error(message)

    def note_error(self, message: str) -> None:
        """记录一条错误消息并递增错误计数（日志采集与调用点登记共用入口）。"""
        self.count("errors")
        if len(self._errors) < _MAX_CAPTURED_ERRORS:
            self._errors.append(message[:_MAX_ERROR_MESSAGE_CHARS])

    def count(self, key: str, n: int = 1) -> None:
        """累加一个运行期诊断计数（跨阶段的横切项，如 warnings/errors/retry）。"""
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + int(n)

    def counts(self) -> dict[str, int]:
        """诊断计数快照（副本）。"""
        with self._lock:
            return dict(self._counters)

    def inc_warning(self) -> None:
        """增加警告计数（等价于 `count("warnings")`）。"""
        self.count("warnings")

    # ── 阶段细分 ──

    def recorder(self, parent_phase: str) -> PhaseBreakdownRecorder:
        """取（或新建）指定父阶段的子项记录器；同一父阶段复用同一实例。"""
        with self._lock:
            rec = self._recorders.get(parent_phase)
            if rec is None:
                rec = PhaseBreakdownRecorder(parent_phase)
                self._recorders[parent_phase] = rec
            return rec

    def set_llm_context(self, context: dict[str, Any] | None) -> None:
        """登记本次运行的 LLM 上下文（provider/model/等待/缓存/用量），空值忽略。"""
        if context:
            self._llm_context = dict(context)

    # ── 日志诊断采集 ──

    def _ensure_log_capture(self) -> None:
        """首次阶段计时时挂上只计数的日志 handler（幂等）。"""
        if self._log_handler is not None:
            return
        handler = _LogCounterHandler(self)
        logger.addHandler(handler)
        self._log_handler = handler

    def _detach_log_capture(self) -> None:
        """摘除日志 handler（save 时调用；未挂载时为空操作）。"""
        if self._log_handler is None:
            return
        logger.removeHandler(self._log_handler)
        self._log_handler = None

    # ── 快照输出 ──

    def snapshot(self) -> ReportRunSnapshot:
        """生成当前会话的运行时快照（含子项细分与诊断计数）。"""
        with self._lock:
            recorders = list(self._recorders.values())
        counters = self.counts()
        breakdown: dict[str, dict[str, float]] = {}
        for rec in recorders:
            spans = rec.spans()
            if spans:
                breakdown[rec.parent_phase] = spans
            for key, n in rec.counters().items():
                counters[key] = counters.get(key, 0) + n
        return ReportRunSnapshot(
            version=APP_VERSION,
            timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            report_type=self._report_type,
            holdings_count=self._holdings_count,
            phases=list(self._phases),
            errors=list(self._errors),
            warnings_count=counters.get("warnings", 0),
            status="interrupted" if self._interrupted else "completed",
            interrupted_stage=self._interrupted_stage if self._interrupted else None,
            breakdown=breakdown,
            counters=counters,
            llm=dict(self._llm_context),
        )

    def save(self) -> None:
        """将本次运行耗时追加到 perf_history.jsonl（遵循原子写入）。

        幂等：一次运行只落一条记录（正常完成先落、随后中断收口再落时跳过）。
        """
        if self._saved:
            logger.debug("[perf] 本次运行已记录，跳过重复落盘")
            return
        line = json.dumps(self.snapshot().to_json(), ensure_ascii=False) + "\n"
        _append_jsonl_atomic(_PERF_HISTORY_FILE, line, max_lines=_PERF_HISTORY_KEEP_LINES)
        self._saved = True
        self._detach_log_capture()
        logger.info("[perf] 耗时已记录到 %s", _PERF_HISTORY_FILE)


# ── 原子写入工具 ────────────────────────────


def _append_jsonl_atomic(path: str, line: str, max_lines: int | None = None) -> None:
    """向 JSONL 文件原子追加一行（原语见 `core/jsonl_store.py`）。

    策略：读全部现有内容 → 追加新行 → tempfile.mkstemp + os.replace 写回。
    遵循原子写入：直接覆写会因断电/崩溃产生半写损坏文件。

    Args:
        path: 目标文件路径
        line: 已序列化单行（含换行）
        max_lines: 保留上限（透传 jsonl_store，仅遥测历史启用；None = 不限）
    """
    append_jsonl_atomic(path, line, prefix=".perf_history_", log_tag="perf", noun="历史文件", max_lines=max_lines)


# ── 数据源健康检查持久化 ──────────────────────────────

# 健康检查历史文件（同 data/state/ 目录）
_HEALTH_CHECK_FILE = os.path.join(_PERF_HISTORY_DIR, "datasource_health.jsonl")
# 健康检查遥测保留上限（同 perf_history 防无界增长；
# summarize_health_history 只取末 10 条，2000 条余量充足）
_HEALTH_CHECK_KEEP_LINES = 2000


def save_health_check_snapshot(
    results: list[dict],
    report_type: str = "",
    holdings_count: int = 0,
) -> None:
    """将一次数据源健康检查结果追加到 datasource_health.jsonl。

    Args:
        results: run_health_checks() 返回的结构化结果列表
        report_type: 本次运行报告类型（basic/both/full）
        holdings_count: 持仓数量
    """
    snapshot = {
        "version": APP_VERSION,
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "report_type": report_type,
        "holdings_count": holdings_count,
        "sources": {
            r["name"]: {"ok": r["ok"], "latency_ms": r["latency_ms"], "message": r["message"]} for r in results
        },
        "total": len(results),
        "ok_count": sum(1 for r in results if r["ok"]),
        "fail_count": sum(1 for r in results if not r["ok"]),
    }
    line = json.dumps(snapshot, ensure_ascii=False) + "\n"
    _append_jsonl_atomic(_HEALTH_CHECK_FILE, line, max_lines=_HEALTH_CHECK_KEEP_LINES)
    logger.info("[health] 数据源健康检查结果已记录到 %s", _HEALTH_CHECK_FILE)


def load_health_history(path: str | None = None) -> list[dict[str, Any]]:
    """加载 datasource_health.jsonl，返回运行记录列表。"""
    path = path or _HEALTH_CHECK_FILE
    if not os.path.isfile(path):
        return []
    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("[health] 忽略损坏行: %s", line[:80])
    return records


def summarize_health_history(limit: int = 10) -> list[dict[str, Any]]:
    """聚合数据源健康历史为最近 limit 次运行摘要。

    每条摘要包含：时间戳、报告类型、持仓数量、源总数/成功数/失败数、
    失败源名称列表（最多前 5 个）。聚合逻辑集中在核心层，
    供 TUI/Web 端展示「数据源健康历史」。

    Args:
        limit: 返回最近多少次运行（默认 10）

    Returns:
        按时间升序的摘要列表；无历史记录时返回 []
    """
    records = load_health_history()
    recent = records[-limit:] if limit > 0 else []
    summaries: list[dict[str, Any]] = []
    for record in recent:
        sources = record.get("sources") or {}
        failed = [name for name, s in sources.items() if not s.get("ok")][:5]
        summaries.append(
            {
                "timestamp": record.get("timestamp", ""),
                "report_type": record.get("report_type", ""),
                "holdings_count": record.get("holdings_count", 0),
                "total": record.get("total", len(sources)),
                "ok_count": record.get("ok_count", sum(1 for s in sources.values() if s.get("ok"))),
                "fail_count": record.get("fail_count", sum(1 for s in sources.values() if not s.get("ok"))),
                "failed_sources": failed,
            }
        )
    return summaries


# ── 工具函数（供 Layer 3 脚本使用） ─────────────────────


def load_history(path: str | None = None) -> list[dict[str, Any]]:
    """加载 perf_history.jsonl，返回运行记录列表。

    Args:
        path: JSONL 文件路径，默认使用 _PERF_HISTORY_FILE。

    Returns:
        按时间升序排列的运行记录列表。
    """
    path = path or _PERF_HISTORY_FILE
    if not os.path.isfile(path):
        return []
    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("[perf] 忽略损坏行: %s", line[:80])
    return records


def module_cost_summary(days: int = 7, path: str | None = None) -> dict[str, dict[str, Any]]:
    """按模块汇总近 N 日运行的 LLM 费用（[S] 面板行尾历史费用摘要数据源）。

    读取 perf 历史记录的 ``llm.modules.*.cost``——与运行事前费用预估
    （``llm.cost_forecast``）和日费用预算统计（``daily_cost_limit``）**同一记录、
    同一字段、同一计费数学**（``llm.pricing.compute_cost_value``），三处展示的
    数字同源不打架；模块费用为 ``llm.total_cost`` 的子集，不会大于同窗口总额。

    Args:
        days: 回看窗口天数（含今日，按记录 ``timestamp`` 本地时间过滤）。
        path: 历史文件路径，默认 ``_PERF_HISTORY_FILE``（测试可指向临时文件）。

    Returns:
        ``{模块 key: {"total": 费用合计, "runs": 含该模块的运行数, "avg": 单次均值}}``；
        无可汇总样本或读取失败返回空 dict（调用方静默省略展示）。
    """
    try:
        records = load_history(path)
    except OSError:
        return {}
    cutoff = datetime.now() - timedelta(days=days)
    summary: dict[str, dict[str, Any]] = {}
    for rec in records:
        ts = rec.get("timestamp")
        if isinstance(ts, str):
            try:
                when = datetime.fromisoformat(ts)
            except ValueError:
                when = None
            if when is not None and when < cutoff:
                continue
        llm = rec.get("llm")
        if not isinstance(llm, dict):
            continue
        modules = llm.get("modules")
        if not isinstance(modules, dict):
            continue
        for key, entry in modules.items():
            if not isinstance(entry, dict):
                continue
            try:
                cost = float(entry.get("cost") or 0.0)
            except (TypeError, ValueError):
                continue
            bucket = summary.setdefault(str(key), {"total": 0.0, "runs": 0})
            bucket["total"] += cost
            bucket["runs"] += 1
    for bucket in summary.values():
        bucket["total"] = round(bucket["total"], 6)
        bucket["avg"] = round(bucket["total"] / bucket["runs"], 6) if bucket["runs"] else 0.0
    return summary


# ── 阶段 ETA 预估（事中进度显示） ────────────────────────

_ETA_LOOKBACK_RUNS = 20  # 预估取最近 N 次运行的同阶段样本


def estimate_stage_eta(
    phase_name: str,
    elapsed_seconds: float,
    *,
    history: list[dict[str, Any]] | None = None,
    report_type: str | None = None,
) -> float | None:
    """基于 perf 历史同阶段中位数，估算当前阶段剩余秒数。

    口径：取最近 ``_ETA_LOOKBACK_RUNS`` 次运行中同名阶段的耗时中位数，
    剩余 = 中位数 − 已耗时（下限 0）。

    Args:
        phase_name: 阶段名（与 PerfCollector.start 传入一致）。
        elapsed_seconds: 当前阶段已耗时秒数。
        history: 历史记录注入（测试用）；None 时读 perf_history.jsonl。
        report_type: 限定样本的报告类型（None = 不限定）。

    Returns:
        预计剩余秒数；历史无该阶段样本（含 history 缺失、report_type 不匹配）
        返回 None；**任何异常静默返回 None**（调用方降级为无 ETA，不打断生成）。
    """
    try:
        records = load_history() if history is None else history
        samples: list[float] = []
        for rec in records[-_ETA_LOOKBACK_RUNS:]:
            if report_type is not None and rec.get("report_type") != report_type:
                continue
            sec = _phase_seconds(rec.get("phases"), phase_name)
            if sec is not None:
                samples.append(sec)
        if not samples:
            return None
        return max(0.0, round(statistics.median(samples) - float(elapsed_seconds), 1))
    except Exception:
        logger.debug("[perf] 阶段 ETA 预估失败（%s），静默降级为无 ETA", phase_name, exc_info=True)
        return None


def _phase_seconds(phases: Any, phase_name: str) -> float | None:
    """从历史记录的 phases 字段取指定阶段耗时（dict 形状；非 dict 记录不计样本）。"""
    if isinstance(phases, dict):
        sec = phases.get(phase_name)
    else:
        return None
    if isinstance(sec, bool) or not isinstance(sec, (int, float)) or sec < 0:
        return None
    return float(sec)


def format_stage_status(status: dict[str, Any], eta: float | None) -> str:
    """阶段状态单行文案 — 所有进度通道共用的唯一格式化点（同源）。

    形如 ``「LLM+新闻」· 已耗时 12s · 预计剩余 ~284s``；eta 为 None 时仅显示
    已耗时。Web 前端展示时外层自带「当前阶段（第 N 步）：」前缀。
    """
    phase = status.get("phase") or ""
    elapsed = float(status.get("elapsed") or 0.0)
    line = f"「{phase}」· 已耗时 {elapsed:.0f}s"
    if eta is not None:
        line += f" · 预计剩余 ~{eta:.0f}s"
    return line
