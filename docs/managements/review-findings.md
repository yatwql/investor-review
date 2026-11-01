# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.16.15-dev
> **编号源**：`rf-next = 1022`（新增问题提出后更新为 +1；已用最大 rf-1021，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
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
| **rf-1006** | 弱证据断言（一个用例的全部断言只有 `is not None` / `isinstance` / `len>0` / 裸真值，只证明「不崩/非空」）。**口径修正**：初扫 189 例 → 计入 `unittest` 断言后 143 例 → 再扣除 `assert_called*` 等 mock 断言后**真弱 75 例**（前两版口径把 `self.assertEqual` 与 `assert_called_once_with` 误判为无断言） | 统一以「用例名承诺了什么」为判据：**已强化 28 例**——trace 守卫 4 文件 24 例改为断言命中的**规则分类**（`_code_cat`/`_doc_cat`，从「有命中」升级到「命中了哪类规则」，并顺手消掉两个文件里各复制一份的 `_code_hit`/`_doc_hit`，改为从兄弟模块导入单源）、熔断网关 4 例改为同一实例/稳定快照断言；**经判读接受 47 例**（`isinstance` 类型契约 15、`not-none` 对象存在契约 15、非空集合/健壮性 17——名字只承诺类型或存在，现断言即其正确强度，再加强只是换写法）。不入门禁（弱断言与合法 smoke 难静态区分） |
| **rf-1004** | 全量时间炸弹筛查余量：`probe-date-bombs.py --all` 扫出 48 个 rot-suspect 文件，账本族 5 个已修（rf-1002 / rf-1003 / 判别式加固）；余 43 个多为**变异伪信号**（测试日期绑生产侧锚点/跨模块 fixture/星期-财季语义），但未逐个人工判读，不能断言全清 | 逐文件人工判读：`python scripts/probe-date-bombs.py --files <file> -v` 看失败断言，再判断是「日期需近期」还是「语义位移」。**自动化重定基已证伪**——三种策略（锚点 = 当天−30d / 当天 / 周对齐平移）分别只通过 4 / 0 / 2 个文件，说明失败主因不是「距 now 变远」，批量改写不安全。静态守卫（`check-test-redundancy` 第 9 类）只覆盖账本日期实参，其余类不入门禁 |

### P3 — 持续监控：兼容残留

