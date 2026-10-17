#!/usr/bin/env python3
"""设计护栏机检（DESIGN.md「Do's and Don'ts — 护栏」样式面的机器化检查）。

规则与 DESIGN.md 护栏条目**逐条同源**（各函数 docstring 标注映射编号）：

  E1 强调色越权（护栏 3）   品牌蓝系 **hex 字面量**（小写归一）出现在非 token 定义行 / 非 JS 字符串
                             → finding；rgb/rgba 透明变体不入 E1（柔和底色实践归 W1 观察）
  E2 明暗同步（护栏 5）      ``[data-theme="dark"]`` 覆盖的变量在 ``:root`` 缺定义 → finding
  E3 双面 token 对表（Colors「同名对齐」段）
                             正向：DESIGN Colors 表两面同列具名 token，双面 ``:root`` 均须定义
                             反向：实现中「值为颜色」的两面同名变量，须在 Colors 表登记
  W1 裸色值存量（护栏 1）    非定义行出现 hex/rgb 字面量（**观察项**，统计不判 finding）
  W2 圆角档位（护栏 2）      ``border-radius`` 档外字面值（**观察项**，统计不判 finding）

**观察期口径**（样式护栏先例，2026-10-08 立；2026-10-13 样式收敛批次修订）：
W 级仅统计与 ``-v`` 明细供分诊，**不判 finding**、不入 pre-commit 钩子域与 CI guards；
**发布门禁域**（release.py ``gate`` 步）已纳入——E 级 finding 拦截、W 级观察统计随发布
留档；开发期快反馈由 unit 测试（真实仓库冒烟 + 观察数基线断言）承担。
检查域：两份报告模板 + partials + Web 工作台样式表。

**W1 豁免域**（与契约护栏 1 的例外文字逐条同源；豁免命中不计入观察统计）：

  1. 引号区间覆盖行——JS 图表配置串 / HTML 内联 style 属性所在行整行豁免（契约「Chart\n     配置域除外」同源；含跨行 style 属性与多行 JS 串拼接）
  2. ``var(--x, <fallback>)`` 回退值——token 缺失防御，非裸值声明
  3. ``@media print`` 块——打印恒定黑白域（双主题契约不覆盖打印态）
  4. 暗色 override 块（``[data-theme="dark"]`` / ``.dark`` 选择器域）——契约「双主题
     override 块除外」同源；判断为「最近选择器行」近似口径，多行选择器可能漏豁免
  5. ``_RAW_COLOR_EXEMPTIONS`` 存量白名单——按（文件, 行内容正则, 理由）登记，仅兜契约钦定值
     与恒定/派生域，不兜可收敛存量

**流程管控**（样式收敛批次定档，防观察面演化失控）：

  1. **运行域定档**：unit 测试快反馈（E 级 + 观察数基线断言）+ 发布门禁
     （release.py gate：E 级拦 / W 级统计留档）；纳入 pre-commit/CI guards 阻塞域
     必须另行独立决策，不得随本脚本改动顺带发生
  2. **白名单只减不增**：新增豁免须带理由并复审；未命中任何现行行的白名单条目会被
     ``-v`` 腐化警告点名，应及时删除
  3. **收敛优先于豁免**：能等值收敛到 token 的一律收敛，白名单只兜契约钦定值与
     恒定/派生域

**W1 口径说明**：HTML 数字实体（``&#9888;`` ⚠ / ``&#10003;`` ✓ 等）不属于色值——
hex 正则以 ``(?<!&)`` 前置断言排除实体形态；观察数口径以样式收敛批次
（2026-10-13）为基线。

用法：
  python scripts/check-style-guardrails.py           # 检查全部
  python scripts/check-style-guardrails.py -v        # 详细输出（含 W 级观察清单）
  python scripts/check-style-guardrails.py --ci      # CI 模式（只输出 文件:描述）

退出码：
  0 — 全部通过（无 E 级 finding；W 级观察项不判 finding）
  2 — 发现 E 级 finding（强调色越权 / 明暗同步缺失 / 双面 token 对表不一致）
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _checklib import REPO_ROOT, add_common_args, rel, report  # noqa: E402

#: 样式检查域（仓库相对路径）
STYLE_DOMAIN = (
    "src/static/tmpl/report_template.html",
    "src/static/tmpl/whatif_template.html",
    "src/static/tmpl/partials",
    "src/static/web/style.css",
)

#: 圆角档位（DESIGN.md Layout「圆角档」+ 药丸/全圆钮 999px；字面 px 值白名单）
RADIUS_TIERS = frozenset({4, 6, 8, 999})

#: 字阶档位（DESIGN.md Typography 字阶表；图标 >24px 豁免；rem 按根 16px 折算）
FONT_TIERS = frozenset({11, 12, 13, 14, 16, 17, 18, 20, 22})

#: 间距档位（DESIGN.md Layout 间距阶；0 为显式清零合法）
SPACING_TIERS = frozenset({0, 4, 8, 12, 16, 24, 32})

_FONT_SIZE = re.compile(r"font-size:\s*(\d+(?:\.\d+)?)(px|rem)")
_SPACING_DECL = re.compile(r"(?:padding|margin|gap|row-gap|column-gap)(?:-(?:top|right|bottom|left))?\s*:\s*([^;}]+)")
_SPACING_PX = re.compile(r"(-?[\d.]+)px\b")

#: DESIGN.md 文件（Colors / Layout 真值来源）
DESIGN_DOC = "docs/managements/DESIGN.md"

_COMMENT_PREFIXES = ("/*", "*", "//", "<!--", "#")
_TOKEN_DEF = re.compile(r"--[\w-]+\s*:")  # 行内任意位置的变量定义形态（含单行 :root {...}）
_HEX = re.compile(r"(?<!&)#[0-9a-fA-F]{3,8}\b")  # (?<!&)：排除 HTML 数字实体（&#9888; 等）误报
_JS_STRING_HEX = re.compile(r"""['"]#[0-9a-fA-F]{3,8}['"]""")
_RGB = re.compile(r"\b(?:rgba?|hsla?)\(")
_RADIUS_PX = re.compile(r"border-radius:\s*(\d+(?:\.\d+)?px)")

