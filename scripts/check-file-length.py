#!/usr/bin/env python3
"""单文件行数红线守护脚本。

阈值口径（developer-guide「文件膨胀阈值」表 + review-findings 文件过长监控区硬上限）：
  - 主程序（``src/python/**.py``） > 1000 行 → finding（硬上限，必须拆分）
  - 脚本（``scripts/**.py``）       > 1000 行 → finding（脚本红线，含包内子模块）
  - 测试（``src/test/**.py``）      > 1200 行 → finding（测试文件红线）
  - 主程序 700-1000 / 脚本 600-1000 / 测试 900-1200 为可选优化区间，不判 finding，
    仅 ``-v`` 输出清单，供 review-findings「文件膨胀」登记表派生刷新
    （人肉快照退役，脚本输出即真值）。
  - ``__init__.py`` 包标记按「薄壳」独立警告线 200 行（门面/包标记应收薄）。
  - ``-v`` 另按「行数 × 近 90 天改动次数」输出拆分优先级排序（git 不可用时
    静默跳过），回答「先拆哪个」而不是只看绝对行数。
  - **登记表同实**：review-findings「文件膨胀登记」P4 表的每条登记行数须等于实测
    行数（文件已删/改名亦判 finding）。登记表是「该拆哪个、距红线多远」的唯一入口，
    手工维护且无其他断言——实测曾 6/9 项漂移（最大 +148 行），余量判断全部失真。

豁免登记：既有破线项须同时在 review-findings 挂账限期处理，二者同步存在——
  - 豁免文件超限 → 不报 finding，``-v`` 列为「豁免」状态；
  - 非豁免文件超限 → finding，退出 2；
  - 豁免文件回落至阈值内 → ``-v`` 提示「可移除豁免」（不判 finding）。

豁免语义名登记（相对路径 → 挂账位置与处理要求；豁免必须与 review-findings
待处理区条目同步存在）：见 ``EXEMPTIONS`` 常量。

用法：
  python scripts/check-file-length.py            # 检查全部
  python scripts/check-file-length.py -v         # 详细输出（含可选优化区间清单与豁免状态）
  python scripts/check-file-length.py --ci       # CI 模式（只输出 文件:描述）

退出码：
  0 — 全部通过（无破线、豁免项均在阈值内、登记表与实测一致）
  2 — 发现 finding（非豁免文件超红线 / 登记表与实测不符）
"""

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _shared.checklib import MANAGEMENTS_DIR, REPO_ROOT, add_common_args, rel, report  # noqa: E402

# ── 阈值与检查域 ──────────────────────────────────────────────

MAIN_SOURCE_LIMIT = 1000
"""主程序单文件硬上限（行数）。"""

SCRIPTS_SOURCE_LIMIT = 1000
"""脚本单文件红线（行数）。"""

TEST_SOURCE_LIMIT = 1200
"""测试单文件红线（行数）。"""

MAIN_SOURCE_ROOT = "src/python"
SCRIPTS_SOURCE_ROOT = "scripts"
TEST_SOURCE_ROOT = "src/test"

#: 各检查域行数上限（> 上限判 finding）与拆分提示
_LIMIT_BY_KIND = {"主程序": MAIN_SOURCE_LIMIT, "脚本": SCRIPTS_SOURCE_LIMIT, "测试": TEST_SOURCE_LIMIT}
_HINT_BY_KIND = {"主程序": "硬上限必须拆分", "脚本": "脚本红线须拆分", "测试": "测试文件红线须拆分"}
#: 各检查域可选优化区间下界（``-v`` 清单只列区间内文件；超上限者已直接判 finding）
#: 该下界同时是 review-findings P3 登记的入表线（警告 = 登记，不再维护第三套数字）
_WARN_BY_KIND = {"主程序": 700, "脚本": 600, "测试": 900}

#: 薄壳文件（``__init__.py`` 包标记/门面）的独立警告线：不计入域警告线，收薄即可
THIN_SHELL_WARN_LINES = 200
_THIN_SHELL_NAME = "__init__.py"

#: 拆分优先级的改动频度窗口（天）
CHURN_WINDOW_DAYS = 90

#: 既有破线豁免：相对路径 → 挂账说明（review-findings 待处理区须有对应条目）。
#: 空 = 当前无挂账破线项；新破线须先拆分，无法立即拆分时在此登记并同步挂账。
EXEMPTIONS: dict[str, str] = {}


