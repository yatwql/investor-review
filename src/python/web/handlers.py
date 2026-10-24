"""Web 路由 handler — 页面/上传/生成提交/轮询/预览/下载/历史/健康/报告追问。

**生成执行体已下沉**：[`web/run_generation.py`](run_generation.py) 承载
``_run_generation``（读持仓 → ``generate_report`` → 退出码映射）、产物清单
``_build_artifacts`` 与收尾通知 ``_notify_web_completion``；本模块只做路由分发与
响应信封，并按既有引用面 re-export 上述符号（patch 请指向 run_generation）。

响应统一信封：成功 ``{"ok": true, "data": ...}``；
错误 ``{"ok": false, "error_code": str|null, "error": 中文文案}``
（error_code 为机器可判定短标识，前端按 code 分支动作，不靠解析中文）。
"""

from __future__ import annotations

import logging
import os
import threading
import time
from urllib.parse import urlparse

from flask import request, send_from_directory

from src.python.config import resolve_output_dir
from src.python.qa.error_codes import (
    QA_CONTEXT_INVALID,
    QA_DISABLED,
    QA_LLM_FAILED,
    QA_LLM_UNAVAILABLE,
    QA_REPORT_NOT_FOUND,
)

# 生成执行体（下沉至 web/run_generation.py；此处 re-export 保持既有引用面，
# 调用点 patch 须指向 run_generation 模块——见该模块 docstring）
from src.python.web.run_generation import (
    _build_artifacts,
)

logger = logging.getLogger("invest")

# 只读观测路由（健康 / 自检 / 日志 / 健康历史）下沉 web/handlers_health.py；
# 此处 re-export 保持既有引用面（测试与调用方 import 路径不变）
from src.python.web.handlers_health import (  # noqa: E402
    _handle_doctor,
    _handle_health,
    _handle_health_history,
    _handle_logs,
)


# 预览/下载扩展名白名单（.lower() 归一化后校验，防 .HTML/.XLSX 绕过）
_ALLOWED_REPORT_EXT = {"html", "js", "map", "css", "png", "svg", "json", "xlsx"}

# 短缓存（运行历史 5s）——防频繁轮询重复读文件。
# 并发边界：server 为 threaded=True，读写由同一把锁保护——锁只保护「读缓存/
# 写缓存」两段，真实计算在锁外；两请求同时 miss 时可能重复计算一次（本地
# 单人 Web 的低风险余量，不引入检查时间内串行化代价）。
# 健康探测的 60s 缓存随其路由下沉 `handlers_health`（含各自的锁）。
_history_cache: dict = {"ts": 0.0, "data": None}
_render_cache_lock = threading.Lock()


# ── 响应信封辅助 ─────────────────────────────────────


def _ok(data):
    return {"ok": True, "data": data}


def _err(error_code, message):
    return {"ok": False, "error_code": error_code, "error": message}


# ── 系统信息组装（版本 / 机器 IP / LLM 状态，对齐 TUI 状态面板）────────


def _build_system_info() -> dict:
    """组装页面状态信息——委托共享层 core.system_info.build_system_info。

    共享单源：版本/机器IP/持仓输出摘要/匿名化/隐私提示/自检开关/LLM（含多链
    provider 链路）状态；TUI ``tui_menu`` 展示同一组原语，渠道层只做传输封装。
    """
    from src.python.core.system_info import build_system_info

    return build_system_info()


# ── 同源校验（轻量，副作用操作用）────────────────────


def _is_same_origin() -> bool:
    """轻量同源校验：Sec-Fetch-Site / Origin 与请求 host 一致性。

    test_client / 无这些头的合法客户端默认放行；跨站请求（伪造提交）拒绝。
    """
    sec_fetch = request.headers.get("Sec-Fetch-Site")
    if sec_fetch and sec_fetch not in ("same-origin", "same-site", "none"):
        return False
    origin = request.headers.get("Origin")
    if origin:
        host = request.host
        try:
            netloc = urlparse(origin).netloc
            if netloc and netloc != host:
                return False
        except ValueError:
            return False
    return True


# ── 路由 handler ─────────────────────────────────────


