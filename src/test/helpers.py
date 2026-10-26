"""测试辅助工具。

集中存放测试中可复用的 mock/helper，避免各测试文件重复定义。
"""

from __future__ import annotations

from concurrent.futures import Future
from datetime import date

_QUARTER_END_MMDD = ("03-31", "06-30", "09-30", "12-31")


def recent_holdings_period(today: date | None = None) -> str:
    """返回相对当天「新鲜」的持仓报告期（最近一个完整季末，YYYY-MM-DD）。

    用于 mock 基金持仓数据的 ``date`` 字段。写死绝对日期会让这类测试随时间
    推移被报告期时效闸门判为陈旧而失败——相对当天生成则恒定落在新鲜区间。
    """
    day = today or date.today()
    quarter = (day.month - 1) // 3
    if quarter == 0:
        return f"{day.year - 1}-12-31"
    return f"{day.year}-{_QUARTER_END_MMDD[quarter - 1]}"


class SynchronousExecutor:
    """同步执行器 — ThreadPoolExecutor 的测试替身。

    用当前线程同步执行 submit 的任务，返回已完成的 Future。
    避免 mock-heavy 测试中 ThreadPoolExecutor 的线程创建开销。
    """

    def __init__(self, max_workers: int = 1) -> None:
        self._max_workers = max_workers

    def submit(self, fn, /, *args, **kwargs) -> Future:
        fut: Future = Future()
        try:
            result = fn(*args, **kwargs)
            fut.set_result(result)
        except BaseException as e:
            fut.set_exception(e)
        return fut

    def __enter__(self) -> SynchronousExecutor:
        return self

    def __exit__(self, *args) -> None:
        pass

    def shutdown(self, wait: bool = True) -> None:
        pass


def make_chain_config(
    *,
    provider: str = "claude",
    api_key: str = "sk-test",
    name: str = "test-provider",
    model: str = "",
    endpoint: str = "",
    priority: int = 10,
    strategy: str = "priority",
    **extra: object,
) -> dict:
    """构造一条 provider 链的最小 LLM 配置（单 provider 即本函数默认参数）。

    运行期 LLM 配置只有一种形态：`_provider_list` + `_strategy`（+ 合并后的非敏感
    设置）。测试需要「一个可用的 provider」时用本函数，不要手写 `provider`/`api_key`
    顶层字段——那是已移除的单 Provider 配置形态。

    Args:
        provider: 后端类型（claude/openai/gemini）
        api_key: 运行期内存条目的内联密钥（等价 credentials_ref 解析结果）
        name: 条目名（记录/展示用）
        model / endpoint: 路由字段（空串表示沿用该后端默认）
        priority: 链内优先级（小者优先）
        strategy: 链策略（priority / weighted / cost_first / fallback_only）
        **extra: 额外的顶层（非敏感）设置，如 `llm_max_concurrency`

    Returns:
        可直接传给 `call_llm()` / `generate_*` 的配置字典
    """
    entry: dict[str, object] = {"name": name, "provider": provider, "api_key": api_key, "priority": priority}
    if model:
        entry["model"] = model
    if endpoint:
        entry["endpoint"] = endpoint
    config: dict[str, object] = {
        "_provider_list": [entry],
        "_strategy": strategy,
        "_preferred_providers": {},
    }
    config.update(extra)
    return config
