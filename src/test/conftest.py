"""conftest.py — 全局 pytest 配置与标记注册入口（夹具实现按域下沉 `src/test/_conftest_*.py`）。

标记分组（支持 -m 选择运行）：
  - scenario: 全部业务场景（S0a-S0d + S1-S33 + T1-T21）
  - llm: LLM 相关测试（全部 mock，无需 API key）
  - edge: 边缘/异常场景测试 — 必须放在 *_edge.py 文件中
  - smoke / data / integration（详见各 marker 说明）

用法：
  cd <项目根目录>
  pytest src/test/ -m "smoke"                                    # 仅冒烟
  pytest src/test/ -m "not llm"                                  # 排除 LLM
  pytest src/test/ -m "scenario"                                 # 全部场景
  pytest src/test/                                             # 全量运行

本文件只留标记注册与会话级兜底，夹具/钩子按域下沉到 `src/test/_conftest_*.py`，再由下方
import 绑定回本模块命名空间（pytest 只认入口模块里的夹具与钩子，import 不可删）：
  - `_conftest_isolation.py`   敏感路径 / 报告输出 / 机器本地状态隔离
  - `_conftest_state_reset.py` 各模块单例、缓存与开关状态的用例级复位
  - `_conftest_cassette.py`    数据源记录-回放
  - `_conftest_network.py`     外网阻断与离线桩
  - `_conftest_hooks.py`       命令行选项、标记全集与收集期 edge/scenario/标记校验
"""

from __future__ import annotations

# ── 平台收集门（非 POSIX 直接不收集伪终端用例）────────────────────────
# `pty`/`termios` 仅 POSIX 提供：这类测试文件即使自身做了跳过保护，也要**不进收集**
# 才彻底杜绝 `ERROR collecting`（收集期任何模块级副作用都可能变错误，而 CI 跑 Linux
# 结构性看不见）。判定按模块可导入性，不依赖文件名约定。
try:  # pragma: no cover - 非 POSIX 分支在 CI 上不可达
    import pty as _pty_probe  # noqa: F401
except ImportError:  # pragma: no cover - 同上
    collect_ignore = ["unit/ui/test_live_status_edge.py"]
from src.test._conftest_cassette import (  # noqa: F401 — 夹具/钩子须绑定在入口命名空间
    _auto_reset_transport_factory,
    _cassette_names,
    _install_cassette_replay,
    _declared_recording_anchor,
    _auto_reset_chain_overrides,
    _auto_reset_self_review_carrier,
    cassette_recording,
)
from src.test._conftest_hooks import (  # noqa: F401 — 夹具/钩子须绑定在入口命名空间
    _KNOWN_MARKERS,
    _BUILTIN_MARKERS,
    pytest_addoption,
    _skip_live_unless_requested,
    pytest_collection_modifyitems,
)
from src.test._conftest_isolation import (  # noqa: F401 — 夹具/钩子须绑定在入口命名空间
    _doctor_probe_targets,
    _isolate_process_wide_state_paths,
    _reset_market_snapshot_bucket,
    _isolate_sensitive_paths,
    holdings_path_isolated,
    _isolate_report_output_dir,
)
from src.test._conftest_network import (  # noqa: F401 — 夹具/钩子须绑定在入口命名空间
    _block_external_network,
    offline_external_sources,
)
from src.test._conftest_state_reset import (  # noqa: F401 — 夹具/钩子须绑定在入口命名空间
    _auto_reset_provider_registry,
    _auto_reset_concurrency_governor,
    _restore_menu_items,
    _auto_reset_module_state,
    _restore_logger_state,
    _auto_reset_config_cache,
    _auto_reset_config_session,
    _auto_reset_last_reason,
    _auto_reset_doc_miss_hits,
    _auto_reset_fingerprint_audit,
    _auto_reset_run_history_state,
    _restore_llm_pricing_state,
    _auto_reset_market_hours_memo,
    _auto_reset_trading_calendar_memo,
    _auto_reset_thinking_wait_total,
    _auto_reset_fact_fix_counts,
    _auto_reset_llm_failure_state,
    _auto_reset_adapter_registry,
    _auto_reset_credential_specs,
    _auto_reset_datasink_limiter,
    _auto_reset_hithink_limiter,
    _auto_reset_llm_fingerprint_baseline,
    _auto_reset_anchor_state,
    _auto_reset_run_manager,
    _auto_reset_report_qa_sessions,
    _auto_reset_indicator_breaker,
    _auto_reset_feature_flags,
    _auto_reset_runtime_overrides,
    _reset_degradation_tracker,
    _reset_provider_usage,
    _auto_reset_cost_tracker,
    _auto_reset_llm_module_failure,
    _mock_market_hours_api,
)


def _install_session_state_fallback_isolation() -> None:
    """会话级兜底隔离：降级状态文件的默认路径。

    用例级 ``_isolate_sensitive_paths`` 把 ``_default_persist_path`` 指向 ``tmp_path``，
    但**后台批量线程**（如 ``fetcher/industry.py`` 经 ``BatchDispatcher`` 派发的取数）
    可能活过用例 teardown——此时 monkeypatch 已还原，线程内 ``get_tracker()`` 会新建
    实例并落到真实路径写盘，污染用户的 ``data/state/.degradation_state.json``。

    故在会话开始即把该函数替换为「会话级临时目录」实现：用例内仍被 ``tmp_path``
    覆盖，teardown 后回落到本兜底值而非真实路径，测试全程不触碰真实状态文件。
    """
    import tempfile
    from pathlib import Path

    from src.python.core import degradation as data_status

    fallback = Path(tempfile.mkdtemp(prefix="pytest-state-")) / ".degradation_state.json"
    data_status._default_persist_path = lambda: str(fallback)


