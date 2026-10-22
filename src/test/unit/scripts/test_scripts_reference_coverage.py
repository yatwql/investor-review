"""文档 ↔ scripts 清单覆盖机检（参考文档与脚本清单的一致性口径）。

三条不变量，防「文档没跟上脚本增删」与「文档指向不存在的脚本」两类漂移：

1. **一览覆盖**：`scripts/` 下每个顶层脚本（`.py` / `.sh` / `.ps1`，排除内部共享模块）
   必须在 `scripts-reference.md` 的「一览」表首列出现——新增脚本忘了登记即红；
2. **不虚指**：一览表与《开发者指南》「按域索引」里出现的脚本名必须真实存在于
   `scripts/`（回归背景：指南启动行曾列 `dev-verify.sh` / `web.sh` 两个不存在的包装脚本）；
3. **实现包点名**：`scripts/_*/` 每个内部实现包须在参考文档中被点名（拆包后读者才知道
   去哪找实现），数量从文件系统派生，不写死。

判据只依赖文件系统与两份文档文本，不 import 项目运行时（与 `check-file-length` 同款）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = REPO_ROOT / "scripts"
REFERENCE = REPO_ROOT / "docs" / "managements" / "scripts-reference.md"
GUIDE = REPO_ROOT / "docs" / "managements" / "developer-guide.md"

#: 内部共享模块（不是可独立运行的脚本，不入「一览」）
_INTERNAL_MODULES = {"_checklib.py", "_traces_common.py"}
_SCRIPT_SUFFIXES = (".py", ".sh", ".ps1")


def _actual_scripts() -> set[str]:
    """`scripts/` 顶层脚本文件名（含 .ps1 变体，排除内部共享模块）。"""
    return {
        p.name
        for p in SCRIPTS_DIR.iterdir()
        if p.is_file() and p.suffix in _SCRIPT_SUFFIXES and p.name not in _INTERNAL_MODULES
    }


def _overview_names() -> set[str]:
    """`scripts-reference.md`「## 一览」表首列里的脚本名集合。"""
    text = REFERENCE.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^## 一览\n(.*?)(?=^## )", text)
    assert match, "scripts-reference.md 缺少「## 一览」小节"
    names: set[str] = set()
    for line in match.group(1).splitlines():
        if not line.startswith("|"):
            continue
        first_cell = line.strip().strip("|").split("|")[0]
        names |= set(re.findall(r"[A-Za-z0-9_.\-]+\.(?:py|sh|ps1)", first_cell))
    return names - {"__init__.py"}


def _domain_index_names() -> set[str]:
    """《开发者指南》「### 按域索引」表里出现的脚本名（含裸名与反引号写法）。"""
    text = GUIDE.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^### 按域索引\n(.*?)(?=^### |^## )", text)
    assert match, "developer-guide.md 缺少「### 按域索引」小节"
    return set(re.findall(r"[A-Za-z0-9_.\-]+\.(?:py|sh|ps1)", match.group(1)))


class TestOverviewCoversEveryScript:
    """不变量 1：新增/改名脚本必须登记进「一览」。"""

    def test_every_top_level_script_is_documented(self):
        missing = sorted(_actual_scripts() - _overview_names())
        assert missing == [], (
            "以下顶层脚本未登记进 scripts-reference.md「## 一览」（新增脚本须补行：分类 + 一句话职责）：\n"
            + "\n".join(f"  - {name}" for name in missing)
        )

    def test_overview_has_no_phantom_scripts(self):
        """一览里的脚本名必须真实存在（防删脚本后留悬空条目）。"""
        phantom = sorted(name for name in _overview_names() if not (SCRIPTS_DIR / name).is_file())
        assert phantom == [], "scripts-reference.md「一览」指向不存在的脚本：\n" + "\n".join(
            f"  - {name}" for name in phantom
        )


class TestGuideDomainIndexIsTruthful:
    """不变量 2：指南「按域索引」里的脚本名必须存在（回归 `dev-verify.sh` / `web.sh`）。"""

    def test_all_named_scripts_exist(self):
        phantom = sorted(name for name in _domain_index_names() if not (SCRIPTS_DIR / name).is_file())
        assert phantom == [], (
            "developer-guide.md「按域索引」列了不存在的脚本（改用实际包装脚本，或补脚本本体）：\n"
            + "\n".join(f"  - {name}" for name in phantom)
        )

    def test_domain_index_covers_every_script_family(self):
        """七域索引须各自至少点名一个真实脚本（防整行被误删成空壳）。"""
        section = re.search(r"(?ms)^### 按域索引\n(.*?)(?=^### |^## )", GUIDE.read_text(encoding="utf-8"))
        assert section, "developer-guide.md 缺少「### 按域索引」小节"
        rows = [
            line
            for line in section.group(1).splitlines()
            if re.match(r"^\| (测试|文档|代码与文件质量|发布|诊断|启动|CLI 子命令) \|", line)
        ]
        assert len(rows) == 7, f"「按域索引」应为 7 个域行（测试/文档/质量/发布/诊断/启动/CLI），实际 {len(rows)}"
        for row in rows:
            # 「代表脚本」列须至少点名一个条目（CLI 子命令行点名的是子命令名而非 .py 文件）
            assert re.findall(r"`[^`]+`", row), f"域行未点名任何条目：{row[:40]}"


