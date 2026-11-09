"""test-reports 归档保留期清理 —— 「保留最近 N 次 + 总量上限」双闸门。

`test-reports/archives/` 每跑一次测试就多一份归档（`<YYYYMMDD>/<HHMMSS>/`），
长年累积会吃满本地磁盘与 CI runner（实测 31 份 ≈ 17G）。本模块按两个独立闸门裁剪：

  - **次数闸门**：只保留最近 `keep` 次运行（按日期/时刻目录名升序取尾部）；
  - **体积闸门**：保留集仍超过 `cap_mb` 时，从最旧的开始继续删，直到不超上限。

设计约束（与 `data/cache` 的 TTL 清理同款）：

  - **失败只告警**：归档清理是旁路，任何 OSError 都不得让测试跑不起来；
  - **不越界**：只处理 `archives/` 下两层目录（日期/时刻），其余文件不动；
  - **空父目录回收**：删完运行目录后清掉空的 `YYYYMMDD/`；
  - **幂等**：没有可删对象时返回零变更。
"""

from __future__ import annotations

import logging
import os
import shutil
from typing import Any

logger = logging.getLogger("invest")

#: 默认保留最近 10 次运行
DEFAULT_KEEP_RUNS = 10
#: 默认归档总量上限 2 GiB
DEFAULT_CAP_MB = 2048


def _run_dirs(archives_dir: str) -> list[str]:
    """列出归档下的「运行目录」（`<日期>/<时刻>` 两级，按名字升序 = 时间升序）。"""
    runs: list[tuple[str, str, str]] = []
    try:
        date_names = sorted(os.listdir(archives_dir))
    except OSError:
        return []
    for date_name in date_names:
        date_path = os.path.join(archives_dir, date_name)
        if not os.path.isdir(date_path):
            continue
        try:
            time_names = sorted(os.listdir(date_path))
        except OSError:
            continue
        for time_name in time_names:
            run_path = os.path.join(date_path, time_name)
            if os.path.isdir(run_path):
                runs.append((date_name, time_name, run_path))
    runs.sort(key=lambda item: (item[0], item[1]))
    return [run_path for _date, _time, run_path in runs]


def _dir_size_bytes(path: str) -> int:
    """目录递归体积（读不到的条目按 0 计，不抛）。"""
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                continue
    return total


def _remove_run(run_path: str) -> int | None:
    """删除一份运行归档，返回释放字节数；失败记警告并返回 None（不计入已删）。"""
    size = _dir_size_bytes(run_path)
    try:
        shutil.rmtree(run_path)
    except OSError as exc:  # 权限/占用：跳过这一份，不影响其余
        logger.warning("归档清理失败（跳过）%s: %s", run_path, exc)
        return None
    return size


def _drop_empty_date_dirs(archives_dir: str) -> None:
    """回收删空的日期层目录（不动有内容的目录）。"""
    try:
        date_names = os.listdir(archives_dir)
    except OSError:
        return
    for date_name in date_names:
        date_path = os.path.join(archives_dir, date_name)
        if not os.path.isdir(date_path):
            continue
        try:
            if not os.listdir(date_path):
                os.rmdir(date_path)
        except OSError:
            continue


def prune_archives(
    archives_dir: str,
    *,
    keep: int = DEFAULT_KEEP_RUNS,
    cap_mb: int = DEFAULT_CAP_MB,
) -> dict[str, Any]:
    """按次数与体积双闸门裁剪归档目录。

    Args:
        archives_dir: 归档根（`test-reports/archives`）。
        keep: 保留最近多少次运行（<=0 视为不启用次数闸门）。
        cap_mb: 保留集体积上限（MiB；<=0 视为不启用体积闸门）。

    Returns:
        ``{"removed": 删除次数, "freed_mb": 释放体积(MiB), "kept": 剩余次数,
        "total_mb": 剩余体积(MiB)}``；目录不存在时各项为 0。
    """
    runs = _run_dirs(archives_dir)
    if not runs:
        return {"removed": 0, "freed_mb": 0.0, "kept": 0, "total_mb": 0.0}

    survivors = list(runs)
    drop: list[str] = []
    if keep > 0 and len(survivors) > keep:
        drop = survivors[:-keep]
        survivors = survivors[-keep:]

    removed = 0
    freed = 0
    for run_path in drop:
        size = _remove_run(run_path)
        if size is None:
            survivors.append(run_path)  # 删不掉的仍算保留，避免统计虚报
            continue
        freed += size
        removed += 1

    # 体积闸门：仍超上限就从最旧的保留项开始继续删
    stuck: list[str] = []
    if cap_mb > 0:
        cap_bytes = cap_mb * 1024 * 1024
        sizes = {run: _dir_size_bytes(run) for run in survivors}
        total = sum(sizes.values())
        while total > cap_bytes and survivors:
            oldest = survivors.pop(0)
            size = sizes.pop(oldest, 0)
            removed_size = _remove_run(oldest)
            if removed_size is None:
                # 删不掉：记下来待本轮回填（若直接 continue 会让该份从统计里消失，
                # 剩声剩余次数/体积比磁盘实际值偏小），下次调用再试
                stuck.append(oldest)
                continue
            freed += removed_size
            total -= size
            removed += 1
    survivors.extend(stuck)

    _drop_empty_date_dirs(archives_dir)

    remaining_size = sum(_dir_size_bytes(run) for run in survivors)
    if removed:
        logger.info(
            "[retention] 归档清理：删除 %d 次运行，释放 %.1f MiB，保留 %d 次 / %.1f MiB",
            removed,
            freed / (1024 * 1024),
            len(survivors),
            remaining_size / (1024 * 1024),
        )
    return {
        "removed": removed,
        "freed_mb": round(freed / (1024 * 1024), 1),
        "kept": len(survivors),
        "total_mb": round(remaining_size / (1024 * 1024), 1),
    }
