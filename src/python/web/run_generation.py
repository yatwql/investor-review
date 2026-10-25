"""Web 生成执行体（RunManager.executor 注入点）—— 生成链路的执行、产物清单与完成通知。

从 ``web/handlers.py`` 下沉（该文件逼近 1000 行红线；路由分发与生成执行本就是两种职责）：

- **执行体**：``_run_generation`` 薄入口 → ``_run_generation_impl``（读持仓 / 输入模式分派 /
  日预算硬闸 / 调用 ``generate_report`` / 退出码映射 / 上传临时文件清理），复刻
  ``cli/cli.py:_handle_report`` 模板。
- **收尾通知**：``_notify_web_completion`` 按 ``notify`` 配置门控派发 ``completion_notify``
  事件——Web 手动生成与内置定时调度共用本执行体，两条链路的无人值守通知在此统一。
- **产物清单**：``_build_artifacts`` 按 report_type 计算可下载产物（类型语义与文件名各取单源）。
- **输入模式映射**：``_web_input_mode_snapshot_domain`` 试算/正式 → 快照隔离域的唯一事实来源。

调用方：``web/app.py`` 把 ``_run_generation`` 注入 ``RunManager.executor``；``web/handlers.py``
的 run 详情接口调用 ``_build_artifacts``。本模块不依赖 ``web/handlers.py``（无循环导入）；
测试 patch 须指向本模块（调用点所在模块）。
"""

from __future__ import annotations

import logging
import os

from src.python.config import resolve_output_dir

logger = logging.getLogger("invest")

# ── 退出码（对齐 cli.py）──────────────────────────────
_EXIT_SUCCESS = 0
_EXIT_PARTIAL = 1
_EXIT_SEVERE = 2


# ── worker 执行体（RunManager.executor 注入点）────────────────


def _web_input_mode_snapshot_domain(mode: str) -> str | None:
    """生成用途（web 输入模式）→ 快照隔离域：试算→web 试算域 / 正式→共享主目录。

    模式与快照隔离域映射的唯一事实来源（语义名即代码名），避免散落多处。
    试算（trial）：快照隔离到 ``web/`` 域，不污染共享时间线；
    正式（formal）：快照写共享主目录（返回 None = 默认共享域）。
    """
    return "web" if mode == "trial" else None


def _run_generation(state, params: dict) -> int:
    """RunManager 执行体入口：委托 ``_run_generation_impl``，收尾派发完成通知。

    通知契约与 CLI ``_handle_report`` 同构：门控前置（未配置不碰跟踪器）、
    尽力而为（异常只 DEBUG，绝不改变退出码 / run 状态）；Web 手动生成与
    内置定时调度共用本入口——定时无人值守正是通知的核心价值。
    """
    result_box: dict = {}
    exit_code = _run_generation_impl(state, params, result_box)
    _notify_web_completion(state, params, exit_code, result_box.get("result"))
    return exit_code


