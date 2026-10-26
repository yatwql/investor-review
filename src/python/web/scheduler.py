"""内置定时生成调度器（config.json ``scheduler`` 块，缺省关闭）。

Web 服务启动后随进程常驻一个 daemon 调度线程：按间隔单步评估「是否到达
今日触发时刻」——每步重读配置（Web 调度面板/手动改 config.json 即时生效，
无需重启）。触发即向 ``RunManager`` 提交「正式-用存量」生成：与手动生成
同队列同 worker 串行，天然同 run 互斥；队列有活动任务时在宽限窗内顺延重试，
宽限超时登记「错过」不再补跑。

触发状态按「计划签名 + 日期」持久化到 ``data/state/scheduler_fired.json``，
进程重启不重复触发；该文件的测试隔离见 ``src/test/_path_isolation.py``。
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Any

from src.python.config import get_config
from src.python.config import normalize_schedule_block, validate_schedule_block  # noqa: F401 — 面板与测试经本模块导入
from src.python.core.atomic_write import write_json_atomic
from src.python.core.constants import PROJECT_ROOT

logger = logging.getLogger("invest")

# 触发状态账本路径（测试经 src/test/_path_isolation.py 重定向到 tmp_path）
_FIRED_STATE_FILE = os.path.join(PROJECT_ROOT, "data", "state", "scheduler_fired.json")

# 调度评估间隔（秒）：面板改配置最迟一个间隔后生效
_TICK_INTERVAL_S = 30
# 触发窗宽限期（分钟）：过时刻后仍补触发的窗口；超窗登记「错过」
_FIRE_GRACE_MINUTES = 30
# 触发账本保留天数（超期条目写回时剔除，防长期膨胀）
_LEDGER_RETAIN_DAYS = 7


def parse_schedule(config: Any) -> dict | None:
    """从配置解析可执行计划；未启用/非法返回 None（非法项记 WARNING）。"""
    raw = config.get("scheduler") if isinstance(config, dict) else None
    if not isinstance(raw, dict) or raw.get("enabled") is not True:
        return None
    try:
        block = validate_schedule_block(raw)
    except ValueError as e:
        logger.warning("定时生成配置非法，本次不调度：%s", e)
        return None
    fire_minutes = int(block["time"][:2]) * 60 + int(block["time"][3:])
    return {**block, "minutes": fire_minutes}


def schedule_signature(schedule: dict) -> str:
    """计划签名（时刻+执行日+报告类型）：改任一参数视为新计划、当日可再触发。"""
    return f"{schedule['time']}|{','.join(str(d) for d in schedule['weekdays'])}|{schedule['report_type']}"


def next_fire_at(now: datetime, schedule: dict) -> datetime | None:
    """下一个触发时刻（严格 > now；今天未到点且逢执行日 → 今天）。"""
    for offset in range(8):
        day = (now + timedelta(days=offset)).date()
        if day.weekday() not in schedule["weekdays"]:
            continue
        candidate = datetime(day.year, day.month, day.day) + timedelta(minutes=schedule["minutes"])
        if candidate > now:
            return candidate
    return None  # 不可达：weekdays 非空时 8 天内必有匹配


def _load_fired() -> dict[str, str]:
    """读触发账本（计划签名 → 日期）；缺失按空账本，损坏记 ERROR 并按空处理。"""
    try:
        with open(_FIRED_STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        fired = data.get("fired")
        return {str(k): str(v) for k, v in fired.items()} if isinstance(fired, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        logger.exception("定时生成账本读取失败，按空账本处理（当日计划可能重复触发）")
        return {}


def _save_fired(fired: dict[str, str]) -> None:
    """写触发账本（经 `core/atomic_write` 唯一原子写原语），写回时剔除超保留期条目。

    写失败只记 ERROR、不向上抛：调度链路不为账本落盘失败中断，代价是重启后
    当日计划可能重复触发（与读取失败同一取舍）。
    """
    cutoff = (datetime.now() - timedelta(days=_LEDGER_RETAIN_DAYS)).strftime("%Y-%m-%d")
    pruned = {k: v for k, v in fired.items() if v >= cutoff}
    ok = write_json_atomic(
        _FIRED_STATE_FILE,
        {"fired": pruned},
        log_tag="scheduler",
        noun="定时生成账本",
    )
    if not ok:
        logger.error("定时生成账本写入失败（重启后当日计划可能重复触发）")


def status_payload(config: Any = None) -> dict:
    """GET /api/scheduler 载荷：归一化配置 + 下次触发预估 + 最近触发日。"""
    if config is None:
        config = get_config()
    block = normalize_schedule_block(config.get("scheduler") if isinstance(config, dict) else None)
    schedule = parse_schedule(config)
    now = datetime.now()
    fired = _load_fired()
    next_at = next_fire_at(now, schedule) if schedule else None
    return {
        **block,
        "next_fire": next_at.strftime("%Y-%m-%d %H:%M") if next_at else None,
        "last_fired": fired.get(schedule_signature(schedule)) if schedule else None,
        "grace_minutes": _FIRE_GRACE_MINUTES,
    }


class SchedulerService:
    """常驻调度线程：按间隔调用 :meth:`tick` 评估并触发生成。"""

    def __init__(self, run_manager: Any) -> None:
        self._run_manager = run_manager
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def tick(self, now: datetime | None = None) -> str:
        """单步调度评估（测试注入 now 直接驱动；线程循环按真实时钟调用）。

        Returns:
            动作标签：``disabled`` 未启用 / ``waiting`` 未到时刻或非执行日 /
            ``fired`` 已触发 / ``deferred`` 顺延（活动任务或队列满，宽限内重试）/
            ``missed`` 错过（超宽限，登记不再补）/ ``duplicate`` 今日已触发过。
        """
        schedule = parse_schedule(get_config())
        if schedule is None:
            return "disabled"
        now = datetime.now() if now is None else now
        if now.weekday() not in schedule["weekdays"]:
            return "waiting"
        now_minutes = now.hour * 60 + now.minute
        if now_minutes < schedule["minutes"]:
            return "waiting"
        signature = schedule_signature(schedule)
        today = now.strftime("%Y-%m-%d")
        fired = _load_fired()
        if fired.get(signature) == today:
            return "duplicate"
        if now_minutes > schedule["minutes"] + _FIRE_GRACE_MINUTES:
            fired[signature] = today
            _save_fired(fired)
            logger.warning(
                "定时生成错过触发窗（%s，宽限 %d 分钟已过），今日不再补跑", schedule["time"], _FIRE_GRACE_MINUTES
            )
            return "missed"
        # 与手动生成同队列互斥：有活动任务顺延（不登记，下个间隔重试）
        if any(r.status in ("queued", "running") for r in self._run_manager.list_runs(limit=50)):
            logger.info("定时生成到达时刻（%s），存在活动任务顺延重试", schedule["time"])
            return "deferred"
        run_id = self._run_manager.submit(
            {
                "file_id": None,
                "report_type": schedule["report_type"],
                "fetch_history": None,
                "force_llm": False,
                "llm_modules": None,
                "mode": "formal",
                "use_existing": True,
            }
        )
        if run_id is None:
            logger.warning("定时生成提交失败（队列已满），宽限窗内继续重试（%s）", schedule["time"])
            return "deferred"
        fired[signature] = today
        _save_fired(fired)
        logger.info("定时生成已触发（%s，报告类型 %s，run %s）", schedule["time"], schedule["report_type"], run_id)
        return "fired"

    def start(self) -> None:
        """启动 daemon 调度线程（幂等：已在运行则不重复启动）。"""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="web_scheduler", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """停止调度线程（测试收尾用；daemon 线程随进程退出兜底）。"""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _loop(self) -> None:
        """线程主循环：单步评估 + 间隔等待；异常兜底不得杀死调度线程。"""
        while not self._stop_event.is_set():
            try:
                self.tick()
            except Exception:
                logger.exception("定时生成调度 tick 异常（下一间隔继续）")
            self._stop_event.wait(_TICK_INTERVAL_S)
