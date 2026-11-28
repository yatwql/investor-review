# 自审记录归档 — v0.19.x

> 归档时间：2026-11-27（v0.19.0 发布，本系列首批已修复批次并入）；2026-11-27 v0.19.0 本批原表搬运；2026-11-28 v0.19.1 本批原表搬运；2026-11-28 v0.19.2 本批原表搬运
> 原始文件：`docs/managements/review-findings.md`
> 涵盖版本：v0.19.x 已修复项（按发布版号批次，v0.19.0 → ）（含 v0.19.2）
> 归档内容：台账表格经 `release.py prepare` 整块搬运（无损）；表外散文留主台账

---

## 已修复（0.19.0）

> 完整复盘见 `changelog.md` 0.19.0 段；此处为台账原表搬运（无损），本批发布日 2026-11-27。

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

## 已修复（0.19.1）

> 完整复盘见 `changelog.md` 0.19.1 段；此处为台账原表搬运（无损），本批发布日 2026-11-28。

| # | 问题 | 修复方向 |
| --- | --- | --- |
| **rf-1255** | 渲染期数据写入模块级 dict（图表数据与章节可见性经模块级状态传递，同一进程内二次渲染会读到上一轮上下文） | 全部改经 `render()` 的 context 传参；`_ENV.globals` 只保留导入期 fail-closed 设置 |
| **rf-1256** | TUI `[R]` 面板分组标题自带分隔符，再被框架拼接一次后出现双重分隔（版式与设计契约提示三段式不符） | 标题文本去掉自带分隔符，由面板统一拼接 |
| **rf-1257** | 空态文案套用状态色（零数据被染成告警色，与 `DESIGN.md` 空态口径不一致） | 空态取色改走 `data-status` 语义属性（品类色与告警色只在有数据时参与） |
| **rf-1258** | 测试域 `F821`（未定义名）按文件豁免，豁免面盖住了 1 处真实未定义名；引号注解散落 | 取消 per-file-ignore，引号注解统一走 `TYPE_CHECKING` 导入块，清 5 条豁免 |
| **rf-1259** | 事实缓存指纹夹具未显式 `encoding`，CI `portability` 严格档（`PYTHONWARNDEFAULTENCODING=1`）报隐式编码 | 夹具读写补显式 `encoding="utf-8"` |
| **rf-1260** | 变异评测 JSON 汇总得分的测试期望值写死切片总数，新增切片即误红 | 期望值改由切片清单长度派生（结构关系断言） |
| **rf-1261** | 变异评测入口为测试直调面 re-export 内部符号；各守卫脚本的例外表各写一套解析；事实缓存指纹未覆盖全部规则模块（107 小时审计 8 项 P2） | 入口收薄至编排面；例外表协议归一 `scripts/_shared/exceptions.py`；事实缓存指纹覆盖全部规则模块 |

## 已修复（0.19.2）

> 完整复盘见 `changelog.md` 0.19.2 段；此处为台账原表搬运（无损），本批发布日 2026-11-28。

