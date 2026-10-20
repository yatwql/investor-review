# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.13.9-dev
> **编号源**：`rf-next = 748`（新增问题取此编号，完成后更新为 +1；已用最大 rf-733，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）

---

## 当前待处理问题


### P1 — 高优先：不做的风险高（尽快执行）

> 入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-257** | plan-8 **Web 模式浏览器真机人工验收余 4 类人工项**：真实 basic/full 进度观察（3.1c/3.2/3.3/3.4）、结果区按钮 4.5、提交即禁用 5.3、2.5/2.6 真实拖拽与 Tab/Enter 抽验；其余断言已自动化复跑通过 | 验证方法与判定标准见 [`docs/plan/web-browser-verification.md`](../plan/web-browser-verification.md)（§1.1 启动/收尾命令 + §5 复验清单）；复跑：`.venv/bin/python scripts/smoke-web.py` + `node docs/tmp/rf257/cdp-check.mjs`，收尾必做 kill 服务/浏览器 + 清空 `data/holdings/uploads/`；全部完成后本表移至已解决 |

### P2 — 中优先：价值明确、成本可控（下批排期）

> 入选标准：修复路径清晰、成本可控；rf-114 前置（rf-113 人工验证）已满足。

| # | 问题 | 修复方向 |
|---|------|----------|

### 开发期已修复（0.13.9-dev）

| # | 问题摘要 |
|---|----------|
| rf-740 | `market_hours.is_market_open()` 进程内分钟级 memo +「市场时段」DEBUG 仅状态变化输出（消除 7 天 12 万行重复 DEBUG） |
| rf-741 | 解析/数据形状类异常（TypeError/KeyError/AttributeError/IndexError）不再按传输级失败退避重试，fail-fast 转下一源 |
| rf-742 | `chain_incremental` 历史修正全量刷新连续触发冷却（源结构性回看时跳过多拉全量，无重叠合并成功重置计数） |
| rf-743 | perf 基准禁网桩在连接级/链路级重试判据中按确定性失败 fail-fast，不再逐次白等退避 |
| rf-745 | requirements.md R-OUT-12 行内两份「覆盖章节」清单不一致（前份缺持仓变动复盘/调仓纪律回放/行动建议三个章节，历史编辑残留）——已删除残留份，保留与实现折叠章节全集一致的清单 |
| rf-746 | requirements.md R-LLM-01「仅在菜单 L 中触发」过时（与 §3.4 Web 同管线、CLI full 同管线不一致）——已改为三渠道完整报告口径 |
| rf-747 | requirements.md R-CON-07 通用降级原则未声明 R-CCH-08 联网必需模块（新闻/资金流向）例外边界——已补例外引用消除歧义 |
| **rf-740** | `core/market_hours.py` `is_market_open()` 无进程内结果缓存：高频调用路径（`cache/_ttl.py` get_ttl、provider 策略选择、价格获取）每次都完整走 config→API→fallback 三层判断并输出 DEBUG 日志；TUI 常驻轮询下 7 天窗口（2026-10-13~20）产生 121,857 行「市场时段」DEBUG（占 app.log 总量 60%、DEBUG 量 68%），日志体积与重复计算双重浪费（来源：2026-10-20 日志+性能追审分析） | 结果按分钟粒度进程内 memo（分钟内开闭市状态不变）；「市场时段」DEBUG 仅状态变化时输出，消除高频重复行 |
| **rf-741** | akshare provider 解析类异常（`'NoneType' object is not subscriptable`）被统一归类为「传输级失败」并同源重试（0.7s 退避后注定重复失败）——7 天窗口 18 次；解析错误是确定性失败，重试浪费请求且把数据缺陷伪装成网络抖动，干扰降级归因（来源：2026-10-20 日志分析） | TypeError/KeyError 等解析异常按业务失败 fail-fast 转下一源（不入传输级重试）；akshare 调用处对 None/缺字段响应加防御，给出明确「源数据缺失」错误 |
| **rf-742** | `fetcher/chain_incremental.py` 历史修正检测对 561910 连续触发「新旧数据重叠→自动全量刷新」（7 天窗口 29 次），全量刷新后重叠未消除——每次运行都多拉全量 260 天 K 线并重写缓存，刷新退化为常态而非例外（来源：2026-10-20 日志分析） | 全量刷新完成后校验重叠是否消除（未消除应告警而非静默）；对同一 cache_key 连续重复触发修正刷新加冷却/升级告警；核对增量起始日与缓存末日口径（交易日历/源差异） |
| **rf-743** | perf 基准禁网运行期间传输层仍走完整重试退避：2026-10-15 单次门禁产生 1,006 条「perf-test-report: 基准运行按设计禁网」WARNING（datasink/cninfo/hithink 各 2~3 次退避重试逐次等待），拉长门禁墙钟并淹没真实告警（来源：2026-10-20 日志+性能追审分析） | `providers/_utils.py` 重试逻辑识别「按设计禁网」失败原因直接 fail-fast（禁网是确定性结果，重试无信息量）；或 perf-test-report 桩首次命中后熔断同端点 |


