# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> **最近发布 [0.16.14]**（2026-10-30）——已发布版本段随发布移入 [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md)；本文件只保留当前开发版本段与归档索引。

---


## [0.16.15-dev] - 开发中（未发布）

### 修复

- **财报摘要并发度提到 3（rf-1017）**：`batch.datasink_workers` 默认 2 → 3——6 只标的 × 3 次请求（索引/章节清单/正文）由 3 波压到 2 波（实测首波索引 4.3s、整段 13s）；免费档 3 请求/秒正好吃满，provider 层限速器仍逐请求兜底。配置手册/参考手册与代码默认值三处同步。
- **季报探测负缓存 + jjcc 对冲并发（rf-1018）**：新增 6h 空季度负缓存 `hold_qmiss`（jjcc/zqcc 双通道均无持仓即登记，无数据基金不再每轮重走 4 个季度）；jjcc 超 1.5s 未返回即并发发出 zqcc、先到先得（实测超短债基金 6.9s 空回等待），jjcc 快速返回时不发额外请求；穿透阶段单只基金的最坏等待由「整段超时预算」降到 1.5s + 一次 zqcc。
- **基金费率并行取数 + 连接预算收紧（rf-1011）**：`fetch_fee_index` 由串行改并行扇出（`BatchDispatcher`，≤4 线程、保序、单代码失败不中断批），费率页超时拆为 `read=15s / connect=4s`——近 7 天最慢一次 289s 里的 85.8s 阶段（9 只基金费率 6~31s 串行）与「不可达主机每只各等 15s」同时收敛，补并发/失败隔离与连接预算回归。
- **hithink 指数 K 线死兜底移除（rf-1012）**：该源只有 A 股端点，指数 thscode 被上游 `code=1002` 拒收（10-28 单次 18 次）。指数 K 线改为直接返回空不发请求，删除随之无用的 `to_index_thscode`，`history_index` 链移除该源；回归用例改为断言「不发请求 + 链不含该源」。
- **落盘慢告警（rf-1013）**：`core/perf.warn_slow_write` 在阶段超 5s 时告警并带产物大小与路径，接入 HTML 页面写入与 Excel 生成——把 7 天内 3 次 18s 级写盘停顿从「只能事后翻历史」变成日志自带现场。
- **只读外部虚拟环境启动中断（rf-1009）**：`.venv` 链接到他人所有的外部环境时，`requirements.txt` 一变就走依赖安装（依赖已满足时 pip 不写盘即成功），随后写 `.venv/.deps_installed` 报 `Permission denied` 被 `set -e` 掐断启动。依标记改为「不可写则落 `data/cache/.deps_installed`」；只读 venv 按 `requirements.txt` 逐条校验已装版本（不跑 `pip install`），缺/低于约束时明确报错并给出外部环境安装命令；补 2 例回归（只读+已满足、只读+缺失）。

- **弱证据断言清零（rf-1006）**：按「用例名承诺了什么」逐例判读，强化 28 例——trace 守卫 4 文件的命中断言从「有命中」升级为断言**规则分类**（`_code_cat`/`_doc_cat`：能发现规则顺序调整与跨类误匹配），并把两个测试文件里各自复制一份的 `_code_hit`/`_doc_hit` 改为从兄弟模块导入（顺带消掉重复实现）；熔断网关 4 例由 `isinstance` 升级为「多次取到同一实例」与「稳定快照」断言。另修正 rf-1006 的统计口径（189 → 143 → 真弱 75：先前未计 `unittest` 断言与 `assert_called*` mock 断言），余 47 例经逐类判读确认为「类型契约/对象存在/非空集合」即其正确强度，不再改写

- **测试分类标记违规（rf-1005）**：`test_cache_report_boundary.py` 一处方法级 `@pytest.mark.unit_cache` 用了未注册标记（文件级 `pytestmark` 已是 `unit_core`，该行是残留笔误），使该用例在标记选择器上成为无域孤儿；删除该行后 `check-test-markers` 650 通过 / 0 违规。另按用户要求全量核对测试用例：冗余（九类守卫 0 finding + 26 组同名同骨架逐组判读均为合法矩阵契约）、无效（无断言/自证/恒真/弱 mock 全 0）、命名与内容（用例级名称词零重合 0 例）均未见需处理项；仅登记 **rf-1006**：189 例弱证据断言（全部断言只有 `is not None`/`isinstance`/`len>0`/裸真值）作为 P3 监控项，待按「名字承诺了什么」逐例判断是否补特征断言

