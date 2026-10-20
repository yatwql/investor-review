"""版本演进快照统计与表格回写（纯函数；路径与 CLI 面留在入口模块）。

统计口径与 folders.md「复现方法」一致：`git ls-files` 清单 + 逐文件精确行数。
表格/注释改写全部以**显式参数**（text/stats/date）驱动——模式缺失即抛
`ReleaseError`（宁可硬失败也不产出半新半旧的注释）。
"""

from __future__ import annotations

import re
from pathlib import Path

from _release._common import ReleaseError, exec_command


def line_count(data: bytes) -> int:
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def build_evolution_stats(root: Path, runner=None) -> dict[str, int]:
    """按 folders.md「复现方法」口径统计：git 清单 + 逐文件精确行数（工作区直读）。"""
    rc, out, err = exec_command(["git", "ls-files"], root, runner)
    if rc != 0:
        raise ReleaseError(f"git ls-files 失败：{err.strip()}")
    paths = [p for p in out.splitlines() if p.strip()]

    cats: dict[str, list[str]] = {"main": [], "test": [], "scripts": [], "tmpl": [], "svg": [], "md": []}
    missing: list[str] = []
    lines: dict[str, int] = {}
    def_test = 0
    def_test_strict = 0
    for rel in paths:
        full = root / rel
        try:
            data = full.read_bytes()
        except OSError:
            missing.append(rel)
            continue
        lines[rel] = line_count(data)
        if rel.endswith(".py"):
            if rel.startswith("src/test/"):
                cats["test"].append(rel)
                # 用例计数在首次读时顺带累计（避免全量测试文件二次读）
                for ln in data.split(b"\n"):
                    if b"def test_" in ln:
                        def_test += 1
                    if ln.lstrip().startswith(b"def test_"):
                        def_test_strict += 1
            elif rel.startswith("src/"):
                cats["main"].append(rel)
            elif rel.startswith("scripts/"):
                cats["scripts"].append(rel)
        elif rel.endswith(".html") and rel.startswith("src/static/tmpl/"):
            cats["tmpl"].append(rel)
        elif rel.endswith(".svg"):
            cats["svg"].append(rel)
        elif rel.endswith(".md"):
            cats["md"].append(rel)

    def pair(name: str) -> tuple[int, int]:
        fs = cats[name]
        return len(fs), sum(lines[p] for p in fs)

    main_f, main_l = pair("main")
    test_f, test_l = pair("test")
    scripts_f, scripts_l = pair("scripts")
    tmpl_f, tmpl_l = pair("tmpl")
    svg_f, svg_l = pair("svg")
    md_f, md_l = pair("md")

    five_files = main_f + test_f + scripts_f + tmpl_f + svg_f
    five_lines = main_l + test_l + scripts_l + tmpl_l + svg_l
    return {
        "main_files": main_f,
        "main_lines": main_l,
        "test_files": test_f,
        "test_lines": test_l,
        "scripts_files": scripts_f,
        "scripts_lines": scripts_l,
        "tmpl_files": tmpl_f,
        "tmpl_lines": tmpl_l,
        "svg_files": svg_f,
        "svg_lines": svg_l,
        "md_files": md_f,
        "md_lines": md_l,
        "five_files": five_files,
        "five_lines": five_lines,
        "def_test_lines": def_test,
        "def_test_strict": def_test_strict,
        "repo_files": len(paths),
        "repo_lines": sum(lines[p] for p in paths),
        "missing": len(missing),
    }


def fmt_pair(files: int, lines_n: int) -> str:
    return f"{files} 文件 / {lines_n:,} 行"


def _growth(base_value: int, cur_value: int, override: str | None = None) -> str:
    if override:
        return override
    if base_value == 0:
        return "新增"
    return f"{cur_value / base_value:.1f}×"


def _cell_number(cell: str) -> int:
    m = re.search(r"(\d[\d,]*)", cell)
    if not m:
        raise ReleaseError(f"基线单元格无数字：{cell!r}")
    return int(m.group(1).replace(",", ""))