#: W1 存量白名单：(文件相对路径, 行内容正则, 理由)——只减不增，新增须带理由并复审
_RAW_COLOR_EXEMPTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "src/static/tmpl/report_template.html",
        r"rgba\(0,\s*0,\s*0",
        "黑色透明阴影/渐变纱——Elevation 契约钦定值及其派生（rest 阴影 0.1 / 侧栏纱 0.06 等），非语义色 token 域",
    ),
    (
        "src/static/tmpl/whatif_template.html",
        r"rgba\(0,\s*0,\s*0",
        "同上（whatif 模板阴影阶沿用报告侧 Elevation 值）",
    ),
    (
        "src/static/tmpl/partials/report_qa_section.html",
        r"rgba\(0,\s*0,\s*0",
        "同上（QA 分区卡片阴影沿用报告侧 Elevation 值）",
    ),
    (
        "src/static/tmpl/report_template.html",
        r"rgba\(255,255,255,0\.",
        "主色底白纱派生面（--primary 之上的半透明白，常态/hover）——契约明文品牌蓝暗色保持原值、蓝底白字，无对应 token 角色",
    ),
    (
        "src/static/tmpl/report_template.html",
        r"rgba\(46,117,182,0\.",
        "品牌蓝透明度派生面（TOC 分组 hover 底），无对应 token 角色",
    ),
    (
        "src/static/web/style.css",
        r"rgba\(31, ?111, ?1(?:76|78)|rgba\(31, ?35, ?40",
        "web 侧 primary/text 透明度派生面（tab hover、日志 summary hover、代码底纱），无透明度 token 族",
    ),
    (
        "src/static/web/style.css",
        r"#fafbfc",
        "上传/提交区灰底（含渐变端点）——双端定制灰阶，单 token 无法表达渐变与该档灰",
    ),
    (
        "src/static/web/style.css",
        r"rgba\(240, ?173, ?78",
        "警告徽章琥珀透明派生（底/边），web 侧无透明度 token 族",
    ),
    (
        "src/static/web/style.css",
        r"#fff0f0|#b02a37",
        "红底警示条（.formal-warning）error 透明派生面与对比红字，web 侧无 error 透明派生 token",
    ),
    (
        "src/static/tmpl/report_template.html",
        r"color: #fff",
        "主色底白字（报告头/章节题/折叠钮/按钮）——契约明文品牌蓝暗色保持原值、蓝底白字恒成立；token 化需新增 --on-primary 双面角色，值恒等无增益",
    ),
    (
        "src/static/tmpl/whatif_template.html",
        r"color: #fff",
        "同上（whatif 模板主色底白字）",
    ),
    (
        "src/static/tmpl/partials/report_qa_section.html",
        r"color: #fff",
        "同上（QA 发送按钮主色底白字）",
    ),
    (
        "src/static/web/style.css",
        r"color: #fff",
        "主色按钮/选中 tab 白字——同契约理由（品牌蓝暗色保持原值、蓝底白字）",
    ),
    (
        "src/static/web/style.css",
        r"#f0f6ff|#e8f1fb",
        "上传区 primary 派生交互面（hover/focus/drag-over 底），无对应 token 角色",
    ),
    (
        "src/static/web/style.css",
        r"background: #e7e9ec",
        "进度条轨道派生灰（--border 不等值），无对应 token 角色",
    ),
)


