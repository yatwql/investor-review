"""TUI `[M]` LLM 多链线路优先级面板 — 按链序展示线路并支持「交换两个编号」。

职责边界：本模块只做展示与输入适配（编号 → order 置换），写盘一律经共享编辑层
``config.edit_ops.apply_config_edit``（``llm_providers.priority`` / ``reorder``），
与 CLI ``--llm-provider-order``、Web 配置面同一校验与同一写路径。

自 ``handlers_config`` 拆出（该文件已达单文件行数红线）：``_apply_edit`` 经函数内
局部导入复用，写盘与错误呈现保持单源，既有 patch 点继续有效。
"""

from __future__ import annotations

from src.python.config import DEFAULT_PROVIDER_PRIORITY
from src.python.core.ansi_colors import GREEN, RESET, YELLOW
from src.python.tui.panel_runtime import NavState, PanelItem, panel_loop
from src.python.tui.prompt_text import panel_prompt
from src.python.tui.switch_panel import inner_width, terminal_columns, wrap_hanging
from src.python.tui.text_layout import style_heading, truncate_display
from src.python.tui.tui_keys import input_choice


def run_llm_providers_panel() -> None:
    """管理 LLM 多链线路优先级（备用顺序）。

    与 CLI ``--llm-provider-order``、Web 配置面同源：写路径全部经共享编辑层
    ``apply_config_edit``（llm_providers.priority / reorder），本面板只做展示与
    「交换两个编号」的输入适配。Esc 即时返回主菜单。
    """
    from src.python.config import get_llm_providers

    state: dict = {"ordered": [], "width": 80}

    def _load() -> tuple[str, list]:
        from src.python.config import order_providers_by_chain

        cfg = get_llm_providers()
        strategy = str(cfg.get("strategy") or "priority")
        raw_providers = [p for p in (cfg.get("providers") or []) if isinstance(p, dict)]
        # 排序口径单一（共享 order_providers_by_chain）：与首页配置块 / 状态行链首 / 运行时一致
        ordered = list(enumerate(order_providers_by_chain(raw_providers)))
        return strategy, ordered

    strategy, ordered = _load()
    columns = terminal_columns()
    width = inner_width(columns)
    if len(ordered) < 2:
        # 单线路直接返回（不进入输入循环，行输入不被触发）
        print()
        print(style_heading(truncate_display(f"  ── LLM 多链线路优先级（strategy: {strategy}） ──", width)))
        for line in wrap_hanging("  当前仅一条线路（或未配置多链），无需调整", width):
            print(line)
        return

    def _render(nav: NavState) -> list[str]:
        strategy, ordered = _load()
        columns = terminal_columns()
        width = inner_width(columns)
        state["ordered"] = ordered
        state["width"] = width
        print()
        print(style_heading(truncate_display(f"  ── LLM 多链线路优先级（strategy: {strategy}） ──", width)))
        for num, (_i, provider) in enumerate(ordered, 1):
            row = (
                f"  {nav.marker(num - 1)}{num}. {provider.get('name')}（{provider.get('provider')}）priority "
                f"{provider.get('priority', DEFAULT_PROVIDER_PRIORITY)}"
            )
            for line in wrap_hanging(row, width):
                print(line)
        print(f"  {nav.marker(len(ordered))}0. 返回主菜单")
        if strategy not in ("priority", "fallback_only"):
            for line in wrap_hanging(
                f"  提示：当前策略 {strategy} 下实际链序由权重/成本决定，此处顺序仅在 priority / fallback_only 策略下生效",
                width,
            ):
                print(line)
        print()
        return []

    def _try_swap(a: int, b: int) -> bool:
        """配对交换：越界/相同编号返回 False（调用方给统一重提示），成功经共享编辑层写盘。"""
        from src.python.tui.handlers_config import _apply_edit  # 局部导入：写盘与错误呈现单源，patch 点不变

        ordered = state["ordered"]
        width = state["width"]
        if not (1 <= a <= len(ordered) and 1 <= b <= len(ordered) and a != b):
            return False
        names = [str(p.get("name")) for _i, p in ordered]
        names[a - 1], names[b - 1] = names[b - 1], names[a - 1]
        if _apply_edit({"key": "llm_providers.priority", "action": "reorder", "order": names}):
            for line in wrap_hanging(
                f"  {GREEN}[OK]{RESET} 已交换 {ordered[a - 1][1].get('name')} 与 {ordered[b - 1][1].get('name')} 的优先级",
                width,
            ):
                print(line)
        return True

    def _invalid() -> None:
        ordered = state["ordered"]
        width = state["width"]
        for line in wrap_hanging(
            f"  {YELLOW}[!]{RESET} 请输入两个不同的编号交换位置（如 3 1），范围 1-{len(ordered)}",
            width,
        ):
            print(line)

    def _on_text(choice: str) -> None:
        parts = choice.split()
        if len(parts) == 2:
            try:
                a, b = int(parts[0]), int(parts[1])
            except ValueError:
                a = b = -1
            if _try_swap(a, b):
                return
        _invalid()

    def _on_picked(keys: tuple[str, ...]) -> None:
        try:
            a, b = int(keys[0]), int(keys[1])
        except ValueError:
            a = b = -1
        if not _try_swap(a, b):
            _invalid()

    # 可派发项：编号线路（可导航，供 ↑↓ + Enter 收集配对）+ 0 返回
    items = [
        PanelItem(
            str(i),
            str(p.get("name")),
            detail=(
                f"模型 {p.get('model') or '默认'} · 优先级 {p.get('priority', DEFAULT_PROVIDER_PRIORITY)}"
                f"（数值小者链序靠前）· 端点 {p.get('endpoint') or '由凭据决定'}"
            ),
        )
        for i, (_x, p) in enumerate(ordered, 1)
    ]
    items.append(PanelItem("0", "返回主菜单", kind="return"))

    try:
        panel_loop(
            items,
            render=_render,
            prompt=panel_prompt("输入两个编号交换优先级", example="3 1"),
            read=input_choice,
            pick=2,
            on_picked=_on_picked,
            on_text=_on_text,
        )
    except (EOFError, KeyboardInterrupt):
        print()
