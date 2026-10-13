"""发布编排内部实现拆分（入口与 CLI 面保留在 `scripts/release.py`）。

- `_common`：ReleaseError 与子进程执行原语（各步骤共享）
- `_versioning`：版本号解析/渲染纯函数（X.Y.Z-dev 推导与改写）
- `_changelog_archive`：changelog 发布段迁出与归档追加（纯文本变换）
- `_evolution`：版本演进快照统计与表格回写（纯函数）

拆分纪律：下沉模块只收**显式参数**（文本/root/runner），不读入口模块的
路径常量——路径解析留在入口，保证测试对入口模块属性的重定向始终生效。
"""