def update_evolution_table(text: str, stats: dict[str, int], with_release: bool, date: str) -> str:
    """改写演进对照表：指标行两列 + 增长列 + 当前开发版列头日期；`with_release` 时发布列同写。"""
    rows: list[tuple[str, int, int, str | None]] = [
        # (行标签锚, 发布列值, 开发列值, 增长格式覆盖)
        ("| 主程序（", stats["main_lines"], stats["main_lines"], None),
        ("| 测试（", stats["test_lines"], stats["test_lines"], None),
        ("| 辅助脚本（", stats["scripts_lines"], stats["scripts_lines"], None),
        ("| HTML 报告模板（", stats["tmpl_lines"], stats["tmpl_lines"], f"1 → {stats['tmpl_files']}"),
        ("| 架构图示（", stats["svg_lines"], stats["svg_lines"], None),
        ("| 文档（", stats["md_lines"], stats["md_lines"], None),
        ("| **代码文件合计**", stats["five_files"], stats["five_files"], None),
        ("| **代码行合计**", stats["five_lines"], stats["five_lines"], None),
        ("| **测试用例数**", stats["def_test_lines"], stats["def_test_lines"], None),
        ("| 仓库文件总数", stats["repo_files"], stats["repo_files"], None),
        ("| 仓库总行数", stats["repo_lines"], stats["repo_lines"], None),
    ]
    out_lines: list[str] = []
    seen: set[str] = set()
    for line in text.split("\n"):
        hit = next((anchor for anchor, _, _, _ in rows if line.startswith(anchor)), None)
        if hit is None:
            out_lines.append(line)
            continue
        rel_val, dev_val, override = next((r[1], r[2], r[3]) for r in rows if r[0] == hit)
        cells = line.split("|")
        if len(cells) < 6:
            out_lines.append(line)
            continue
        base_cell = cells[2]
        bold = "**" in cells[3]
        pair_rows = hit in {"| 主程序（", "| 测试（", "| 辅助脚本（", "| HTML 报告模板（", "| 架构图示（", "| 文档（"}
        if pair_rows:
            # 行数指标行的增长比以「行数」为基准；基线以 0 开头（历史布局差异）直接判「新增」
            if re.match(r"\s*0(?!\d)", base_cell):
                base_val = 0
            else:
                ml = re.search(r"(\d[\d,]*) 文件 / (\d[\d,]*) 行", base_cell)
                base_val = int(ml.group(2).replace(",", "")) if ml else _cell_number(base_cell)
            files_key = {
                "| 主程序（": "main_files",
                "| 测试（": "test_files",
                "| 辅助脚本（": "scripts_files",
                "| HTML 报告模板（": "tmpl_files",
                "| 架构图示（": "svg_files",
                "| 文档（": "md_files",
            }[hit]
            rel_cell = fmt_pair(stats[files_key], rel_val)
            dev_cell = fmt_pair(stats[files_key], dev_val)
        else:
            base_val = _cell_number(base_cell)
            fmt = (lambda v: f"**{v:,}**") if bold else (lambda v: f"{v:,}")
            rel_cell = fmt(rel_val)
            dev_cell = fmt(dev_val)
        growth = _growth(base_val, dev_val, override)
        cells[3] = f" {rel_cell} " if with_release else cells[3]
        cells[4] = f" {dev_cell} "
        cells[5] = f" {growth}"
        out_lines.append("|".join(cells))
        seen.add(hit)
    missing_rows = [anchor for anchor, _, _, _ in rows if anchor not in seen]
    if missing_rows:
        raise ReleaseError(f"演进对照表缺行：{missing_rows}")
    result = "\n".join(out_lines)

    result, n_date = re.subn(
        r"(当前开发版（[^）]*?· 本次重跑时的工作区 · )\d{4}-\d{2}-\d{2}",
        lambda m: m.group(1) + date,
        result,
        count=1,
    )
    if n_date != 1:
        raise ReleaseError("演进对照表「当前开发版」列头日期模式缺失（列头格式变化时先同步本工具）")
    return result


_CURRENT_DEV_DATE = re.compile(r"当前开发版（[^）]*?· 本次重跑时的工作区 · (\d{4}-\d{2}-\d{2})")


def check_evolution_freshness(text: str, today: str) -> list[str]:
    """演进对照新鲜度：「当前开发版」列头日期须为今日（gate 前置断言，防跳过 evolution 步骤发布过期快照）。

    evolution 为发布链人工步骤，无断言时跳过即以过期快照发布。该列语义为
    「本次重跑时的工作区」滚动读数；表头日期与数据行由同一命令原子刷新，
    故列头日期一致即传递性覆盖数据行新鲜度。表头格式变化时随
    ``update_evolution_table`` 的同源模式同步。
    """
    m = _CURRENT_DEV_DATE.search(text)
    if not m:
        return ["folders.md 演进对照表「当前开发版」列头日期模式缺失（列头格式变化时先同步本工具）"]
    if m.group(1) != today:
        return [
            f"演进对照「当前开发版」列日期为 {m.group(1)}，非今日 {today}——先执行 release.py evolution 刷新后再 gate"
        ]
    return []


def update_ratio_note(text: str, stats: dict[str, int], with_release: bool) -> str:
    """测试/主程序行数比注释：`--release` 时最新发布点一并改写，否则只滚当前工作区。

    两种目标模式任一缺失即抛 `ReleaseError`——宁可硬失败也不产出半新半旧的注释。
    """
    ratio = stats["test_lines"] / stats["main_lines"] if stats["main_lines"] else 0.0
    pair = f"{stats['test_lines']:,} / {stats['main_lines']:,}"
    if with_release:
        text, n_release = re.subn(
            r"升至 \*\*[\d.]+:\d\*\*（[\d,]+ / [\d,]+，最新发布点）",
            f"升至 **{ratio:.2f}:1**（{pair}，最新发布点）",
            text,
            count=1,
        )
        if n_release != 1:
            raise ReleaseError("比值注释「最新发布点」模式缺失（注释格式变化时先同步本工具）")
    text, n_ws = re.subn(
        r"当前工作区为 \*\*[\d.]+:\d\*\*（[\d,]+ / [\d,]+）",
        f"当前工作区为 **{ratio:.2f}:1**（{pair}）",
        text,
        count=1,
    )
    if n_ws != 1:
        raise ReleaseError("比值注释「当前工作区为」模式缺失（注释格式变化时先同步本工具）")
    return text


def update_case_note(text: str, stats: dict[str, int]) -> str:
    """用例口径注释中的 grep / 严格定义行数；pytest 收集口径留人工核对提示。

    目标短语在真实文档中位于行中（非行首），不做行首锚定；模式缺失即抛
    `ReleaseError`（不静默漏更、不留滞留计数）。
    """
    text, n_grep = re.subn(
        r"(最初 \d+ → 当前 )[\d,]+",
        lambda m: m.group(1) + f"{stats['def_test_lines']:,}",
        text,
        count=1,
    )
    if n_grep != 1:
        raise ReleaseError("用例口径注释「最初 → 当前」模式缺失（注释格式变化时先同步本工具）")
    text, n_strict = re.subn(
        r"口径为 [\d,]+；",
        f"口径为 {stats['def_test_strict']:,}；",
        text,
        count=1,
    )
    if n_strict != 1:
        raise ReleaseError("用例口径注释「口径为」模式缺失（注释格式变化时先同步本工具）")
    return text
