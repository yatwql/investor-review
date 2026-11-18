"""conftest 夹具实现 — 敏感路径 / 报告输出 / 机器本地状态隔离。

本模块由入口 `src/test/conftest.py` 显式 import 回来注册（pytest 只认入口模块命名空间里的
夹具与钩子）；改动后跑 `pytest src/test -q` 验证收集与自动复位仍然生效。
"""

from __future__ import annotations

import pytest

from src.test._path_isolation import apply_report_output_isolation, seed_sensitive_path_isolation


# ═══════════════════════════════════════════════════════════════
# 敏感路径自动隔离（autouse）
# ═══════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def _doctor_probe_targets(tmp_path_factory):
    """doctor 目录探针的 session 级落点：``[(标签, 目录)]``，三个可写目录。

    独立于各用例的 ``tmp_path``：``_check_writable`` 会在目标目录写哨兵文件
    （随即删除），而有用例断言 `tmp_path` 内无残留，故探针落点不能在 tmp_path 下。
    session 级复用单个目录，pytest 按保留策略自动清理。
    """
    base = tmp_path_factory.mktemp("doctor_probe")
    targets: list[tuple[str, str]] = []
    for label, rel in (("输出目录", "reports"), ("缓存目录", "data/cache"), ("日志目录", "logs")):
        target = base / rel
        target.mkdir(parents=True, exist_ok=True)
        targets.append((label, str(target)))
    return targets


@pytest.fixture(scope="session", autouse=True)
def _isolate_process_wide_state_paths(tmp_path_factory):
    """进程级（session）钉死会**活过用例 teardown** 的落盘路径。

    有些状态写入发生在后台线程/延迟回调里：用例 teardown 时函数级 monkeypatch 已
    还原，线程再解析路径就会写回真实 `data/state/`。这里用 session 级 MonkeyPatch
    在整个测试进程内固定这些路径（不随单个用例还原）：

    - 数据源熔断状态（`DataSourceRegistry._get_breaker_state_path`）：真实运行里
      熔断失败上下文会带测试网络守卫的报错文本，一旦落真实文件会污染生产熔断状态。
    """
    import pytest as _pytest

    from src.python.core.provider_registry import DataSourceRegistry

    base = tmp_path_factory.mktemp("process_state")
    state_dir = base / "data" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            DataSourceRegistry,
            "_get_breaker_state_path",
            staticmethod(lambda: str(state_dir / "circuit_breaker.json")),
        )
        yield


@pytest.fixture(autouse=True)
def _reset_market_snapshot_bucket():
    """每个用例前清空行情口径桶 memo。

    桶是「一份报告判定一次」的进程级状态：不清会让用例互相遮蔽（先跑的用例把 memo
    填好，后面本该读交易日历的用例直接命中 memo → 漏声明离线也能过），表现为
    「整套跑绿、单跑某文件红」这种顺序依赖。清掉后每个用例的判定都是真的。
    """
    from src.python.core.market_hours import reset_market_snapshot

    reset_market_snapshot()
    yield
    reset_market_snapshot()


