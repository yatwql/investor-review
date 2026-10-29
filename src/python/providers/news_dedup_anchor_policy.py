"""新闻去重锚点 — **策略层**：保留期/体积目标/同源采样/裁剪编排。

策略只描述「哪些行该留、文件该多大」，字节动作（分片读写、原子替换、备份）在
``providers/news_dedup_anchor_store.py``；去重判定在 ``providers/news_dedup.py``。
``compact_anchor_file`` 是唯一裁剪实现（生产维护与 ``scripts/eval-dedup-threshold.py``
共用），工具侧只打印结果。
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import shutil
from datetime import datetime, timedelta
from typing import Any

from src.python.providers.news_dedup_rules import (
    ANCHOR_LEGACY_ERA,
    ANCHOR_RULES_FIELD,
    _ANCHOR_RULES_VERSION,
    anchor_rules_version,
)
from src.python.providers import news_dedup_anchor_store as _anchor_store
from src.python.providers.news_dedup_anchor_store import (
    _ANCHOR_KEEP_BACKUP_ENV,
    _ANCHOR_LOCK,
    _anchor_parse_ts,
    _anchor_shard_name,
    _append_anchor_lines,
    _compact_verified,
    anchor_shard_paths,
    anchor_total_bytes,
    read_anchor_lines,
)

logger = logging.getLogger("invest")

#: 本批次待写的锚点（写侧批内缓冲）：积攒后一次性追加进当月分片。
#: 与存储层的 ``_ANCHOR_LOCK`` 共用同一把锁（append 与 flush 互斥）。
_ANCHOR_RECORDS: list[dict[str, Any]] = []


def reset_anchor_records() -> None:
    """清空批次缓冲（报告边界/测试隔离用；不落盘）。"""
    global _ANCHOR_RECORDS
    with _ANCHOR_LOCK:
        _ANCHOR_RECORDS = []


#: 体积告警线：超过此值在加载时提醒压缩（flush 写全文、加载解析全文件，均是全文成本）
_ANCHOR_SIZE_WARN_BYTES = 32 * 1024 * 1024
#: 体积告警线：超过时记录一次维护提示；实际裁剪目标见 `_ANCHOR_SIZE_TARGET_BYTES`，
#: 压缩只在评估/维护路径执行（报告路径不压缩）。
#: 压缩保留每个标题对的**最新一条**（文件 append-only → 最后即最新），并先备份 .bak。
#: 用 `INVEST_DEDUP_AUTO_COMPACT=0` 可关闭维护压缩（仅保留告警）。
_ANCHOR_COMPACT_ENV = "INVEST_DEDUP_AUTO_COMPACT"
#: 采集开关（默认开启）：边界案例持续积累供诊断/阈值校准；显式设 0 可关闭。
#: 采集与去重判定解耦——写侧只追加、不读 39MB 旧文件（跨轮重复由校准工具按键去重）。
_ANCHOR_COLLECT_ENV = "INVEST_DEDUP_COLLECT_ANCHORS"
#: 压缩时的保留期（天）：锚点只服务于「近期同对新闻不重复追加 + 周期性阈值校准」，
#: 过期记录没有消费者。仅按 key 去重无法压小文件（标题对高度唯一，实测重复率 0.000），
#: 保留期才是时间维度的上限；`INVEST_DEDUP_ANCHOR_RETENTION_DAYS` 可覆盖（0 = 不限）。
#: 30 天的依据：实测该窗口保留 68% 行（≈23 MB）而校准样本量仍远超「≥50/100 条」建议值。
_ANCHOR_RETENTION_DAYS = 30
_ANCHOR_RETENTION_ENV = "INVEST_DEDUP_ANCHOR_RETENTION_DAYS"

#: 体积裁剪目标（低于告警线，留缓冲避免下一次运行立刻再越线）：告警线只提示，
#: 目标线才真裁——二者语义不同，不要合并成一个常量。
_ANCHOR_SIZE_TARGET_BYTES = 24 * 1024 * 1024
#: 体积裁剪时每个分支至少保留的最新条数：小分支（方向对立等只有几十条）不会被
#: 整类裁光，否则校准报告会误报「该规则没生效」。
_ANCHOR_BRANCH_MIN_KEEP = 50

#: 同源锚点规则名（写侧按此采样，避免与判定分支名对不上）
_SAME_SRC_RULE = "same_src"
#: 同源锚点采样分母（确定性：按标题对哈希取模，同一对恒定入选或恒定跳过）。
#: 同源样本只服务「同一源合并阈值」校准，而 2~5 的 bigram 区间样本极密（实测占
#: 锚点文件 61%，且 ``ratio`` 恒为占位值 0.0）；按 1/N 采样后样本量仍远超校准所需
#: （工具建议 ≥50 条），体积增长降到可忽略。1 = 全量采集，0 = 不采该规则。
_SAME_SRC_ANCHOR_SAMPLE = 50


def _anchor_key(record: dict[str, Any]) -> str:
    """锚点去重键：source 对 + 标题对（顺序无关）。"""
    a = (record.get("source_a", "") or "", record.get("title_a", "") or "")
    b = (record.get("source_b", "") or "", record.get("title_b", "") or "")
    # 排序使 (A,B) 与 (B,A) 视为同一对，避免来源顺序不同产生重复
    sa, ta = (a, b) if a <= b else (b, a)
    return f"{sa[0]}|{sa[1]}|{ta[0]}|{ta[1]}"


def _anchor_collection_enabled() -> bool:
    """是否采集去重锚点（默认开启；``INVEST_DEDUP_COLLECT_ANCHORS=0`` 可关闭）。"""
    raw = os.environ.get(_ANCHOR_COLLECT_ENV, "1")
    return str(raw).strip().lower() not in ("0", "", "false", "no")


def _anchor_retention_days() -> int:
    """保留期天数（环境变量覆盖；非法值回落默认，0 表示不按时间裁剪）。"""
    raw = os.environ.get(_ANCHOR_RETENTION_ENV)
    if raw is None or not str(raw).strip():
        return _ANCHOR_RETENTION_DAYS
    try:
        return max(0, int(float(str(raw).strip())))
    except (TypeError, ValueError):
        return _ANCHOR_RETENTION_DAYS


def _anchor_retention_cutoff(days: int | None = None) -> datetime | None:
    """保留期起点（None = 不裁剪）。

    以「今天 − N 天」为界；压缩与读取都按此判定，使体积有确定上限。
    ``days`` 缺省取 :func:`_anchor_retention_days`（环境变量/默认值）；
    显式传 0 表示不按时间裁剪（供校准脚本的 ``--retention-days 0``）。
    """
    effective = _anchor_retention_days() if days is None else max(0, int(days))
    if effective <= 0:
        return None
    return datetime.now() - timedelta(days=effective)


def _anchor_ts_on_or_after(ts: Any, cutoff: datetime) -> bool:
    """记录 `ts`（"YYYY-MM-DD" / "YYYY-MM-DD HH:MM"）是否在保留期内。

    无法解析的记录**保留**（宁可留一条无用行，也不因格式演进静默丢历史）。
    """
    text = str(ts or "").strip()
    if not text:
        return True
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[: len(text)], fmt) >= cutoff
        except ValueError:
            continue
    return True


def _anchor_within_retention(record: dict[str, Any], cutoff: datetime | None) -> bool:
    """记录是否在保留期内：`ts`（发布时间）或 `written_at`（写入时刻）任一在窗口内即保留。

    只按 `ts` 判定会误伤补录/回溯抓到的老新闻——这类记录 `ts` 很老但刚写入，一压缩
    就消失。早期记录没有 `written_at`，退化为只按 `ts` 判定（缺失仍视为保留）。
    """
    if cutoff is None:
        return True
    if _anchor_ts_on_or_after(record.get("ts"), cutoff):
        return True
    written = _anchor_parse_ts(record.get("written_at"))
    return bool(written and written >= cutoff)


def _anchor_branch(record: dict[str, Any]) -> str:
    """记录所属判定分支（体积裁剪按分支保留配额用）。"""
    return str(record.get("rule") or "")


def compact_anchor_file(
    path: str | None = None,
    *,
    dry_run: bool = False,
    retention_days: int | None = None,
    target_bytes: int | None = None,
    branch_min_keep: int | None = None,
) -> dict[str, Any]:
    """压缩锚点文件：每 key 最新 + 保留期 + 体积上限（分支配额保护），返回统计字典。

    三重条件取交集：

    1. **每 key 最新**：文件 append-only，最后一行即最新；重复行对校准无信息量。
    2. **保留期**（默认 :data:`_ANCHOR_RETENTION_DAYS`）：`ts` 或 `written_at` 任一在
       窗口内即保留（补录老新闻不会被秒裁）。
    3. **体积上限**（默认 :data:`_ANCHOR_SIZE_TARGET_BYTES`）：裁完仍超目标时按时间从最旧
       继续丢直到达标；每个分支保留最新的 ``branch_min_keep`` 条不被裁剪——小分支
       （方向对立等只有几十条）不会整类消失，否则校准报告会误报「该规则没生效」。

    并发安全：读取前后比对 ``(size, mtime_ns)``，期间被并发追加则放弃本次压缩并在结果
    标 ``aborted``（不加锁也不吞并发写入）。无行可裁且无需补标注时**不重写**文件
    （避免几十 MB 的空转重写）。

    Returns:
        统计字典：``before_lines`` / ``after_lines`` / ``before_bytes`` / ``after_bytes`` /
        ``unique_keys`` / ``legacy_era``（丢弃的重复行中指纹不一致的条数）/
        ``unattributed``（补 legacy 标注的行数）/ ``expired``（超保留期丢弃）/
        ``trimmed`` / ``trimmed_by_branch``（体积裁剪）/ ``retention_days`` /
        ``aborted``（放弃原因）/ ``written``（是否已写盘）。
    """
    target_path = path or _anchor_store._ANCHOR_PATH
    retention = _anchor_retention_days() if retention_days is None else max(0, int(retention_days))
    stats: dict[str, Any] = {
        "before_lines": 0,
        "after_lines": 0,
        "before_bytes": 0,
        "after_bytes": 0,
        "unique_keys": 0,
        "legacy_era": 0,
        "unattributed": 0,
        "expired": 0,
        "trimmed": 0,
        "trimmed_by_branch": {},
        "retention_days": retention,
        "aborted": None,
        "written": False,
        "shards": [],
    }
    snapshot: dict[str, tuple[int, int]] = {}
    for anchor_path in anchor_shard_paths(target_path):
        try:
            st = os.stat(anchor_path)
        except OSError:
            continue
        snapshot[anchor_path] = (st.st_size, st.st_mtime_ns)
        stats["before_bytes"] += st.st_size
    if not snapshot:
        return stats
    cutoff = _anchor_retention_cutoff(retention)
    cap = _ANCHOR_SIZE_TARGET_BYTES if target_bytes is None else max(0, int(target_bytes))
    quota = _ANCHOR_BRANCH_MIN_KEEP if branch_min_keep is None else max(0, int(branch_min_keep))

    lines = read_anchor_lines(target_path)
    for anchor_path, sig in snapshot.items():
        try:
            st = os.stat(anchor_path)
        except OSError:
            stats["aborted"] = "vanished-after-read"
            return stats
        if (st.st_size, st.st_mtime_ns) != sig:
            stats["aborted"] = "concurrent-write"
            return stats

    latest: dict[str, int] = {}
    by_idx: dict[int, dict[str, Any]] = {}
    for idx, line in enumerate(lines):
        text = line.strip()
        if not text:
            continue
        stats["before_lines"] += 1
        try:
            record = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not _anchor_within_retention(record, cutoff):
            stats["expired"] += 1
            continue
        by_idx[idx] = record
        latest[_anchor_key(record)] = idx
    stats["unique_keys"] = len(latest)

    kept: list[tuple[int, dict[str, Any], str, datetime]] = []
    for idx, record in by_idx.items():
        if latest[_anchor_key(record)] != idx:
            if record.get(ANCHOR_RULES_FIELD, "") != _ANCHOR_RULES_VERSION:
                stats["legacy_era"] += 1
            continue
        text = lines[idx] if lines[idx].endswith("\n") else lines[idx] + "\n"
        if not anchor_rules_version(record):
            # 早期版本写入的行没有规则指纹（无法归因到任何时代）：补 legacy 标注后
            # 保留，避免它们与在用指纹的样本混在一起统计
            record = {**record, ANCHOR_RULES_FIELD: ANCHOR_LEGACY_ERA}
            text = json.dumps(record, ensure_ascii=False) + "\n"
            stats["unattributed"] += 1
        when = _anchor_parse_ts(record.get("ts")) or _anchor_parse_ts(record.get("written_at"))
        kept.append((idx, record, text, when or datetime.max))

    total = sum(len(text.encode("utf-8")) for _, _, text, _ in kept)
    trimmed_by_branch: dict[str, int] = {}
    if cap and total > cap:
        protected: set[int] = set()
        per_branch: dict[str, list[tuple[datetime, int]]] = {}
        for pos, (_, record, _, when) in enumerate(kept):
            per_branch.setdefault(_anchor_branch(record), []).append((when, pos))
        for rows in per_branch.values():
            for _, pos in sorted(rows, reverse=True)[:quota]:
                protected.add(pos)
        drop: set[int] = set()
        for pos in sorted(range(len(kept)), key=lambda p: (kept[p][3], p)):
            if total <= cap:
                break
            if pos in protected:
                continue
            drop.add(pos)
            total -= len(kept[pos][2].encode("utf-8"))
            branch = _anchor_branch(kept[pos][1])
            trimmed_by_branch[branch] = trimmed_by_branch.get(branch, 0) + 1
        if drop:
            kept = [entry for pos, entry in enumerate(kept) if pos not in drop]
    stats["trimmed_by_branch"] = trimmed_by_branch
    stats["trimmed"] = sum(trimmed_by_branch.values())

    body = "".join(text for _, _, text, _ in kept)
    stats["after_lines"] = len(kept)
    # 预估体积按实际压缩率算（干跑也能看出收益；分片各带独立 gzip 头，真实值略大）
    stats["after_bytes"] = len(gzip.compress(body.encode("utf-8"))) if body else 0
    if dry_run:
        return stats
    if stats["after_lines"] == stats["before_lines"] and not stats["trimmed"] and not stats["unattributed"]:
        return stats  # 无事可做：不重写任何分片

    directory = os.path.dirname(target_path) or "."
    grouped: dict[str, list[str]] = {}
    for _, record, text, _ in kept:
        grouped.setdefault(_anchor_shard_name(record), []).append(text)

    backups: list[str] = []
    written: list[str] = []
    try:
        os.makedirs(directory, exist_ok=True)
        for name in sorted(grouped):
            shard_path = os.path.join(directory, name)
            tmp_path = f"{shard_path}.compact.tmp"
            with gzip.open(tmp_path, "wt", encoding="utf-8") as f:
                f.writelines(grouped[name])
            if not _compact_verified(tmp_path):
                os.remove(tmp_path)
                stats["aborted"] = "verify-failed"
                return stats
            if os.path.exists(shard_path):
                backup = f"{shard_path}.bak"
                shutil.copy2(shard_path, backup)
                backups.append(backup)
            os.replace(tmp_path, shard_path)
            written.append(name)
        # 整月被裁空的分片：删掉，否则读侧会把已裁掉的样本再读回来。
        # 删除前按 `INVEST_DEDUP_KEEP_BACKUP` 留一份备份——否则「整月被裁空」这条路径
        # 会绕过重写前的 .bak，用户没有任何回滚点。
        for stale in anchor_shard_paths(target_path):
            if os.path.basename(stale) in written:
                continue
            if os.environ.get(_ANCHOR_KEEP_BACKUP_ENV, "0").strip() not in ("0", "", "false"):
                try:
                    shutil.copy2(stale, stale + ".bak")
                except OSError:
                    pass
            try:
                os.remove(stale)
            except OSError:
                continue
    except OSError as e:
        stats["aborted"] = f"write-failed: {e}"
        return stats
    stats["written"] = True
    stats["shards"] = written
    stats["after_bytes"] = anchor_total_bytes(target_path)
    keep_backup = os.environ.get(_ANCHOR_KEEP_BACKUP_ENV, "0").strip() not in ("0", "", "false")
    if not keep_backup:
        for backup in backups:
            if _compact_verified(backup[: -len(".bak")]):
                try:
                    os.remove(backup)
                except OSError:
                    pass
    return stats


def _compact_anchor_file(size: int) -> bool:
    """锚点文件超告警线时就地压缩（每 key 最新 + 保留期 + 体积上限），成功返回 True。

    由显式维护路径触发（``INVEST_DEDUP_MAINTENANCE=1`` 或校准工具 ``--compact``）；
    任何失败都只告警、不阻断报告（原文件保持不动）。
    """
    if os.environ.get(_ANCHOR_COMPACT_ENV, "1").strip() == "0":
        return False
    if size <= _ANCHOR_SIZE_WARN_BYTES or not anchor_shard_paths():
        return False
    try:
        result = compact_anchor_file(_anchor_store._ANCHOR_PATH)
    except Exception:  # 压缩失败绝不阻断报告
        logger.warning("[dedup] 锚点文件维护压缩失败（继续使用原文件）", exc_info=True)
        return False
    if result["aborted"]:
        logger.info("[dedup] 锚点压缩本轮跳过（%s），下次再处理", result["aborted"])
        return False
    if not result["written"]:
        return False
    branches = sorted(result["trimmed_by_branch"].items(), key=lambda kv: -kv[1])[:3]
    branch_text = "、".join(f"{name or '(无分支)'} {count} 条" for name, count in branches)
    logger.info(
        "[dedup] 锚点文件已压缩（维护）：%.1f MB → %.1f MB（每 key 最新 + 近 %d 天 + 体积上限 %.0f MB；"
        "超期 %d 条、体积裁剪 %d 条%s、无指纹旧行补 legacy %d 条）",
        result["before_bytes"] / 1e6,
        result["after_bytes"] / 1e6,
        result["retention_days"],
        _ANCHOR_SIZE_TARGET_BYTES / 1e6,
        result["expired"],
        result["trimmed"],
        f"（{branch_text}）" if branch_text else "",
        result["unattributed"],
    )
    return True


#: 维护开关（默认关闭）：开启时超阈值执行就地压缩；关闭时只做体积告警（无读取）。
_ANCHOR_MAINTENANCE_ENV = "INVEST_DEDUP_MAINTENANCE"


_ANCHOR_SIZE_WARNED = False


def _maybe_maintain_anchor_file() -> None:
    """追加后检查体积：超阈值时按维护开关决定压缩或提示（只 stat，不读全文）。

    常态报告**不压缩**——压缩要全量读+重写整份文件（实测 34 MB / 9.5 万行）；
    需要压缩时运行 ``scripts/eval-dedup-threshold.py``（评估后默认压缩）或
    ``--compact``，也可显式设 ``INVEST_DEDUP_MAINTENANCE=1`` 让下一次 flush 顺带压缩。
    压缩按三重条件裁到体积目标内（保留期 + 体积上限 + 分支配额），故体积有确定上限。
    """
    size = anchor_total_bytes()
    if not size:
        return
    if size <= _ANCHOR_SIZE_WARN_BYTES:
        return
    global _ANCHOR_SIZE_WARNED
    if os.environ.get(_ANCHOR_MAINTENANCE_ENV, "0").strip().lower() in ("1", "true", "yes"):
        _compact_anchor_file(size)
        return
    if _ANCHOR_SIZE_WARNED:
        return
    _ANCHOR_SIZE_WARNED = True
    logger.info(
        "[dedup] 锚点文件 %.1f MB（建议线 %.0f MB，累加采集不影响报告耗时）："
        "需要压缩时运行 `python scripts/eval-dedup-threshold.py --compact`"
        "（或设 INVEST_DEDUP_MAINTENANCE=1 在下次 flush 顺带压缩）",
        size / 1e6,
        _ANCHOR_SIZE_WARN_BYTES / 1e6,
    )


def _record_anchor(record: dict[str, Any]) -> None:
    """线程安全地追加一条锚点记录（采集关闭时零开销返回）。"""
    if not _anchor_collection_enabled():
        return
    if record.get("rule") == _SAME_SRC_RULE and not _anchor_sampled(record):
        return
    with _ANCHOR_LOCK:
        _ANCHOR_RECORDS.append(record)


def _anchor_sampled(record: dict[str, Any]) -> bool:
    """锚点是否入选（确定性哈希采样：同一标题对每次运行结果恒定）。"""
    sample = _SAME_SRC_ANCHOR_SAMPLE
    if sample <= 0:
        return False
    if sample == 1:
        return True
    digest = hashlib.sha256(_anchor_key(record).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % sample == 0


def _make_anchor(
    item_a: dict[str, Any],
    item_b: dict[str, Any],
    ratio: float,
    bigram_overlap: int,
    merged: bool,
    rule: str,
) -> dict[str, Any]:
    """构建一条锚点记录（边界案例），用于后续阈值校准。

    记录带 ``anchor_rules_version``（:data:`_ANCHOR_RULES_VERSION`）——校准工具
    据此区分「哪个规则时代」的样本；同一标题对也可用标题重算（见
    :func:`_pair_similarity`）。
    """
    return {
        "ts": item_a.get("ctime", "") or item_b.get("ctime", ""),
        "title_a": item_a.get("title", ""),
        "title_b": item_b.get("title", ""),
        "source_a": item_a.get("_source", ""),
        "source_b": item_b.get("_source", ""),
        "ratio": round(ratio, 3),
        "bigram_overlap": bigram_overlap,
        "merged": merged,
        "rule": rule,
        ANCHOR_RULES_FIELD: _ANCHOR_RULES_VERSION,
        # 写入时刻：`ts` 是新闻发布时间，补录/回溯抓到的老新闻 `ts` 很老但刚写入，
        # 保留期判定需要它做第二判据（否则压缩会把刚采到的样本立刻裁掉）。
        "written_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _flush_anchors() -> None:
    """将内存中的锚点记录**追加**到 JSONL 文件，然后清空列表。

    设计取舍：采集与去重判定解耦——写侧只追加（单次 ``write`` + ``fsync``），
    **不读旧文件**。同一标题对跨轮重复由校准工具 ``load_anchors`` 按键去重
    （保留最早一条），因此重复行不影响诊断结论，只影响文件体积；体积由体积告警
    与 ``eval-dedup-threshold.py --compact``（或显式维护开关）治理。

    本次批次内仍按 ``_anchor_key`` 去重，避免同一次运行重复写入同一对。
    """
    global _ANCHOR_RECORDS
    if not _anchor_collection_enabled():
        with _ANCHOR_LOCK:
            _ANCHOR_RECORDS = []
        return
    if not _ANCHOR_RECORDS:
        return
    with _ANCHOR_LOCK:
        records = _ANCHOR_RECORDS
        _ANCHOR_RECORDS = []  # 先清空再写，防止递归写入

    new_records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        key = _anchor_key(record)
        if key in seen:
            continue
        seen.add(key)
        new_records.append(record)
    if not new_records:
        return
    if _append_anchor_lines([json.dumps(r, ensure_ascii=False) + "\n" for r in new_records]):
        _maybe_maintain_anchor_file()
