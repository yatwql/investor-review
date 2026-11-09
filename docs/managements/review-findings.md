# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.17.7-dev
> **编号源**：`rf-next = 1103`（新增问题提出后更新为 +1；已用最大 rf-1102，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
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

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P3 — 持续监控：兼容残留

> **本节性质**：这是**已核销的盘点基线**，不是待办清单。下方表格为空 = 本轮没有兼容残留需要处理。
> 兼容面的处置总纲（不保留跳版本兼容、未登记键不生效）归 `technical.md` §6.1 与附录 I，本文件只留盘点结论，不重复维护口径。

入选标准：需先确认数据契约再动，当前不影响行为正确性。

**盘点口径**（怎么盘、什么才算问题，下次盘点照这个执行）：逐类比对「旧配置项 / 旧配置文件 / 旧数据文件 / 旧数据文件结构 / 旧缓存结构 / 旧缓存文件 / 旧内部 API」；只有「旧版本产物能让当前版本**行为不正确**」才算本类待办，仅仅「旧文件还能读」不算。

**本轮结论**（七类均无兼容面，故下表为空）——逐类依据：`config.json` / `llm_settings.json` / `llm_providers.json` / `logger.json` / `llm_pricing_ref.json` 一律用 `schema_version`（或 `version`）硬闸门，不符即**拒绝加载并提示重新生成**，无静默迁移分支；`features.json` 无名称级兼容（无旧文件名回退）；缓存读取路径声明「不保留旧缓存文件的兼容」（`cache/_io.py`：损坏即删）；`schemas/replay_schedule.py` 对旧版本规则序列**按未命中丢弃**；`cninfo`/`_api_responses` 等上游返回形状容错属**第三方变体**（三分归属与逐处判据见 `technical.md` §9.2）。

| # | 问题 | 修复方向 |
| --- | --- | --- |