#: 文件膨胀登记表所在文档（review-findings 的 P4「存量监控清单」）
REGISTRY_DOC = MANAGEMENTS_DIR / "review-findings.md"

#: 登记行形态：``| \`<相对路径>\` <行数> 行（…） | … |``
_REGISTRY_ROW = re.compile(r"^\|\s*`([^`]+)`\s*(\d+)\s*行", re.M)

#: 登记表所在章节（``### P4`` 起、下一个 ``## `` 止）
_REGISTRY_SECTION = re.compile(r"^### P4.*?$(.*?)(?=^## )", re.M | re.S)


def _parse_registry(text: str, root: Path) -> list[tuple[str, int, int | str]]:
    """从登记表文本取 [(相对路径, 登记行数, 实测行数或错误说明)]；章节缺失返回空列表。"""
    match = _REGISTRY_SECTION.search(text)
    if match is None:
        return []
    rows: list[tuple[str, int, int | str]] = []
    for path_str, registered in _REGISTRY_ROW.findall(match.group(1)):
        try:
            actual: int | str = len((root / path_str).read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeDecodeError):
            actual = "文件不存在或不可读"
        rows.append((path_str, int(registered), actual))
    return rows


def registry_rows(root: Path = REPO_ROOT) -> list[tuple[str, int, int | str]]:
    """返回 [(相对路径, 登记行数, 实测行数或错误说明)]；文档/章节缺失返回空列表。"""
    try:
        text = REGISTRY_DOC.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return _parse_registry(text, root)


def check_registry_lines(root: Path = REPO_ROOT) -> list[str]:
    """登记表同实：P4 登记行数须等于实测行数（登记表腐化即 finding）。"""
    try:
        text = REGISTRY_DOC.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{rel(REGISTRY_DOC)}: 文件膨胀登记表不可读（{exc}）"]
    if _REGISTRY_SECTION.search(text) is None:
        return [f"{rel(REGISTRY_DOC)}: 未匹配到 P4 登记表章节（标题结构已变更，请同步本检查的锚点）"]
    findings: list[str] = []
    # 章节存在但零条登记属合法态（全部拆完），只对实际条目判同实
    for path_str, registered, actual in _parse_registry(text, root):
        if not isinstance(actual, int):
            findings.append(f"{rel(REGISTRY_DOC)}: 登记项 {path_str} 无法核对（{actual}）")
            continue
        if actual != registered:
            findings.append(
                f"{rel(REGISTRY_DOC)}: 登记项 {path_str} 记 {registered} 行 ≠ 实测 {actual} 行"
                f"（{actual - registered:+d}，拆分/登记变更后须回写该值）"
            )
    return findings


def collect_line_counts(root: Path) -> list[tuple[str, str, int]]:
    """遍历检查域，返回 (类别, 相对路径, 行数) 记录列表（类别：主程序/脚本/测试）。"""
    records: list[tuple[str, str, int]] = []
    for sub, kind in (
        (MAIN_SOURCE_ROOT, "主程序"),
        (SCRIPTS_SOURCE_ROOT, "脚本"),
        (TEST_SOURCE_ROOT, "测试"),
    ):
        base = root / sub
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            try:
                lines = len(path.read_text(encoding="utf-8").splitlines())
            except (OSError, UnicodeDecodeError):
                continue
            records.append((kind, rel(path), lines))
    return records