def _quoted_lines(text: str) -> set[int]:
    """引号区间覆盖的行号集合（JS 图表配置串 / HTML 内联 style 属性，整行豁免）。

    跨行 ``style="...{% if %}...{% endif %}"`` 与多行 JS 串拼接均被覆盖；
    口径为「引号内色值所在行整行豁免」——同行引号外的孤立声明极少出现且多为混合域。
    """
    out: set[int] = set()
    quote: str | None = None
    line_no = 1
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\n":
            line_no += 1
        elif quote is None and ch in ("'", '"'):
            quote = ch
        elif quote is not None:
            if ch == "\\":
                i += 1  # 转义跳过下一字符
            elif ch == quote:
                quote = None
            else:
                out.add(line_no)
        i += 1
    return out


def _in_var_fallback(code: str, pos: int) -> bool:
    """``pos`` 是否落在 ``var(--x, <fallback>)`` 的回退值区间（token 缺失防御）。"""
    for m in re.finditer(r"var\(\s*--[\w-]+\s*,", code):
        close = code.find(")", m.end())
        end = close if close != -1 else len(code)
        if m.end() <= pos < end:
            return True
    return False


def _script_block_lines(text: str) -> set[int]:
    """``<script>`` 区域行号集（JS 字符串色值属图表配置/绘制域，不归 W3 内联属性）。"""
    out: set[int] = set()
    inside = False
    for i, raw in enumerate(text.splitlines(), 1):
        if "<script" in raw:
            inside = True
        if inside:
            out.add(i)
        if "</script>" in raw:
            inside = False
    return out


def _quoted_positions(text: str) -> set[tuple[int, int]]:
    """引号内字符的 (行, 列) 集合；状态机与 ``_quoted_lines`` 同构（转义处理一致）。"""
    out: set[tuple[int, int]] = set()
    quote: str | None = None
    line_no = 1
    col = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\n":
            line_no += 1
            col = 0
        elif quote is None and ch in ("'", '"'):
            quote = ch
        elif quote is not None:
            if ch == "\\":
                i += 1
                col += 2
                continue
            elif ch == quote:
                quote = None
            else:
                out.add((line_no, col))
        col += 1
        i += 1
    return out


def _scoped_block_lines(text: str, selector_re: str) -> set[int]:
    """选择器域块覆盖的行号集合（近似口径：depth==0 累积选择器行直到 ``{``）。"""
    out: set[int] = set()
    pending = ""
    depth = 0
    inside = False
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if depth == 0 and line:
            pending = f"{pending} {line}".strip() if not pending else f"{pending} {line}"
        if depth == 0 and "{" in line:
            inside = bool(re.search(selector_re, pending))
            pending = ""
        if inside:
            out.add(i)
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            depth = 0
            inside = False
    return out


def _media_print_lines(text: str) -> set[int]:
    """``@media print`` 块覆盖的行号集合（打印恒定黑白域，W1 豁免）。"""
    return _scoped_block_lines(text, r"@media\s+print")


def _dark_override_lines(text: str) -> set[int]:
    """暗色 override 块覆盖的行号集合（契约「双主题 override 块除外」同源）。"""
    return _scoped_block_lines(text, r'(\.dark\b|\[data-theme=["\']dark["\'])')


def _w1_exempt(rel_path: str, line: str) -> str | None:
    """存量白名单命中判定，返回豁免理由（未命中返回 None）。"""
    for path_pat, line_pat, reason in _RAW_COLOR_EXEMPTIONS:
        if rel_path == path_pat and re.search(line_pat, line):
            return reason
    return None


def _stale_exemptions(targets: list[Path]) -> list[str]:
    """白名单腐化检查：条目未命中任何现行行 → 应删除（白名单只减不增）。"""
    stale: list[str] = []
    for path_pat, line_pat, _reason in _RAW_COLOR_EXEMPTIONS:
        hit = False
        for path in targets:
            if rel(path) != path_pat:
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if re.search(line_pat, line):
                    hit = True
                    break
            if hit:
                break
        if not hit:
            stale.append(f"{path_pat}: /{line_pat}/ 未命中任何现行行（白名单腐化，条目应删除）")
    return stale


