"""测试：shell 脚本契约机检 — `set -e`/`set -u` 下的死代码 `$?` 与裸位置参数

回归场景（launch.sh 无参崩溃的两类伴生缺陷）：
  - **死代码 `$?`**：脚本顶部声明 `set -euo pipefail` 后，紧跟在独立命令之后的
    `if [ $? -ne 0 ]` 永不触发——`set -e` 已在该命令非零时中止脚本，错误处理
    分支是假安全感（真实失败只留下原始退出码，用户看不到可读提示）。同理
    `if [ $? -eq 0 ]` 的 else 分支不可达。正确写法是把命令放进 `if` 条件本身。
  - **裸位置参数**：`set -u` 下无参调用时 `$1` 展开即报 `unbound variable`。
    launch.sh 已实际发生（无参启动崩溃），此处静态面兜底封堵回流。

判定方式为纯静态读取，不执行脚本（执行面由 test_launch_script_regression.py
的沙箱用例覆盖）；两面合围堵死 shell 契约缺陷类。
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_GITHOOKS_DIR = _REPO_ROOT / ".githooks"
_BASH = shutil.which("bash") or "/bin/bash"

# 裸位置参数：$1..$9，后不接标识符字符（排除 $10 之类）。
_BARE_POSITIONAL_RE = re.compile(r"(?<![A-Za-z0-9_])\$[1-9](?![A-Za-z0-9_])")
# 合法守卫形态：${1:-} / ${1-}
_GUARDED_POSITIONAL_RE = re.compile(r"\$\{[1-9][:-]")


# 检查面 = scripts/*.sh + .githooks/*（可执行钩子，含无扩展名的 pre-commit）
def _shell_scripts() -> list[Path]:
    found = list(_SCRIPTS_DIR.glob("*.sh"))
    if _GITHOOKS_DIR.is_dir():
        found += [p for p in _GITHOOKS_DIR.iterdir() if p.is_file() and not p.name.startswith(".")]
    return sorted(found)


def _has_option(content: str, flag: str) -> bool:
    """脚本是否启用某 shell 选项（覆盖 `set -euo pipefail` / `set -o nounset` 两写法）。"""
    if flag == "errexit":
        return bool(re.search(r"set\s+-[a-zA-Z]*e|set\s+-o\s+errexit", content))
    if flag == "nounset":
        return bool(re.search(r"set\s+-[a-zA-Z]*u|set\s+-o\s+nounset", content))
    raise ValueError(flag)


def _is_function_definition(stripped: str) -> bool:
    """判定是否函数定义行（`name() {` 或 `function name …`）。

    不可用 `^[a-zA-Z_]\\w*\\s*\\(\\)` 单正则——它会把 `if [ ... ]; then` 之类
    行尾的 `then`/`do` 误判为函数定义，导致 depth 恒 >0、顶层裸位置参数分支
    永不执行（实测漏报根因）。
    """
    if "(" not in stripped or ")" not in stripped:
        return False
    if re.match(r"^\s*function\s+[A-Za-z_]\w*", stripped):
        return True
    return bool(re.match(r"^\s*[A-Za-z_]\w*\s*\(\s*\)\s*({|;|\n|$)", stripped))


def _remove_comment(line: str) -> str:
    r"""删除行内注释（`#` 前导且不在引号内），**保留引号内容**。

    不得删除引号内容——裸位置参数（如 `ENTRY="$1"`）恰恰位于引号内，剥离
    引号会让检测永远匹配不到（实测漏报根因）。注释删除须做引号状态扫描，
    避开 `echo "a#b"` 这类引号内 `#` 被误删；注释里出现的 `$?`/`$1` 说明
    文本则被丢弃，不会被误判为代码。
    """
    out = []
    quote = ""
    for i, ch in enumerate(line):
        if quote:
            if ch == quote and (i == 0 or line[i - 1] != "\\"):
                quote = ""
            out.append(ch)
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#":
            break  # 引号外的注释起点 → 剩余丢弃
        else:
            out.append(ch)
    return "".join(out)


def _strip_comments_and_strings(content: str) -> str:
    r"""删除行内注释，保留引号内容（裸 `$1` 恰在引号内，删引号会漏报）。

    返回逐行处理后的多行串，供调用方按行遍历。字符串字面量内的 `$1`
    （如 awk 脚本）仍可能触发，但 scripts/ 受检面内无此类写法，且宁可
    误报也不漏报。
    """
    return "\n".join(_remove_comment(line) for line in content.splitlines())


def _bare_positional_in_code(stripped: str) -> bool:
    r"""该行是否含**未被 `${N:-}` 守卫**的裸位置参数 `$1..$9`。

    单引号内为字面量（如 awk '{print $1}'）不计；`${1:-}` 为合法守卫不计。
    """
    probe = re.sub(r"'[^']*'", "", stripped)  # 剥单引号字面量
    if _GUARDED_POSITIONAL_RE.search(probe):
        return False  # 已用 ${N:-} 守卫
    return bool(_BARE_POSITIONAL_RE.search(probe))


@pytest.mark.unit
@pytest.mark.unit_scripts
class TestShellDeadCodeExitStatusCheck:
    """`set -e` 下，独立命令之后的 `if [ $? -ne 0 ]` / `else` 分支是不可达死代码。"""

    def test_no_unreachable_dollar_question_checks(self):
        """启用 errexit 的脚本不得出现「独立命令 + $? 判定」的假安全感写法。"""
        offenders = []
        for path in _shell_scripts():
            raw = path.read_text(encoding="utf-8")
            if not _has_option(raw, "errexit"):
                continue
            lines = [_remove_comment(ln) for ln in raw.splitlines()]
            for idx, line in enumerate(lines):
                # 命中 `if [ $? -ne 0 ]` 形态：上一有效行是独立命令（非 if/while/&&/||）
                if re.search(r"if\s*\[\s*\$\?\s*-ne\s*", line):
                    prev = next((ln for ln in reversed(lines[:idx]) if ln.strip()), "")
                    if not re.search(r"(if|while|&&|\|\||\{)\s*$", prev.strip()):
                        offenders.append(f"{path.name}:{idx + 1}  不可达的 $? -ne 0 检查")
        assert offenders == [], (
            "set -e 下紧跟独立命令的 `if [ $? -ne 0 ]` 永不触发（失败时脚本已退出），"
            "应改为 `if ! cmd; then …`：\n" + "\n".join(offenders)
        )


@pytest.mark.unit
@pytest.mark.unit_scripts
class TestShellNounsetPositionalParam:
    """`set -u` 下裸 `$1`（无参调用）展开即崩，须用 `${1:-}` 或先做参数个数判定。"""

    def test_no_bare_positional_params_under_nounset(self):
        r"""启用 nounset 的脚本不得在顶层裸引用 $1..$9（函数内形参受调用方保障，放行）。

        例外：若同一顶层块中该位置参数已先经 `${N:-}` 守卫（launch.sh 的
        `if [ "${1:-}" … ]; then ENTRY="$1"` 模式），后续裸引用不会触发 unbound，
        视为安全——否则该守卫写法会被迫退化，误报反降低可读性。`shift` 会改变
        位置参数语义（$1 变为下一个可能未设置的参数），遇 shift 须清空豁免集。
        """
        offenders = []
        for path in _shell_scripts():
            raw = path.read_text(encoding="utf-8")
            if not _has_option(raw, "nounset"):
                continue
            code = _strip_comments_and_strings(raw)
            depth = 0  # 函数体深度：顶层为 0，函数内放行
            guarded: set[str] = set()  # 顶层块内已 `${N:-}` 守卫过的位置参数号
            for idx, line in enumerate(code.splitlines()):
                stripped = line.strip()
                if _is_function_definition(stripped):
                    depth += 1
                for m in _GUARDED_POSITIONAL_RE.finditer(stripped):
                    guarded.add(m.group(0)[2])  # ${1:-} → "1"
                if depth == 0 and _bare_positional_in_code(stripped):
                    bare = {m.group(0)[1] for m in _BARE_POSITIONAL_RE.finditer(stripped)}
                    bare -= guarded
                    if bare:
                        offenders.append(f"{path.name}:{idx + 1}  裸位置参数 {stripped[:40]}")
                if stripped == "}" and depth > 0:
                    depth -= 1
                if re.fullmatch(r"shift(\s+\d+)?", stripped):
                    guarded.clear()  # shift 后位置参数语义改变，早期守卫不再适用
        assert offenders == [], (
            "set -u 下顶层裸 $N 在无参调用时展开即崩（launch.sh 已实际发生），"
            "应改用 ${N:-} 或先判 $#：\n" + "\n".join(offenders)
        )


@pytest.mark.unit
@pytest.mark.unit_scripts
class TestShellSyntax:
    """全部受检脚本须通过 `bash -n` 语法检查（防改坏）。"""

    def test_bash_syntax_check(self):
        for path in _SCRIPTS_DIR.glob("*.sh"):
            proc = subprocess.run(
                [_BASH, "-n", str(path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
            )
            assert proc.returncode == 0, f"{path.name} 语法错误：\n{proc.stderr}"
