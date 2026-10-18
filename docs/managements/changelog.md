# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.13.5]**（2026-10-17）——已发布版本段随发布移入 [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.13.6-dev] - 开发中（未发布）

### Added

- HTML 报告右上角浮动「打印 / 导出 PDF」按钮（plan-127）：`window.print()` 唤起浏览器打印/另存 PDF，44×44 触控目标、`--primary` 语义色、打印稿自隐藏（独立 `@media print` 规则）；补模板结构/可访问性/触控尺寸/打印隐藏回归用例，`reports-instruction.md` 同步入口说明
- Web 内置定时生成（plan-130）：配置页签新增「定时生成」调度面板（执行日/时刻/报告类型/启用开关），保存写入 `config.json` 的 `scheduler` 块；服务端 daemon 调度线程到点自动读正式持仓生成（正式-用存量），与手动生成同队列串行互斥、宽限 30 分钟内顺延、超时登记错过，触发账本落 `data/state/scheduler_fired.json` 防重启重复；缺省关闭零行为变化，面板改配置 30s 内生效无需重启（`GET/POST /api/scheduler`，校验 400 + 同源守卫 403）；补解析/触发窗/账本/API/面板接线回归用例，配置默认值模板与 `how-to-config.md`/`how-to-use-web-mode.md` 同步
- perf-view 费用趋势（plan-129）：`--by day|week|hour` 时段聚合表新增「费用合计/费用环比」列（耗时与 `llm.total_cost` 同表交叉，零数据新增，无费用样本自动省列，末档附环比提示行）；`--json` 汇总新增 `llm_cost` 费用块（runs/合计/均值/中位/单次最高）与 `--by` 时的 `by_period` 时段费用序列；补 9 个回归用例（费用列/环比/省列/机读字段/整链渲染）

### Fixed

- LLM 计费口径统一修复（rf-701/702/703）：`_normalize_usage_tokens` claude 分支把 `input_tokens` 归一为总输入（补 `cache_read_input_tokens`，兼容端点命中大于未命中不再产生负费用），openai 分支补读 DeepSeek 原生端点顶层 `prompt_cache_hit_tokens`（优先于 `prompt_tokens_details.cached_tokens`）；`estimate_cost` 的 `cache_miss` 下限 0 防御；报告页脚/批处理汇总/新闻相关性费用估值统一走归一层，会话累计费用与单次估算同参等值；补 5 个回归用例
- LLM 模型定价表按官方定价页核实修正（rf-700）：Claude Opus 4.x 15/75→5/25、Haiku 4.5 0.25/1.25→1/5、Fable 5 3/15→10/50、Gemini 3.5 Flash 0.15/0.6→1.5/9、Gemini 2.5 Flash 0.15/0.6→0.30/2.50、2.5 Pro 输出 5→10、GPT-4o/mini 缓存命中补 50% 折扣；同步 `llm-technical.md` 附录 B 与 `how-to-config-llm.md` 定价表。DeepSeek 峰谷价与 Kimi 价经核实无偏差，不影响现有费用估算
- 过期缓存生成路径自动清理（rf-704）：`cache.auto_cleanup_expired()` 尽力而为包装（任何异常吞掉返回 0），`generate_report` 入口调用（CLI/TUI/Web 三渠道共用入口），无人值守 CLI 定时任务不再只增不减地堆积过期缓存文件；补委托与吞异常回归用例
- Web 进度轮询任务丢失终态处理（rf-705）：`pollOnce` 识别 404/`NOT_FOUND` → 停止轮询 + `restoreGenerateBtn()` 单源复位 + 结果区渲染失败态（提示任务已失效请刷新），不再被当瞬时错误无限重试；补 main.js 源结构回归用例
- Web 进度事件通道完整性（rf-706）：`pollOnce` 增在途互斥（pollBusy，成功/异常/同步抛三路复位）+ 按 `seq > lastSeq` 过滤重复回放；服务端 events 载荷补 `first_seq`（`RunState.oldest_seq`），前端缺口时渲染「中间已省略 N 条」占位行不再静默跳号；补 RunState 边界/载荷字段/main.js 源结构回归用例
- Web 生成进度断点续传（rf-707）：活动 run 写 sessionStorage（提交成功/流程重置/轮询完成/任务失效四点闭环清理），页面加载 `resumeActiveRun()` 重建进度视图从 `after=0` 续轮询；run 已随服务重启消失时走任务不存在终态收口不空转；补 main.js 源结构回归用例

（本次发布内容见下方归档索引）

## 归档

- [`archived_changelog.0.13.x.md`](../archive/v0.13.x/archived_changelog.0.13.x.md) — v0.13.0 ~ v0.13.5（2026-10-13 ~ 2026-10-17）
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
