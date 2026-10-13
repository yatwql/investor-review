# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.0]**（2026-10-13）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.1-dev] - 开发中（未发布）

### Added

- 报告「投资分析汇总」市场温度行下新增**计算逻辑**与**分级标准**两行说明（低估＜30 分 / 合理 30~70 分 / 高估＞70 分，边界值归合理档；三因子权重 50%/30%/20%，波动率反向越波动越冷）——文案由计算层权重/阈值常量单源派生，改常量自动跟随；展示构建器缺字段时两行静默省略（旧契约兼容）。

### Changed

- 脚本目录优化批次：`release.py` 拆 `_release/` 内部实现包（共享原语/版本号纯函数/changelog 归档/演进快照四模块，入口保留 CLI 与命令壳，869→517 行）；文档路径常量上收 `_checklib`（5 检查脚本与 doc-drift 内部包的内联拼路径收编）；`check-script-contract` 规则② 增加 `args.verbose` 消费侧 AST 检查（防空开关，`check-svg.py` 的空 -v 同步实现消费）；三守护同次运行双扫消除（doc-traces 四遍目录走查收敛为一遍 / doc-drift `-v` 模式二次全量读复用首轮 / semantic-index 指纹面与扫描面同源）；演进统计对测试文件的全量二次读消除；三个 sh 启动垫片加 `set -euo pipefail`。


（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0（2026-10-13）
- [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md) — v0.12.1 ~ v0.12.13（2026-10-03 ~ 2026-10-13）
- [`archived_changelog.0.11.x.md`](../archive/v0.11.x/archived_changelog.0.11.x.md) — v0.11.0 ~ v0.11.12 + v0.12.0（2026-09-15 ~ 2026-10-03）
- [`archived_changelog.0.10.x.md`](../archive/v0.10.x/archived_changelog.0.10.x.md) — v0.10.1 ~ v0.10.19（2026-08-04 ~ 2026-09-13）
- [`archived_changelog.0.9.x.md`](../archive/v0.9.x/archived_changelog.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_changelog.0.8.x.md`](../archive/v0.8.x/archived_changelog.0.8.x.md) — v0.8.0 ~ v0.8.11（2026-07-21 ~ 2026-07-30）
- [`archived_changelog.0.7.x.md`](../archive/v0.7.x/archived_changelog.0.7.x.md) — v0.7.0 ~ v0.7.9（2026-07-18 ~ 2026-07-21）
- [`archived_changelog.0.6.x.md`](../archive/v0.6.x/archived_changelog.0.6.x.md) — v0.6.0 ~ v0.6.10（2026-07-15 ~ 2026-07-18）
- [`archived_changelog.0.5.x.md`](../archive/v0.5.x/archived_changelog.0.5.x.md) — v0.5.0 ~ v0.5.12（2026-07-14 ~ 2026-07-15）
- [`archived_changelog.0.4.x.md`](../archive/v0.4.x/archived_changelog.0.4.x.md) — v0.4.0 ~ v0.4.5（2026-07-12 ~ 2026-07-14）
- [`archived_changelog.0.3.x.md`](../archive/v0.3.x/archived_changelog.0.3.x.md) — v0.3.0 ~ v0.3.10（2026-07-08 ~ 2026-07-12)
- [`archived_changelog.0.2.x.md`](../archive/v0.2.x/archived_changelog.0.2.x.md) — v0.2.0 ~ v0.2.91（2026-06-27 ~ 2026-07-08）
- [`archived_changelog.0.1.x.md`](../archive/v0.1.x/archived_changelog.0.1.x.md) — 早期版本记录
