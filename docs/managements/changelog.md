# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.19.0]**（2026-11-27）——已发布版本段随发布移入 [`archived_changelog.0.19.x.md`](../archive/v0.19.x/archived_changelog.0.19.x.md)；本文件只保留当前开发版本段与归档索引。

---

## [0.19.1-dev] - 开发中（未发布）

### 新增
- **质量三件套第 1 件：测试有效性机检两条**——`check-test-redundancy` 增设第 10 类「patch 打在 re-export 面」（只报非公开面，避免把门面替换误判为回归），并新增**会话级全局状态泄漏守卫**：模块级可变全局在用例结束后未复原即报，堵住「上一条用例改写单例、下一条用例因此变绿」的串扰
- **质量三件套第 2 件：变异测试基座 `scripts/eval-mutation-score.py`**（离线评测域，阈值三态退出码）——内置有界变异器，四类算子（比较/布尔/数值/边界）+ 备份恢复四层安全阀（原文件快照、恢复后逐文件校验、进程异常兜底复原、只写工作副本）；首期基线 `core-dates` 100% / `analysis-correlation` 76%
- **属性测试落地**（hypothesis）：相关性对称 / 缩放 / 置换不变与数值工具守恒不变量；测试依赖按单源登记，不与运行时依赖混列
- **两条静态机检**：浮点均值/方差必须 `math.fsum`（含 20 处等价改写）、测试禁真实耗时与真实子进程（`check-test-redundancy` 第 11 类）
- **`scripts/_shared/exceptions.py` 例外表协议归一**：各守护脚本的例外/豁免表改由同一协议读写（键形态、替代路径、复核期限字段一致），新增例外不再各写一套解析

### 修复
- **全仓审计 3 项 P1（rf-1255、rf-1256、rf-1257）**：渲染期上下文彻底移出模块级 dict（图表数据与章节可见性一律经 `render()` context 传递，`_ENV.globals` 只剩导入期 fail-closed 设置）；TUI `[R]` 面板分组标题去双重分隔符（DESIGN-TUI 提示三段式）；空态文案不再染状态色，改走 `data-status` 语义属性（DESIGN 空态口径）
- **测试域 `F821` 取消按文件豁免（rf-1258）**：引号注解改走 `TYPE_CHECKING` 导入块，清 5 条 per-file-ignore 与 1 处真实未定义名——未定义名从此是硬错误而非豁免噪声
- **事实缓存指纹夹具补显式 `encoding`（rf-1259）**：CI `portability` 严格档（`PYTHONWARNDEFAULTENCODING=1`）下不再因隐式编码红
- **变异评测 JSON 汇总得分的期望值改由切片数派生（rf-1260）**：新增切片不再把「总数写死」的断言误打成红
- **107 小时变更审计整改（rf-1261）**：例外表协议归一、变异评测入口收薄（不再为测试直调面 re-export 内部符号）、事实缓存指纹覆盖全部规则模块，并清 8 项 P2

### 变更
- **板块前缀知识收为单源前缀表**：后缀推断与市值档共用同一张表，`core/code_utils.py` 外不再各写一份前缀串；文档十一类措辞对齐
- **巨型函数与口径债务继续挂账监控**：本轮审计识别的超长函数留在 `review-findings.md` 的 P4 文件膨胀登记表（含拆分方向），不在本版强行拆分

### 测试
- **变异基线从零扩到六切片**：`core-dates` 100%、`analysis-correlation` 76% → 四切片收口（`analysis-metrics` 77.5%→95.0%、`cache-ttl-atomic-write` 55.0%→100%、`cache` 100%（278/278）、`metrics` 93.8%（9 个等价变异体））→ 六切片（`pipeline-data` 87%→100%、`factor-formulas` 42.5%→92.5%）
- **因子公式数值断言批**：按「可手算定值」给公式型模块补数值断言（区别于只断言形状/符号），`pipeline_data` 契约补未注册键不自动登记等断言
- **相关性数值链断言**：p 值 / `pearson_r` / 滚动趋势 / 完整窗边界 / 全窗不足降级逐项可区分
- **缓存边界与返回契约**：「组清空 0 条」「命中率无样本」两个零值边界 + 缓存读侧返回契约（坏载荷按未命中，不抛错）
- 变异评测 `--jobs>1` 时对共享导入面给出警告（并行改同一文件会互相覆盖备份）

## 归档

- [`archived_changelog.0.19.x.md`](../archive/v0.19.x/archived_changelog.0.19.x.md) — v0.19.0（2026-11-27）
- [`archived_changelog.0.18.x.md`](../archive/v0.18.x/archived_changelog.0.18.x.md) — v0.18.0 ~ v0.18.7（2026-11-12 ~ 2026-11-26）
- [`archived_changelog.0.17.x.md`](../archive/v0.17.x/archived_changelog.0.17.x.md) — v0.17.0 ~ v0.17.9（2026-11-04 ~ 2026-11-11）
- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.17（2026-10-25 ~ 2026-11-03）
- [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md) — v0.15.0 ~ v0.15.9（2026-10-24 ~ 2026-10-25）
- [`archived_changelog.0.14.x.md`](../archive/v0.14.x/archived_changelog.0.14.x.md) — v0.14.0 ~ v0.14.8（2026-10-21 ~ 2026-10-23）
- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.12（2026-10-13 ~ 2026-10-21）
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
