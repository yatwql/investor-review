# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.16.10-dev
> **编号源**：`rf-next = 968`（新增问题提出后更新为 +1；已用最大 rf-967，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
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
| **rf-959** | 事实校验把**正确的**占比/目标权重与正确收益率改错：①「把低风险资产从当前的 18.3%（012325 12.5% + 240012 5.8%）提到 25% 附近」——18.3% 是占比、25% 是目标权重，被按最近邻改写成 012325 的 4.6% 与 240012 的 -8.0%，句子变成「从 4.6%（…12.5%+5.8%）提到 -8.0% 附近」自相矛盾；②「纳指联接 016055 +18.66%、建信装备 +21.91%」——「建信装备」是 011506 的口语简称，未解析 → 回退同句代码 016055，把正确的 +21.91% 换成 18.7%。改错后的矛盾随后被 `self_review` 当模型错误报出（矛盾由校验器制造）。根源：`_REBALANCE_TARGET_KEYWORDS` 只收「降至/升至」式、占比无「占比」字样、简称解析失败即全局最近邻兜底 | 新增三条非收益率守卫（与既有胜率/权重/止盈目标守卫同层）：①`_is_target_value_context`（数值后「附近/左右」或前 6 字「提到/提至/提高到」→ 目标位）；②`_is_breakdown_sum_context`（数值后括号内分项百分比之和 ≈ 该数值 → 合计/占比）；③`_unresolved_attached_subject`（数值紧贴的名称解析不出持仓 → 归属不可知，宁漏改不误改；时间/范围填充词与度量词先剥离）。另将 `FACT_CHECK_RULES_VERSION`（`fact-rules-2`）并入四可回写模块指纹——修正会回写模块缓存且键不变，规则语义变化须换键，否则旧缓存里被旧规则改错的正文继续复用。回归 7 例（含「守卫不过度」：可解析主体的错值仍纠正、时间填充词不遮蔽主体） |
| **rf-960** | 括号内并列多品种时数值归**首个**代码，把后一个品种的正确收益率改错：「（240012 -8.03%、561910 -36.20%）」里 561910 的 -36.20% 被改写成 240012 的 -8.0%；叠加「按数值去重（每轮只判一处）+ 修正回写缓存」，逐轮把同一事实的其余句子逐个改错，最终同一份报告与缓存里并存 -8.0% 与 -36.20%，且下游自检把矛盾当模型错误报出 | ①`_locate_subject_code` 括号作用域取**最近**代码（原来取括号内首个）；②去重粒度改为「(数值, 所在句)」——跨句各自判定，后续句里的同一数值同样受检；③改写改「全有或全无」：同一 wrong_value 的全部出现处都判错才整体替换，同句同值多义（止盈 30% 与收益率 30%）或仅部分判错则整值跳过（一处也不改）；④同句同品种只可能有一个持仓收益率——该品种收益率已确认后，句内它的第二个百分数按非收益率跳过（括号里的占比 7.3% 曾被改写成 -36.2%）；⑤`FACT_CHECK_RULES_VERSION` → `fact-rules-3` 一次性换键。回归 8 例（括号并列两品种各自的正确值都不改、错值仍按自身收益率纠正、同值多义不改、全判错才整体替换） |
| **rf-961** | 权重类表述被按收益率改写：①「它现在仍占 7.3%」——中文最常见的权重表达「占 X%」，`_NON_RATE_PRE_WORDS` 只收「占比」，裸「占」未识别，7.3% 被改成 561910 的 -36.2%；②表格行「| 建设银行 | 601939 | 8.8% | 6.5% | 减仓 | …持仓收益率 −8.03%…」——权重列与目标列是裸百分比、单元格内无任何语境词，按就近代码归因把 8.8%/6.5% 都改成 241.5%（实测单轮 9 处「修正」全是这一类）；③「已修正明细」按**判定**列表生成而非按**实际生效**，归属不可知被跳过的项仍被宣称已修正，读者无法判断正文是否真被改过；④负缓存探测（`probe()` 读不到记录 = 该缺失不存在，属正常预期）计入全局缓存未命中，虚计每轮 7~13 次并误触发「同前缀未命中 ≥5 次」告警 | ①`_NON_RATE_PRE_WORDS` 增「占」「仓位占比」；②新增 `_is_table_weight_cell_context`——数值是独立表格单元格且同行还有另一个独立百分比单元格时整体跳过（单列百分比仍校验）；③`apply_numerical_corrections` 增 `applied` 出参，runner 只把真正替换的计入明细/计数/摘要，被跳过项也不列为告警；④`cache.get` 增 `record_stats` 参数，`NegativeCache.probe` 传 False。`FACT_CHECK_RULES_VERSION` → `fact-rules-4`。回归 10 例 |
| **rf-962** | 兼容层存量清理：按本项目「不承诺兼容旧数据文件 / 旧数据结构 / 旧缓存（结构）/ 旧内部 API」的口径，代码里仍留有多处纯兼容分支，增加理解与维护成本：①`analysis/metrics.py` 重复声明 4 个常量（仅供外部直接引用，实际实现与唯一使用点都在 `metrics_returns.py`）；②`get_rate_limiter` 上被挂了一个`cache_clear` 属性（兼容旧调用点，已有模块级 `clear_rate_limiter_cache()`）；③`_benchmark_returns` 同时接 list 与 dict 两种形态（生产只有 list）；④锚点读取/压缩/体积统计/doctor 检查都额外接纳「未分片的早期单文件」（`dedup_anchors.jsonl`），含把它并入分片后删除、以及「含旧版单文件」的提示文案 | 全部移除并按新契约收紧：①删重复常量（`whatif_backtest` 改从 `metrics_returns` 取）；②`get_rate_limiter` 上的属性已移除，调用方统一走 `clear_rate_limiter_cache()`，测试相应改写并新增断言「该属性不存在」；③只接 list；④`anchor_shard_paths` 只认 `dedup_anchors-YYYYMM.jsonl.gz`（不读、不并入、不统计单文件）；相关测试改为写按月分片，并把「旧单文件仍可读」反转为「旧单文件被忽略」。**保留项（经判定不属旧格式兼容）**：`.json`/`.json.gz` 双缓存编码（均为现行格式，按体积阈值切换）、`_detail_value` 的 dict/对象双形态（两种形态均在生产使用）、`tiantian_holdings` 的季度接口回退（数据源备用通道，非我方格式）、`_llm_schema` 保留未知模块（前向兼容，防新版配置被旧代码截断）、`holding_status` 归一 Excel 浮点假象 `"600900.0"`（属现行输入形态）。回归 4 例 |
| **rf-963** | 缓存命中率被**状态探针**污染：历史数据增量链路对每只标的多读一次 `{cache_key}_correction_streak`（连续触发计数），读不到即「未连续触发」属正常预期，却按缓存未命中统计——单轮虚计 17 次，命中率从 100% 掉到 94%，并触发「同前缀未命中 ≥5 次」告警（告警本身正确，但指向的是计数口径而非真问题） | 两处 streak 读取改传 `record_stats=False`（与负缓存同一口径：状态量探针不计入命中率，其值另由自身写入路径维护）。实测同机连续两次运行：`[cache] 本次命中 157 / 未命中 0（100%）`，此前为 `555 / 38（94%）`，未命中前缀 `history_history 17 / report_datasink 13 / report_symbol 7` 全部归零 |
| **rf-964** | ①**板块/指数涨跌被改写成品种收益率**：「银行板块净流出15.06亿、跌0.35%，白酒净流出16.86亿、跌2.35%」被全局最近邻兜底改写为某品种收益率（先 102.0%、后 4.6%，随最近邻漂移）；更贵的是它**回写缓存** → 下一轮自检输入段变化 → 每轮多付一次 11~17s 自检调用（长驻进程连跑三份报告稳定复现）。②**缓存命中率汇总按进程累计而非按轮**：`reset_cache_stats` 只有定义与导出口，生产侧从不调用，长驻进程连跑时「本次命中 X / 未命中 Y」累计成进程累计值（实测未命中前缀 5→10→15 递进），「同前缀未命中 ≥5 次」告警随之失真 | ①新增 `_MARKET_SCOPE_NOUNS` + `_is_market_scope_no_subject`：分句含板块/指数/大盘类名词**且**分句内出现不了任何持仓主体（代码/全名/简称/尾名）时跳过改写（归属不可知）；②`report/_run_scope.start_report_run()` 增 `reset_cache_stats()`，与降级事件、自检载体重置同处；③`FACT_CHECK_RULES_VERSION` → `fact-rules-5`（缓存里已被改错的正文需失效重算）。回归 5 例（板块涨跌不改、指数涨跌不改、含持仓主体的错值仍纠正、报告边界清零计数） |
| **rf-965** | ①**指数涨跌被改写成基金收益率**：`纳斯达克100涨1.18%、标普500涨0.60%` 里的 1.18% 被改成 016055 的 18.7%——指数中文名与基金名重叠（「纳斯达克100」同是 016055 名称的一部分），「分句内有无持仓主体」的判据在此失效；改错后同样回写缓存，使下一轮 `self_review` 重算（实测 16.4s）。②**自检输出上限过低反复触顶**：`max_tokens_self_review=3072`，实测输出恰好 3072 被截断 → 自动以 4608 重生成，同一份自检付两次调用且多等 5~8s。③**版本盐在日志里不可见**：两个版本号都会整批换键，但运行日志无痕迹，模块整批重算时只能翻代码比对指纹。④「同前缀未命中」告警只说前缀不说键，看到还得回 DEBUG 翻 | ①市场口径判据由「分句内有无主体」升级为「市场名词与持仓主体谁更近」，并按**位置重叠**排除「市场名词其实属于某持仓简称」（`_subject_spans` 代码/全名/简称三级区间 + `_alias_normalized` 位置回映）；词表补 纳斯达克/道琼斯/富时/科创50/创业板指/北证；②默认上限 3072→4608；③新增 `fingerprint.cache_key_salts()` / `log_cache_key_salts()`，报告边界打「本轮开始」、收尾 `[cache]` 汇总行带版本盐尾注；④告警追加该前缀下未命中次数最多的 5 个具体键（键名计数有界 500）。`FACT_CHECK_RULES_VERSION` → `fact-rules-6`。回归 9 例 |
| **rf-966** | 近 24 小时变更的技术债核查发现 6 项：①**分层越界**——`cache/_stats.log_cache_summary` 反向 `import llm.fingerprint` 取版本盐（cache 是基础层，只能依赖下层与贯穿层；该 import 无环但方向错，且 check-import-surface 查不出）；②**运行收尾日志分散**——缓存汇总由 `core/perf.save()` 打、版本盐由报告层打，同一「本轮结束」信息分两处；③**主体匹配三份实现**——`_locate_subject_in`（取代码）/ `_has_subject_candidate`（取布尔）/ 数值检查器本地 `_subject_spans`（取区间）各写一遍同一套「代码→全名→简称归一」匹配，口径一分叉就出现「主体解析得到、距离算不出」的内部不一致；④**规则版本注释写成逐版沿革**——代码注释列 v2~v6 变更史，与「注释只述现状、沿革归 changelog/review-findings」的纪律冲突（守护反复报痕迹）；⑤`_key_prefix` 文档示例输入输出不符；⑥`chain_incremental` 连续触发计数两处重复同注释读法，且 `int()` 遇非数值（脏数据）会中断取数主链、日期缺失时 `.get("date")` 比较抛 TypeError | ①`log_cache_summary(top, salts_note="")` 由调用方传入版本盐，cache 侧只依赖 cache；②新增 `report._run_scope.finish_report_run(perf)` 统一收尾（落台账 + 版本盐 + 缓存汇总），缓存汇总由该 hook 统一打，`perf.save()` 只负责落台账，4 处调用点改走该 hook；③`_subject_spans` 下沉 `_utils` 作单源，`_has_subject_candidate` 由它派生（描述性尾名单独兜底），数值检查器改为 import；④版本注释只留「递增判据 + 现状口径位置」；⑤示例改为 `llm_expert_review_…` → `llm_expert_review`；⑥抽出 `_correction_streak_key` / `_read_correction_streak`（非数值按 0），日期比较加字符串前置判定。回归：`unit/llm`+`unit/fetcher`+`unit/cache`+`unit/core` 全绿，新增/改写 3 例（版本盐由调用方传入、计数键脏数据按 0、日期缺失不比较） |
| **rf-967** | dev 连续 8 次推送在 GitHub CI 的 `portability` job 变红，本地三档门禁全绿：`test_ruff_exclude_contract.py` 两例用 `subprocess.run(..., text=True)` 未传 `encoding=`，在 `PYTHONWARNDEFAULTENCODING=1` + `pytest.ini` 的 `error::EncodingWarning` 下直接抛异常。本地不设该环境变量故无从暴露，属典型「本地绿、CI 红」环境差异 | ①两处调用补 `encoding="utf-8"`；②新增静态回归守卫 `src/test/unit/test_subprocess_text_encoding_contract.py`——AST 扫描 `src/python`/`scripts`/`src/test` 全部 `subprocess.*` 调用，凡开了文本模式（`text=True` / `universal_newlines=True`）而缺 `encoding=` 即失败，并附扫描器自检 4 例（能抓到缺 encoding / 接受显式 encoding / 认 `universal_newlines` 别名 / 不误报二进制模式），避免用例恒真。**本地验证口径**：`PYTHONWARNDEFAULTENCODING=1 pytest src/test/unit` 全量通过（12327 通过），与 CI 该 job 同源 |

### 归档档案
- [`archived_review-findings.0.16.x.md`](../archive/v0.16.x/archived_review-findings.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-10-27）
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
