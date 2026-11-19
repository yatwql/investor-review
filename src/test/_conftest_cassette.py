"""conftest 夹具实现 — 数据源记录-回放（离线回放真实响应体）。

本模块由入口 `src/test/conftest.py` 显式 import 回来注册（pytest 只认入口模块命名空间里的
夹具与钩子）；改动后跑 `pytest src/test -q` 验证收集与自动复位仍然生效。
"""

from __future__ import annotations

import pytest


# ═══════════════════════════════════════════════════════════════
# 数据源记录-回放（语义名 datasource_cassette）
# ═══════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _auto_reset_transport_factory():
    """自动重置 HTTP 传输层注入点，防止测试间状态污染。

    ``core.http_client._TRANSPORT_FACTORY`` 是模块级单例：某用例安装后若异常
    退出未走到 ``use_transport_factory`` 的还原分支，后续用例的
    ``make_http_client()`` 会持续拿到陈旧传输。与 ``_auto_reset_provider_registry``
    同模式，前后各清一次。
    """
    from src.python.core import http_client

    http_client._TRANSPORT_FACTORY = None
    yield
    http_client._TRANSPORT_FACTORY = None


def _cassette_names(request) -> list[str]:
    """取用例声明的 cassette 名称；用法错误直接报错而非静默忽略。"""
    names: list[str] = []
    for mark in request.node.iter_markers("cassette"):
        if not mark.args or not isinstance(mark.args[0], str) or not mark.args[0]:
            raise pytest.UsageError(
                '[!] cassette 标记用法错误：需提供一个 cassette 名称，如 @pytest.mark.cassette("tencent_quote")'
            )
        names.append(mark.args[0])
    return names


@pytest.fixture(autouse=True)
def _install_cassette_replay(request):
    """按用例声明的 cassette 安装**离线回放**传输层（provider 零改动）。

    安装方式是替换 ``make_http_client()`` 的传输层（``core.http_client``
    的唯一构造点）。

    规则：
    - 未声明 ``@pytest.mark.cassette("名称")`` 的用例：不安装任何工厂，
      行为与既有测试完全一致。
    - 普通用例：安装离线回放（未命中即失败，**不回落真实网络**）。
    - ``live`` 套件：**不装回放**——回放与「验证源可达」互斥，且录制用例需要
      真实网络。录制由显式请求 ``cassette_recording`` fixture 的用例自行开启。
    """
    from src.python.core.cassette import cassette_replay

    names = _cassette_names(request)
    if not names or request.node.get_closest_marker("live") is not None:
        yield
        return
    # 季报窗口按当前日期向前循环，而录制内容固定在录制当日：把窗口锚定到 cassette
    # 的 recorded_at，否则跨季度后回放会先去请求未录制的季度而报假 miss（上游是否漂移
    # 无关）。锚定后请求形状仍须与录制逐字一致，漂移照样报 miss。
    from src.python.providers.tiantian_holdings import quarter_walk_anchor

    with cassette_replay(names), quarter_walk_anchor(_declared_recording_anchor(names)):
        yield


def _declared_recording_anchor(names: list[str]):
    """取所声明 cassette 中最新的录制时点（无法解析或缺失则 None = 按当前时间）。"""
    from datetime import datetime

    from src.python.core.cassette import list_cassettes

    wanted = set(names)
    anchors = []
    for entry in list_cassettes():
        if entry.get("name") not in wanted:
            continue
        try:
            anchors.append(datetime.fromisoformat(entry.get("recorded_at") or ""))
        except ValueError:
            continue
    return max(anchors) if anchors else None


@pytest.fixture(autouse=True)
def _auto_reset_chain_overrides():
    """重置调用级数据源覆盖（进程级运行作用域状态，避免测试间污染）。"""
    from src.python.fetcher.chain import reset_chain_overrides

    reset_chain_overrides()
    yield
    reset_chain_overrides()


@pytest.fixture(autouse=True)
def _auto_reset_self_review_carrier():
    """重置生成后自检的运行作用域载体（模块级状态，避免测试间污染）。"""
    from src.python.llm.self_review import reset_self_review

    reset_self_review()
    yield
    reset_self_review()


@pytest.fixture
def cassette_recording(request):
    """录制会话 —— 需 ``--run-live`` + ``--record-cassettes`` 双开关，否则跳过。

    录制传输照单全收该用例的全部流量，无法把不同请求归属到不同 cassette，
    故要求「一用例一 cassette」：声明多个时直接报错。
    """
    from src.python.core.cassette import cassette_record

    if not request.config.getoption("--record-cassettes"):
        pytest.skip("未开启录制：需 `--run-live --record-cassettes` 双开关显式启用")

    marks = list(request.node.iter_markers("cassette"))
    names = _cassette_names(request)
    if len(names) != 1:
        raise pytest.UsageError(
            f"[!] 录制模式下单个用例只能声明一个 cassette，实际声明了 {len(names)} 个："
            f"{', '.join(names) or '（无）'}。请拆成多个用例分别录制。"
        )
    with cassette_record(names[0], source=marks[0].kwargs.get("source", "")) as session:
        yield session
