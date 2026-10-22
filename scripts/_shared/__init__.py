"""跨脚本共享设施包（检查脚本的 CLI 契约原语 + 跨域词表）。

`scripts/` 顶层只保留可直接运行的入口；共享库一律落在内部包中：

  - `checklib.py`       ← CLI 契约（`-v/--ci`）、输出、路径、文档区间解析、结论缓存
  - `traces_common.py`  ← 代码注释域与用户文档域共用的历史叙述正则单一来源

包内模块用 `from _shared.checklib import …` / `from _shared.traces_common import …`
引用（调用方已把 `scripts/` 放入 sys.path）。
"""
