# -*- coding: utf-8 -*-
"""报告阅读版式契约（DESIGN.md Typography / Layout）静态断言。

- 字阶 token（--fs-*/--lh-*）在主报告与 What-if 两模板 :root 就位
- 无游离字号字面量（>24px 图标字号豁免）
- 表格数字排版（tabular-nums + 行高档）与正文行长控制（78ch）
- WCAG AA 对比度：动态解析两模板亮/暗色值计算（核心阅读色 ≥4.5）
"""

import json
import re
from pathlib import Path

import pytest

from src.test.unit.report._html_report_fixtures import read_template_text

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]

REPO_ROOT = Path(__file__).resolve().parents[4]
TMPL_DIR = REPO_ROOT / "src/static/tmpl"
REPORT_TMPL = TMPL_DIR / "report_template.html"
WHATIF_TMPL = TMPL_DIR / "whatif_template.html"
PARTIALS = sorted(TMPL_DIR.glob("partials/*.html"))

REQUIRED_FS = [
    "fs-h1",
    "fs-kpi",
    "fs-h2",
    "fs-h3",
    "fs-body",
    "fs-table",
    "fs-table-sm",
    "fs-footnote",
]
REQUIRED_LH = ["lh-tight", "lh-body", "lh-table"]

# 核心阅读色（正文级 ≥4.5；子集断言，不锁总数）
CORE_LIGHT_TEXT = ["text", "text-secondary", "text-tertiary", "text-muted", "text-faint"]
CORE_LIGHT_RISK = ["profit", "loss"]


def _root_block(text: str) -> str:
    m = re.search(r":root\s*\{(.*?)\}", text, re.S)
    assert m, "缺 :root 块"
    return m.group(1)


def _dark_block(text: str) -> str:
    m = re.search(r'\[data-theme="dark"\]\s*\{(.*?)\}', text, re.S)
    assert m, "缺暗色块"
    return m.group(1)


def _hex(block: str, name: str):
    m = re.search(rf"{re.escape(name)}:\s*(#[0-9a-fA-F]{{3,6}})", block)
    return m.group(1) if m else None


