"""报告编排共享层 — TUI 和 CLI 共用。

本文件为聚合门面：
  - 风格因子/行业 Beta 计算族 → `_report_factor_metrics.py`
  - 市场温度/持仓相关性       → `_report_aux_metrics.py`
门面保留主编排入口（`generate_report`）、完整数据准备（`prepare_report_data`）、
估值分位编排（`compute_valuation_data`/`_fetch_valuation_for_code`，其内部
依赖门面命名空间解析被 mock patch 的辅助函数）并 re-export 子模块符号。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.python.report.progress import ProgressReporter
from src.python.report.run_integrity import bind_health, bind_perf, guard_run

# ── 子模块 re-export ────────────────────────────────────
from src.python.report._report_aux_metrics import (  # noqa: F401
    compute_correlation_data,
    compute_market_temperature_data,
)
from src.python.report._report_factor_metrics import (  # noqa: F401
    _fetch_holding_bars,
    compute_factor_exposure_data,
    compute_industry_beta_data,
)

from ._orchestrator_data import (  # noqa: F401
    _fetch_valuation_for_code,
    _penetrated_targets,
    _real_valuation_for_code,
    compute_cost_position_data,
    compute_financial_indicator_data,
    compute_financial_report_digest_data,
    compute_purchase_status_data,
    compute_valuation_data,
    prepare_report_data,
)

from src.python.config import resolve_output_dir

logger = __import__("logging").getLogger("invest")


# ── 数据结构 ───────────────────────────────────────────────


@dataclass
class ReportResult:
    """报告生成结果。"""

    holdings_ok: bool = False
    excel_ok: bool = False
    html_ok: bool = False
    news_ok: bool = True
    history_ok: bool = True
    report_generated: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        if not self.report_generated:
            return 2
        if self.errors:
            return 1
        return 0


def _read_section_flags(config: dict) -> dict:
    """从 config 读取章节可见性开关，返回统一字典。"""
    from src.python.config import (
        is_enable_fund_deep_analysis,
        is_enable_history,
        is_enable_llm,
        is_enable_news,
        is_enable_portfolio_evolution,
    )

    return {
        "fund_deep_analysis": is_enable_fund_deep_analysis(config),
        "news": is_enable_news(config),
        "history": is_enable_history(config),
        "evolution": is_enable_portfolio_evolution(config),
        "llm": is_enable_llm(config),
    }


# ── prepare_report_data ──
# ★ config 参数已为必传


# ── 估值分位 编排 ──
# 估值族留在门面：compute_valuation_data 内部经门面命名空间调用


# _fetch_valuation_for_code（测试 patch 该路径），不可整体迁移。


# ── 产物类型语义 ──


def artifacts_for_report_type(report_type: str) -> tuple[str, ...]:
    """报告类型 → 产物 kind 序列（类型语义与 generate_report 生成分支同源）。

    basic → 仅 Excel；both/full → HTML + Excel。Web 产物按钮等消费方从本函数
    派生，禁止在渠道层镜像同一类型规则。

    Returns:
        kind 元组（"html" / "xlsx"），顺序为展示顺序。
    """
    if report_type in ("both", "full"):
        return ("html", "xlsx")
    return ("xlsx",)


# ── generate_report ──


@guard_run
def generate_report(
    holdings: list,
    config: dict,
    reporter: ProgressReporter,
    report_type: str = "basic",
    fetch_history: bool | None = None,
    force_llm: bool = False,
    force_llm_modules: list[str] | None = None,
    output_dir: str | None = None,
    transactions: list | None = None,
    dividends: list | None = None,
    *,
    snapshot_namespace: str | None = None,
) -> ReportResult:
    """生成投资分析报告。

    basic: 仅 Excel（无数据准备/快照/历史）
    both:  HTML+Excel（不含 LLM）
    full:  HTML+Excel+LLM

    Args:
        fetch_history: 是否获取组合历史走势数据（as-if 模拟），仅 both/full 有效。
            None 表示未显式指定，按 `config.history.fetch_mode` 决定
            （默认 auto，即获取）
        transactions: 交易流水记录（「交易流水」页签，无则 None）。
            成本流水子模块（功能开关 `cost_lots`）开启时用于成本分档 + XIRR
        dividends: 分红流水记录（「分红流水」页签，无则 None）。
            成本流水子模块开启时用于分红累计 + XIRR
        snapshot_namespace: 快照隔离域（None=共享主目录；如 "web"=web 试算域）。
            仅 both/full 生效；快照对比/组合演进/快照差异均在本域内闭环。
    """
    result = ReportResult()

    # 生成入口静默自动清理过期缓存（尽力而为：清理失败绝不影响生成——无人值守
    # CLI 定时任务此前无任何自动清理入口，过期缓存文件只增不减）
    from src.python.cache import auto_cleanup_expired

    removed = auto_cleanup_expired()
    if removed:
        logger.info("生成前自动清理过期缓存 %d 个文件", removed)

    if fetch_history is None:
        # 未显式传参 → 委托 history_policy 解析（off/auto/prompt 单一事实来源）：
        # 非交互场景 prompt 按获取处理，TUI 通过注入 ask 回调交互询问。
        from src.python.report.history_policy import resolve_fetch_history

        fetch_history = resolve_fetch_history(config)

    # 实验性功能状态日志（红色高亮）
    from src.python.config.features import log_experimental_features

    log_experimental_features()

    if report_type == "basic":
        # basic 路径：仅生成 Excel，不调 prepare_report_data / capture_snapshot / fetch_history_data
        from src.python.config import is_enable_action, is_enable_cost_lots
        from src.python.core.perf import PerfCollector
        from src.python.core.registry import get_report_section_order
        from src.python.report._report_health import _collect_health_checks, _spawn_health_checks
        from src.python.report.excel_generator import generate_excel_report

        perf = PerfCollector(report_type="basic", holdings=holdings, stage_announcer=reporter.stage_progress)
        bind_perf(perf)
        sec_order = get_report_section_order(config)
        output = output_dir or resolve_output_dir(config)

        # 后台启动健康检查（与 Excel 生成并行）
        _health_fut = _spawn_health_checks()
        bind_health(_health_fut, "basic", holdings)

        try:
            perf.start("Excel 生成")
            generate_excel_report(
                holdings,
                include_news=False,
                output_dir=output,
                section_order=sec_order,
                progress=reporter,
                # 数据质量仪表盘子模块开关（basic 无行情数据，品种覆盖区块显示降级占位）
                # 数据质量仪表盘已内置恒开（开关移除，见 changelog）；参数保留待清理
                enable_data_quality=True,
                # 行动建议章节开关（basic 纯算法可见；action_data 由 excel_generator
                # 就地由行情明细构建——basic 不经编排层，无 pipeline_data 注入）
                enable_action=is_enable_action(config),
                # 成本流水子模块开关 + 交易/分红流水（汇总/市值/分类页签渲染成本分档 + XIRR + 分红累计）
                enable_cost_lots=is_enable_cost_lots(),
                transactions=transactions,
                dividends=dividends,
            )
            perf.stop()
            result.excel_ok = True
            result.holdings_ok = True
            result.report_generated = True
        except Exception:
            perf.add_error("Excel 报告生成失败")
            reporter.add_error("Excel 报告生成失败（详情请查看日志文件 logs/app.log）")
            logger.exception("生成 Excel 报告失败")
            result.errors.append("Excel 报告生成失败")

        perf.save()
        _collect_health_checks(_health_fut, "basic", holdings)
        return result

    if report_type == "both":
        from src.python.report._report_generation import _generate_report_both

        return _generate_report_both(
            holdings,
            config,
            reporter,
            fetch_history=fetch_history,
            output_dir=output_dir,
            transactions=transactions,
            dividends=dividends,
            snapshot_namespace=snapshot_namespace,
        )

    if report_type == "full":
        from src.python.report._report_generation import _generate_report_full

        return _generate_report_full(
            holdings,
            config,
            reporter,
            fetch_history=fetch_history,
            force_llm=force_llm,
            force_llm_modules=force_llm_modules,
            output_dir=output_dir,
            transactions=transactions,
            dividends=dividends,
            snapshot_namespace=snapshot_namespace,
        )

    result.report_generated = True
    reporter.info("generate_report: 骨架模式—未知 report_type")
    return result
