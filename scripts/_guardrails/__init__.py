"""设计护栏规则声明包：check-style-guardrails.py 的规则表与常量单源。

CLI 侧只保留判定流程与渲染，规则声明（检查域、档位白名单、存量豁免表）
集中在此——加一条豁免或调一档口径只改一处。入口模块按原面 re-export，
测试与调用方仍以 `check_style_guardrails.RADIUS_TIERS` 等名字访问。
"""

from _guardrails.rules import (
    DESIGN_DOC,
    FONT_TIERS,
    RADIUS_TIERS,
    SPACING_TIERS,
    STYLE_DOMAIN,
    _COMMENT_PREFIXES,
    _FONT_SIZE,
    _HEX,
    _JS_STRING_HEX,
    _RADIUS_PX,
    _RAW_COLOR_EXEMPTIONS,
    _RGB,
    _SPACING_DECL,
    _SPACING_PX,
    _TOKEN_DEF,
)

__all__ = [
    "DESIGN_DOC",
    "FONT_TIERS",
    "RADIUS_TIERS",
    "SPACING_TIERS",
    "STYLE_DOMAIN",
    "_COMMENT_PREFIXES",
    "_FONT_SIZE",
    "_HEX",
    "_JS_STRING_HEX",
    "_RADIUS_PX",
    "_RAW_COLOR_EXEMPTIONS",
    "_RGB",
    "_SPACING_DECL",
    "_SPACING_PX",
    "_TOKEN_DEF",
]
