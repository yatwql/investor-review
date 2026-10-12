"""报告问答会话服务（report_qa_session）— 会话表 / 轮数上限 / 用量记账 / 编排。

设计落点：``docs/archive/v0.12.x/report-followup-qa/report-followup-qa-design.md`` §3.4-3.6。

职责：

  - **会话表**（进程内）：按 ``(report, session_id)`` 复用问答历史；换报告或未知
    session_id 一律新建会话（同会话必同报告，防上下文串味）；超过保留上限按
    最久未用淘汰；``threading.RLock`` 结构锁 + 每会话执行锁（同会话串行、跨会话并行）。
  - **轮数硬上限**：``_QA_MAX_TURNS`` 轮后显式报错（``QA_SESSION_LIMIT``），
    超限不静默；LLM 失败不消耗轮次（未交付回答不计数）。
  - **输入 token 软上限**：按字符数粗估（2 字符≈1 token，宁高估），超限返回
    ``QA_INPUT_CAP_EXCEEDED`` 引导刷新——**不做**会话缓存（设计取舍：靠系统
    prompt 复现性与上下文上限约束）。
  - **用量独立记账**：``QaSession.usage``（input/output tokens + provider），
    不写报告周期的 LLM 用量统计（依赖方向 ``qa → llm`` 单向，llm 不感知 qa）。
  - **质量核对**：回答经 ``llm/fact_checker.run_fact_check``（``auto_correct=False``
    只检不改，报告数据为准），summary 含警示时附加 ``qa-fact-warning`` 标注；
    核对异常降级返回原文不阻断。
  - **降级**：LLM 未配置/未产出 → ``QA_LLM_UNAVAILABLE``/``QA_LLM_FAILED``，
    Web 路由映射 503，前端展示占位文案，不把错误码当正常回答。

安全边界：日志只记问题前 ``_QA_LOG_QUESTION_CHARS`` 字与 token 数，不记
上下文与回答正文；上下文提取失败（文件缺失/结构不可解析）在消耗轮次前返回。

Web 路由（``web/handlers._handle_report_qa_ask``）与 TUI 追问入口共用本入口。
"""

from __future__ import annotations

import logging
import threading
import time
import uuid

from src.python.config import get_llm_config
from src.python.llm.api import call_llm
from src.python.llm.fact_checker import run_fact_check
from src.python.llm.markdown import markdown_to_html
from src.python.qa.context import (
    ReportQaContextError,
    extract_report_qa_context,
    sanitize_report_filename,
)
from src.python.qa.error_codes import (
    QA_BAD_QUESTION,
    QA_BAD_REPORT,
    QA_INPUT_CAP_EXCEEDED,
    QA_LLM_FAILED,
    QA_LLM_UNAVAILABLE,
    QA_QUESTION_TOO_LONG,
    QA_SESSION_LIMIT,
)

logger = logging.getLogger("invest")

# ── 会话/输入口径 ──
_QA_MAX_TURNS = 10  # 单会话轮数硬上限（设计：超限显式报错）
_QA_HISTORY_TURNS = 6  # 近期问答进入 prompt 的轮数（更早仅折叠问题清单）
_QA_SESSION_KEEP = 32  # 会话表保留上限（超出按最久未用淘汰）
_QA_QUESTION_MAX_CHARS = 1_000
_QA_ANSWER_MAX_TOKENS = 2_048
_QA_TOKEN_CHARS_PER_TOKEN = 2  # 混排粗估：2 字符≈1 token（宁高估不低估）
_QA_INPUT_TOKEN_CAP = 60_000  # 输入软上限（上下文 60K 字符 + 历史/问题仍有余量）
_QA_LOG_QUESTION_CHARS = 20
_QA_FACT_WARNING_CLASS = "qa-fact-warning"
_QA_FOOTNOTE_CLASS = "qa-answer-note"

# 事实核对 summary 出现警示的判据（与 llm/fact_checker 口径一致）
_FACT_WARN_MARK = "⚠"

_QA_SYSTEM_RULES = (
    "你是投资复盘报告的答疑助手，只能依据下方【本期报告内容】回答读者对本期报告的提问。\n"
    "边界（不可逾越）：\n"
    "1. 只答疑本期报告已生成的内容，不引入报告之外的实时数据（行情/新闻均为报告生成时点数据）。\n"
    "2. 不给出仓位操作建议（不回答「该不该加/减仓」类问题，指出报告中相关数据即可）。\n"
    "3. 不做全市场筛选与选股（超出报告范围的问题如实说明）。\n"
    "4. 回答用中文、简洁分点；涉及数字时给出报告中的原始口径与所在章节。\n"
    "5. 报告未覆盖的内容直接说明「报告中未涉及」，不得编造。\n"
)

