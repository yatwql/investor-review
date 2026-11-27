# 自审记录归档 — v0.19.x

> 归档时间：2026-11-27（v0.19.0 发布，本系列首批已修复批次并入）；2026-11-27 v0.19.0 本批原表搬运
> 原始文件：`docs/managements/review-findings.md`
> 涵盖版本：v0.19.x 已修复项（按发布版号批次，v0.19.0 → ）（含 v0.19.0）
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
