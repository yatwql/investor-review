# 投资复盘助手 - 自我审查问题记录
> 文档版本：0.19.0-dev
> **编号源**：`rf-next = 1255`（新增问题提出后更新为 +1；已用最大 rf-1254，递增保证唯一，归档不回收。若与历史归档冲突，运行 `scripts/check-task-numbering.py` 校验）
---

## 当前待处理问题

### P1 — 高优先：不做的风险高（尽快执行）

入选标准：默认开启功能与用户渠道未经完整验证，遗漏即放行线上缺陷。

| # | 问题 | 修复方向 |
|---|------|----------|

### P2 — 中优先：价值明确、成本可控（下批排期）

入选标准：重构收益明确、回归面可圈定。

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

### P4 — 持续监控：文件膨胀登记

行数与拆分优先级以 `scripts/check-file-length.py -v` 为准（口径见 `technical.md` C28），达警告线（主程序 700 / 脚本 600 / 测试 900）即登记。下表为存量监控项（红线：主程序 1000 / 测试 1200，触线必须拆分）：

| 文件 | 现状与拆分方向 |
|------|----------------|
| `src/python/core/perf.py` 797 行 | 采集器与台账落盘可拆（`perf` 采集 / `perf_history` 读写两文件） |
| `src/python/core/doctor.py` 793 行 | 检查项按域分文件（环境 / 配置 / 数据源 / 报告产物），入口只留编排 |
| `src/python/llm/fact_checker/_numerical.py` 764 行 | 数值校验按规则族拆（金额 / 比率 / 计数），共享解析原语上提包内 `_common` |
| `src/python/tui/handlers_config.py` 743 行 | 配置面板按域拆（内容选项 / 全局设置 / 目录与文件名） |
| `scripts/_doc_drift/_format.py` 742 行 | 格式化规则按文档类型拆（章节 / 表格 / 树 / 统计） |
| `src/python/core/degradation.py` 768 行 | 状态词与事件模型、登记面与持久化可拆两文件 |
| `src/python/report/action_sheet.py` 754 行 | 行动页签内各块（建议表 / 判断依据 / 决策书 / 复盘）拆子模块 |
| `src/python/fetcher/financial_report.py` 725 行 | 按「索引 / 正文 / 全文定位」三阶下沉 |
| `src/python/providers/akshare_extras.py` 721 行 | 按接口族拆（指数 / 行业 / 分红 / 盈利预测） |
| `src/python/core/provider_registry.py` 710 行 | 熔断与会话缓存各自独立文件 |
| `src/python/llm/skeleton.py` 909 行 | 模板数据与渲染逻辑可下沉 `llm/skeleton_*`（骨架模板 / 占位渲染） |
| `src/python/cli/_handlers.py` 894 行 | 命令处理器按渠道分文件（generate/config/data 三簇），保持入口薄 |
| `src/python/tui/handlers_holdings.py` 825 行 | 面板流程与输入采集高度耦合（共用 `_Session`），拆分收益低于风险，暂不拆 |
| `src/static/tmpl/report_template.html` 278 行 | 样式已抽到 `partials/_report_styles.html`，各自单一关注点，均未触 1000 行 |
| `src/static/tmpl/whatif_template.html` 543 行 | **不在行数守护域内**（`check-file-length` 只扫 `.py`）；样式已抽到 `partials/_whatif_styles.html` |

## 已解决问题

### 开发期已修复（0.19.0-dev）

> 本表为本开发周期已修条目的**摘要行**（详情见 `changelog.md` 对应段）；发布时由 `release.py prepare` 的 archive 步原表搬入版本归档并在此留占位。