_sessions: dict[str, "QaSession"] = {}
_sessions_table_lock = threading.Lock()


class QaSession:
    """单份报告的问答会话（内存态，结构字段与执行期字段分离）。

    Attributes:
        session_id: 会话标识（返回给前端续传）。
        report: 所属报告文件名（同会话必同报告）。
        history: 问答历史（``q`` 问题原文 / ``a`` 回答 Markdown 纯文本，
            无 HTML——prompt 组装只做文本，避免标签噪声）。
        turns: 已消耗轮数（仅成功回答后递增）。
        usage: 累计用量 ``{"input_tokens", "output_tokens", "provider"}``。
        context: 追问上下文（惰性一次构建，同报告多轮复用）。
    """

    def __init__(self, report: str) -> None:
        self.session_id = uuid.uuid4().hex[:12]
        self.report = report
        self.history: list[dict] = []
        self.turns = 0
        self.usage: dict = {"input_tokens": 0, "output_tokens": 0, "provider": ""}
        self.context = None
        self.last_used = time.time()
        self._lock = threading.Lock()


def create_report_qa_session(report: str) -> QaSession:
    """新建会话并登记到会话表（超出保留上限时淘汰最久未用）。"""
    session = QaSession(report)
    with _sessions_table_lock:
        if len(_sessions) >= _QA_SESSION_KEEP:
            oldest = min(_sessions.values(), key=lambda s: s.last_used)
            _sessions.pop(oldest.session_id, None)
        _sessions[session.session_id] = session
    return session


def report_qa_session_count() -> int:
    """当前会话表大小（诊断/测试用）。"""
    with _sessions_table_lock:
        return len(_sessions)


def reset_report_qa_sessions() -> None:
    """清空会话表（测试隔离用——conftest autouse 夹具每用例调用）。"""
    with _sessions_table_lock:
        _sessions.clear()


def _acquire_session(report: str, session_id: str | None) -> QaSession:
    """取会话：有效 id 且同报告则复用，否则新建（未知 id 不继承他人历史）。"""
    if session_id:
        with _sessions_table_lock:
            session = _sessions.get(session_id)
            if session is not None and session.report == report:
                session.last_used = time.time()
                return session
    return create_report_qa_session(report)


def _history_block(session: QaSession) -> str:
    """历史 → prompt 片段（近期问答 + 更早问题折叠清单，纯文本）。"""
    if not session.history:
        return ""
    older = session.history[:-_QA_HISTORY_TURNS]
    recent = session.history[-_QA_HISTORY_TURNS:]
    lines: list[str] = []
    if older:
        lines.append("【更早讨论过的问题（仅列问题）】" + "；".join(h["q"] for h in older))
    lines.append("【近期问答（上下文衔接用）】")
    for item in recent:
        lines.append(f"问：{item['q']}\n答：{item['a']}")
    return "\n".join(lines) + "\n\n"


def _fail(code: str, message: str, **extra) -> dict:
    return {"ok": False, "error_code": code, "error": message, **extra}


def _fact_check(answer_html: str, holdings: list[dict]) -> tuple[bool, bool]:
    """事实核对（只检不改）。返回 (是否附加质量警示, 是否降级原文)。"""
    try:
        _checked, summary = run_fact_check(
            answer_html,
            holdings,
            module_label="报告追问",
            auto_correct=False,
        )
    except Exception:  # 核对自身异常：降级返回原文，不阻断追问
        logger.warning("[report_qa] 事实核对异常，降级返回原文", exc_info=True)
        return False, True
    warned = bool(summary) and _FACT_WARN_MARK in summary
    return warned, False


