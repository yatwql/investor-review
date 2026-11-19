"""akshare 接口名兼容层：**调用方只写逻辑名**，跨版本改名集中在这张表里。

akshare 会在小版本里**就地重命名**导出接口且不留别名（实测 1.20.42 → 1.20.65：
`tool_trade_date_hist_sina` → `calendar_trade_date_hist_sina`、`stock_fund_flow_industry`
→ `stock_fund_flow_industry_ths`、`news_cctv` → `alternative_news_cctv`、
`stock_sector_fund_flow_rank` → `stock_fund_flow_sector_rank_em`）。依赖声明是区间
（`akshare>=1.16,<2.0`），所以同一份代码会跑在新旧两种名字上：

- 只写旧名 → 新解析的机器上 `AttributeError`，数据源静默降级（CI 实测交易日历与行业
  资金流两条链路整条失效，报告仍出得来、只是少了数据）；
- 只写新名 → 老机器上同样失效。

因此名字解析只在这一处，调用方写逻辑名；解析按候选链顺序取**第一个存在的**接口
（同一个函数的改名，参数与返回结构一致，不改语义）。

用法::

    from src.python.core.akshare_compat import resolve

    fn = resolve(ak, "news_cctv")   # 按候选链解析出当前可调用的那个接口名
    df = fn(date=date_str)

新增改名时：把逻辑名与新名加进 `_ALIASES`，不要在调用点写 `hasattr` 分支。
"""

from __future__ import annotations

from typing import Any, Callable

#: 逻辑名 → akshare 里可能有过的全部接口名（首选在前：旧名可用时仍走旧名，行为不变）
_ALIASES: dict[str, tuple[str, ...]] = {
    "tool_trade_date_hist_sina": ("tool_trade_date_hist_sina", "calendar_trade_date_hist_sina"),
    "stock_fund_flow_industry": ("stock_fund_flow_industry", "stock_fund_flow_industry_ths"),
    "news_cctv": ("news_cctv", "alternative_news_cctv"),
    "stock_sector_fund_flow_rank": ("stock_sector_fund_flow_rank", "stock_fund_flow_sector_rank_em"),
}


def candidate_names(name: str) -> tuple[str, ...]:
    """该逻辑名在 akshare 里可能的全部接口名（首选在前；未登记的原样返回）。"""
    return _ALIASES.get(name, (name,))


def resolve(akshare: Any, name: str) -> Callable[..., Any]:
    """按候选链解析出真正可调用的接口函数。

    Args:
        akshare: `akshare` 模块（测试可传替身对象）。
        name: 逻辑名（`candidate_names` 的键）。

    Returns:
        该接口的可调用对象。

    Raises:
        AttributeError: 候选链里的名字全都不存在（akshare 又改名的信号，应更新 `_ALIASES`）。
    """
    tried = candidate_names(name)
    for candidate in tried:
        fn = getattr(akshare, candidate, None)
        if callable(fn):
            return fn
    raise AttributeError(f"akshare 无该接口（逻辑名 {name!r}，已试：{', '.join(tried)}）")
