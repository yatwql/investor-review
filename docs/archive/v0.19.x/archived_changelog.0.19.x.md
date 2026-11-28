# 变更日志归档 — v0.19.x

> 归档时间：2026-11-28（v0.19.1 发布并入；已并入 2 段：v0.19.0（11-27）、v0.19.1（11-28））
> 原始文件：`docs/managements/changelog.md`
> 涵盖版本：v0.19.0 ~ v0.19.1（2026-11-27 ~ 2026-11-28）
> 归档内容：由 `release.py prepare` 自动迁入各发布段

---

## [0.19.0] - 2026-11-27

### 修复
- **测试冗余检查入口收薄（rf-1254）**：`scripts/check-test-redundancy.py` 不再为 `load_script` 直调面 re-export 内部符号（13 块 / 52 个，其中 14 个有真实引用、其余删除），测试改为直接导入 `_test_redundancy.*`；入口只保留 `main()` 实际使用的编排面，`兼容 load_script 直调面` 注释归零，`F401` 信号恢复有效
- **审计待排期六项收口（rf-1247、rf-1248、rf-1249、rf-1250、rf-1251、rf-1252）**：`config` 包补公开覆写读取/清除入口并让截图脚本改走公开面（`check-import-surface` 新增 scripts 侧跨包私有导入规则 + 9 条存量例外）；浮点转换 4 处 `type: ignore` 统一到 `num_utils.finite_or`；宽捕获标注统一为 `# noqa: BLE001 — 理由` 形态并由 `check-code-traces` 增加散文形态检查，体检 12 处重复降级理由收为模块级口径；生产入口为测试打桩保留的死 import 清除、`test-runner.py` 以 70 项显式 `__all__` 替代整文件 F401 豁免；`_report_generation.py` 收为纯门面后删除其 F821 豁免；`compute_factor_exposure_data` 128 行拆为 4 个私有辅助（主函数 51 行）
- **宽捕获抑制形态统一 / 数值转换归一 / 脚本侧导入面兜底（rf-1247、rf-1248、rf-1249）**：散文形态宽捕获按 ruff 实际命中分流——命中处补 `noqa: BLE001 — <理由>`，未命中处（函数体已上抛 / 已 `logger.exception`）只留理由不挂空转抑制；`core/doctor.py` 的 12 处重复降级理由抽为模块级「体检降级口径」注释并逐处只引一句短注释；`check-code-traces` 新增 CAPTURE 支路（口径词无 `noqa: BLE001` 即报，附单测与 scripts-reference 说明）。4 处 `float(safe_num(...))  # type: ignore[arg-type]` 归一到 `core.num_utils.finite_or`（全仓只剩 `num_utils` 一处类型忽略，行为逐点等价并有联合回归用例）。`config` 包补公开的 `get_config_path_override()` / `clear_config_path_override()`，截图脚本不再读私有全局，`check-import-surface` 增 `cross-private-scripts` 规则把 `scripts/` 递归纳入导入面受检域（9 条存量例外登记，带替代路径与复核期限）。
- **83 小时变更审计与整改（rf-1236、rf-1237、rf-1238、rf-1239、rf-1240、rf-1241、rf-1242、rf-1243、rf-1244、rf-1245、rf-1246、rf-1253）**：两路只读审计（架构约束 / 技术债务）结论为无 P0、2 处 P1；本轮修复：`scripts/_release/_evolution.py` 的缺失文件 KeyError（补回归用例）、LLM 模块键元组单源化（新建 `llm/module_registry.py`，11 处调用点改派生，`core`/`config` 由守卫用例锁定等值）、报告生成门面 re-export 收口（删两处复述 + 修正一处死 patch）、pipeline_data 未注册键改为不自动登记（键集 `frozenset` 化）、5 处动态 `logging` 导入、日志级别与双发文案对齐、`factor_workers` 默认值单源、穿透品类状态常量显式化、`tui/handlers_switch.py` 查找去重与配色补齐；跨包私有访问（rf-1247）、`safe_num` 包装（rf-1248）、BLE001 双形态（rf-1249）、F401 兼容面（rf-1250）、F821 豁免（rf-1251）、巨型函数（rf-1252）登记为待排期；`add_error`+`error` 双发（rf-1246 / rf-1253）已在复评收口批统一为只 `add_error` 并补 WARNING 级 caplog 锚点
- **展示脚本取帧泄漏配置路径覆写（rf-1235）**：`scripts/_screenshots/tui_frame.py` 的 `capture_frame` 原先以 `get_config_path()`（有效路径）作还原值——原进程「无覆写」时该值即 `_CONFIG_FILE`，`finally` 再用 `set_config_path_override` 回写就把「覆写=默认路径」永久钉在进程上；现改为记录**原覆写值**并走 `config` 包公开入口 `get_config_path_override()` / `clear_config_path_override()` 还原（None 即还原 None，不再直接读写私有全局 `_config_defaults._CONFIG_PATH_OVERRIDE`），进入与还原各清一次配置缓存，私有 `_clear_config_cache` 换成公开 `invalidate_config_cache`。同源缺口 `src/test/_path_isolation.py` 未清覆写会让上一条用例（如取帧）遗留的演示路径盖掉本轮隔离路径造成跨用例配置串读，现补两条**会红的**回归用例（无前置覆写的真取帧结束后覆写仍为 None、隔离 seed 清掉泄漏覆写）
- **测试用例审计第二批整改（rf-1231 / rf-1232 / rf-1233 / rf-1234）**：按被测模块归位 11 处用例归属（新增 8 个语义化测试文件，其中 6 个为 `*_edge.py`：core 模型极端值、LLM 基类边界、缓存目录安全、配置原子写、API Key 脱敏、持仓目录符号链接过滤；`cli_progress` 迁入 report 域、`news_sources` 用例并入 providers 域、`security_edge` 主体按 cache/config/llm/reader 拆开），跨文件语义重复 13 组各补一侧差异断言（缓存矩阵轮次语义、限速、进度器、凭证矩阵、缺条目各报一条、非零退出码透传），弱断言 14 处改可区分的期望值（截断样本集合、显式 HHI 行定位、相邻档位差、分类集合结构关系），命名失配 10 处按体内行为定名或补齐断言（符号链接真造、乱序输入验严格降序、Event 定序断并发、部分结果断言）；`testplan.md` 的 R-NWS-05/R-NWS-07 载体路径与 `folders.md` 目录树、用例计数同步；web 冒烟与并发缓存用例改结构关系与终态自洽断言
- **测试用例全量审计与首批整改（rf-1225、rf-1226、rf-1227、rf-1228、rf-1229、rf-1230）**：对 901 个测试文件 / 15560 条用例做五类排查（无效、冗余、分类、外网、命名失配）——机械类（死用例/无断言/完全重复/自证/恒真/弱 mock/死 fixture/标记合规）由 `check-test-redundancy --ci` 已验证 0 发现；语义类首批整改 23 处：删恒真/自比较/死语句断言 6 处（`test_factor_evaluator_edge` 的 `len(x)==len(x)`、`test_metrics_edge` 的 `==0.0 or ==-0.0`、`test_correlation_edge` 的 `list(reversed(seq)) and seq` 与丢弃返回值与条件式跳过、`test_news_dedup_perf` 同输入自比）、堵可空过的断言 4 处（`test_liquidity_otc` 遍历前补非空、`test_news_correlator` 条件断言改先筛后断、`test_news_sources` 改断言具体返回值）、去与实现同式的恒等式 2 处（`test_data_freshness` 改断言 `stale is False`、`test_cost_tracker` 改 `used==0`/`remaining==budget`）、修断言结构失效 3 处（`test_filesystem_edge` 的 `or` 写法、`test_cli_edge` 改用 `input` mock、`test_cli_handler_branches` 改验 ERROR 级）、删源码字面断言 1 处（`test_security_edge` 的 `getsource` 查 `mkstemp`）、命名与内容对齐 8 处（含 `test_html_writer_contents`、`test_guard_branch_coverage`、`test_cli_edge` 四处、`test_startup_wizard` 补状态检测断言）。剩余分类迁移（rf-1231）、跨文件语义重复（rf-1232）、弱断言（rf-1233）、命名失配（rf-1234）已入 `review-findings.md` P2 排期
- **`_beta_se` 零方差判定跨解释器不一致（rf-1224）**：`_math_utils._beta_se` 用内建 `sum()` 求均值，而 3.12 起 `sum()` 对浮点改走 Neumaier 补偿累加、3.11 仍是朴素左累加，末位差异让恒定基准的 `Σ(x-x̄)²` 在 3.11 上残留约 `1e-35` 而不为 0——零方差分支未命中，标准误算出 `1.1e15`（GitHub CI 仅 3.11 档红、3.12/3.13 绿）。均值/SSE/SSX 改用 `math.fsum`（正确舍入，跨解释器一致），零方差改按「基准极差为 0」判定（对全等浮点精确）。同批次收口 `report/html_writer_nav.py` 的 ruff format 差异（CI format job 红）。