def _handle_index():
    from flask import render_template

    from src.python.config import get_config
    from src.python.core.constants import APP_NAME, APP_VERSION

    # 表单默认参数在页面加载时取一次 get_config()（页面刷新即重取，
    # 避免页面参数与 run 出队时配置快照时刻不一致）。
    # 历史走势默认跟随配置 fetch_mode（off→关闭；auto/prompt→开启）。
    config = get_config()
    fetch_mode = (config.get("history", {}) or {}).get("fetch_mode") or "auto"
    history_checked = bool(config.get("enable_history", True)) and fetch_mode != "off"
    # 表单说明文案（模板里嵌在复选框 label 括号中，不再重复「历史走势」前缀）
    config_note = "跟随配置开启" if history_checked else "当前配置关闭"
    # 模块级强刷候选：键名单一来源 force_scope，中文名经注册表派生
    from src.python.core.registry import get_llm_module_names
    from src.python.llm.force_scope import FORCEABLE_LLM_MODULES

    _llm_names = get_llm_module_names()
    llm_module_choices = [(k, _llm_names.get(k, k)) for k in FORCEABLE_LLM_MODULES]
    # 静态资源带版本查询串 ?v={APP_VERSION}（防浏览器缓存旧 JS/CSS 导致功能异常）
    # 状态区系统信息（版本 / 机器 IP / LLM 状态）随页面渲染，对齐 TUI 状态面板
    return render_template(
        "index.html",
        app_name=APP_NAME,
        app_version=APP_VERSION,
        history_checked=history_checked,
        config_note=config_note,
        llm_module_choices=llm_module_choices,
        system_info=_build_system_info(),
    )


def _handle_upload():
    from src.python.web.upload import UploadError, save_upload

    file = request.files.get("file")
    if file is None or not file.filename:
        return _err("UPLOAD_BAD_FILE", "未选择文件"), 400
    try:
        data = save_upload(file.stream, file.filename)
    except UploadError as e:
        return _err(e.error_code, e.message), 400
    return _ok(data)


def _handle_create_run(run_manager):
    from src.python.web.upload import resolve_file

    payload = request.get_json(silent=True) or {}
    file_id = payload.get("file_id")
    report_type = payload.get("report_type", "basic")
    fetch_history = payload.get("fetch_history")
    force_llm = payload.get("force_llm", False)
    llm_modules = payload.get("llm_modules")
    mode = payload.get("mode", "trial")
    use_existing = payload.get("use_existing", False)

    # 枚举校验（BAD_PARAM）
    if report_type not in ("basic", "both", "full"):
        return _err("BAD_PARAM", "报告格式不合法（basic/both/full）"), 400
    if fetch_history is not None and not isinstance(fetch_history, bool):
        return _err("BAD_PARAM", "历史走势参数不合法"), 400
    if not isinstance(force_llm, bool):
        return _err("BAD_PARAM", "强制 LLM 参数不合法"), 400
    if llm_modules is not None:
        if not isinstance(llm_modules, list) or not all(isinstance(m, str) for m in llm_modules):
            return _err("BAD_PARAM", "LLM 模块列表参数不合法"), 400
        from src.python.llm.force_scope import resolve_force_scope

        try:
            resolve_force_scope(False, llm_modules)
        except ValueError as e:
            return _err("BAD_PARAM", str(e)), 400
    if mode not in ("trial", "formal"):
        return _err("BAD_PARAM", "生成用途不合法（trial/formal）"), 400
    if not isinstance(use_existing, bool):
        return _err("BAD_PARAM", "输入来源参数不合法"), 400

    budget_ack = bool(payload.get("budget_ack", False))
    if "budget_ack" in payload and not isinstance(payload["budget_ack"], bool):
        return _err("BAD_PARAM", "预算确认参数不合法"), 400
    # ── 日预算硬闸（LLM 费用）：超限且未经弹层确认 → 409（自动化需显式 budget_ack）──
    if report_type == "full":
        from src.python.llm.cost_forecast import budget_status

        _budget = budget_status()
        if _budget.get("exceeded") and not budget_ack:
            return (
                _err(
                    "BUDGET_EXCEEDED",
                    f"今日 LLM 费用已达日预算上限"
                    f"（已花 {_budget['symbol']}{_budget['spent']:.4f} / 上限 {_budget['symbol']}{_budget['limit']:.4f}），"
                    "确认「用已有结果继续」后重试",
                ),
                409,
            )

    # 模式 × 输入来源组合校验：
    #   - 正式 + 用存量：无需上传（不携带 file_id），读正式持仓文件
    #   - 其余（试算 / 正式 + 上传）：必须有合法未过期 file_id
    if mode == "formal" and use_existing:
        if isinstance(file_id, str) and file_id:
            return _err("BAD_PARAM", "正式-用存量模式下无需上传文件（请勿携带 file_id）"), 400
    else:
        if not isinstance(file_id, str) or not file_id:
            return _err("BAD_PARAM", "缺少 file_id"), 400
        # file_id 存在且未过期（TTL 清理后引用 → FILE_EXPIRED）
        if resolve_file(file_id) is None:
            return _err("FILE_EXPIRED", "上传文件已过期，请重新上传"), 404
    # 副作用操作轻量同源校验
    if not _is_same_origin():
        return _err("BAD_PARAM", "同源校验失败，拒绝提交"), 403

    run_id = run_manager.submit(
        {
            "file_id": file_id,
            "report_type": report_type,
            "fetch_history": fetch_history,
            "force_llm": force_llm,
            "llm_modules": llm_modules or None,
            "mode": mode,
            "use_existing": use_existing,
            "budget_ack": budget_ack,
        }
    )
    if run_id is None:
        return _err("RUN_QUEUE_FULL", "已有任务在跑，排队或稍后再试"), 429
    return _ok({"run_id": run_id}), 202


