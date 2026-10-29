"""隔离演示工作区：截图用的自造持仓 + 占位凭据 + 报告生成。

截图要展示 `data/holdings`、`reports` 这类**相对路径**，直接引用真实配置会把本机绝对路径
印上屏。演示工作区（默认 `docs/tmp/screenshots/demo/`，git 忽略域）与真实 `data/` 完全隔离：
持仓是公开品种 + 自造整数份额成本，凭据是明显占位值，报告也只写进演示目录。

配置用**绝对路径**（相对路径会被解析到项目根），上屏的相对路径由 TUI 渲染端抹掉演示目录
前缀得到（`data/holdings` / `reports`），因此工作区不必再维护第二份「展示用配置」。

用法见入口 `scripts/make-screenshots.py demo|report`。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO_ROOT / "docs" / "tmp" / "screenshots"

#: 演示持仓：(账户, 名称, 代码, 份额, 每份成本) —— 公开品种 + 自造整数，与任何真实账户无关
HOLDINGS: tuple[tuple[str, str, str, float, float], ...] = (
    ("演示账户A", "沪深300ETF", "510300", 20000, 3.85),
    ("演示账户A", "中证500ETF", "510500", 8000, 5.62),
    ("演示账户A", "贵州茅台", "600519", 100, 1480.0),
    ("演示账户B", "宁德时代", "300750", 300, 210.0),
    ("演示账户B", "易方达蓝筹精选", "005827", 15000, 2.31),
    ("演示账户B", "招商中证白酒", "161725", 12000, 0.95),
)

HOLDINGS_FILENAME = "演示持仓.xlsx"

#: 占位凭据：值明显不是真 key，让首页状态行显示「LLM 已配置」而非首次使用告警
DEMO_API_KEY = "sk-demo-not-a-real-key"

#: 演示工作区的凭据块名（llm_key.json 的键 = llm_providers.json 的 credentials_ref）
DEMO_CREDENTIALS_REF = "demo-main"

#: 运行上下文标签（真实运行为空）——日志分析据此区分演示产出与真实产出
DEMO_RUN_CONTEXT = "demo"


#: 演示报告运行会写真实运行状态（perf 台账 / 健康历史 / 实验与熔断状态 / 去重锚点）。
#: 「真实 data/ 零接触」要求这些目录在跑前快照、跑后原样还原。
GUARDED_STATE_DIRS: tuple[str, ...] = ("data/state", "data/calibration", "data/history")


def snapshot_paths(paths: tuple[Path, ...]) -> dict[Path, bytes]:
    """把这些目录下的文件全部读入内存（不存在或不可读的目录忽略）。"""
    snap: dict[Path, bytes] = {}
    for base in paths:
        if not base.is_dir():
            continue
        for file in base.rglob("*"):
            if file.is_file():
                snap[file] = file.read_bytes()
    return snap


def restore_paths(paths: tuple[Path, ...], snap: dict[Path, bytes]) -> None:
    """还原快照：删掉运行期新增的文件，写回原有内容。"""
    for base in paths:
        if not base.is_dir():
            continue
        for file in base.rglob("*"):
            if file.is_file() and file not in snap:
                file.unlink(missing_ok=True)
    for file, data in snap.items():
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)


def demo_dir(output_root: Path | None = None) -> Path:
    """演示工作区目录（默认 `docs/tmp/screenshots/demo`）。"""
    return (output_root or DEFAULT_ROOT) / "demo"


def _config(demo: Path) -> dict[str, object]:
    """按演示工作区绝对路径装配配置（报告生成用）。"""
    return {
        "holdings_dir": str(demo / "data" / "holdings"),
        "holdings_filename": HOLDINGS_FILENAME,
        "output_dir": str(demo / "reports"),
        "llm_key_file": str(demo / "data" / "config" / "llm_key.json"),
        "llm_settings_file": str(demo / "data" / "config" / "llm_settings.json"),
        "llm_providers_file": str(demo / "data" / "config" / "llm_providers.json"),
        "data_key_file": str(demo / "data" / "config" / "data_key.json"),
        "news_sources": {},
        "history": {"fetch_mode": "auto", "days": 365},
        "daily_cost_limit": 0,
        "notify": {"desktop": False},
    }


def _write_holdings(demo: Path) -> None:
    """按账户分 worksheet 写演示持仓（固定四列：名称/代码/持仓份额/每份成本）。"""
    from openpyxl import Workbook

    holdings_dir = demo / "data" / "holdings"
    holdings_dir.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    default_sheet = workbook.active
    if default_sheet is not None:
        workbook.remove(default_sheet)
    for account in dict.fromkeys(item[0] for item in HOLDINGS):
        sheet = workbook.create_sheet(account)
        sheet.append(["名称", "代码", "持仓份额", "每份成本"])
        for row_account, name, code, shares, cost in HOLDINGS:
            if row_account == account:
                sheet.append([name, code, shares, cost])
    workbook.save(holdings_dir / HOLDINGS_FILENAME)


def _write_llm_files(demo: Path) -> None:
    """写入演示工作区的 LLM 配置对（凭据块名与 provider 引用同名）。

    两份文件必须同位：``llm_key.json`` 的凭据块名 = ``DEMO_CREDENTIALS_REF``，
    ``llm_providers.json`` 只声明引用同一个块。不同名时每次演示 run 都会刷
    「引用凭据在 llm_key.json 中不存在」的 WARNING，把真实日志里的告警统计带偏；
    凭据本身是明显占位值，不连任何真实源。
    """
    config_dir = demo / "data" / "config"
    (config_dir / "llm_key.json").write_text(
        json.dumps(
            {DEMO_CREDENTIALS_REF: {"api_key": DEMO_API_KEY, "model": "demo-model"}}, ensure_ascii=False, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    (config_dir / "llm_providers.json").write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "name": DEMO_CREDENTIALS_REF,
                        "provider": "claude",
                        "credentials_ref": DEMO_CREDENTIALS_REF,
                        "priority": 10,
                        "timeout": 120,
                    }
                ],
                "strategy": "priority",
                "preferred_providers": {},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def isolation_env(demo: Path) -> dict[str, str]:
    """演示运行的环境变量：日志与缓存都改落演示目录，真实 data/ 与 logs/ 零接触。

    Returns:
        需并入子进程 env 的键值对。
    """
    return {
        "INVEST_PROJECT_ROOT": str(demo),
        "INVEST_LOG_PATH": str(demo / "logs" / "app.log"),
        "INVEST_RUN_CONTEXT": DEMO_RUN_CONTEXT,
        "INVEST_CACHE_DIR": str(demo / "data" / "cache"),
    }


def _link_repo_src(demo: Path) -> None:
    """把仓库 ``src/`` 软链进演示根：``PROJECT_ROOT`` 指向演示根后，模板与静态资产仍可解析。

    隔离的是「数据面」（``data/`` / ``reports/``），代码与模板资产不复制——
    否则演示根会变成第二份源码树，容易与仓库漂移。
    """
    import os

    link = demo / "src"
    target = REPO_ROOT / "src"
    if link.is_symlink() or link.exists():
        return
    try:
        os.symlink(target, link, target_is_directory=True)
    except OSError:
        print(f"  [!] 无法创建 src 软链（Windows 需开发者模式）：{link}")


def assert_demo_holdings(output_root: Path | None = None) -> Path:
    """护栏：演示持仓文件存在且位于演示目录内，否则拒绝继续（防截图读到真实持仓）。

    隔离方式是整体搬项目根（``INVEST_PROJECT_ROOT``）：配置、持仓、产物同在演示目录。
    本断言兜住「环境没带上」的情形——宁可报错，不出带真实数据的图。

    Returns:
        演示工作区目录。

    Raises:
        RuntimeError: 演示持仓缺失，或调用方解析出的路径逃出演示目录。
    """
    demo = demo_dir(output_root).resolve()
    holdings = (demo / "data" / "holdings" / HOLDINGS_FILENAME).resolve()
    if demo not in holdings.parents:
        raise RuntimeError(f"演示隔离失效：{holdings} 不在演示目录内，拒绝截图")
    if not holdings.is_file():
        raise RuntimeError(f"演示持仓文件不存在（{holdings}），先跑 make-screenshots.py demo")
    return demo


def build(output_root: Path | None = None) -> Path:
    """建（或刷新）演示工作区，返回其目录。"""
    demo = demo_dir(output_root)
    config_dir = demo / "data" / "config"
    for path in (config_dir, demo / "reports"):
        path.mkdir(parents=True, exist_ok=True)

    _link_repo_src(demo)
    _write_holdings(demo)
    _write_llm_files(demo)
    config = _config(demo)
    (config_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return demo


def config_path(output_root: Path | None = None) -> Path:
    """演示工作区的报告配置路径。"""
    return demo_dir(output_root) / "data" / "config" / "config.json"


def report_command(config: Path) -> list[str]:
    """在演示工作区生成 Excel+HTML 报告的命令行（cwd 由调用方设为演示目录）。"""
    return [
        sys.executable,
        "-m",
        "src.python.cli",
        "--config",
        str(config),
        "report",
        "--type",
        "both",
        "--history",
        "auto",
        "--yes",
    ]


def clean_cli_text(text: str, *, tail_lines: int = 22) -> list[str]:
    """CLI 输出 → 可直接上屏的行（去进度回车残段、抹演示路径、只留尾部）。

    Args:
        text: 伪终端捕获的原始输出（含 ``\r`` 进度刷新与 ANSI 色）。
        tail_lines: 保留末尾行数（默认 22：汇总 + 耗时排行 + 产物路径，够用不冗长）。

    Returns:
        逐行文本列表；空行被丢弃。
    """
    import re

    # 控制台日志前缀「2026-10-27 07:52:43,331 」剥掉，上屏只留「[INFO] 正文」——
    # 与实机配色/可读性一致，也避免同一屏出现五个不同秒数干扰阅读。
    stamp = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} ")
    lines: list[str] = []
    # 终端输出的行尾是 CRLF：先把 CRLF 归一成 LF，再按 LF 切行，最后才把行内的
    # 孤立 \r 当进度刷新取末段（顺序错了会把整行当成「末段为空」而全部丢弃——
    # 实测：CRLF 未归一 + 先 split("\r") 时，23KB 输出只剩 1 行）。
    for raw in text.replace("\r\n", "\n").split("\n"):
        segment = raw.split("\r")[-1].rstrip()  # 进度刷新只保留最后一次
        segment = stamp.sub("", segment)
        if not segment.strip():
            continue
        lines.append(segment)
    lines = scrub_cli_paths(lines)
    return lines[-tail_lines:]


def scrub_cli_paths(lines: list[str]) -> list[str]:
    """抹掉绝对路径前缀（演示工作区 → 空，仓库根 → 空），上屏读作相对路径。"""
    prefixes = sorted({str(demo_dir().resolve()), str(REPO_ROOT)}, key=len, reverse=True)
    out: list[str] = []
    for line in lines:
        for prefix in prefixes:
            line = line.replace(prefix + os.sep, "").replace(prefix, "")
        out.append(line)
    return out


def capture_report_text(output_root: Path | None = None) -> str:
    """用伪终端跑一次演示报告，返回可上屏的 CLI 输出（含进度与耗时排行）。

    伪终端是必要的：CLI 在非 TTY 下会退化为无进度/无耗时排行的精简输出，
    截出来的图与用户真机所见不一致。运行同样受状态护栏保护。
    """
    import pty

    config = config_path(output_root)
    if not config.is_file():
        build(output_root)
    demo = demo_dir(output_root)
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT),
        "TERM": "xterm-256color",
        "COLUMNS": "110",
        **isolation_env(demo),
    }
    guarded = tuple(REPO_ROOT / rel for rel in GUARDED_STATE_DIRS)
    snap = snapshot_paths(guarded)
    master, slave = pty.openpty()
    try:
        proc = subprocess.Popen(
            report_command(config),
            cwd=demo,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=slave,
            stderr=slave,
            close_fds=True,
        )
        os.close(slave)
        chunks: list[bytes] = []
        while True:
            try:
                chunk = os.read(master, 65536)
            except OSError:  # 从端关闭
                break
            if not chunk:
                break
            chunks.append(chunk)
        proc.wait(timeout=900)
        text = b"".join(chunks).decode("utf-8", errors="replace")
    finally:
        os.close(master)
        restore_paths(guarded, snap)
    return "\n".join(clean_cli_text(text))


def run_report(output_root: Path | None = None) -> int:
    """在演示工作区跑一次报告生成，返回命令行退出码（工作区缺失时先建）。"""
    config = config_path(output_root)
    if not config.is_file():
        build(output_root)
    demo = demo_dir(output_root)
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT), **isolation_env(demo)}
    guarded = tuple(REPO_ROOT / rel for rel in GUARDED_STATE_DIRS)
    snap = snapshot_paths(guarded)
    try:
        completed = subprocess.run(
            report_command(config),
            cwd=demo,
            env=env,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    finally:
        # 演示运行写下的 perf 台账 / 健康历史 / 去重锚点一律还原（截图不污染真实统计）
        restore_paths(guarded, snap)
    print(f"  [{'OK' if completed.returncode == 0 else 'ERR'}] 演示报告（{demo / 'reports'}）")
    return completed.returncode