@pytest.fixture(autouse=True)
def _isolate_sensitive_paths(tmp_path, monkeypatch, _doctor_probe_targets):
    """自动将 config.json 和缓存目录重定向到临时目录。

    防止测试运行意外修改用户的真实配置文件（data/config/config.json）、
    LLM 密钥文件（data/config/llm_key.json）、缓存文件（data/cache/）、
    持仓快照（data/history/snapshots/）等。

    机制：
    - 替换 _config_defaults._CONFIG_FILE → tmp_path/data/config/config.json
    - 替换 cache._CACHE_DIR → tmp_path/data/cache
    - 设置 DOC_DRIFT_SNAPSHOT_CACHE → tmp_path/data/cache/test_coverage_snapshot.json
      （check-doc-drift 测试计数快照缓存，见 _path_isolation.seed_sensitive_path_isolation）
    - 设置 TEST_REDUNDANCY_CACHE → tmp_path/data/cache/test_redundancy_facts.json
      （check-test-redundancy 按文件事实缓存，同上重定向）
    - 设置 CHECK_CONCLUSION_CACHE_DIR → tmp_path/data/cache/guard_conclusions
      （结论缓存目录，同上重定向；当前接入：doc-traces / semantic-index / doc-links /
       code-traces / requirement-trace / doc-drift）
    - 替换 HISTORY_SNAPSHOT_DIR → tmp_path/data/history/snapshots
    - 替换去重锚点语料路径 → tmp_path/data/calibration/dedup_anchors.jsonl（采集默认开，
      防用例把测试标题写进阈值校准语料）
    - 清除 config 内存缓存，使 get_config() 从临时路径读取
    （无文件时自动回退到 _DEFAULT_CONFIG 默认值）

    注意：本 fixture 不影响 holdings_dir/output_dir 等配置值本身，
    测试如需使用真实文件读写，应在测试类中自行 setup 隔离。
    """
    seed_sensitive_path_isolation(monkeypatch, tmp_path, _doctor_probe_targets)
    # 注：llm_settings.json 不在此处 seed 隔离路径。需要读写真实配置的测试
    # （如 test_all_keys_tracked 检查代码 vs 配置文件的键名一致性），
    # 应直接从 PROJECT_ROOT 读取真实文件，而非依赖隔离路径的副本。


@pytest.fixture
def holdings_path_isolated(tmp_path, monkeypatch):
    """把 holdings_dir/holdings_filename 重定向到临时目录（正式覆盖类测试专用）。

    防止正式模式测试覆盖真实 data/holdings/。autouse 不可用——部分既有测试
    断言默认 holdings_dir 路径，全量重定向会破坏它们。测试内需自行在
    tmp_path/holdings/ 下构造正式持仓文件（文件名 = 本 fixture 的
    holdings_filename），再用 ``monkeypatch.setitem`` 调整配置。
    """
    import src.python.config._config_defaults as _cfg_defaults
    import src.python.config._core as _cfg_core

    monkeypatch.setitem(_cfg_defaults._DEFAULT_CONFIG, "holdings_dir", str(tmp_path / "holdings"))
    monkeypatch.setitem(_cfg_defaults._DEFAULT_CONFIG, "holdings_filename", "测试持仓.xlsx")
    _cfg_core._clear_config_cache()
    return {"holdings_dir": str(tmp_path / "holdings"), "holdings_filename": "测试持仓.xlsx"}


@pytest.fixture(autouse=True)
def _isolate_report_output_dir(tmp_path, monkeypatch):
    """报告输出目录兜底防线：指向项目真实 reports/ 的输出一律重定向到临时目录。

    敏感路径隔离（_isolate_sensitive_paths）不覆盖 output_dir/reports，依赖各
    测试自行 setup；测试若漏传输出目录（如 generate_report 在 config 缺
    output_dir 时 fallback 到相对路径 "reports"），会真实写入项目 reports/
    目录（累积空页签残留）。本 fixture 在两个真实落盘入口把指向项目真实
    reports/ 的输出透明重定向到 tmp_path/reports：

      - Excel：excel_writer.save_workbook —— excel_module_loader 在运行时
        `from excel_writer import save_workbook`，取到的是被 patch 后的模块
        属性，故 excel_generator 报告链路天然覆盖。
      - HTML：html_save._save_html_report 与 html_writer._save_html_report
        两处一起 patch —— html_writer 模块 import 时已拷贝引用，需补 patch
        调用方名字；函数内动态查模块全局，patch 模块属性必生效。

    显式指向临时目录的测试不受影响；测试自身 patch 写盘函数（mock）会覆盖
    本包装。判定仅基于"解析后是否等于项目真实 reports 目录"。
    """
    apply_report_output_isolation(monkeypatch, tmp_path)