def _handle_cost_preflight():
    """GET /api/runs/cost-preflight —— 事前费用预估 + 日预算状态（生成确认弹层数据源）。

    仅 ``report_type=full``（含 LLM 调用）时给 ``forecast``；``budget`` 恒给。
    预估失败（``forecast.ok=False``）由客户端按「不阻塞生成」处置，本接口不报错。
    ``llm_modules`` 查询参数（逗号分隔）透传重新生成范围——与 ``POST /api/runs``
    的 ``resolve_force_scope`` 同源，预估按所选范围重估（范围内模块静态单价
    口径）；非法模块键以 ``forecast.ok=false`` 数据面表达（预估失败不阻塞语义）。
    """
    from src.python.llm.cost_forecast import budget_status, forecast_run_cost

    report_type = request.args.get("report_type", "full")
    _mods = [m.strip() for m in request.args.get("llm_modules", "").split(",") if m.strip()]
    payload: dict = {"relevant": report_type == "full"}
    if payload["relevant"]:
        try:
            payload["forecast"] = forecast_run_cost(force_modules=_mods or None)
        except ValueError as exc:  # 非法模块键 → 数据面降级，不 500 不阻塞
            payload["forecast"] = {"ok": False, "reason": str(exc)}
    payload["budget"] = budget_status()
    return _ok(payload)


def _handle_list_runs(run_manager):
    states = run_manager.list_runs(limit=10)
    return _ok([s.snapshot() for s in states])


def _handle_run_detail(run_manager, run_id):
    state = run_manager.get(run_id)
    if state is None:
        return _err("NOT_FOUND", "任务不存在"), 404
    data = state.snapshot()
    if state.status in ("done", "failed"):
        data["artifacts"] = _build_artifacts(state.params, state)
    return _ok(data)


def _handle_run_events(run_manager, run_id):
    state = run_manager.get(run_id)
    if state is None:
        return _err("NOT_FOUND", "任务不存在"), 404
    raw = request.args.get("after", "0")
    try:
        after = max(0, int(raw))
    except (TypeError, ValueError):
        after = 0
    events = state.events_after(after)
    last_seq = events[-1]["seq"] if events else after
    return _ok(
        {
            "events": events,
            "status": state.status,
            "last_seq": last_seq,
            # first_seq：仍保留的最小序号（None = 缓冲空）——客户端据识别被淘汰的中间事件
            "first_seq": state.oldest_seq(),
        }
    )


def _handle_run_history():
    from src.python.core.perf import load_history

    now = time.time()
    with _render_cache_lock:
        if _history_cache["data"] is not None and now - _history_cache["ts"] < 5:
            return _ok(_history_cache["data"])
    records = load_history()
    with _render_cache_lock:
        _history_cache["ts"] = now
        _history_cache["data"] = records
    return _ok(records)


# ── 调仓 What-if 模拟（同步执行，独立产物）────────────────

# 同一时刻仅允许一个模拟（threaded 服务器下防止双写同名「调仓模拟.*」产物）
_whatif_lock = threading.Lock()


