"""把「内部建 py_mini_racer(V8) 上下文」的 akshare 调用放进子进程执行。

**为什么必须隔离**：akshare 若干接口（`tool_trade_date_hist_sina`、`stock_fund_flow_industry`）
在函数体内就地 `py_mini_racer.MiniRacer()` 建 V8 上下文。V8 平台的初始化是进程级的且与线程
绑定，实测三种崩法都拦不住（原生崩溃/死锁，`try/except` 与 pytest 均无效）：

1. 两条线程先后初始化 V8 → 段错误（栈顶 `_make_context` → `mr_init_context`）；
2. 上下文在**别的线程**的 GC 里被释放 → 段错误（`MiniRacer.__del__` → `mr_free_context`）；
3. 上下文活到进程退出期、在主线程被释放 → `close()` 去 join 已结束线程的事件循环，退出死锁。

调用方（工作线程池）无法保证「创建/回收永远落在同一条线程且不留活口」——异常栈帧、
第三方内部缓存都会把上下文留到下一次 GC。**子进程隔离**把这条不确定性彻底隔在进程边界外：
子进程退出即回收全部 V8 状态，父进程只拿 JSON 结果；子进程崩了/挂了，父进程照常降级。

**接口约束**：
- 只允许调用白名单里的 akshare 接口（`_ALLOWED_FUNCTIONS`），参数走 kwargs 白名单透传；
- 返回值统一为 `list[dict]`（DataFrame → `to_dict("records")`），日期等复杂类型转字符串；
- 离线契约：`INVEST_SUBPROCESS_NETWORK_OFFLINE=1` 时子进程不发起任何网络请求（测试/基准用，
  父进程的 socket 桩影响不到子进程，故用环境变量显式传达）。

新增 V8 类取数时：把接口名加进 `_ALLOWED_FUNCTIONS`，并在调用方用 `run_akshare_v8(...)`；
**不要**在主进程直接调这些接口——`src/test/unit/core/test_v8_call_sites.py` 会扫描并报红。
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from typing import Callable

logger = logging.getLogger("invest")

#: 允许在子进程中调用的 akshare 接口（白名单：只有这些名字会被拼进子进程脚本）
_ALLOWED_FUNCTIONS: frozenset[str] = frozenset({"tool_trade_date_hist_sina", "stock_fund_flow_industry"})

#: 子进程输出标记（结果 JSON 紧随其后一行）
_RESULT_MARKER = "<<<V8_RESULT>>>"
_ERROR_MARKER = "<<<V8_ERROR>>>"

#: 离线开关环境变量（父进程 socket 桩不跨进程，故显式传达给子进程）
OFFLINE_ENV = "INVEST_SUBPROCESS_NETWORK_OFFLINE"

#: 子进程脚本：白名单接口 → DataFrame → records JSON。异常也转 JSON 回传，便于父进程归类。
_CHILD_SCRIPT = f'''
import json
import sys

payload = json.loads(sys.argv[1])
if __import__("os").environ.get({OFFLINE_ENV!r}, "") == "1":
    print({_ERROR_MARKER!r} + json.dumps({{"type": "offline", "message": "offline stub"}}, ensure_ascii=False))
    raise SystemExit(1)

try:
    import akshare as ak
    df = getattr(ak, payload["func"])(**payload.get("kwargs", {{}}))
    records = df.to_dict("records") if hasattr(df, "to_dict") else list(df or [])
    print({_RESULT_MARKER!r} + json.dumps(records, ensure_ascii=False, default=str))
except Exception as exc:
    print({_ERROR_MARKER!r} + json.dumps({{"type": type(exc).__name__, "message": str(exc)}}, ensure_ascii=False))
    raise SystemExit(1)
'''


class V8SourceError(RuntimeError):
    """V8 类取数不可用（子进程崩溃/超时/返回不可解析/离线桩）。

    调用方按「数据源不可用」统一降级，无需区分具体原因；原因文本带在消息里。
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        super().__init__(f"{reason}: {detail}" if detail else reason)


def _validated_payload(func: str, kwargs: dict | None) -> dict:
    """校验接口名与参数（只允许白名单接口 + JSON 可序列化参数）。"""
    if func not in _ALLOWED_FUNCTIONS:
        raise ValueError(f"不在 V8 子进程白名单内的 akshare 接口: {func!r}（见 core/v8_subprocess.py）")
    params = dict(kwargs or {})
    try:
        json.dumps(params, ensure_ascii=False)
    except TypeError as exc:
        raise ValueError(f"参数不可 JSON 序列化（子进程只收纯数据）: {exc}") from exc
    return {"func": func, "kwargs": params}


def _parse_child_output(proc: subprocess.CompletedProcess) -> list[dict]:
    """解析子进程输出：结果 JSON 或错误 JSON。"""
    stdout = proc.stdout or ""
    for line in stdout.splitlines():
        if line.startswith(_RESULT_MARKER):
            try:
                data = json.loads(line[len(_RESULT_MARKER) :])
            except json.JSONDecodeError as exc:
                raise V8SourceError("unparsable", f"子进程结果不是合法 JSON: {exc}") from exc
            return data if isinstance(data, list) else []
        if line.startswith(_ERROR_MARKER):
            try:
                info = json.loads(line[len(_ERROR_MARKER) :])
            except json.JSONDecodeError:
                info = {"type": "unknown", "message": line[len(_ERROR_MARKER) :]}
            # 离线桩/网络失败属「源不可用」，不是程序缺陷：原因里带上子进程给的类型
            raise V8SourceError("source_failed", f"{info.get('type')}: {info.get('message')}")
    tail = (proc.stderr or "").strip().splitlines()[-3:]
    raise V8SourceError("no_result", f"子进程未返回结果（退出码 {proc.returncode}）: {' | '.join(tail)}")


def _run_child(payload: dict, timeout: float) -> list[dict]:
    """起子进程执行白名单接口，返回 records。"""
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _CHILD_SCRIPT, json.dumps(payload, ensure_ascii=False)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        # V8 死锁在这里被兜住：子进程被杀，父进程按源不可用降级（主进程不再挂死）
        raise V8SourceError("timeout", f"子进程超过 {timeout:.0f}s 未返回，已终止") from exc
    return _parse_child_output(proc)


def run_akshare_v8(
    func: str,
    kwargs: dict | None = None,
    *,
    timeout: float = 90.0,
    runner: Callable[[dict, float], list[dict]] | None = None,
) -> list[dict]:
    """在子进程中调用白名单内的 V8 类 akshare 接口，返回 records。

    Args:
        func: akshare 接口名（必须在 `_ALLOWED_FUNCTIONS` 白名单内）
        kwargs: 关键字参数（须 JSON 可序列化）
        timeout: 子进程超时（秒）；超时即杀子进程并按源不可用降级
        runner: 执行器注入（测试用；默认起真实子进程）

    Returns:
        ``list[dict]``（DataFrame 的 records 形态；无数据时为空列表）

    Raises:
        ValueError: 接口名不在白名单 / 参数不可序列化
        V8SourceError: 子进程崩溃、超时、离线桩或返回不可解析（调用方按源不可用降级）
    """
    payload = _validated_payload(func, kwargs)
    records = (runner or _run_child)(payload, timeout)
    logger.debug("[v8-subprocess] %s 返回 %d 条记录", func, len(records))
    return records
