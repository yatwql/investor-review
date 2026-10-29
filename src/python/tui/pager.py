"""行长输出分页查看器：一屏一屏看，页脚常驻键位行。

用途：日志详情、健康历史、自检报告这类「一屏放不下、又要读完再走」的输出。相比
「一次打满 + 按任意键」的闸门，它给的是可翻页、可搜索的真能力，而不是靠停屏补偿
滚出可视区的内容。

退化口径（两条都不新增击键）：

  - 输出不足一屏 → 整段直打后直接返回（与逐行打印逐字节一致）；
  - 非 TTY（管道 / 重定向 / CI） → 同样整段直打，绝不读键。

键位只在本视图内有效（契约 Keys 表的「分页器键位块」），退出用 `q` / `Esc` / `0`
三键——与面板「`0` 返回」的肌肉记忆同向。
"""

from __future__ import annotations

from collections.abc import Callable

from src.python.core.ansi_colors import DIM, RESET
from src.python.tui.text_layout import MIN_TERMINAL_ROWS, terminal_rows
from src.python.tui.tui_keys import KEY_DOWN, KEY_ESC, KEY_UP, get_key, input_choice

#: 页脚键位行（单一文案来源；契约 Display Modes 的「页脚键位行」行型）
FOOTER_KEYS = "空格 下翻 · b 上翻 · g/G 首末 · / 搜索 · q 退出"

_QUIT_KEYS = ("q", KEY_ESC, "0")
_PAGE_DOWN_KEYS = (" ", KEY_DOWN, "j")
_PAGE_UP_KEYS = (KEY_UP, "k", "b")


def _footer(start: int, end: int, total: int, hit: str = "") -> str:
    """页脚：键位 + 当前区间 + 可选命中计数。"""
    position = f"（第 {start}-{end} / {total} 行）"
    suffix = f" · {hit}" if hit else ""
    return f"  {DIM}── {FOOTER_KEYS} {position}{suffix} ──{RESET}"


def _title_line(title: str) -> str:
    return f"  {DIM}{title}{RESET}"


def _fits_one_screen(lines: list[str], rows: int) -> bool:
    """整段是否一屏放得下（标题 + 内容 + 页脚）。"""
    return len(lines) + 2 <= rows


def _stdout_is_tty() -> bool:
    import sys

    try:
        return bool(sys.stdout.isatty())
    except Exception:
        return False


def _can_redraw_inplace() -> bool:
    """能否原地重绘（POSIX + TTY；其余环境逐页追加）。"""
    import os

    return os.name == "posix" and _stdout_is_tty()


class Pager:
    """分页视图状态机（可注入读键/输出/行输入，便于用例驱动）。"""

    def __init__(
        self,
        title: str,
        lines: list[str],
        *,
        rows: int | None = None,
        key_reader: Callable[[], str] = get_key,
        line_reader: Callable[..., str | None] = input_choice,
        echo: Callable[[str], None] = print,
        inplace: bool | None = None,
    ) -> None:
        self._title = title
        self._lines = lines
        self._rows = rows if rows is not None else terminal_rows()
        self._read = key_reader
        self._read_line = line_reader
        self._echo = echo
        self._inplace = _can_redraw_inplace() if inplace is None else inplace
        self._page_size = max(1, self._rows - 2)
        self._start = 0
        self._hit_note = ""
        self._start_rendered = False

    # ── 视图 ──

    @property
    def page_size(self) -> int:
        """每屏内容行数（标题与页脚各占一行）。"""
        return self._page_size

    def page_lines(self) -> list[str]:
        """当前页的上屏行（标题 + 内容 + 页脚）。"""
        end = min(self._start + self._page_size, len(self._lines))
        body = self._lines[self._start : end]
        return [_title_line(self._title), *body, _footer(self._start + 1, end, len(self._lines), self._hit_note)]

    def _draw(self) -> None:
        page = self.page_lines()
        if self._inplace and self._start_rendered:
            self._echo(f"\x1b[{len(page)}A\x1b[0J")
        for line in page:
            self._echo(line)
        self._start_rendered = True

    # ── 动作 ──

    def _scroll(self, delta: int) -> None:
        last = max(0, len(self._lines) - self._page_size)
        self._start = min(last, max(0, self._start + delta))
        self._hit_note = ""

    def _search(self) -> None:
        """行子串搜索：命中行置顶，再按 `/` 取下一个（不引入高亮色语义）。"""
        try:
            keyword = self._read_line("  搜索关键词（回车确认 · Esc 取消）: ")
        except (EOFError, KeyboardInterrupt):
            return
        if keyword is None:
            return
        word = keyword.strip()
        if not word:
            self._hit_note = ""
            return
        hits = [i for i, line in enumerate(self._lines) if word in line]
        if not hits:
            self._hit_note = f"未命中「{word}」"
            return
        nxt = next((i for i in hits if i > self._start), hits[0])
        self._start = min(max(0, len(self._lines) - self._page_size), nxt)
        ordinal = hits.index(nxt) + 1
        self._hit_note = f"命中 {ordinal}/{len(hits)}"

    def run(self) -> None:
        """驱动视图直到用户退出。"""
        self._start_rendered = False
        self._draw()
        last = max(0, len(self._lines) - self._page_size)
        while True:
            key = self._read()
            if key in _QUIT_KEYS:
                return
            if key in _PAGE_DOWN_KEYS:
                if self._start >= last:
                    continue
                self._scroll(self._page_size)
            elif key in _PAGE_UP_KEYS:
                if self._start <= 0:
                    continue
                self._scroll(-self._page_size)
            elif key == "g":
                if self._start == 0:
                    continue
                self._scroll(-len(self._lines))
            elif key == "G":
                if self._start == last:
                    continue
                self._start = last
                self._hit_note = ""
            elif key == "/":
                self._search()
            else:
                continue
            self._draw()


def view(
    title: str,
    lines: list[str],
    *,
    rows: int | None = None,
    key_reader: Callable[[], str] = get_key,
    line_reader: Callable[..., str | None] = input_choice,
    echo: Callable[[str], None] = print,
    inplace: bool | None = None,
) -> None:
    """查看一组长输出：不足一屏或非 TTY 时整段直打，否则进分页视图。"""
    if not lines:
        return
    effective_rows = rows if rows is not None else terminal_rows()
    tty = _stdout_is_tty()
    if not tty or effective_rows < MIN_TERMINAL_ROWS or _fits_one_screen(lines, effective_rows):
        # 退化路径也带上标题：管道/重定向的输出要能自解释（哪一组条目）
        for line in [_title_line(title), *lines]:
            echo(line)
        return
    Pager(
        title,
        lines,
        rows=effective_rows,
        key_reader=key_reader,
        line_reader=line_reader,
        echo=echo,
        inplace=inplace if inplace is not None else _can_redraw_inplace(),
    ).run()
