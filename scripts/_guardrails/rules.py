"""设计护栏规则声明 — 检查域、档位白名单、正则与存量豁免表。

纯声明（无 I/O、无判定逻辑），供 `check-style-guardrails.py` 的检查与观测
函数引用。改档位或加豁免只动本文件。
"""

from __future__ import annotations

import re

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
