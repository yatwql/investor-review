# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.15.0]**（2026-10-24）——已发布版本段随发布移入 [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.15.1-dev] - 开发中（未发布）

- **`plan-204` 测试用例全量审计与整改**：机检补位四类人工判据（自证式用例 / 双结果放行 / 弱断言 / 名称与内容不一致），扫描 586 个测试文件、11,111 个 `def test_`，整改 23 例——安全基线 3 例自证式改触生产（`cache.set` 产物扫描 / LLM 源码禁止日志含 `api_key` / HTML 模板绝对路径扫描）、文件系统边缘 4 例双结果放行改按 `reader` 契约断言、配置崩溃清理补 `assertRaises`、弱断言 11 例补足语义（行业映射锁定指数代码、分位阈值、警告文案、参数校验原因、cassette 响应体、凭据声明字段）、启动向导 2 例合并、2 处死变量清理。对应台账 rf-851（自证式安全用例）、rf-852（双结果放行）、rf-853（崩溃清理），以及 rf-854（弱断言）、rf-855（重复用例与死变量）。

- **`plan-203` 发布流程四处改进（v0.15.0 复盘落地）**：① **失败前移**——`[C]` 日志动线改标 `scenario_basic`（dev-verify 也跑），动线驱动器新增「打点矩阵自证」（`builtins.input` 与各消费方读取入口必须都指向 feeder，局部导入绕过 patch 时直接报错）；② **bench 顺序**——发布子集调整为 `regression → integration → unit → dev-verify`，让 `--fail-fast` 在场景失败时立刻中止长尾 `unit`（实测曾白等约 45s）；③ **台账自证**——失败命令写 `failure`（失败步 / rc / 报告目录 / 失败用例名 / 输出尾部，保留第一现场），复盘不必再按 mtime 反查测试报告归档；④ **预检与记账**——`check` 增加 changelog 派生预演（只算不写，prepare 的文档手术问题在动文件前暴露）；publish 的提交/合并/tag/推送分段入账，gate 戳增存逐文件代码哈希，指纹不一致时点名「gate 后改动的代码文件」并说明将实跑 P1 verify。回归 9 例（发布工具 5 / 打点矩阵 2 / 无效编号提示 2）。对应台账 rf-844（publish 记账与重跑提示）、rf-845（check 派生预演）、rf-846（bench 顺序）、rf-847（台账失败字段）、rf-848（打点矩阵自证）、rf-849（无效编号提示派生）。

- **`rf-850` 概述行与归档完成标记口径对齐**：「当前迭代」重算的排除集并入「已完成」（原只认 ✅/❌），与 `plan_completed_sections` 的归档判据单源——台账里写「已完成，待发布归档」的任务不再被算作在办；回归 1 例。同时梳理 `plan.md`：已完成项只留状态摘要与归档去向，在办项只留现状与动作/判据，概述行按现存在办节重算。

- **`plan-202` 演示截图生成器入库**：README/手册配图的生成过程从 `docs/tmp/` 的一次性脚本收进仓库——入口 `scripts/make-screenshots.py`（`demo` / `report` / `tui` / `web` 四子命令）+ 实现包 `scripts/_screenshots/`（`demo_workspace.py` / `tui_frame.py` / `web_shot.py` + `cdp_shot.mjs`）。演示工作区两账户 6 只公开品种 + 明显占位凭据，配置用绝对路径、上屏路径由渲染端抹掉演示目录前缀，真实 `data/` 零接触；TUI 取帧走生产渲染函数（非真实 TTY，文本与配色同源），超宽行折行时在续行重新打开配色；Web 档按「导航 → 文本替换 → 滚动 → 截视口」取图（固定侧栏不丢），浏览器从 `--chrome` / `CHROME_BIN` / Playwright 缓存 / 系统路径依次解析。16 例回归覆盖演示持仓与配置口径、报告命令装配、折行保色与路径瘦身、渲染尺寸、浏览器解析次序、入口分发；`scripts-reference.md` / `developer-guide.md` 按域索引 / `folders.md` 目录树同步登记。

- **`plan-201` 事实校验评估函数参数收敛（`rf-839` 技术债）**：`llm/fact_checker/_numerical.py::_evaluate_percent_value` 的 22 个参数（7 基础值 + 10 语境开关 + 5 数据映射）收进冻结 dataclass `PercentContext`——字段即语义，新增一种语境只需加字段并在调用点赋值，不必再改签名/文档/全部直接用例；函数签名收敛为 `_evaluate_percent(ctx)`，语境判定优先级（非收益率早退 → 回撤 → 收益语境）仍在函数体内单源维持。行为零变化：`src/test/unit/llm` 1326 例全绿（含 rf-836 的 6 例回归）。

- **`plan-200` 配置体系重构第 15 轮：稳态观测与回退演练**（配置重构 15 轮到齐）：新增 `src/test/unit/config/test_config_resilience_contract.py`（10 例，全部 `tmp_path` 隔离）把四类路径变成可复跑断言——① **非法配置不静默**：非法 `schema_version` 返回 None 且日志含文件名 + 键 + 原因；`logger.json` 单键非法只回落该键（其余键按文件生效）；② **删除后重建**：`llm_settings.json` v2 模板、`logger.json` 幂等 `ensure_logger_file`、`llm_pricing_ref.json` 默认模板（23 个模型价）重建后均可加载；③ **缓存首轮重算**：首轮未命中 → 写入 → 次轮命中（目录隔离统一由 conftest 提供）；④ **非当前结构拒绝**：消息含「删除该文件后重新生成」。实测（临时目录）：非法配置 0.1ms 内检出并拒绝、三份重建即用、无静默降级。观测项复用现有日志与 `perf_history`，未新增面板。

- **`rf-843` Web 配置面板块标题显示内部 id + 调优块渲染报错**：块标题曾用 `labels[blockKey]` 取，而 `labels` 只登记可编辑键，`sections` / `llm` / `standalone_*` 等块直接显示英文 id；重拍截图时又发现 `renderTuningGroup` 与块标题取源不一致（引用未定义 `surface`），整个配置面板渲染失败。修复：新增 `block_titles` 随面下发（单一来源，11 个块 id 全覆盖），前端一律取服务端下发的标题（不回退到块 id、不写死中文）；`renderAnonGroup` / `renderTuningGroup` 改为接收 `surface`；契约测试补「每块都有中文标题且标题≠块 id」两例。

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.15.x.md`](../archive/v0.15.x/archived_changelog.0.15.x.md) — v0.15.0（2026-10-24）
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
