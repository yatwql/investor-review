"""报告追问区块（partials/report_qa_section.html）渲染契约测试。

覆盖阶段 2 验收：关态模板分支守卫（报告字节不变的结构前提）、开态区块表面
（空态/失败态文案 = DESIGN.md Data States 口径、端点与 file:// 降级探测）、
样式 token 纪律（不新增色值）、`report_qa_enabled` 经 render context 传递且
不写模板 globals。
"""

from __future__ import annotations

import os
import re

import pytest

from src.python.report.html_jinja_env import _ENV

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.unit_qa]

_TMPL_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "static", "tmpl"))
_PARTIAL = os.path.join(_TMPL_DIR, "partials", "report_qa_section.html")
_MAIN_TMPL = os.path.join(_TMPL_DIR, "report_template.html")
_HTML_WRITER = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "python", "report", "html_writer.py")
)


def _render_partial(**ctx) -> str:
    """按既有 partial 快照测试惯例直接渲染（无父模板依赖）。"""
    with open(_PARTIAL, encoding="utf-8") as f:
        tpl = _ENV.from_string(f.read())
    return tpl.render(**ctx)


class TestPartialSurface:
    """开态区块表面（结构/空态与失败态文案/端点/降级探测）。"""

    @pytest.fixture(autouse=True)
    def _html(self):
        self.html = _render_partial()

    def test_core_elements_present(self):
        assert 'id="report-qa"' in self.html
        assert "data-qa-input" in self.html
        assert "data-qa-send" in self.html
        assert "data-qa-thread" in self.html
        assert 'maxlength="1000"' in self.html  # 与服务端问题长度上限同源

    def test_empty_and_failure_copy_follow_data_states(self):
        assert "输入问题开始追问" in self.html  # 空态
        assert "服务暂不可用，请稍后重试" in self.html  # 失败态
        assert "正在结合本期报告内容作答…" in self.html  # 进行态
        assert "本轮对话已达上限，刷新页面开始新会话" in self.html  # 上限态（与服务端文案一致）

    def test_same_origin_endpoint_and_file_scheme_fallback(self):
        assert 'fetch("/api/qa/ask"' in self.html
        assert "location.protocol" in self.html and '"file:"' in self.html
        assert "经 Web 工作台打开报告后可使用追问" in self.html

    def test_envelope_contract_consumed(self):
        # 前端按信封分支：ok/data.ok、error_code、remaining_turns、usage 双 token
        assert "body.data.ok" in self.html
        assert "error_code" in self.html
        assert "remaining_turns" in self.html
        assert "input_tokens" in self.html and "output_tokens" in self.html

    def test_answer_note_and_fact_warning_class_rendered_in_thread_css(self):
        # 服务端 qa/session.py 注入的两段附注 class 在区块样式内有落点
        assert ".qa-answer-note" in self.html
        assert ".qa-fact-warning" in self.html


class TestStyleTokenDiscipline:
    """样式遵守 DESIGN.md：颜色走 token，仅保留与既有按钮一致的 #fff 反白。"""

    def test_no_raw_hex_colors_beyond_white_on_primary(self):
        style = re.search(r"<style>(.*?)</style>", _partial_source(), re.S)
        assert style is not None
        hexes = {h.lower() for h in re.findall(r"#[0-9a-fA-F]{3,8}\b", style.group(1))}
        assert hexes <= {"#fff", "#ffffff"}, f"发现 token 之外的色值：{hexes}"

    def test_breakpoint_and_print_handling(self):
        html = _partial_source()
        assert "@media (max-width: 768px)" in html  # 与报告既有断点一致
        assert "@media print" in html and ".qa-block" in html  # 打印隐藏交互块


def _partial_source() -> str:
    """取 partial 源文本（样式断言用）。"""
    with open(_PARTIAL, encoding="utf-8") as f:
        return f.read()


class TestTemplateFlagGuard:
    """主模板：区块 include 必须整体处于 report_qa_enabled 分支内（关态字节不变前提）。"""

    @pytest.fixture(autouse=True)
    def _src(self):
        with open(_MAIN_TMPL, encoding="utf-8") as f:
            self.src = f.read()

    def test_include_is_wrapped_by_flag_branch(self):
        pattern = (
            r"\{%\s*if\s+report_qa_enabled\s*%\}.*?"
            r"\{%\s*include\s+\"partials/report_qa_section\.html\"\s+with\s+context\s*%\}.*?"
            r"\{%\s*endif\s*%\}"
        )
        assert re.search(pattern, self.src, re.S), "追问区块 include 未被 report_qa_enabled 分支完整包裹"

    def test_report_qa_tokens_only_inside_guarded_branch(self):
        guarded = re.search(r"\{%\s*if\s+report_qa_enabled\s*%\}.*?\{%\s*endif\s*%\}", self.src, re.S)
        assert guarded is not None
        start, end = guarded.span()
        outside = self.src[:start] + self.src[end:]
        assert "report_qa" not in outside, "report_qa 相关标记泄漏到开关分支之外（关态将改变产物字节）"

    def test_include_sits_before_footer(self):
        assert self.src.index("report_qa_section.html") < self.src.index("FOOTER")


class TestRenderContextWiring:
    """`report_qa_enabled` 经 render context 传递，不写模板 globals。"""

    def test_flag_not_registered_in_template_globals(self):
        assert "report_qa_enabled" not in _ENV.globals

    def test_html_writer_computes_and_passes_flag_as_render_kwarg(self):
        with open(_HTML_WRITER, encoding="utf-8") as f:
            src = f.read()
        assert 'is_feature_enabled("report_qa")' in src
        assert "report_qa_enabled=report_qa_enabled" in src

    def test_flag_defaults_off(self):
        """注册表默认值必须为关（实验组纪律：默认关、开态才改产物）。"""
        from src.python.config.features import feature_switch_registry, is_feature_enabled

        assert feature_switch_registry["report_qa"].default is False
        assert is_feature_enabled("report_qa") is False
