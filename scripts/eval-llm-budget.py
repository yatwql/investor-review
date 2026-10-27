#!/usr/bin/env python3
"""LLM 表达预算校准（离线评测，不进三档门禁）。

用途：在不改生产代码的前提下，用冻结的持仓样本比较「不同预算档位 × 不同模式」
下的输出长度、墙钟与结构完整度，决定是否值得把预算落成默认值。

典型用法：

    # 1) 从最近一次持仓快照生成冻结样本（离线）
    .venv/bin/python scripts/eval-llm-budget.py freeze \\
        --snapshot data/history/snapshots/snapshot_20261026T214032.json

    # 2) 先看计划（不调用 LLM、零费用）
    .venv/bin/python scripts/eval-llm-budget.py run --dry-run

    # 3) 正式测量（真实调用，约 20 次生成；产物落 docs/tmp/llm-budget/）
    .venv/bin/python scripts/eval-llm-budget.py run --repeats 3

    # 4) 只跑标准模式，快速看趋势
    .venv/bin/python scripts/eval-llm-budget.py run --modes standard --tiers 4800,4000 --repeats 2

退出码：0 成功 / 1 运行失败 / 2 参数错误 / 3 判定不通过。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/ 导入面
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 仓库根：脚本需 import src.python.*

from _eval_llm_budget.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