def _handle_whatif():
    """调仓 What-if 模拟（POST /api/whatif，副作用，同源守卫）。

    payload：
      - candidate_file_id（必填）：目标持仓（调仓后/假设）上传 file_id
      - base_file_id（可选）：基准持仓上传 file_id；缺省走 use_existing
      - use_existing（默认 True）：无 base_file_id 时用配置默认持仓文件
      - effective_date（可选 YYYY-MM-DD）：指定后追加时序回测（opt-in 联网）

    全程同步执行（本地计算，与 CLI/TUI 同链 run_whatif_simulation），
    成功返回产物 basename，前端经 /api/reports/<filename> 预览下载。
    """
    from src.python.core.reader import read_holdings
    from src.python.report.whatif_operations import run_whatif_simulation
    from src.python.web.upload import resolve_file

    payload = request.get_json(silent=True) or {}
    candidate_file_id = payload.get("candidate_file_id")
    base_file_id = payload.get("base_file_id")
    use_existing = payload.get("use_existing", True)
    effective_date = payload.get("effective_date")

    # ── 参数校验（BAD_PARAM）──
    if not isinstance(candidate_file_id, str) or not candidate_file_id:
        return _err("BAD_PARAM", "缺少目标持仓 file_id"), 400
    if base_file_id is not None and (not isinstance(base_file_id, str) or not base_file_id):
        return _err("BAD_PARAM", "基准持仓 file_id 不合法"), 400
    if not isinstance(use_existing, bool):
        return _err("BAD_PARAM", "输入来源参数不合法"), 400
    if effective_date is not None and not isinstance(effective_date, str):
        return _err("BAD_PARAM", "生效日格式不合法"), 400
    # 格式校验/归一化委托共享层 normalize_effective_date（与 CLI/TUI 同一规则）
    from src.python.report.whatif_operations import normalize_effective_date

    try:
        effective_date = normalize_effective_date(effective_date)
    except ValueError as e:
        return _err("BAD_PARAM", str(e)), 400
    # 副作用操作轻量同源校验
    if not _is_same_origin():
        return _err("BAD_PARAM", "同源校验失败，拒绝提交"), 403

    # ── 文件来源解析（上传过期 → FILE_EXPIRED 404）──
    candidate_path = resolve_file(candidate_file_id)
    if candidate_path is None:
        return _err("FILE_EXPIRED", "目标持仓文件已过期，请重新上传"), 404

    if base_file_id:
        base_path = resolve_file(base_file_id)
        if base_path is None:
            return _err("FILE_EXPIRED", "基准持仓文件已过期，请重新上传"), 404
    elif use_existing:
        from src.python.config import resolve_holdings_path

        base_path = resolve_holdings_path()
    else:
        return _err("BAD_PARAM", "缺少基准持仓来源"), 400

    # ── 读取两侧持仓（空/读失败 → 422，对齐 CLI 退出码语义）──
    base_holdings = read_holdings(base_path)
    cand_holdings = read_holdings(candidate_path)
    if not base_holdings:
        return _err("WHATIF_UNAVAILABLE", f"基准持仓读取失败或为空: {os.path.basename(base_path)}"), 422
    if not cand_holdings:
        return _err("WHATIF_UNAVAILABLE", f"目标持仓读取失败或为空: {os.path.basename(candidate_path)}"), 422

    # ── 互斥执行（忙碌 → 429）──
    if not _whatif_lock.acquire(blocking=False):
        return _err("WHATIF_BUSY", "已有调仓模拟在执行，请稍后再试"), 429
    try:
        output_dir = resolve_output_dir()
        result = run_whatif_simulation(
            base_holdings,
            cand_holdings,
            base_file=base_path,
            candidate_file=candidate_path,
            output_dir=output_dir,
            reporter=None,
            effective_date=effective_date,
        )
    except Exception:
        logger.exception("调仓 What-if 模拟执行异常")
        return _err("WHATIF_FAILED", "调仓模拟执行异常，请查看日志"), 500
    finally:
        _whatif_lock.release()

    if not result.ok:
        return _err("WHATIF_UNAVAILABLE", f"调仓对比数据不可用: {result.reason}"), 422
    return _ok(
        {
            "excel": os.path.basename(result.excel),
            "html": os.path.basename(result.html),
            "base_count": len(base_holdings),
            "candidate_count": len(cand_holdings),
        }
    )


