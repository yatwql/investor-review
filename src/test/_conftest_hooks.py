"""conftest 夹具实现 — 命令行选项、标记全集与收集期校验。

本模块由入口 `src/test/conftest.py` 显式 import 回来注册（pytest 只认入口模块命名空间里的
夹具与钩子）；改动后跑 `pytest src/test -q` 验证收集与自动复位仍然生效。
"""

from __future__ import annotations

import warnings

import pytest

# ── 项目自定义标记全集（与 pytest_configure 注册的标记保持一致）──

_KNOWN_MARKERS: set[str] = {
    # scenario 分支
    "scenario",
    "scenario_basic",
    "scenario_resilience",
    "scenario_llm",
    "scenario_datetime",
    "scenario_stock",
    "scenario_fund",
    "scenario_mixed_accounts",
    "scenario_new_holdings",
    "scenario_cache_hit",
    "scenario_bond",
    "scenario_network_down",
    "scenario_single_holding",
    "scenario_zero_cost",
    "scenario_extreme",
    "scenario_perf",
    "scenario_security",
    # unit 分支
    "unit",
    "unit_providers",
    "unit_fetcher",
    "unit_llm",
    "unit_news",
    "unit_report",
    "unit_config",
    "unit_core",
    "unit_cli",
    "unit_ui",
    "unit_analysis",
    "unit_scripts",
    "unit_web",
    "unit_qa",
    # 跨领域标记
    "llm",
    "edge",
    "real_repo",
    "smoke",
    "data",
    "integration",
    # integration 分支
    "integration_contract",
    "integration_isolation",
    "integration_news_pipeline",
    "integration_cache",
    "integration_tui",
    "integration_cli",
    # 真实网络验证套件（opt-in，默认跳过，不入门禁）
    "live",
    # 数据源记录-回放（用例声明所需 cassette，离线运行）
    "cassette",
}

# pytest 内置标记 — 这些不算"项目标记"
_BUILTIN_MARKERS: set[str] = {"skip", "skipif", "xfail", "usefixtures", "filterwarnings"}


def pytest_addoption(parser):
    """注册 `--run-live` 选项：显式允许运行 live 真实网络套件。

    不设置则 live 标记的测试一律跳过（防止误入 `all` 门禁触发真实网络）。
    """
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="运行 @pytest.mark.live 真实网络验证套件（默认跳过，不入门禁）",
    )
    parser.addoption(
        "--record-cassettes",
        action="store_true",
        default=False,
        help="录制数据源真实响应体写入 src/test/data/cassettes/（需与 --run-live 同用，默认关闭）",
    )


@pytest.fixture(autouse=True)
def _skip_live_unless_requested(request):
    """默认跳过 live 套件，仅 `--run-live` 或 `-m live` 时运行。

    机制性保证 live 测试不进入任何门禁（dev-verify/verify/all 等均不含）：
    - `pytest -m live`：marker 过滤已收集 live 项，本 fixture 放行（显式指定）
    - `--run-live`：显式开关，放行
    - 其余任何方式（含 `all` 全量）收集到 live 项：一律 skip，不发起真实网络
    """
    if request.config.getoption("--run-live"):
        return
    if request.node.get_closest_marker("live") is not None:
        pytest.skip("live 套件为 opt-in（真实网络验证），需 `--run-live` 或 `-m live` 显式运行")


