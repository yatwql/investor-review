"""持仓成本相对历史价格区间位置（cost_position）— 纯计算层。

指标定义（设计见 ``docs/archive/v0.13.x/holding-cost-position-design.md``）：

.. code-block:: text

    cost_position_pct = clamp((每份成本 − 窗口最低价) / (窗口最高价 − 窗口最低价), 0, 1)

- ≈1 → 成本买在区间高位（追涨嫌疑）；≈0 → 低位布局
- 窗口内最高价 == 最低价（停牌/极窄波动）→ 取 0.5 中性值
- 成本价越出区间（大幅浮盈/浮亏后加仓摊薄等）→ clamp 到 0/1

本模块只做纯数学（无 I/O、不导入 report/ 包）；取数与数据契约装配在
``report/cost_position.py``。
"""

from __future__ import annotations

from src.python.core.num_utils import finite_or

#: 短窗口（交易日）——列头/脚注中的窗口数字一律由本常量派生，禁止写字面量
SHORT_WINDOW_DAYS = 20

#: 长窗口（交易日）——260 交易日 ≈ 52 周，列头「(52周)」= LONG_WINDOW_DAYS // 5
LONG_WINDOW_DAYS = 260

#: 缺失占位符（与持仓明细页签既有「--」口径一致）
PLACEHOLDER = "--"

#: 窗口最高 == 最低（无波动）时的中性值
NEUTRAL_POSITION = 0.5


def compute_window_position(cost: float | None, closes: list[float], window: int) -> float | None:
    """成本价在近 ``window`` 交易日收盘价区间中的百分位（0~1）。

    Args:
        cost: 每份成本价（持仓均价，近似买入价）；None 或 <=0 视为无效返回 None
        closes: 收盘价序列（按日期升序，正值有效；0/None/非正值跳过）
        window: 窗口长度（交易日）；<=0 返回 None

    Returns:
        0.0~1.0 的百分位浮点；数据不可用（无效成本/空窗口/无有效价）返回 None，
        渲染层写占位符。高 == 低返回中性值 NEUTRAL_POSITION。
    """
    if cost is None or window <= 0 or not closes:
        return None
    cost = finite_or(cost, fallback=-1.0)
    if cost <= 0:
        return None
    window_closes = closes[-window:]
    valid = [c for c in window_closes if finite_or(c, fallback=-1.0) > 0]
    if not valid:
        return None
    low = min(valid)
    high = max(valid)
    if high <= low:
        return NEUTRAL_POSITION
    pct = (cost - low) / (high - low)
    return max(0.0, min(1.0, pct))


def positions_from_closes(cost: float | None, closes: list[float]) -> dict[str, float | None]:
    """同一价格序列上计算短/长两窗口百分位。

    Args:
        cost: 每份成本价
        closes: 收盘价序列（升序，同源——长窗口一次取数，短窗口取其尾部切片）

    Returns:
        ``{"short": float|None, "long": float|None}``；窗口值来自本模块常量
    """
    return {
        "short": compute_window_position(cost, closes, SHORT_WINDOW_DAYS),
        "long": compute_window_position(cost, closes, LONG_WINDOW_DAYS),
    }