- **时间炸弹第二批（rf-1003，按清单核算）**：用「测试内绝对日期整体回移 3 年」的变异筛查把 55 个含保留期/TTL 关键词的文件跑了一轮，11 个出现变异失败，逐条判读后 4 个是真炸弹（账本保留期 730 天且写侧即裁）：`test_signal_ledger.py` / `test_signal_ledger_edge.py` / `test_doctor.py` / `test_signal_record.py` 共 20 例改为从当天回推派生日期，文件内绝对日期清零；其余 7 个为变异伪信号（显式 today 注入 / 无时钟依赖 / 星期-财季语义随位移改变），在 rf-1003 里逐个记明判据备查

- **时间炸弹测试（rf-1002）**：`test_news_dedup_compact.py` 的体积裁剪用例用绝对日期 `2026-10-01` 造样本，撞上 30 天锚点保留期（按 `now()` 算）——2026-10-31 当天 300/303 条先被判 `expired`，体积裁剪路径未执行而断言 `trimmed > 0` 失败，失败信息看不出是样本过期。改用 `_recent_ts()` 相对时间（4 处绝对日期全替换），并给用例加前提自检 `expired == 0`；`developer-guide` 测试文件规范补「勿用绝对日期参与与现在比较的判定」及其反例

- **依赖声明单源化（rf-1000）**：`requirements.txt` 与 `pyproject.toml` 长期各自演进——`akshare` 一边 `>=1.16,<2.0` 一边 `==1.18.64`、`pdfplumber` 一边 `>=0.11,<1.0` 一边 `==0.11.10`，`h2` 只在 requirements 出现且 pyproject 缺声明；于是启动脚本装出的环境与 `pip install .` 不是同一套，差异无法复现。现在两文件头部明写角色分工（pyproject 只列运行时直接依赖，requirements 另含 flask 传递锁定与开发工具），运行时约束逐字对齐（补 `h2>=4.2.0`）；新增 `test_dependency_declarations.py` 四例守住约束一致、额外包必须归类、白名单不留空条目、requirements 保 BOM
- **共享常量单源化（rf-1001）**：`DEFAULT_WINDOW = 60`（行业 Beta / 风格因子 / 相关性三处）、三档估值刻度 `TIER_*`（估值分位与市场温度各一份，后者零引用）、`SIDE_BUY/SIDE_SELL`（费用模型与持仓编辑器各一份）收敛到 `core/constants.py` 单一来源，消费模块改 `import` 引用；`MIN_SAMPLES`（相关性重叠样本 vs 估值序列样本）与 `SOURCE_CONFIG`（映射来源 vs 配置来源层级）核为同值不同义，就地补注释禁止误并

