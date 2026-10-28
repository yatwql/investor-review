# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.16.8-dev
> **编号源**：`rf-next = 938`（新增问题提出后更新为 +1；已用最大 rf-937，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | Web 模式真机验收余 4 类人工项（进度观察、结果区按钮、提交即禁用、拖拽与键位） | 判定标准见 [`web-browser-verification.md`](../archive/v0.15.x/web-browser-verification/web-browser-verification.md)；复跑 `scripts/test-smoke-web.py` 与 `docs/tmp/browser-verify/cdp-check.mjs`；收尾 kill 服务与浏览器、清空 `data/holdings/uploads/` |

### P2 — 中优先：价值明确、成本可控（下批排期）

入选标准：重构收益明确、回归面可圈定。当前无登记项。

### P3 — 持续监控：兼容残留

入选标准：需先确认数据契约再动，当前不影响行为正确性。当前无登记项。

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。下表为**存量监控清单**（不占用 rf 编号，拆分后删除对应行；当前 6 项，全在可选优化区间，无红线违规）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/test/unit/scripts/test_release_tool_gate.py` 1147 行（测试登记线 900 / 红线 1200） | 按域再拆：`refresh` 编排一组、`publish` 一组独立成文件；拆分前先确认不放宽断言 |
| `src/test/conftest.py` 1007 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 装配与 marker 注册 |
| `src/python/llm/generators_orchestrator.py` 845 行（主程序登记线 700） | 生成编排与共享钩子可再分（`generators_*` 同族已多文件，按模块族对齐） |
| `src/python/cli/_handlers.py` 789 行（主程序登记线 700） | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄壳 |
| `src/python/llm/skeleton.py` 745 行（主程序登记线 700） | 骨架模板与占位渲染可分（模板数据 vs 渲染逻辑） |
| `src/static/tmpl/report_template.html` 994 行（**不在行数守护域内**：`check-file-length` 只扫 `.py`） | 再涨即无拦截——要么纳入守护扫面（模板按 1000 红线），要么按页签拆 partial；当前 6 行余量，下一项报告页改动就会触线 |

## 已解决问题

| # | 问题 | 修复 |
|---|------|------|
| **rf-927** | 持仓变动复盘误报新增/清仓：演示快照污染真实快照目录，逐对差分把整批标的当真实调仓 | 事件抽取加基线切换守卫（相邻期代码 Jaccard < 0.5 跳过并标注）+ 截图护栏补 `data/history` + 隔离并删除 7 个污染快照；回归 6 例 |
| **rf-928** | 行业资金流向每份报告重复撞超时：失败负缓存只在进程内存，而每份报告是新进程 | 负缓存落盘（30 分钟、跨进程）+ 失败回退最近成功载荷（≤3 天，标 `stale`）；回归 4 例 |
| **rf-929** | 场内基金（LOF/ETF）行情被源侧简称误杀后无兜底：`_name_matches` 汉字集合重叠 0.7 阈值拒掉「白酒基金LOF」vs「招商中证白酒」，且场内基金不在降级名单 → 该持仓永久缺价 | 名称判据加「连续 2 汉字公共段」一档 + 股票链路失败后场内基金也降级净值链路；回归 3 例（含反例：不同标的仍拒） |
| **rf-930** | 演示/基准运行与真实运行共享 `logs/app.log` 与 `data/cache`：演示告警混进真实日志分析、缓存互串 | 新增 `INVEST_LOG_PATH` / `INVEST_RUN_CONTEXT` / `INVEST_CACHE_DIR` 三通道，截图工具自动注入；回归 9 例 |
| **rf-931** | 演示工作区凭据块与 provider 引用漂移：`llm_key.json` 只有旧格式 `default`，providers 引用 `deepseek-main`/`opencode-go` → 每次演示 run 刷 2 行告警 | `build()` 同源写入凭据块与 providers（同名 `demo-main`）；回归 2 例 |
| **rf-932** | 残留输出目录锁被当作持续占用：只判存在不判持有者，4 天前残留锁让每次启动刷一条告警 | 锁加陈旧判据（pid 存活 / 文件年龄 12h）并支持接管；回归 5 例 |
| **rf-933** | LLM 缓存冷启动未命中被归因为 `ttl_expired`：无上轮快照时误判「内容没变只是到点」，据此放宽 TTL 省钱是错的 | 归因补 `cache_miss` 三态（冷启动）；回归 1 例 |
| **rf-934** | `llm_settings.json` 读取失败吞掉异常原因，面板只报「读取失败按默认展示」 | 日志带异常类型/消息与路径；回归 1 例 |
| **rf-935** | 输出目录锁的 pid 探活在 Windows 上会杀进程（`os.kill(pid, 0)` 在 Windows 走 `TerminateProcess`，探测即杀） | 改 `OpenProcess` 查询句柄，无法判定退化为文件年龄判据；回归 4 例 |
| **rf-936** | 行业资金流向「陈旧回退」未标新鲜度：源不可达回退上次成功载荷后，报告与 LLM 提示词把它当今日数据 | `mark_data_used` 新增 `freshness` 通道（进事件 `detail`、不进降级计数）+ 质量块新增「陈旧回退」行 + 取数侧如实标注与告警；回归 7 例 |
| **rf-937** | 兼容层技术债：为旧形态保留的迁移/回退/再导出分支（llm_key 扁平文档自动改写、`market_hour_aware` 退役告警、穿透 `funds` 回退、TUI 再导出壳） | 全量移除并存纪律入 developer-guide「兼容层纪律」；`llm_key.json` 旧形态改为拒绝加载 + 改写指引（不迁移、不写 `.bak`）；测试同步重写/收窄（净 +5 例） |

### 归档档案
- [`archived_review-findings.0.16.x.md`](../archive/v0.16.x/archived_review-findings.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-10-27）
- [`archived_review-findings.0.15.x.md`](../archive/v0.15.x/archived_review-findings.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x（2026-10-14 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.0 ~ v0.12.13（2026-10-03 ~ 2026-10-12）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.0 ~ v0.11.11（2026-09-18 ~ 2026-10-02）
- [`archived_review-findings.0.10.x.md`](../archive/v0.10.x/archived_review-findings.0.10.x.md) — v0.10.1 ~ v0.10.20（2026-08-04 ~ 2026-09-15）
- [`archived_review-findings.0.9.x.md`](../archive/v0.9.x/archived_review-findings.0.9.x.md) — v0.9.0 ~ v0.9.12（2026-07-30 ~ 2026-08-03）
- [`archived_review-findings.0.8.x.md`](../archive/v0.8.x/archived_review-findings.0.8.x.md) — v0.8.0 ~ v0.8.10（2026-07-21 ~ 2026-07-30）
- [`archived_review-findings.0.7.x.md`](../archive/v0.7.x/archived_review-findings.0.7.x.md) — v0.7.x
- [`archived_review-findings.0.6.x.md`](../archive/v0.6.x/archived_review-findings.0.6.x.md) — v0.6.x
- [`archived_review-findings.0.5.x.md`](../archive/v0.5.x/archived_review-findings.0.5.x.md) — v0.5.x
- [`archived_review-findings.0.4.x.md`](../archive/v0.4.x/archived_review-findings.0.4.x.md) — v0.4.x
- [`archived_review-findings.0.3.x.md`](../archive/v0.3.x/archived_review-findings.0.3.x.md) — v0.3.x
- [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md) — v0.2.x
- [`archived_review-findings.0.1.x.md`](../archive/v0.1.x/archived_review-findings.0.1.x.md) — 早期版本
