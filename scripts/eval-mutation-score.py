#!/usr/bin/env python3
"""变异得分离线评测入口（`eval-` 域：不进提交/发布门禁）——只装配 CLI 并调用执行面。

行覆盖率证明「用例执行过这行代码」，不证明「断言住了这行代码的行为」；本脚本用变异得分作为
**测试有效性指标**：按目标切片逐点注入变异，再跑该切片的相关测试。逐切片执行、判定与汇总输出
在 `_eval_mutation/cli.py`，目标表与默认阈值在 `_eval_mutation/targets.py`，内置变异器与安全阀
在 `_eval_mutation/runner.py`。

用法：
  .venv/bin/python scripts/eval-mutation-score.py --list-targets   # 目标清单（不依赖后端）
  .venv/bin/python scripts/eval-mutation-score.py --dry            # 只打印执行计划
  .venv/bin/python scripts/eval-mutation-score.py                  # 实跑全部切片并判定
  .venv/bin/python scripts/eval-mutation-score.py --only core-dates -v
  .venv/bin/python scripts/eval-mutation-score.py --json           # 机读结果
  .venv/bin/python scripts/eval-mutation-score.py --ci             # 仅输出 文件:描述（未达标各一行）

退出码：
  0 — 全部目标得分达标（`--list-targets` / `--dry` 亦返回本码）
  1 — `--backend mutmut` 但后端未安装（环境缺失，已打印安装命令；内置后端不会返回本码）
  2 — 存在低于阈值或无法解析得分的目标；工作树脏（拒跑）；切片名未匹配；还原校验失败
  130 — 用户中断（Ctrl-C），原文件已还原
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── 项目路径（脚本独立运行：先把仓库根与 scripts/ 加入 sys.path 以引用内部包） ──
_SCRIPTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
for _path in (str(_PROJECT_ROOT), str(_SCRIPTS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from _eval_mutation.cli import main

if __name__ == "__main__":
    sys.exit(main())
