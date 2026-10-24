# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.15.1-dev
> **编号源**：`rf-next = 856`（新增问题取此编号，完成后更新为 +1；已用最大 rf-855，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | Web 模式浏览器真机验收余 **4 类人工项**：真实 basic/full 进度观察（3.1c / 3.2 / 3.3 / 3.4）、结果区按钮（4.5）、提交即禁用（5.3）、真实拖拽与 Tab / Enter 抽验（2.5 / 2.6）；其余项已由自动化用例覆盖 | 判定标准见 [`../archive/v0.15.x/web-browser-verification/web-browser-verification.md`](../archive/v0.15.x/web-browser-verification/web-browser-verification.md)（启动 / 收尾命令 + 复验清单）；复跑 `.venv/bin/python scripts/test-smoke-web.py` + `node docs/tmp/browser-verify/cdp-check.mjs`；收尾 kill 服务与浏览器、清空 `data/holdings/uploads/`；全部通过后移入已解决 |

### P2 — 中优先：价值明确、成本可控（下批排期）

入选标准：重构收益明确、回归面可圈定，且不与在办功能争抢同一批文件。

当前无待办项。

| # | 问题 | 修复方向 |
|---|------|----------|

### P3 — 持续监控：文件膨胀登记

> **单一事实源**：行数、登记线与拆分优先级以 `scripts/check-file-length.py -v` 为准（主程序警告 >700 / 红线 >1000；`scripts/` >600 / >1000；测试 >900 / >1200，且 >80 用例告警；`__init__.py` 薄壳 >200）。口径与理由见 `technical.md` C28。
> **入表规则**：达到警告线即登记在此表（登记线 = 警告线，不另立数字），行数快照随复核刷新；破线豁免当前为 0。

**当前无登记项**——三域均在登记线以下，新增文件触线时按上述口径登记。

## 已解决问题

### 开发期已修复（0.15.1-dev）

