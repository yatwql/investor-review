# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.12.10]**（2026-10-11）——已发布版本段随发布移入 [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.12.11-dev] - 开发中（未发布）

### Added
- **风险调整超额与基准对照（plan-85，开关 `risk_adjusted_excess`，默认关）**：组合历史走势与回撤章新增第五区块「风险调整超额」（Excel + HTML 双端同源）——逐基准年化 IR / 跟踪误差 / 几何年化超额 + 近 12/24 个完整月跑赢胜率 + 滚动 250 日超额序列（HTML 折线图）；IR/TE 需 ≥60 对齐交易日、滚动需 ≥250，样本不足逐项「数据不足」占位（分层降级）；未配置业绩基准整块「数据不可用：<原因>」。度量实现 `analysis/benchmark_excess.py`（纯标准库、analysis 层隔离），装配 `report/_snapshot.py::assemble_history_augmented_data`（full/both 双路径同源，防契约漂移）。
- **危机区间双层回放（plan-88，开关 `crisis_replay`，默认关）**：危机区间标注区块升级——组合层统计子块扩展窗（max(lookback, 365) 交易日）内静态危机区间的组合收益/回撤/恢复（窗外行标「组合窗口外」），指数层覆盖全部静态区间（新增 2025 关税冲击锚点；指数长窗日线按静态表最早起点动态推算天数、封顶 3650）给出指数区间收益与区间最大回撤；未配置业绩基准时指数层静默缺席、组合层照常。`CRISIS_INTERVALS` 静态清单单一来源，全端标题/说明/占位动态跟随（移除 Excel 危机注释、HTML 章标题与占位文案的硬编码年份清单）。
- 两开关共享同一次子块扩展窗取数（未开启时零新增网络请求、产物逐字节一致）；同步区块契约注册表（走势章 4→5 区块）、TUI 面板编号、开关表与附录 H。
- **品牌**：猫头鹰吉祥物「守望」上线——新增 `src/static/owl-mascot.svg`（卡通猫头鹰立于净值增长曲线，底色与 architecture.svg 同源），README 头部嵌入并补定位描述（夜间守望 / 智慧顾问不越位 / 全景视野 / 守口如命）；favicon.svg 改为品牌蓝底 + 猫头鹰头像（16px 可辨）。

### Fixed
- **favicon**：旧图标 XML 注释内含 `--` 非法 token，严格 XML 解析器下图标渲染失败——随品牌图标重绘顺带修复。

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md) — v0.12.1 ~ v0.12.10（2026-10-03 ~ 2026-10-11）
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