def _run_generation_impl(state, params: dict, result_box: dict | None = None) -> int:
    """单个 run 的执行体：读持仓 → 建 reporter → generate_report → 映射退出码。

    ``result_box``（可选出参）回传 ``ReportResult``，供收尾通知载荷读取
    excel_ok/html_ok 产物标志；早期严重失败/异常时无 result 可传。

    在 worker 线程执行。每个 run 启动时取一次 ``get_config()`` 快照
    （run 期间不受外部配置修改影响）；产物 output_dir 基于该快照
    保存到 run 记录（产物 URL/下载基于 run 记录而非实时配置）。
    上传临时文件在 finally 中立即删除（§6.1 清理）。

    输入模式分派（试算隔离 vs 正式共享）：
      - 试算（trial，默认）：读上传临时文件，快照写 ``web/`` 隔离域
        （``snapshot_namespace="web"``），不落正式持仓、不写共享快照。
      - 正式（formal）+ 上传：先 ``promote_upload_to_holdings`` 提升临时文件
        为正式持仓（备份旧文件为 .bak），读正式文件，快照写共享主目录。
      - 正式（formal）+ 用存量（use_existing）：直接读正式持仓文件
        （路径仅从 ``get_config()`` 派生，无目录穿越向量），快照写共享主目录。
    正式模式的提升发生在 run 出队后、生成前——报告后续失败（LLM/网络）
    不影响已提交的正式文件（正式模式语义，UI/文档已说明）。
    """
    from src.python.config import get_config
    from src.python.core.reader import read_holdings_with_flows, require_holdings
    from src.python.report.orchestrator import generate_report

    from src.python.web.holdings_update import promote_upload_to_holdings
    from src.python.web.progress import WebProgressReporter
    from src.python.web.upload import discard_file, resolve_file

    mode = params.get("mode", "trial")
    use_existing = bool(params.get("use_existing", False))
    file_id = params.get("file_id")

    try:
        # 每个 run 启动取一次配置快照（run 期间不受外部配置修改影响）
        config = get_config()

        # ── 日预算硬闸（LLM 费用，权威兜底）：超限且未经确认 → 本次运行中止。
        #    覆盖定时调度与直连 API 等不经弹层的链路（create_run 已先挡一道 409）。──
        if params.get("report_type") == "full" and not params.get("budget_ack"):
            from src.python.llm.cost_forecast import budget_status

            _budget = budget_status()
            if _budget.get("exceeded"):
                state.errors.append(
                    f"今日 LLM 费用已达日预算上限（{_budget.get('display', '')}），本次生成已中止；"
                    "确认「用已有结果继续」后重试可继续"
                )
                return _EXIT_SEVERE
        # 输入模式 → 快照隔离域（试算→web/ 正式→共享主目录），单一来源
        snapshot_namespace = _web_input_mode_snapshot_domain(mode)

        # ── 按模式解析持仓来源与快照隔离域 ──
        if mode == "formal":
            holdings_dir = config.get("holdings_dir") or ""
            holdings_name = config.get("holdings_filename") or ""
            formal_path = os.path.join(holdings_dir, holdings_name) if holdings_dir and holdings_name else None
            if use_existing:
                # 正式 + 用存量：直接读正式文件（路径仅从配置派生）
                if formal_path is None or not os.path.isfile(formal_path):
                    shown = formal_path or "（未配置 holdings_dir/holdings_filename）"
                    state.errors.append(f"正式持仓文件不存在：{shown}。请先在正式模式上传覆盖，或改用临时试算")
                    return _EXIT_SEVERE
                holdings_path = formal_path
            else:
                # 正式 + 上传：出队后先提升为正式文件（备份旧文件），再读正式路径
                path = resolve_file(file_id) if file_id else None
                if path is None:
                    state.errors.append("上传文件已过期，请重新上传")
                    return _EXIT_SEVERE
                if formal_path is None:
                    state.errors.append("未配置正式持仓文件路径（holdings_dir/holdings_filename）")
                    return _EXIT_SEVERE
                promote_upload_to_holdings(path, formal_path)
                holdings_path = formal_path
        else:
            # 试算（默认）：读上传临时文件，快照隔离到 web/ 域
            path = resolve_file(file_id) if file_id else None
            if path is None:
                state.errors.append("上传文件已过期，请重新上传")
                return _EXIT_SEVERE
            holdings_path = path

        parsed = read_holdings_with_flows(holdings_path)
        holdings = parsed.holdings
        try:
            require_holdings(holdings)  # 不传服务端路径（错误面向浏览器）
        except ValueError as e:
            state.errors.append(str(e))
            return _EXIT_SEVERE

        reporter = WebProgressReporter(state)
        result = generate_report(
            holdings=holdings,
            config=config,
            reporter=reporter,
            report_type=params.get("report_type", "basic"),
            # None → generate_report 回退到配置层 history.fetch_mode 解析
            fetch_history=params.get("fetch_history"),
            force_llm=bool(params.get("force_llm")),
            force_llm_modules=params.get("llm_modules"),
            output_dir=None,
            transactions=parsed.transactions,
            dividends=parsed.dividends,
            snapshot_namespace=snapshot_namespace,
        )

        state.output_dir = resolve_output_dir(config)
        state.errors = list(result.errors)
        if result_box is not None:
            result_box["result"] = result
        return result.exit_code
    except Exception:
        logger.exception("[web-run] run %s 生成异常", state.run_id)
        state.errors.append("生成任务执行异常（详情请查看日志）")
        return _EXIT_SEVERE
    finally:
        # 试算 / 正式-上传携带 file_id → 清理上传临时文件（正式文件本体保留；
        # promote 为 copy，临时文件生命周期不变，仍由这里统一清理）
        if file_id:
            discard_file(file_id)


def _notify_web_completion(state, params: dict, exit_code: int, result: object) -> None:
    """Web 生成收尾完成/失败通知（门控前置 + 尽力而为，与 CLI ``_notify_report_completion`` 同构）。

    Web 手动生成与内置定时调度共用 ``_run_generation`` 执行体——两条链路的
    通知统一在此派发（定时无人值守正是通知的核心价值）。
    契约：未配置任何通道时 ``should_notify`` 即返回（不碰跟踪器、不构造
    事件）；本函数内部任何异常只记 DEBUG，绝不改变 exit_code / run 状态。
    """
    try:
        from src.python.config import get_config
        from src.python.core.completion_notify import (
            build_completion_event,
            dispatch_completion_notification,
            should_notify,
        )
        from src.python.report.data_status import degradation_summary

        config = get_config() or {}
        notify_cfg = config.get("notify") or {}
        if not should_notify(notify_cfg, ok=exit_code == 0):
            return
        output_dir = state.output_dir or resolve_output_dir(config)
        event = build_completion_event(
            report_type=str(params.get("report_type", "basic") or "basic"),
            exit_code=exit_code,
            output_dir=str(output_dir),
            errors=list(state.errors or []),
            excel_ok=bool(getattr(result, "excel_ok", False)),
            html_ok=bool(getattr(result, "html_ok", False)),
            degradations=degradation_summary(),
        )
        dispatch_completion_notification(event, notify_cfg)
    except Exception:
        logger.debug("完成通知发送流程异常（非关键，不影响任务）", exc_info=True)


def _build_artifacts(params: dict, state) -> list[dict]:
    """按 report_type 计算产物清单（路径相对 output_dir，供前端渲染按钮）。

    类型 → kind 规则委托 `orchestrator.artifacts_for_report_type` 单源（禁止渠道
    层镜像 CLI --type 语义）；文件名取 `core.constants` 最新版常量。
    严重失败（exit_code 2）或执行失败（failed）时无可用产物，返回空。
    """
    from src.python.core.constants import LATEST_HTML_NAME, LATEST_XLSX_NAME
    from src.python.report.orchestrator import artifacts_for_report_type

    report_type = params.get("report_type", "basic")
    if not state.output_dir:
        return []
    # 严重失败/执行失败：报告未生成，产物按钮无意义（点击只会 404）
    if state.status == "failed" or state.exit_code == _EXIT_SEVERE:
        return []
    names = {"html": ("HTML 报告", LATEST_HTML_NAME), "xlsx": ("Excel 报告", LATEST_XLSX_NAME)}
    return [{"kind": k, "name": names[k][0], "path": names[k][1]} for k in artifacts_for_report_type(report_type)]
