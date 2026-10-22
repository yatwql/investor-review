"""发布编排内部实现拆分（入口 `scripts/release.py` 只保留路径常量 / `env` 投影 / 薄包装 / `main`）。

- `_common`：ReleaseError 与子进程执行原语（各步骤共享）
- `_cli`：argparse 装配（`build_parser`）与命令分派（`run_cli`），bench 模式子集常量的声明点
- `_commands_base`：命令共用原语（耗时埋点 / 预检 / git 探测 / 发布戳 / 归档路径推导）
- `_commands_prep`：准备阶段命令实现（check / archive-init / prepare / archive）
- `_commands_ship`：交付阶段命令实现（refresh / evolution / publish / devbump）
- `_versioning`：版本号解析/渲染纯函数（X.Y.Z-dev 推导与改写）
- `_changelog_archive`：changelog 发布段迁出、归档追加与归档头部两行派生（纯文本变换）
- `_archive_flow`：归档迁移的命令编排（显式 `ArchiveContext` 路径入参、先算后写、前置缺件清单）
- `_ledger_archive`：台账与设计文档归档迁移（rf 已解决表原表搬运 + 占位/头部/索引派生、
  plan 已完成节搬入、docs/plan 完成判定与引用/目录树搬迁——纯文本变换，判定边界留人）
- `_evolution`：版本演进快照统计与表格回写（纯函数）

拆分纪律：下沉模块只收**显式参数**（文本/root/runner/**env**），不读入口模块的
路径常量——路径解析留在入口；`env` 是入口模块的属性投影（每次访问回读当前值），
故测试对入口模块做 `setattr` 重定向对下沉实现同样生效。
"""