class TestInternalPackagesAreNamed:
    """不变量 3：拆包后在参考文档里点名实现包（读者才知道去哪找实现）。"""

    def test_each_internal_package_mentioned(self):
        packages = sorted(
            p.name
            for p in SCRIPTS_DIR.iterdir()
            if p.is_dir() and p.name.startswith("_") and not p.name.startswith("__")
        )
        assert packages, "scripts/ 下未发现内部实现包（至少 _checklib 依赖的包应存在）"
        text = REFERENCE.read_text(encoding="utf-8")
        missing = [name for name in packages if f"{name}/" not in text and name not in text]
        assert missing == [], (
            "以下内部实现包未在 scripts-reference.md 中点名（拆包后须在对应条目注明实现位置）：\n"
            + "\n".join(f"  - scripts/{name}/" for name in missing)
        )


# ── 内容层：详情小节覆盖 + CLI 旗标真实性 ─────────────────────


#: 允许「一览有条目、无独立详情小节」的条目（薄垫片：实现与用法已在其所属条目里说明）
_SECTIONLESS_OK = {"probe-csi-factor-indices.py"}

#: 文档会提到的**外部工具**旗标（pip / pytest / git / pi 等，不经本仓脚本解析器）
_EXTERNAL_FLAGS = {
    "--break-system-packages",
    "--no-deps",
    "--failed-first",
    "--last-failed",
    "--list-models",
    "--is-ancestor",
    "--no-hardlinks",
    "--lf",
    "--tb",
    "--co",
    "--durations",
    "--pdb",
    "--capture",
    "--collect-only",
    "--html",
    "--run-live",
    "--no-ff",
    "--fix",
    "--force-refresh",
    "--full-bench",
    "--with-test-count",
    "--dry-run",
    "--no-archive",
    "--skip-design-docs",
    "--record-cassettes",
}


def _doc_tokens(path: Path, pattern: str) -> set[str]:
    return set(re.findall(pattern, path.read_text(encoding="utf-8")))


def _ast_flags() -> set[str]:
    """`scripts/**` 与 CLI 解析器里所有 `--flag` 字面量（静态 AST，不执行脚本）。"""
    import ast

    roots = [SCRIPTS_DIR, REPO_ROOT / "src" / "python" / "cli"]
    flags: set[str] = set()
    for root in roots:
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    flags |= set(re.findall(r"^--[a-z][a-z0-9]*(?:-[a-z0-9]+)*$", node.value))
    return flags


class TestDetailSections:
    """每条一览条目要么有独立详情小节（加粗脚本名标题），要么在豁免表里说明。"""

    def test_every_entry_has_detail_section_or_exemption(self):
        missing = sorted(
            name
            for name in _overview_names()
            if name.endswith(".py")
            and not name.startswith("_")
            and name not in _SECTIONLESS_OK
            and not re.search(rf"\*\*`{re.escape(name)}`", REFERENCE.read_text(encoding="utf-8"))
        )
        assert missing == [], (
            "以下脚本在一览表里有条目，但缺独立详情小节（或加入 _SECTIONLESS_OK 并说明理由）：\n"
            + "\n".join(f"  - {name}" for name in missing)
        )


class TestDocumentedFlagsExist:
    """两份文档提到的 `--flag` 必须能在脚本/CLI 解析器里找到（防旗标改名/删除后文档滞留）。"""

    def test_doc_flags_resolve_to_parser_or_external_tool(self):
        known = _ast_flags() | _EXTERNAL_FLAGS
        violations = []
        for doc in (REFERENCE, GUIDE):
            for flag in sorted(_doc_tokens(doc, r"--[a-z][a-z0-9]*(?:-[a-z0-9]+)+")):
                if flag not in known:
                    violations.append(f"{doc.name}: {flag}")
        assert violations == [], (
            "文档提到的旗标在脚本/CLI 解析器里找不到（可能已改名或删除），请同步文档或补白名单：\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