### 测试
- **`scripts/` 域测试覆盖率补齐（79.3% → 90.2%）**：分四批补测，共新增 21 个测试文件，覆盖此前无判护的面——发布编排（`publish`/`refresh`/`gate` 与台账归档）、`test-runner` 分阶段报告、截图工作区与 TUI/Web/Excel 出图链路、LLM 预算评测与决策质量回测、视觉资产像素校验；新增用例均按域标记归类（`unit_scripts`）并同步目录树与用例计数

## [0.19.1] - 2026-11-28

### 新增
- **质量三件套第 1 件：测试有效性机检两条**——`check-test-redundancy` 增设第 10 类「patch 打在 re-export 面」（只报非公开面，避免把门面替换误判为回归），并新增**会话级全局状态泄漏守卫**：模块级可变全局在用例结束后未复原即报，堵住「上一条用例改写单例、下一条用例因此变绿」的串扰
- **质量三件套第 2 件：变异测试基座 `scripts/eval-mutation-score.py`**（离线评测域，阈值三态退出码）——内置有界变异器，四类算子（比较/布尔/数值/边界）+ 备份恢复四层安全阀（原文件快照、恢复后逐文件校验、进程异常兜底复原、只写工作副本）；首期基线 `core-dates` 100% / `analysis-correlation` 76%
- **属性测试落地**（hypothesis）：相关性对称 / 缩放 / 置换不变与数值工具守恒不变量；测试依赖按单源登记，不与运行时依赖混列
- **两条静态机检**：浮点均值/方差必须 `math.fsum`（含 20 处等价改写）、测试禁真实耗时与真实子进程（`check-test-redundancy` 第 11 类）
- **`scripts/_shared/exceptions.py` 例外表协议归一**：各守护脚本的例外/豁免表改由同一协议读写（键形态、替代路径、复核期限字段一致），新增例外不再各写一套解析

