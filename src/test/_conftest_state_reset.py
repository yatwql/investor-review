"""conftest 夹具实现 — 各模块单例、缓存与开关状态的用例级自动复位。

本模块由入口 `src/test/conftest.py` 显式 import 回来注册（pytest 只认入口模块命名空间里的
夹具与钩子）；改动后跑 `pytest src/test -q` 验证收集与自动复位仍然生效。
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _auto_reset_provider_registry():
    """自动重置 DataSourceRegistry 单例，防止测试间状态污染。

    每个测试执行前清空注册信息、熔断状态和会话缓存。
    依赖 provider_registry.get_registry().reset() 而非重新创建实例。
    """
    from src.python.core.provider_registry import get_registry

    get_registry().reset()


@pytest.fixture(autouse=True)
def _auto_reset_concurrency_governor():
    """自动重置进程级并发预算账本。

    租约跨用例残留会让后续池被误缩容（表现为「偶发」少一个 worker 的诡异时序），
    口径与 provider registry 单例重置一致：只清账本，不改任何配置值。
    """
    from src.python.core.concurrency import GOVERNOR

    GOVERNOR.reset()


@pytest.fixture(autouse=True)
def _restore_menu_items():
    """自动还原 ``MENU_ITEMS``（模块级可变列表），防止功能开关裁剪串扰。

    ``tui_menu._apply_feature_gates()`` 用切片赋值**原地裁剪**全局菜单（菜单项整体
    消失而非置灰），裁剪后不会自动恢复。任一用例触发裁剪（如把 doctor_check 关掉）
    就会让同进程后续用例看到项数不足的菜单——单进程顺序下通常不暴露，xdist 分片
    改变用例顺序后即表现为「页脚断言缺退出键」类随机失败。
    """
    from src.python.tui import tui_menu

    snapshot = list(tui_menu.MENU_ITEMS)
    yield
    tui_menu.MENU_ITEMS[:] = snapshot


@pytest.fixture(autouse=True)
def _auto_reset_module_state():
    """复位各模块级会话态 / 注册标志 / 限速器单例（进/出两侧），防跨用例串扰。

    这些状态都不是「配置」，而是**运行期会话痕迹**：注入的传输层工厂、惰性注册标记、
    上一次取数的源命中快照、按键解析残留、失败标记……单个模块各自持有，一旦上一条用例
    写入、本用例读到，断言就变成顺序相关的隐式依赖（xdist 换分片即随机红）。

    口径与 ``_auto_reset_provider_registry`` 一致：复位只是把状态置回「未载入」，
    不改变任何默认值、不发起取数。需要某项携住状态跑完整个用例的，自行 patch。
    """

    def _reset() -> None:
        from src.python.cache import _stats as cache_stats
        from src.python.config._llm_pricing import invalidate_pricing_cache
        from src.python.config._llm_settings import invalidate_llm_config_cache
        from src.python.core import circuit_breaker, doctor, http_client, rate_limit_state
        from src.python.fetcher import batch, bond_yield, factor_catalog_loader, source_adapter
        from src.python.llm import observation, pacing, research_contract
        from src.python.providers import (
            akshare_extras,
            cninfo,
            eastmoney,
            eastmoney_industry,
            news_aggregator,
            tiantian_holdings,
        )
        from src.python.llm.fact_checker import _coverage as fact_check_coverage
        from src.python.report import fund_style_base
        from src.python.tui import report_artifacts, tui_handlers, tui_keys

        cache_stats.reset_cache_stats()
        invalidate_llm_config_cache()
        invalidate_pricing_cache()
        circuit_breaker.reset_circuit_text()
        rate_limit_state.reset_push2_limit_state()
        doctor.reset_adapter_survey()
        http_client.reset_transport_factory()
        batch.clear_rate_limiter_cache()
        factor_catalog_loader.invalidate_catalog_cache()
        bond_yield.reset_bond_yield_api_cache()
        source_adapter.reset_adapter_registry()
        observation.clear_llm_observation()
        research_contract.reset_contract_state()
        pacing.reset_policies()
        akshare_extras.reset_failure_state()
        cninfo.reset_cninfo_limiter()
        cninfo.reset_cninfo_unreachable()
        eastmoney.reset_eastmoney_pager_limiter()
        eastmoney_industry.reset_eastmoney_industry_limiter()
        news_aggregator.reset_last_source_results()
        tiantian_holdings.reset_quarter_walk_anchor()
        fund_style_base.reset_tencent_registration()
        report_artifacts.reset_open_failure_memo()
        tui_handlers.reset_busy_state()
        tui_keys.reset_key_parser_state()
        fact_check_coverage.reset_numerical_coverage()

    _reset()
    yield
    _reset()


@pytest.fixture(autouse=True)
def _restore_logger_state():
    """隔离 ``core.logger`` 的模块级生效值，免日志配置用例把临时路径/级别留给后续用例。

    这六个常量由 ``_apply_logger_config`` 从 env + ``logger.json`` 推导后**原地改写**：
    用例 monkeypatch 的只是输入（配置路径 / 环境变量），推导结果不会跟着回退。历史同类
    事故见 ``_restore_llm_pricing_state``（定价时段串到下一条用例，单跑绿、并行偶发红）。

    不给它接 ``reload_logger_config()``：那每次都要读文件并重配 handler——全量套件会因此多出上万次
    读盘，还会与 pytest 自己的捕获 handler 抢位置。只回填常量，零 I/O。
    """
    from src.python.core import logger as logger_mod

    log_file = logger_mod._LOG_FILE
    max_bytes = logger_mod._LOG_MAX_BYTES
    backup_count = logger_mod._LOG_BACKUP_COUNT
    console_color = logger_mod._CONSOLE_COLOR
    file_level = logger_mod._CONFIG_FILE_LEVEL
    console_level = logger_mod._CONFIG_CONSOLE_LEVEL
    yield
    logger_mod._LOG_FILE = log_file
    logger_mod._LOG_MAX_BYTES = max_bytes
    logger_mod._LOG_BACKUP_COUNT = backup_count
    logger_mod._CONSOLE_COLOR = console_color
    logger_mod._CONFIG_FILE_LEVEL = file_level
    logger_mod._CONFIG_CONSOLE_LEVEL = console_level


@pytest.fixture(autouse=True)
def _auto_reset_config_cache():
    """自动丢弃 ``tui_menu._config_cache``，防止配置缓存跨用例串扰。

    该缓存是模块级字典，首次 ``refresh_config()`` 后一直存在；用例读取时如走
    ``get_config_cache()``（渲染页头/菜单的路径），拿到的就是**上一条用例**载入的
    那份配置（含它自己的 monkeypatch 结果）。故与 ``_restore_menu_items`` 同习语，
    在每个用例前后都回到「未载入」基线。
    """
    from src.python.tui import tui_menu

    tui_menu.reset_config_cache()
    yield
    tui_menu.reset_config_cache()


@pytest.fixture(autouse=True)
def _auto_reset_config_session():
    """自动关闭配置面板会话，防止撤销记录跨用例串扰。

    ``handlers_config._session`` 是模块级可变单例，``_apply_edit`` 在它非空时
    **必然**把每次写盘记入撤销栈。面板自身在进入/退出时 ``reset``/``close``，
    但直接调 ``_apply_edit`` 的用例并不进面板——上一用例留下的会话会让本用例的
    写入记入别人栈里（后续 ``u`` 用例据此误掽到不存在的改动）。

    故意不依赖面板进出：连直接调用写盘路径的用例也回到「无会话」基线。
    """
    from src.python.tui import handlers_config

    handlers_config.close_config_session()
    yield
    handlers_config.close_config_session()


@pytest.fixture(autouse=True)
def _auto_reset_last_reason():
    """自动清除「provider 失败原因」线程本地载体，防止测试间状态污染。

    该载体（``providers/_utils`` 的 ``_last_reason``）是**消费即清**的：provider
    写入后由链路在返回空时取用。但不少 provider 用例直接调 ``datasink``/``cninfo``
    的取数函数只看返回值（不消费原因）——写入的原因便残留在该测试所在 worker 的
    主线程槽位里，污染同 worker 中**下一个**读载体的用例（实测 CI 3.11：
    ``test_reason_is_thread_local`` 读到 500 用例残留的 ``'HTTP 500'``）。

    与 ``_auto_reset_provider_registry`` 同习语：模块级可变状态在每个测试前复位，
    使用例不依赖执行顺序/worker 分配。
    """
    from src.python.providers import utils

    utils.clear_last_reason()


@pytest.fixture(autouse=True)
def _auto_reset_doc_miss_hits():
    """清零「空正文负缓存命中」按轮计数，避免用例间串味。"""
    from src.python.fetcher.financial_report import reset_doc_miss_hits

    reset_doc_miss_hits()


@pytest.fixture(autouse=True)
def _auto_reset_fingerprint_audit():
    """清空指纹组件审计基线，避免用例间「上次报告」串味。"""
    from src.python.llm.generators_orchestrator import reset_fingerprint_audit

    reset_fingerprint_audit()
    yield
    reset_fingerprint_audit()


@pytest.fixture(autouse=True)
def _auto_reset_run_history_state():
    """清空历史 chain 的单轮状态（窗口复用 memo + 空结果连续计数）。

    两者都是「本轮报告」语义的模块级状态：不重置时用例会从上游用例的
    memo 里直接拿数据，表现为「mock 未被调用」或「全量刷新未发生」。
    """
    from src.python.fetcher.chain_incremental import reset_run_history_state
    from src.python.report._run_scope import clear_run_memo

    reset_run_history_state()
    clear_run_memo()
    yield
    reset_run_history_state()
    clear_run_memo()


@pytest.fixture(autouse=True)
def _restore_llm_pricing_state():
    """隔离 llm.pricing 模块级状态，避免定价用例的 reload 影响后续用例。

    历史缺陷：`test_llm_pricing` 用临时 llm_pricing_ref.json 调 `reload_pricing()`，
    结束后只失效配置缓存、未恢复 `PRICING_PEAK_PERIODS`；同一 xdist worker 中后跑的
    `test_peak_periods_defaults` 读到自定义时段（单跑绿、并行偶发红）。
    """
    import copy

    from src.python.llm import pricing

    snapshot = {
        "merged": copy.deepcopy(pricing.PRICING_MERGED),
        "currency": pricing.PRICING_CURRENCY,
        "peak": list(pricing.PRICING_PEAK_PERIODS),
        "idle": list(pricing.PRICING_IDLE_PERIODS),
        "weekend": pricing.PRICING_WEEKEND_ALWAYS_IDLE,
        "holiday": pricing.PRICING_HOLIDAY_ALWAYS_IDLE,
        "timezone_name": pricing.PRICING_TIMEZONE_NAME,
        "timezone": pricing.PRICING_TZ,
        "loaded": pricing._PRICING_LOADED,
    }
    yield
    pricing.PRICING_MERGED.clear()
    pricing.PRICING_MERGED.update(snapshot["merged"])
    pricing.PRICING_CURRENCY = snapshot["currency"]
    pricing.PRICING_PEAK_PERIODS[:] = snapshot["peak"]
    pricing.PRICING_IDLE_PERIODS[:] = snapshot["idle"]
    pricing.PRICING_WEEKEND_ALWAYS_IDLE = snapshot["weekend"]
    pricing.PRICING_HOLIDAY_ALWAYS_IDLE = snapshot["holiday"]
    pricing.PRICING_TIMEZONE_NAME = snapshot["timezone_name"]
    pricing.PRICING_TZ = snapshot["timezone"]
    pricing._PRICING_LOADED = snapshot["loaded"]


@pytest.fixture(autouse=True)
def _auto_reset_market_hours_memo():
    """自动复位 market_hours 的进程内分钟级 memo 与日志去重状态。

    memo 按「进程内分钟」缓存开闭市判定：不复位时，前一个用例（常 mock
    config/API 层）留在 memo 里的结果会让后一个用例直接命中旧值、跳过其
    mock 路径，用例结果随执行顺序漂移。与 ``_auto_reset_last_reason`` 同习语。
    """
    from src.python.core import market_hours

    market_hours.reset_memo_state()
    yield
    market_hours.reset_memo_state()


@pytest.fixture(autouse=True)
def _auto_reset_trading_calendar_memo():
    """自动复位交易日历的进程内 memo（与 market_hours memo 同习语）。

    不复位时，前一个用例（常 monkeypatch cache.get / 临时缓存目录）留在 memo 里的
    日历会让后一个用例绕过它自己的取数路径，用例结果随执行顺序漂移。
    """
    from src.python.core import trading_calendar

    trading_calendar._reset_calendar_memo()
    yield
    trading_calendar._reset_calendar_memo()


@pytest.fixture(autouse=True)
def _auto_reset_thinking_wait_total():
    """自动复位 thinking 串行等待累计（模块级累加器，跨用例不得串味）。"""
    from src.python.llm._llm_dispatch import reset_thinking_wait_total

    reset_thinking_wait_total()
    yield
    reset_thinking_wait_total()


@pytest.fixture(autouse=True)
def _auto_reset_fact_fix_counts():
    """自动复位事实校验自动修正计数（模块级累加器，跨用例不得串味）。"""
    from src.python.llm.fact_checker import reset_auto_correction_counts

    reset_auto_correction_counts()
    yield
    reset_auto_correction_counts()


@pytest.fixture(autouse=True)
def _auto_reset_llm_failure_state():
    """自动复位 LLM 调用失败的模块级/线程局部状态，防止测试间污染。

    覆盖 ``llm/api_base`` 两处：全局 ``_last_llm_failure_reason``（成功时清除、
    失败时写入，供 call_llm 切换日志与 call_claude 安全网判定）与线程局部
    「服务端错误信封」标志（_extract_content 写入，安全网据此区分服务端故障
    与真·空响应）。安全网用例常 mock call_llm_with_retry，写入路径不执行，
    残留值会让安全网判定随执行顺序漂移。与 ``_auto_reset_last_reason`` 同习语。
    """
    from src.python.llm import api_base

    api_base.clear_last_llm_failure()
    api_base.clear_last_server_error()
    yield
    api_base.clear_last_llm_failure()
    api_base.clear_last_server_error()


@pytest.fixture(autouse=True)
def _auto_reset_adapter_registry():
    """自动重置数据源适配器注册表，防止测试间状态污染。

    每个测试执行前先把注册表恢复为「模块导入后」的初始内容（即各适配器模块
    注册的真实适配器），测试中临时注入的适配器不会泄漏到后续用例。
    """
    from src.python.fetcher import source_adapter

    baseline = source_adapter.snapshot_adapters()
    yield
    source_adapter.restore_adapters(baseline)


@pytest.fixture(autouse=True)
def _auto_reset_credential_specs():
    """自动重置数据源凭据声明表，防止测试间状态污染。

    声明表在生产中为空（全部免费源），测试为验证机制会注入合成声明；
    每个测试执行前清空，避免合成声明泄漏到后续用例（尤其会影响
    check-sources / doctor 的凭据预检分支）。
    """
    from src.python.core import datasource_credential

    datasource_credential.reset_credential_specs()


@pytest.fixture(autouse=True)
def _auto_reset_datasink_limiter():
    """重置 DataSinking 限速器单例（读配置一次，跨测试须重建）。"""
    from src.python.providers import datasink

    datasink.reset_datasink_limiter()


@pytest.fixture(autouse=True)
def _auto_reset_hithink_limiter():
    """重置同花顺数据服务限速器单例（读配置一次，跨测试须重建）。"""
    from src.python.providers import hithink

    hithink.reset_hithink_limiter()


@pytest.fixture(autouse=True)
def _auto_reset_llm_fingerprint_baseline():
    """复位跨进程指纹基线的进程内缓存（防用例间串基线）。

    快照文件本身已由 `_isolate_sensitive_paths` 重定向到 tmp_path；这里只清读缓存，
    保证「同一用例内多次调用读到同一份落盘结果」而不会读到上一个用例的快照。
    """
    from src.python.llm.fingerprint_baseline import reset_baseline_cache

    reset_baseline_cache()
    yield
    reset_baseline_cache()


@pytest.fixture(autouse=True)
def _auto_reset_anchor_state():
    """自动重置新闻去重锚点模块单例状态，防止测试间状态污染。

    每个测试执行前清空内存锚点记录列表，避免某测试记录的锚点状态泄漏到
    后续测试（锚点路径已由 _isolate_sensitive_paths 隔离到 tmp_path；
    写侧已无跨轮 key 缓存，不需要额外重置）。
    """
    from src.python.providers import news_dedup_anchor_policy

    # 批内缓冲与「已告警」标记都属写侧（策略层）状态：必须改实际持有者，
    # 改门面 `news_dedup.<同名>` 只是换个副本，状态照旧串到下个用例
    news_dedup_anchor_policy.reset_anchor_records()
    news_dedup_anchor_policy._ANCHOR_SIZE_WARNED = False


@pytest.fixture(autouse=True)
def _auto_reset_run_manager():
    """自动重置 RunManager 单例，防止测试间状态污染。

    每个测试执行前销毁 web.runs 模块级单例，下次 get_run_manager() 重建。
    与 _auto_reset_provider_registry / _reset_degradation_tracker 同模式。
    """
    from src.python.web.runs import reset_run_manager

    reset_run_manager()


@pytest.fixture(autouse=True)
def _auto_reset_report_qa_sessions():
    """自动清空报告追问会话表（qa/session 模块级内存态），防止测试间串会话。

    会话含问答历史/轮数/用量，泄漏会污染后续用例的会话复用与轮数断言；
    与 _auto_reset_run_manager 同模式（额外带 teardown 双保险）。
    """
    from src.python.qa.session import reset_report_qa_sessions

    reset_report_qa_sessions()
    yield
    reset_report_qa_sessions()


@pytest.fixture(autouse=True)
def _auto_reset_indicator_breaker():
    """自动重置指标熔断器单例，防止测试间状态污染。

    每个测试执行前销毁 IndicatorBreaker 实例并清空其状态文件，
    避免某测试记录的断路状态泄漏到后续测试（尤其网关聚合测试）。
    依赖 reset_indicator_breaker() 销毁当前实例，下次 get_indicator_breaker() 重建。
    """
    from src.python.analysis.circuit_breaker_wrapper import reset_indicator_breaker

    reset_indicator_breaker()


@pytest.fixture(autouse=True)
def _auto_reset_feature_flags():
    """自动重置 FEATURE_FLAGS 为默认值，防止测试间 feature 状态泄漏。

    每个测试执行前通过 reset_feature_flags() 恢复出厂默认值。
    需要特定 feature 状态的测试应自行 mock is_feature_enabled()
    或在测试体内调用 set_feature_enabled()，reset fixture 保证不污染下游。
    """
    from src.python.config.features import reset_feature_flags

    reset_feature_flags()


@pytest.fixture(autouse=True)
def _auto_reset_runtime_overrides():
    """自动清空命令行一次性覆写（--chapter / --anonymize 的进程内状态）。

    覆写层是模块级字典，测试直接调用 CLI 覆写函数后若不清理，会串到后续用例
    （读到的 chapter / 匿名化模式不再是配置真值）。
    """
    from src.python.config._runtime_overrides import reset_overrides

    reset_overrides()
    yield
    reset_overrides()


@pytest.fixture(autouse=True)
def _reset_degradation_tracker():
    """自动重置 DegradationTracker 单例，防止测试间状态污染。

    每次测试执行前清空计数器和事件日志。
    依赖 reset_tracker() 销毁当前实例，下次 get_tracker() 重新创建。
    """
    from src.python.core.degradation import reset_tracker

    reset_tracker()


@pytest.fixture(autouse=True)
def _reset_provider_usage():
    """自动清空 provider 归属登记表，防止测试间状态污染。

    ``mark_provider_used`` 的登记表是模块级状态（矩阵「命中源」列的数据源），
    与 _reset_degradation_tracker 同模式：逐用例清空，避免某用例登记的
    provider 归属泄漏到后续用例的 build_data_source_matrix() 输出。
    """
    from src.python.core.degradation import reset_provider_usage

    reset_provider_usage()


@pytest.fixture(autouse=True)
def _auto_reset_cost_tracker():
    """自动重置 cost_tracker 全局状态 + session 用量，防止测试间状态污染。

    问题场景（xdist 并发）：
      测试 A 通过 patch('src.python.llm.session.get_session_usage') 使用 MagicMock，
      同一 worker 上后续的 BudgetManagement 测试调用 get_budget_status() 时，
      get_session_usage() 返回 MagicMock，导致 usage.get('input_tokens', 0) 返回
      MagicMock → max(0, _input_budget - MagicMock) 抛出 TypeError。

    修复策略：
      1. 重置 session 用量，确保 get_session_usage() 返回干净数据
      2. 重置 budget 为默认值，消除自定义预算残留
    """
    from src.python.llm.cost_tracker import DEFAULT_INPUT_BUDGET, reset_budget
    from src.python.llm.session import reset_session_usage

    reset_session_usage()
    reset_budget(DEFAULT_INPUT_BUDGET)


@pytest.fixture(autouse=True)
def _auto_reset_llm_module_failure():
    """自动重置 LLM_MODULE_FAILURE 全局字典，防止测试间状态污染。

       问题场景（xdist 并发）：
         write_llm_sheets() 读取 LLM_MODULE_FAILURE 判断模块是否被禁用（见
         llm_content.py write_llm_sheets），若某测试设置
         LLM_MODULE_FAILURE[key]=FAIL_REASON_DISABLED 后未清理，同一 worker
    上后续 test_content_none 等测试的页签被跳过不写入，占位符断言失败。
    """
    from src.python.llm.prompts import LLM_MODULE_FAILURE

    LLM_MODULE_FAILURE.clear()


@pytest.fixture(autouse=True)
def _mock_market_hours_api(monkeypatch):
    """禁用实时东方财富 push2 API 调用，使用内置默认值判断市场时段。

    `is_market_open()` 有 3 层降级（config → push2 API → 内置默认值），
    本 fixture 跳过第 2 层（push2 HTTP 请求），直接走内置 fallback 判断，
    避免每测试类首次调用时触发 ~1-3s 的网络请求。

    `_is_market_open_fallback()` 基于北京时区工作日 09:30-11:30+13:00-15:00
    判断，在测试环境中稳定返回预期值。不影响任何测试断言——测试依赖的是
    mock 返回的行情数据，而非真实市场状态。
    """
    monkeypatch.setattr(
        "src.python.core.market_hours._is_market_open_official",
        lambda _: None,
    )
