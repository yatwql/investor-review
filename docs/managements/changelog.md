# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.10]**（2026-10-20）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.11-dev] - 开发中（未发布）

### Added

- 发布链耗时埋点：新增 `scripts/_release/_timing.py`（分步计时 + JSON 记录），`release.py` 每命令尾行打印耗时摘要并追加 `logs/release.jsonl`（`command` / `ok` / `elapsed_s` / `version` / `steps[]`）——gate 的回归/十守护/设计护栏、refresh 的 bench/collect/sync、publish 的 P1 verify、evolution 的快照与统计同步均记为分步；`logs/` 为 git 忽略域，写入失败只打 `[!]` 且不改退出码（自审 rf-771）
- `release.py refresh` 新增 `--full-bench`：bench 默认只测发布口径四档 `unit` / `dev-verify` / `regression` / `integration`（未测模式按 `--update-docs` 既有口径保留上次实测，不写脏），全量十四档降为显式入口（自审 rf-772）

- `check-doc-drift` 新增第二十项检查「迁档占位↔归档节」：review-findings 每个「已随 vX.Y.Z 发布迁入」占位，对应 `archived_review-findings.{X.Y}.x.md` 必须存在含该版本号的二级标题归档节——占位已写、归档正文缺失（发布归档迁移只删不写）即当场报出；doc-drift 项目清单五处文档同步（自审 rf-756）
- `check-doc-drift` 新增第二十一项「树描述计数禁令」：folders.md 目录树描述禁写「阿拉伯数字+量词」的易漂移计数（开关项数/菜单项数/文件数类，与「测试真值单一来源」同源纪律）；docs/archive 记录域豁免、中文数词设计常量不入检；现存 6 处 src 域违规改定性措辞（自审 rf-757）
- `check-code-traces` 新增「日志统一」AST 级守卫（`_traces_code/logging_discipline.py`）：生产层 `print()` 白名单制——豁免域为 `tui/`、`cli/` 整目录（终端交互即其输出本体）与进度反馈 / 一次性终端检查报告 / 首启向导六个模块，白名单外调用即报 LOG 并返回退出码 2；developer-guide 退出码表与三家 AST 守卫说明同步，technical.md 日志统一约束登记机检载体；用例覆盖检出（函数体内嵌套/多行/报告层）、豁免（目录/文件）、不误伤（`sys.stdout.write`/`obj.print()`/字符串字面量/测试层/非 py）、语法错误容错与白名单完整性（条目存在 + 现存 print 全部落在豁免域）

### Changed

- `check-doc-drift` 分区纪律检查新增第 D 条「节归属」：「开发期已修复」节只允许出现在已解决区、P 档标题只允许出现在待处理区——原第 A 条按 rf 标识比对，标题（节）错位时完全静默（rf-765 即由此产生）（自审 rf-765）

