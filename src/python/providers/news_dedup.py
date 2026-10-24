"""新闻去重主流程 — 标题模糊去重 + 锚点采集。

判定口径（阈值常量 / 模板词表 / 归一化 / 实体 bigram / 相似度 / 方向词对 / 规则指纹）
在 ``providers/news_dedup_rules.py``；本模块负责锚点采集与比较循环，并原面
re-export 规则原语（``from ...news_dedup import _normalize_title`` 等既有引用不受影响）。
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Any

from src.python.core.constants import PROJECT_ROOT

from src.python.providers.news_dedup_rules import (
    ANCHOR_RULES_FIELD,
    _ANCHOR_RULES_VERSION,
    _CROSS_BG2_RATIO,
    _CROSS_BIGRAM_MIN,
    _CROSS_CANDIDATE_RATIO,
    _CROSS_DIRECT_RATIO,
    _CROSS_SAFE_RATIO,
    _SAME_SRC_BIGRAM_MIN,
    _extract_entity_bigrams,
    _has_opposite_direction,
    has_proper_noun_token,
    _normalize_title,
    _overlap_of_norms,
    _ratio_of_norms_bounded,
    share_event_group,
)

logger = logging.getLogger("invest")

# ── 锚点采集（阈值校准用） ──────────────────────────────────────
# 边界案例收集（阈值校准用）**默认开启**（`INVEST_DEDUP_COLLECT_ANCHORS=0` 可关）：
# _dedup_by_title 记录、aggregate_news() 结束时**追加**至 data/calibration/dedup_anchors.jsonl，
# 不读旧文件（跨轮重复由校准工具按键去重）。锚点不参与去重判定。
# 一条记录为一个 JSON 行，append-only。格式：
#   {"ts","title_a","title_b","source_a","source_b",
#    "ratio","bigram_overlap","merged","rule","anchor_rules_version"}
_ANCHOR_RECORDS: list[dict[str, Any]] = []
_ANCHOR_LOCK = threading.Lock()
_ANCHOR_PATH = os.path.join(
    PROJECT_ROOT,
    "data",
    "calibration",
    "dedup_anchors.jsonl",
)
#: 体积告警线：超过此值在加载时提醒压缩（flush 写全文、加载解析全文件，均是全文成本）
_ANCHOR_SIZE_WARN_BYTES = 32 * 1024 * 1024
#: 压缩阈值（与告警线同值）：超过时记录一次维护提示；实际压缩只在评估/维护路径执行。
#: 压缩保留每个标题对的**最新一条**（文件 append-only → 最后即最新），并先备份 .bak。
#: 用 `INVEST_DEDUP_AUTO_COMPACT=0` 可关闭维护压缩（仅保留告警）。
_ANCHOR_COMPACT_ENV = "INVEST_DEDUP_AUTO_COMPACT"
#: 采集开关（默认开启）：边界案例持续积累供诊断/阈值校准；显式设 0 可关闭。
#: 采集与去重判定解耦——写侧只追加、不读 39MB 旧文件（跨轮重复由校准工具按键去重）。
_ANCHOR_COLLECT_ENV = "INVEST_DEDUP_COLLECT_ANCHORS"
#: 压缩时的保留期（天）：锚点只服务于「近期同对新闻不重复追加」，过期记录无消费者。
#: 仅按 key 去重无法压小文件（标题对高度唯一，实测压后仍 37.9 MB），保留期才是
#: 真正的体积上限；`INVEST_DEDUP_ANCHOR_RETENTION_DAYS` 可覆盖（0 = 不限，退回纯去重）。
_ANCHOR_RETENTION_DAYS = 120
_ANCHOR_RETENTION_ENV = "INVEST_DEDUP_ANCHOR_RETENTION_DAYS"


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
    try:
        with open(_ANCHOR_PATH, "a", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        return True
    except OSError as e:
        logger.warning("[dedup] 锚点文件追加失败: %s", e)
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
        with open(path, encoding="utf-8") as f:
            first = f.readline().strip()
        if not first:
            return False
        json.loads(first)
        return True
    except (OSError, json.JSONDecodeError):
        return False


def _compact_anchor_file(size: int) -> bool:
    """锚点文件超阈值时就地压缩（每 key 最新 + 保留期），成功返回 True。

    由显式维护路径触发（``INVEST_DEDUP_MAINTENANCE=1`` 或校准工具 ``--compact``）；
    任何失败都只告警、不阻断报告（原文件保持不动）。
    """
    if os.environ.get(_ANCHOR_COMPACT_ENV, "1").strip() == "0":
        return False
    if size <= _ANCHOR_SIZE_WARN_BYTES or not os.path.exists(_ANCHOR_PATH):
        return False
    try:
        cutoff = _anchor_retention_cutoff()
        last_line: dict[str, int] = {}
        with open(_ANCHOR_PATH, encoding="utf-8") as f:
            for lineno, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if cutoff and not _anchor_ts_on_or_after(record.get("ts"), cutoff):
                        continue  # 超出保留期：直接丢弃（消费者只关心近期重复对）
                    last_line[_anchor_key(record)] = lineno
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
        if not last_line:
            return False
        keep = set(last_line.values())
        tmp_path = f"{_ANCHOR_PATH}.compact.tmp"
        with open(_ANCHOR_PATH, encoding="utf-8") as src, open(tmp_path, "w", encoding="utf-8") as dst:
            for lineno, line in enumerate(src):
                if lineno in keep:
                    dst.write(line if line.endswith("\n") else line + "\n")
        backup = f"{_ANCHOR_PATH}.bak"
        import shutil

        shutil.copy2(_ANCHOR_PATH, backup)
        os.replace(tmp_path, _ANCHOR_PATH)
        new_size = os.path.getsize(_ANCHOR_PATH)
        keep_backup = os.environ.get(_ANCHOR_KEEP_BACKUP_ENV, "0").strip() not in ("0", "", "false")
        if not keep_backup and _compact_verified(_ANCHOR_PATH):
            try:
                os.remove(backup)
            except OSError:
                keep_backup = True
        logger.info(
            "[dedup] 锚点文件已压缩（维护）：%.1f MB → %.1f MB（每 key 最新 + 近 %d 天；%s）",
            size / 1e6,
            new_size / 1e6,
            _anchor_retention_days(),
            f"已清理备份释放 {(size - new_size) / 1e6:.1f} MB"
            if not keep_backup
            else f"备份保留 {os.path.basename(backup)}",
        )
        return True
    except OSError as e:  # 压缩失败不阻断报告：保留原文件与告警
        logger.warning("[dedup] 锚点文件维护压缩失败（继续使用原文件）：%s", e)
        return False


#: 维护开关（默认关闭）：开启时超阈值执行就地压缩；关闭时只做体积告警（无读取）。
_ANCHOR_MAINTENANCE_ENV = "INVEST_DEDUP_MAINTENANCE"


_ANCHOR_SIZE_WARNED = False


def _maybe_maintain_anchor_file() -> None:
    """追加后检查体积：超阈值时按维护开关决定压缩或提示（只 stat，不读全文）。

    常态报告**不压缩**——压缩需要全量读+重写 39MB，且压缩后未必能降到阈值以下；
    需要压缩时运行 ``scripts/eval-dedup-threshold.py --compact``，或显式设
    ``INVEST_DEDUP_MAINTENANCE=1`` 让下一次 flush 顺带压缩一次。
    """
    try:
        size = os.path.getsize(_ANCHOR_PATH)
    except OSError:
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
    with _ANCHOR_LOCK:
        _ANCHOR_RECORDS.append(record)


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


def _dedup_by_title(
    items: list[dict[str, Any]],
    cross_threshold: float = _CROSS_CANDIDATE_RATIO,
) -> list[dict[str, Any]]:
    """基于标准化标题模糊去重 + 中文实体 bigram 辅助判定。

    五档阈值策略（2026-08-17 基于 42560 条锚点分层采样校准）：
      - 同源：共享实体 bigram ≥ ``_SAME_SRC_BIGRAM_MIN``(4) 即合并。
        同源不会同时出现方向对立报道（如"突破3万亿"vs"跌破3万亿"），
        所以不依赖 SequenceMatcher 阈值，只检查实体重叠。
      - 跨源安全区：
        ① ratio ≥ ``_CROSS_DIRECT_RATIO``(0.65) 且专名 bg ≥ 1 直接合并（高相似改写重复，
           如"英国央行如期维持利率不变"vs"英国央行以6比3票数维持利率不变"）
        ② 0.50 ≤ ratio < 0.65 需专名 bg ≥ 2 才合并——旧规则直接合并导致
           40-50% 误合并（"行云科技签算力合同"vs"亿田智能签算力合同"共享模板骨架）
      - 跨源候选区：``_CROSS_CANDIDATE_RATIO``(0.35) ≤ ratio < 0.50，阶梯判定：
        ③ 共享 ≥ ``_CROSS_BIGRAM_MIN``(3) 个实体 bigram → 合并（高实体重叠，低 ratio 门槛）
        ④ 共享 ≥ 2 个实体 bigram 且 ratio ≥ bg=2 梯度阈值（0.375）且共享项含**真专名**
           （英数 token 需含字母、不在泛词否决表，纯数字不算；见 ``_TOKEN_LIKE`` /
           ``_GENERIC_TOKENS``）→ 合并
           （CPI/PPI、荣耀IPO 类共享专名 token 的真重复；纯中文公司名共享
           如"英伟达/伟达"、仅共享数字如"某指数 100 vs 另一指数 100"、
           跨主体泛词共现如"两只 ETF 各自的行情"不代表同一事件）
        ⑤ 方向对立（上涨vs下跌/加息vs降息/站稳vs跌破分属两标题）且共享实体 → 不合并
        ⑥ 否则跳过（实体重叠不足或 ratio 太低）

    阈值全部取自本模块常量（``_CROSS_*`` / ``_SAME_SRC_BIGRAM_MIN``），校准工具
    从同一处读取；相似度口径的唯一实现在 :func:`_pair_similarity`。

    模板词治理：_STOP_BIGRAMS 扩充财报/回购/指数/预警/地震/目标价等模板词，
    提取 bigram 前整体掩码替换（_mask_stop），消除同类新闻共享模板骨架的虚高
    重叠。英文专名占位按长度分桶（_tk2_/_tk4_/_tk6_），不同长度英文词不再
    共享相似度。_normalize_title 保留空格防英文 token 粘连。
    """
    if not items:
        return items

    kept: list[dict[str, Any]] = []
    kept_norms: list[str] = []
    kept_sources: list[str] = []
    for item in items:
        norm = _normalize_title(item.get("title", ""))
        if not norm:
            kept.append(item)
            continue
        is_dup = False
        source = item.get("_source", "") or ""
        for idx, existing in enumerate(kept_norms):
            existing_src = kept_sources[idx]
            existing_item = kept[idx]
            same_source = bool(source) and bool(existing_src) and source == existing_src

            # ① 同源：共享实体 bigram ≥ 阈值即合并
            if same_source:
                overlap = _overlap_of_norms(norm, existing)
                if overlap >= _SAME_SRC_BIGRAM_MIN:
                    is_dup = True
                    break
                # 锚点：同源 bigram 接近阈值
                if 2 <= overlap <= 5:
                    _record_anchor(_make_anchor(item, existing_item, 0.0, overlap, False, "same_src"))

            # ② 跨源安全区：ratio ≥ 0.65 直接合并；0.50~0.65 需专名 bg ≥ 2
            #    剥离通用日期模式后比较，避免不同新闻因共享"2026年7月"等虚高；
            #    英文专名按长度分桶占位，避免共享专名（Anthropic/Meta/AMD）导致
            #    SequenceMatcher 比率虚高（英文专名在 _extract_entity_bigrams
            #    中已有独立处理，ratio 中可降权）。口径实现见 _ratio_of_norms。
            ratio = _ratio_of_norms_bounded(norm, existing, cross_threshold)
            if ratio >= _CROSS_SAFE_RATIO:
                overlap = _overlap_of_norms(norm, existing)
                # ratio ≥ 0.65 直接合并也要求专名 bg ≥ 1：不同公司同模板
                # （"XX：2026年半年度净利润同比增长N%"）ratio 可高达 0.7+，
                # 但掩码后 bg=0（公司名不同），不能当作改写型重复。
                if ratio >= _CROSS_DIRECT_RATIO and overlap >= 1:
                    is_dup = True
                    break
                if overlap >= 2:
                    is_dup = True
                    # 锚点：跨源安全区合并样本（含擦边 0.50~0.65）
                    _record_anchor(_make_anchor(item, existing_item, ratio, overlap, True, "cross_safe"))
                    break
                # 安全区但实体不足：跳过（记录锚点供校准，继续子串包含判定）
                _record_anchor(_make_anchor(item, existing_item, ratio, overlap, False, "cross_safe"))

            # ③ 跨源候选区：候选区入口 ≤ ratio < 0.50，需共享 ≥ 3 实体 bigram
            if not same_source and ratio >= cross_threshold:
                bg1 = _extract_entity_bigrams(norm)
                bg2 = _extract_entity_bigrams(existing)
                shared = bg1 & bg2
                overlap = len(shared)
                # ④ 方向对立检测：共享实体 + 相反方向词分属两标题 → 不合并
                #    （"美联储或暂缓加息"vs"城堡证券预计美联储将加息"）
                if overlap >= 1 and _has_opposite_direction(norm, existing):
                    _record_anchor(_make_anchor(item, existing_item, ratio, overlap, False, "cross_opposite"))
                elif overlap >= _CROSS_BIGRAM_MIN:
                    # bg=3 下限档加事件一致性：同主体不同事件对（公司名贡献多
                    # 个 bigram 凑满 bg=3，如「暗盘跌 vs 资金抢筹」）不合并、
                    # 落候选区保留（详见 news_dedup_rules._EVENT_GROUPS）；
                    # 不转入下方 bg=2 梯度（专名判据对同主体对恒成立，会绕过）
                    if overlap == _CROSS_BIGRAM_MIN and not share_event_group(norm, existing):
                        _record_anchor(_make_anchor(item, existing_item, ratio, overlap, False, "cross_skip"))
                        continue
                    is_dup = True
                    _record_anchor(_make_anchor(item, existing_item, ratio, overlap, True, "cross_merge"))
                    break
                # ⑤ bg=2 梯度：中高 ratio + 共享**真专名** → 合并
                #    英数 token 需含字母（纯数字共享不算专名证据）、或 _tk 虚拟专名，
                #    且不在泛词否决表（ai/etf/cm 跨主体高频串，锚点抽样中靠它们
                #    过闸的合并绝大多数为误合并）；CPI/PPI、荣耀IPO 等真发布会/
                #    公司缩写照常，靠此规则捕获。
                elif overlap >= 2 and ratio >= _CROSS_BG2_RATIO and has_proper_noun_token(shared):
                    is_dup = True
                    _record_anchor(_make_anchor(item, existing_item, ratio, overlap, True, "cross_merge_bg2"))
                    break
                # 锚点：跨源候选区但 bigram 不足
                _record_anchor(_make_anchor(item, existing_item, ratio, overlap, False, "cross_skip"))

            # ⑥ 子串包含
            if not is_dup:
                short, long = (norm, existing) if len(norm) <= len(existing) else (existing, norm)
                if len(short) >= 6 and short in long:
                    is_dup = True
                    break

        if not is_dup:
            kept_norms.append(norm)
            kept_sources.append(source)
            kept.append(item)
    return kept
