# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.16.8
> **编号源**：`rf-next = 959`（新增问题提出后更新为 +1；已用最大 rf-958，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
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

入选标准：需先确认数据契约再动，当前不影响行为正确性。当前无登记项。

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。下表为**存量监控清单**（不占用 rf 编号，拆分后删除对应行；当前 7 项，全在可选优化区间，无红线违规）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/test/unit/scripts/test_release_tool_gate.py` 1147 行（测试登记线 900 / 红线 1200） | 按域再拆：`refresh` 编排一组、`publish` 一组独立成文件；拆分前先确认不放宽断言 |
| `src/test/conftest.py` 1007 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 装配与 marker 注册 |
| `src/python/llm/generators_orchestrator.py` 869 行（主程序登记线 700） | 生成编排与共享钩子可再分（`generators_*` 同族已多文件，按模块族对齐）；预检键/指纹段可下沉 `generators_orchestrator_cache.py` |
| `src/python/cli/_handlers.py` 789 行（主程序登记线 700） | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄壳 |
| `src/python/llm/skeleton.py` 815 行（主程序登记线 700） | 骨架模板、占位渲染、缓存归因与回写已四簇并存：模板数据/渲染逻辑可下沉子模块（`llm/skeleton_*`） |
| `src/python/fetcher/financial_report.py` 702 行（主程序登记线 700） | 索引/章节清单/正文三阶取数与负缓存同文件，刚过线：负缓存样板已收口到 `cache/_negative.py`，再涨则按「索引 / 正文 / 全文定位」三阶下沉 |
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
| **rf-945** | `self_review` 缓存键随「运行元信息」漂移：自检输入含 LLM 用量页脚与事实校验摘要段落——页脚在新生成（含 Token/耗时/费用）与缓存命中（含"使用缓存"）间必然不同，校验摘要的检查项计数又随缓存态变化（命中时排名校验跳过）。结果是上游每次重算后，下一次运行的自检键必然变化，多付一次 10~15s | 自检输入改为「纯分析正文」：新增 `strip_llm_footer`（页脚，`llm/skeleton.py`）与 `strip_fact_check_blocks`（校验摘要/建议/修正明细，`fact_checker`），编排层组装自检输入时依次剥离；报告渲染仍用完整正文（校验结论与用量信息对读者有用）。同时补分段诊断日志（未命中时打印六段输入摘要，8 位），使「哪一段变了」可直接读日志判定。实测：强制重算 `global_macro` 后下一次运行自检直接命中（0.0s，6/6 模块命中，总 24.7s），此前该场景必多一次 12.8s
| **rf-946** | 事实校验自动修正不回写缓存：完全命中缓存的运行里 `counters` 仍记 `fact_fix:智囊团深度复盘=2`（连续多轮恒为 2），修正只作用于当轮输出 → 同一缓存内容每轮都要重做一次修正，且报告展示正文与缓存存储正文口径不一致（不可复现） | 修正后**回写缓存**（`skeleton.write_back_module_cache`，键取预检/写侧同源的 `cache_info[mk]["key"]`，不改指纹、不新开键）：缓存正文 = 展示正文，下一轮命中即零修正；摘要属当轮元信息不写入。摘要拼接前回写，写失败只记日志不中断；回归 6 例（含幂等：命中轮次零修正） |
| **rf-947** | 全缓存运行时数据准备占 89%，其中「财报摘要与指标」单独 5~8s（6 次 2.5~10.4s 波动）：实测日志显示每份报告都为同一批文档重发 `/documents/{id}/sections`（源侧 200 但无可用清单），5 篇 × 0.3~1.4s ≈ 5s，是快速复跑的绝对瓶颈 | 章节清单不可得记**负缓存**（`report_sections_miss_`，注册表 6h；传输级失败仍不缓存），并覆盖「非空但不可用」清单（按清单取正文全空 → 先失效再记，恢复窗口 6h），`_invalidate_sections_cache` 同清正负两键；计时拆分为「财报摘要」「财务指标」两段（原合并段无法归因）；批量取数评估为不可行（DataSinking 索引/正文均按单标的请求，akshare 多期指标按单代码）。回归 6 例（含传输失败不缓存、失效可恢复、命中计数） |
| **rf-948** | `providers/news_dedup.py` 795 行三簇混装（分片 gzip 读写 / 保留期·体积目标·采样策略 / 统计），与 `cache/` 包「存储层拆 `_io`/`_paths`」先例不一致，本批一次 +459 行后逼近 1000 红线 | 按层拆分：字节动作 → `providers/news_dedup_anchor_store.py`；保留期/体积目标/同源采样/裁剪编排 → `providers/news_dedup_anchor_policy.py`；`news_dedup.py` 保留判定主流程并原面 re-export（`compact_anchor_file` 仍单一实现）。顺带修正测试隔离：锚点路径 patch 打到实际持有者（此前打门面 → 测试追写真实 `data/calibration/`），并清理 30 行被污染样本；回归 296 例全绿 |
| **rf-949** | 负缓存探针样板复制到第 3 份：`_miss_key` 的 lock + 命中计数 + `reset_*` + get/set 在「标的正文缺失」「章节清单不可得」「某文档无该章节」各写一遍，新增一类就要再抄一遍，命名与日志口径还会漂移 | 抽 `cache/_negative.py::NegativeCache`（`probe`/`is_missing`/`mark`/`clear`/`hits`/`summary_text`；TTL 强制取注册表类型）+ 可枚举清单 `negative_cache_entries()`/`nonzero_summaries()`/`reset_all_negative_hits()`；四处调用点改为只声明「标签 + 键前缀 + TTL 类型」，报告级汇总改为遍历清单（新增类零分支）；回归 12 例 |
| **rf-950** | `perf_history.jsonl` 历史记录的 `breakdown["数据准备"]["财报摘要与指标"]` 在新版被拆成「财报摘要」「财务指标」两键，跨版本对拍时旧键孤立存在、与新键混算会让均值失真 | 读取侧加别名归一 `_LEGACY_BREAKDOWN_ALIASES`（旧合并段 → `财报摘要+财务指标（旧·合并段）` **单列**，不与新子项混算），scripts-reference 的阶段细分表标注版本分界；回归 1 例 |
| **rf-951** | 历史 K 线主机不可达时按标的白等：腾讯 K 线单标的耗时 2 分钟级（超时预算 60s × 同源重试 3 次，且挂起也算可重试失败）→ 「历史走势」阶段十余个持仓累计二十分钟；日志实证 `Tencent K 线 sz300502 传输级失败（ConnectTimeout）` 连续出现 | 分两档收敛：provider 内 `_KLINE_TIMEOUT` 60s→10s、attempts 3→2 且挂起（≥ 预算一半）不重试；链级新增 `_HANG_ELAPSED_SECONDS=20s` 判据，挂起型直接落下一槽（不重试）。回归 3 例（挂起不重试 / 快速失败仍重试） |
| **rf-952** | `/documents/{id}/sections` 传输级失败不留状态：每份报告都为同一篇文档再付一次超时预算（实测 817432 单篇挂起 20.7s，`财报摘要` 阶段 30.5s 中占 2/3），而探测本身只是取数优选路径 | 新增 30min **短退避**负缓存（`report_sections_backoff_{doc_id}`，注册表类型 `report_sections_backoff`），探测成功即清；与「确定性缺失 6h 负缓存」语义分离。回归 3 例（开退避不进确定性缓存 / 成功解除 / 失效可恢复） |
| **rf-954** | LLM 缓存换键归因跨进程不可见：指纹/键基线只存进程内存（`_LAST_FP_COMPONENTS` / `_PREV_MODULE_CACHE_KEY`），重启后无上轮基线 → 键变了也只能落进 `ttl_expired`（实测 22:52 四模块被记 ttl_expired，实际 expert_review 键 `bb5e0593dabe…` → `d86f4195c09f…`），「哪一段输入变了」无据可查 | 新增 `llm/fingerprint_baseline.py`：编排收尾落盘「各模块键 + 指纹组件哈希」到 `data/state/llm_fingerprint_snapshot.json`，下次预检读作基线；归因主信号改为「键是否变化」（键变 ⇒ `fingerprint_changed` 并打出变化组件；键未变而读不到内容 ⇒ `ttl_expired`；无基线 ⇒ `cache_miss`）。快照读写失败降级为无基线，不参与键构造；测试隔离加基线路径重定向 + 进程内复位。回归 10 例 |
| **rf-944** | LLM 关键路径：`expert_review` 独占 57–110s（≈6.1ms/输出 token），串行尾再叠加 `self_review` 11s + 归因 4–25s；且台账无逐模块耗时，关键路径只能靠日志时间戳反推 | ① 逐模块耗时入台账（`perf_history.llm.modules[*].duration_seconds`，命中记 0）；② 归因并入并行批（`_MODULE_FNS["holding_change"]` + 共享客户端 + 异常隔离，`self_review` 仍后置）；③ 注释/文档同步为并行口径并由用例机检。实测 4 次完整报告：串行尾残差 0.02/0.01/0.04s（阈值 5s）、`expert_review` p50 61.5s（阈值 83.6s）、归因 5.7–6.5s 全在并行批内、缓存全命中运行归因 0.0s；设计见归档 `llm-critical-path-instrumentation-design.md`。评估后不实施：TTL 调值、输出预算削减、thinking 降档、并发 3→4
| **rf-938** | 去重锚点 61% 是零信息量记录（`same_src` 57,899/94,706，`ratio` 恒 0.0、`merged` 恒 false），主导体积增长 | 写侧按标题对 SHA-256 哈希 **1/50 确定性采样**同源锚点（同一样本对恒定入选，`_SAME_SRC_ANCHOR_SAMPLE` 可调，1=全量）；实测存量 94,706 → 37,913 条（40%）；回归 4 例 |
| **rf-939** | 锚点保留期 120 天大于数据实际年龄（59 天）→ 压缩保留 100%，零缩减，自检压缩建议无效 | 保留期默认降到 **30 天**；保留判定改为 `ts`（发布时间）**或** `written_at`（写入时刻）任一在窗口内即保留——补录/回溯老新闻不被秒裁；回归 5 例 |
| **rf-940** | 锚点体积无确定性上限：键全唯一 + 保留期未触发，越 32 MB 只告警不回缩（约 3 个月到 100 MB） | 压缩加**体积目标 24 MB**（`_ANCHOR_SIZE_TARGET_BYTES`，与告警线分离）：超目标按最旧裁剪到 ≤24 MB，**每分支保留最新 50 条**防小分支整类消失；读取前后比对 `(size, mtime)`，并发追加则放弃本次压缩；无行可裁不重写；回归 6 例 |
| **rf-941** | 21%（20,306 条）锚点缺 `anchor_rules_version`，与在用指纹混算 | 压缩时对无指纹旧行补 `ANCHOR_LEGACY_ERA` 标注并计数；校准报告分「当前指纹 / 历史指纹 / 未标注」三桶并列出历史指纹 Top3；回归 5 例 |
| **rf-942** | 锚点维护段文档与实现漂移（写 120 天可压小、未写缺省压缩与体积上限口径） | 按三重条件重写 developer-guide / technical / requirements R-DATA-09 / scripts-reference / testplan 与自检提示；压缩结果打印超期/体积裁剪（含分支分布）/补标注/并发放弃四类计数 |
| **rf-955** | 缓存清理器按文件名前缀统一取 TTL，把同前缀下的异构寿命键一并裁掉：`sector_flow_last_good`（设计 3 天）与 `sector_flow_negative`（设计 30 分钟）都落到 900s → 陈旧回退基准活不过一次启动清理，R-BRK-09 的回退条款结构性不可达 | 注册表新增 `exact_key_ttls` 单源声明 + `get_exact_ttl_map()`，清理器按精确键覆盖前缀默认值；取数侧 TTL 同源读取；回归 6 例（对应 `plan-237`） |
| **rf-956** | `scripts/probe.py` 子探针 import 失败被静默当成「探测失败」：入口只把 `scripts/` 加进 `sys.path`，子探针的 `from src.python…` 全部 ImportError——`csi` 因此长期输出「无可用代码」的错误结论 | 入口补仓库根 `sys.path`；`_probes` 登记表加 Protocol 契约面；`sector-flow` target 实测双通道（主 0/4、备 4/4） |
| **rf-957** | `test_fingerprint_baseline.py` 两个用例依赖执行顺序：单跑通过、整目录跑必红（同目录其他用例写过内存键基线后未复位，`reset_baseline_cache()` 只清文件侧） | `reset_baseline_cache()` 同时清 `skeleton._PREV_MODULE_CACHE_KEY`（上轮基线本就是「快照 + 进程内」两个来源）；回归 1 例断言 reset 后归因为冷启动而非「键变了」 |
| **rf-953** | `HTML 生成` 阶段耗时分化（同机同持仓 0.3s ↔ 17.3s，日志内找不到对应耗时动作） | **根因**：该阶段夹带了惰性补数据（基金排名/业绩/基金经理/风格），而卡顿源是基金经理页面的 SSL 握手超时——它以 `ConnectError` 抛出而非 `TimeoutException`，未被识别成「站点不可达」，于是又去撞档案页，同一只基金连等两次（各 ~6.9s）。**修复**：连接阶段单独封顶（`httpx.Timeout(6.0, connect=3.0)` / `(4.0, connect=3.0)`），`ConnectError` 归入「站点不可达」并跳过档案页回退；回归 2 例（握手失败不赌回退 / 连接预算封顶） |
| **rf-958** | `plan.md` 概述与正文可脱钩且无告警：`plan-70` 小节被删而概述仍引用（有编号无正文的孤儿），随后压缩概述又把唯一引用删掉，任务静默消失 | P3 恢复该小节并保留单一事实位（technical §6.9）；`check-doc-drift` 新增「概述引用的 plan-N ⇒ 正文小节或计划归档存在」断言（`_PLAN_ANY_HEADING_ID` 认无状态标记的在办小节），回归 2 例（孤儿报出 / 正文存在不误报） |

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