def _is_comment(line: str) -> bool:
    return line.lstrip().startswith(_COMMENT_PREFIXES)


def _root_block(css: str) -> str:
    m = re.search(r":root\s*\{([^}]*)\}", css, re.S)
    return m.group(1) if m else ""


def _root_vars(css: str) -> dict[str, str]:
    """``:root`` 变量名 → 原始值。"""
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", _root_block(css)))


def _dark_vars(css: str) -> set[str]:
    out: set[str] = set()
    for blk in re.findall(r"""\[data-theme=['"]dark['"]\]\s*\{([^}]*)\}""", css, re.S):
        out |= set(re.findall(r"(--[\w-]+)\s*:", blk))
    return out


def _design_table_shared(design_text: str) -> set[str]:
    """DESIGN.md Colors 表中「报告侧」与「工作台侧」两列**同现**的具名 token。

    支持组合书写：``--primary``(-hover) 展开为附加名；反引号单 token 直取；
    通配（``--warn-*``）与破折号占位不参与对表。
    """
    try:
        sec = design_text.split("## Colors — 语义角色表")[1].split("## Typography")[0]
    except IndexError:
        return set()

    def toks(cell: str) -> set[str]:
        out = set(re.findall(r"`(--[\w-]+)`", cell))
        out |= {base + suf for base, suf in re.findall(r"`(--[\w-]+)`\((-\w+)\)", cell)}
        return out

    rep, web = set(), set()
    for line in sec.splitlines():
        if line.startswith("|") and "---" not in line and "角色族" not in line:
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 4:
                rep |= toks(cols[2])
                web |= toks(cols[3])
    return rep & web


def _table_all_tokens(design_text: str) -> set[str]:
    """Colors 表两列出现过的全部具名 token（正反向对表的登记集）。"""
    try:
        sec = design_text.split("## Colors — 语义角色表")[1].split("## Typography")[0]
    except IndexError:
        return set()
    out: set[str] = set()
    for line in sec.splitlines():
        if line.startswith("|") and "---" not in line and "角色族" not in line:
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 4:
                out |= set(re.findall(r"`(--[\w-]+)`", cols[2] + " " + cols[3]))
                out |= {a + b for a, b in re.findall(r"`(--[\w-]+)`\((-\w+)\)", cols[2] + " " + cols[3])}
    return out


def _brand_hexes(paths: list[Path]) -> set[str]:
    """品牌蓝系 hex 集合——从检查域各 ``:root`` 的强调系 token 动态提取（真值=实现定义）。"""
    brand: set[str] = set()
    for path in paths:
        if not path.is_file():
            continue
        css = path.read_text(encoding="utf-8")
        for name, val in _root_vars(css).items():
            if name in ("--primary", "--primary-hover", "--focus", "--accent"):
                brand |= {h.lower() for h in _HEX.findall(val)}
    return brand


def check_emphasis_color(path: Path, brand: set[str]) -> list[str]:
    """E1 强调色越权（护栏 3）：品牌蓝字面量只许出现在 token 定义行与 JS fallback 串。"""
    findings: list[str] = []
    text = path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if _is_comment(line) or _TOKEN_DEF.search(line):
            continue
        if _JS_STRING_HEX.search(line):
            continue
        for hit in {h.lower() for h in _HEX.findall(line)} & brand:
            findings.append(f"{rel(path)}:{i}: 强调色越权：品牌蓝 {hit} 应改用 var(--primary) 系 token")
    return findings


def check_dark_sync(path: Path) -> list[str]:
    """E2 明暗同步（护栏 5）：dark 覆盖变量必须在 ``:root`` 有定义（亮色为源）。"""
    text = path.read_text(encoding="utf-8")
    root = set(_root_vars(text))
    return [
        f"{rel(path)}: dark 覆盖变量 {name} 在 :root 缺定义（明暗不同步）" for name in sorted(_dark_vars(text) - root)
    ]


