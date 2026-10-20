"""测试：check-style-guardrails.py — 设计护栏机检（DESIGN.md 护栏样式面）。

覆盖：
  - E1 强调色越权：品牌蓝字面量命中 / token 定义行与 JS fallback 串豁免 / 注释豁免
    / 品牌蓝集从 :root 强调系 token 动态提取（注入合成定义即生效）
  - E2 明暗同步：dark 覆盖变量根缺命中 / 根齐通过
  - E3 双面 token 对表：表共名缺定义命中 / 两面同名颜色变量未登记命中 / 一致通过
  - W1/W2 观察语义：裸色值与圆角档外**不进 findings**（只进 observations）
  - W3 内联色值：HTML 引号内（非 script 域）色值独立观察——W1 引号整行豁免为 JS
    图表配置设计，内联 style 盲区由本项找回；css 文件与 script 域不归 W3
  - W4/W5 档外字号/间距：字面值不在契约档位集才观察，var()/token/图标 ≥24px 不判
  - W1 豁免域：HTML 实体误报排除 / 引号区间行（JS 配置与内联 style，含跨行）/
    var() 回退值 / @media print 块 / 暗色 override 块 / 存量白名单命中与腐化检测
  - 收敛基线：真实仓库观察数只减不增（样式收敛批次基线机制化）
  - 真实仓库冒烟：E 级零 finding + observations 键齐备 + --ci 退出 0（结构断言）
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from src.test._script_loader import load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
    pytest.mark.usefixtures("offline_external_sources"),
]

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"


@pytest.fixture(scope="module")
def guard():
    return load_script("check-style-guardrails.py")


_MINIMAL_DESIGN = """## Colors — 语义角色表

| 角色族 | 角色 | 报告侧实现 | 工作台侧实现 | 备注 |
|---|---|---|---|---|
| 强调 | 品牌蓝 | `--primary` | `--primary` | 单强调色 |

## Typography — 字阶表
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


class TestEmphasisColor:
    """E1 强调色越权（护栏 3）。"""

    def test_brand_hex_outside_definition_is_finding(self, guard, tmp_path):
        f = _write(tmp_path, "a.html", ":root { --primary: #2E75B6; }\n.btn { background: #2E75B6; }\n")
        findings, _ = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert any("强调色越权" in x for x in findings)

    def test_definition_js_comment_exempt(self, guard, tmp_path):
        f = _write(
            tmp_path,
            "b.html",
            ":root { --primary: #2E75B6; }\n"
            "/* .x { color: #2E75B6 } */\n"
            "const c = '#2E75B6';\n"
            ".y { color: var(--primary); }\n",
        )
        findings, _ = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert not any("强调色越权" in x for x in findings)

    def test_brand_set_derived_from_root_token(self, guard, tmp_path):
        """品牌集动态提取：:root 里新强调 token 的 hex 立即进白名单检查域。"""
        f = _write(tmp_path, "c.html", ":root { --primary: #123456; }\n.z { outline: #123456; }\n")
        findings, _ = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert any("#123456" in x for x in findings)


class TestDarkSync:
    """E2 明暗同步（护栏 5）。"""

    def test_dark_var_missing_root_is_finding(self, guard, tmp_path):
        f = _write(tmp_path, "d.html", ':root { --ok: #0a0; }\n[data-theme="dark"] { --ghost: #fff; }\n')
        findings, _ = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert any("--ghost" in x and "缺定义" in x for x in findings)

    def test_dark_vars_present_in_root_pass(self, guard, tmp_path):
        f = _write(tmp_path, "e.html", ':root { --ok: #0a0; }\n[data-theme="dark"] { --ok: #6b6; }\n')
        findings, _ = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert not any("缺定义" in x for x in findings)


class TestTokenAlignment:
    """E3 双面 token 对表（Colors「同名对齐」段）。"""

    def test_table_shared_token_missing_on_side_is_finding(self, guard, tmp_path):
        design = _MINIMAL_DESIGN  # 表共名 --primary
        rep = _write(tmp_path, "report_template.html", ":root { --primary: #2E75B6; }\n")
        web = _write(tmp_path, "style.css", ":root { --accent: #0f0; }\n")
        findings, _ = guard.run_checks(files=[rep, web], design_text=design)
        assert any("--primary" in x and "共名" in x for x in findings)

    def test_shared_color_not_registered_in_table_is_finding(self, guard, tmp_path):
        """两面同名颜色变量（表外新 token）→ 未登记命中。"""
        rep = _write(tmp_path, "report_template.html", ":root { --brand-new: #123456; }\n")
        web = _write(tmp_path, "style.css", ":root { --brand-new: #654321; }\n")
        findings, _ = guard.run_checks(files=[rep, web], design_text=_MINIMAL_DESIGN)
        assert any("--brand-new" in x and "未在 Colors 表登记" in x for x in findings)

    def test_aligned_pair_passes(self, guard, tmp_path):
        rep = _write(tmp_path, "report_template.html", ":root { --primary: #2E75B6; }\n")
        web = _write(tmp_path, "style.css", ":root { --primary: #1f6fb2; }\n")
        findings, _ = guard.run_checks(files=[rep, web], design_text=_MINIMAL_DESIGN)
        assert findings == []