# ── 缓存管理（统计 + 清理过期）──────────────────────────


def _handle_cache_stats():
    """缓存统计（GET /api/cache，只读）：总量/前缀分布/命中率/过期预估。

    结构化载荷由 ``cache.operations.get_cache_stats_payload`` 单源组装（保序
    数组、top 截断、命中率与过期预估），Web 侧只做传输封装。
    """
    from src.python.cache.operations import get_cache_stats_payload

    return _ok(get_cache_stats_payload())


def _handle_cache_cleanup():
    """清理过期缓存（POST /api/cache/cleanup，副作用，同源守卫）。

    与 TUI `[3]` 同链（cache.cleanup_expired），仅删 TTL 已过期文件；
    有效缓存不受影响，下次读取按需重建。
    """
    from src.python.cache import cleanup_expired

    if not _is_same_origin():
        return _err("BAD_PARAM", "同源校验失败，拒绝提交"), 403
    removed = cleanup_expired(dry_run=False)
    return _ok({"removed": removed})


def _handle_config_edit():
    """配置编辑：GET 返回可编辑面，POST 应用单次编辑（副作用，同源守卫）。

    POST 校验失败（未知键/类型/枚举/action 非法）→ 400 BAD_PARAM；
    写共享配置异常 → 500 CONFIG_WRITE_FAILED（详情记日志，前端不泄露内部细节）。
    """
    from src.python.web.config_edit import ConfigEditError, apply_config_edit, get_config_edit_surface

    if request.method == "POST":
        if not _is_same_origin():
            return _err("BAD_PARAM", "同源校验失败，拒绝提交"), 403
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return _err("BAD_PARAM", "请求体格式不合法"), 400
        try:
            data = apply_config_edit(payload)
        except ConfigEditError as e:
            return _err("BAD_PARAM", str(e)), 400
        except Exception:
            logger.exception("[config-edit] 配置写入失败")
            return _err("CONFIG_WRITE_FAILED", "配置写入失败（详情请查看日志）"), 500
        return _ok(data)
    return _ok(get_config_edit_surface())


# 追问错误码 → HTTP 状态码（与设计 §3.6 校验矩阵一致：
# 参数/超长/会话与输入超限 400；报告缺失/结构不可解析 404；开关关闭 403；LLM 全链失败 503）
_QA_STATUS_BY_CODE = {
    QA_REPORT_NOT_FOUND: 404,
    QA_CONTEXT_INVALID: 404,
    QA_LLM_UNAVAILABLE: 503,
    QA_LLM_FAILED: 503,
}


def _handle_report_qa_ask():
    """POST /api/qa/ask — 报告对话式追问（``report_qa`` 开关控制，默认关）。

    缺参/非法 report → 400；报告文件缺失/结构不可解析 → 404；开关关闭 → 403
    （error_code=``QA_DISABLED``）；LLM 未配置/未产出 → 503（前端按信封
    展示「服务暂不可用」占位，不把错误码当正常回答）。

    report 路径净化在路由层（仅 output_dir 下 .html 文件名），语义校验
    （问题长度/轮数/上下文）在 ``qa.session.ask_report_qa``（与 TUI 共用）。
    """
    from src.python.config.features import is_feature_enabled

    if not is_feature_enabled("report_qa"):
        return _err(QA_DISABLED, "报告追问功能未开启（功能开关面板启用「报告对话式追问」）"), 403

    payload = request.get_json(silent=True) or {}
    report = str(payload.get("report") or "").strip()
    session_id = payload.get("session_id") or None
    if session_id is not None and not isinstance(session_id, str):
        return _err("BAD_PARAM", "session_id 参数不合法"), 400
    from src.python.qa.context import sanitize_report_filename

    if sanitize_report_filename(report) is None:
        return _err("BAD_PARAM", "report 参数不合法（仅限 .html 报告文件名）"), 400

    from src.python.qa.session import ask_report_qa

    result = ask_report_qa(report=report, question=str(payload.get("question") or ""), session_id=session_id)
    if not result.get("ok"):
        code = result.get("error_code")
        return _err(code, result.get("error")), _QA_STATUS_BY_CODE.get(code, 400)
    return _ok(result)