| # | 问题 | 修复方向 |
| --- | --- | --- |

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线即登记。下表为**存量监控清单**（不占用 rf 编号，拆分后删除对应行；条数即表内行数，全在可选优化区间，无红线违规；登记行数与实测的一致性由 `check-file-length.py` 断言）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/test/unit/scripts/test_release_tool_gate.py` 1147 行（测试登记线 900 / 红线 1200） | 按域再拆：`refresh` 编排一组、`publish` 一组独立成文件；拆分前先确认不放宽断言 |
| `src/test/conftest.py` 1185 行（测试登记线 900） | fixture 族按域下沉（行情/LLM/网络/持久化各一模块），conftest 只留 autouse 装配与 marker 注册 |
| `src/python/llm/generators_orchestrator.py` 843 行（主程序登记线 700） | 生成编排与共享钩子按模块族再分；预检键/指纹段可下沉 `generators_orchestrator_cache.py` |
| `src/python/report/decision_basis.py` 962 行（主程序登记线 700，红线 1000） | 六段块装配（信号/可信度/风险预算/纪律/结算+按视界表现/约束）仍在单模块；拆分方向：结算批表与按视界表现聚合（`build_settlement_summary`＋`build_performance`＋`_mean`/`_tone_*` 色彩助手）可整体下沉 `decision_basis_settlement.py`（只读账本、无跨段依赖，预计 −180 行）；信号清单与区分度登记（`_build_signal_rows`＋`BACKTEST_CONCLUSIONS`）可再下沉一簇 |
| `src/python/llm/skeleton.py` 847 行（主程序登记线 700） | 模板数据与渲染逻辑可下沉 `llm/skeleton_*`（骨架模板 / 占位渲染 / 缓存归因 / 回写四簇并存） |
| `src/python/cli/_handlers.py` 852 行（主程序登记线 700） | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄壳 |
| `src/python/tui/handlers_holdings.py` 825 行（红线 1000） | 面板流程与输入采集高度耦合（共用 `_Session`），拆分收益低于回归面；再涨 ~150 行则按「面板流程 / 输入采集」两段拆，并把 `_market_data` 的会话内记忆一并做进去 |
| `src/python/fetcher/financial_report.py` 719 行（主程序登记线 700） | 刚过线：再涨则按「索引 / 正文 / 全文定位」三阶下沉（负缓存样板统一在 `cache/_negative.py`） |
| `src/static/tmpl/report_template.html` 277 行（样式已抽到 `partials/_report_styles.html` 750 行，各自单一关注点，均未触 1000 行） | 主模板只剩骨架 + include；再增长则按「首页/持仓/LLM/附录」四段拆 partial |
| `src/static/tmpl/whatif_template.html` 543 行（**不在行数守护域内**：`check-file-length` 只扫 `.py`） | 样式已抽到 `partials/_whatif_styles.html`；剩余为标记与图表配置，暂无需拆分 |

## 已解决问题

### 开发期已修复（0.17.7-dev）

> 本表为本开发周期已修条目的**摘要行**（详情见 `changelog.md` 对应段）；发布时由 `release.py prepare` 的 archive 步原表搬入版本归档并在此留占位。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-1088** | `core/holdings_editor.py::ambiguous_price_kind` 内联 ``len(raw) == 6 and raw.startswith("00")`` 做代码形态/重叠区判定，属代码类型判定分散（违反「代码类型判定中心化」约束） | 改用 ``code_utils`` 的 ``is_six_digit_code`` + ``is_otc_code_overlap``；补「非 6 位码恒 False」形态用例 |
| **rf-1089** | `llm/pricing.py::_is_holiday` 经 `trading_calendar._is_trading_day` 判节假日，日历缓存缺失时会真实取数（akshare）；撤离线声明后无日历缓存的机器上整批 LLM 缓存用例被网络守卫拦成硬失败 | 改读 `cached_trading_days()`（只读缓存、绝不取数），无缓存按「非节假日」降级；补「只读缓存 / 无缓存降级 / 周末不查日历 / 异常降级」4 例回归 |
| **rf-1090** | `llm/strategy.py::_apply_cost_first` 读 `input_price`/`output_price`（计价表实际键为 `input`/`output`），所有模型得分恒 `inf`，`cost_first` 策略静默退化为「保持原序」；旧用例用同款假键名把错哄住了 | 改读真实键 + 模型名小写归一，缺价/子表按未知排末尾；用例改用真实键名，并新增「以真实定价表为真值」的顺序断言 |
| **rf-1091** | 类型债清理：`api_base._attempt` 的 `result` 可能未绑定（`PacingGate.__exit__` 声明为 `bool` 即可被推断为吞异常）、`analysis/scenario.py` CI 区间值可能为 None 仍参与乘法、`analysis/rebalance.py`/`trade_discipline.py` 配置段可能为 None 却被 `dict()`/下标、`tui_keys` 的 msvcrt 平台桩与 `fd` 可空、`holding_change_review` 方向值 `get` 重载不匹配 | 逐个按「值判空 + 显式类型收窄」修：`__exit__` 改 `-> None`、`_attempt` 结果与返回下沉进 `with`、CI/配置段先 `isinstance` 收窄、msvcrt 走 `getattr` 降级、方向值 `isinstance(int)` 判定；无行为变更，均由既有用例与静态检查复核 |
| **rf-1092** | `src/python` 余 34 处 pyright error（现场 pyright 实测 83 处，含 48 处 `reportArgumentType`），且类型检查未进门禁——只能靠偶发人工扫描发现，其中已证明混有真实缺陷 | 分簇清零到 **0 error**：① 可空值簇（`reportOptional*` / `possiblyUnbound`）逐点判空收窄；② 数值归一统一走 `core.num_utils` （`safe_num` / `finite_or`），谓词升级 `TypeGuard`（免二次判空）；③ 平台桩走 `getattr` 降级（`msvcrt`）、`PacingGate.__exit__` 改 `-> None`、`cache._store` 用 `builtin_set` 别名避开同名遮蔽；④ 新增 `scripts/check-types.py`（退出码 0/1 环境缺失/2）入 pre-commit 与 CI `guards`，规则基线落 `pyproject.toml [tool.pyright]`（受检域 `src/python`，`src/test` 刻意不入域）；⑤ 补 14 例脚本测试。验收：`check-types.py --ci` 通过（`src/python` 零 ERROR），CI `guards` 变绿 |
| **rf-1094** | **陈旧离线声明**：66 个测试文件声明 `offline_external_sources`（撤掉声明后该文件全绿），说明用例早已不依赖任何外部数据——离线桩把「本可能漏 mock 的真实外部访问」遮住，也让这些文件对 provider 行为变化失去敏感度（48h 审计时 `test_cache_matrix` 正是同类问题导致整批红） | 逐文件试跑法（撤声明 → 单跑该文件 → 全绿即陈旧）撤掉 **66 处**（llm 12 + 全库 54），保留 61 处确有附带依赖（交易日历/行情/健康探针）的声明；撤后 dev-verify 9290 通过 0 失败 |
| **rf-1093** | `scripts/` 顶层脚本余 50 处 pyright error（流对象 `sys.stdout.reconfigure`、`ctypes.windll`/`msvcrt` 平台桩、动态 target 的 `build_parser`、AST 节点 `lineno`、`check-doc-traces` 分支内赋值被判成可能未绑定等），故 `check-types` 守护域只覆盖 `src/python` | 逐簇清零到 **0 error**（流对象用 `cast(Any, …)` 取 `reconfigure`；平台桩 `getattr` 降级；动态模块 `build_parser` 判空；AST 用 `getattr(node, "lineno", 0)`；分支赋值先落默认值；`socket` 替换改 `setattr`、`xml` 数值属性收口到 `_num_attr` 助手），并把 `scripts` 加回 `[tool.pyright] include` 与 `check-types` 默认受检路径——守护域从此 = 产品代码 + 入口/守护脚本 |
| **rf-1095** | `test-reports/archives/` 无轮转机制，实测 31 份归档 ≈ 17G（本地磁盘与 CI runner 都会被吃满） | 新增 `scripts/_test_runner/retention.py::prune_archives`（次数闸门 keep 最近 N 次 + 体积闸门 cap MiB，两侧均可关）、`test-runner.py` 启动前静默清理并新增 `--keep-runs` / `--archive-cap-mb`；删除失败只告警不计入已删、空日期层回收；补 7 例用例（次数/体积/同日排序/两闸门可关/缺目录/删除失败） |
| **rf-1096** | **时间相关缓存用例在盘中必红**：11 个 LLM 缓存用例断言「同产出第二次命中缓存」，但未钉死行情口径桶——该桶随钟面变化（盘中档禁止复用价格相关模块），故 09:00–15:00 跑必失败、收盘后转绿；实测 09:30 跑 dev-verify 报 38 处失败，环境一变即误判为回归 | 每个缓存断言文件加 autouse fixture `_freeze_market_bucket_for_cache_asserts`（统一 `freeze_market_bucket` 钉收盘档，用例内显式冻结仍可覆盖），llm 全档 1679 通过；与 `test_module_fingerprint` 的既有做法同一口径 |
| **rf-1097** | **门禁链路越来越慢**（实测每次提交 ≈61.5s：钩子 13.5s + `dev-verify` 45.5s），且 `--parallel high` 无增益（16 worker 仍 45.5s → 非 CPU 瓶颈）：① `check-types` 全量 pyright 13.7s/次；② `dev-verify` 内有 5 个「真实仓库守护冒烟」用例与钩子对同一棵树重复跑同一守护（≈20s）；③ 若干 report 用例套着真实重试退避等待（单文件 22s） | 三层提速且不降覆盖：① `check-types --changed` 只查变更文件（14s → 0.5~2s；变更 >25 个或取不到 git 清单时回落全量），钩子用快车道，**CI guards 与 P2 恒全量**；② 真实仓库冒烟加 `real_repo` 标记并从 `dev-verify` 排除（`verify`/CI 仍全跑）；③ 按「加离线桩前后计时」重新校准离线声明，为 4 个真受退避等待拖慢的文件恢复声明。实测 `dev-verify` 45.5s → 33.2s，钩子 13.5s → ≈5s |
| **rf-1098** | 并行档位缺少可固定入口与上限：worker = 核数 × 系数且 medium 无上限（32 核会开到 16，实测偏慢），慢机器只能每次命令行带参数，并行度也不可解释（输出只报 worker 数） | medium 封顶 8、新增 `TEST_RUNNER_PARALLEL` 环境变量（优先级 CLI > 环境 > 缺省）、worker 少于核数时提示可提升方式；补 9 例用例（级别优先级/非法值回落/封顶/high 不封顶/low 下限）；scripts-reference 补选择建议 |
| **rf-1099** | **Windows 上 `standard`/`unit` 档 720s 超时**：`tui_keys._get_key_windows()` 无 `isatty` 前置判定（Linux 分支有），非交互 stdin（pytest/管道/重定向）下 `msvcrt.getch()` 会一直阻塞到有按键，整档测试跑不完；`dev-verify` 不含 `unit_ui` 故本地与 CI（Linux）结构性看不见 | 把 `isatty` 判定提到 `import msvcrt` 之前（与 Linux 分支同口径，非 Windows 也可被测试覆盖），非 tty 直接返回 `KEY_UNKNOWN`；Windows 分支既有用例补 tty 前提，新增「非 tty 不等键」回归 |
| **rf-1100** | 整档超时（720s）只给出一句「测试超时」，不指明**哪个用例**卡住——排障只能靠反复二分或 `-v` 刷屏；慢机器（Windows）上「卡住」与「真慢」也无法区分 | 新增可选单用例看门狗：`TEST_RUNNER_PER_TEST_TIMEOUT=<秒>` 时给 pytest 传 `--timeout / --timeout-method=thread`（`pytest-timeout` 入 `.[test]` 可选依赖，**未设变量不启用**，避免慢机误杀），超时用例即被点名并打印堆栈；补 3 例用例（默认不启用 / 设值启用 / 空白忽略）；scripts-reference 补「整档超时怎么定位」 |
| **rf-1101** | **Windows 上收集失败**：`test_live_status_edge.py` 在模块顶层 `import pty` / `import termios`（POSIX 专属），Windows 收集期直接报 `ERROR collecting …`，把整档 `unit`/`regression` 拖成错误——CI 与本地均 Linux，结构性看不见 | 改用 `pytest.importorskip(...)` 前置（本平台缺失即整模块跳过，收集期不产生错误）；新增跨平台 import 守卫用例（AST 扫 `src/test` 模块级 POSIX 专属导入，违规即红；try 包裹/importorskip/函数体内三类合法写法不误报） |
| **rf-1102** | pytest 非测试失败（退出码 2/3/4/5）在 runner 里只显示成「0 passed, 0 failed (0.0s)」——看不出是用法错误（缺插件 / 环境变量残留）还是未收集到用例，排障只能靠手工重跑 pytest | 按退出码给出可执行提示（4=用法错误：常见缺 pytest-timeout 或 `TEST_RUNNER_*` 残留；5=未收集到用例：marker 与测试树不匹配；2=中断；3=内部错误），并回放输出末 8 行；补 2 例用例 |

### 归档档案
- [`archived_review-findings.0.17.x.md`](../archive/v0.17.x/archived_review-findings.0.17.x.md) — v0.17.x（2026-11-04 ~ 2026-11-08）
- [`archived_review-findings.0.16.x.md`](../archive/v0.16.x/archived_review-findings.0.16.x.md) — v0.16.x（2026-10-25 ~ 2026-11-03）
- [`archived_review-findings.0.15.x.md`](../archive/v0.15.x/archived_review-findings.0.15.x.md) — v0.15.x（2026-10-24 ~ 2026-10-25）
- [`archived_review-findings.0.14.x.md`](../archive/v0.14.x/archived_review-findings.0.14.x.md) — v0.14.x（2026-10-21 ~ 2026-10-23）
- [`archived_review-findings.0.13.x.md`](../archive/v0.13.x/archived_review-findings.0.13.x.md) — v0.13.x（2026-10-13 ~ 2026-10-21）
- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md) — v0.12.x（2026-10-03 ~ 2026-10-13）
- [`archived_review-findings.0.11.x.md`](../archive/v0.11.x/archived_review-findings.0.11.x.md) — v0.11.x（2026-09-15 ~ 2026-10-02）
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
