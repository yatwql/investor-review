"""Web 生成流程前端接线回归测试（main.js 生成按钮单源复位）。

背景缺陷：run 完成后「生成报告」按钮停在「生成中...」禁用态——pollOnce 完成
分支只移除 aria-busy，未复位文案与禁用态、未回调 updateGenerateBtn()，且上传
文件已随 run 消费但 state.fileId 未清，按钮与单源判定脱节，导致无法再次生成、
不能换报告格式再生成。

修复：完成分支与 resetFlow 共用 restoreGenerateBtn() 单源复位（清已消费
file_id → updateGenerateBtn() → 文案还原 + 重新上传提示；正式-用存量免上传
立即可再生成）。本文件做源结构断言，防两处口径漂移回退。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

MAIN_JS = Path("src/static/web/main.js")

pytestmark = [pytest.mark.unit, pytest.mark.unit_web]


def _main_js() -> str:
    return MAIN_JS.read_text(encoding="utf-8")


def _block(pattern: str, src: str) -> str:
    """取首个匹配块的 body 文本（用于函数体/分支体断言）。"""
    m = re.search(pattern, src, re.S)
    assert m, f"未找到匹配块: {pattern}"
    return m.group(0)


class TestGenerateBtnRestoreAfterRun:
    """生成完成后按钮复位闭环：完成分支 → 复位函数 → 单源判定。"""

    def test_completion_branch_restores_before_load_result(self) -> None:
        """done/failed 完成分支须先复位按钮再加载结果。"""
        body = _block(
            r"data\.status === 'done' \|\| data\.status === 'failed'\)\s*\{[^}]*\}",
            _main_js(),
        )
        assert "restoreGenerateBtn()" in body, "完成分支须调用按钮复位"
        assert "loadResult()" in body, "完成分支须加载结果"
        assert body.index("restoreGenerateBtn()") < body.index("loadResult()"), "先复位后加载结果"

    def test_restore_helper_clears_consumed_state_and_rejudges(self) -> None:
        """复位函数闭环：清 aria-busy、清已消费 file_id、回调单源判定、文案还原。"""
        body = _block(r"function restoreGenerateBtn\(message\)\s*\{.*?\n  \}", _main_js())
        assert "removeAttribute('aria-busy')" in body
        assert "state.fileId = null" in body, "run 已消费上传文件，file_id 必须清空"
        assert "updateGenerateBtn()" in body, "禁用态须回到单源判定"
        assert "textContent = '生成报告'" in body, "文案不得停在「生成中...」"
        assert "重新上传" in body, "试算/正式-上传须提示重新上传"
        assert "isFormalExisting()" in body, "正式-用存量免上传须走可立即再生成分支"

    def test_reset_flow_shares_restore_single_source(self) -> None:
        """resetFlow 与完成分支共用同一复位函数（防两处口径漂移）。"""
        body = _block(r"function resetFlow\(message\)\s*\{.*?\n  \}", _main_js())
        assert "restoreGenerateBtn(message)" in body, "resetFlow 须复用单源复位"


class TestPollUnknownRunTerminal:
    """任务丢失（服务重启）后轮询终态处理：404 不得被当瞬时错误无限重试。"""

    def test_catch_treats_not_found_as_terminal(self) -> None:
        """pollOnce catch 识别 404/NOT_FOUND → 停轮询 + 单源复位 + 结果区落态。"""
        body = _block(r"function pollOnce\(\)\s*\{.*?\n  \}", _main_js())
        catch = _block(r"\.catch\(function \(err\) \{.*?\n      \}\)", body)
        assert "err.httpStatus === 404" in catch, "404 须被识别为任务不存在"
        assert "err.errorCode === 'NOT_FOUND'" in catch, "须同时识别 NOT_FOUND 错误码"
        i_stop = catch.index("stopPolling()")
        i_restore = catch.index("restoreGenerateBtn()")
        i_render = catch.index("renderResultState(2")
        assert i_stop < i_restore < i_render, "终态须先停轮询、再单源复位、最后渲染结果区"
        assert "任务已不存在" in catch, "结果区须给出任务已失效的可操作提示"
        assert "任务已失效" in catch, "进度阶段须落终态文案，不得停在进行中"

    def test_transient_errors_keep_retrying(self) -> None:
        """非终态错误不在 catch 内无条件停轮/落态（瞬时错误仍等下一轮重试）。"""
        body = _block(r"function pollOnce\(\)\s*\{.*?\n  \}", _main_js())
        catch = _block(r"\.catch\(function \(err\) \{.*?\n      \}\)", body)
        if_block = _block(r"if \(err && \(err\.httpStatus === 404.*?\n        \}", catch)
        remainder = catch.replace(if_block, "")
        assert "stopPolling()" not in remainder, "停轮必须限定在任务不存在终态分支内"
        assert "renderResultState(2" not in remainder, "结果区落态必须限定在终态分支内"


class TestPollChannelIntegrity:
    """进度事件通道完整性：在途互斥 + 序号过滤 + 缺口占位（防重复渲染/静默跳号）。"""

    def test_inflight_guard_set_and_cleared_on_all_exits(self) -> None:
        """pollBusy 在发起前置位，成功与 catch 两路都放行（不得卡死轮询）。"""
        body = _block(r"function pollOnce\(\)\s*\{.*?\n  \}", _main_js())
        assert "if (state.pollBusy)" in body, "在途互斥：上一轮未返回时跳过本轮"
        assert "state.pollBusy = true;" in body
        assert body.count("state.pollBusy = false;") >= 2, "成功与异常两路都须复位在途标志"

    def test_events_filtered_by_seq(self) -> None:
        """只回放 seq 大于已读序号的事件（在途重叠/重复响应不重复渲染）。"""
        body = _block(r"function pollOnce\(\)\s*\{.*?\n  \}", _main_js())
        assert "ev.seq > state.lastSeq" in body

    def test_gap_placeholder_from_first_seq(self) -> None:
        """first_seq 大于已读+1 时渲染省略占位（不静默跳号）。"""
        src = _main_js()
        body = _block(r"function pollOnce\(\)\s*\{.*?\n  \}", src)
        assert "data.first_seq" in body, "轮询须读服务端 first_seq 做缺口判定"
        notice = _block(r"function appendGapNotice\(count\)\s*\{.*?\n  \}", src)
        assert "已省略" in notice and "event-gap" in notice

    def test_backend_exposes_oldest_seq_baseline(self) -> None:
        """后端链路：RunState.oldest_seq 存在且 events 载荷携带 first_seq。"""
        runs_src = Path("src/python/web/runs.py").read_text(encoding="utf-8")
        handlers_src = Path("src/python/web/handlers.py").read_text(encoding="utf-8")
        assert "def oldest_seq" in runs_src
        assert "first_seq" in handlers_src


class TestActiveRunResumeOnLoad:
    """断点续轮询：活动 run 落 sessionStorage，加载时重建进度视图续轮询。"""

    def test_run_id_persisted_on_submit(self) -> None:
        """提交成功后写入会话标记（刷新/误关重开可恢复）。"""
        body = _block(
            r"\.then\(handleResponse\)\s*\.then\(function \(data\) \{\s*state\.runId = data\.run_id;.*?\n      \}\)",
            _main_js(),
        )
        assert "saveRunId(data.run_id)" in body

    def test_run_id_cleared_on_reset_and_terminal(self) -> None:
        """流程重置与轮询终态（完成/任务不存在）都清会话标记。"""
        src = _main_js()
        reset_body = _block(r"function resetFlow\(message\)\s*\{.*?\n  \}", src)
        assert "clearRunId()" in reset_body
        poll = _block(r"function pollOnce\(\)\s*\{.*?\n  \}", src)
        assert poll.count("clearRunId()") >= 2, "完成分支与 404 终态分支都须清理"

    def test_resume_rebuilds_progress_and_polls_on_init(self) -> None:
        """init 调用 resumeActiveRun；恢复路径重建进度视图并启动轮询。"""
        src = _main_js()
        assert "var RUN_ID_KEY = 'investor_util_active_run_id'" in src
        init = _block(r"function init\(\)\s*\{.*?\n  \}", src)
        assert "resumeActiveRun();" in init
        resume = _block(r"function resumeActiveRun\(\)\s*\{.*?\n  \}", src)
        assert "startPolling();" in resume and "showProgress();" in resume
