#!/usr/bin/env python3
"""去重阈值校准工具 — 基于锚点数据分析**当前规则**的判定分布与边界风险。

用法：
  python scripts/eval-dedup-threshold.py             # 分析全部锚点，并在分析后默认压缩一次
  python scripts/eval-dedup-threshold.py --summary   # 仅汇总统计（仍做默认压缩维护）
  python scripts/eval-dedup-threshold.py --no-compact            # 只分析、不压缩（只读）
  python scripts/eval-dedup-threshold.py --compact   # 只压缩锚点（每 key 最新 + 保留期裁剪）
  python scripts/eval-dedup-threshold.py --compact --retention-days 0   # 仅按键去重、不按时间裁剪
  python scripts/eval-dedup-threshold.py --file X    # 指定锚点文件

**采集前置**：去重锚点**默认采集**（写侧只追加、不读旧文件，报告零读取开销）；
``INVEST_DEDUP_COLLECT_ANCHORS=0`` 可关闭。跨轮重复由本工具 ``load_anchors``
按键去重（保留最早一条），不影响诊断结论。

**维护约定**：评估默认在分析完成后压缩一次锚点文件（每 key 最新 + 保留期），
使评估顺带完成体积维护；``--no-compact`` 可只读分析，``--dry-run`` 只演练不写盘。

**口径（关键）**：锚点文件 append-only、跨规则时代累积，故本工具**不信任记录里的
``ratio`` / ``bigram_overlap`` / ``rule``**，而是拿 ``title_a`` / ``title_b`` 用当前代码
重算相似度与实体重叠（``news_dedup._pair_similarity``），再按当前阈值重新判定分支——
结论始终反映**当前**规则。阈值同样从 ``news_dedup`` 读取，本文件不自写一份数字
（两处各写一份会漂移：如工具正文写 0.30 而代码为 0.35）。记录时的规则指纹与当前
不同的样本单列「历史规则时代」，仅作参照、不参与结论。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from typing import Any

# ── 项目路径（脚本独立运行，需先把仓库根加入 sys.path） ──
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 晚导入：sys.path 就绪后再引用项目模块
from src.python.providers.news_dedup import (
    _ANCHOR_SIZE_WARN_BYTES,
    anchor_shard_paths,
    anchor_total_bytes,
    compact_anchor_file,
    read_anchor_lines,
)
from src.python.providers.news_dedup_rules import (
    ANCHOR_RULES_FIELD,
    _ANCHOR_RULES_VERSION,
    anchor_rules_version,
    _CROSS_BG2_RATIO,
    _CROSS_BIGRAM_MIN,
    _CROSS_CANDIDATE_RATIO,
    _CROSS_DIRECT_RATIO,
    _CROSS_SAFE_RATIO,
    _GENERIC_TOKENS,
    _RATIO_CLEAN,
    _SAME_SRC_BIGRAM_MIN,
    _TOKEN_LIKE,
    _has_opposite_direction,
    has_proper_noun_token,
    _normalize_title,
    _pair_similarity,
    proper_noun_tokens,
    share_event_group,
)

#: 默认锚点文件（与 news_dedup._ANCHOR_PATH 同源，不再各写一份路径）
_ANCHOR_PATH = os.path.join(_PROJECT_ROOT, "data", "calibration", "dedup_anchors.jsonl")

#: 本次运行实际读取的文件（main 按 --file 赋值；报告内的体积/压缩提示随之指向同一文件）
_ACTIVE_FILE = _ANCHOR_PATH


# ═══════════════════════════════════════════════════════════════
#  锚点读取与压缩
# ═══════════════════════════════════════════════════════════════


def _anchor_key(record: dict[str, Any]) -> tuple[str, str, str, str]:
    """锚点去重键：source 对 + 标题对（顺序无关，与 news_dedup._anchor_key 同口径）。"""
    a = (record.get("source_a", "") or "", record.get("title_a", "") or "")
    b = (record.get("source_b", "") or "", record.get("title_b", "") or "")
    sa, ta = (a, b) if a <= b else (b, a)
    return (sa[0], sa[1], ta[0], ta[1])


def load_anchors(path: str = _ANCHOR_PATH) -> list[dict[str, Any]]:
    """加载并按键去重（保留每个标题对的**最早**一条）的锚点记录。

    保留最早一条的理由：它附带当时的规则判定与规则指纹，便于与「当前规则重判」
    对比（漂移量）；压缩场景另走 :func:`compact_anchors`（保留最新一条）。

    Returns:
        去重后的记录列表；文件不存在时返回空列表（调用方决定是否退出）。
    """
    buckets: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for line in read_anchor_lines(path):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        buckets.setdefault(_anchor_key(record), record)
    return list(buckets.values())


def compact_anchors(
    path: str = _ANCHOR_PATH,
    *,
    dry_run: bool = False,
    retention_days: int | None = None,
) -> dict[str, Any]:
    """压缩锚点文件（每 key 最新 + 保留期 + 体积上限），返回统计字典。

    实现在 :func:`news_dedup.compact_anchor_file`——生产维护路径与本工具共用同一套
    三条件（含分支配额保护与并发写入检测），避免两份实现漂移。``retention_days=None``
    取生产默认值（``_anchor_retention_days()``）；``0`` = 只按键去重、不按时间裁剪。
    """
    return compact_anchor_file(path, dry_run=dry_run, retention_days=retention_days)


# ═══════════════════════════════════════════════════════════════
#  当前规则重判
# ═══════════════════════════════════════════════════════════════


def classify_pair(ratio: float, overlap: int, same_source: bool, title_a: str, title_b: str) -> str:
    """按**当前**阈值重判一对标题会走哪个分支（与 ``_dedup_by_title`` 同序）。

    Returns:
        分支名：``same_src_merged`` / ``same_src_kept`` / ``cross_safe_merged`` /
        ``cross_safe_kept`` / ``cross_opposite`` / ``cross_merge`` /
        ``cross_merge_bg2`` / ``cross_skip`` / ``below_candidate``。
    """
    if same_source:
        return "same_src_merged" if overlap >= _SAME_SRC_BIGRAM_MIN else "same_src_kept"
    if ratio >= _CROSS_SAFE_RATIO:
        if ratio >= _CROSS_DIRECT_RATIO and overlap >= 1:
            return "cross_safe_merged"
        if overlap >= 2:
            return "cross_safe_merged"
        return "cross_safe_kept"
    if ratio >= _CROSS_CANDIDATE_RATIO:
        if overlap >= 1 and _has_opposite_direction(_normalize_title(title_a), _normalize_title(title_b)):
            return "cross_opposite"
        if overlap >= _CROSS_BIGRAM_MIN:
            # 与生产同源：bg=3 下限档事件不一致 → 候选区保留（同主体不同事件）
            if overlap == _CROSS_BIGRAM_MIN and not share_event_group(
                _normalize_title(title_a), _normalize_title(title_b)
            ):
                return "cross_skip"
            return "cross_merge"
        if overlap >= 2 and ratio >= _CROSS_BG2_RATIO and _shared_carries_proper_noun(title_a, title_b):
            return "cross_merge_bg2"
        return "cross_skip"
    return "below_candidate"


def _shared_carries_proper_noun(title_a: str, title_b: str) -> bool:
    """共享项中是否含真专名证据（与生产同源 ``has_proper_noun_token``，泛词否决表已生效）。"""
    from src.python.providers.news_dedup_rules import _extract_entity_bigrams

    shared = _extract_entity_bigrams(_normalize_title(title_a)) & _extract_entity_bigrams(_normalize_title(title_b))
    return has_proper_noun_token(shared)


def _shared_proper_nouns(title_a: str, title_b: str) -> list[str]:
    """共享项里的专名证据清单（展示用；与生产同源 ``proper_noun_tokens``，泛词否决已生效）。"""
    from src.python.providers.news_dedup_rules import _extract_entity_bigrams

    shared = _extract_entity_bigrams(_normalize_title(title_a)) & _extract_entity_bigrams(_normalize_title(title_b))
    return proper_noun_tokens(shared)


def analyze(records: list[dict[str, Any]]) -> dict[str, Any]:
    """对全部锚点做「当前规则重判」并汇总。"""
    branches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    era_current = 0
    era_unattributed = 0
    era_versions: Counter[str] = Counter()
    drift = 0
    for record in records:
        title_a = record.get("title_a", "") or ""
        title_b = record.get("title_b", "") or ""
        if not title_a or not title_b:
            continue  # 缺标题的残行不参与判定（空串相似度恒为 1，会误进安全区）
        ratio, overlap = _pair_similarity(title_a, title_b)
        same_source = bool(record.get("source_a")) and record.get("source_a") == record.get("source_b")
        branch = classify_pair(ratio, overlap, same_source, record.get("title_a", ""), record.get("title_b", ""))
        version = anchor_rules_version(record)
        if version == _ANCHOR_RULES_VERSION:
            era_current += 1
        if version:
            era_versions[version] += 1
        else:
            era_unattributed += 1
        # 记录时的 rule 与重判分支口径不同（如记录 cross_skip vs 重判 cross_merge）
        stored = record.get("rule", "")
        if stored and not _branch_matches_stored(branch, stored):
            drift += 1
        branches[branch].append({**record, "_ratio_now": ratio, "_overlap_now": overlap})
    return {
        "branches": branches,
        "era_current": era_current,
        "era_legacy": len(records) - era_current - era_unattributed,
        "era_unattributed": era_unattributed,
        "era_versions": era_versions,
        "drift": drift,
    }


def _branch_matches_stored(branch: str, stored: str) -> bool:
    """重判分支与记录时 ``rule`` 是否同类（历史时代的分支命名有差异，只做粗对齐）。"""
    if stored == "cross_merge_bg2":
        return branch == "cross_merge_bg2"
    if stored == "cross_safe":
        return branch.startswith("cross_safe")
    if stored == "same_src":
        return branch.startswith("same_src")
    return branch == stored


# ═══════════════════════════════════════════════════════════════
#  报告
# ═══════════════════════════════════════════════════════════════


def report(records: list[dict[str, Any]], *, summary_only: bool = False, sample: int = 10) -> None:
    """分析锚点数据，输出当前规则下的判定分布与边界风险。"""
    if not records:
        print("[!] 锚点文件为空，尚无数据可用于校准。")
        return
    size = anchor_total_bytes(_ACTIVE_FILE)

    data = analyze(records)
    branches: dict[str, list[dict[str, Any]]] = data["branches"]

    print(f"锚点目录: {os.path.dirname(_ACTIVE_FILE) or '.'}（{len(anchor_shard_paths(_ACTIVE_FILE))} 个分片/文件）")
    print(f"  体积: {size / 1e6:.1f} MB（告警线 {_ANCHOR_SIZE_WARN_BYTES / 1e6:.0f} MB）")
    print(f"唯一标题对: {len(records)}")
    print(
        f"规则时代: 当前指纹 {_ANCHOR_RULES_VERSION} = {data['era_current']} 条；"
        f"历史时代 = {data['era_legacy']} 条；未标注（旧版遗留）= {data['era_unattributed']} 条"
        "（旧样本按当前代码重算，仍计入下方分布）"
    )
    others = {v: n for v, n in data["era_versions"].items() if v != _ANCHOR_RULES_VERSION}
    if others:
        shown = "、".join(f"{v}={n}" for v, n in sorted(others.items(), key=lambda kv: -kv[1])[:3])
        print(f"  历史指纹分布（Top3）: {shown}（压缩后可一并归并为较少时代）")
    print(f"与记录时判定不一致: {data['drift']} 条（规则已调整，属正常）")
    print()
    print("── 当前规则重判分布 ──")
    for name in (
        "same_src_merged",
        "same_src_kept",
        "cross_safe_merged",
        "cross_safe_kept",
        "cross_merge",
        "cross_merge_bg2",
        "cross_opposite",
        "cross_skip",
        "below_candidate",
    ):
        print(f"  {name:18s} {len(branches.get(name, [])):6d}")
    print()

    _report_skip_edges(branches.get("cross_skip", []), summary_only, sample)
    _report_merge_edges(branches.get("cross_merge", []), summary_only, sample)
    _report_bg2_merges(branches.get("cross_merge_bg2", []), sample)
    _report_safe_edges(branches.get("cross_safe_merged", []))
    _report_same_src(branches.get("same_src_kept", []), branches.get("same_src_merged", []))
    _print_advice(branches)
    _print_current_rules()


def _report_skip_edges(skips: list[dict[str, Any]], summary_only: bool, sample: int) -> None:
    """cross_skip：进候选区但未合并 —— 关注「有实体重叠却没过线」的漏判候选。"""
    print(f"=== cross_skip（进候选区但未合并，当前阈值 {_CROSS_CANDIDATE_RATIO}）===")
    print(f"  数量: {len(skips)}")
    if not skips:
        print()
        return
    by_bg: dict[int, int] = defaultdict(int)
    for r in skips:
        by_bg[min(r["_overlap_now"], 3)] += 1
    print("  实体重叠分布: " + "  ".join(f"bg={k}{'+' if k == 3 else ''}:{v}" for k, v in sorted(by_bg.items())))
    bg_le1 = [r for r in skips if r["_overlap_now"] <= 1 and r["_ratio_now"] >= 0.40]
    print(f"  bg≤1 且 ratio≥0.40: {len(bg_le1)} 条")
    print("    多数不是重复：共享日期/财经骨架（如板块指数行情句式）抬高 ratio，实体无重叠")
    print("    少数是同一主体的多篇报道（如一公司两篇财报快讯，公司名只贡献 1~2 个 bigram）")
    print("    —— 属规则有意保守（实体证据不足不合并）：误合并会静默丢掉一篇独立报道，故不因这类样例降阈值")
    print(f"    ratio 侧已剥离: {_RATIO_CLEAN.pattern}；实体侧模板词已掩码")
    if not summary_only and bg_le1:
        for r in bg_le1[:3]:
            print(f"      r={r['_ratio_now']:.3f} bg={r['_overlap_now']}")
            print(f"        [{r['source_a']}] {r['title_a'][:44]}")
            print(f"        [{r['source_b']}] {r['title_b'][:44]}")
    below_bg2 = [r for r in skips if r["_overlap_now"] >= 2 and r["_ratio_now"] < _CROSS_BG2_RATIO]
    if below_bg2:
        print()
        print(f"[?] bg≥2 且 ratio 落在 {_CROSS_CANDIDATE_RATIO:.3f}~{_CROSS_BG2_RATIO:.3f}: {len(below_bg2)} 条")
        print(
            f"    若把 _CROSS_BG2_RATIO 降到 {_CROSS_CANDIDATE_RATIO:.3f}，这些会新增合并；"
            "含真专名的才是漏判候选，纯数字/中文共享不算"
        )
        proper = [r for r in below_bg2 if _shared_carries_proper_noun(r["title_a"], r["title_b"])]
        print(f"    其中含真专名证据: {len(proper)} 条")
        if not summary_only:
            for r in proper[:sample]:
                print(f"      r={r['_ratio_now']:.3f} shared={_shared_proper_nouns(r['title_a'], r['title_b'])}")
                print(f"        [{r['source_a']}] {r['title_a'][:46]}")
                print(f"        [{r['source_b']}] {r['title_b'][:46]}")
    print()


def _report_merge_edges(merges: list[dict[str, Any]], summary_only: bool, sample: int) -> None:
    """cross_merge：高实体重叠已合并 —— 关注 bg=3 边界（误合并风险）。"""
    print(f"=== cross_merge（共享 ≥{_CROSS_BIGRAM_MIN} 实体 bigram 已合并）===")
    print(f"  数量: {len(merges)}")
    if not merges:
        print()
        return
    edge = [r for r in merges if r["_overlap_now"] == _CROSS_BIGRAM_MIN]
    if edge:
        high_ratio = [r for r in edge if r["_ratio_now"] >= 0.40]
        print(f"  bg={_CROSS_BIGRAM_MIN} 边界: {len(edge)} 条（其中 ratio≥0.40: {len(high_ratio)} 条）")
        print(
            "    样本需人工判读：bg=3 靠实体重叠合并，模板词已掩码，但同领域不同事件"
            "（共 3 个实体名）仍可能误合并 → 出现误合并样例时优先扩模板词表/方向对，而非抬高阈值"
        )
        if not summary_only:
            for r in edge[:sample]:
                print(f"      r={r['_ratio_now']:.3f} bg={r['_overlap_now']}")
                print(f"        [{r['source_a']}] {r['title_a'][:44]}")
                print(f"        [{r['source_b']}] {r['title_b'][:44]}")
    print()


def _report_bg2_merges(bg2: list[dict[str, Any]], sample: int) -> None:
    """cross_merge_bg2：bg=2 + 中高 ratio + 真专名 —— 展示共享证据类型。"""
    print(f"=== cross_merge_bg2（bg=2 + ratio≥{_CROSS_BG2_RATIO} + 真专名）===")
    print(f"  数量: {len(bg2)}")
    if not bg2:
        print()
        return
    for r in bg2[:sample]:
        print(f"    r={r['_ratio_now']:.3f} shared={_shared_proper_nouns(r['title_a'], r['title_b'])}")
        print(f"      [{r['source_a']}] {r['title_a'][:44]}")
        print(f"      [{r['source_b']}] {r['title_b'][:44]}")
    print()


def _report_safe_edges(safe_merged: list[dict[str, Any]]) -> None:
    """cross_safe_merged：ratio ≥ 0.50 —— 关注 0.50~0.65 且实体证据仅 2 的擦边。"""
    print(f"=== cross_safe_merged（ratio ≥ {_CROSS_SAFE_RATIO}）===")
    print(f"  数量: {len(safe_merged)}")
    if not safe_merged:
        print()
        return
    edge = [
        r for r in safe_merged if _CROSS_SAFE_RATIO <= r["_ratio_now"] < _CROSS_DIRECT_RATIO and r["_overlap_now"] < 3
    ]
    print(f"  擦边区（{_CROSS_SAFE_RATIO}~{_CROSS_DIRECT_RATIO} 且 bg<3）: {len(edge)} 条")
    print("    靠 ratio 合并、实体证据少 → 误合并风险集中区，新增误合并样例时优先查这里")
    print()


def _report_same_src(kept: list[dict[str, Any]], merged: list[dict[str, Any]]) -> None:
    """同源：合并阈值只依赖实体重叠（同源不出现方向对立报道）。"""
    print(f"=== 同源（阈值 bg≥{_SAME_SRC_BIGRAM_MIN}）===")
    print(f"  已合并: {len(merged)} 条；未达阈值: {len(kept)} 条")
    if not kept:
        print()
        return
    by_bg: dict[int, int] = defaultdict(int)
    for r in kept:
        by_bg[min(r["_overlap_now"], 3)] += 1
    print("  未达阈值的重叠分布: " + "  ".join(f"bg={k}{'+' if k == 3 else ''}:{v}" for k, v in sorted(by_bg.items())))
    print(
        "    bg=2/3 与阈值的差距较大，但同源新闻多为模板差异"
        "（模板词已掩码），不因此降阈值；出现真重复样例时优先扩模板词表"
    )
    print()


def _print_advice(branches: dict[str, list[dict[str, Any]]]) -> None:
    """数据驱动的建议（不写死结论）。"""
    print("=" * 60)
    print("校准建议")
    print("=" * 60)
    cross_total = sum(
        len(branches.get(b, []))
        for b in (
            "cross_skip",
            "cross_merge",
            "cross_merge_bg2",
            "cross_safe_merged",
            "cross_safe_kept",
            "cross_opposite",
        )
    )
    same_total = len(branches.get("same_src_kept", [])) + len(branches.get("same_src_merged", []))
    skips = branches.get("cross_skip", [])
    missed = [
        r
        for r in skips
        if r["_overlap_now"] >= 2
        and r["_ratio_now"] >= _CROSS_BG2_RATIO
        and _shared_carries_proper_noun(r["title_a"], r["title_b"])
    ]
    if missed:
        print(f"[!!] 规则异常：{len(missed)} 条满足 bg=2 梯度条件却未合并 —— 检查 classify_pair 与判定链是否同序")
    else:
        print("[OK] bg=2 梯度无漏判：满足条件的样本都已合并")

    below = [
        r
        for r in skips
        if r["_overlap_now"] >= 2
        and r["_ratio_now"] < _CROSS_BG2_RATIO
        and _shared_carries_proper_noun(r["title_a"], r["title_b"])
    ]
    if below:
        print(
            f"[?] 降 _CROSS_BG2_RATIO 至 {_CROSS_CANDIDATE_RATIO:.3f} 会新增合并 {len(below)} 条，"
            "需人工判读真伪（纯数字 token 常见误合并，故当前要求含字母 + 0.375 双门槛）"
        )
    edges = branches.get("cross_merge", [])
    edge3 = [r for r in edges if r["_overlap_now"] == _CROSS_BIGRAM_MIN]
    if edge3:
        print(f"[!] 跨源 bg={_CROSS_BIGRAM_MIN} 边界 {len(edge3)} 条：误合并风险集中区，需抽样人工判读")
    print(f"[i] 有效跨源样本 {cross_total} 条（≥100 条建议校准一次）；同源样本 {same_total} 条（≥50 条建议校准一次）")
    if anchor_total_bytes(_ACTIVE_FILE) > _ANCHOR_SIZE_WARN_BYTES:
        print(
            f"[!] 锚点文件超过 {_ANCHOR_SIZE_WARN_BYTES / 1e6:.0f} MB："
            f"运行 `python scripts/eval-dedup-threshold.py --compact` 压缩"
        )
    print()


def _print_current_rules() -> None:
    """打印当前阈值（全部取自 news_dedup 常量，无硬编码数字）。"""
    print("─" * 60)
    print("当前阈值规则（来源：news_dedup 常量）")
    print("─" * 60)
    print(f"  跨源候选区入口: ratio ≥ {_CROSS_CANDIDATE_RATIO}")
    print(f"  跨源主规则: 共享 ≥ {_CROSS_BIGRAM_MIN} 实体 bigram → 合并")
    print(
        f"  跨源专名梯度: 共享 = 2 且 ratio ≥ {_CROSS_BG2_RATIO} 且共享项含真专名"
        f"（英数需含字母、非泛词[{','.join(sorted(_GENERIC_TOKENS))}]，pattern={_TOKEN_LIKE.pattern}）→ 合并"
    )
    print(
        f"  跨源安全区: ratio ≥ {_CROSS_DIRECT_RATIO} 且专名 bg≥1 → 合并；"
        f"{_CROSS_SAFE_RATIO}~{_CROSS_DIRECT_RATIO} 需专名 bg≥2"
    )
    print(f"  同源: 共享 ≥ {_SAME_SRC_BIGRAM_MIN} 实体 bigram → 合并")
    print("  方向对立（上涨/下跌、站稳/跌破…）→ 不合并")
    print(f"  规则指纹: {_ANCHOR_RULES_VERSION}（写入锚点字段 {ANCHOR_RULES_FIELD}）")
    print()


def _print_compaction_result(result: dict[str, Any], file: str, *, dry_run: bool, before_bytes: int) -> None:
    """打印压缩结果（--compact 与评估后默认维护共用）。"""
    print(f"锚点文件: {file}")
    print(f"  压缩前: {result['before_lines']} 行 / {before_bytes / 1e6:.1f} MB")
    print(
        f"  压缩后: {result['after_lines']} 行 / {result['after_bytes'] / 1e6:.1f} MB"
        f"（唯一标题对 {result['unique_keys']}）"
    )
    print(f"  丢弃重复行中被判为历史规则时代的: {result['legacy_era']} 条")
    print(f"  保留行中无指纹、已补 legacy 标注的: {result['unattributed']} 条")
    print(f"  超保留期（{result['retention_days']} 天，0=不裁剪）丢弃: {result['expired']} 条")
    if result["trimmed"]:
        detail = "、".join(f"{name or '(无分支)'} {n} 条" for name, n in result["trimmed_by_branch"].items())
        print(f"  体积超目标裁剪: {result['trimmed']} 条（{detail}）")
    if result["aborted"]:
        print(f"  [!] 本轮放弃（{result['aborted']}），原文件未动")
    print(
        "  "
        + (
            "[..] --dry-run：未写盘"
            if dry_run
            else "[OK] 已原子替换（每个标题对保留最新一条）"
            if result["written"]
            else "[OK] 无需改动（未重写文件）"
        )
    )


def main() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true", help="仅显示汇总统计")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--compact", action="store_true", help="只压缩锚点文件（每个标题对保留最新一条）")
    mode.add_argument("--no-compact", action="store_true", help="评估后不压缩（只读分析；默认评估后压缩维护）")
    parser.add_argument("--dry-run", action="store_true", help="演练：压缩（--compact 或评估后默认维护）不写盘")
    parser.add_argument("--file", default=_ANCHOR_PATH, help=f"锚点文件路径（默认 {_ANCHOR_PATH}）")
    parser.add_argument(
        "--retention-days",
        type=int,
        default=None,
        help="压缩保留期天数（默认 _anchor_retention_days()；0 = 仅按键去重不裁剪）",
    )
    args = parser.parse_args()
    global _ACTIVE_FILE
    _ACTIVE_FILE = args.file

    before = anchor_total_bytes(args.file)

    if args.compact:
        result = compact_anchors(args.file, dry_run=args.dry_run, retention_days=args.retention_days)
        if not result["before_lines"]:
            print(f"[!] 锚点文件不存在或为空: {args.file}")
            return
        _print_compaction_result(result, args.file, dry_run=args.dry_run, before_bytes=before)
        return

    records = load_anchors(args.file)
    if not records:
        print(f"[!] 锚点文件不存在或为空: {args.file}")
        print("    请先运行一次报告生成（触发新闻获取），积累数据后再校准。")
        sys.exit(0)
    report(records, summary_only=args.summary)

    # 评估顺带维护：默认在分析完成后压缩（分析用完整样本，压缩只影响文件体积）。
    if not args.no_compact:
        print()
        print("=" * 60)
        print("[..] 评估后维护压缩（默认；--no-compact 可关闭）")
        try:
            result = compact_anchors(args.file, dry_run=args.dry_run, retention_days=args.retention_days)
        except OSError as exc:
            print(f"[!] 维护压缩失败（不影响本次评估结论）：{exc}")
            return
        _print_compaction_result(result, args.file, dry_run=args.dry_run, before_bytes=before)


if __name__ == "__main__":
    main()
