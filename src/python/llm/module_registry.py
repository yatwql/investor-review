"""LLM 模块键单一事实位 — 报告侧模块后缀的全集、顺序与派生子集。

模块后缀（``settings_suffix``）的**权威定义**仍在 ``core/data_registry.py`` 的
``_MODULE_REGISTRY``（决定 llm_settings 合法键名、缓存前缀、页签/章节可见性）。
本模块只固定「报告侧可见的 LLM 模块清单与其产出顺序」，让各调用点引用同一份
常量而非各持一份字面量元组——质量评级与模块明细两处的成员集合须由本模块派生
与 5 元素口径，新增模块时必然只改一处，漂移后无任何报错、只表现为评级缺失或
明细行缺行。

顺序是契约（不是排版）：多处调用点按位置与四元组结果对齐
（``zip(结果元组, PARALLEL_MODULE_ORDER)``、``enumerate`` 取 ``_disabled[i]``、
``.index(module_key)`` 定位槽位、生成参数后缀串接后整体哈希），故本模块提供
**有序元组**常量，调用点须保持此顺序（字母序与产出序不同，会静默错位）。
"""

from __future__ import annotations

__all__ = [
    "LLM_MODULE_ORDER",
    "LLM_MODULE_SUFFIXES",
    "PARALLEL_MODULE_ORDER",
]

#: 报告侧 LLM 模块后缀全集（有序）：四个并行单例模块在前，新闻关联在后。
LLM_MODULE_ORDER: tuple[str, ...] = (
    "global_macro",
    "expert_review",
    "health_check",
    "penetration_deep",
    "news_correlation",
)

#: 同上，集合形态（成员判定/子集断言用；不含顺序语义）。
#:
#: **对外契约面，不是内部实现细节**：生产代码取的是 `LLM_MODULE_ORDER`（有序）与
#: `PARALLEL_MODULE_ORDER`（四并行子集），本集合面供守卫与派生方引用——测试用它校
#: 「注册表 / 页签键 / 可强制范围 ⊆ 全集」，下游派生集合（如页签键表）用它做双向相等
#: 断言。名字带 `SUFFIXES` 表示模块后缀而非序号；新增模块只需进 `LLM_MODULE_ORDER`，
#: 本集合随派生而变，不另维护。
LLM_MODULE_SUFFIXES: frozenset[str] = frozenset(LLM_MODULE_ORDER)

#: 四并行单例模块（顺序 = ``llm_content`` 四元组与各阶段结果元组的位置顺序）。
#:
#: 排除 ``news_correlation`` 的理由：它的 LLM 部分是**二次增强**（关键词模式无
#: LLM 也照样出章），既无降级占位模板、也无独立正文可评级，且走的是与四模块
#: 分离的串行后置调用阶段——凡「按四元组位置对齐」或「需要独立正文/占位/评级」
#: 的调用点都只应取这四键，混入新闻关联会整体错位或凭空多出一行/一档评级。
PARALLEL_MODULE_ORDER: tuple[str, ...] = tuple(m for m in LLM_MODULE_ORDER if m != "news_correlation")
