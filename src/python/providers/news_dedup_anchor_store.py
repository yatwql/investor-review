"""新闻去重锚点 — **存储层**：分片命名/路径/汇总体积/读取/追加/原子替换。

锚点文件是「同对新闻已经见过」的边界样本库（阈值校准用），按
``dedup_anchors-YYYYMM.jsonl.gz`` 按月分片：写侧 multi-member gzip 追加（不重写既有
块），读侧透明解压。本模块只做**字节层**动作，保留期/体积目标/采样等策略在
``providers/news_dedup_anchor_policy.py``，去重主流程在 ``providers/news_dedup.py``。
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import threading
from datetime import datetime
from typing import Any

from src.python.core.constants import PROJECT_ROOT

logger = logging.getLogger("invest")

# ── 锚点采集（阈值校准用） ──────────────────────────────────────
# 边界案例收集（阈值校准用）**默认开启**（`INVEST_DEDUP_COLLECT_ANCHORS=0` 可关）：
# _dedup_by_title 记录、aggregate_news() 结束时**追加**至
# data/calibration/dedup_anchors-YYYYMM.jsonl.gz（按月分片、gzip 压缩、多 member 追加写），
# 不读旧文件（跨轮重复由校准工具按键去重）。锚点不参与去重判定。
# 一条记录为一个 JSON 行，append-only。格式：
#   {"ts","title_a","title_b","source_a","source_b",
#    "ratio","bigram_overlap","merged","rule","anchor_rules_version"}
_ANCHOR_LOCK = threading.Lock()
_ANCHOR_PATH = os.path.join(
    PROJECT_ROOT,
    "data",
    "calibration",
    "dedup_anchors.jsonl",
)
#: 分片命名：`dedup_anchors-YYYYMM.jsonl.gz`（按月一文件；写侧按 multi-member gzip 追加，
#: 读侧透明解压）。分片让单文件不会无限长，压缩只重写受影响的月份。
_ANCHOR_SHARD_PREFIX = "dedup_anchors-"
_ANCHOR_SHARD_SUFFIX = ".jsonl.gz"


def anchor_shard_paths(base: str | None = None) -> list[str]:
    """锚点分片路径列表（月份升序；末尾追加仍存在的未分片文件）。"""
    target = base or _ANCHOR_PATH
    directory = os.path.dirname(target) or "."
    try:
        names = sorted(
            name
            for name in os.listdir(directory)
            if name.startswith(_ANCHOR_SHARD_PREFIX) and name.endswith(_ANCHOR_SHARD_SUFFIX)
        )
    except OSError:
        names = []
    paths = [os.path.join(directory, name) for name in names]
    if os.path.exists(target):
        paths.append(target)
    return paths


def anchor_total_bytes(base: str | None = None) -> int:
    """锚点总体积（各分片 + 未分片文件之和；不含 `.bak` 与临时文件）。"""
    total = 0
    for path in anchor_shard_paths(base):
        try:
            total += os.path.getsize(path)
        except OSError:
            continue
    return total


def read_anchor_lines(base: str | None = None) -> list[str]:
    """读取全部锚点行（各月分片 + 未分片文件）。

    分片为 gzip，透明解压；单个分片损坏/截断时保留已读出的行并告警，不影响其它分片
    ——锚点只是校准样本，宁可少几行也不让整份历史不可读。
    """
    lines: list[str] = []
    for path in anchor_shard_paths(base):
        if path.endswith(".gz"):
            try:
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    lines.extend(f.readlines())
            except (OSError, EOFError) as e:
                logger.warning("[dedup] 锚点分片读取失败（跳过其余内容）：%s（%s）", os.path.basename(path), e)
            continue
        try:
            with open(path, encoding="utf-8") as f:
                lines.extend(f.readlines())
        except OSError as e:
            logger.warning("[dedup] 锚点文件读取失败：%s", e)
    return lines


def _anchor_shard_name(record: dict[str, Any]) -> str:
    """记录应归属的分片文件名（按 `ts`/`written_at` 的月份）。"""
    when = _anchor_parse_ts(record.get("ts")) or _anchor_parse_ts(record.get("written_at")) or datetime.now()
    return f"{_ANCHOR_SHARD_PREFIX}{when:%Y%m}{_ANCHOR_SHARD_SUFFIX}"


def _append_anchor_lines(lines: list[str]) -> bool:
    """以**追加**方式写入锚点行（不读全文、不整文件替换）。

    为什么不再走 ``append_jsonl_atomic_many``：该原语的原子性来自「读全文 → 整文件
    替换」，锚点文件实测 37.9 MB 且每次 flush 只有数十条新记录，等于为几十行重写
    几十 MB。单次 ``write`` + ``fsync`` 追加：

      - 单次 write 提交整批行（不逐行 write，减少半写窗口）；
      - 读侧本就逐行容错（``json.JSONDecodeError`` 跳过、压缩丢弃坏行），崩溃留下的
        半行不会污染既有记录；
      - 失败返回 False，由调用方撤回本次已登记的 key（与原子写语义一致）。

    Returns:
        是否落盘成功。
    """
    payload = "".join(line if line.endswith("\n") else line + "\n" for line in lines)
    if not payload:
        return True
    shard = os.path.join(
        os.path.dirname(_ANCHOR_PATH) or ".",
        f"{_ANCHOR_SHARD_PREFIX}{datetime.now():%Y%m}{_ANCHOR_SHARD_SUFFIX}",
    )
    try:
        os.makedirs(os.path.dirname(shard), exist_ok=True)
        # gzip 追加写 = 追加一个**新 member**（不重写既有压缩块），读侧按成员连续解压
        with gzip.open(shard, "at", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        return True
    except (OSError, EOFError) as e:
        logger.warning("[dedup] 锚点分片追加失败: %s", e)
        return False


#: 压缩后是否保留 `.bak`（`INVEST_DEDUP_KEEP_BACKUP=1` 打开）。默认不保留：
#: 新文件经解析校验 + ``os.replace`` 原子替换后才删备份，安全性由原子替换与本目录
#: 「可重建」语义保证；常驻备份会白占与主文件相当的磁盘（实测 37.9 MB）。
_ANCHOR_KEEP_BACKUP_ENV = "INVEST_DEDUP_KEEP_BACKUP"


def _compact_verified(path: str) -> bool:
    """压缩产物自检：非空且首/末行可解析（防写出半截文件后删掉备份）。"""
    try:
        if os.path.getsize(path) == 0:
            return False
        if ".jsonl.gz" in path:  # 含 `.compact.tmp` 中间态（此时扩展名已不是 .gz）
            with gzip.open(path, "rt", encoding="utf-8") as f:
                first = f.readline().strip()
        else:
            with open(path, encoding="utf-8") as f:
                first = f.readline().strip()
        if not first:
            return False
        json.loads(first)
        return True
    except (OSError, EOFError, json.JSONDecodeError):
        return False


def _anchor_parse_ts(value: Any) -> datetime | None:
    """解析锚点时间字段（缺省/非法 → None）。"""
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[: len(text)], fmt)
        except ValueError:
            continue
    return None
