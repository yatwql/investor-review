"""Jinja2 模板环境 — _ENV 实例 + 自定义过滤器 + section_visible fallback。"""

from __future__ import annotations

import logging
import os
from typing import Any

from jinja2 import BytecodeCache, Environment, FileSystemLoader, pass_context

from src.python.core.code_utils import is_qdii_extended
from src.python.core.registry import _REPORT_SECTION_DEFAULT
from src.python.core.constants import PROJECT_ROOT
from src.python.report.market_value import PRICE_TYPE_OFFICIAL_NAV_T1

logger = logging.getLogger("invest")

# ── 路径 & Jinja2 环境 ─────────────────────────────────────

# 报告 Jinja 模板统一归 src/static/tmpl/（与前端资产同目录，src/python 仅保留 Python 代码）
_TEMPLATE_DIR = os.path.normpath(os.path.join(PROJECT_ROOT, "src", "static", "tmpl"))


class _JinjaBytecodeCache(BytecodeCache):
    """模板字节码缓存（落 ``<缓存根>/jinja/``）。

    为何需要：模板**编译**（解析 + 生成 Python 源码）是 HTML 生成阶段的主要开销，
    实测 18 个模板（主模板 + 17 个 partial）编译占该阶段 0.65s ≈ 97%（渲染本身仅
    ~0.02s）；冷缓存时还要从挂载盘读 18 个模板文件，这就是该阶段在 0.02s~21s 间
    大幅挖动的主因（实测：落盘仅 0.003s）。

    目录按需解析（而非构造时固定）：缓存根在运行期可被重定向
    （``INVEST_CACHE_DIR`` / 测试 fixture 改 ``cache._CACHE_DIR``），构造时固化会把
    测试写入真实 ``data/cache``。缓存键含模板源码校验和（jinja 自带），改模板自动失效。
    """

    __slots__ = ("_subdir",)

    def __init__(self, subdir: str = "jinja") -> None:
        super().__init__()
        self._subdir = subdir

    def _path(self, bucket: Any) -> str:
        from src.python.cache import get_cache_dir

        return os.path.join(get_cache_dir(), self._subdir, f"{bucket.key}.cache")

    def load_bytecode(self, bucket: Any) -> None:
        try:
            with open(self._path(bucket), "rb") as f:
                bucket.bytecode_from_string(f.read())
        except FileNotFoundError:
            return
        except OSError as e:  # 缓存不可读只影响「下次还得编译」，不得阻断报告
            logger.debug("Jinja 字节码缓存读取失败（回退编译）: %s", e)

    def dump_bytecode(self, bucket: Any) -> None:
        path = self._path(bucket)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = f"{path}.tmp"
            with open(tmp, "wb") as f:
                f.write(bucket.bytecode_to_string())
            os.replace(tmp, path)
        except OSError as e:  # 写不进缓存最多是下次再编译，不得影响报告产出
            logger.debug("Jinja 字节码缓存写入失败（忽略）: %s", e)


_ENV = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=True,
    bytecode_cache=_JinjaBytecodeCache(),
)


# ── Jinja2 自定义过滤器 ─────────────────────────────────────


def _jinja_money(value: Any) -> str:
    """格式化金额：1,234.56"""
    try:
        return f"{float(value):,.2f}"
    except (ValueError, TypeError):
        return "--"


def _jinja_pct(value: Any) -> str:
    """格式化比率 (0.15 → +15.00%)"""
    try:
        v = float(value)
        sign = "+" if v >= 0 else ""
        return f"{sign}{v * 100:.2f}%"
    except (ValueError, TypeError):
        return "--"


def _jinja_price(value: Any) -> str:
    """格式化价格：四位小数"""
    try:
        return f"{float(value):.4f}"
    except (ValueError, TypeError):
        return "--"


def _jinja_shares(value: Any) -> str:
    """格式化份额：两位小数"""
    try:
        return f"{float(value):,.2f}"
    except (ValueError, TypeError):
        return "--"


def _jinja_change(value: Any) -> str:
    """格式化涨跌幅：百分数"""
    try:
        v = float(value)
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.2f}%"
    except (ValueError, TypeError):
        return "--"