入选标准：需先确认数据契约再动，当前不影响行为正确性。

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。下表为**存量监控清单**（不占用 rf 编号，拆分后删除对应行；当前 8 项，全在可选优化区间，无红线违规）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/test/unit/scripts/test_release_tool_gate.py` 1147 行（测试登记线 900 / 红线 1200） | 按域再拆：`refresh` 编排一组、`publish` 一组独立成文件；拆分前先确认不放宽断言 |
| `src/test/conftest.py` 1007 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 装配与 marker 注册 |
| `src/python/llm/generators_orchestrator.py` 869 行（主程序登记线 700） | 生成编排与共享钩子按模块族再分；预检键/指纹段可下沉 `generators_orchestrator_cache.py` |
| `src/python/llm/skeleton.py` 815 行（主程序登记线 700） | 模板数据与渲染逻辑可下沉 `llm/skeleton_*`（骨架模板 / 占位渲染 / 缓存归因 / 回写四簇并存） |
| `src/python/cli/_handlers.py` 789 行（主程序登记线 700） | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄壳 |
| `src/python/tui/handlers_holdings.py` 782 行（红线 1000） | 面板流程与输入采集高度耦合（共用 `_Session`），拆分收益低于回归面；再涨 ~150 行则按「面板流程 / 输入采集」两段拆，并把 `_market_data` 的会话内记忆一并做进去 |
| `src/python/fetcher/financial_report.py` 702 行（主程序登记线 700） | 刚过线：再涨则按「索引 / 正文 / 全文定位」三阶下沉（负缓存样板已收口到 `cache/_negative.py`） |
| `src/static/tmpl/report_template.html` 994 行（**不在行数守护域内**：`check-file-length` 只扫 `.py`） | 要么纳入守护扫面（模板按 1000 红线），要么按页签拆 partial；余量约 6 行，下一项报告页改动即触线 |

## 已解决问题

### 开发期已修复（0.16.15-dev）

| # | 问题 | 修复 |
|---|------|------|
| **rf-1021** | 因子暴露取数串行 + 单路取数无耗时/告警盲区：04-01 12:27 运行 因子暴露 10.48s，其中 9.4s 是「持仓 K 线全部回来后才开始拉因子指数 K 线」的空等（两组互不依赖）；单路取数无计时，事后只能看到阶段总数，无法定位是哪只标的/哪个指数 | 两组取数合并到同一 `worker_pool` 并发发出（worker = min(factor_workers, 持仓数 + 因子指数数)），墙钟由「两组之和」变为「各自最慢值」；新增 `_timed_fetch` 单路计时，超 5s 打 WARNING（带标的标签与耗时），行业 Beta 的两路取数同样接入；2 例回归（并发墙钟 < 0.7×串行基线、慢路告警含标的） |
| **rf-1019** | 并发只有「逐池上限」没有「进程级预算」：各池各自 `min(请求, max_total_workers)`，多池叠加实测可达 15+ 线程；而配置注释/文档把 `max_total_workers` 写成「全局 batch 线程硬上限」，与实现不符；弱机器只能靠新加的核数钳位兜底 | 新增 `core/concurrency.GOVERNOR`：参与池（`BatchDispatcher` + `worker_pool`）建池时从共享预算分配，不足缩到至少 1 并 WARNING（不抢占已运行池）；预算 = min(配置 max_total_workers, 核数)；每份报告由 `PerfCollector` 重置观测并把 `concurrency_budget/peak/clamps` 写入 perf_history；文档改为「两层上界（逐池 + 进程级）」；9 例回归（预算解析/缩容告警/同名幂等/释放/worker_pool/快照计数）+ conftest 自动重置账本 |
| **rf-1020** | 4 处压力敏感并发热点硬编码且无配置口：实时取价 8、基金重仓股市值/PE 8、风格因子 6（两处）/4（两处）、指数历史 5——弱机器/弱网只能改代码；同时这些池也不参与全局预算，缩容管不到 | 新增 `batch.market_price_workers`(8) / `fund_style_workers`(8) / `factor_workers`(6) / `index_workers`(5)，默认值 = 原硬编码值（零行为变化），四处改为 `get_batch_worker_count(...) + worker_pool(...)` 纳入预算；配置默认值、模板、配置手册/参考手册四处同步 |
| **rf-1017** | 财报摘要并发度不足：`batch.datasink_workers` 默认 2，6 只标的 × 3 次请求（索引/章节清单/正文）要排 3 波——实测首波索引 4.3s、整段 13s，加上正文波次共 25.7s，是数据准备的最大残差 | 默认并发提到 **3**（DataSinking 免费档 3 请求/秒，2 并发吃不满；provider 层限速器仍逐请求兜底，不会因并发超限）；config 默认值、`financial_report_digest` 兜底值与配置手册/参考手册三处同步，3 并发压到 2 波 |
| **rf-1018** | 季报持仓探测两处浪费：① 无数据的基金每轮都重走 4 个季度 × 2 通道（jjcc/zqcc），无负缓存；② jjcc 空回前挂起实测 6.9s（012325 超短债），串行等完才改 zqcc，单只基金白等一整段预算，穿透阶段 15.3s 由此抬升 | ① 新增负缓存类型 `hold_qmiss`（6h，键含年月，新季度天然新键）——双通道均空即登记，后续运行跳过该季度；② 新增 1.5s 对冲：jjcc 超时未回即并发发出 zqcc，谁先带回非空内容先用谁（jjcc 快速返回时不发额外请求），线程池 `shutdown(wait=False)` 避免等回在途请求；负缓存与对冲各 1 例回归 + 快速路径「不多发请求」1 例；负缓存登记表/配置手册/手册缓存表/technical 四处同步 |
| **rf-1011** | 近 7 天最慢一次 289s：基金 F10 费率按代码串行取数（9 只 6.1/18.8/26.1/31.0s ≈ 82s，快照对比 85.8s 几乎全是它）；同一站不可达时每只基金还要等满 15s | `fetch_fee_index` 改并行扇出（复用 `fetcher/batch.BatchDispatcher`，≤4 线程、结果保序、单代码失败不中断批）；费率页超时拆为 `httpx.Timeout(read=15, connect=4)`，不可达主机 4s 内失败；补 2 例回归（并发度≥2 + 单代码异常隔离、连接预算 4s） |
| **rf-1012** | hithink 指数 K 线必然失败：`fetch_index_kline` 把指数 thscode（`000930.SH` 等）发到 A 股端点，上游回 `code=1002 Unknown thscode`（2026-10-28 单次运行 18 次）；该源又是 `history_index` 链最后一位＝必然失败的兜底 | 本源指数 K 线直接返回空（不发请求，docstring 写明实测依据），删除只剩它用的 `to_index_thscode`，`history_index` 链移除 hithink；回归用例改为「不发起任何请求 + 链成员不含 hithink」 |
| **rf-1013** | 写盘阶段偶发 18s 无告警无归因：HTML「页面写入」p50 0.23s，7 天内 3 次 18.0/18.3/19.8s，同批 Excel 一次 10.6s | `core/perf.warn_slow_write(label, seconds, path)` 超阈（5s）告警并带产物大小/路径；接入 HTML 页面写入（路径+大小）与 Excel 生成（输出目录）；补 3 例（阈值下静默、超阈含 MB 与路径、目录路径只报路径） |
| **rf-1014** | `读取 llm_settings.json 失败，LLM 开关按默认展示` 6 次（10-27/10-28）不带原因，无法区分半写、权限、JSONC 解析失败 | 复核：读取入口已在 2026-10-28 补 `(异常类型: 消息)` 与路径（此后 0 复现）。本轮补回归用例锁死「失败日志必须含类型与路径」，防再次退回静默 None |
| **rf-1015** | 退役配置键告警 `config.json market_hour_aware 已退役并被忽略` 5 次（2026-10-25） | 复核关闭：兼容层移除后源码已无该文案，当前 `config.json` 无该键，2026-10-25 之后 0 次复现——无需改代码 |
| **rf-1016** | 「风格与因子」阶段 p95 18.3s / max 208.8s，却只是一个合并计时项，分不清是取数、行业 Beta 还是相关性计算 | 拆三段记入 breakdown（`因子暴露` / `行业 Beta` / `相关性矩阵`）；旧「风格与因子」键在 perf 历史读取侧按别名列为「因子暴露+行业Beta+相关性（旧·合并段）」，不与新子项混算；补 2 例（三子项入账、旧键别名可见），文档三处同步 |
| **rf-1010** | 近 60 小时变更自查出三类跨层文案重复：①同一句「本次改动 N 项（u 撤销上次 · U 全部还原）」页脚在 `tui/handlers_config.py` 与 `tui/handlers_switch.py` 各一份；②调仓输入持仓读取失败提示在 CLI/TUI/Web 各写一份 f-string；③日志/健康历史读取失败提示三渠道三种措辞（「读取运行日志失败（详见日志）」/「读取运行日志失败」/「读取运行日志失败（详情请查看日志）」，「读取数据源健康历史失败」/「读取健康历史失败」）——渠道共性规则单源清单未覆盖，改一处漂一处 | ①`tui/switch_panel.change_footer(count)` 单源，配置面板与导航面板共用（`config_undo_footer` 改为委托）；②`whatif_operations.WHATIF_BASE/TARGET_HOLDINGS_UNREADABLE` 常量三渠道引用；③`core/log_reader.LOG_READ_FAILED_MESSAGE` + `core/perf.HEALTH_HISTORY_READ_FAILED_MESSAGE` 三渠道引用（Web 措辞随之与 CLI/TUI 统一）；`test_channel_layering` 补 3 例契约（含渠道层不得复现字面量的反向断言），`technical.md` 跨渠道单源清单登记三项新来源 |
| **rf-1009** | 只读外部虚拟环境启动中断：`.venv` 符号链接到他人所有的 `env.investor`（`drwxr-xr-x nobody:nogroup`）时，`requirements.txt` 一变（哈希漂移）便进依赖安装——依赖已满足时 pip 不写盘即成功返回，紧接着 `echo "$REQ_HASH" > .venv/.deps_installed` 报 `Permission denied`，被 `set -e` 直接掐断启动（此前「无此毛病」只因哈希恰好未变、从不写标记） | 依赖标记加可写性回退（标记或 venv 目录不可写 → 落 `data/cache/.deps_installed`）；只读 venv 按 `requirements.txt` 逐条校验已装版本（不跑 `pip install`），缺/低于约束才报错并给出外部环境安装命令；`test_launch_script_regression.py` 补 2 例回归（只读+已满足 → 越过依赖段；只读+缺失 → 可读报错）；实机启动已越过依赖段进入 TUI |
| **rf-995** | 设计护栏 W4 字号档外 8 处：`font-size: 0.95rem`（15.2px），折算后不在字阶 11/12/13/14/16/17/18/20/22px 上 | 统一取 `1rem`（16px），行高与间距不变；护栏 W4 归零 |
| **rf-996** | 设计护栏 W5 间距档外 172 处：实现停在 6/10/14/18/20 等中间档，与 DESIGN.md 间距阶 0/4/8/12/16/24/32 不符 | 全部吸附到间距阶（等距取小值）；侧栏 220px 收敛为 `--toc-width` token、`.sr-only` 与汇总片负值归零；护栏 W5 归零 |
| **rf-997** | 单次运行写盘相位异常：HTML 18.1s / Excel 10.6s（同口径中位 0.2 / 0.3s），产物尺寸与历史一致 | 同环境复跑两次均 0.03 / 0.23s，宿主 I/O 探针（顺序写 2905 MB/s、905K 落盘 1.1ms）正常 → 瞬时宿主负载、非代码缺陷，观察关闭 |
| **rf-998** | 命中内容缓存的模块仍带费用、「使用缓存」标记失真：会话累计值未按本次裁剪，逐模块 `costs` 整字典照搬，汇总表与用量页签同源失真 | `_usage_delta` 逐模块 `costs` 按币种做差、`cached` 按本次有无 token 增量判定；`record_per_module` 真调用时翻回 `False`；历史台账按各次真实花费重分配；回归 1 例 |
| **rf-980** | 版切首跑「明细装配与建议」长尾：10.5s vs 常规 0.45s | 两次版切首跑 0.544s / 0.948s 不复现；该阶段长尾散见多版本、与版切无关 → 观察关闭 |
| **rf-999** | 报告层结构性债：单函数 >120 行 57 个（最大 `generate_excel_report` 466 行、`_generate_report_full` 391、`write_html_report` 378、`generate_all_llm` 372），签名 ≥13 参数 31 个（最劣 `_render_template` 80 个关键字参数、`write_html_report` 49、`_generate_full_html_report` 44、`generate_excel_report` 32）——参数镜像模板上下文，改一个字段要动签名与调用两侧；`check-file-length` 只看文件行数，函数级/签名级阈值不在守护域内，故长期未被拦 | 分两刀走：① 先给 `_render_template` 引入 `RenderContext` 数据类（单调用点：`html_writer` + 用例内 `_build_minimal_render_data`），把 80 参数收成一个入参；② 再按域拆 `generate_excel_report` / `write_html_report`（页签族上下沉），每刀以「模板 golden hash 不变」为验收；拆完补一条函数级行数与签名参数数的守护（阈值待定，先观察） |
| **rf-1000** | 依赖声明双源漂移：`akshare`（requirements `>=1.16,<2.0` vs pyproject `==1.18.64`）、`pdfplumber`（`>=0.11,<1.0` vs `==0.11.10`）两侧策略冲突，`h2` 只在 requirements 出现——「启动脚本装环境」与 `pip install .` 解析出两套依赖，环境差异无法复现；该域不在十守护内 | 两文件声明角色与契约写进头部注释（pyproject 只列运行时直接依赖，requirements 含传递锁定/开发工具），约束逐字对齐（`akshare >=1.16,<2.0`、`pdfplumber >=0.11,<1.0`、补 `h2>=4.2.0`）；新增 `src/test/unit/test_dependency_declarations.py` 四例守住：约束逐字一致 / 额外包必须归类白名单 / 白名单不得留空条目 / requirements 保 BOM |
| **rf-1001** | 共享常量多处字面量各写一份：`DEFAULT_WINDOW = 60` ×3（`industry_beta`/`style_factor_regression`/`correlation`）、三档估值刻度 `TIER_UNDERVALUED/FAIR/OVERVALUED` ×2（`valuation_percentile` 定义 + `market_temperature` 同值副本，后者实际零引用）、`SIDE_BUY/SIDE_SELL` ×2（`trade_cost_model`/`holdings_editor`）；改口径/文案要改多处，漏改即静默不一致 | 收敛到 `core/constants.py` 单一来源（运行时读取的模块 `import` 引用），删除 `market_temperature` 的三条死副本；`MIN_SAMPLES`（相关性重叠样本 vs 估值序列样本）与 `SOURCE_CONFIG`（映射来源 vs 配置来源层级）经核为**同值不同义**，不合并，就地补注释说明避免误并 |
| **rf-1002** | 时间炸弹测试：`test_news_dedup_compact.py::TestSizeCap::test_branch_quota_protects_small_branch` 用绝对日期 `2026-10-01 10:00` 造样本，而锚点保留期默认 30 天按 `now()` 计算 → 2026-10-31 当日起 300/303 条样本先被判 `expired`，体积裁剪路径根本没执行（`trimmed=0`），用例失败且失败信息看不出是「样本过期」；同文件另两处 `2026-10-28` 为同类潜在炸弹（2026-11-27 起失效）。生产代码行为正确（保留期先于体积裁剪） | 新增 `_recent_ts(days_ago, hour)` 相对时间 helper 替换全部 4 处绝对日期；被测用例补**前提自检** `assert result["expired"] == 0`，时间戳再滑出窗口时错误直指原因而非伪装成功能缺陷；`developer-guide.md`「测试文件规范」补绝对日期禁令（含正/反例与「远过去用常量偏移」写法）。全仓扫描：228 个测试文件含 2026+ 绝对日期字面量 1965 处（多为 fixture 输入，为上界），其中 55 个同时出现保留期/TTL 关键词，后续按清单逐个核算，本轮不扩面 |
| **rf-1008** | 近 8 小时变更（66 文件）自带的技术债，自查出 4 类共 6 处：①**同一「相对日期」助手写了 5 份**（`test_signal_ledger._day` / 三个 decision 测试的 `_BASE+_d` / 两个 capture 测试的 `_REPORT_DATE` 直派生 / `test_news_dedup_compact._recent_ts`）——修一处漂一处；②ruff 检出的未使用导入 1 处；③行为改了文案没改 2 处（`eval-dedup-threshold.py` 仍打印「保留行中无指纹、已补 legacy 标注的」；`test_news_dedup_compact` docstring 仍写「无需补标注」）；④`test_decision_llm_capture` 5 处 `_parse_table_row()` 结果直接下标（Optional 未收窄） | ①新建 `src/test/_relative_dates.py` 单源（`anchor`/`day`/`recent_ts`，docstring 写明为何禁止各文件自写），6 个测试文件改为导入（窗口不同的保留一行薄包装）；②删除该未使用导入；③两处文案改为现状（丢弃无指纹旧行）；④补 `assert row is not None`（同时强化断言）。另把 `history_snapshot` / `whatif_writer` 两处 `os.makedirs` 的异常补上下文路径（消掉长期挂的 unchecked-call 观察项）。复核确认测试内 `_code_hit`/`_doc_hit` 副本已无残留 |
| **rf-1007** | 按「不兼容旧数据/旧文件/旧缓存/旧配置/旧内部 API」政策全仓核查出的遗留兼容层 8 处：①去重锚点旧行（无 `anchor_rules_version`）补 `legacy` 标注永久保留（`news_dedup_anchor_policy` / `news_dedup_rules.ANCHOR_LEGACY_ERA`）②快照时间戳接受 ISO 等 4 种旧形态（`history_snapshot._SNAPSHOT_TS_FORMATS`）③LLM 内容纯文本回退按 `\n\n` 分段「兼容历史输入」（`llm_content._split_html_blocks`）④JS 资产产出松散副本「兼容既有产物布局」（`_copy_js_assets`，`html_writer` + `whatif_writer` 调用）⑤`reader._EXPECTED_HEADER` 无引用死别名、⑥`reader._TRADE_HEADER` 内部别名⑦`fund_manager._request_fund_html` 无调用方兼容壳、⑧`pipeline_data_builder` 指向已删模块的「orchestrator.py 兼容入口」陈旧标题 | 全部删除/收敛：旧锚点行**直接丢弃**（统计键 `unattributed` 语义改为「丢弃数」）；快照时间戳唯一形态 `YYYYMMDDTHHMMSS`；LLM 内容只认块级 HTML；JS 资产只内嵌不产松散副本（`_copy_js_assets` 及 2 处调用点删除）；两个 reader 别名删除（`TRADE_HEADER` 直接引用）；`_request_fund_html` 删除；陈旧标题改写。同时校正 4 个锁定旧形态的用例（锚点 legacy 标注→丢弃、ISO/纯文本分段→单块、旧 `metrics_*` 键→通用未知键、旧 `history.analysis`→通用未知项），并把 prosperity「旧 dict benchmarks」用例改名为「非契约形状被忽略」（生产本就只接受 list）。**核查确认无需改动的三类**：旧缓存文件（`_CACHE_KEY_VERSION` 入文件名、不读旧版本）、旧配置项（未知键只 warn 忽略、无迁移/回填）、持仓表头（仅容忍尾部多余列，不接受旧列名/列序） |
| **rf-1005** | `src/test/unit/cache/test_cache_report_boundary.py:42` 方法级 `@pytest.mark.unit_cache` 使用**未注册**标记（文件级 `pytestmark` 已是 `unit_core`，该行属残留笔误）——`check-test-markers` 唯一违规项，且会让该用例在选择器上成为「无域」孤儿 | 删除该行方法级标记（域由文件级 `pytestmark` 提供）；`check-test-markers` 由 649 通过 / 1 违规 → 650 通过 / 0 违规 |
| **rf-1003** | rf-1002 清单核算出的真实时间炸弹（变异筛查：把测试内绝对日期整体回移 3 年，“差异即依赖日期处于近期”）：4 文件 20 例依赖写死日期处于保留期内，而账本**写侧即裁剪**（`signal_ledger.append_signals` → `prune_jsonl_by_age` 730 天；`decision_ledger` 同系）——最近一例 2028-09-09 起失效，失败形态是“空账本/KeyError”，看不出是日期过期 | 4 文件（`unit/core/test_signal_ledger.py`、`..._edge.py`、`test_doctor.py`、`unit/report/test_signal_record.py`）全部改为从当天回推派生（`_day(offset)` / `date.today() - timedelta(days=30)`），断言改用派生值拼接；文件内绝对日期清零；边界用例 2 处刻意畸形入参补类型忽略注释。**该类缺陷已常驻化**：静态守卫 `check-test-redundancy.py` 第 9 类 `check_ledger_absolute_dates`（入门禁）+ 全域经验筛查 `probe-date-bombs.py`（不入门禁）。**清单其余 7 文件判为变异伪信号**（生产侧显式注入 today 参数 / 无时钟依赖 / 星期-财季语义随日期位移改变）：`test_crisis_annotation`（历史危机区间为生产侧真实日期）、`test_trading_calendar`（周末判定）、`test_cninfo`（财季分类）、`test_tiantian`（新老期间比较）、`test_market_value_premium`（显式 `self.td`，2023-06-24 为周六）、`test_release_tool`（today 作参数传入，样本在未变异的 fixture 里）、`test_holding_change_injection`（窗口串为无横线格式未被替换） |

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