| # | 问题 | 修复 |
|---|------|------|
| **rf-855** | 启动向导「幂等」用例与「标记后非首次」用例只差一次重复调用，断言完全相同；交易日历用例留着未使用的 `trading_days` 集合并在末尾 `del`，指数链路用例的 `call_count` 计数从未被读取 | 两条启动向导用例合并为一条（重复标记 + 状态不变）；两处死变量删除 |
| **rf-854** | 一批「弱断言」：名称为映射/阈值/警告/命中语义，实际只断言 `is not None`（行业映射、分位最小样本、汇率/夏普警告、参数校验、cassette 命中、凭据缺失、指数全失败） | 按契约补足：映射锁定具体指数代码、分位恰达阈值断言 100、警告断言文案要点、参数校验断言键名与原因、cassette 断言响应体、凭据断言返回声明字段、指数全失败断言空字典 |
| **rf-853** | 配置原子写崩溃用例在收尾阶段 `try/except OSError: pass`——崩溃未抛出时用例照样通过，临时文件清理断言失去前提 | 改为 `with self.assertRaises(OSError)` 明确崩溃契约，再比对 `.tmp` 文件数 |
| **rf-852** | 文件系统边缘 4 例接受双结果（占用文件接受任意异常、超长路径 `except OSError: pass`、空字节 xlsx 允许列表或异常）——两种结局都算过，等于没有契约 | 按 `reader` 实现钉死：PermissionError/OSError 原样抛出、超长路径（mock 后）返回空列表、尾部空字节 xlsx 正常解析出 1 条持仓 |
| **rf-851** | 安全基线 3 例为**自证式**：缓存用例自造 JSON 再扫自己、日志用例自定义脱敏函数再断言它脱敏、HTML 用例用本地正则断言本地样本——均不触生产代码，恒过 | 改为触生产：缓存条目由 `cache.set` 写出后再扫、LLM 源码静态守卫（日志语句不得含 `api_key`）、HTML 模板产物扫绝对路径；对应文档同步 |
| **rf-850** | 「当前迭代」概述行重算与归档完成标记口径不一致：归档只认 ✅/❌/「已完成」，而重算只排除 ✅/❌——台账里写「已完成，待发布归档」的节会被归档搬走，搬走前却仍算进「在办」项数（概述行与实际在办数对不上） | `recompute_current_iteration` 排除集并入「已完成」，与 `plan_completed_sections` 单源；回归 1 例（「已完成」节与 ✅ 同口径） |
| **rf-849** | `[C]` 面板无效编号提示写死「可输入 1-16 或子项 7.1 / 7.2」：章节与子项是注册表派生量，新增一章后提示立刻过期，把用户引到不存在的编号 | 新增 `invalid_number_hint()` 从 `chapter_numbers()` / `sub_item_numbers()` 现取范围；回归 2 例（范围随注册表、注册表缩短时提示同步缩短） |
| **rf-848** | TUI 动线驱动器的打点可能静默失效：处理器函数内 `from tui_keys import input_choice` 绕过模块属性 patch，用例表面在跑、实际读真实 stdin（rf-842 的根因只在 P2 regression 暴露） | `run_flow` 前置「打点矩阵自证」——逐项校验 `builtins.input` 与各消费方 `input_choice` / `get_key` 都指向 feeder，任一未命中即报错；日志动线改标 `scenario_basic` 让 P0 也覆盖；回归 2 例 |
| **rf-847** | 发布台账失败记录只有 `ok=false`：复盘时无法回答「折在哪一步、哪些用例红、报告在哪」，只能去 `test-reports/archives/` 按 mtime 反查（目录名与结束时间对不上） | 失败命令写 `failure`：失败步 / 退出码 / 报告目录 / 失败用例名 / 输出尾部（首次失败保留第一现场）；回归 2 例 |
| **rf-846** | 发布 bench 的 `--fail-fast` 在多档并行时形同虚设：`unit` 等长尾档与场景档同批启动，场景失败仍要等完整 unit 跑完（实测一次白等约 45s） | 发布子集按「快而决定性 → 长尾」排序（regression → integration → unit → dev-verify）；回归 1 例锁顺序 |
| **rf-845** | prepare 的文档手术会在写入前因 changelog 派生失败中止，但该失败发生在 archive-init 与台账操作之后，排查要回退已动文件 | `check` 增加 changelog 派生预演（`apply_changelog_release` 只算不写），派生失败在动文件前中止并给出修复方向 |
| **rf-844** | publish 台账只记「统计快照同步」一步（1.32s），实际提交/合并/tag/推送均未入账；且 gate 后代码有改动时只说「实跑 verify」，读者不知道改了什么、是否白跑 | 提交/合并/tag/推送分段计时入账；gate 戳增存逐文件代码哈希，publish 指纹不一致时点名 gate 后改动的代码文件并说明 verify 为何重跑；回归 2 例 |
| **rf-843** | Web 配置面板的块标题回退成内部块 id：`renderBoolBlock` 用 `labels[blockKey]` 取标题，而 labels 只登记可编辑键；`sections` / `llm` 等块在面板上直接显示英文 id（中文块标题只有 `features.*` 组与少数写死项）。同批发现 `renderTuningGroup` 签名与块标题取源不一致（引用未定义 `surface`）导致整面板渲染失败 | 块标题改为**服务端随面下发**（`block_titles`，单一来源），前端一律取服务端下发的标题（不回退到 id、不写死中文）；`renderTuningGroup` / `renderAnonGroup` 改为接收 `surface`；契约测试补「每块都有中文标题且标题≠块 id」 |
| **rf-839** | `_evaluate_percent_value` 参数蔓延（单函数 22 个参数：7 基础值 + 10 语境开关 + 5 数据映射），新增一种语境要同步改签名/文档/调用点与全部直接用例，语境判定顺序只体现在函数体里 | 收进冻结 dataclass `PercentContext`（22 字段，字段即语义），函数签名单参 `_evaluate_percent(ctx)`；调用点构造上下文，语境优先级仍在函数体内单源维持；`src/test/unit/llm` 1326 例全绿（行为零变化） |

### 归档档案
- [`archived_review-findings.0.15.x.md`](../archive/v0.15.x/archived_review-findings.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-24）
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x 开发期已修复批次（2026-10-14 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.0 ~ v0.12.13  （2026-10-03 ~ 2026-10-12）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.0 ~ v0.11.11  （2026-09-18 ~ 2026-10-02）
- [`archived_review-findings.0.10.x.md`](../archive/v0.10.x/archived_review-findings.0.10.x.md) — v0.10.1 ~ v0.10.20（2026-08-04 ~ 2026-09-15）
- [`archived_review-findings.0.9.x.md`](../archive/v0.9.x/archived_review-findings.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_review-findings.0.8.x.md`](../archive/v0.8.x/archived_review-findings.0.8.x.md) — 0.8.0 ~ 0.8.10（2026-07-21 ~ 2026-07-30）
- [`archived_review-findings.0.7.x.md`](../archive/v0.7.x/archived_review-findings.0.7.x.md) 
- [`archived_review-findings.0.6.x.md`](../archive/v0.6.x/archived_review-findings.0.6.x.md)
- [`archived_review-findings.0.5.x.md`](../archive/v0.5.x/archived_review-findings.0.5.x.md)
- [`archived_review-findings.0.4.x.md`](../archive/v0.4.x/archived_review-findings.0.4.x.md)
- [`archived_review-findings.0.3.x.md`](../archive/v0.3.x/archived_review-findings.0.3.x.md)
- [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md)
- [`archived_review-findings.0.1.x.md`](../archive/v0.1.x/archived_review-findings.0.1.x.md)