def pytest_collection_modifyitems(config, items):
    """收集期校验 edge 标记与文件名的匹配约束。

    规则（§1.9 边缘测试文件隔离规范）：
      1. 任何带 @pytest.mark.edge 的测试，其所属文件必须以 _edge.py 结尾
      2. 任何 *_edge.py 文件中的测试，必须带有 @pytest.mark.edge 标记
      3. 违规项报错停止，不允许静默跳过
    """
    for item in items:
        fspath = str(item.fspath)
        has_edge_marker = item.get_closest_marker("edge") is not None
        is_edge_file = fspath.endswith("_edge.py")

        if has_edge_marker and not is_edge_file:
            raise pytest.UsageError(
                f"[!] 边缘测试文件隔离违规：\n"
                f"    测试项 {item.name} 带有 @pytest.mark.edge 标记，\n"
                f"    但所在文件 {fspath} 不以 _edge.py 结尾。\n"
                f"    请将该测试移至对应的 *_edge.py 文件，或移除 edge 标记。"
            )
        if is_edge_file and not has_edge_marker:
            raise pytest.UsageError(
                f"[!] 边缘测试文件隔离违规：\n"
                f"    文件 {fspath} 以 _edge.py 结尾，\n"
                f"    但其测试项 {item.name} 缺少 @pytest.mark.edge 标记。\n"
                f"    请为该测试添加 @pytest.mark.edge，或移出 _edge.py 文件。"
            )

    # ── scenario 目录×基础 marker 双向一致校验（与上方 edge 隔离同纪律）──
    # 背景：scenario/regression（P2 门禁）/integration 三模式按裸 `scenario`
    # marker 筛选；子域 marker（scenario_security 等）不被任何门禁选择器消费。
    # 仓内裸 scenario 现状靠基类/模块级佩戴隐式继承，新文件若只带子域 marker
    # 将静默漏出回归门禁（连下方缺标记警告都不触发，它只查「无任何自定义
    # marker」）——本段收集期双向硬拦截：目录内必带裸 scenario；带裸 scenario
    # 必属 scenario 目录（scenario_* 子域 marker 不受本约束）。
    for item in items:
        fspath_norm = str(item.fspath).replace("\\", "/")
        in_scen_dir = "/test/scenario/" in fspath_norm
        has_scen = item.get_closest_marker("scenario") is not None
        if in_scen_dir and not has_scen:
            raise pytest.UsageError(
                f"[!] scenario 门禁 marker 违规：\n"
                f"    测试项 {item.name}（{fspath_norm}）位于 src/test/scenario/ 下，"
                f"但未佩戴基础 `scenario` marker——不会被 scenario/regression/"
                f"integration 门禁选择器收集。\n    请在模块级 pytestmark 或基类上补"
                f" @pytest.mark.scenario（子域 marker 另挂）。"
            )
        if has_scen and not in_scen_dir:
            raise pytest.UsageError(
                f"[!] scenario 门禁 marker 违规：\n"
                f"    测试项 {item.name}（{fspath_norm}）佩戴了基础 `scenario` "
                f"marker，但不在 src/test/scenario/ 目录下——scenario 选择器会越目录"
                f"误抓。\n    请移入 scenario 目录，或改用 scenario_* 子域/其他 marker。"
            )

    # ═══════════════════════════════════════════════════════════════
    # 标记遗漏警告（预防性）
    # ═══════════════════════════════════════════════════════════════
    # 检查每个测试是否至少有一个项目自定义标记。
    # 若没有，发出 PytestWarning 提醒补充 pytestmark 模块级变量。
    # 当前全部已有测试均已覆盖（通过 pytestmark 模块级变量），
    # 本检查旨在防止新增测试文件时遗漏标记。目录归域特例（handlers/cache→unit_core、
    # startup→unit_ui 等）以 scripts/_test_redundancy/markers.py 期望表为单一事实来源。
    _warned_files: set[str] = set()
    for item in items:
        item_markers = {m.name for m in item.iter_markers()}
        has_custom = not _KNOWN_MARKERS.isdisjoint(item_markers)
        if has_custom or item_markers.issubset(_BUILTIN_MARKERS):
            continue
        fspath = str(item.fspath)
        if fspath not in _warned_files:
            _warned_files.add(fspath)
            warnings.warn(
                pytest.PytestWarning(
                    f"[!] 测试文件缺少项目标记（pytestmark）：{fspath}\n"
                    f"    请在文件顶部添加 pytestmark 变量，例如：\n"
                    f"    pytestmark = [pytest.mark.unit, pytest.mark.unit_report]\n"
                    f"    目录归域以 scripts/_test_redundancy/markers.py 期望表为准（特例："
                    f"unit/startup→unit_ui、unit/handlers 与 unit/cache→unit_core）\n"
                    f"    已知标记：{', '.join(sorted(_KNOWN_MARKERS))}"
                )
            )
