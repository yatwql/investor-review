# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.16.15-dev
> **编号源**：`rf-next = 999`（新增问题提出后更新为 +1；已用最大 rf-998，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | Web 模式真机验收余 4 类人工项（进度观察、结果区按钮、提交即禁用、拖拽与键位） | 判定标准见 [`web-browser-verification.md`](../archive/v0.15.x/web-browser-verification/web-browser-verification.md)；复跑 `scripts/test-smoke-web.py` 与 `docs/tmp/browser-verify/cdp-check.mjs`；收尾 kill 服务与浏览器、清空 `data/holdings/uploads/` |

### P2 — 中优先：价值明确、成本可控（下批排期）

入选标准：重构收益明确、回归面可圈定。

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P3 — 持续监控：兼容残留

入选标准：需先确认数据契约再动，当前不影响行为正确性。

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。下表为**存量监控清单**（不占用 rf 编号，拆分后删除对应行；当前 7 项，全在可选优化区间，无红线违规）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/test/unit/scripts/test_release_tool_gate.py` 1147 行（测试登记线 900 / 红线 1200） | 按域再拆：`refresh` 编排一组、`publish` 一组独立成文件；拆分前先确认不放宽断言 |
| `src/test/conftest.py` 1007 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 装配与 marker 注册 |
| `src/python/llm/generators_orchestrator.py` 869 行（主程序登记线 700） | 生成编排与共享钩子可再分（`generators_*` 同族已多文件，按模块族对齐）；预检键/指纹段可下沉 `generators_orchestrator_cache.py` |
| `src/python/cli/_handlers.py` 789 行（主程序登记线 700） | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄壳 |
| `src/python/llm/skeleton.py` 815 行（主程序登记线 700） | 骨架模板、占位渲染、缓存归因与回写已四簇并存：模板数据/渲染逻辑可下沉子模块（`llm/skeleton_*`） |
| `src/python/tui/handlers_holdings.py` 782 行（红线 1000） | 面板 + 账户/标的选择 + 录入采集 + 价格/净值 + 校验 + 保存写盘六类职责同居一文件：仍在红线内且流程高度耦合（共用 `_Session`），拆分收益暂低于回归面；再涨 ~150 行则按「面板流程 / 输入采集」两段拆，并把 `_market_data` 的会话内记忆一并做进去 |
| `src/python/fetcher/financial_report.py` 702 行（主程序登记线 700） | 索引/章节清单/正文三阶取数与负缓存同文件，刚过线：负缓存样板已收口到 `cache/_negative.py`，再涨则按「索引 / 正文 / 全文定位」三阶下沉 |
| `src/static/tmpl/report_template.html` 994 行（**不在行数守护域内**：`check-file-length` 只扫 `.py`） | 再涨即无拦截——要么纳入守护扫面（模板按 1000 红线），要么按页签拆 partial；当前 6 行余量，下一项报告页改动就会触线 |

## 已解决问题

### 开发期已修复（0.16.15-dev）

| # | 问题 | 修复 |
|---|------|------|
| **rf-995** | 设计护栏 W4 档外字号 8 处（均为 `font-size: 0.95rem`，即 15.2px）：字阶为 11/12/13/14/16/17/18/20/22px，0.95rem 折算后不在任何档上——同一种「次要正文」写法在 8 处各自重复，字号漂移不可控 | 统一贴到最近档 16px（`1rem`）：8 处同改，行高与间距不变；此后新增字号只取 `var(--fs-*)` token 或字阶值，护栏 W4 归零 |
| **rf-996** | 设计护栏 W5 档外间距 172 处（分布：6px×50、10×28、3×18、14×15、18×13、2×12、20×12、1×11，其余零星）：DESIGN.md 间距阶为 0/4/8/12/16/24/32 且明文「禁 14/18/20 等阶外值新增」，而实现层长期停在中间档位——契约与实现两张皮，护栏只能永久挂着观察项 | 全部吸附到间距阶（取最近档，等距取小值）；三处语义特例单独改写：侧栏让位 `margin-left: 220px` 与侧栏 `width: 220px` 的重复魔术数收敛为 `--toc-width` token；`.sr-only` 的 `margin: -1px` 改 `0`（裁剪 hack 不依赖该值）；汇总片内联 `margin: -2px 0 6px` 改 `0 0 8px`；吸附后 W5 归零，并用前后截屏核验不塌版面 |
| **rf-997** | 写盘相位耗时异常且连续抬升（观察项）：2026-10-30T23:04 那次运行 HTML 生成 18.1s、Excel 生成 10.6s（72h 同口径 med 分别 0.2s / 0.3s），两相位同时恶化；产物体积正常（905K HTML / 135K xlsx，与历史 894~928K 一致）、图表装配 0.0s，故排除数据量与渲染，指向 I/O 侧。趋势 0.2→2.7→3.1→18.1（近 4 次），磁盘余量 259G（占 87%）、reports 仅 172M，非空间不足 | 先原样复跑确认是否复现；复现则采宿主 I/O（顺序写/4K fsync 延迟、`/proc/diskstats` util·await）；不复现则归为瞬时宿主负载，连续两次不复现即关闭。**观察记录**：23:35 同环境复跑 HTML 0.03s / Excel 0.24s（同时段数据准备 12.1s、总 36.1s），第一次不复现，待第二次；**关闭**（2026-10-31 00:52）：第二次同环境复跑 HTML 0.03s / Excel 0.23s（两次连续不复现，写盘相位回中位），判定为瞬时宿主负载，非代码缺陷 |
| **rf-998** | 命中内容缓存的模块仍显示费用、「本次是否缓存」判定失真（两者都来自会话累计值未做本次裁剪）：`_usage_delta` 对顶层 `costs` 按币种做差，但逐模块 `costs` 是整字典照搬，`cached` 标记也直接沿用——同一会话内第二份报告整块命中缓存（token/调用数零增量）时，明细表仍带出上一份的模块费用（实测 expert_review 显示 CNY 0.061，而本次真实花费仅 CNY 0.0119），而真跑过的模块因标记粘着继续显示「使用缓存」（实测 00:52 有 5 个 `fingerprint_changed` 重算模块被标 cached=True）。汇总表与报告用量页签同源，故总表一起虚高 | ① `_usage_delta` 对逐模块 `costs` 按币种做差、`cached` 改为「累计标记为真 且 本次 token 无增量」；② `record_per_module` 在真调用（有 token/费用）时把命中标记翻回 False，累计视图与本次口径一致；回归 1 例（命中模块费用清空 + 真跑模块翻成非缓存） |
| **rf-980** | 版切首跑异常长尾（观察项）：v0.16.13-dev 首次生成时「明细装配与建议」10.5s，其余 4 次运行均为 0.45s 量级（同快照其余阶段无异常） | 不构成代码缺陷、暂无复现，保留观察：后续两次版切首跑若再出现则查该阶段内部耗时，连续两次不复现即关闭；**关闭**（2026-10-31）：后续两次版切首跑「明细装配与建议」分别 0.544s（0.16.14-dev，后续 med 0.557s）与 0.948s（0.16.15-dev，后续 med 0.48/max 0.52s），连续两次不复现。另据 92 个样本，该阶段长尾散见于 0.15.5-dev 65.5s、0.15.6-dev 15.3s、0.16.4-dev 4.7s、0.16.9-dev 3.6s，与版切无关、属该阶段偶发，非版本切换引入 |


### 归档档案
- [`archived_review-findings.0.16.x.md`](../archive/v0.16.x/archived_review-findings.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-10-30）
- [`archived_review-findings.0.15.x.md`](../archive/v0.15.x/archived_review-findings.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x（2026-10-14 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.x（2026-10-03 ~ 2026-10-12）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.x（2026-09-18 ~ 2026-10-02）
- [`archived_review-findings.0.10.x.md`](../archive/v0.10.x/archived_review-findings.0.10.x.md) — v0.10.x（2026-08-04 ~ 2026-09-15）
- [`archived_review-findings.0.9.x.md`](../archive/v0.9.x/archived_review-findings.0.9.x.md) — v0.9.x（2026-07-30 ~ 2026-08-03）
- [`archived_review-findings.0.8.x.md`](../archive/v0.8.x/archived_review-findings.0.8.x.md) — v0.8.x（2026-07-21 ~ 2026-07-30）
- [`archived_review-findings.0.7.x.md`](../archive/v0.7.x/archived_review-findings.0.7.x.md) — v0.7.x
- [`archived_review-findings.0.6.x.md`](../archive/v0.6.x/archived_review-findings.0.6.x.md) — v0.6.x
- [`archived_review-findings.0.5.x.md`](../archive/v0.5.x/archived_review-findings.0.5.x.md) — v0.5.x
- [`archived_review-findings.0.4.x.md`](../archive/v0.4.x/archived_review-findings.0.4.x.md) — v0.4.x
- [`archived_review-findings.0.3.x.md`](../archive/v0.3.x/archived_review-findings.0.3.x.md) — v0.3.x
- [`archived_review-findings.0.2.x.md`](../archive/v0.2.x/archived_review-findings.0.2.x.md) — v0.2.x
- [`archived_review-findings.0.1.x.md`](../archive/v0.1.x/archived_review-findings.0.1.x.md) — 早期版本
