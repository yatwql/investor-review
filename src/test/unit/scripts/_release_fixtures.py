"""release.py 测试共享设备（非测试模块，pytest 不收集）。

为什么单独成模块：`test_release_tool*.py` 多组用例共用同一套设备（子进程替身、临时
仓库夹具、台账与目录树样例），此前集中在单个测试文件里已逼近 1200 行红线。各测试
模块各自 `load_script("release.py", module_name=...)` 取**独立模块实例**，保证
`_ToolRepoFixture` 对路径属性的重定向互不干扰。
"""

from __future__ import annotations

import argparse
from pathlib import Path


def _mode_arg(cmd: list[str]) -> str:
    """取命令中 `--mode` 的取值（无则空串）——bench 范围断言用。"""
    return cmd[cmd.index("--mode") + 1] if "--mode" in cmd else ""


class FakeRunner:
    """脚本化子进程替身：按「命令片段全部出现」匹配应答，记录全部调用。"""

    def __init__(self, responses=None, default=(0, "", "")):
        self.responses = list(responses or [])
        self.default = default
        self.calls: list[list[str]] = []

    def run(self, cmd, root, capture=True):
        cmd = [str(c) for c in cmd]
        self.calls.append(cmd)
        for matcher, resp in self.responses:
            if all(m in cmd for m in matcher):
                return resp
        return self.default


def ns(**kwargs) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


def _sample_changelog(archive_name: str = "archived_changelog.0.12.x.md") -> str:
    return (
        "# 变更日志\n\n"
        "> **最近发布 [0.12.5]**（2026-10-07）——已发布版本段随发布移入 "
        f"[`{archive_name}`](../archive/v0.12.x/{archive_name})；本文件只保留当前开发版本段与归档索引。\n\n"
        "---\n\n\n"
        "## [0.12.6-dev] - 开发中（未发布）\n\n"
        "- **条目一**：内容甲 | rf-1\n"
        "- **条目二**：内容乙\n\n"
        "（本次发布内容见下方归档索引）\n\n"
        "## 归档\n\n"
        f"- [`{archive_name}`](../archive/v0.12.x/{archive_name}) — v0.12.1 ~ v0.12.5"
        "（2026-10-03 ~ 2026-10-07）\n"
        "- [`archived_changelog.0.11.x.md`](../archive/v0.11.x/archived_changelog.0.11.x.md)"
        " — v0.11.0 ~ v0.11.12（2026-09-15 ~ 2026-10-03）\n"
    )


_EVOLUTION_SAMPLE = (
    "| 指标 | 最初版本（首个提交 · 2026-06-27） | 最新发布（最近发布 tag v0.12.5 · 2026-10-07）"
    " | 当前开发版（0.12.6-dev · 本次重跑时的工作区 · 2026-10-07） | 增长（最初 → 当前） |\n"
    "| 主程序（`src/**/*.py`，不含测试） | 30 文件 / 7,258 行 | 335 文件 / 88,669 行"
    " | 335 文件 / 88,669 行 | 12.2×\n"
    "| 测试（`src/test/**/*.py`） | 13 文件 / 6,108 行 | 484 文件 / 140,058 行"
    " | 484 文件 / 140,058 行 | 22.9×\n"
    "| 辅助脚本（`scripts/*.py`） | 0（当时仅 `launch.sh` / `launch.ps1`） | 57 文件 / 13,990 行"
    " | 57 文件 / 13,990 行 | 新增\n"
    "| HTML 报告模板（`src/static/tmpl/*.html`） | 0（当时为 `src/tmpl/`：1 个 / 469 行）"
    " | 22 文件 / 4,874 行 | 22 文件 / 4,874 行 | 1 → 22\n"
    "| 架构图示（SVG） | 0 | 3 文件 / 337 行 | 3 文件 / 337 行 | 新增\n"
    "| 文档（`.md`） | 7 文件 / 1,355 行 | 176 文件 / 66,469 行 | 176 文件 / 66,469 行 | 49.1×\n"
    "| **代码文件合计**（前 5 项） | **43** | **901** | **901** | 21.0×\n"
    "| **代码行合计**（前 5 项） | **13,366** | **247,928** | **247,928** | 18.5×\n"
    "| **测试用例数**（`def test_` 行数口径） | **491** | **8,833** | **8,833** | 18.0×\n"
    "| 仓库文件总数 | 56 | 1,126 | 1,126 | 20.1×\n"
    "| 仓库总行数（全部跟踪文件） | 15,600 | 322,464 | 322,464 | 20.7×\n"
    '> - **测试用例数**采 `git grep -c "def test_"` 的**行数口径**（含注释/文档串中的 `def test_` 提及）：'
    "最初 491 → 当前 8,833；按更严格的「以 `def test_` 开头的定义行（含类方法缩进）」口径为 8,792；"
    "按 pytest 实际收集（含参数化展开）为 **9,259** 项（另 20 项 opt-in live 反选，全量 9,279）。\n"
    "> - **测试 / 主程序行数比**由 0.84:1（6,108 / 7,258）升至 **1.58:1**（140,058 / 88,669，最新发布点），"
    "当前工作区为 **1.58:1**（140,058 / 88,669）。\n"
)


def _sample_review_findings() -> str:
    """主台账最小样本：一节本版已解决表 + 归档档案索引行。"""
    return (
        "# 自审记录\n\n## 已解决问题\n\n"
        "### 开发期已修复（0.12.6-dev）\n\n"
        "| # | 问题 | 处理 |\n|---|------|------|\n"
        "| **rf-901** | 问题甲 | 处理甲 |\n"
        "| **rf-902** | 问题乙 | 处理乙 |\n\n"
        "### 归档档案\n\n"
        "- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md)"
        " — v0.12.x 开发期已修复批次（2026-09-01 ~ 2026-10-05）\n"
    )


