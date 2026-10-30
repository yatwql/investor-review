# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.13]**（2026-10-30）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.16.14-dev] - 开发中（未发布）

### 修复

- **状态条中止键与文档对齐**（rf-988）：`LiveStatusBar` 缺省 `cancel_hint` 仍是已撤回的「q 中止」，报告器直接把它拼进状态条——TTY 上实显「… · q 中止」而该键无人监听。新增 `live_status.CANCEL_HINT` 作单一来源（`Ctrl+C 中断`），`status_bar_text` 与 `LiveStatusBar` 两处缺省同取；docstring 参数名（`cancel_hint` → `hint`）对齐。回归 3 例
- **配置面板会话测试间复位**（rf-989）：`handlers_config._session` 是模块级单例且 `_apply_edit` 非空时必然记撤销，conftest 补齐 `_auto_reset_config_session` autouse（进/出两侧均关闭）。回归 2 例
- **截图 `xlsx` 行数缺省单源**（rf-990）：入口 `--rows` 缺省改取 `xlsx_frame.DEFAULT_MAX_ROWS`，列上限收敛为 `_MAX_COLUMNS` 常量。回归 1 例
- **TUI 配置缓存测试间复位**（rf-991）：`tui_menu._config_cache` 是模块级字典，页头/菜单渲染读 `get_config_cache()`——补齐 `reset_config_cache()` 与 conftest 的 `_auto_reset_config_cache` autouse（进/出两侧复位）。回归 3 例；同文件菜单项取值改走带断言的 `_menu_item()`（`index_by_key` 返回 None 时直接失败，不再静默取错项）
- **已解决台账归档断层补齐**（rf-982）：v0.16.5 起的 9 个发布周期里 53 条 `rf` 条目写在 `## 已解决问题` 直属层（未写 `### 开发期已修复（X-dev）` 节头），归档按「本版无该节 = 无待迁档」整批静默漏搬，归档文件停在 v0.16.4。已按 git 首次包含 tag 反查归属版本，补入 v0.16.7 / v0.16.8 / v0.16.9 / v0.16.11 / v0.16.13 五个批次；`apply_rf_archive` 改为节缺失时按本版归位直属层表，`rf_archive_status` 新增 `unfiled` 态，`gate` 与 `check-doc-drift` 分区纪律（E 条）对「版本节之外的台账行」直接报错。回归 4 例
- **归档批次标题按发布版号标注**（rf-983）：批次节由 `## 开发期已修复（0.16.11-dev）` 改为 `## 已修复（0.16.11）`，说明行同指 `changelog.md 0.16.11 段`——归档只记录已发布版本，写 `-dev` 会把已打 tag 的批次读成开发中状态。v0.13.x~v0.16.x 既有归档 26 个批次节按同规则迁移；`has_archive_section` 与回归断言同步
- **计划台账完成项漏档守卫 + 历史补录**（rf-982 同批）：`check-doc-drift` 分区纪律新增 F 条——现行 changelog 提到的 `plan-N` 必须在 plan.md 在办条目或计划归档里有条目（完成项被直接删除而不迁档时，任务会从台账与归档两面消失）；并补录 v0.15.2 / v0.15.8 / v0.16.5 / v0.16.6 已实现但未入档的 8 个计划项（plan-208/209/225/226/228/230/231/232，每节注明「补录」与来源 changelog 段）
- **历史台账引用残迹回填**（rf-984）：归档 changelog 段提到的 62 个 `rf` 编号（rf-37~50、rf-480~508、rf-516、rf-565、rf-711、rf-790、rf-822/823/829、rf-863~866、rf-901~911、rf-943）原先只在 changelog 留痕、台账与归档都无对应条目；按 changelog 段落回填到 v0.8.10 / v0.11.10 / v0.11.11 / v0.12.2 / v0.14.1 / v0.14.5 / v0.14.6 / v0.15.2 / v0.16.2 / v0.16.8 十个批次节，每节标注「补录（2026-10-30）」并说明问题描述未单独留存（修复列即当日变更摘要）
- **台账段序统一为升序**（rf-985）：review-findings / changelog / plan 的版本段与计划条目自带完成版本，在同一文件内一律升序（旧→新），现行文件与归档文件同口径；归一现存归档（changelog 9 份、review-findings 4 份、plan 7 份），`check-doc-drift` 新增第 23 项 `check_ledger_order` 守卫（现行 + 归档全扫）
- **[C] 面板章节名与报告章节名对齐**（rf-986）：`enable_news` 显示名由「市场新闻」改为报告章名「财经热点关联分析」，同一章的 LLM 增强行标「（LLM 增强）」；config 模板注释、CLI 示例与手册（配置参考/配置手册/FAQ/报告说明/TUI 菜单）同步
- **[C] 面板窄屏状态可见 + 章名缩短**（rf-987）：长章名不再把「开启/关闭」挤出屏幕——名称按剩余宽度截断，状态与 `*` 保留；同一报告章的 LLM 增强行显示名缩短为「财经热点关联分析（LLM）」

### 变更

- **`[C]` 面板拆分与排版参数收纳**（rf-992）：`run_report_chapters_panel` 247 行单函数拆为 `_ChaptersPanel`（会话态 + 九个具名方法），入口只留两行编排；`_format_row` 的 13 个关键字参数收为「排版预算 + 行内容」两个参数（`_RowLayout` / `_ChapterRow`）。输出逐字节不变（113 例渲染/写盘/闸门/帮助用例全过）。
- README 配图全量重出（v0.16.14-dev）：TUI / CLI / Web 三区（生成・持仓录入・配置）/ HTML 报告三图按当前界面重拍，新增 **Excel 报告图**（`src/static/excel-report.png`）——`make-screenshots.py` 新增 `xlsx` 子命令，读演示报告的真实工作簿按单元格显示值（百分比 / 千分位 / HYPERLINK 取文本）/ 合并区 / 列宽重排成带列标与页签条的表格图；README 补「Excel 报告」小节并修正 Web 持仓录入与配置面板的标题归属（原先配置标题压在了持仓图上方）。全部图来自虚构演示持仓，真实 `data/` 零接触。
- 章节更名：「财经新闻热点与持仓关联分析」→「财经热点关联分析」（Excel 页签名 / HTML 章标题 / TUI `[C]` 章节名 / Web 章节名 / CLI 输出 / LLM 模块显示名 / 配置文件生成器注释与报告模板注释同步；显示名单源 `core/data_registry` + `core/report_section_registry`，一次改动五渠道同变）。
- TUI 面板行序调整（`[S]` / `[C]` 共用）：配置项由「名称 键名 [状态]」改为「名称 [状态]* 键名」——状态紧贴名称，长列表（30+ 行）靠红/绿状态扫读，不再被内部键名推到视野远端；子项闸门提示由「（启用本章节后可切换）」缩短为「（父章未开）」。契约同步 `DESIGN-TUI.md` 行型表，回归 4 例（宽/窄档列序 + `[C]` 行序 + 漂移星标位置）。

## 归档

- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.13（2026-10-25 ~ 2026-10-30）
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
- 新增回归 8 例：基金经理超时跳过回退 / 非超时仍回退 / 总预算 ≤10s（3 例），历史重叠数值一致不刷新 / 数值变化触发刷新 / 舍入容差不误报 / 无重叠不触发 / 整窗重叠只拉一次（5 例）