def pytest_configure(config):
    """注册自定义标记，避免 pytest 警告。"""
    config.addinivalue_line("markers", "scenario: 业务场景集成测试（S0a-S0d + S1-S33 + T1-T21）")
    config.addinivalue_line("markers", "scenario_basic: 基础业务链路（S1-S5 + S0a-S0d + S21-S28 + S29-S33）")
    config.addinivalue_line("markers", "scenario_resilience: 异常容错场景（S6-S10）")
    config.addinivalue_line("markers", "scenario_llm: LLM 场景组合（S11-S20）")
    config.addinivalue_line("markers", "scenario_perf: 性能基准测试")
    config.addinivalue_line("markers", "scenario_security: 安全基线测试")
    config.addinivalue_line("markers", "scenario_datetime: 日期/时间场景（T1-T21）")
    config.addinivalue_line("markers", "scenario_stock: 场景 S1 — 纯股票组合")
    config.addinivalue_line("markers", "scenario_fund: 场景 S2 — 纯基金组合")
    config.addinivalue_line("markers", "scenario_mixed_accounts: 场景 S3 — 混合多账户")
    config.addinivalue_line("markers", "scenario_new_holdings: 场景 S4 — 新持仓无缓存")
    config.addinivalue_line("markers", "scenario_cache_hit: 场景 S5 — 缓存全命中")
    config.addinivalue_line("markers", "scenario_bond: 场景 S6 — 纯债券基金组合")
    config.addinivalue_line("markers", "scenario_network_down: 场景 S7 — 网络中断降级")
    config.addinivalue_line("markers", "scenario_single_holding: 场景 S8 — 单账户单持仓")
    config.addinivalue_line("markers", "scenario_zero_cost: 场景 S9 — 零成本持仓")
    config.addinivalue_line("markers", "scenario_extreme: 场景 S10 — 极端值")
    config.addinivalue_line("markers", "unit: 单元测试总标记")
    config.addinivalue_line("markers", "unit_providers: 数据源提供商单元测试")
    config.addinivalue_line("markers", "unit_fetcher: 数据获取调度单元测试")
    config.addinivalue_line("markers", "unit_llm: LLM 模块单元测试")
    config.addinivalue_line("markers", "unit_news: 新闻模块单元测试")
    config.addinivalue_line("markers", "unit_report: 报告生成单元测试")
    config.addinivalue_line("markers", "unit_config: 配置管理单元测试")
    config.addinivalue_line("markers", "unit_core: 核心基础设施单元测试")
    config.addinivalue_line("markers", "unit_cli: CLI 命令行模式单元测试")
    config.addinivalue_line("markers", "unit_ui: TUI/UI 交互单元测试")
    config.addinivalue_line("markers", "unit_analysis: 分析计算模块单元测试（流动性/再平衡/汇率/无风险利率）")
    config.addinivalue_line("markers", "unit_scripts: scripts/ 工程脚本单元测试（历史痕迹检查/版本一致性等）")
    config.addinivalue_line(
        "markers",
        "real_repo: 真实仓库全量扫描的守护冒烟（pre-commit 钩子与 CI guards 已对同一棵工作树跑过同一守护，"
        "故不进 dev-verify，只在 verify / CI 全量档执行）",
    )
    config.addinivalue_line("markers", "unit_web: Web 入口（src/python/web/）单元测试")
    config.addinivalue_line("markers", "unit_qa: 报告对话式追问（src/python/qa/）单元测试")
    config.addinivalue_line("markers", "llm: LLM 相关测试（全部 mock，无需 API key）")
    config.addinivalue_line("markers", "edge: 边缘/异常场景测试 — 必须放在 *_edge.py 文件中，不得与普通测试混搭")
    config.addinivalue_line("markers", "smoke: 冒烟测试（快速验证核心功能）")
    config.addinivalue_line("markers", "data: 数据正确性验证测试")
    config.addinivalue_line("markers", "integration: 集成测试—模块间契约/全链路/缓存一致性")
    config.addinivalue_line("markers", "integration_contract: 模块间接口契约验证")
    config.addinivalue_line("markers", "integration_isolation: 错误隔离业务语义验证")
    config.addinivalue_line("markers", "integration_news_pipeline: 新闻流水线全链路")
    config.addinivalue_line("markers", "integration_cache: 跨模块缓存一致性验证")
    config.addinivalue_line("markers", "integration_tui: TUI → Handler 路由集成测试")
    config.addinivalue_line("markers", "integration_cli: CLI 命令行模式集成测试")
    config.addinivalue_line(
        "markers", "live: 真实网络验证套件（opt-in，默认跳过，仅 `-m live` 或 `--run-live` 运行；不入门禁）"
    )
    config.addinivalue_line(
        "markers",
        'cassette: 声明用例所需的已录制数据源响应（`@pytest.mark.cassette("名称", source="源")`），'
        "运行期离线回放真实响应体，不发起网络请求",
    )
    _install_session_state_fallback_isolation()