### 修复
- **全仓审计 3 项 P1（rf-1255、rf-1256、rf-1257）**：渲染期上下文彻底移出模块级 dict（图表数据与章节可见性一律经 `render()` context 传递，`_ENV.globals` 只剩导入期 fail-closed 设置）；TUI `[R]` 面板分组标题去双重分隔符（DESIGN-TUI 提示三段式）；空态文案不再染状态色，改走 `data-status` 语义属性（DESIGN 空态口径）
- **测试域 `F821` 取消按文件豁免（rf-1258）**：引号注解改走 `TYPE_CHECKING` 导入块，清 5 条 per-file-ignore 与 1 处真实未定义名——未定义名从此是硬错误而非豁免噪声
- **事实缓存指纹夹具补显式 `encoding`（rf-1259）**：CI `portability` 严格档（`PYTHONWARNDEFAULTENCODING=1`）下不再因隐式编码红
- **变异评测 JSON 汇总得分的期望值改由切片数派生（rf-1260）**：新增切片不再把「总数写死」的断言误打成红
- **107 小时变更审计整改（rf-1261）**：例外表协议归一、变异评测入口收薄（不再为测试直调面 re-export 内部符号）、事实缓存指纹覆盖全部规则模块，并清 8 项 P2

### 变更
- **板块前缀知识收为单源前缀表**：后缀推断与市值档共用同一张表，`core/code_utils.py` 外不再各写一份前缀串；文档十一类措辞对齐
- **巨型函数挂账监控（rf-1262、rf-1263、rf-1264、rf-1265、rf-1266、rf-1267）**：本轮审计识别的 6 项超长函数（生产域单函数 ≥193 行，按行数降序）在 `review-findings.md` 的 P2 排期表各占独立条目并给出拆分方向，不在本版强行拆分

### 测试
- **变异基线从零扩到六切片**：`core-dates` 100%、`analysis-correlation` 76% → 四切片收口（`analysis-metrics` 77.5%→95.0%、`cache-ttl-atomic-write` 55.0%→100%、`cache` 100%（278/278）、`metrics` 93.8%（9 个等价变异体））→ 六切片（`pipeline-data` 87%→100%、`factor-formulas` 42.5%→92.5%）
- **因子公式数值断言批**：按「可手算定值」给公式型模块补数值断言（区别于只断言形状/符号），`pipeline_data` 契约补未注册键不自动登记等断言
- **相关性数值链断言**：p 值 / `pearson_r` / 滚动趋势 / 完整窗边界 / 全窗不足降级逐项可区分
- **缓存边界与返回契约**：「组清空 0 条」「命中率无样本」两个零值边界 + 缓存读侧返回契约（坏载荷按未命中，不抛错）
- 变异评测 `--jobs>1` 时对共享导入面给出警告（并行改同一文件会互相覆盖备份）
