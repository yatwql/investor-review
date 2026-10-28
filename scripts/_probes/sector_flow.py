"""行业资金流向双通道可用性探测（scripts/probe.py::sector-flow target）。

背景：行业资金流向主通道（东财 `push2`）在本机出口会被配额型限流——表现为
TLS 层 `RemoteDisconnected`（约 0.2s 秒断，非超时），偶发短窗口放行几次随即
恢复失败。日志只能证明「失败过」，无法证明「现在到底哪个通道能取数」，
故用本探针逐个通道直调**取数层**（与报告同一代码路径，不写缓存/不记负缓存）。

判读：
  A. 主通道成功率 ≥ 8/10 → 主通道可用，不需备用
  B. 主通道低、备用通道高 → 备用通道顶上（生产行为即自动切换，无需干预）
  C. 两通道都低 → 环境侧普遍受限（出口/时段/风控），报错照常降级，勿改代码
"""

from __future__ import annotations

import time

PROBE_TARGET = "sector-flow"

_PROBES = 10


def build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        description="行业资金流向逐通道可用性探测（主=东财 push2，备=同花顺；只读取数，不写缓存）",
    )
    parser.add_argument("--count", type=int, default=_PROBES, help=f"每通道探测次数（默认 {_PROBES}）")
    return parser


def _probe_channel(name: str, fetch, count: int) -> tuple[int, list[str]]:
    """连续调用某通道取数函数，返回 (成功次数, 每次结果描述)。"""
    from src.python.providers.akshare_extras import _SectorFlowUnavailable

    ok = 0
    detail: list[str] = []
    for i in range(1, count + 1):
        t0 = time.time()
        try:
            rows = fetch()
            dt = (time.time() - t0) * 1000
            if rows:
                ok += 1
                detail.append(f"[{i}] 成功 {dt:5.0f}ms  行业数={len(rows)}")
            else:
                detail.append(f"[{i}] 空榜 {dt:5.0f}ms")
        except _SectorFlowUnavailable as exc:
            dt = (time.time() - t0) * 1000
            detail.append(f"[{i}] 不可用 {dt:5.0f}ms  {exc.kind}")
        except Exception as exc:  # noqa: BLE001 — 诊断脚本需覆盖所有异常
            dt = (time.time() - t0) * 1000
            detail.append(f"[{i}] 异常 {dt:5.0f}ms  {type(exc).__name__}: {exc}")
    return ok, detail


def run(args) -> int:
    """主入口：逐通道探测并给出建议。"""
    from src.python.providers import akshare_extras as ae

    count = max(1, int(getattr(args, "count", _PROBES) or _PROBES))
    channels = [
        (name, ae._SECTOR_FLOW_CHANNEL_LABELS.get(name, name), ae._SECTOR_FLOW_FETCHERS[name])
        for name in ae._SECTOR_FLOW_CHANNELS
    ]

    print(f"行业资金流向通道探测 — 每通道 {count} 次（只读取数，不写缓存/负缓存）")
    results: dict[str, int] = {}
    for name, label, fetch in channels:
        print(f"\n【{label}】({name})")
        ok, detail = _probe_channel(name, fetch, count)
        results[name] = ok
        for line in detail:
            print(f"  {line}")
        print(f"  成功率: {ok}/{count}")

    primary = channels[0][1]
    print("\n结果:")
    for name, label, _ in channels:
        print(f"  {label}: {results[name]}/{count}")
    if results[channels[0][0]] * 10 >= count * 8:
        print(f"  判读: {primary} 可用，无需备用通道介入")
        return 0
    if any(results[n] * 10 >= count * 8 for n, _, _ in channels[1:]):
        print("  判读: 主通道受限，备用通道可用——生产链路会自动切换，无需改代码")
        return 0
    print("  判读: 全部通道均受限（环境侧/时段性），报告按既有降级口径处理，勿改代码")
    return 1