def ask_report_qa(
    report: str,
    question: str,
    session_id: str | None = None,
    *,
    output_dir: str | None = None,
    llm_config: dict | None = None,
    http_client=None,
) -> dict:
    """报告追问主入口（Web 路由与 TUI 共用）。

    Args:
        report: 报告文件名（basename，.html）。
        question: 读者问题（非空，≤ ``_QA_QUESTION_MAX_CHARS`` 字）。
        session_id: 续传会话 id（缺省/未知/换报告 → 新建会话）。
        output_dir: 报告目录（缺省取 config.output_dir）。
        llm_config: 显式 LLM 配置（缺省读 ``get_llm_config()``，测试可注入）。
        http_client: 注入式 HTTP 客户端（透传 ``call_llm``，测试用）。

    Returns:
        成功 ``{"ok": True, "session_id", "answer_html", "turns",
        "remaining_turns", "usage", "fact_warning"}``；
        失败 ``{"ok": False, "error_code", "error", ...}``（错误码见模块 docstring
        与 Web 路由状态码映射表）。
    """
    question = (question or "").strip()
    if not question:
        return _fail(QA_BAD_QUESTION, "问题不能为空")
    if len(question) > _QA_QUESTION_MAX_CHARS:
        return _fail(
            QA_QUESTION_TOO_LONG,
            f"问题过长（上限 {_QA_QUESTION_MAX_CHARS} 字），请精简后重试",
        )
    if sanitize_report_filename(report) is None:
        return _fail(QA_BAD_REPORT, "report 参数不合法（仅限 .html 报告文件名）")

    config = llm_config if llm_config is not None else get_llm_config()
    if not config:
        return _fail(QA_LLM_UNAVAILABLE, "服务暂不可用（LLM 未配置）")

    session = _acquire_session(report, session_id)
    with session._lock:  # 同会话串行（历史/轮数/记账一致性），跨会话并行
        if session.turns >= _QA_MAX_TURNS:
            return _fail(
                QA_SESSION_LIMIT,
                f"本轮对话已达 {_QA_MAX_TURNS} 轮上限，请刷新页面开始新会话",
                session_id=session.session_id,
            )
        if session.context is None:
            try:
                session.context = extract_report_qa_context(report, output_dir=output_dir)
            except ReportQaContextError as exc:
                logger.warning("[report_qa] 上下文不可用 code=%s report=%s", exc.code, report)
                return _fail(exc.code, str(exc))

        history_block = _history_block(session)
        input_chars = (
            len(_QA_SYSTEM_RULES)
            + len(session.context.declaration)
            + len(session.context.text)
            + len(history_block)
            + len(question)
        )
        if input_chars // _QA_TOKEN_CHARS_PER_TOKEN > _QA_INPUT_TOKEN_CAP:
            return _fail(
                QA_INPUT_CAP_EXCEEDED,
                "会话输入已达上限，请刷新页面开始新会话",
                session_id=session.session_id,
            )

        system_prompt = (
            _QA_SYSTEM_RULES
            + "\n【生成条件】\n"
            + session.context.declaration
            + "\n\n【本期报告内容】\n"
            + session.context.text
        )
        user_prompt = history_block + question
        content, usage, provider_info = call_llm(
            system_prompt,
            user_prompt,
            config,
            max_tokens=_QA_ANSWER_MAX_TOKENS,
            http_client=http_client,
        )
        if not content or not content.strip():
            logger.warning("[report_qa] LLM 未产出有效回答 report=%s", report)
            return _fail(
                QA_LLM_FAILED,
                "服务暂不可用（本次未产出有效回答，请稍后重试）",
                session_id=session.session_id,
            )
        answer_html = markdown_to_html(content).strip()
        if not answer_html:
            return _fail(
                QA_LLM_FAILED,
                "服务暂不可用（本次未产出有效回答，请稍后重试）",
                session_id=session.session_id,
            )

        warned, degraded = _fact_check(answer_html, session.context.holdings_details)
        fragments = [answer_html]
        if warned:
            fragments.append(
                f'<div class="{_QA_FACT_WARNING_CLASS}">⚠ 回答中的部分数值未能与报告数据'
                "完全核对一致，请以报告原文为准。</div>"
            )
        fragments.append(
            f'<div class="{_QA_FOOTNOTE_CLASS}">基于报告生成时的数据（非实时），仅供参考，不构成操作建议。</div>'
        )
        final_html = "".join(fragments)

        # ── 记账与轮数（成功交付才消耗轮次）──
        in_tok = int((usage or {}).get("input_tokens") or (usage or {}).get("prompt_tokens") or 0)
        out_tok = int((usage or {}).get("output_tokens") or (usage or {}).get("completion_tokens") or 0)
        session.turns += 1
        session.history.append({"q": question, "a": content})
        session.usage["input_tokens"] += in_tok
        session.usage["output_tokens"] += out_tok
        if provider_info:
            session.usage["provider"] = str(provider_info.get("name") or provider_info.get("model") or "")
        session.last_used = time.time()
        logger.info(
            "[report_qa] 会话=%s 第%d轮 问题前%d字=%r tokens=%d/%d%s",
            session.session_id,
            session.turns,
            _QA_LOG_QUESTION_CHARS,
            question[:_QA_LOG_QUESTION_CHARS],
            in_tok,
            out_tok,
            "（核对降级）" if degraded else "",
        )
        return {
            "ok": True,
            "session_id": session.session_id,
            "answer_html": final_html,
            "turns": session.turns,
            "remaining_turns": max(0, _QA_MAX_TURNS - session.turns),
            "usage": dict(session.usage),
            "fact_warning": warned,
        }
