"""板块分类原语 — 行业关键词表加载与名称→板块判定（core 层共享）。

为什么在 `core/`：关键词表与判定是**纯分类计算**，被 `report/`（穿透、事件窗）与
`analysis/`（景气度评分与输入装配）两侧共同消费。分类原语若留在报告层，纯计算层
就只能反向依赖报告层（分层越界），口径也会随两侧各写一份而漂移。

单源在 ``data/knowledge/sector_keywords.json``：本模块负责读盘、降级与只读访问，
消费方一律经 :func:`sector_keywords` 取用，不各自读盘、不复制表。
"""

from __future__ import annotations

import json
import logging
import os

from src.python.core.constants import PROJECT_ROOT

logger = logging.getLogger("invest")

#: 行业关键词映射表路径（名称关键词 → 板块）
SECTOR_KEYWORDS_FILE = os.path.join(PROJECT_ROOT, "data/knowledge/sector_keywords.json")


def load_sector_keywords() -> dict[str, str]:
    """从 ``sector_keywords.json`` 加载行业关键词映射表；不可读时降级为空表。

    Returns:
        关键词 → 板块名 的映射；文件缺失或 JSON 损坏一律返回 ``{}``（判定回落 "--"）。
    """
    if not os.path.exists(SECTOR_KEYWORDS_FILE):
        logger.warning("[板块] 行业关键词文件 %s 不存在，使用空表", SECTOR_KEYWORDS_FILE)
        return {}
    try:
        with open(SECTOR_KEYWORDS_FILE, encoding="utf-8") as f:
            data: dict[str, str] = json.load(f)
        logger.debug("[板块] 已加载 %d 条行业关键词", len(data))
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("[板块] 加载行业关键词文件失败: %s，使用空表", e)
        return {}


_SECTOR_KEYWORDS: dict[str, str] = load_sector_keywords()


def sector_keywords() -> dict[str, str]:
    """行业关键词表只读副本（关键词 → 板块），供各域复用同一份映射。

    Returns:
        关键词 → 板块名（如 ``{"白酒": "消费", "芯片": "科技"}``）的浅拷贝。
    """
    return dict(_SECTOR_KEYWORDS)


def reset_sector_keywords() -> None:
    """把进程内关键词表退回「按当前文件重新读盘」的基线（测试隔离用）。"""
    global _SECTOR_KEYWORDS
    _SECTOR_KEYWORDS = load_sector_keywords()


def reload_sector_keywords() -> dict[str, str]:
    """重新读盘并替换进程内关键词表（配置/知识库热更新与测试注入用）。

    Returns:
        新表（与 :func:`sector_keywords` 同一份内容的浅拷贝）。
    """
    global _SECTOR_KEYWORDS
    _SECTOR_KEYWORDS = load_sector_keywords()
    return dict(_SECTOR_KEYWORDS)


def classify_sector(name: str, _code: str = "") -> str:
    """根据证券名称判断所属板块（关键词命中）。

    Args:
        name: 证券名称
        _code: 证券代码（保留位，当前判定不看代码）

    Returns:
        板块名称，如 "消费" / "科技" / "医药" / "新能源"；空名称或未命中返回 "--"。
    """
    if not name:
        return "--"
    clean = name.replace(" ", "").upper()
    for keyword, sector in _SECTOR_KEYWORDS.items():
        if keyword.upper() in clean:
            return sector
    return "--"