def _sample_rf_archive() -> str:
    """归档文件最小样本：头两行 + 一个既有批次节。"""
    return (
        "# 自审记录归档 — v0.12.x\n\n"
        "> 归档时间：2026-10-05（v0.12.5 发布）\n"
        "> 涵盖版本：v0.12.x 开发期已修复项（v0.12.1 → v0.12.5）\n\n---\n\n"
        "## 开发期已修复（0.12.5-dev）\n\n> 完整复盘见 `changelog.md` 0.12.5-dev 段；此处仅摘要行。\n\n"
        "- rf-900 已修复（2026-10-05）：旧条目\n"
    )


def _sample_plan() -> str:
    """计划样本：一个在办节（无完成标记）+ 两个已完成节（标题带 ✅）。"""
    return (
        "# 计划\n\n"
        "## plan-77 在办任务\n\n- [ ] 待做\n\n"
        "## plan-42 已完成任务 ✅\n\n**完成（2026-09-20，v0.12.3）**：已做\n\n"
        "## plan-43 另一完成项 ✅\n\n**完成（2026-09-25，v0.12.4）**：已做\n"
    )


_TREE_SAMPLE = """
````
├── docs/
│   ├── archive/
│   │   └── v0.12.x/                          # 版本归档
│   │       ├── archived_changelog.0.12.x.md # 变更日志归档
│   │       └── tui-runtime/                  # 某设计归档
│   │           └── tui-runtime.md # 设计
│   ├── managements/
│   │   └── plan.md # 计划
│   └── plan/                                 # 中间设计文件（在办）
│       ├── design-done.md # 已完成设计
│       └── design-open.md # 在办设计
└── README.md
````
"""


class _ToolRepoFixture:
    """把 release 模块的输出路径重定向到临时目录，并构造最小文件集。"""

    def __init__(self, rel_mod, tmp_path: Path):
        self.mod = rel_mod
        self.root = tmp_path
        core = tmp_path / "src" / "python" / "core"
        core.mkdir(parents=True)
        docs = tmp_path / "docs" / "managements"
        docs.mkdir(parents=True)
        archive = tmp_path / "docs" / "archive" / "v0.12.x"
        archive.mkdir(parents=True)
        (core / "constants.py").write_text('APP_VERSION = "0.12.6-dev"\n', encoding="utf-8")
        (tmp_path / "README.md").write_text(
            "> 当前版本：0.12.6-dev（[版本历史](docs/managements/changelog.md)）\n", encoding="utf-8"
        )
        (docs / "changelog.md").write_text(_sample_changelog(), encoding="utf-8")
        (archive / "archived_changelog.0.12.x.md").write_text("# 归档\n", encoding="utf-8")
        (docs / "folders.md").write_text(_EVOLUTION_SAMPLE + _TREE_SAMPLE, encoding="utf-8")
        (docs / "review-findings.md").write_text(_sample_review_findings(), encoding="utf-8")
        (docs / "plan.md").write_text(_sample_plan(), encoding="utf-8")
        plan_docs = tmp_path / "docs" / "plan"
        plan_docs.mkdir(parents=True)
        (plan_docs / "design-done.md").write_text("# 已完成设计\n\n依据 plan-42 落地。\n", encoding="utf-8")
        (plan_docs / "design-open.md").write_text("# 在办设计\n\n依据 plan-77 展开。\n", encoding="utf-8")
        (archive / "archived_review-findings.0.12.x.md").write_text(_sample_rf_archive(), encoding="utf-8")
        (archive / "archived_plan.0.12.x.md").write_text(
            "# 计划归档 — v0.12.x\n\n> 涵盖版本：v0.12.x（v0.12.1 → v0.12.5）\n\n---\n", encoding="utf-8"
        )
        paths = {
            "REPO_ROOT": tmp_path,
            "CONSTANTS_FILE": core / "constants.py",
            "README_FILE": tmp_path / "README.md",
            "CHANGELOG_FILE": docs / "changelog.md",
            "FOLDERS_FILE": docs / "folders.md",
            "_MANAGEMENTS_DIR": docs,
            "_ARCHIVE_DOCS_DIR": tmp_path / "docs" / "archive",
            "RF_FILE": docs / "review-findings.md",
            "PLAN_FILE": docs / "plan.md",
            "PLAN_DOCS_DIR": plan_docs,
            "GATE_STAMP_FILE": tmp_path / "logs" / "release-gate-stamp.json",
        }
        for name, value in paths.items():
            setattr(rel_mod, name, value)
            setattr(self, name, value)


def _ok_runner(overrides: list | None = None) -> FakeRunner:
    """预检/一致性/git 默认全过（工作树干净）；各测试按需覆写单条。"""
    pairs: list[tuple] = [
        (["git", "branch", "--show-current"], (0, "dev\n", "")),
        (["git", "status", "--porcelain"], (0, "", "")),
        (["git", "rev-parse"], (1, "", "")),
        (["scripts/check-version-consistency.py"], (0, "[OK] 15/15\n", "")),
        (["git", "status", "--short"], (0, " M docs/x.md\n", "")),
    ]
    for matcher, resp in overrides or []:
        pairs = [p for p in pairs if p[0] != matcher] + [(matcher, resp)]
    return FakeRunner(responses=pairs)
