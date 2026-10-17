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