| # | 问题 | 修复方向 |
| --- | --- | --- |
| **rf-1269** | 分层越界存量项：板块分类原语（行业关键词表 + 名称→板块判定）居 `report/penetration.py`，纯计算层 `analysis/`（景气度评分与输入装配）只能反向依赖报告层 | 原语整块下沉 `core/sector.py`（关键词表加载/降级/只读访问/热重载 + `classify_sector`），report 与 analysis 双侧改为消费 core；分层例外表与文档表同步删除 2 行 |
| **rf-1270** | 分层越界存量项：持仓快照存储（保存/加载/列表/清理 + 命名空间隔离）整体居 `report/history_snapshot.py`，`analysis/` 三处与 `web/`、`scripts/` 均为读快照而反向依赖报告层 | 整模块迁至 `core/snapshot_store.py`（只依赖 core 与 schemas，无报告侧耦合），全仓引用改指 core；纯存储用例随模块归位 `unit/core` 并按模块改名；分层例外表与文档表同步删除 3 行 |
| **rf-1271** | 分层越界存量项（7 行）：纯解析/派生原语（费率表模型、三张报表派生、财务指标全文解析、回撤事件下限常量）居 `analysis/`，`fetcher/`、`providers/`、`config/`、`report/` 四处为复用同一口径而反向依赖纯计算层 | 四个纯计算模块整块下沉 `core/`（只依赖 `core`/`schemas`，零上层耦合），全仓引用改指 core；其用例随模块归位 `unit/core`；分层例外表与 `technical.md` 存量例外表各减 7 行；分层守卫用例的示例目标改为仍在 `analysis/` 的模块 |
| **rf-1272** | 分层越界存量项（2 行）：配置层反向依赖 LLM 实现——`config/_llm_providers.py` 写盘后直接调 `llm.pacing.register_policies`，`config/_validation_llm.py` 从 `llm.depth_profile` 取深度档常量（常量真值本就在 `core/constants.py`） | 前者改为「配置只发信号」：写盘递增 `get_providers_revision()` 修订序号，`llm/pacing.py` 惰性装载时按序号变化自行重载（分层单向）；后者直接改从 `core/constants.py` 取常量。分层例外表与存量例外表各减 2 行 |
| **rf-1273** | 分层越界存量项：行业/概念关键词扩展（含取数）居 `report/news_correlation.py`，缓存预热为复用同一口径而反向依赖报告层 | 原语迁入 `fetcher/news.py::expand_industry_keywords`（与新闻聚合同层，取数归取数层）；预热与报告两侧改引 fetcher；纯函数的 5 条用例随迁 `unit/fetcher`；分层例外表与存量例外表各减 1 行 |
| **rf-1274** | 新闻源传输级失败被记成「成功 0 条」（实测华尔街见闻连续两天 DNS 失败仍显示正常）：provider 契约是「失败返回空列表」，聚合层只看返回值无法区分「网络失败」与「源侧确实没有新闻」，健康矩阵与 `get_last_source_status()` 同时失真，provider 还打印「获取成功」 | provider 在传输/解析/鉴权失败分支经 `providers.utils.set_last_reason` 落可读原因；取数包装层（`news_sources._fetch_from_*`）把「空结果 + 有原因」转成 `NewsSourceUnavailable` 抛出，聚合层既有 `except` 分支即登记「失败(<原因>)」；新增 4 条回归用例（含新浪多分类线程内原因回传） |
| **rf-1275** | 财报索引「各源均无该标的」未入负缓存，每轮重探：实测 16 个代码 × 2~4 源全部预期缺失，单轮财报摘要阶段 50.9s（占数据准备 65%）几乎全是纯等待 | 新增负缓存 `report_index_miss_`（6h，注册表 + 数据源文档 + `technical.md` 同源登记）：仅当主备两源都答「无该标的」且**无传输级失败**时写入，传输级失败照旧不入缓存；新增 2 条回归用例（第二轮即命中负缓存、探源次数保持 1 / 传输级失败不入缓存） |
| **rf-1277** | 市值缺失被当成「全亏 -100%」：`fact_checker` 组合收益率用 `sum(market_value)` 算，明细缺 `market_value` 时当 0 市值，得出 -100%，把 LLM 正确的「累计收益率 5%」判为不一致并生成「实际 -100.0%」的自动修正；对应用例 `test_missing_market_value` 只断言 `isinstance(issues, list)`，把该缺陷完全掩盖 | `_calc_portfolio_values` 增「市值全缺失 → 收益率不可知」分支（按 0 记，由下游 `profit_rate < 0.01` 语境门跳过收益类比对）；用例改为断言 `checked == 1 / issues == [] / corrections == []`（回归锁） |
| **rf-1278** | 测试用例年度审计发现四类问题：跨文件或跨类**冗余**（注册表不变式在 `unit/config/test_features.py` 与 `test_feature_registry.py` 双份；`test_financial_indicator_hithink::test_chain_order` 与 `test_financial_indicator::test_chain_registered_with_main_and_fallback` 同断言）、**名实不符**（`test_load_missing_file_returns_none` 实为「列举后文件消失」、`test_today_str_none` 实传空串、`test_none` 语义不明）、**弱断言致无效**（`test_zero_budget_returns_without_blocking` 用快探针导致断言恒过、`run_scope` 两处只断言 `isinstance(dict)`、熔断状态用例只断言 `isinstance(dict)` 未验委派） | 冗余项按「一条不变式一个出处」合并（注册表派生断言归 `test_feature_registry.py`，更强的划分/完整项留 `test_features.py`；链序断言只留描述性命名的那条）；名实不符三项改名并补语义注释；弱断言改断可观测结果（零预算用挂起探针断言「超时」占位项、run_scope 断言基线等于真实用量、熔断断言委派返回同一对象） |
| **rf-1268** | 两个包的门面与其子模块在**顶层**互相导入（`config` 门面 ↔ `_core`/`_llm_settings`，`llm/fact_checker` 门面 ↔ `_numerical`）：导入能否成功取决于包初始化走到第几行，调换 `__init__` 里顶层导入的顺序或新增一行就可能变成 `ImportError`，且报错点与病因相距很远 | 子模块侧改用 `import 包.子模块 as 名` 直取子模块（不经包门面转手），环消除；新增 `src/test/unit/core/test_import_cycles.py` 以顶层导入图的强连通分量为守卫，防再次引入 |
