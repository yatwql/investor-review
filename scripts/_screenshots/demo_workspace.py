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
    workbook.remove(workbook.active)
    for account in dict.fromkeys(item[0] for item in HOLDINGS):
        sheet = workbook.create_sheet(account)
        sheet.append(["名称", "代码", "持仓份额", "每份成本"])
        for row_account, name, code, shares, cost in HOLDINGS:
            if row_account == account:
                sheet.append([name, code, shares, cost])
    workbook.save(holdings_dir / HOLDINGS_FILENAME)


def build(output_root: Path | None = None) -> Path:
    """建（或刷新）演示工作区，返回其目录。"""
    demo = demo_dir(output_root)
    config_dir = demo / "data" / "config"
    for path in (config_dir, demo / "reports"):
        path.mkdir(parents=True, exist_ok=True)

    _write_holdings(demo)
    config = _config(demo)
    (config_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (config_dir / "llm_key.json").write_text(
        json.dumps({"provider": "claude", "api_key": DEMO_API_KEY}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
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


def run_report(output_root: Path | None = None) -> int:
    """在演示工作区跑一次报告生成，返回命令行退出码（工作区缺失时先建）。"""
    config = config_path(output_root)
    if not config.is_file():
        build(output_root)
    demo = demo_dir(output_root)
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    completed = subprocess.run(
        report_command(config),
        cwd=demo,
        env=env,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    print(f"  [{'OK' if completed.returncode == 0 else 'ERR'}] 演示报告（{demo / 'reports'}）")
    return completed.returncode
