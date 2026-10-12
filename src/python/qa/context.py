"""报告上下文提取（report_qa_context）— 报告 HTML → 追问上下文与持仓基线。

设计落点：``docs/archive/v0.12.x/report-followup-qa/report-followup-qa-design.md`` §3.3。

上下文三段（设计口径）：**报告章节文本 + 生成条件声明**（关键数据摘要由
「汇总章全文」承担）——汇总/LLM 章全文保留，其余数据章摘要化，整体设字符上限。

解析锚点收敛在本文件（报告模板契约变更时的**唯一同步点**）：

  - 章节容器：``div.section[id^="sec-"]``；章标题：``div.section-title``
  - 持仓明细表：``sec-holdings_detail`` 内首张含「名称/代码/市值」表头的表
    （表头名映射取列，不受可选列（资金加权成本/申购状态等）增减影响）
  - 生成条件：``<title>`` 标题（结构化声明段；统计时间/所属交易日行随
    汇总章文本进入上下文）

失败策略（显式报错，不静默给错误上下文）：

  - 报告文件缺失 → ``ReportQaContextError(code="QA_REPORT_NOT_FOUND")``
  - 路径非法（非 .html 文件名）→ ``ReportQaContextError(code="QA_BAD_REPORT")``
  - 锚点全缺失（无法识别章节）→ ``ReportQaContextError(code="QA_CONTEXT_INVALID")``

零取数承诺：只读 ``output_dir`` 下的报告 HTML，不 import 任何数据源模块
（网络守卫下可测）。
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from src.python.config import get_default

logger = logging.getLogger("invest")

# ── 上下文容量口径（字符≈token 混排粗估，2 字符≈1 token）──
# 数据章摘要上限：真实报告单章可达 4 万~25 万字符（持仓明细/仓位矩阵/用量页签），
# 摘要保留章首结构与主要数值，问答「定位类」问题足够；LLM 章是追问主对象故留全文。
_QA_DATA_SECTION_CAP = 2_500
# LLM 章全文上限：常态单章 1~8K 字符，辩论/多维视角时可到 15K+，超限取章首。
_QA_LLM_SECTION_CAP = 16_000
# 整体上下文上限：典型报告 25~40K 字符（≈12~20K token，贴合设计 8~15K 估算），
# 恶性膨胀（多章超长）时保汇总+LLM 章、砍尾部数据章。
_QA_CONTEXT_CHAR_CAP = 60_000

# LLM 章（全文保留）——与报告模板 LLM 章 id 集合一致
_LLM_SECTION_IDS = frozenset(
    {
        "sec-summary",
        "sec-global_macro",
        "sec-expert_review",
        "sec-health_check",
        "sec-penetration_deep",
        "sec-self_review",
    }
)
_SUMMARY_SECTION_ID = "sec-summary"
_HOLDINGS_SECTION_ID = "sec-holdings_detail"
_TRUNC_MARK = "……（本章过长，已截断摘要，完整内容见报告原文）"
_CAP_MARK = "\n……（报告内容超出追问上下文上限，后文已截断）"
# 持仓明细表必含表头（缺一即认为非明细表——如「按分类」聚合表无单票行）
_HOLDINGS_HEADER_REQUIRED = ("名称", "代码", "市值")
# 数值清洗：去千分位/单位/百分号（收益率按百分数入基线，如 "12.34%" → 12.34）
_NUM_RE = re.compile(r"[^0-9.\-+]")

# 判定为「结构不可解析」前必须至少识别到的章节数下限之外的锚点
_ANCHOR_SECTION_PREFIX = "sec-"


class ReportQaContextError(Exception):
    """追问上下文提取失败。

    Attributes:
        code: 机器可读错误码（``QA_BAD_REPORT`` / ``QA_REPORT_NOT_FOUND`` /
            ``QA_CONTEXT_INVALID``），由会话层原样回传给 Web 路由做状态码映射。
    """

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ReportQaContext:
    """单份报告的追问上下文（冻结值对象，会话内一次构建多轮复用）。"""

    report: str
    text: str
    declaration: str
    holdings_details: list[dict] = field(default_factory=list)


class _ReportHtmlParser(HTMLParser):
    """最小化的报告 HTML 解析器：分章收集文本行 + 原始表格行。

    只认锚点不依赖具体样式（class 仅作标题辅助判定），script/style 整块跳过。
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self._sid = ""  # 当前章节 id（首章前为 ""，整体丢弃）
        self._lines: list[str] = []
        self._line: list[str] = []
        self._in_title = False
        self.title_parts: list[str] = []
        self.sections: list[tuple[str, list[str]]] = []
        self.tables: list[tuple[str, list[list[str]]]] = []  # (章 id, 原始行)
        self._rows: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    # ── 行/章缓冲 ──
    def _flush_line(self) -> None:
        text = "".join(self._line).strip()
        if text:
            self._lines.append(text)
        self._line = []

    def _flush_section(self) -> None:
        self._flush_line()
        if self._sid:  # 首章之前的导航/页眉不入上下文
            self.sections.append((self._sid, self._lines))
        self._lines = []

    # ── 标签事件 ──
    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = dict(attrs)
        if tag in ("script", "style"):
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "title":
            self._in_title = True
            return
        cls = a.get("class") or ""
        if tag == "div" and (a.get("id") or "").startswith(_ANCHOR_SECTION_PREFIX):
            self._flush_section()
            self._sid = a["id"] or ""
            return
        if tag == "table":
            self._flush_line()
            self._rows = []
            return
        if tag == "tr":
            if self._rows is not None:
                if self._row is not None:  # 上一行未闭合（容错落盘）
                    self._rows.append(self._row)
                self._row = []
            return
        if tag in ("td", "th"):
            if self._row is not None:
                self._cell = []
            return
        if tag == "br":
            self._flush_line()
            return
        if tag in ("p", "li", "div", "h1", "h2", "h3", "h4", "h5", "h6"):
            if tag == "div" and "section-title" in cls:
                self._flush_line()
                self._line.append("◆ ")
            else:
                self._flush_line()

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag == "title":
            self._in_title = False
            return
        if tag in ("td", "th"):
            if self._row is not None and self._cell is not None:
                self._row.append("".join(self._cell).strip())
            self._cell = None
            return
        if tag == "tr":
            if self._rows is not None and self._row:
                row = self._row
                self._rows.append(row)
                self._flush_line()
                self._lines.append(" | ".join(row))
            self._row = None
            return
        if tag == "table":
            if self._rows is not None:
                self.tables.append((self._sid, self._rows))
            self._rows = None
            self._flush_line()
            return
        if tag in ("p", "li", "div", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush_line()

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_title:
            self.title_parts.append(data)
            return
        if self._cell is not None:
            self._cell.append(data)
            return
        self._line.append(data)

    def finish(self) -> None:
        """收尾（parser.close() 后调用）：落盘最后一章。"""
        self._flush_section()


def sanitize_report_filename(report: str) -> str | None:
    """报告文件名单源净化（Web 路由 / 会话服务 / 上下文提取三层共用）。

    合法：非空 basename、不含 ``..`` 与路径分隔符、后缀为 ``.html``
    （大小写不敏感；``.html`` 这类纯后缀无基名一律拒绝）。非法返回
    ``None``——各层转译为自己的错误面（Web 400 / ``QA_BAD_REPORT``），
    分层防御语义不变（每层各自调用本函数）。
    """
    if not report or report != os.path.basename(report):
        return None
    if ".." in report or "/" in report or "\\" in report:
        return None
    if Path(report).suffix.lower() != ".html":
        return None
    return report


def _resolve_report_path(report: str, output_dir: str | None) -> Path:
    """解析报告文件路径（净化单源 + 分层防御）。"""
    if sanitize_report_filename(report) is None:
        raise ReportQaContextError("report 参数不合法", code="QA_BAD_REPORT")
    base = output_dir or get_default("output_dir") or "reports"
    path = Path(base) / report
    if not path.is_file():
        raise ReportQaContextError("报告文件不存在（可能已被删除或移动，请重新生成报告）", code="QA_REPORT_NOT_FOUND")
    return path


def _truncate(text: str, cap: int) -> str:
    if len(text) <= cap:
        return text
    return text[:cap].rstrip() + _TRUNC_MARK


def _to_float(raw: str) -> float | None:
    cleaned = _NUM_RE.sub("", raw.replace(",", ""))
    if not cleaned or cleaned in ("-", "+", ".", "-."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_holdings(tables: list[tuple[str, list[list[str]]]]) -> list[dict]:
    """持仓明细表 → 事实核对/上下文持仓基线（按表头名映射，合计行按空代码剔除）。"""
    for sid, rows in tables:
        if sid != _HOLDINGS_SECTION_ID or not rows:
            continue
        header = rows[0]
        if not set(_HOLDINGS_HEADER_REQUIRED) <= set(header):
            continue
        idx = {name: i for i, name in enumerate(header)}
        out: list[dict] = []
        for row in rows[1:]:
            if len(row) != len(header):
                continue
            code = row[idx["代码"]].strip()
            if not code:  # 合计/小计行
                continue
            item: dict = {
                "name": row[idx["名称"]].strip(),
                "code": code,
                "market_value": _to_float(row[idx["市值"]]),
            }
            for opt in ("份额", "收益率"):
                if opt in idx:
                    value = _to_float(row[idx[opt]])
                    item["shares" if opt == "份额" else "profit_rate"] = value
            out.append(item)
        return out
    return []


def extract_report_qa_context(report: str, output_dir: str | None = None) -> ReportQaContext:
    """从 output_dir 中读取报告 HTML，构建追问上下文（纯本地，零取数）。

    Args:
        report: 报告文件名（basename，须为 .html）。
        output_dir: 报告目录，缺省取 ``config.output_dir``。

    Returns:
        :class:`ReportQaContext`（章节文本 + 生成条件声明 + 持仓基线）。

    Raises:
        ReportQaContextError: 路径非法 / 文件缺失 / 锚点缺失（见模块 docstring）。
    """
    path = _resolve_report_path(report, output_dir)
    html = path.read_text(encoding="utf-8")
    parser = _ReportHtmlParser()
    parser.feed(html)
    parser.close()
    parser.finish()

    if not parser.sections:
        logger.warning("[report_qa] 报告无可用章节锚点（sec-*），判定结构不可解析 report=%s", report)
        raise ReportQaContextError("无法解析该报告结构，追问不可用（请重新生成报告后重试）", code="QA_CONTEXT_INVALID")

    parts: list[str] = []
    for sid, lines in parser.sections:
        text = "\n".join(lines).strip()
        if not text:
            continue
        if sid == _SUMMARY_SECTION_ID:
            parts.append(_truncate(text, _QA_LLM_SECTION_CAP))  # 汇总章小，等同全文
        elif sid in _LLM_SECTION_IDS:
            parts.append(_truncate(text, _QA_LLM_SECTION_CAP))
        else:
            parts.append(_truncate(text, _QA_DATA_SECTION_CAP))
    context_text = "\n\n".join(parts)
    if len(context_text) > _QA_CONTEXT_CHAR_CAP:
        context_text = context_text[:_QA_CONTEXT_CHAR_CAP].rstrip() + _CAP_MARK

    title = "".join(parser.title_parts).strip()
    declaration = (
        f"报告标题：{title or report}；报告文件：{report}；"
        "统计时间/所属交易日见「汇总」章内时间行；数据均为报告生成时点数据，非实时。"
    )
    holdings = _extract_holdings(parser.tables)
    logger.info(
        "[report_qa] 上下文构建完成 report=%s 章节数=%d 字符=%d 持仓行=%d",
        report,
        len(parser.sections),
        len(context_text),
        len(holdings),
    )
    return ReportQaContext(
        report=report,
        text=context_text,
        declaration=declaration,
        holdings_details=holdings,
    )
