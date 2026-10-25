"""JSONL 事件存储原语 — 原子追加 + 容错读取（core 层共享）。

本模块抽出 `core/perf.py` 与 `core/decision_ledger.py` 中**逐字重复**的
原子追加实现，避免第三份拷贝（`core/signal_ledger.py` 亦需要同一原语）。

设计约束遵从（对齐 `core/perf.py` / `core/decision_ledger.py` 先例）：
    分层约束  — 本模块属 core 层，只依赖 stdlib，禁止 import report/llm/analysis
    原子写入  — 读全部现有内容 → 追加新行 → 落盘走 `core/atomic_write` 的
                mkstemp + os.replace，防断电/崩溃产生半写损坏档
    无单例    — 纯函数集，不驻留模块全局状态
    日志统一  — logging.getLogger("invest")；log_tag/noun 由调用方注入，
                保证迁移后各调用点日志文本逐字不变

调用方（各自保持原有 prefix / log_tag / noun）：
    core/perf.py            → prefix=".perf_history_"      tag="perf"
    core/decision_ledger.py → prefix=".decision_ledger_"   tag="decision_ledger"
    core/signal_ledger.py   → prefix=".signal_ledger_"     tag="signal_ledger"
    providers/news_dedup.py → prefix=".dedup_anchors_"     tag="dedup"
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable

from src.python.core.atomic_write import write_text_atomic

logger = logging.getLogger("invest")


def append_jsonl_atomic(
    path: str,
    line: str,
    *,
    prefix: str = ".jsonl_",
    log_tag: str = "jsonl",
    noun: str = "JSONL 文件",
    max_lines: int | None = None,
) -> bool:
    """向 JSONL 文件原子追加一行（`line` 需自带结尾换行）。

    Args:
        path: 目标 JSONL 文件路径（父目录不存在时自动创建）
        line: 已序列化的单行内容（含 "\\n"）
        prefix: 临时文件名前缀（各调用点保留原值，便于故障定位）
        log_tag: 日志标签（如 "perf"）
        noun: 日志中对该文件的称谓（如 "历史文件" / "账本"）

    Returns:
        是否落盘成功。写盘异常已在内部记日志并**不向上抛出**（本原语只负责尽力
        持久化，不承担中断调用链的职责）；但必须把成败**如实返回**——调用方若对
        外承诺「已写入 N 条」，就得据此判定，否则写盘失败会被报成成功。
    """
    return append_jsonl_atomic_many(path, [line], prefix=prefix, log_tag=log_tag, noun=noun, max_lines=max_lines)


def append_jsonl_atomic_many(
    path: str,
    lines: list[str],
    *,
    prefix: str = ".jsonl_",
    log_tag: str = "jsonl",
    noun: str = "JSONL 文件",
    max_lines: int | None = None,
) -> bool:
    """向 JSONL 文件**一次性**原子追加多行（`lines` 每项需自带结尾换行）。

    批量入口存在的理由是成本：本原语的原子性来自「读全文 → 拼接 → 整文件
    替换」，逐行调用等价于每行重写一次全文件（O(n²)）。调用方有多行要写时
    必须走本函数一次性拼接，不得在循环里调 ``append_jsonl_atomic``。

    Args:
        path: 目标 JSONL 文件路径（父目录不存在时自动创建）
        lines: 已序列化的多行内容（每项含 "\\n"）；空列表时立即返回 True
        其余参数同 :func:`append_jsonl_atomic`

    ``max_lines``（保留上限）：追加后超限时只留末尾 N 行、最旧行丢弃——专为
    **遥测类**只增历史（perf/健康检查）防无界增长设计。业务态账本（决策/信号/
    折叠/去重锚点）丢失即丢状态，**不得**用它做裁剪；这类文件需要保留窗口时走
    :func:`prune_jsonl_by_age`（按龄裁剪 + 可选保留谓词，不会无视语义丢状态）。
    追加本就要重写全文件，裁剪零额外 I/O 成本。

    Returns:
        是否落盘成功（语义同 :func:`append_jsonl_atomic`）。
    """
    if not lines:
        return True
    existing = ""
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = f.read()
        except OSError:
            logger.warning("[%s] %s不可读，将重新创建: %s", log_tag, noun, path)

    content = existing + "".join(lines)
    if max_lines is not None:
        parts = content.splitlines(keepends=True)
        if len(parts) > max_lines:
            logger.debug(
                "[%s] %s超出保留上限（%d 行），丢弃最旧 %d 行",
                log_tag,
                noun,
                len(parts),
                len(parts) - max_lines,
            )
            content = "".join(parts[-max_lines:])

    return write_text_atomic(
        path,
        content,
        prefix=prefix,
        log_tag=log_tag,
        noun=noun,
    )


def read_jsonl(
    path: str,
    *,
    log_tag: str = "jsonl",
    noun: str = "JSONL 文件",
) -> list[dict[str, Any]]:
    """读取全量记录（按写入顺序）。

    损坏行（JSON 解析失败）跳过并告警，不中断后续行；文件不存在返回空列表。
    非 dict 的合法 JSON 行（如裸数组/标量）同样跳过——账本契约只认对象。
    """
    if not os.path.isfile(path):
        return []
    records: list[dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("[%s] 忽略损坏行: %s", log_tag, line[:80])
                    continue
                if isinstance(parsed, dict):
                    records.append(parsed)
                else:
                    logger.warning("[%s] 忽略非对象行: %s", log_tag, line[:80])
    except OSError:
        logger.warning("[%s] %s读取失败: %s", log_tag, noun, path)
    return records


def prune_jsonl_by_age(
    path: str,
    *,
    retention_days: int,
    date_key: str,
    keep: Callable[[dict[str, Any]], bool] | None = None,
    prefix: str = ".jsonl_",
    log_tag: str = "jsonl",
    noun: str = "JSONL 文件",
) -> tuple[int, int]:
    """按**龄**裁剪业务态账本：早于保留窗口的行丢弃，`keep` 命中的行无条件保留。

    为什么不做成 `max_lines`：业务账本一行就是一份状态（决策/结算/信号），按行数
    截断会把最旧的已结算样本一起裁掉，「跨期反思」类消费随即失样本；按龄裁剪才
    对应真实语义（超过保留期的历史不再参与反思），`keep` 再兜住必须长期留存的
    记录（如已结算决策）。

    Args:
        retention_days: 保留天数（<=0 表示不裁剪，直接返回）
        date_key: 行内日期字段名（取 ISO 日期前 10 位比较；解析失败的行**保留**）
        keep: 额外保留谓词（返回 True 的行无论多旧都留下）
        prefix/log_tag/noun: 同其他原语（保留调用点原有日志文本）

    Returns:
        (保留行数, 丢弃行数)。文件不存在或全空时返回 (0, 0)。
    """
    import datetime as _dt

    if retention_days <= 0 or not os.path.isfile(path):
        return (0, 0)
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines(keepends=True)
    except OSError:
        logger.warning("[%s] %s不可读，跳过裁剪: %s", log_tag, noun, path)
        return (0, 0)

    cutoff = (_dt.date.today() - _dt.timedelta(days=retention_days)).isoformat()
    kept: list[str] = []
    dropped = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            kept.append(line)  # 坏行不裁：留给读取侧告警，不由裁剪静默吞掉
            continue
        if not isinstance(record, dict):
            kept.append(line)
            continue
        day = str(record.get(date_key) or "")[:10]
        fresh_enough = not day or day >= cutoff
        if fresh_enough or (keep is not None and keep(record)):
            kept.append(line)
        else:
            dropped += 1
    if dropped:
        write_text_atomic(path, "".join(kept), prefix=prefix, log_tag=log_tag, noun=noun)
        logger.info("[%s] %s按龄裁剪：丢弃 %d 行（保留 %d 天）", log_tag, noun, dropped, retention_days)
    return (len(kept), dropped)