- **跨渠道共用文案与取价枚举单源化**：调仓不可用提示在 CLI/TUI/Web 三处各写一份字面量（含 Web 的错误码重复），收敛为 `whatif_operations.WHATIF_UNAVAILABLE` + `whatif_unavailable_message()`；取价方式「官方净值(T-1)」原本在 `market_value` 产出、`html_jinja_env` 与 `_holdings_detail_blocks` 各自比较字面量，收敛为 `market_value.PRICE_TYPE_OFFICIAL_NAV_T1` 并由消费方引用；行情获取进度提示 4 处收敛为 `progress.MSG_FETCHING_MARKET*`。新增跨渠道单源契约用例 2 例（字面量不得在渠道层复现）。**另登记 rf-999**：报告层 57 个函数 >120 行、31 个签名 ≥13 参数，按「RenderContext → 按页签族拆分」两刀走，本轮未动结构
- **版切首跑长尾观察关闭（rf-980）**：两次版切首跑「明细装配与建议」分别 0.544s、0.948s（同版本后续 med 0.48~0.56s），连续两次不复现；92 个样本显示该阶段长尾散见于多个版本且与版切无关，判为阶段偶发、非版本切换引入，台账按判据关闭
- **缓存命中的费用与标记按本次裁清（rf-998）**：`_usage_delta` 只对顶层按币种做差，逐模块 `costs` 整字典照搬、`cached` 标记直接沿用会话累计——同一会话第二份报告整块命中缓存时，明细仍带上一份的模块费用（实测虚高到 CNY 0.061，本次真实花费 CNY 0.0119），汇总表/用量页签同源一起失真；真跑的模块又因标记粘着继续显示「使用缓存」。现在逐模块费用按币种做差，`cached` 按「本次无 token 增量」判定，`record_per_module` 在真调用时翻回 False。回归 1 例；**历史台账同步清洗**（`data/state/perf_history.jsonl`，原文件备份为 `.bak-20261031-010242`）：13 条不一致记录按该次 `cost_by_currency` 真实花费重分配、38 条本就一致的保留原记账、59 条早于费用统计的只刷 `cached` 口径；清洗后「逐模块费用和 vs 该次真实花费」不一致记录 0 条
- **写盘相位耗时异常（rf-997，环境侧关闭）**：2026-10-30T23:04 一次运行 HTML 生成 18.1s / Excel 生成 10.6s（同口径中位 0.2 / 0.3s）。当日两次空闲复跑（23:35、次日 00:52）分别 0.03/0.23s 与 0.03/0.23s 连续不复现；宿主 I/O 探针正常（顺序写 2905 MB/s、单次 905K 落盘 1.1ms），产物尺寸与历史一致，判为瞬时宿主负载、非代码缺陷，台账按判据关闭。

### 变更

- **并发治理：进程级预算 + 4 处热点配置化（rf-1019 / rf-1020）**：新增 `core/concurrency.GOVERNOR`，把「各池各自钳位」补成「逐池 + 进程级」两层上界——参与池建池时从 `batch.max_total_workers`（再按核数钳）的共享预算分配，不足缩到至少 1 并 WARNING，不抢占已运行池；预算/峰值/缩容次数写入 `perf_history` 的 `counters.concurrency_*`，每次报告开头打一条预算 INFO。同时把实时取价 8、基金风格 8、风格因子 6/4、指数历史 5 四处硬编码并发改为配置项（默认值 = 原值，零行为变化）。各模块打磨过的取值一律保留，弱机器用配置下调。
- **性能细分补充（rf-1016）**：数据准备阶段把「风格与因子」拆成 `因子暴露` / `行业 Beta` / `相关性矩阵` 三个子项，旧键在 perf 历史读取侧按别名单列「旧·合并段」（不与新子项混算）；requirements / technical / scripts-reference 三处子项清单同步。
- **诊断盲区复核（rf-1014 / rf-1015）**：`llm_settings.json` 读取失败日志已含异常类型与路径（补回归用例锁死）；退役配置键告警随兼容层移除后不再出现，登记收敛。
- **跨层文案单源（rf-1010）**：60 小时变更自查出的三类重复文案收敛到单源——TUI「本次改动 N 项」页脚改为 `switch_panel.change_footer(count)`；调仓输入持仓不可读提示收敛为 `whatif_operations.WHATIF_BASE/TARGET_HOLDINGS_UNREADABLE`；日志/健康历史读取失败提示收敛为 `core/log_reader.LOG_READ_FAILED_MESSAGE` / `core/perf.HEALTH_HISTORY_READ_FAILED_MESSAGE`，Web 侧措辞随之与 CLI/TUI 统一。`test_channel_layering` 补 3 例契约，`technical.md` 单源清单同步登记。
- **本轮变更自检（rf-1008）**：把同一「相对日期」助手收敛到 `src/test/_relative_dates.py` 单源（原 6 个测试文件各写一份 `_d`/`_day`/`_recent_ts`），删 1 处未使用导入，修正 2 处「行为改了文案没改」（校准工具仍打印「已补 legacy 标注」、紧凑化用例 docstring 仍写「无需补标注」），并为 `test_decision_llm_capture` 5 处 `_parse_table_row()` 结果补非 None 断言；顺带给 `history_snapshot`/`whatif_writer` 的目录创建异常带上目标路径

