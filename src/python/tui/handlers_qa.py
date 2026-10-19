"""TUI 报告对话式追问入口（主菜单 [Q]，``report_qa`` 开关门控）。

文本输入循环（``input()`` 多轮 while + 退出指令，非全屏 TUI）：选择报告 →
提问 → 展示回答 → 继续/退出。会话/上下文/记账/降级全部经
``qa/session.py::ask_report_qa``（与 Web 路由同源同一服务），本模块零业务
副本——只做终端呈现与输入编排；LLM 调用因此天然经 Provider Chain 与合规
漏斗（LLM 调用统一入口的架构约束），用量独立记账于 ``QaSession.usage``（不进报告 LLM
用量页签，见 llm-technical §9.1 记账边界）。
"""

from __future__ import annotations

import os
from datetime import datetime
from html.parser import HTMLParser

from src.python.core.logger import setup_logger
from src.python.qa.error_codes import QA_CONTEXT_INVALID, QA_INPUT_CAP_EXCEEDED, QA_REPORT_NOT_FOUND, QA_SESSION_LIMIT
from src.python.qa.session import ask_report_qa
from src.python.tui.text_layout import wrap_prompt
from src.python.tui.tui_keys import input_choice

logger = setup_logger()

_QA_REPORT_LIST_MAX = 8  # 报告候选展示上限（输出目录顶层 .html，按修改时间倒序）
_QA_PROMPT = "  请输入问题（回车/q 返回主菜单）: "
#: 终止整个输入循环的错误码（会话上限/报告不可用——继续提问无意义）
_EXIT_LOOP_CODES = frozenset({QA_SESSION_LIMIT, QA_INPUT_CAP_EXCEEDED, QA_REPORT_NOT_FOUND, QA_CONTEXT_INVALID})
#: 输入级中止（已超会话轮数上限/单条输入超长——展示提示后退出本轮追问）
_INPUT_ABORT_CODES = frozenset({QA_SESSION_LIMIT, QA_INPUT_CAP_EXCEEDED})


class _TextExtractor(HTMLParser):
    """HTML → 纯文本提取（块级标签换行、script/style 整块丢弃，终端展示用）。"""

    _BLOCK_TAGS = frozenset(
        {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "hr", "table", "blockquote"}
    )
    _SKIP_TAGS = frozenset({"script", "style"})

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._SKIP_TAGS:
            self._skip += 1
        elif tag in self._BLOCK_TAGS and self._parts and self._parts[-1] != "\n":
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def text(self) -> str:
        """拼接提取结果。"""
        return "".join(self._parts)


def _html_to_text(html: str) -> str:
    """剥离 HTML 为可读纯文本（块级换行、压缩连续空行、去首尾空白）。"""
    parser = _TextExtractor()
    parser.feed(html or "")
    text = "\n".join(line.strip() for line in parser.text().splitlines())
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip()


def _resolve_output_dir() -> str:
    """当前报告输出目录（config 覆写优先，缺省取默认值，与 Web 路由同口径）。"""
    from src.python.config import get_config, get_default

    config = get_config()
    return config.get("output_dir") or get_default("output_dir")


def _list_reports(output_dir: str) -> list[str]:
    """输出目录顶层的 HTML 报告文件名（修改时间倒序，截断至展示上限）。

    只列顶层（最新版固定名产物）；日期归档子目录不入选——追问锚定「本期
    报告」，历史归档追问无入口（与 Web 报告页追问同一取材面）。
    """
    try:
        names = [
            name
            for name in os.listdir(output_dir)
            if name.lower().endswith(".html") and os.path.isfile(os.path.join(output_dir, name))
        ]
    except OSError:
        return []
    entries: list[tuple[float, str]] = []
    for name in names:
        try:
            entries.append((os.path.getmtime(os.path.join(output_dir, name)), name))
        except OSError:  # 并发删除等竞态：跳过该文件
            continue
    entries.sort(reverse=True)
    return [name for _mtime, name in entries[:_QA_REPORT_LIST_MAX]]


def _select_report(output_dir: str) -> str | None:
    """编号选择报告（回车默认最新、q/EOF/Ctrl+C 取消）。"""
    reports = _list_reports(output_dir)
    if not reports:
        print("  [!] 输出目录暂无 HTML 报告——先生成一份报告，或在 [D] 中核对输出目录")
        return None
    print(f"\n  可追问的报告（{output_dir}）：")
    for i, name in enumerate(reports, 1):
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(os.path.join(output_dir, name)))
            stamp = f"{mtime:%Y-%m-%d %H:%M}"
        except OSError:
            stamp = "时间未知"
        print(f"    {i}. {name}  ({stamp})")
    while True:
        try:
            raw = input_choice(wrap_prompt("  选择报告编号（直接回车 = 最新，q 取消）: "))
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if raw is None:  # Esc：取消问答
            return None
        if raw.lower() == "q":
            return None
        if raw == "":
            return reports[0]
        try:
            idx = int(raw)
        except ValueError:
            print("  [!] 请输入编号")
            continue
        if 1 <= idx <= len(reports):
            return reports[idx - 1]
        print(f"  [!] 编号超出范围（1-{len(reports)}）")


def _qa_input_loop(report: str) -> None:
    """问答输入循环：提问 → 展示回答（纯文本化）→ 续问，直到退出指令或终止错误。"""
    print(f"\n  [..] 追问会话：{report}")
    print("      回答基于该报告生成时的数据（非实时），仅供参考，不构成操作建议")
    print("      回车或 q 返回主菜单\n")
    session_id: str | None = None
    turns = 0
    while True:
        try:
            question = input(_QA_PROMPT).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question or question.lower() == "q":
            break
        print("  [..] 思考中…")
        result = ask_report_qa(report=report, question=question, session_id=session_id)
        if not result.get("ok"):
            error = result.get("error") or "服务暂不可用"
            code = result.get("error_code") or ""
            print(f"  [!] {error}")
            logger.info("[report_qa] TUI 追问失败 code=%s report=%s", code, report)
            if code in _EXIT_LOOP_CODES:
                if code in _INPUT_ABORT_CODES:
                    print("      会话已达上限，返回主菜单（重新进入可开新会话）")
                break
            continue
        session_id = result.get("session_id") or session_id
        turns = int(result.get("turns") or 0)
        for line in _html_to_text(result.get("answer_html") or "").splitlines():
            print(f"    {line}" if line else "")
        if result.get("fact_warning"):
            print("  [!] 回答中的部分数值未能与报告数据完全核对一致，请以报告原文为准")
        usage = result.get("usage") or {}
        remaining = result.get("remaining_turns")
        print(
            f"      第 {turns} 轮完成"
            + (f"，剩余 {remaining} 轮" if remaining is not None else "")
            + f"｜累计 tokens {usage.get('input_tokens', 0)}/{usage.get('output_tokens', 0)}"
        )
    if turns:
        print(f"  [OK] 追问结束（共 {turns} 轮，用量见上）")


def _cmd_report_qa() -> None:
    """菜单 [Q] 回调：报告对话式追问（选择报告后进入文本输入循环）。"""
    from src.python.config.features import is_feature_enabled

    if not is_feature_enabled("report_qa"):
        # 菜单层已按开关裁剪（FEATURE_GATED_ITEMS）；此处为直调/竞态兜底
        print("  [!] 报告追问功能未开启（[S] 面板启用「报告对话式追问」，或 --experiment report_qa）")
        return
    output_dir = _resolve_output_dir()
    report = _select_report(output_dir)
    if report is None:
        return
    logger.info("[report_qa] TUI 追问会话开始 report=%s", report)
    _qa_input_loop(report)
