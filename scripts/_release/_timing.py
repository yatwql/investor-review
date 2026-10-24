"""发布编排耗时埋点 —— 分步计时与 `logs/release.jsonl` 追加记录。

为什么单独成模块：发布墙钟（prepare / refresh / evolution / gate / publish 各步耗时）
此前只在终端打印、不落盘，整改（结论缓存 / 门禁并行 / bench 并行采集）的效果无法跨
版本对拍——每次都要现场重测。本模块把每步耗时写成一行 JSON：

    {"ts": "2026-01-01T10:00:00+08:00", "command": "gate", "ok": true,
     "elapsed_s": 13.6, "version": "x.y.z-dev",
     "steps": [{"step": "P2 场景回归", "elapsed_s": 13.1}]}

`logs/` 属 git 忽略域（不入仓库、不进 `folders.md` 目录树、无门禁依赖），记录失败一律
降级为 `[!]` 提示，绝不阻断发布——埋点是**观测面**，不是门禁面。

拆分纪律同 `_release/_common.py`：只收显式参数（路径/文本由调用方传入），不读入口
模块的路径常量，保证测试对入口模块属性的重定向始终生效。
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path


def now_iso() -> str:
    """本地时区 ISO 时间戳（秒精度，含偏移）——便于跨机/跨时区对拍。"""
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


#: 台账保留条数上限（一次发布约 7 条，500 条覆盖数十次发布；防无界增长）
RELEASE_LOG_MAX_LINES = 500


class StepTimer:
    """分步计时器：收集命令内各步耗时，并提供总墙钟。"""

    def __init__(self) -> None:
        self._t0 = time.perf_counter()
        self.steps: list[dict] = []

    @contextmanager
    def step(self, label: str, **extra):
        """`with timer.step("标签"):` —— 退出时记录该步耗时（异常路径同样记录）。"""
        started = time.perf_counter()
        try:
            yield
        finally:
            self.mark_elapsed(label, started, **extra)

    def mark_elapsed(self, label: str, started_at: float, **extra) -> dict:
        """按起点时刻补记一步（用于不便包 `with` 的多分支/早退代码块）。"""
        entry = {"step": label, "elapsed_s": round(time.perf_counter() - started_at, 2), **extra}
        self.steps.append(entry)
        return entry

    def step_seconds(self, label: str) -> float | None:
        """取某步耗时（同名多步取首次）；未记录返回 None。"""
        for entry in self.steps:
            if entry["step"] == label:
                return entry["elapsed_s"]
        return None

    @property
    def total(self) -> float:
        """自计时器创建至今的总墙钟（秒，两位小数）。"""
        return round(time.perf_counter() - self._t0, 2)

    @property
    def steps_total(self) -> float:
        """各步耗时之和（用于直观确认「步内已覆盖大头」）。"""
        return round(sum(entry["elapsed_s"] for entry in self.steps), 2)

    def summary(self) -> str:
        """`步名 1.2s · 步名 0.3s` 形式的一行摘要（无步时为空串）。"""
        return " · ".join(f"{entry['step']} {entry['elapsed_s']:.1f}s" for entry in self.steps)


def build_record(
    command: str,
    elapsed_s: float,
    ok: bool,
    steps: list[dict] | None = None,
    version: str = "",
    session_usage: dict | None = None,
    agent: dict | None = None,
    failure: dict | None = None,
) -> dict:
    """构造一条耗时记录（字段顺序固定，便于人工扫读与 jq 取值）。

    ``session_usage``：该命令结束时 agent 会话的**累计** token 用量快照
    （`session_usage()` 产出；非 agent 环境下为 None，字段省略）。累计值使
    「发布窗口用量」= 末行 − 边界行，无需逐行记账。

    ``agent``：执行本次发布的 agent 身份（`agent_identity()` 产出：provider /
    model / thinking / session_id）——回答「这版是谁（哪个模型、什么思考档）发的」；
    非 agent 环境下同样省略。

    ``failure``：失败命令的原因快照（失败步 / 退出码 / 报告目录 / 失败用例名 /
    输出尾部）——失败记录只有 ok=false 时无法回答「折在哪、为什么」，复盘
    只能去报告归档里按时间反查；有该字段就能直接读台账。
    """
    record = {
        "ts": now_iso(),
        "command": command,
        "ok": bool(ok),
        "elapsed_s": round(float(elapsed_s), 2),
        "version": version,
        "steps": list(steps or ()),
    }
    if failure:
        record["failure"] = dict(failure)
    if agent:
        record["agent"] = dict(agent)
    if session_usage:
        record["session_usage"] = dict(session_usage)
    return record


def append_record(path: Path, record: dict, *, max_lines: int = RELEASE_LOG_MAX_LINES) -> Path:
    """追加一行耗时记录（有界 + 原子），返回目标路径。

    实现委托 `core/jsonl_store.append_jsonl_atomic`（全仓 JSONL 原子追加的单一原语，
    已被 perf_history / 各类账本采用）——不在这里另写一份写盘：直接 `open("a")` 既
    违反原子写入约束（崩溃可留下半行），也无上限（每跑一次 release 子命令就多一行，
    无界增长）。`max_lines` 只留最近若干条，足够跨版本对拍。
    """
    from src.python.core.jsonl_store import append_jsonl_atomic

    line = json.dumps(record, ensure_ascii=False) + "\n"
    ok = append_jsonl_atomic(
        str(path), line, prefix=".release_log_", log_tag="release", noun="发布耗时台账", max_lines=max_lines
    )
    if not ok:
        raise OSError(f"写入失败：{path}")
    return Path(path)


# ── 会话 token 用量采集（发布编排在同一 agent 会话内执行） ──────────────

#: 会话 JSONL 里参与统计的条目类型（与 pi 的 session-format 一致）：
#: assistant 消息、非消息用量（如 cache_warm）、压缩摘要用量 —— 三者都计入会话总量。
_USAGE_ROLES = frozenset({"assistant"})


def agent_identity(env: dict | None = None) -> dict:
    """当前 agent 执行环境身份（provider / model / thinking / session）。

    数据源为 pi 注入的环境变量（非配置文件）：``PI_PROVIDER`` / ``PI_MODEL`` /
    ``PI_REASONING_LEVEL`` / ``PI_SESSION_ID``。非 agent 环境（CI、手动 shell）下这些
    变量缺失 → 返回空 dict，调用方据此省略字段，台账形状保持不变。

    ``env`` 参数只用于测试注入（缺省读 ``os.environ``）。
    """
    src = os.environ if env is None else env
    identity = {
        "provider": (src.get("PI_PROVIDER") or "").strip(),
        "model": (src.get("PI_MODEL") or "").strip(),
        "thinking": (src.get("PI_REASONING_LEVEL") or "").strip(),
        "session_id": (src.get("PI_SESSION_ID") or "").strip(),
    }
    return {k: v for k, v in identity.items() if v}


def _zero_usage() -> dict:
    return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "total": 0, "cost": 0.0}


def _add_usage(acc: dict, usage: dict) -> None:
    """把一条 pi `Usage` 累加进聚合器（字段名 snake 化，缺项按 0）。"""
    acc["input"] += int(usage.get("input") or 0)
    acc["output"] += int(usage.get("output") or 0)
    acc["cache_read"] += int(usage.get("cacheRead") or 0)
    acc["cache_write"] += int(usage.get("cacheWrite") or 0)
    acc["total"] += int(usage.get("totalTokens") or 0)
    cost = usage.get("cost") or {}
    acc["cost"] += float(cost.get("total") or 0.0)


def session_usage(session_file: str | Path | None) -> dict:
    """读取 agent 会话 JSONL，返回**累计** token 用量（无文件/不可读时返回空 dict）。

    数据源是 pi 会话文件（`PI_SESSION_FILE`），三类条目都计入会话总量
    （与 pi 自身的 session token 统计同口径）：

    - ``message`` 且 ``message.role == "assistant"`` → ``message.usage``
    - ``usage``（非消息用量，如 ``cache_warm``）→ ``usage``
    - ``compaction``（摘要生成）→ ``usage``

    实现刻意**容错**：文件缺失、单行 JSON 损坏、字段类型异常都只跳过该条——
    埋点是观测面，采集失败绝不阻断发布。
    """
    if not session_file:
        return {}
    path = Path(session_file)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    acc = _zero_usage()
    seen = False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        kind = entry.get("type")
        usage = None
        if kind == "message":
            message = entry.get("message") or {}
            if message.get("role") in _USAGE_ROLES:
                usage = message.get("usage")
        elif kind in ("usage", "compaction"):
            usage = entry.get("usage")
        if isinstance(usage, dict):
            _add_usage(acc, usage)
            seen = True
    return acc if seen else {}


def release_token_usage(records: list[dict]) -> dict:
    """按台账记录推算「上一次 devbump 之后」的发布窗口 token 用量。

    `records` 为 `logs/release.jsonl` 的行（按时间顺序）。算法：以最后一条
    ``devbump`` 为窗口外边界，取其后各行的会话累计用量快照；窗口用量 =
    末行累计 − 边界累计（无边界时以会话起点 0 计）。**跨会话**（agent 重启后
    累计从 0 重新开始）按正增量分段累加，避免出现负数。
    """
    snaps = [(r.get("command"), r.get("session_usage") or {}) for r in records]
    if not snaps:
        return {}
    boundary = -1
    for idx, (command, _usage) in enumerate(snaps):
        if command == "devbump":
            boundary = idx
    window = snaps[boundary + 1 :]
    if not window:
        return {}
    base = _zero_usage() if boundary < 0 else {**_zero_usage(), **(snaps[boundary][1] or {})}
    acc = _zero_usage()
    prev = {**_zero_usage(), **base}
    for _command, usage in window:
        if not usage:
            continue
        cur = {**_zero_usage(), **usage}
        for key in ("input", "output", "cache_read", "cache_write", "total"):
            delta = cur[key] - prev[key]
            acc[key] += delta if delta > 0 else cur[key]  # 负增量 = 会话重启
        cost_delta = cur["cost"] - prev["cost"]
        acc["cost"] += cost_delta if cost_delta > 0 else cur["cost"]
        prev = cur
    return acc


def format_agent(agent: dict) -> str:
    """把 agent 身份格式化为 `provider/model（thinking=…）` 形式（无数据时返回空串）。"""
    if not agent or not agent.get("model"):
        return ""
    label = f"{agent.get('provider', '')}/{agent.get('model')}".lstrip("/")
    thinking = agent.get("thinking")
    return f"{label}（thinking={thinking}）" if thinking else label


def format_tokens(usage: dict) -> str:
    """把 token 用量格式化为一行摘要（无数据时返回空串）。"""
    if not usage or not usage.get("total"):
        return ""
    return (
        f"{usage['total']:,} tok（in {usage['input']:,} / out {usage['output']:,} / "
        f"cache r {usage['cache_read']:,} w {usage['cache_write']:,}，≈¥{usage['cost']:.2f}）"
    )