def _jinja_price_type_class(price_type: str, name: str = "") -> str:
    """取价方式着色的语义 class：数据时效性高/可靠 → `rating-stable`，否则空串。

    着色规则同 Excel 端 `_apply_price_type_colors`：
      - "场内收盘价(T)"、"场内午市收盘(T)"、"官方净值(T)" → 稳定（蓝）
      - QDII 基金（取价方式为「官方净值」旧一日口径）→ 稳定（蓝）
    模板只用 class，不写内联 `style="color: …"`（Jinja 进 CSS 值位置会被解析器判语法错）。
    """
    if price_type in ("场内收盘价(T)", "场内午市收盘(T)", "官方净值(T)"):
        return "rating-stable"
    if price_type == PRICE_TYPE_OFFICIAL_NAV_T1 and name and is_qdii_extended(name):
        return "rating-stable"
    return ""


def _jinja_profit_class(value: Any) -> str:
    """盈亏语义 class：盈→`profit`、亏→`loss`、零/不可解析→空串。

    模板改用 class 而非内联 `style="color:..."`：把 Jinja 花括号放进 CSS 值位置会被任何
    CSS 解析器判为语法错（HTML 语言服务因此对每个模板报几十条误报），且颜色语义本应
    由 class 承载（`DESIGN.md` 色彩角色表），暗色主题自动跟随。
    """
    try:
        v = float(value)
        if v > 0:
            return "profit"
        if v < 0:
            return "loss"
        return ""
    except (ValueError, TypeError):
        return ""


def _jinja_thousands(value: Any) -> str:
    """格式化整数：1,234"""
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


def _jinja_sentiment_colorize(text: str) -> str:
    """将 [利好]/[利空] 标记着色为 HTML 内联样式，其余文本保持原样。

    [利好] → 红 var(--profit)，[利空] → 绿 var(--loss)（跟随主题）。
    返回的 HTML 已在过滤器层处理，模板中使用 ``| safe`` 避免二次转义。
    """
    if not text:
        return text
    text = text.replace("[利好]", '<span style="color:var(--profit);font-weight:bold">[利好]</span>')
    text = text.replace("[利空]", '<span style="color:var(--loss);font-weight:bold">[利空]</span>')
    return text


# ── 注册过滤器 & 全局函数 ────────────────────────────────────


@pass_context
def _jinja_anon_code(ctx, value: Any) -> Any:
    """匿名化代码列掩码：在模板渲染点把持仓真码折叠为显示掩码。

    与产物自由文本全文替换不同，这里是**精确键控**查找（真码是完整键），
    因此不会误伤金额/JSON 数值；指数、基准等非持仓代码不在映射内、原样通过。
    上下文无 ``anon_code_map`` 或未命中时返回原值，off/code_display 零副作用。

    Args:
        ctx: Jinja 渲染上下文（pass_context 注入）。
        value: 待渲染的代码（非 str 或空值原样返回）。

    Returns:
        折叠后的显示代码。
    """
    if not isinstance(value, str) or not value:
        return value
    code_map = ctx.get("anon_code_map") or {}
    return code_map.get(value, value)


_ENV.filters["money"] = _jinja_money
_ENV.filters["pct"] = _jinja_pct
_ENV.filters["price"] = _jinja_price
_ENV.filters["shares"] = _jinja_shares
_ENV.filters["change"] = _jinja_change
_ENV.filters["profit_class"] = _jinja_profit_class
_ENV.filters["price_type_class"] = _jinja_price_type_class
_ENV.filters["thousands"] = _jinja_thousands
_ENV.filters["sentiment_colorize"] = _jinja_sentiment_colorize
_ENV.filters["anon_code"] = _jinja_anon_code

_ENV.globals["section_visible"] = lambda key: False  # fail-closed 默认值，生产环境由 context 变量覆盖

# 章节显示名单源：模板/partials 标题一律 {{ section_names[key] }}（与导航、Excel 页签同源于
# core/registry.py 的 _REPORT_SECTION_DEFAULT[].name），改名收敛为注册表单点变更
_ENV.globals["section_names"] = {sec["key"]: sec["name"] for sec in _REPORT_SECTION_DEFAULT}