class TestObservations:
    """W 级观察语义：统计但不判 finding。"""

    def test_raw_color_only_observed(self, guard, tmp_path):
        f = _write(tmp_path, "f.html", ":root { --ok: #0a0; }\n.a { box-shadow: 0 1px 2px rgba(0,0,0,0.1); }\n")
        findings, obs = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert findings == []
        assert obs["raw_colors"], "裸色值应进观察统计"

    def test_out_of_tier_radius_only_observed(self, guard, tmp_path):
        f = _write(tmp_path, "g.html", ":root { --ok: #0a0; }\n.b { border-radius: 3px; }\n")
        findings, obs = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert findings == []
        assert any("3px" in x for x in obs["radius"]), "档外圆角应进观察统计"

    def test_tier_radius_not_observed(self, guard, tmp_path):
        f = _write(
            tmp_path,
            "h.html",
            ':root { --ok: #0a0; }\n.c { border-radius: 8px; }\n[data-theme="dark"] { --ok: #0a0; }\n',
        )
        _, obs = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert not any("8px" in x for x in obs["radius"])


class TestRealRepoSmoke:
    """真实仓库冒烟：E 级零 finding（观察期口径）+ CLI 退出 0。"""

    def test_e_level_clean(self, guard):
        findings, obs = guard.run_checks()
        assert findings == [], f"E 级应零 finding: {findings[:3]}"
        assert set(obs) == {"raw_colors", "radius", "inline_colors", "type_scale", "spacing_scale"}

    def test_radius_tiers_match_design(self, guard):
        """圆角档位与 DESIGN.md Layout「圆角档」同源（4/6/8 明文 + 999 药丸）。"""
        design = (_REPO_ROOT / "docs" / "managements" / "DESIGN.md").read_text(encoding="utf-8")
        for tier in ("4px", "6px", "8px"):
            assert tier in design, f"DESIGN Layout 应含圆角档 {tier}"
        assert guard.RADIUS_TIERS >= {4, 6, 8, 999}

    def test_ci_exit_zero(self):
        proc = subprocess.run(
            [sys.executable, str(_SCRIPTS_DIR / "check-style-guardrails.py"), "--ci"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        assert proc.returncode == 0, f"--ci 应退出 0（观察期 E 级零 finding）: {proc.stdout}{proc.stderr}"


class TestW1Exemptions:
    """W1 豁免域（引号行/var 回退/print/暗色块/白名单）与 HTML 实体误报修复。"""

    def test_html_entity_not_observed(self, guard, tmp_path):
        """HTML 数字实体（&#9888; ⚠ / &#10003; ✓ / &#8505; ⓘ）不得计为裸色值。"""
        f = _write(
            tmp_path,
            "ent.html",
            ":root { --ok: #0a0; }\n<span>&#9888; &#10003; &#8505; &#9675;</span>\n",
        )
        _, obs = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert obs["raw_colors"] == []

    def test_quoted_line_exempt(self, guard, tmp_path):
        """引号区间覆盖行豁免（JS 配置串 / HTML 内联 style 属性，含跨行续行）。"""
        f = _write(
            tmp_path,
            "q.html",
            ":root { --ok: #0a0; }\n"
            "const cfg = { bg: 'rgba(46,117,182,0.1)', fg: '#fff' };\n"
            '<td style="background-color: #FF4444; color: white;">x</td>\n'
            '<td style="background-color: #FF8C00;\n'
            '  color: white;">y</td>\n'
            ".outside { color: #abc; }\n",
        )
        _, obs = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert len(obs["raw_colors"]) == 1 and "#abc" in obs["raw_colors"][0], "引号行豁免后仅引号外裸值应保留"

    def test_var_fallback_exempt(self, guard, tmp_path):
        """var(--x, <fallback>) 回退值豁免（token 缺失防御，非裸值声明）。"""
        f = _write(
            tmp_path,
            "v.html",
            ":root { --ok: #0a0; }\n.a { color: var(--chart-text, #888); }\n.b { border: 1px solid var(--border-color, rgba(128,128,128,0.25)); }\n",
        )
        _, obs = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert obs["raw_colors"] == []

    def test_print_media_exempt(self, guard, tmp_path):
        """@media print 块豁免（打印恒定黑白域），块外裸值仍观察。"""
        f = _write(
            tmp_path,
            "p.html",
            ":root { --ok: #0a0; }\n"
            "@media print {\n  body { background: #fff; color: #000; }\n}\n"
            ".d { color: #abc; }\n",
        )
        _, obs = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert len(obs["raw_colors"]) == 1 and "#abc" in obs["raw_colors"][0]

    def test_dark_override_block_exempt(self, guard, tmp_path):
        """暗色 override 块豁免（契约「双主题 override 块除外」），块外裸值仍观察。"""
        f = _write(
            tmp_path,
            "dk.html",
            ':root { --ok: #0a0; }\n[data-theme="dark"] .upload {\n  background: #1a1a1a;\n}\n.x { color: #abc; }\n',
        )
        _, obs = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert len(obs["raw_colors"]) == 1 and "#abc" in obs["raw_colors"][0]

    def test_whitelist_exemption_and_stale_detection(self, guard, tmp_path, monkeypatch):
        """存量白名单命中跳过；未命中现行行 → 腐化警告点名（只减不增纪律）。"""
        f = _write(tmp_path, "w.html", ":root { --ok: #0a0; }\n.t { color: #123abc; }\n")
        rel_path = guard.rel(f)
        monkeypatch.setattr(
            guard,
            "_RAW_COLOR_EXEMPTIONS",
            ((rel_path, r"#123abc", "测试豁免"), (rel_path, r"#deadbe", "注定腐化")),
        )
        _, obs = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert obs["raw_colors"] == [], "白名单命中的行不应进观察"
        stale = guard._stale_exemptions([f])
        assert len(stale) == 1 and "#deadbe" in stale[0]


class TestInlineColors:
    """W3 内联/属性色值：HTML 引号内非 script 域色值进观察，W1 归零口径不受影响。"""

    def test_inline_style_hex_observed(self, guard, tmp_path):
        f = _write(tmp_path, "i.html", '<td style="color: #888;">x</td>\n')
        findings, obs = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert len(obs["inline_colors"]) == 1, "内联 style 色值应进 W3"
        assert obs["raw_colors"] == [], "W1 引号豁免口径保持不变"

    def test_inline_style_hex_is_finding(self, guard, tmp_path):
        """W3 收口后内联 style 色值同时进 E 级 findings（不再是纯观察项）。"""
        f = _write(tmp_path, "i2.html", '<td style="color: #888;">x</td>\n')
        findings, _ = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert any("内联 style 色值" in item for item in findings), "内联色值应升为 E 级 finding"

    def test_script_region_not_inline(self, guard, tmp_path):
        """<script> 域 JS 字符串色值属绘制/图表配置域，不归 W3。"""
        f = _write(tmp_path, "s.html", "<script>\nvar c = '#abc123';\n</script>\n")
        _, obs = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert obs["inline_colors"] == []

    def test_css_file_not_inline_domain(self, guard, tmp_path):
        f = _write(tmp_path, "x.css", ".a { color: #888; }\n")
        _, obs = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert obs["inline_colors"] == [] and len(obs["raw_colors"]) == 1


class TestScaleObservations:
    """W4 档外字号 / W5 档外间距：只判字面量，var()/档位值/图标字号不判。"""

    def test_out_of_tier_font_and_margin_observed(self, guard, tmp_path):
        f = _write(tmp_path, "o.css", ".a { font-size: 15px; margin: 10px 0; }\n")
        _, obs = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert any("font-size 15px" in x for x in obs["type_scale"])
        assert any("间距 10px" in x for x in obs["spacing_scale"])

    def test_tier_and_token_values_not_observed(self, guard, tmp_path):
        f = _write(
            tmp_path,
            "t.css",
            ".a { font-size: var(--fs-body); margin: 8px 12px; }\n.b { font-size: 28px; }\n",
        )
        _, obs = guard.run_checks(files=[f], design_text=_MINIMAL_DESIGN)
        assert obs["type_scale"] == [] and obs["spacing_scale"] == []


class TestBaselineNoGrowth:
    """样式收敛批次基线：真实仓库观察数只减不增（管控机制化，非演进总数断言）。"""

    #: 2026-10-13 样式收敛批次后的治理基线——只允许沿收敛路径下降，不得回升
    _W1_BASELINE = 0
    _W2_BASELINE = 0
    #: W3/W4/W5 为设计契约审计批次（2026-10-17）新增观察维度——按实测存量登记，
    #: 同样只减不增（新增内联色值/档外字号间距必须走 token 或先入契约登记）
    _W3_BASELINE = 40
    _W4_BASELINE = 8
    _W5_BASELINE = 175

    def test_observed_counts_within_baseline(self, guard):
        """新增裸色值/档外圆角必须走 token 或复审白名单，否则本断言红。"""
        _, obs = guard.run_checks()
        assert len(obs["raw_colors"]) <= self._W1_BASELINE
        assert len(obs["radius"]) <= self._W2_BASELINE
        assert len(obs["inline_colors"]) <= self._W3_BASELINE
        assert len(obs["type_scale"]) <= self._W4_BASELINE
        assert len(obs["spacing_scale"]) <= self._W5_BASELINE
