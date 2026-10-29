# -*- coding: utf-8 -*-
"""`PROJECT_ROOT` 环境覆盖（`INVEST_PROJECT_ROOT`）回归测试。

该覆盖是演示截图/回归夹具的隔离闸门：配置、持仓、产物全部随根切换；
未设置时必须回落到仓库根（缺省行为不变）。子进程验证——常量在 import 期求值，
同进程无法安全重算。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

REPO_ROOT = Path(__file__).resolve().parents[4]


def _probe(env_root: str | None) -> dict:
    """在子进程里 import constants/config，返回根与派生路径。"""
    code = (
        "import json;"
        "from src.python.core.constants import PROJECT_ROOT;"
        "from src.python.config import resolve_holdings_path, resolve_output_dir;"
        "print(json.dumps({'root': PROJECT_ROOT,"
        " 'holdings': resolve_holdings_path(), 'output': resolve_output_dir()}))"
    )
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    if env_root is None:
        env.pop("INVEST_PROJECT_ROOT", None)
    else:
        env["INVEST_PROJECT_ROOT"] = env_root
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_project_root_falls_back_to_repo_when_unset():
    data = _probe(None)
    assert Path(data["root"]) == REPO_ROOT
    assert Path(data["holdings"]).is_relative_to(REPO_ROOT)
    assert Path(data["output"]).is_relative_to(REPO_ROOT)


def test_project_root_override_moves_data_and_reports(tmp_path: Path):
    """设置覆盖后：根、持仓目录与产物目录全部落到覆盖根（真实 data/reports 零接触）。"""
    (tmp_path / "data" / "holdings").mkdir(parents=True)
    data = _probe(str(tmp_path))

    assert Path(data["root"]) == tmp_path
    assert Path(data["holdings"]).is_relative_to(tmp_path)
    assert Path(data["output"]).is_relative_to(tmp_path)
    assert Path(data["output"]) == tmp_path / "reports"