def _lum(hexv: str) -> float:
    hexv = hexv.lstrip("#")
    if len(hexv) == 3:
        hexv = "".join(c * 2 for c in hexv)
    r, g, b = (int(hexv[i : i + 2], 16) / 255 for i in (0, 2, 4))

    def f(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = f(r), f(g), f(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


class TestTypeScaleTokens:
    """字阶/行高 token 两模板就位。"""

    @pytest.mark.parametrize("tmpl", ["report_template.html", "whatif_template.html"], ids=["report", "whatif"])
    def test_font_scale_defined(self, tmpl):
        root = _root_block(read_template_text(tmpl))
        missing = [t for t in REQUIRED_FS if f"--{t}:" not in root]
        assert not missing, f"{tmpl} 缺字阶 token: {missing}"

    @pytest.mark.parametrize("tmpl", ["report_template.html", "whatif_template.html"], ids=["report", "whatif"])
    def test_line_height_defined(self, tmpl):
        root = _root_block(read_template_text(tmpl))
        missing = [t for t in REQUIRED_LH if f"--{t}:" not in root]
        assert not missing, f"{tmpl} 缺行高 token: {missing}"


class TestNoStrayFontSizes:
    """文本字号一律走 token（>24px 图标字号豁免）。"""

    def test_template_and_partials_tokenized(self):
        stray = []
        for f in PARTIALS:
            for i, ln in enumerate(read_template_text(f.name, with_partials=False).splitlines(), 1):
                m = re.search(r"font-size:\s*(\d+(?:\.\d+)?)px", ln)
                if m and float(m.group(1)) <= 24:
                    stray.append(f"{f.name}:{i}")
        assert stray == [], f"游离字号字面量: {stray}"


class TestTableNumericTypography:
    """表格数字排版与行高档。"""

    @pytest.mark.parametrize("tmpl", ["report_template.html", "whatif_template.html"], ids=["report", "whatif"])
    def test_tabular_nums(self, tmpl):
        text = read_template_text(tmpl)
        assert "font-variant-numeric: tabular-nums" in text
        table_rule = re.search(r"table \{[^}]+\}", text)
        assert table_rule and "tabular-nums" in table_rule.group(0), "tabular-nums 应在 table 规则上"

    def test_row_line_height_token(self):
        text = read_template_text()
        assert re.search(r"\btd \{[^}]*line-height: var\(--lh-table\)", text)
        assert re.search(r"\bth \{[^}]*line-height: var\(--lh-table\)", text)

    def test_body_line_height_token(self):
        for f in (REPORT_TMPL, WHATIF_TMPL):
            assert "line-height: var(--lh-body);" in read_template_text(f.name)


class TestReadingWidth:
    """宽度密度分治：正文行长受控，宽表/图表保持全宽横滚。"""

    @pytest.mark.parametrize("tmpl", ["report_template.html", "whatif_template.html"], ids=["report", "whatif"])
    def test_prose_max_width(self, tmpl):
        text = read_template_text(tmpl)
        assert ".section p { max-width: 78ch; }" in text


class TestWcagContrast:
    """WCAG AA（正文级 4.5:1）：核心阅读色动态计算。"""

    BGS_LIGHT = ["--bg", "--surface"]

    @pytest.mark.parametrize("tmpl", ["report_template.html", "whatif_template.html"], ids=["report", "whatif"])
    def test_light_text_contrast(self, tmpl):
        root = _root_block(read_template_text(tmpl))
        below = []
        for fg in CORE_LIGHT_TEXT:
            fg_hex = _hex(root, fg)
            assert fg_hex, f"{tmpl.name} 亮色缺 {fg}"
            for bg in self.BGS_LIGHT:
                bg_hex = _hex(root, bg)
                assert bg_hex, f"{tmpl.name} 亮色缺 {bg}"
                r = _ratio(fg_hex, bg_hex)
                if r < 4.5:
                    below.append(f"{fg}({fg_hex}) on {bg}({bg_hex})={r:.2f}")
        assert not below, f"亮色对比度 <4.5: {below}"

    @pytest.mark.parametrize("tmpl", ["report_template.html", "whatif_template.html"], ids=["report", "whatif"])
    def test_light_updown_contrast(self, tmpl):
        """涨跌语义色有定义时须达 AA（两模板有则算）。"""
        root = _root_block(read_template_text(tmpl))
        below = []
        for fg in CORE_LIGHT_RISK:
            fg_hex = _hex(root, fg)
            if not fg_hex:
                continue
            for bg in self.BGS_LIGHT:
                bg_hex = _hex(root, bg)
                if not bg_hex:
                    continue
                r = _ratio(fg_hex, bg_hex)
                if r < 4.5:
                    below.append(f"{fg}({fg_hex}) on {bg}({bg_hex})={r:.2f}")
        assert not below, f"涨跌色对比度 <4.5: {below}"

    @pytest.mark.parametrize("tmpl", ["report_template.html", "whatif_template.html"], ids=["report", "whatif"])
    def test_dark_text_contrast(self, tmpl):
        dark = _dark_block(read_template_text(tmpl))
        below = []
        for fg in CORE_LIGHT_TEXT:
            fg_hex = _hex(dark, fg)
            if not fg_hex:
                continue
            for bg in self.BGS_LIGHT:
                bg_hex = _hex(dark, bg)
                if not bg_hex:
                    continue
                r = _ratio(fg_hex, bg_hex)
                if r < 4.5:
                    below.append(f"dark {fg}({fg_hex}) on {bg}({bg_hex})={r:.2f}")
        assert not below, f"暗色对比度 <4.5: {below}"


class TestSharedStylesheetParity:
    """报告页与调仓页两套样式：公共面必须同源，不得静默漂移。

    样式按关注点拆成 `_base_styles.html`（两页公共面）+ `_report_styles.html` /
    `_whatif_styles.html`（页面专属面）。锁三条：

    ① **单页聚合内选择器唯一**——同一选择器出现两次会互相覆盖，是抽取/合入时的典型事故；
    ② **跨页同名选择器同源**——要么逐字一致（公共面必然如此），要么在差异白名单里；
    ③ **白名单只减不增**——条目须仍真实存在差异，差异消失即须删除。
    """

    #: 两页**有意不同**的选择器 → 理由（新增条目须写明为什么两页必须不同）
    ALLOWED_DIVERGENCE = {
        ":root": "两页 token 集合不同（调仓页无 TOC/图表相关 token）",
        ".back-to-top-link": "调仓页无目录导航，回顶链接定位差异",
        ".chart-export-btn": "报告页按 44px 触控目标，调仓页按导出按钮字号收敛",
        ".section-title": "报告页章节题有 TOC 折叠态留白差异",
        ".summary-card .meta": "报告页 meta 上边距归零（草稿对照表间距契约）",
        '[data-theme="dark"]': "暗色覆盖块按各页 token 集合各自成块",
        "table": "报告页宽表需 width/border-collapse/tabular-nums，调仓页为窄表",
        "td": "报告页加 line-height token（宽表行高契约）",
        "th": "报告页加 line-height token（宽表行高契约）",
    }

    @staticmethod
    def _rules(path: Path) -> dict[str, str]:
        """单文件 `<style>` 内顶层「选择器 → 归一化声明」映射（at-rule 整块跳过）。"""
        text = path.read_text(encoding="utf-8")
        inner = re.search(r"<style>(.*)</style>", text, re.S)
        text = inner.group(1) if inner else text
        masked = re.sub(r"@media[^{]*\{(?:[^{}]|\{[^{}]*\})*\}", lambda m: "\n" * len(m.group(0)), text, flags=re.S)
        out: dict[str, str] = {}
        for m in re.finditer(r"(?P<sel>[^{}\n][^{}]*?)\s*\{(?P<body>[^{}]*)\}", masked, re.S):
            sel = re.sub(r"/\*.*?\*/", "", m.group("sel"), flags=re.S).strip()
            out[sel] = re.sub(r"\s+", " ", m.group("body")).strip()
        return out

    def _page_rules(self) -> tuple[dict[str, str], dict[str, str]]:
        tmpl = Path(__file__).resolve().parents[4] / "src" / "static" / "tmpl" / "partials"
        base = self._rules(tmpl / "_base_styles.html")
        report = {**base, **self._rules(tmpl / "_report_styles.html")}
        whatif = {**base, **self._rules(tmpl / "_whatif_styles.html")}
        return report, whatif

    def test_no_duplicate_selector_within_page(self):
        """单页聚合（公共面 + 页面面）内选择器不得重复——重复即互相覆盖。"""
        tmpl = Path(__file__).resolve().parents[4] / "src" / "static" / "tmpl" / "partials"
        base = self._rules(tmpl / "_base_styles.html")
        for page_file in ("_report_styles.html", "_whatif_styles.html"):
            page = self._rules(tmpl / page_file)
            dup = sorted(set(base) & set(page))
            assert dup == [], f"{page_file} 与公共面重复定义（后者会覆盖前者）: {dup}"

    def test_shared_selectors_are_identical_or_allowlisted(self):
        report, whatif = self._page_rules()
        drift = [
            sel
            for sel in sorted(set(report) & set(whatif))
            if report[sel] != whatif[sel] and sel not in self.ALLOWED_DIVERGENCE
        ]
        assert drift == [], f"两页同名规则实现不一致（确认是否有意，再登记白名单）: {drift}"

    def test_allowlist_has_no_stale_entries(self):
        """白名单条目必须仍然真实存在差异（差异消失即须删除，只减不增）。"""
        report, whatif = self._page_rules()
        stale = [
            sel
            for sel in self.ALLOWED_DIVERGENCE
            if sel not in report or sel not in whatif or report[sel] == whatif[sel]
        ]
        assert stale == [], f"白名单条目已无差异或选择器已消失，应删除: {stale}"


class TestReportCssRulesetBaseline:
    """报告页 CSS 规则集基线（拆样式 partial 时的「视觉无变化」回归网）。

    报告页没有逐字节 golden（章节顺序/序号随配置变化，字节本就不稳），但样式面可以锁成
    「归一化后的（选择器 → 声明）多重集哈希」：单纯搬移规则位置（如抽公共面到
    `_base_styles.html`）不改变哈希，而任何规则的增删改必变——正好是判断「拆样式有没有
    动到视觉」所需的信号。改动样式时须显式复核并更新常量（评审动作，不是自动豁免）。
    """

    #: 归一化「选择器→声明」多重集 sha256（2026-11-05 公共样式抽离批次标定）
    _RULESET_HASH = "9190e9f16ca369b6b72623f698779eb86de7a7e20e5d83948a1b5430df669474"

    def _ruleset_hash(self) -> tuple[str, int, int]:
        import hashlib

        from src.test.unit.report._html_report_fixtures import (
            _REPORT_SECTION_DEFAULT,
            _build_minimal_render_data,
            _render_template,
        )

        order = [dict(s) for s in _REPORT_SECTION_DEFAULT]
        data = _build_minimal_render_data(
            order,
            {s["key"]: s["number"] for s in order},
            {s["key"]: True for s in order},
        )
        soup = _render_template(data)
        css = "\n".join(node.get_text() for node in soup.find_all("style"))
        masked = re.sub(r"@media[^{]*\{(?:[^{}]|\{[^{}]*\})*\}", lambda m: "\n" * len(m.group(0)), css, flags=re.S)
        rules = sorted(
            (
                re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S).strip(),
                re.sub(r"\s+", " ", m.group(2)).strip(),
            )
            for m in re.finditer(r"([^{}\n][^{}]*?)\{([^{}]*)\}", masked, re.S)
        )
        digest = hashlib.sha256(json.dumps(rules, ensure_ascii=False).encode()).hexdigest()
        return digest, len(rules), len(re.findall(r"@media\b", css))

    def test_ruleset_matches_baseline(self):
        digest, count, media = self._ruleset_hash()
        assert count > 0, "渲染产物应含样式规则"
        assert digest == self._RULESET_HASH, (
            f"报告页 CSS 规则集已变化（{count} 条规则 / {media} 个 @media）。"
            "若为有意改动，请复核渲染差异后更新本类 _RULESET_HASH；若只是搬移规则位置，"
            "哈希本不应变化——请确认没有顺带增删规则。"
        )