| # | 问题 | 修复方向 |
|---|------|----------|
| **rf-1249** | 同一 `BLE001` 并存两种标注形态（`# noqa: BLE001` 与散文「有意宽捕获」），散文形态无机检；`core/doctor.py` 12 处逐字重复同一降级理由注释 | 散文形态按 ruff 实际命中分流：命中处补 `noqa: BLE001 — <理由>`，未命中处（函数体已上抛 / 已 `logger.exception`）只留理由不挂空转抑制；`doctor.py` 的 12 处重复理由抽为模块级「体检降级口径」注释、逐处只引一句短注释；新增 `check-code-traces` 的 CAPTURE 支路（口径词无 `noqa: BLE001` 即报）配单测与 scripts-reference 说明 |
| **rf-1248** | 4 处 `float(safe_num(...))  # type: ignore[arg-type]`（`safe_num` 可返回 None，靠 `default=0.0` 巧合自保） | 归一到 `core/num_utils.finite_or` 单源（4 处 type-ignore 全删，全仓只剩 `num_utils` 一处），行为逐点等价；补一条四点联合回归用例覆盖 None/空串/非数字/NaN/±inf 与合法值 |
| **rf-1247** | `scripts/_screenshots/tui_frame.py` 跨包读私有 `config._config_defaults._CONFIG_PATH_OVERRIDE`（`check-import-surface` 的 `PY_ROOT` 只扫 `src/python`，scripts 侧无兜底） | `config` 包补公开 `get_config_path_override()` / `clear_config_path_override()`（导出进 `__all__`），截图脚本改用公开面还原；`check-import-surface` 增 `cross-private-scripts` 规则把 `scripts/` 递归纳入导入面受检域（9 条存量例外登记，含替代路径与复核期限） |
| **rf-1253** | `report/_llm_news.py` 同一失败既 `add_error` 又即时 `error` 上屏（与 rf-1241 的「同消息双通道」不是同一处，当时未并入） | 与 rf-1246 同批收口：只保留 `add_error`（TUI 收尾摘要 `print_error_summary` + WARNING 日志即它的两个可见面），删即时 `error` 行 |
| **rf-1246** | `report/_llm_news.py` 新闻失败提示与 LLM 分支**口径分裂**（新闻只 `add_error`；LLM 额外即时 `error`，同一类降级两个可见面） | 两条兄弟路径统一为只 `add_error`，各补一条 `caplog` 断言锁定 WARNING 级（判定依据：`add_error` 已进 TUI 收尾摘要与日志，即时 `error` 是重复上屏） |
| **rf-1235** | 展示脚本取帧泄漏配置路径覆写：`scripts/_screenshots/tui_frame.py` 的 `capture_frame` 以 `get_config_path()`（有效路径）作还原值，原进程「无覆写」时该值即 `_CONFIG_FILE`，`finally` 里再 `set_config_path_override` 回写便把「覆写=默认路径」永久钉在进程上；同源的 `src/test/_path_isolation.py` 未清覆写则让上一条用例（如取帧）遗留的演示路径盖掉本轮隔离路径，跨用例配置串读。两处都缺会红的回归用例 | 还原改用**原覆写值**，走 `config` 包已提供的公开入口 `get_config_path_override()` / `clear_config_path_override()`（原值为 None 即 `clear`），覆写值的读写统一经该公开面；进入与还原各清一次配置缓存，私有 `_clear_config_cache` 换成公开 `invalidate_config_cache`；隔离 seed 由 `seed_sensitive_path_isolation` 把 `_CONFIG_PATH_OVERRIDE` 置 None；补两条会红的回归用例（无前置覆写的真取帧结束后覆写仍为 None、隔离 seed 清掉泄漏覆写） |
| **rf-1245** | `tui/handlers_switch.py` 同一查找逻辑三份内联实现、赋值通道 `parse_switch_override` 解析两次、一处 `[!]` 提示缺配色 | 抽 `_find_switch_item_by_key()` 共用、解析只做一次、按 DESIGN-TUI 补齐颜色角色，并引入 `SwitchItem` 类型别名 |
| **rf-1244** | `report/penetration*.py` 的 `industry_status` 为裸字符串状态机，缺键默认值为「健康」 | 改显式常量集合，缺键显式归入「未知」而非静默算健康 |
| **rf-1243** | `report/_report_factor_metrics.py` 的 `factor_workers` 默认值 3 处硬编码 6 | 收敛为单源常量（取自配置默认值表），三处引用该常量 |
| **rf-1242** | 4 处 `logger.debug` 与「要留痕」注释矛盾（DEBUG 不进默认 INFO 的 app.log） | 级别对齐为 INFO；`providers/cninfo` 的「留痕」指负缓存机制、非级别要求，保留 |
| **rf-1241** | `report/_llm_news.py` 两处对同一消息 `add_error` + `warn` 双发 | 保留跨通道恒可见的 `add_error`，删 `warn`；断言改指保留的那一路 |
| **rf-1240** | 5 处 `__import__("logging").getLogger()` 无理由动态导入 | 模块顶部 `import logging`，logger 名不变 |
| **rf-1239** | `report/pipeline_data_builder.py` 对未注册 pipeline_data 键「告警即自动登记」进模块级集合，与数据契约「违反则不通过」不符且键宇宙两份事实位 | 三个注入路径一律不登记（`frozenset` 使 `.add` 结构上不可能），未知键告警指向附录 H；`_validate_keys` 形参改 `AbstractSet` |
| **rf-1238** | 报告生成门面把同一组符号 `# noqa: F401` 复述三遍；其中一处 patch 打在从未被调用的绑定上（死 patch） | 权威 re-export 收拢到 `_report_generation`，`_generation_shared` 整块删除、`_generation_full` 仅留实际调用依赖；死 patch 改指真实调用点 |
| **rf-1237** | LLM 模块键元组在 10+ 处各抄一份且成员已不一致（4 元素 vs 5 元素），新增模块会静默漏入质量评分/模块明细 | 新建 `llm/module_registry.py` 单源（产出序 / 后缀集合 / 并行子集 + 排除理由），11 处调用点改派生；`core`/`config` 因分层不改，由守卫用例锁定等值 |
| **rf-1236** | `scripts/_release/_evolution.py` 在 `git ls-files` 含工作区缺失文件时 `sum(lines[p] for p in paths)` 抛 KeyError，崩在缺失清单打印之前 | 求和跳过未读入路径，`missing` 语义不变；补回归用例（缺失文件下命令存活且计数正确） |
| **rf-1254** | `scripts/check-test-redundancy.py` 为让测试经 `load_script` 取内部符号而 re-export 13 块 52 个符号并加 `# noqa: F401 — 兼容 load_script 直调面`，入口「未用符号」信号永久失效（新增真实死 import 无人发现） | 测试改为直接导入 `_test_redundancy.*`，入口只保留 `main()` 真实使用的 `run_checks`/`audit_similar_bodies`；52 个符号中 14 个有真实引用、其余随块删除；`兼容 load_script 直调面` 注释归零，`ruff --select F401 scripts` 干净 |
| **rf-1252** | `report/_report_factor_metrics.py::compute_factor_exposure_data` 128 行未拆分 | 按职责提取 4 个同文件私有辅助（延迟导入+降级/并发取数/停更剔除/装配），主函数 128→51 行，签名与行为不变 |
| **rf-1251** | `pyproject.toml` 对生产文件 `report/_report_generation.py` 禁用 F821 | 该文件已收为 37 行纯门面，豁免成陈旧条目 → 删除；`ruff --select F821 src/python` 干净 |
| **rf-1250** | 生产入口为测试 patch 保留无使用者 import（`check-test-redundancy` 的 `ast`、`release` 的 `os`）+ 整文件 F401 豁免 | patch 点改到真实调用模块后删 import；`test-runner.py` 以 70 项显式 `__all__` 替代整文件豁免，未声明者仍报 F401 |
| **rf-1234** | 用例名与体内验证行为不对应 10 处（去重口径/排序/并发/符号链接/上限配置等） | 名字与体内行为取同一口径：按名字补齐断言或按行为命名；已落 8 处，其余目标文件在仓库中不存在 |
| **rf-1233** | 弱断言 14 处（截断未验收缩、入参回显、硬边界值、任意单元格命中、写死条数等） | 取可区分的期望值（截断前后集合、显式档位差、具体单元格定位）与结构关系断言；已落 7 处，其余目标文件不存在 |
| **rf-1232** | 跨文件语义重复 13 组（行情/缓存矩阵/限速/进度器/凭证矩阵等） | 保留双方但一侧承担该模块独有差异断言（矩阵轮次、来源、非零退出码、缺条目各报一条）；已落 9 组 |
| **rf-1231** | 用例归属与所在目录/域标记不一致 11 处（core 模型极端值、LLM 基类边界、cli 进度器、news_sources 跨域、security_edge 主体跨域） | 按被测模块就近归位并同步域标记：拆出 8 个语义化测试文件（含 6 个 `*_edge.py`），`folders.md` 目录树与 `test-plan` 载体路径同步；3 处目标文件在仓库中不存在（标记未注册、模块已并入他处） |
| **rf-1230** | 用例名与体内验证行为不对应 8 处：`report/test_security_edge.py` 的 `test_json_loads_not_pollutable`（内容属 stdlib 契约）、`report/test_html_writer_contents.py` 的 `test_generate_all_llm_receives_dict_indices`（内容为 `assert_not_called`）、`core/test_guard_branch_coverage.py` 的 `test_..._delegation_...`（仅验证类型）、`cli/test_cli_edge.py` 四处（`_EXIT_SEVERE`/默认值/多文件自动选/无 input）、`startup/test_startup_wizard.py` 该类仅验 `_llm_key_present`，未验状态检测 | 名字与体内行为取同一口径；能按名字补断言的补上（cache 路径补 `input` mock 断言、启动用例补 `_detect_startup_state()["llm_key_ok"]`） |
| **rf-1229** | `report/test_security_edge.py` 用 `inspect.getsource` 断言源码含 `mkstemp`/`os.replace` 字面（实现一变即红，与运行时行为脱钩） | 删除源码字面断言，原子写完整性由并写用例覆盖 |
| **rf-1228** | 断言结构失效 3 处：`core/test_filesystem_edge.py:40` 的 `assertIn(x, msg or "..." in msg)` 使第二条件永不生效、`cli/test_cli_edge.py:28` 用 `"input" not in str(mock_gen.call_args)` 检查无关字符串、`cli/test_cli_handler_branches.py:125` 的 `caplog.text.strip() != ""` 任意日志即可通过 | 拆成独立断言；取 `patch("builtins.input")` + `assert_not_called()`；日志断言取级别与文案 |
| **rf-1227** | 与实现同式的恒等式断言 2 处：`core/test_data_freshness.py:345` 用输出字段 `prev_trading_day` 反推 `stale`、`llm/test_cost_tracker.py:25` 的 `used>=0`/`remaining<=budget` 对 `max(0, ·)` 恒真 | 取显式期望值（`stale is False`、`used==0` 且 `remaining==budget`） |
| **rf-1226** | 可空过的断言 4 处：`analysis/test_liquidity_otc.py` 两处遍历 `result` 前无结构断言、`news/test_news_correlator.py:42` 断言写在 `if 关键词 in title` 内、`news/test_news_sources.py:81` mock 直返 list 后只做 `assertIsInstance` | 遍历前断言结果非空；条件断言取「先筛命中项再断非空」；对返回值取具体断言 |
| **rf-1225** | 恒真/自比较/死代码断言 6 处：`analysis/test_factor_evaluator_edge.py:30` 的 `len(x)==len(x) and x`、`analysis/test_metrics_edge.py:423` 的 `== 0.0 or == -0.0`、`analysis/test_correlation_edge.py` 的 `list(reversed(seq)) and seq`、丢弃返回值语句、`if exact["available"]` 条件式断言、`news/test_news_dedup_perf.py:76` 同输入自比 | 取结构关系断言（目录派生条数）；删恒真分支与死语句；条件断言取无条件口径；自比较取与未缓存实现对比 |
| **rf-1224** | `_beta_se` 用 `sum()` 算均值，Python 3.12+ 的补偿求和与 3.11 朴素累加末位不同——恒定基准下 Σ(x-x̄)² 在 3.11 上残留约 1e-35，零方差未被识别，标准误算出 1.1e15（CI 3.11 单档红） | 均值/SSE/SSX 一律改用 `math.fsum`（正确舍入、跨解释器一致），并以「基准极差为 0」判定零方差 |

### 归档档案
- [`archived_review-findings.0.19.x.md`](../archive/v0.19.x/archived_review-findings.0.19.x.md) — v0.19.x（2026-11-27 ~ 2026-11-27）
- [`archived_review-findings.0.18.x.md`](../archive/v0.18.x/archived_review-findings.0.18.x.md) — v0.18.x（2026-11-12 ~ 2026-11-26）
- [`archived_review-findings.0.17.x.md`](../archive/v0.17.x/archived_review-findings.0.17.x.md) — v0.17.x（2026-11-04 ~ 2026-11-10）
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