### P3 — 持续监控：文件过长登记表（>500 行观察，脚本域 >400 即入观察 / **>1000 行为硬上限必须拆分**（主程序与脚本）；按距红线余量升序）

> **派生源**：行数与全集以 `scripts/check-file-length.py -v` 输出为真值（该输出列出全部 >500 行主程序、>400 行脚本、>800 行测试文件）；红线（主程序/脚本 >1000 行、测试 >1200 行）由 `check-file-length.py --ci` 自动拦截（豁免路径与本表挂账同步），不依赖本表人工发现新破线者。本表仅登记需跟踪/决策的文件，**触发式处理**：未逼近红线不排期，逼近时按本表拆分建议执行。
> **红线体系**：主程序警告 >500 / 硬上限 >1000；`scripts/` 同域（警告 >400 / 红线 >1000）；测试 >800 警告 / >1200 红线。体系调整决策与理由见 `docs/managements/technical.md`「大文件红线体系（主程序/脚本/测试）」决策记录。
> **测试文件口径**：阈值见 `developer-guide.md`「文件膨胀阈值」表（行数 >800 警告 / >1200 红线；测试项 >80 警告 / >120 红线），**当前无挂账项**；警告级全集以 `scripts/check-file-length.py -v` 为派生源，逼近红线（1200 行 / 120 项）时按「被测函数 / 场景类型」拆分为同目录兄弟分片，并同步刷新 `test-coverage.md` / `folders.md` 用例计数。

| # | 文件 | 行数 | 状态 | 拆分建议 |
|---|------|------|------|----------|

| **rf-626** | `llm/prompts_core.py`、`llm/generators.py`、`report/html_writer.py`、`analysis/rebalance.py` | 350 / 444 / 796 / 751 | **临界带四文件登记项**，`-v` 月度复核 | `html_writer`/`rebalance` 逼近 980 行启动拆分（域下沉 + 门面 re-export + 测试 patch 改指持有子模块） |
| **rf-86** | `cache/operations.py` | 739 | 500-1000 可选优化区间，增长偏快，`-v` 按月复核 | 数据结构定义/基金刷新/公共缓存/持仓缓存/缓存清理 5 个职责 |
| **rf-79** | `core/code_utils.py` | 766 | 500-1000 可选优化区间，维持现状，`-v` 按月复核 | 可考虑将 `estimate_market_cap_by_prefix()` 等非核心判定函数移出（不拆） |
| **rf-665** | `config/features.py`、`_doc_drift/_format.py`、`tui/handlers_config.py` | 737 / 558 / 534 | 500-1000 可选优化区间，`-v` 按月复核 | `features.py` 随注册表逐开关增长（每项 ~10 行），逼近 980 行时考虑将 `FeatureSwitchDef` 字段声明/注册表条目下沉独立子模块；另两文件由 `-v` 月度复核 |
| **rf-89** | `report/excel_generator.py` | 659 | 500-1000 可选优化区间，增长偏快，暂维持现状，`-v` 按月复核 | 页签编排可进一步下沉到独立 writer（后续择机） |
| **rf-80** | `report/data_status.py` | 649 | 维持现状（DegradationTracker 单类，内部职责内聚） | DegradationTracker 单类偏大（不拆） |
| **rf-711** | `web/handlers.py` | 852 | 500-1000 可选优化区间，增长较快，`-v` 按月复核 | 生成执行体可下沉 `web/run_generation.py` 子模块（逼近 980 行时启动） |
| **rf-81** | `report/html_renderers.py` | 577 | 维持现状（render 函数同属渲染域） | 所有 HTML render 函数揉合一体（不拆） |
| **rf-85** | `fetcher/fund.py` | 553 | 500-1000 可选优化区间，暂维持现状，若再增则按职责拆分 | 排名/持仓/基准三职责可拆分为子模块（后续择机） |
| **rf-78** | `fetcher/batch.py` | 520 | 维持现状（BatchDispatcher 内聚，复核确认不拆） | BatchDispatcher 本身内聚，可维持现状（不拆） |

## 已解决问题

### 归档档案

- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x 开发期已修复批次（2026-10-14 ~ 2026-10-20）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.x 已修复批次与开发期追加（2026-10-03 ~ 2026-10-12）
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


### 开发期已修复（0.13.8-dev）

（本版开发期已修复项已随 v0.13.8 发布迁入上方归档档案）