- `release.py gate` 新增演进对照新鲜度断言（P2 前置）：「当前开发版」列头「本次重跑时的工作区」日期须为当日——evolution 为发布链人工步骤，跳过即以过期快照发布的缺口由此闭合（表头与数据行同命令原子刷新，日期一致即数据行同步）；发布编排描述三处文档同步（自审 rf-758）
- `check-doc-traces` 围栏内 folders.md 目录树行照检（围栏代码块跳过仅针对非树行内容——目录树整块位于围栏内，原跳过逻辑使「树行照检」规则从未生效）；树行按路径分域（docs/archive/ 子树=归档记录域仅复盘叙事检出、docs/plan/ 子树=任务记录域照检章节+约束代号）；树行专属无后缀来源叙述补强（「从 framework 拆出」类带后缀模式覆盖不到）；folders.md 现存 14 处违规描述改语义化；developer-guide 树行纪律描述同步（自审 rf-760）
- 交易所代码前缀改为 `code_utils` 单点定义：新增 `EXCHANGE_PREFIXES` 常量与公开 `strip_exchange_prefix()`（只剥前缀、不校验码位，供 5/6 位形态自判等场景复用），`_strip_prefix` / `to_fmp_symbol` / `holding_status.classify_code_format` 三处自建前缀表或元组字面量收编复用；`to_fmp_symbol` 带前缀输入的透传分支此前因大小写不匹配而不可达，随常量复用一并修正；反向机检由单测钉住「前缀元组唯一定义点」（自审 rf-763）
- folders.md 归档子树版本目录块重排为版本升序（0.9.x 后原接 0.13→0.12→0.11→0.10 倒序——归档落盘三次均插入同一锚点且 `check_dir_tree` 仅集合双向比对、顺序零机检）；`check-doc-drift` 目录树检查新增「版本目录块升序」断言（自审 rf-761）
- developer-guide「check-doc-drift」项清单补齐至 21 项（16 项陈旧：17~21 五项缺列）并改与脚本 docstring 同源措辞；technical.md 约束外参照句「十项逐条对账」改「逐项对账」（自审 rf-762）
- 架构设计约束（代码类型判定/缓存/原子写入/HTTP 工厂/日志统一/开关注册表等全部编号约束）与设计契约（DESIGN.md / DESIGN-TUI.md）全量审计：机械扫描 + 逐约束对照适用范围裁决——无直连 `requests`（统一 httpx 工厂）、报告层无 `call_llm` 直调、开关单源派生、DESIGN.md 护栏 E 级通过且 W 基线（字号 8/间距 172/W1 白名单 15）与契约声明一致、DESIGN-TUI 无 hex 字面量与 GitHub 系色残留；登记 rf-763（holding_status 自建 sh/sz/bj 前缀元组，判定中心化约束违反）/ rf-764（whatif_writer HTML 直写未复用原子写原语）与日志统一约束无机检守护（该缺口已由同期新增的日志统一支路闭合）（自审 rf-763/rf-764）

### Fixed

- review-findings 分区顺序恢复：三个「开发期已修复」节（0.13.11 / 0.13.10 / 0.13.9）原夹在待处理区 P2 与 P3 之间、0.13.8 占位落在归档索引之后——重排为 待处理（P1→P2→P3）→ 已解决（开发期已修复 0.13.11→0.13.8，再归档档案）；同时去掉 P3 表头与首行间的空行（该表原在渲染上断裂为「空表头 + 裸行」）（自审 rf-765）
- P3 文件膨胀登记表与 `check-file-length.py -v` 真值对齐：登记口径改为逼近红线档（主程序 ≥700 / 脚本 ≥600 / 测试 ≥1000，余量 ≤30%），警告级全集明确指向 `-v` 不逐项登记；表改为逐文件、按距红线余量升序，行数按 `-v` 快照刷新，并补登主程序八文件（rf-773）/ 脚本四文件（rf-774）/ 测试十三文件（rf-775）；原表 10 行中 5 个行数陈旧且声称的「全登记」实际只覆盖 10/58（自审 rf-766）
- `plan-169`（日志统一约束机检守护）补归档：已完成并从 plan.md 移除但 `archived_plan.0.13.x.md` 无该条，编号已消耗却无从追溯（自审 rf-767）
- plan-92 现状句「17 页签」改为 19（与报告章节注册表及 README 对齐）（自审 rf-768）
- testplan §6.4「补充自动化门禁」列表编号重复（`15.` 出现两次，16~18 连带错位）重排为 15~19 连续编号（自审 rf-769）
- llm-technical.md 目录层级修正：附录 A/B/C 原错缩进挂在「13. 集成点」下且缺「附录」父项，改为与章同名同级的「附录」父项 + 回退一级缩进（自审 rf-770）
- 调仓模拟报告 HTML 双产物（最新版 + 归档版）改经 `_write_html_atomic` 原子落盘（tmp + `os.replace` + 中断收口登记），与主报告口径对齐——原直写 `open("w")` 在进程中断时留下半写截断的 HTML；补中断场景与原子原语调用面回归用例（自审 rf-764）

- TestGate 门禁编排用例与演进新鲜度断言隔离：新鲜度直读真实 folders.md + 墙钟，编排用例在不同时区/日期的 CI 上随机红（本地已过零点、CI 仍是前一日 → 先行拦截返回 2，回归/守护一个不跑）；新增 autouse 夹具将新鲜度视为通过（编排用例只验序列），并新增新鲜度失败即中止且不触发子进程的专项用例（自审 rf-759）

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.10（2026-10-13 ~ 2026-10-20）
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