def split_findings(
    records: list[tuple[str, str, int]],
    exemptions: dict[str, str] | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """把测量记录分成 (违规 finding, 豁免在列, 可移除豁免) 三组。"""
    exemptions = EXEMPTIONS if exemptions is None else exemptions
    violations: list[str] = []
    exempted: list[str] = []
    removable: list[str] = []
    for kind, path, lines in records:
        limit = _LIMIT_BY_KIND[kind]
        over = lines > limit
        if path in exemptions:
            if over:
                exempted.append(f"{path}（{kind} {lines} 行 > {limit}，豁免在列：{exemptions[path]}）")
            else:
                removable.append(f"{path}（已回落至 {limit} 行内，可移除豁免登记）")
        elif over:
            hint = _HINT_BY_KIND[kind]
            violations.append(f"{path}: {kind} {lines} 行 > {limit} 行（{hint}），须拆分或在豁免登记挂账")
    return violations, exempted, removable


def warn_threshold(kind: str, path: str) -> int:
    """返回该文件的可选优化区间下界（薄壳 ``__init__.py`` 用独立线）。"""
    if path.endswith(_THIN_SHELL_NAME):
        return THIN_SHELL_WARN_LINES
    return _WARN_BY_KIND[kind]


def over_limit_inventory(records: list[tuple[str, str, int]]) -> list[str]:
    """可选优化区间清单（主程序 >700 / 脚本 >600 / 测试 >900；薄壳 >200）。"""
    rows: list[tuple[int, str]] = []
    for kind, path, lines in records:
        warn_at = warn_threshold(kind, path)
        if lines > warn_at:
            label = "薄壳" if path.endswith(_THIN_SHELL_NAME) else kind
            rows.append((lines, f"  [{label}] {lines:>5} 行  {path}"))
    rows.sort(key=lambda item: -item[0])
    return [line for _lines, line in rows]


def churn_counts(root: Path, days: int = CHURN_WINDOW_DAYS) -> dict[str, int]:
    """近 ``days`` 天各文件改动次数（best-effort：git 缺失/失败返回空映射）。"""
    try:
        proc = subprocess.run(
            ["git", "log", f"--since={days}.days", "--name-only", "--pretty=format:"],
            cwd=str(root),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if proc.returncode != 0:
        return {}
    return Counter(line.strip() for line in proc.stdout.splitlines() if line.strip())


def priority_inventory(records: list[tuple[str, str, int]], churn: dict[str, int]) -> list[str]:
    """按「行数 × 近 90 天改动次数」排序的可选优化区间清单（只在 ``-v`` 输出）。"""
    rows: list[tuple[int, int, int, str]] = []
    for kind, path, lines in records:
        if lines <= warn_threshold(kind, path):
            continue
        commits = int(churn.get(path, 0))
        label = "薄壳" if path.endswith(_THIN_SHELL_NAME) else kind
        rows.append(
            (
                lines * commits,
                lines,
                commits,
                f"  {lines * commits:>8} 分（{lines} 行 × {commits} 次）  [{label}] {path}",
            )
        )
    rows.sort(key=lambda item: (-item[0], -item[1], item[3]))
    return [line for _score, _lines, _commits, line in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="单文件行数红线守护（主程序/脚本 >1000 / 测试 >1200）")
    add_common_args(parser)
    args = parser.parse_args()

    records = collect_line_counts(REPO_ROOT)
    violations, exempted, removable = split_findings(records)

    if args.verbose:
        print(
            f"检查域：{MAIN_SOURCE_ROOT}/（≤{MAIN_SOURCE_LIMIT} 行）+ {SCRIPTS_SOURCE_ROOT}/"
            f"（≤{SCRIPTS_SOURCE_LIMIT} 行）+ {TEST_SOURCE_ROOT}/（≤{TEST_SOURCE_LIMIT} 行）"
            f"，共 {len(records)} 个 py 文件"
        )
        for line in over_limit_inventory(records):
            print(line)
        churn = churn_counts(REPO_ROOT)
        if churn:
            print("按「行数 × 近 90 天改动次数」的拆分优先级：")
            for line in priority_inventory(records, churn):
                print(line)
        rows = registry_rows(REPO_ROOT)
        if rows:
            print(f"文件膨胀登记表（{rel(REGISTRY_DOC)} P4）：")
            for path_str, registered, actual in rows:
                mark = "" if actual == registered else "  ← 须回写"
                print(f"  {path_str}: 记 {registered} 行 / 实测 {actual}{mark}")
        for line in exempted:
            print(f"[豁免] {line}")
        for line in removable:
            print(f"[可移除豁免] {line}")

    registry_findings = check_registry_lines(REPO_ROOT)  # 显式传根：与上面 -v 的登记实况同源
    ok_message = (
        f"[OK] 行数红线通过（主程序/脚本 ≤{MAIN_SOURCE_LIMIT} 行 / 测试 ≤{TEST_SOURCE_LIMIT} 行；"
        f"豁免在列 {len(exempted)} 项，违规 {len(violations)} 项；登记表 {len(registry_rows())} 项与实测一致）"
    )
    return report(
        [*violations, *registry_findings],
        ok_message,
        ci=args.ci,
        fail_message="[!] 发现 {n} 处行数问题（超红线 / 登记表与实测不符），须拆分或回写登记值",
    )


if __name__ == "__main__":
    sys.exit(main())