- **旧形态兼容层清理（rf-1007）**：按「不兼容旧数据文件/旧缓存/旧配置项/旧内部 API」政策清掉 8 处遗留兼容——去重锚点无指纹旧行由「补 legacy 标注保留」改为**直接丢弃**（`unattributed` 统计语义同步为丢弃数，校准工具打印文案随之调整）；快照时间戳只认 `YYYYMMDDTHHMMSS`（删 ISO 等 3 种旧形态）；LLM 内容不再对纯文本按 `\n\n` 兜底分段（只认块级 HTML）；JS 资产只内嵌、不再向输出目录产松散副本（`_copy_js_assets` 与 `html_writer`/`whatif_writer` 两处调用删除）；删 `reader._EXPECTED_HEADER`（零引用死别名）与 `reader._TRADE_HEADER`（内部别名，直接用 `TRADE_HEADER`）、`fund_manager._request_fund_html`（无调用方的旧 API 壳）；改写指向已删模块的「orchestrator.py 兼容入口」标题。同步校正 4 个锁定旧形态的用例并给 prosperity「旧 dict benchmarks」用例改名。核查确认**无需改动**：旧缓存文件（版本号入文件名、不读旧版本）、旧配置项（未知键只告警、无迁移回填）、持仓表头（仅容忍尾部多余列）

- **时间炸弹探测与守卫常驻（rf-1002 / rf-1003 配套）**：`check-test-redundancy.py` 增第 9 类 I「账本日期写死绝对日期」——静态 AST 检查账本写入/裁剪类调用（`append_signals`/`append_decision`/`register_deterministic_signals`/`prune_jsonl_by_age` …）的 `report_date`/`settle_date`/`date` 实参，写死「当前年 ±2 年」内绝对日期即 finding（含经模块级常量转手；远过去锚点如 `2020-01-02` 不报），随 pre-commit 钩子与 CI `guards` 一起兜底；另新增 `probe-date-bombs.py`（probe- 探测类，**不入门禁**）做全域经验筛查：把候选测试文件里的绝对日期整体回移 N 年后逐个跑 pytest，失败即 rot-suspect，改写前备份 + `finally`/`atexit` 双兜底还原 + sha256 校验、脏文件默认跳过。测试：守卫 6 例 + 探测脚本 7 例（含真实子进程还原校验）。**全量筛查**：`--all` 扫出 48 个 rot-suspect，账本族 5 文件已修完（含 `register_action_decisions` / `register_llm_decisions` 两个写入包装层补入守卫管辖）；余量作为 rf-1004 持续监控项留档——三种自动化重定基策略（锚点当天−30d / 当天 / 周对齐）分别只通过 4 / 0 / 2 个文件，证明批量改写不安全，须逐文件人工判读

- **设计护栏 W 级清零**（rf-995 / rf-996）：模板与工作台 CSS 的间距、字号字面量全部吸附到 DESIGN.md 契约阶梯——间距 254 处（阶外 6/10/14/18/20 与零星值 → 4/8/12/16/24/32，等距取小档）、字号 8 处 `0.95rem`（15.2px）→ `1rem`（16px）；三处语义特例单独收敛：报告侧栏让位与栏宽的重复魔术数 `220px` 提取为 `--toc-width` token（顺带消除两处同值漂移风险）、`.sr-only` 的 `margin: -1px` 改 `0`（裁剪 hack 不依赖该值）、汇总片内联 `margin: -2px 0 6px` 改 `0 0 8px`。护栏观察项归零（裸色值 0 / 圆角 0 / 内联色值 0 / 字号 0 / 间距 0）；README 六张配图按新样式重出；whatif 关态零改动基线哈希按评审记录更新，宽屏让位用例改为断言 token 单源。

## 归档

- [`archived_changelog.0.16.x.md`](../archive/v0.16.x/archived_changelog.0.16.x.md) — v0.16.0 ~ v0.16.14（2026-10-25 ~ 2026-10-30）
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