def check_token_alignment(report_css: str, web_css: str, design_text: str) -> list[str]:
    """E3 双面 token 对表（Colors「同名对齐」段）：表 ↔ 实现双向。"""
    findings: list[str] = []
    rep, web = _root_vars(report_css), _root_vars(web_css)
    shared_in_table = _design_table_shared(design_text)
    for name in sorted(shared_in_table):
        if name not in rep or name not in web:
            findings.append(
                f"{DESIGN_DOC}: Colors 表共名 token {name} 双面定义缺失"
                f"（报告 {'有' if name in rep else '无'} / 工作台 {'有' if name in web else '无'}）"
            )
    registered = _table_all_tokens(design_text)
    shared_colors = {
        n
        for n in set(rep) & set(web)
        if n in rep and ("#" in rep[n] or "rgb" in rep[n]) and ("#" in web[n] or "rgb" in web[n])
    }
    for name in sorted(shared_colors - registered):
        findings.append(f"{DESIGN_DOC}: 两面同名颜色变量 {name} 未在 Colors 表登记（实现先于契约）")
    return findings


def observe_raw_colors(path: Path) -> list[str]:
    """W1 裸色值存量（护栏 1，观察）：豁免域（引号内/var 回退/print/暗色块/白名单）之外的 hex/rgb 字面。"""
    details: list[str] = []
    text = path.read_text(encoding="utf-8")
    rel_path = rel(path)
    print_lines = _media_print_lines(text)
    dark_lines = _dark_override_lines(text)
    quoted = _quoted_lines(text)
    for i, line in enumerate(text.splitlines(), 1):
        if _is_comment(line) or _TOKEN_DEF.search(line):
            continue
        if i in print_lines or i in dark_lines or i in quoted:
            continue
        exempt = _w1_exempt(rel_path, line)
        if exempt is not None:
            continue
        for m in _HEX.finditer(line):
            if not _in_var_fallback(line, m.start()):
                details.append(f"{rel_path}:{i}: {line.strip()[:96]}")
                break
        else:
            for m in _RGB.finditer(line):
                if not _in_var_fallback(line, m.start()):
                    details.append(f"{rel_path}:{i}: {line.strip()[:96]}")
                    break
    return details


def observe_radius(path: Path) -> list[str]:
    """W2 圆角档位（护栏 2，观察）：字面 px 圆角不在档位集内。"""
    details: list[str] = []
    text = path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        for raw in _RADIUS_PX.findall(line):
            if int(float(raw[:-2])) not in RADIUS_TIERS:
                details.append(f"{rel(path)}:{i}: border-radius {raw} 档外（档位 {sorted(RADIUS_TIERS)}）")
    return details


def observe_inline_colors(path: Path) -> list[str]:
    """W3 内联/属性色值（护栏 1，观察）：W1 的引号整行豁免为 JS 图表配置设计，
    HTML 内联 ``style=``/旧式色值属性被同域连带豁免形成盲区——本项按 (行,列) 位置
    级判定把引号内非 script 域的色值找回，独立口径不并入 W1 归零基线。"""
    if path.suffix.lower() != ".html":
        return []
    text = path.read_text(encoding="utf-8")
    quoted = _quoted_positions(text)
    script = _script_block_lines(text)
    details: list[str] = []
    for i, line in enumerate(text.splitlines(), 1):
        if i in script or _is_comment(line):
            continue
        for m in _HEX.finditer(line):
            if (i, m.start()) in quoted:
                details.append(f"{rel(path)}:{i}: {line.strip()[:96]}")
                break
        else:
            for m in _RGB.finditer(line):
                if (i, m.start()) in quoted:
                    details.append(f"{rel(path)}:{i}: {line.strip()[:96]}")
                    break
    return details


def observe_type_scale(path: Path) -> list[str]:
    """W4 档外字号（护栏 6/字阶表，观察）：字面 px/rem 字号不在 8 档集（图标 >24px
    与 var(--fs-*) token 天然不命中；rem 按根 16px 折算）。"""
    details: list[str] = []
    text = path.read_text(encoding="utf-8")
    print_lines = _media_print_lines(text)
    for i, line in enumerate(text.splitlines(), 1):
        if _is_comment(line) or i in print_lines:
            continue
        for m in _FONT_SIZE.finditer(line):
            val = float(m[1]) * (16 if m[2] == "rem" else 1)
            if val >= 24 or int(val) in FONT_TIERS:
                continue
            details.append(f"{rel(path)}:{i}: font-size {m[1]}{m[2]} 档外（字阶 {sorted(FONT_TIERS)}）")
    return details


