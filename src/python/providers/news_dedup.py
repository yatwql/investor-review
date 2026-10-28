"""新闻去重主流程 — 标题模糊去重 + 锚点采集门面。

判定口径（阈值常量 / 模板词表 / 归一化 / 实体 bigram / 相似度 / 方向词对 / 规则指纹）
在 ``providers/news_dedup_rules.py``；锚点文件的字节动作在
``providers/news_dedup_anchor_store.py``，保留期/体积/采样策略在
``providers/news_dedup_anchor_policy.py``。本模块保留比较循环，并原面
re-export 两层原语（``from ...news_dedup import compact_anchor_file`` /
``_normalize_title`` 等既有引用与 patch 点不受影响）。
"""

from __future__ import annotations

import logging
from typing import Any

from src.python.providers.news_dedup_anchor_policy import (  # noqa: F401  — 门面 re-export
    _ANCHOR_BRANCH_MIN_KEEP,
    _ANCHOR_COLLECT_ENV,
    _ANCHOR_COMPACT_ENV,
    _ANCHOR_KEEP_BACKUP_ENV,
    _ANCHOR_MAINTENANCE_ENV,
    _ANCHOR_RETENTION_DAYS,
    _ANCHOR_RETENTION_ENV,
    _ANCHOR_SIZE_TARGET_BYTES,
    _ANCHOR_SIZE_WARN_BYTES,
    _SAME_SRC_ANCHOR_SAMPLE,
    _SAME_SRC_RULE,
    _anchor_branch,
    _anchor_collection_enabled,
    _anchor_key,
    _anchor_retention_cutoff,
    _anchor_retention_days,
    _anchor_sampled,
    _anchor_ts_on_or_after,
    _anchor_within_retention,
    _compact_anchor_file,
    _flush_anchors,
    _make_anchor,
    _maybe_maintain_anchor_file,
    _record_anchor,
    compact_anchor_file,
    reset_anchor_records,
)
from src.python.providers.news_dedup_anchor_store import (  # noqa: F401  — 门面 re-export
    _ANCHOR_PATH,
    _ANCHOR_SHARD_PREFIX,
    _ANCHOR_SHARD_SUFFIX,
    anchor_shard_paths,
    anchor_total_bytes,
    read_anchor_lines,
)
from src.python.providers.news_dedup_rules import (  # noqa: F401  — 门面 re-export
    ANCHOR_LEGACY_ERA,
    ANCHOR_RULES_FIELD,
    _ANCHOR_RULES_VERSION,
    anchor_rules_version,
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
                    _record_anchor(_make_anchor(item, existing_item, 0.0, overlap, False, _SAME_SRC_RULE))

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
