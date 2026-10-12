"""持仓快照持久化：保存/加载/列表/清理。

所有文件写入委托 `core/atomic_write`（mkstemp + os.replace 原子写）。
竞争条件防护：快照文件名使用时间戳（snapshot_{timestamp}.json）。

命名空间（namespace）：快照可按隔离域读写（如 web 试算域 `web`），
落在 `HISTORY_SNAPSHOT_DIR/{namespace}/` 子目录；`namespace=None` 时读写
共享主目录（默认行为，TUI/CLI 不变）。namespace 值经白名单校验
（仅小写字母/数字/`-`/`_`，拒绝路径分隔符），防路径穿越。

用法：
  >>> from src.python.schemas.history import SnapshotData, AccountSnapshot
  >>> sd = SnapshotData(...)
  >>> path = save(sd)                # 共享主目录（默认）
  >>> path = save(sd, "web")         # web 试算隔离域
  >>> latest = load_latest("web")    # 读 web 域最新
  >>> baseline = load_comparison_baseline("20261011T215611")  # 环比基线（跳过同一交易日）
  >>> all_snapshots = list_all()
  >>> prune(max_count=12)
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any

from src.python.core.atomic_write import write_text_atomic

from src.python.core.constants import (
    HISTORY_SNAPSHOT_DIR,
    HISTORY_SNAPSHOT_MAX_COUNT,
    HISTORY_SNAPSHOT_RETENTION_DAYS,
)
from src.python.schemas.history import AccountSnapshot, SnapshotData, SnapshotHolding

logger = logging.getLogger("invest")

# ── 命名空间 ──────────────────────────────────────────────
# 允许的 namespace 字符集：小写字母/数字/`-`/`_`（目录段安全，无路径分隔符）
_NAMESPACE_RE = re.compile(r"^[a-z0-9_-]+$")


def _namespace_dir(namespace: str | None) -> str:
    """解析命名空间对应的快照目录。

    Args:
        namespace: 隔离域标识（None=共享主目录，如 "web"=web 试算域）。

    Returns:
        对应目录绝对路径。

    Raises:
        ValueError: namespace 含非法字符（非小写字母/数字/`-`/`_`）时。
    """
    if namespace is None:
        return HISTORY_SNAPSHOT_DIR
    _validate_namespace(namespace)
    return os.path.join(HISTORY_SNAPSHOT_DIR, namespace)


def _validate_namespace(namespace: str) -> None:
    """校验 namespace 值合法性（防路径穿越）。

    仅允许小写字母/数字/`-`/`_`；拒绝 `..`、`/`、`\\` 等路径分隔符。
    """
    if not _NAMESPACE_RE.match(namespace):
        raise ValueError(f"非法快照命名空间 {namespace!r}：仅允许小写字母/数字/'-'/'_'")


# ── JSON 编解码辅助 ──────────────────────────────────────────


def _holding_to_dict(h: SnapshotHolding) -> dict[str, Any]:
    return {
        "code": h.code,
        "name": h.name,
        "shares": h.shares,
        "cost_price": h.cost_price,
        "market_value": h.market_value,
        "daily_pnl": h.daily_pnl,
        "total_pnl": h.total_pnl,
        "cost_total": h.cost_total,
    }


def _holding_from_dict(d: dict[str, Any]) -> SnapshotHolding:
    return SnapshotHolding(
        code=d["code"],
        name=d.get("name", ""),
        shares=d.get("shares", 0.0),
        cost_price=d.get("cost_price", 0.0),
        market_value=d.get("market_value", 0.0),
        daily_pnl=d.get("daily_pnl", 0.0),
        total_pnl=d.get("total_pnl", 0.0),
        cost_total=d.get("cost_total", 0.0),
    )


def _account_to_dict(a: AccountSnapshot) -> dict[str, Any]:
    return {
        "account_name": a.account_name,
        "holdings": [_holding_to_dict(h) for h in a.holdings],
    }


def _account_from_dict(d: dict[str, Any]) -> AccountSnapshot:
    return AccountSnapshot(
        account_name=d["account_name"],
        holdings=tuple(_holding_from_dict(h) for h in d.get("holdings", [])),
    )


def _snapshot_to_dict(sd: SnapshotData) -> dict[str, Any]:
    return {
        "accounts": [_account_to_dict(a) for a in sd.accounts],
        "total_value": sd.total_value,
        "total_cost": sd.total_cost,
        "total_pnl": sd.total_pnl,
        "total_pnl_pct": sd.total_pnl_pct,
        "timestamp": sd.timestamp,
        "fingerprint": sd.fingerprint,
        "llm_summary": sd.llm_summary,
    }


def _snapshot_from_dict(d: dict[str, Any]) -> SnapshotData:
    return SnapshotData(
        accounts=tuple(_account_from_dict(a) for a in d.get("accounts", [])),
        total_value=d.get("total_value", 0.0),
        total_cost=d.get("total_cost", 0.0),
        total_pnl=d.get("total_pnl", 0.0),
        total_pnl_pct=d.get("total_pnl_pct", 0.0),
        timestamp=d.get("timestamp", ""),
        fingerprint=d.get("fingerprint", ""),
        llm_summary=d.get("llm_summary", ""),
    )


# ── 公开 API ────────────────────────────────────────────────


def save(snapshot: SnapshotData, namespace: str | None = None) -> str:
    """将 SnapshotData 保存为快照 JSON 文件。

    原子写入委托 `core/atomic_write`（同目录临时文件 + os.replace）。
    文件名格式：snapshot_{timestamp}.json（timestamp = ISO 格式）。

    Args:
        snapshot: 要保存的快照数据
        namespace: 隔离域标识（None=共享主目录，如 "web"=web 试算域）

    Returns:
        已写入文件的绝对路径

    Raises:
        OSError: 目录创建或文件写入失败
        ValueError: namespace 含非法字符时
    """
    snap_dir = _namespace_dir(namespace)
    os.makedirs(snap_dir, exist_ok=True)

    ts = snapshot.timestamp or datetime.now().strftime("%Y%m%dT%H%M%S")
    filename = f"snapshot_{ts}.json"
    final_path = os.path.join(snap_dir, filename)

    data = _snapshot_to_dict(snapshot)
    content = json.dumps(data, ensure_ascii=False, indent=2)

    # 原子写入：委托 core/atomic_write（唯一原语，mkstemp + os.replace）。
    # 本函数的契约是**失败即抛**（见 docstring Raises），故把原语的布尔成败还原
    # 为 OSError——原语只记日志不抛出（其调用方多为「尽力持久化」场景），此处
    # 必须显式还原，否则写盘失败会被静默吞成"已保存"。
    if not write_text_atomic(
        final_path,
        content,
        prefix=".snapshot_tmp_",
        log_tag="history_snapshot",
        noun="快照",
    ):
        raise OSError(f"快照写入失败: {final_path}")

    logger.info("[history_snapshot] 快照已保存: %s (%d KB)", filename, len(content) // 1024)
    return final_path


def load_latest(namespace: str | None = None) -> SnapshotData | None:
    """加载最新的快照文件（按 mtime）。

    从快照目录中查找所有 snapshot_*.json 文件，
    返回 mtime 最大的那个的解析结果。

    Args:
        namespace: 隔离域标识（None=共享主目录，如 "web"=web 试算域）

    Returns:
        SnapshotData 或 None（无快照文件时）

    Raises:
        ValueError: namespace 含非法字符时
    """
    snapshots = _list_snapshot_files(namespace)
    if not snapshots:
        return None

    latest = max(snapshots, key=lambda p: os.path.getmtime(p))
    return _load_file(latest)


#: 快照时间戳可解析格式族（紧凑格式在前，与 save() 写盘格式一致）
_SNAPSHOT_TS_FORMATS = (
    "%Y%m%dT%H%M%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%Y%m%d",
)


def _parse_snapshot_timestamp(ts: str) -> datetime | None:
    """解析快照时间戳（紧凑/ISO 格式族）；不可解析返回 None。"""
    for fmt in _SNAPSHOT_TS_FORMATS:
        try:
            return datetime.strptime(ts, fmt)
        except (ValueError, TypeError):
            continue
    return None


def load_comparison_baseline(current_ts: str, namespace: str | None = None) -> SnapshotData | None:
    """加载环比比对基线：域内所属交易日早于本次报告的最新一份快照。

    同一交易日可能多次生成报告，与“上一份”比对时净值未变、结论无信息量；
    基线因此跳过与 ``current_ts`` 同属一个交易日的全部快照，取**更早交易日中
    时间戳最新**的一份——即“上一个有报告的交易日的最新一份报告”（中间隔日
    未跑时自然落到更早可用快照）。交易日归属经
    ``core.trading_calendar.trading_day_as_of``（盘前 <9:30 归前一交易日、
    节假日回溯；交易日历不可用回退排除周六日），与报告头“所属交易日”同口径。

    降级与容错：
      - ``current_ts`` 不可解析 → 回退 :func:`load_latest`（退化为“上一份”旧口径，不阻塞环比）
      - 候选快照内部时间戳不可解析或文件损坏 → 随 ``load_all`` 自动跳过
      - 域内无快照或无更早交易日快照 → None（调用方按首次运行口径隐藏环比）

    Args:
        current_ts: 本次报告快照时间戳（``YYYYMMDDTHHMMSS``，兼容 ISO）
        namespace: 隔离域标识（None=共享主目录，如 "web"=web 试算域）

    Returns:
        基线快照 SnapshotData；无可比基线时 None。

    Raises:
        ValueError: namespace 含非法字符时
    """
    current = _parse_snapshot_timestamp(current_ts or "")
    if current is None:
        logger.debug("[history_snapshot] 基线时间戳不可解析 %r，回退最新一份快照", current_ts)
        return load_latest(namespace)

    candidates = load_all(namespace)
    if not candidates:
        return None

    from src.python.core.trading_calendar import trading_day_as_of

    current_td = trading_day_as_of(current)
    eligible: list[tuple[datetime, SnapshotData]] = []
    for sd in candidates:
        parsed = _parse_snapshot_timestamp(sd.timestamp or "")
        if parsed is None:
            continue
        # 所属交易日更早才可比（trading_day_as_of 随时钟单调，早于当前交易日
        # 的候选必然也是更早的时点）；同交易日候选一律跳过
        if trading_day_as_of(parsed) < current_td:
            eligible.append((parsed, sd))
    if not eligible:
        return None

    # 取时间戳最新者（load_all 已跳过损坏文件）
    eligible.sort(key=lambda item: item[0], reverse=True)
    return eligible[0][1]


def load_all(namespace: str | None = None) -> list[SnapshotData]:
    """加载全部快照（按时间戳升序），供多期趋势聚合（组合演进）。

    Args:
        namespace: 隔离域标识（None=共享主目录，如 "web"=web 试算域）

    Returns:
        按 timestamp 升序排列的 SnapshotData 列表（损坏文件自动跳过）。
        无快照文件时返回空列表。

    Raises:
        ValueError: namespace 含非法字符时
    """
    snapshots: list[tuple[str, float, SnapshotData]] = []
    for path in _list_snapshot_files(namespace):
        ts = os.path.basename(path).replace("snapshot_", "").replace(".json", "")
        data = _load_file(path)
        if data is not None:
            snapshots.append((ts, os.path.getmtime(path), data))
    # 按时间戳升序；同名时间戳时按 mtime 兜底
    snapshots.sort(key=lambda x: (x[0], x[1]))
    return [sd for _, _, sd in snapshots]


def list_all(namespace: str | None = None) -> list[dict[str, Any]]:
    """列出所有快照文件的元信息（按 mtime 降序）。

    Args:
        namespace: 隔离域标识（None=共享主目录，如 "web"=web 试算域）

    Returns:
        每个元素包含 filename、mtime、timestamp（从文件名解析）、size 的 dict 列表。
        空列表表示无快照文件。

    Raises:
        ValueError: namespace 含非法字符时
    """
    files = _list_snapshot_files(namespace)
    entries = []
    for path in sorted(files, key=lambda p: os.path.getmtime(p), reverse=True):
        mtime = os.path.getmtime(path)
        basename = os.path.basename(path)
        size = os.path.getsize(path)
        # 从文件名解析时间戳：snapshot_{ts}.json
        ts = basename.replace("snapshot_", "").replace(".json", "")
        entries.append(
            {
                "filename": basename,
                "path": path,
                "mtime": mtime,
                "mtime_str": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp": ts,
                "size": size,
            }
        )
    return entries


def prune(
    retention_days: int = HISTORY_SNAPSHOT_RETENTION_DAYS,
    max_count: int = HISTORY_SNAPSHOT_MAX_COUNT,
    namespace: str | None = None,
) -> int:
    """删除超出保留天数和最大数量的旧快照文件。

    两阶段清理：
      1. 删除 mtime 早于 retention_days 天的文件（时间优先）
      2. 若剩余文件仍超过 max_count，再删除最旧的超出部分（数量兜底）

    多进程安全：删除基于逐个文件操作，不会因文件数突变而出错。

    Args:
        retention_days: 保留天数，默认 HISTORY_SNAPSHOT_RETENTION_DAYS (60)
        max_count: 最大保留数，默认 HISTORY_SNAPSHOT_MAX_COUNT (12)
        namespace: 隔离域标识（None=共享主目录，如 "web"=web 试算域）

    Returns:
        实际删除的文件数量

    Raises:
        ValueError: namespace 含非法字符时
    """
    from datetime import datetime

    files = _list_snapshot_files(namespace)
    if not files:
        return 0

    now = datetime.now().astimezone()
    deleted = 0
    kept: list[str] = []

    # 阶段 1：按保留天数删除
    for path in sorted(files, key=os.path.getmtime):
        mtime = datetime.fromtimestamp(os.path.getmtime(path)).astimezone()
        age_days = (now - mtime).total_seconds() / 86400
        if age_days > retention_days:
            try:
                os.unlink(path)
                deleted += 1
            except OSError as e:
                logger.warning("[history_snapshot] 删除失败 %s: %s", os.path.basename(path), e)
        else:
            kept.append(path)

    # 阶段 2：按最大数量兜底（仅对阶段 1 幸存文件再限制）
    if max_count > 0 and len(kept) > max_count:
        # 按 mtime 升序排列，删除最旧的超出部分
        kept_sorted = sorted(kept, key=os.path.getmtime)
        to_delete = kept_sorted[: len(kept_sorted) - max_count]
        for path in to_delete:
            try:
                os.unlink(path)
                deleted += 1
            except OSError as e:
                logger.warning("[history_snapshot] 删除失败 %s: %s", os.path.basename(path), e)

    if deleted:
        logger.info(
            "[history_snapshot] 清理了 %d 个旧快照（保留 %d 天内，最多 %d 个）", deleted, retention_days, max_count
        )
    return deleted


# ── 内部辅助 ────────────────────────────────────────────────


def _list_snapshot_files(namespace: str | None = None) -> list[str]:
    """列出快照目录中所有 snapshot_*.json 文件。

    Args:
        namespace: 隔离域标识（None=共享主目录，如 "web"=web 试算域）

    Returns:
        文件绝对路径列表，按文件名排序

    Raises:
        ValueError: namespace 含非法字符时
    """
    snap_dir = _namespace_dir(namespace)
    if not os.path.isdir(snap_dir):
        return []
    try:
        return [
            os.path.join(snap_dir, f) for f in os.listdir(snap_dir) if f.startswith("snapshot_") and f.endswith(".json")
        ]
    except OSError:
        return []


def _load_file(path: str) -> SnapshotData | None:
    """从指定路径加载并解析快照 JSON 文件。

    Args:
        path: 快照文件绝对路径

    Returns:
        SnapshotData 或 None（文件不存在/损坏）
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return _snapshot_from_dict(data)
    except (json.JSONDecodeError, OSError, KeyError) as e:
        logger.warning("[history_snapshot] 文件损坏 %s: %s", os.path.basename(path), e)
        return None