def observe_spacing_scale(path: Path) -> list[str]:
    """W5 档外间距（护栏 2/Layout 间距阶，观察）：padding/margin/gap 首个字面 px
    值不在 4/8/12/16/24/32 档（仅首值近似口径，控制噪声；auto/calc/%/em 不判）。"""
    details: list[str] = []
    text = path.read_text(encoding="utf-8")
    print_lines = _media_print_lines(text)
    for i, line in enumerate(text.splitlines(), 1):
        if _is_comment(line) or i in print_lines:
            continue
        for m in _SPACING_DECL.finditer(line):
            px = _SPACING_PX.search(m.group(1))
            if px and float(px.group(1)) not in SPACING_TIERS:
                details.append(f"{rel(path)}:{i}: 间距 {px.group(1)}px 档外（间距阶 {sorted(SPACING_TIERS)}）")
    return details


def _collect_files(paths: tuple[str, ...] | None) -> list[Path]:
    files: list[Path] = []
    for rel_path in paths or STYLE_DOMAIN:
        base = REPO_ROOT / rel_path
        if base.is_dir():
            files.extend(sorted(base.glob("*.html")))
        elif base.is_file():
            files.append(base)
    return files


def run_checks(
    paths: tuple[str, ...] | None = None,
    design_text: str | None = None,
    files: list[Path] | None = None,
) -> tuple[list[str], dict[str, list[str]]]:
    """执行全部规则。

    Args:
        paths: 检查域相对路径（缺省 ``STYLE_DOMAIN``）。
        design_text: DESIGN.md 正文（缺省读仓库真值）。
        files: 显式文件列表（测试注入合成文件，优先于 ``paths``）。

    Returns:
        ``(findings, observations)`` —— findings 为 E 级（退出 2）；
        observations 为 W 级明细列表（统计用，不判 finding）。
    """
    targets = files if files is not None else _collect_files(paths)
    if design_text is None:
        design_path = REPO_ROOT / DESIGN_DOC
        design_text = design_path.read_text(encoding="utf-8") if design_path.is_file() else ""

    brand = _brand_hexes(targets)
    findings: list[str] = []
    observations: dict[str, list[str]] = {
        "raw_colors": [],
        "radius": [],
        "inline_colors": [],
        "type_scale": [],
        "spacing_scale": [],
    }

    report_css = ""
    web_css = ""
    for path in targets:
        text = path.read_text(encoding="utf-8")
        if path.name == "report_template.html":
            report_css = text
        if path.name == "style.css":
            web_css = text
        findings += check_emphasis_color(path, brand)
        if ":root" in text or "[data-theme" in text:
            findings += check_dark_sync(path)
        observations["raw_colors"] += observe_raw_colors(path)
        observations["radius"] += observe_radius(path)
        observations["inline_colors"] += observe_inline_colors(path)
        observations["type_scale"] += observe_type_scale(path)
        observations["spacing_scale"] += observe_spacing_scale(path)

    if design_text and report_css and web_css:
        findings += check_token_alignment(report_css, web_css, design_text)
    return findings, observations


def main() -> int:
    parser = argparse.ArgumentParser(description="设计护栏机检（DESIGN.md 护栏样式面）")
    add_common_args(parser)
    args = parser.parse_args()

    findings, observations = run_checks()
    stale = _stale_exemptions(_collect_files(None))
    w1, w2 = len(observations["raw_colors"]), len(observations["radius"])
    w3, w4, w5 = (len(observations[k]) for k in ("inline_colors", "type_scale", "spacing_scale"))

    if args.verbose:
        for line in observations["raw_colors"]:
            print(f"  [观察] {line}")
        for line in observations["radius"]:
            print(f"  [观察] {line}")
        for key in ("inline_colors", "type_scale", "spacing_scale"):
            for line in observations[key]:
                print(f"  [观察] {line}")
        print(f"  [豁免] W1 存量白名单 {len(_RAW_COLOR_EXEMPTIONS)} 条（命中即跳过，理由见常量声明）")
        for line in stale:
            print(f"  [!] {line}")
    if not args.ci and (w1 or w2 or w3 or w4 or w5):
        hint = "（-v 看明细）" if not args.verbose else ""
        print(
            f"[!] 观察项（不判 finding，观察期）：裸色值 {w1} 处、圆角档外 {w2} 处、"
            f"内联色值 {w3} 处、字号档外 {w4} 处、间距档外 {w5} 处{hint}"
        )

    return report(
        findings,
        f"[OK] 设计护栏 E 级通过（观察期统计：裸色值 {w1}、圆角档外 {w2}、"
        f"内联色值 {w3}、字号档外 {w4}、间距档外 {w5}）",
        ci=args.ci,
    )


if __name__ == "__main__":
    sys.exit(main())