def _handle_serve_report(filename: str):
    """预览/下载产物（route ``<path:filename>`` → 参数名 filename）。

    扩展名白名单先拦（防 .HTML/.XLSX 大小写绕过）；``send_from_directory``
    内置 ``..`` 净化（§6.2 防路径穿越）。
    """
    from src.python.config import get_config

    ext = os.path.splitext(filename)[1].lstrip(".").lower()
    if ext not in _ALLOWED_REPORT_EXT:
        return _err("BAD_PARAM", "不支持的文件类型"), 400
    config = get_config()
    output_dir = resolve_output_dir(config)
    return send_from_directory(output_dir, filename)


# ── 路由注册 ─────────────────────────────────────────


def _handle_scheduler_get():
    """GET 定时生成：归一化调度配置 + 下次触发预估（只读）。"""
    from src.python.web.scheduler import status_payload

    return _ok(status_payload())


def _handle_scheduler_post():
    """保存定时生成配置（写 config.json ``scheduler`` 块，副作用，同源守卫）。

    校验失败（时刻/执行日/报告格式非法）→ 400 BAD_PARAM；
    写共享配置异常 → 500 CONFIG_WRITE_FAILED（详情记日志，前端不泄露内部细节）。
    """
    from src.python.config.edit_ops import apply_scheduler_block
    from src.python.config import validate_schedule_block
    from src.python.web.scheduler import status_payload

    if not _is_same_origin():
        return _err("BAD_PARAM", "同源校验失败，拒绝提交"), 403
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return _err("BAD_PARAM", "请求体格式不合法"), 400
    try:
        block = validate_schedule_block(payload)
    except ValueError as e:
        return _err("BAD_PARAM", str(e)), 400
    try:
        apply_scheduler_block(block)
    except Exception:
        logger.exception("[scheduler] 调度配置写入失败")
        return _err("CONFIG_WRITE_FAILED", "配置写入失败（详情请查看日志）"), 500
    return _ok(status_payload())


def create_handlers(app, run_manager) -> None:
    """注册全部 HTTP 路由。

    注意：``/api/runs/history`` 必须先于 ``/api/runs/<run_id>`` 注册
    （run_id 为 token 字符串，否则 history 会被当作 run_id 捕获）。
    """
    app.add_url_rule("/", "index", _handle_index)

    app.add_url_rule("/api/upload", "upload", _handle_upload, methods=["POST"])

    app.add_url_rule("/api/runs", "create_run", lambda: _handle_create_run(run_manager), methods=["POST"])
    app.add_url_rule("/api/runs", "list_runs", lambda: _handle_list_runs(run_manager), methods=["GET"])
    # 静态历史路由必须先注册
    app.add_url_rule("/api/runs/history", "run_history", _handle_run_history, methods=["GET"])
    app.add_url_rule("/api/runs/cost-preflight", "cost_preflight", _handle_cost_preflight, methods=["GET"])
    app.add_url_rule(
        "/api/runs/<run_id>", "run_detail", lambda run_id: _handle_run_detail(run_manager, run_id), methods=["GET"]
    )
    app.add_url_rule(
        "/api/runs/<run_id>/events",
        "run_events",
        lambda run_id: _handle_run_events(run_manager, run_id),
        methods=["GET"],
    )

    app.add_url_rule("/api/reports/<path:filename>", "serve_report", _handle_serve_report, methods=["GET"])
    app.add_url_rule("/api/qa/ask", "report_qa_ask", _handle_report_qa_ask, methods=["POST"])
    app.add_url_rule("/api/whatif", "whatif", _handle_whatif, methods=["POST"])
    app.add_url_rule("/api/cache", "cache_stats", _handle_cache_stats, methods=["GET"])
    app.add_url_rule("/api/cache/cleanup", "cache_cleanup", _handle_cache_cleanup, methods=["POST"])
    app.add_url_rule("/api/health", "health", _handle_health, methods=["GET"])
    app.add_url_rule("/api/health/history", "health_history", _handle_health_history, methods=["GET"])
    app.add_url_rule("/api/doctor", "doctor", _handle_doctor, methods=["GET"])
    app.add_url_rule("/api/logs", "logs", _handle_logs, methods=["GET"])

    app.add_url_rule("/api/config/edit", "config_edit", _handle_config_edit, methods=["GET", "POST"])
    app.add_url_rule("/api/scheduler", "scheduler_get", _handle_scheduler_get, methods=["GET"])
    app.add_url_rule("/api/scheduler", "scheduler_set", _handle_scheduler_post, methods=["POST"])
