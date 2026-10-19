"""TUI 统一交互运行时：把「读键 → 导航态 → 派发 → 反馈/重绘」的循环控制流单源化。

历史成因：`input_choice(arrows=True)` 是逐面板按需接入、导航态是面板内联变量（游标
+ engaged），导致方向键导航仅首页完整生效——`[S]` 游标只落临时反馈行、重绘后无行内
标记（视觉「像没反应」），`[P]` 等其余子菜单完全无导航。历次交互缺陷（Esc 取消补 14 处、
窄屏反馈两套口径、方向键拆包误判）均因控制流在 13 处面板各自手写、无单一契约。

本模块只统一「怎么到达一次派发」，不改「派发什么」——面板仍自己渲染帧（`render(nav)`）
与持有动作闭包（`PanelItem.action`），派发语义（编号/字母/默认项含义）全部保持。

设计文档：`docs/plan/tui-panel-runtime-design.md`。

架构约束遵从：
  - 单文件行数红线（≤1000 行）：运行时职责收敛，不塞版面/写路径；
  - 无模块级可变全局：导航态在 `NavState` 实例，不落全局；
  - 中文报错 / 单源反馈：反馈行复用既有色常量与 `[!]`/`[OK]` 前缀。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Literal

from src.python.tui.tui_keys import KEY_DOWN, KEY_UP, input_choice


class NavState:
    """列表面板方向键导航态（游标 + engaged 标记）。

    以主循环 `tui.py` 的 `sel` 导航为语义真值：engaged 前裸回车保持各面板原语义
    （不误触切换），engaged 后裸回车按游标选中项派发。游标回绕、纯导航不动配置。

    直达键（键入编号/字母）只同步游标**不置 engaged**——保证「键入 1 切换后按回车」
    仍走各面板原「无效/默认」语义，不误触二次切换（见设计 §3.6）。
    """

    __slots__ = ("count", "cursor", "engaged")

    def __init__(self, count: int = 0, cursor: int = 0, engaged: bool = False) -> None:
        self.count = count
        self.cursor = cursor
        self.engaged = engaged

    def sync(self, index: int) -> None:
        """游标同步到指定项（不置 engaged；供直达键对齐视觉位置）。"""
        self.cursor = index

    def engage(self, index: int | None = None) -> None:
        """进入导航态（engaged）；可选同时把游标移到指定项。"""
        if index is not None:
            self.cursor = index
        self.engaged = True

    def move(self, key: str, navigable: Callable[[int], bool] | None = None) -> bool:
        """↑/↓ 移动游标（回绕）并置 engaged。

        Args:
            key: ``KEY_UP`` 或 ``KEY_DOWN``。
            navigable: 可导航谓词（下标 → 是否可落）；``None`` = 全部可导航（简
                单回绕）。给了谓词则跳过不可导航项（如 ``kind=return`` 的「0/B
                返回」，回绕不落到返回项，保↑ 回绕到末末末项的原语义）。

        Returns:
            是否发生了移动（空列表或无可导航项返回 False，调用方不反馈）。
        """
        if self.count <= 0:
            return False
        step = -1 if key == KEY_UP else 1
        if navigable is None:
            self.engaged = True
            self.cursor = (self.cursor + step) % self.count
            return True
        i = self.cursor
        for _ in range(self.count):
            i = (i + step) % self.count
            if navigable(i):
                self.cursor = i
                self.engaged = True
                return True
        return False

    def marker(self, index: int) -> str:
        """行内游标标记：engaged 且命中当前行给 ``▸``，否则空格（占位对齐）。"""
        return "▸" if self.engaged and index == self.cursor else " "


@dataclass(frozen=True)
class PanelItem:
    """列表面板的一行可派发项（编号/字母 → 动作闭包）。

    ``key`` 是派发键：单字符时支持直达（键入即派发），多字符（如 S 面板 ``enable_news``）
    只经 ``on_text`` 词法匹配。``kind`` 决定派发后控制流：
      - ``action``：执行闭包后回到循环（重绘）；
      - ``return``：执行闭包（若有）后 `panel_loop` 返回（「0/B 返回」类）；
      - ``info``：只读提示项（闭包自打印），回到循环。
    """

    key: str
    label: str
    kind: Literal["action", "return", "info"] = "action"
    action: Callable[[], None] | None = None


def panel_loop(
    items: list[PanelItem],
    *,
    render: Callable[[NavState], Iterable[str | None]],
    prompt: str,
    read: Callable[..., str | None] | None = None,
    repaint: Literal["loop", "feedback"] = "loop",
    on_text: Callable[[str], None] | None = None,
    on_nav_moved: Callable[[], None] | None = None,
    on_help: Callable[[str], bool] | None = None,
    default_key: str | None = None,
    direct: bool = True,
    pick: int = 1,
    on_picked: Callable[[tuple[str, ...]], None] | None = None,
) -> None:
    """统一列表面板交互循环：读键 → 导航态 → 派发 → 反馈/重绘，直到 Esc/返回项。

    调用方（面板）只提供：可派发项清单（`items`）、帧渲染（`render(nav)`）、输入提示
    （`prompt`），以及可选的自由文本词法（`on_text`）。循环控制流（方向键游标、Enter
    防误触、直达键游标同步、Esc 返回、无效反馈）全部由本函数单源承担。

    退出语义（契约见设计 §3.6）：Esc（`read` 返回 None）返回；`kind="return"` 项派发后
    返回；Ctrl+C/EOF/`render` 异常原样上抛（由调用方 except 链承接，运行时不吞）。

    Args:
        items: 可派发项清单（顺序即导航顺序；空清单仍可读键交给 `on_text`）。
        render: 帧渲染回调（每轮重建）；返回行序列，``None`` 行按空行打印。
        prompt: 输入提示（调用方负责折行，如 `wrap_prompt`）。
        read: 行输入源；``None`` = `tui_keys.input_choice`。恒以 `arrows=True` 调用
            （方向键返回 ``KEY_UP``/``KEY_DOWN``），面板传本模块 `input_choice` 名字
            保既有测试 patch 点。
        repaint: 方向键移动后反馈方式——``"loop"`` 回到循环顶整屏重绘（行内 ``▸``
            标记随游标移动）；``"feedback"`` 只回单行位置反馈不重绘（窄档防刷屏），
            并回调 `on_nav_moved` 让面板按需置重绘。
        on_text: 未命中任何项键时的自由文本词法（如 S 面板 ``?3``/``key=on``、
            M 面板 ``3 1``）；``None`` = 无效反馈。
        on_nav_moved: 方向键移动成功后的回调（供 ``feedback`` 面板置重绘标记）。
        on_help: 面板自定义帮助（收到去掉问号的目标，``""`` 表示无参）；返回 True
            表示已处理。返回 False / 未提供时由运行时印通用「可用键一览」——``?``
            因此全面板可用（帮助入口不再是个别面板的特权）。
        default_key: 裸回车（空输入）且未导航时的默认派发项键；``None`` = 交
            `on_text`（无则无效反馈）——保持「不误触切换」原语义。
        direct: 单字符直达派发开关（键入即派发并同步游标）；M 面板置 False 让数字
            进 `on_text` 组「``3 1``」双编号词法。
        pick: Enter 收集个数（M 面板交换优先级需 2 项）；>1 时逐次 Enter 收集，
            收满调 `on_picked`。
        on_picked: 收满 `pick` 项后的回调（如执行交换）。

    Raises:
        KeyboardInterrupt / EOFError: 原样上抛（不被吞）。
    """
    if read is None:
        read = input_choice
    nav = NavState(count=len(items))
    picked: list[str] = []

    while True:
        for row in render(nav):
            print(row if row is not None else "")

        choice = read(prompt, arrows=True)  # type: ignore[call-arg]

        if choice is None:  # Esc：误入面板即时返回
            return

        # ── ? 帮助（运行时单源：无参=可用键一览，?N=单项详情；全面板一致）──
        if choice[:1] in ("?", "？"):
            _emit_help(choice[1:].strip(), items, on_help)
            continue

        # ── 方向键导航：移动游标（跳过 return 项），回调面板置重绘，按 repaint 策略补位置反馈 ──
        if choice in (KEY_UP, KEY_DOWN):
            if nav.move(choice, navigable=lambda i: items[i].kind != "return"):
                if on_nav_moved is not None:
                    on_nav_moved()  # 面板据以置重绘（窄档导航后强制重绘，行内 ▸ 移动）
                if repaint == "feedback":
                    _emit_nav_feedback(nav, items)
            continue

        # ── Enter（空输入）：防误触——engaged 派发/收集选中项 / default_key / 交 on_text ──
        if choice == "":
            if nav.engaged and items:
                if pick > 1:
                    _collect(items[nav.cursor].key, items, picked, pick, on_picked)
                    continue
                choice = items[nav.cursor].key
            elif default_key is not None:
                choice = default_key
            elif on_text is not None:
                on_text("")
                continue
            else:
                _emit_invalid()
                continue

        # pick>1：非 Enter 输入——return 项退出，其余交 on_text 词法（不走项直达派发）
        if pick > 1:
            ret = next((it for it in items if it.kind == "return" and it.key == choice), None)
            if ret is not None:
                if ret.action is not None:
                    ret.action()
                return
            if on_text is not None:
                on_text(choice)
            else:
                _emit_invalid()
            continue

        # ── 单字符直达派发：键入即选中并派发（游标同步，视觉与派发一致）──
        idx = _index_by_key(choice, items) if (direct and len(choice) == 1) else None
        if idx is not None:
            nav.sync(idx)  # 只同步游标、不置 engaged（保「键入后裸回车不误触」）
            choice = items[idx].key

        # ── 项键派发 ──
        item = _find_by_key(choice, items)
        if item is not None:
            if item.action is not None:
                item.action()
            if item.kind == "return":
                return
            continue

        # ── 未命中项键 → 自由文本词法 / 无效反馈 ──
        if on_text is not None:
            on_text(choice)
        else:
            _emit_invalid()


def _index_by_key(choice: str, items: list[PanelItem]) -> int | None:
    """单字符在项清单中的下标（大小写不敏感）；无匹配返回 None。"""
    up = choice.upper()
    for i, item in enumerate(items):
        if item.key.upper() == up:
            return i
    return None


def _find_by_key(key: str, items: list[PanelItem]) -> PanelItem | None:
    """按键精确定位项（区分大小写，供多字符键与派发复用）；无匹配返回 None。"""
    return next((it for it in items if it.key == key), None)


def _collect(
    key: str,
    items: list[PanelItem],
    picked: list[str],
    pick: int,
    on_picked: Callable[[tuple[str, ...]], None] | None,
) -> None:
    """pick>1 模式：收集一项，收满调 `on_picked` 并清空（不足给进度反馈）。"""
    picked.append(key)
    if len(picked) >= pick:
        if on_picked is not None:
            on_picked(tuple(picked))
        picked.clear()
    else:
        item = _find_by_key(key, items)
        label = item.label if item else key
        print(f"  [..] 已选 {key}. {label}（再选 {pick - len(picked)} 项）")


def _emit_nav_feedback(nav: NavState, items: list[PanelItem]) -> None:
    """``feedback`` repaint：方向键移动后的单行位置反馈（含 ▸ 与回车语义提示）。"""
    if not items:
        return
    item = items[nav.cursor % len(items)]
    print(f"  ▸ {item.key}. {item.label}（回车选择 · Esc 返回）")


def _emit_help(
    target: str,
    items: list[PanelItem],
    on_help: Callable[[str], bool] | None,
) -> None:
    """``?`` / ``?键`` 帮助输出（帮助入口全面板可用的单源实现）。"""
    from src.python.tui.prompt_text import item_detail_lines, keys_help_lines

    if on_help is not None and on_help(target):
        return
    if not target:
        for line in keys_help_lines(items):
            print(line)
        return
    item = _find_by_key(target, items) or _find_by_key(target.upper(), items)
    if item is None:
        _emit_invalid()
        return
    for line in item_detail_lines(item):
        print(line)


def _emit_invalid() -> None:
    """统一无效输入反馈（单源口径，全档一致）。"""
    from src.python.core.ansi_colors import RESET, YELLOW

    print(f"  {YELLOW}[!]{RESET} 无效选择")
