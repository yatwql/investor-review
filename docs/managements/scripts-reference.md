# 辅助脚本参考

> **定位**：`scripts/` 下全部辅助脚本的字典——按用途分类（测试 / 文档 / 代码与文件质量 / 发布 / 诊断 / 启动 / CLI 子命令），每条含**设计逻辑**（为什么存在 / 判什么 / 怎么判 / 边界与取舍）与**使用逻辑**（怎么跑 / 退出码 / finding 处置 / 何时跑）。
> **与开发者指南的分工**：开发主线（环境 / 门禁 / 测试 / 调试 / 扩展 / 发布）见 [开发者指南](developer-guide.md)；这里只回答「某个脚本干什么、怎么跑」。
> **无版本头**：本文件同 `DESIGN.md` / `DESIGN-TUI.md`，属参考型管理文档，不入版本一致性与发布归档受检清单。

## 目录

- [一览](#一览)
- [检查脚本的公共部分](#检查脚本的公共部分)
- [测试类](#测试类)
- [文档类](#文档类)
- [代码与文件质量类](#代码与文件质量类)
- [发布类](#发布类)
- [诊断类](#诊断类)
- [启动脚本](#启动脚本)
- [CLI 子命令](#cli-子命令)
- [LLM 幻觉率采样测试](#llm-幻觉率采样测试)

`scripts/` 下的工具脚本按**用途分类**组织：测试类 / 文档类 / 代码与文件质量类 / 发布类 / 诊断类 / 启动类。检查类条目统一按两个视角记录：

- **设计逻辑**——为什么存在、判什么、怎么判定、边界与取舍（改规则前先读这段）。
- **使用逻辑**——怎么跑、退出码怎么读、finding 怎么处置、什么时候会自动跑。

所有检查脚本共用的契约、设施与处置流程集中在「检查脚本的公共部分」，各条目不再重复。哪些脚本属于阻塞门禁的十守护、各在 P0 还是 P2，以「三级门禁」章节的五处同源清单为准。

## 一览

| 脚本 | 分类 | 一句话 |
|:-----|:-----|:-------|
| `test-runner.py` | 测试 | pytest 标记模式封装驱动，支持 17 种 `--mode` |
| `extract-test-failures.py` | 测试 | 从 pytest-html 报告提取失败用例详情 |
| `find-order-dependent-test.py` | 测试 | 单跑绿合跑红的顺序依赖污染源二分定位 |
| `check-code-traces.py` | 质量 | 代码注释/文档字符串中历史变更痕迹检查 |
| `check-doc-traces.py` | 文档 | 面向读者文档（.md）历史变更痕迹 + 结构性冗余（DUPLICATE）检查 |
| `check-test-markers.py` | 测试 | AST 静态扫描验证测试标记合规性 |
| `check-task-numbering.py` | 测试 | 任务编号（plan-/rf-）全局一致性检查，防新增编号与历史归档冲突 |
| `check-task-numbering-hook.py` | 测试 | Claude Code PostToolUse hook——编辑编号管理文档后自动校验编号一致性 |
| `check-semantic-index.py` | 文档 | 功能语义命名表正反向一致性校验（功能开关注册表表外键 / 僵尸条目 / 合并章 key 缺失） |
| `check-doc-drift.py` | 文档 | 文档与实现一致性校验（章节表/章节数量、开关表/分组计数/默认值断言、配置与 LLM 默认值表、TUI 面板编号、目录树、项目统计表；`--sync` 自动回写统计快照） |
| `check-doc-links.py` | 文档 | 文档链接与结构一致性校验（死链/死锚点/重复标题/层级/编号序列/§引用） |
| `check-file-length.py` | 质量 | 单文件行数红线守护（主程序/脚本 >1000 行 / 测试 >1200 行；豁免登记与 review-findings 挂账同步，`-v` 输出可选优化区间清单供登记表派生） |
| `check-test-redundancy.py` | 测试 | 测试用例冗余与无效检查（死用例 / 无断言 / 完全重复 / 自证用例 / 硬编码演进总数 / 恒真断言 / 死 fixture / 弱 mock 断言；实现拆在 `_test_redundancy/`——八类检查各一模块 + 共用 AST 原语 + 事实缓存 + 编排，入口只留 CLI） |
| `check-requirement-trace.py` | 测试 | 需求 ID ↔ 验证载体追溯（单段 ID 全域覆盖 / 载体文件存在 / ID 双向一致） |
| `install-claude-hook.py` | 测试 | 安装/卸载 Claude Code PostToolUse hook（任务编号一致性自动校验） |
| `llm-hallucination-sampler.py` | 测试 | 10 组标准持仓 × LLM 幻觉率采样（薄 CLI，实现在 `_halluc_sampler/` 包） |
| `calibrate-dedup-threshold.py` | 测试 | 新闻去重阈值校准分析 |
| `collect-test-coverage.py` | 测试 | 测试覆盖计数收集（`--collect-only` 快照；`--update-docs` 回写 test-coverage/folders 计数行） |
| `smoke-web.py` | 测试 | Web 模式 HTTP 冒烟脚本（test_client 进程内全链路断言，可独立运行） |
| `check-version-consistency.py` | 发布 | 版本号全局一致性检查（P0/P2 守护脚本 + 发布流程必跑） |
| `check-style-guardrails.py` | 质量 | 设计护栏机检（DESIGN.md 护栏样式面；E 级：强调色越权/明暗同步/双面 token 对表判 finding，W 级：裸色值/圆角档位观察统计——未入 pre-commit 钩子与 CI guards；**发布门禁**（release.py gate）已纳入，开发期快反馈由 unit 测试承担） |
| `check-script-contract.py` | 质量 | scripts 顶层脚本契约机检（退出码声明 ⊆ {0,2} 白名单、check-* 统一 `add_common_args` CLI 面、文本 I/O 显式 encoding、脚本↔测试覆盖映射，四条规则——**观察期**未入钩子与 CI） |
| `release.py` | 发布 | 发布流程分步编排（check / archive-init〔新小版本归档骨架：三份归档 + 目录树块 + 三处索引行，幂等〕/ prepare〔含台账与设计文件归档迁移；不跨版本发布，`--version` 与推导值不一致即中止并给指引〕/ refresh / evolution / gate / publish / devbump，每步独立可审阅、失败即停；refresh 纯文档变更跳过 bench+collect（`--force-refresh` 强制）、bench 默认只测发布子集四档（`--full-bench` 全量）、gate 十守护并行且随核数收敛 ≤4 路并断言归档已迁完；devbump 切版后清空上一版迁档占位节；每命令耗时入 `logs/release.jsonl` 台账） |
| `perf-test-report.py` | 诊断 | 端到端报告生成管线性能基准（独立脚本，mock 外部数据源） |
| `perf-view.py` | 诊断 | 性能历史趋势查看（读取 perf_history.jsonl → 版本演进总表 + P95/P99 分位概览 + 离群/尾部归因 + 异常运行/同版本漂移 + 秒每品种归一化 + 时段聚合（耗时与费用合计/环比）/机读输出（llm_cost、by_period 费用字段）；实现拆在 `_perf_view/`——`stats.py` 统计原语 / `data.py` 派生 / `report.py` 渲染 / `cli.py` 入口，主入口只留 docstring 与 re-export） |
| `probe.py` | 诊断 | 探测统一入口（按 target 分发到 `probes/` 子模块；新探针实现契约面登记即用） |
| `probe-csi-factor-indices.py` / `probe-push2.py` | 诊断 | 旧入口兼容垫片（薄委托到 `probes/csi.py` / `probes/push2.py`，用法不变） |
| `factor_zoo_eval.py` | 诊断 | 因子动物园目录评测（非生产代码；五个来源族各抽 5 个因子，评测 A 字段可得率 / B 与既有信号族增量 / C 全量计算耗时占比三项指标，A/B/C 全过才转正立项；子命令 catalog / fields / signals / timing / verdict / all，产物只落 `docs/tmp/factor-zoo/`；实现拆在 `_factor_zoo/`） |
| `check-svg.py` | 诊断 | README SVG 架构图检查（子命令 `geom` 几何 / `pixel` 像素 / `text-overflow` 文字色越界；像素子命令需 Pillow） |
| `_checklib.py` | 内部 | 检查脚本共享设施（统一 `-v/--ci` 契约与 `[OK]`/`[ERR]` 输出、`rel()`、`report()`、文档区间与表格解析） |
| `_test_runner/` | 内部 | 测试驱动内部实现包（paths / modes / pytest_env / machine_info / doc_writer / report_html / runner） |
| `launch.sh` / `launch.ps1` | 启动 | Linux/macOS / Windows 一键启动脚本（无参数启动 TUI；`web` 子命令启动 Web 浏览器模式） |
| `cli.sh` / `cli.ps1` | 启动 | Linux/macOS / Windows CLI 命令行包装（无参数默认生成报告） |
| `llm.sh` / `llm.ps1` | 启动 | Linux/macOS / Windows 完整报告快捷入口（固定 `report --type full`，等价 TUI「生成完整报告」） |
| `check-sources` | 诊断 | cli.py 子命令：数据源联通性检测 |
| `doctor` | 诊断 | cli.py 子命令：系统自检（环境/配置/目录/开关/适配/凭据/数据源七组，`--offline`/`--timeout`，不受实验开关约束） |
| `view-logs` | 诊断 | cli.py 子命令：查看结构化运行日志（`--level`/`--lines`/`--since`/`--until`，与 TUI `[V]` 同实现） |
| `whatif` | 诊断 | cli.py 子命令：调仓 What-if 模拟（对比两份持仓生成独立 diff 报告，见 [快速开始](../manuals/how-to-start.md)） |
| `cassettes` | 诊断 | cli.py 子命令：数据源记录-回放维护（列表 / `--verify` 离线回放校验，见下文「CLI 子命令」） |

## 检查脚本的公共部分

以下四块适用于所有检查脚本，条目里只写各自的差异。

**检查脚本的共享设施与统一契约（`_checklib.py` / `_traces_common.py` / `_traces_code/` / `_traces_doc/` / `_test_runner/`）**

`scripts/` 下的检查脚本共用一套 CLI 契约与设施，避免每个脚本各写一份：

- **统一契约**（`_checklib.add_common_args()` / `report()`）：`-v/--verbose` 详细输出、`--ci` 仅输出 `文件:描述`；**通过退出 0，发现 finding 退出 2**（`check-code-traces.py` 另有 HIGH=1 / LOW=3 的分级语义，属其自身约定）；通过打印 `[OK] …`，失败逐条 `[ERR] file:desc`（`--ci` 下为裸行）+ 汇总行
- **共享原语**：`REPO_ROOT` / `rel()`（仓库相对路径，非仓库内路径原样返回）、`extract_region()` / `replace_region()`（标记区间）、`extract_table_region()` / `replace_table_region()`（表区域，带结构校验）
- **`_traces_code/`**：check-code-traces 内部实现包——`patterns.py`（**匹配表**：历史痕迹/标识符/暗号模式与编译镜像；只管「命中了什么」，共享历史叙述正则引用 `_traces_common` 常量）、`exemptions.py`（**豁免表**：章节计数与迭代轮次豁免〔check-doc-traces 共用〕+ 代码侧行级豁免〔合法领域值/魔法编号领域值/测试回归元描述〕与 `_is_*_excluded` 判定——调漏检改前者、调误报改后者，不在一处相互淹没）、`extract.py`（注释/标识符抽取）、`scan.py`（扫描调度）、`layers.py`（core 反向依赖守卫）、`config.py`（扫描域配置与规则载体豁免：`RULE_CARRIER_DIRS` / `RULE_CARRIER_FILES`）；check-code-traces.py 只留 CLI 与原面 re-export
- **`_traces_doc/`**：check-doc-traces 后端包——`patterns.py`（文档痕迹模式表 `DOC_PATTERNS` / 树行专属 `TREE_ONLY_PATTERNS` / 行级豁免 `EXCLUDE_PATTERNS`+`is_excluded`，共享历史叙述正则引用 `_traces_common` 常量）、`bundle.py`（编译镜像 + 按域取子集 + 树行拼表，`pattern_bundle` 按〔分类集, CIPHER 开关, 树行〕lru 缓存并集预筛——预筛面与精确面同源）、`dedup.py`（结构性冗余扫描：单次遍历内完成标题路径感知判重、台账/归档域重复长行与区块同小节限定、空白归一与同块单报），入口薄 CLI 与原面 re-export
- **`_traces_common.py`**：两脚本**逐字节相同**的历史叙述正则单一来源（命名常量 + `SHARED_REGEXES` 元组）；只登记字面量，**分类与描述仍按各自域定义**，判定入口/域矩阵/豁免语义不在此模块——新增同源词汇先加此处再两侧引用，仅一域需要的词汇不进共享表（机检见 `test_trace_shared_vocabulary`：两表交集须恰等于词表、两侧须都引用、模式源码内不得写死字面量）
- **`_test_runner/`**：`test-runner.py` 的内部实现包（paths / modes / pytest_env / machine_info / doc_writer / report_html / runner），入口仅保留 CLI 与主流程并原面 re-export —— 既有测试访问 `test_runner._env_value` 等名字仍有效；**注意**：monkeypatch 内部状态（如 `_LATEST_DIR` / `_DOC_COVERAGE_PATH`）须指向持有它的子模块（`_test_runner.report_html` / `_test_runner.doc_writer`）

**跨脚本口径：共性 / 差异（`_traces_common` 的边界）**

两守护共享的是**词汇**，不是判定：`_traces_common.py` 只登记正则字面量，分类、严重度、豁免策略、文档类型矩阵、扫描通道（文本 / AST）全部留在各自域内。因此同一正则在两域的分类可以不同，这是**有意保留**的差异：

| 共享常量 | 代码域分类（退出码） | 文档域分类（退出码） | 关系 |
|:---|:---|:---|:---|
| `CIPHER_CONSTRAINT` | `CODE`（2，硬禁止） | `CIPHER`（1） | 两侧均阻塞，域内治理层级不同 |
| `HISTORY_LEGACY_LABEL` / `HISTORY_ITERATION_MARK` / `HISTORY_STATE_EARLY` | `VERSION`（1） | `HIGH`（1） | 同为阻塞，仅分类标签不同 |
| `HISTORY_PHYSICAL_MERGE` | `CHANGE`（3，仅提示复核） | `HIGH`（1，阻塞） | **唯一严重度分歧**：文档面向读者须改写为当前结构，代码注释里该叙述只提示 |
| `LOW_*` 七条（`LOW_REFACTOR_TO` / `LOW_DEPRECATED` / `LOW_PASSIVE_PAST` / `LOW_NOT_YET` / `LOW_TODO` / `LOW_FUTURE_PLAN` / `LOW_TRANSITIONAL`） | `TODO` / `CHANGE` / `DEPR`（3） | `LOW`（2） | 均非阻塞（差异只在"仅复核"档位与退出码数值） |

维护规则：新增共享词条时**两域各自定分类与描述**（不得为了"统一"而改另一域的分类——那会改变退出码乃至阻塞与否）；只在一域需要的词条不进共享表。分域矩阵与严重度分桶均有常量承载（`check-doc-traces.py` 的 `DOMAIN_*`、`check-code-traces.py` 的 `HIGH/CODE/LOW_CATEGORIES`），由 `test_trace_shared_vocabulary` 的域矩阵 / 分桶用例机检。

**通用设计逻辑（痕迹类检查的共同取舍）**

两脚本各自的扫描面、规则与退出码见上两节；本节讲**共同的设计取舍与处置流程**，作为规则变更时的判断依据。

这两支检查不做语义判定，只做**痕迹召回**：纪律本身（"文档只描述当前是什么/做什么"）不可机检，但违反它留下的语言形态相当稳定——时间前缀、来源归属、对比结构、进度状态词。检查器认定的是这些**形态**，所以命中不等于一定违规：误报靠豁免与分级压住，漏报靠域矩阵与词表覆盖压住。理解这一点，后面每条规则才有解释力。

1. **为什么是逐行正则而非 AST**：两侧需求相反。代码侧要查的是注释与文档串里的**叙述**——AST 只能给出"这有一段注释"，给不出内容语义，故注释按语言抽成行后走正则；而标识符命名、core 反向依赖、交互层外 `print()` 是**语法结构**，走 AST。同一脚本内两条通道各管一半，互不替代。文档侧 Markdown 没有统一 AST（表格/围栏/目录树的意义在渲染层），"当前状态"与"历史叙述"的差别是措辞，正则正好对上。
2. **为什么不用 LLM 判定**：成本（每次提交数十万字）、不可回放（同输入不同结论）、不可解释（finding 指不到规则）。规则命中能回答"哪条模式、为什么命中"，这是它能进阻塞门禁的前提。
3. **判定链（一行如何变成 finding）**：并集预筛（一次扫描判断"可能命中"，普通行直通）→ 逐模式精确匹配（**首个命中**决定分类与描述）→ 域门禁（该文档类型 / 该扫描通道是否查这个分类）→ 行级豁免（合法当前状态与流程描述）→ 定级（阻塞 / 仅提示）。
   - **预筛只加速、不改结论**：命中后仍走逐条精确分支。
   - **门禁与豁免只能减不能加**：都发生在"已命中"之后。
   - **顺序即语义**：模式表内的先后决定首个命中的分类，调整顺序属行为变更（非必要不动）。
4. **误报的四个泄压阀**（缺一个就会被天天误报，进而被整条绕过）：行级豁免（"当前不支持""门禁流程""运行时按日期归档"等合法表述）、结构性豁免（围栏代码块、行内代码令牌、常规域的表格行）、域矩阵（按文档类型决定查什么）、分级（拿不准的进 LOW，不阻塞）。
5. **尺子怎么量自己**：规则的模式与描述字面量必然长得像被查对象，故按**结构**豁免——工具自身文件（`check-*traces.py` 文件名模式）、规则载体目录（`_traces_code` / `_traces_doc`）与载体单文件（`_traces_common.py`）。按结构而非清单识别，新增同类工具或后端包自动生效，不会漏登记。
6. **可回放的前提**：结论缓存有两面——输入面（受检文件内容与清单）与逻辑面（CLI + 扫描后端 + 共享词表）。判定面搬家而指纹不带过去，就会出现"规则变了、结论还是上次的"假绿，故逻辑面文件清单本身有机检。
7. **明确的取舍**：不追求零误报（追求"高置信必真、低置信不阻塞"）；不做跨语言语义理解（中英文各登记形态，生僻说法宁可漏）；两脚本不合并（退出码、文档类型域、扫描通道都不同）；共享层只放字面量（分类/严重度/域矩阵归各域）。

**通用使用逻辑（finding 处置与流程）**

- **怎么跑**：`--ci` 给机器（只输出 `文件:描述`，无前缀与汇总），人读用默认输出，排查豁免或跳过原因加 `-v`；两脚本都是全仓扫描（不接路径参数），聚焦单个文件用 `--ci | grep <路径>`。
- **退出码怎么读**：文档侧 0 通过 / 1 必须改 / 2 仅提示（LOW）；代码侧 0 通过 / 1 高置信 / 2 任务编号·标识符·章节轮次·日志违规 / 3 仅提示。
- **一条 finding 的四种处置**（按优先级）：
  1. **改表述**（首选）：去掉时间、来源、对比，只写当前是什么——比加豁免便宜，也不会削弱检查。
  2. **判为合法 → 加最窄豁免**：优先收窄正则，其次行级白名单，最后才是域矩阵；**禁止整文件/整目录豁免**（该文件从此永久失去检查）。加豁免须在提交说明里写清"为什么这段叙述属于当前状态"。
  3. **判为应检出但漏了 → 加词条**：先定语义名与分类，再按"共享词表 → 两域引用 → 正向用例"落地；只在一域需要的词条不进共享表。
  4. **判为误伤当前语义 → 加负向用例**：先把"有意不检"锁进测试，再收窄正则——否则下次扩词会把它扫回来。
- **改检查项的标准顺序**（固定，跳过任一步都会留下单侧漂移）：词条 → 分类/分桶 → 域矩阵 → 正向+负向用例 → 三处文档（脚本 docstring / 本指南 / 门禁清单）→ 全仓 `--ci` 对拍（改动前后 findings 必须能逐条解释）。
- **何时跑**：`git commit` 时钩子按暂存域自动执行，**不要手动重复**；提交前手动只需跑测试门禁；发布门禁（P2）里它属十守护之一，CI 的 `guards` job 恒跑全量兜底。
- **缓存**：输入或逻辑面变化自动失效；排查"改了规则结论没变"时**不要删缓存**，用 `CHECK_CONCLUSION_CACHE_DIR=$(mktemp -d)` 隔离跑一次对照——这样能区分"缓存未失效（缺陷）"与"规则确实没覆盖（漏报）"。
- **报误报的最小信息集**：finding 原文 + 你的判定（合法 / 应改）+ 处置（豁免 / 词条）+ 用例名。四项齐了，一次提交即可落地，不用来回确认。

> 新增检查脚本时直接复用 `_checklib`，不要自建 argparse/输出/退出样板；**跨脚本共用**的历史变更叙述正则放 `_traces_common.py`（词表单一来源），单域模式放各自 `_traces_*/patterns.py`（只管「匹配什么」），豁免策略放 `_traces_code/exemptions.py` 与 `_traces_doc/patterns.py` 的 `EXCLUDE_PATTERNS`（只管「命中后哪些算合法」）；文档域的模式子集与预筛放 `_traces_doc/bundle.py`。

## 测试类

测试驱动、覆盖率采集、失败定位、冒烟与采样工具，以及测试质量机检（冗余 / 标记 / 需求追溯，其中部分属十守护——以「三级门禁」清单为准）。

**测试驱动与覆盖率**

**`test-runner.py` — 测试模式驱动**

pytest 的 `-m` 标记表达式封装层，按 `--mode` 选择预定义组合。所有 `--mode` 的详细说明见上文「测试模式详解」章节。

```bash
# 查看所有可用 mode
.venv/bin/python scripts/test-runner.py --help

# 日常提交前门禁（P0）
.venv/bin/python scripts/test-runner.py --mode dev-verify

# 合入门禁（P1）
.venv/bin/python scripts/test-runner.py --mode verify

# 发布门禁（P2）
.venv/bin/python scripts/test-runner.py --mode verify,regression

# 多档并行采集（可选；默认 4 核+ 为 2、弱机为 1，自适应）
.venv/bin/python scripts/test-runner.py --mode dev-verify,regression --jobs 2

# 跨机器耗时采集 + 自动更新 test-coverage.md 环境耗时对照（含机器信息采集）
.venv/bin/python scripts/test-runner.py --mode bench --update-docs

# 带行覆盖率
.venv/bin/python scripts/test-runner.py --mode unit --coverage
```

**`collect-test-coverage.py` — 测试覆盖计数收集**

只做 `.venv/bin/python -m pytest --collect-only`（收集测试项，**不执行测试**，耗时约 2s），模式计数谓词由 `_test_runner/modes.py::MODES` 的 marker 表达式现场编译，输出各模式 / unit 子标记 / scenario 分组 / 跨类标记 / 功能域 / 文件分布的项数，供 `docs/managements/test-coverage.md` 快照更新使用。

```bash
.venv/bin/python scripts/collect-test-coverage.py                 # 仅输出（人工对照改文档）
.venv/bin/python scripts/collect-test-coverage.py --update-docs   # 按本次快照回写计数行
```

**说明**：
- 只收集不执行——测试体不会运行，不影响测试结果，也不会触发真实数据源 / LLM 调用
- 项数随版本迭代变化，属撰写时快照，精确计数以本脚本实时输出为准
- **`--update-docs` 回写**：按本次快照改写 `test-coverage.md` 计数行（反引号标记行 + 能映射到标记的加粗标签行，比对域与 `check-doc-drift` 的计数核对同构、复用其行匹配原语，写后必然通过 `--with-test-count` 核对）与 `folders.md` 项目统计表「测试用例」行；只改数字、粗体/千分位/后缀原样保留，内容一致则零变更（幂等）；收集退出码非 0/5（如收集期校验中断）时**跳过回写**并告警，错数不落盘。与 `test-runner --mode bench --update-docs`（写耗时对照表）互不重叠
- 计数口径直接取自 `MODES` 的 marker 表达式（复用 pytest 自身的 `-m` 求值器，`verify` / `dev-verify` 等组合模式与阶段 marker 回落同源），表达式只在 `modes.py` 定义一处、模式增删自动跟随；`all`（已由「总收集: N」表达）与 `live`（默认收集宇宙排除，计数恒 0）为显式豁免并在脚本内注记理由

**失败定位**

**`extract-test-failures.py` — 失败用例提取**

见上文「快速定位失败用例」章节。

**`find-order-dependent-test.py` — 顺序依赖污染源二分**

见上文「定位顺序依赖失败」章节。

**冒烟与采样**

**`smoke-web.py` — Web 模式 HTTP 冒烟脚本**

Web 模式全链路可复跑冒烟验证（上传→生成→进度→产物，Flask `test_client` 进程内走 HTTP 契约，不占端口、不发真实网络）。管线（fake executor）、健康探测、历史记录均 mock，`output_dir` 与上传目录临时隔离，不触碰真实数据。

```bash
# 全量断言（页面渲染/健康检查/上传校验/运行 202/进度事件/完成态/产物下载/历史记录/产物目录隔离/正式-用存量/配置编辑）
.venv/bin/python scripts/smoke-web.py

# 仅打印失败项
.venv/bin/python scripts/smoke-web.py --quiet
```

退出码：0 = 全部通过；2 = 存在失败项。同款断言已由 `src/test/unit/web/test_smoke_web.py`（`unit_web` 标记）纳入 `dev-verify`/`verify` 门禁，本脚本用于手动快速复跑。

**`llm-hallucination-sampler.py` — LLM 幻觉率采样**

见下文「LLM 幻觉率采样测试」章节。

**`calibrate-dedup-threshold.py` — 新闻去重阈值校准**

新闻标题去重（同源/跨源安全区分级 + 候选区阶梯 + 方向对立防护，阈值见 `news_dedup.py` 校准常量）在每次报告运行时自动记录"边界案例"到 `data/cache/dedup_anchors.jsonl`。积累足够锚点后，用此脚本分析当前阈值是否合理。

```bash
# 分析全部锚点，输出建议
.venv/bin/python scripts/calibrate-dedup-threshold.py

# 仅看汇总统计（不展开详细列表）
.venv/bin/python scripts/calibrate-dedup-threshold.py --summary

# 指定锚点文件
.venv/bin/python scripts/calibrate-dedup-threshold.py --file data/cache/dedup_anchors.jsonl
```

**校准时机**：建议锚点文件积累 **100 条以上**（约 5~10 次报告运行）后校准一次。脚本只分析不自动修改阈值，是否需要调整由开发者判断。

**测试质量机检**

**`check-test-redundancy.py` — 测试用例冗余与无效检查**

**设计逻辑**（为什么存在 / 判什么 / 怎么判 / 边界与取舍）

静态分析 `src/test/`（默认跳过 `pytest.ini` 刻意排除的 `live/` 真网套件），抓八类「看着有测试其实没测住」的问题：

1. **死用例**：同文件同类同名重复定义（后者覆盖前者）、类名不以 `Test` 开头的方法形式 `test_*`、`Test*` 类定义了 `__init__`（pytest 整类跳过）
2. **无断言用例**：既无 `assert`、也无 `pytest.raises/warns/fail`、也无 `assertEqual` 等 `assert*` / `assert_called*`，且不经同类辅助方法（如 `self._assert_pairs_contain(...)`，其内部含断言）——断言落在辅助方法里同样算数
3. **完全重复用例**：去 docstring 后「函数体 + 参数 + 装饰器」AST 归一化一致（同一被测对象同一断言）。凡函数体内出现**无法解析**的 `self.<attr>` 间接调用（目标来自 `setUp` / 跨模块基类）一律跳过比对——避免把「同名方法绑定不同被测对象」的并行覆盖误判为重复
4. **自证用例**：同一用例内既 `@patch("<mod>.<fn>")` 又直接调用同名函数，且把该 mock 的 `.return_value` 设成某字面量、再用断言与该字面量比较（断言恒真，等于没测）
5. **硬编码「会演进的总数」**：把**可增长集合的条数**写死进断言（如 `assert len(req_ids) == 276`、`assert len(sections) == 17`）。
   这类总数是文档真值来源的派生量，**新增一条需求/章节/开关就会把测试打红**——良性变更被误判为回归，而它捕捉不到任何真实缺陷；且与门禁脚本（如 `check-requirement-trace` 的全域覆盖断言）**职责重复**。
   正确写法是断言**结构关系**：集合双向相等（`set(a) == set(b)`）、子集/覆盖（`expected <= set(a)`）、序号连续（`numbers == list(range(1, n+1))`）、唯一性（`len(keys) == len(set(keys))`）。
   判定保守（宁少报不误报）：仅看 `assert` 中的 `len(x) ==/> 数字`；实参名需含语义关键词（`requirement`/`section`/`switch`/`module`/`domain`/…）**或**文件路径含 `requirement`/`registry`；忽略 `<= 3` 的小数字（常为有意断言）。
6. **恒真断言**：`assert True` / `assert x == x`——形式上有断言、实际不验证任何行为
7. **死 fixture**：test 文件内定义（排除 conftest 自身与 autouse）且全仓语料（测试 + conftest）无任何引用——定义后从未被消费的死代码
8. **弱 mock 断言**：`assert <mock>.<属性>` 作真值 / `assertIsNotNone(<mock>)`——Mock 恒真且恒不为 None，断言恒成立不验证行为（`.called` / `assert_called*` 等专用断言不算弱）

**使用逻辑**（怎么跑 / 退出码 / finding 处置 / 何时跑）

```bash
.venv/bin/python scripts/check-test-redundancy.py                 # 八类全查
.venv/bin/python scripts/check-test-redundancy.py -v              # 详细输出（扫描规模 + 各类计数 + 跳过的间接调用用例数）
.venv/bin/python scripts/check-test-redundancy.py --ci            # CI 模式（只输出 文件:描述，退出码 2）
.venv/bin/python scripts/check-test-redundancy.py --include-live  # 连带扫描 src/test/live/
.venv/bin/python scripts/check-test-redundancy.py --audit         # 附加建议性骨架审计（同名同骨架分组找复制粘贴嫌疑；恒不参与退出码）
.venv/bin/python scripts/check-test-redundancy.py --audit --audit-all  # 骨架审计连带文件内组（默认仅跨文件）
```

> `--audit` 为建议性输出：骨架同构多为合法矩阵契约（同场景×不同模块），须人工判读后决定合并或差异化断言；`--audit-all` 连带文件内组。

> 删除/合并用例后须同步刷新 `test-coverage.md`（模式/子标记计数）与 `folders.md`（测试文件数/行数/用例数），
> 两处由 `check-doc-drift.py --with-test-count` 兜底核对。**修法优先级**：名实不符的用例应改成真正跑它名字
> 声称的场景（补上原本空白的覆盖），而不是改名了事。

> **何时跑**：`git commit` 时由 pre-commit 钩子按暂存域自动执行（**勿手动重复**）；发布门禁（P2）与 CI `guards` job 恒跑全量兜底。

**`check-test-markers.py` — 标记合规性检查**

**设计逻辑**（为什么存在 / 判什么 / 怎么判 / 边界与取舍）

AST 静态扫描所有 `test_*.py` 文件，检查：
- 标记完整性（是否有 `unit_*` 子标记）
- 拼写错误（未注册的 marker 名）
- `_edge.py` 是否漏标 `edge`，或非 `_edge.py` 文件是否误标 `edge`

**使用逻辑**（怎么跑 / 退出码 / finding 处置 / 何时跑）

```bash
.venv/bin/python scripts/check-test-markers.py
```

无报错输出即合规。新增/修改测试文件后必须运行此脚本。

> **何时跑**：不入钩子与 CI——新增/修改测试文件后手动跑；`conftest.py` 的收集期校验是兜底。

**`check-requirement-trace.py` — 需求 ID ↔ 验证载体追溯**

**设计逻辑**（为什么存在 / 判什么 / 怎么判 / 边界与取舍）

校验 `requirements.md` 的需求 ID 与 `testplan.md` §2.1 追溯表的双向一致：映射表格式齐备、ID 均存在于需求侧、ID 唯一、**已补全域全覆盖**（`_COVERED_DOMAINS` 中每个域的全部 ID 均有载体行）、载体文件真实存在于磁盘。

**使用逻辑**（怎么跑 / 退出码 / finding 处置 / 何时跑）

```bash
.venv/bin/python scripts/check-requirement-trace.py                 # 全量校验
.venv/bin/python scripts/check-requirement-trace.py -v              # 详细输出（逐域覆盖进度）
.venv/bin/python scripts/check-requirement-trace.py --ci            # CI 模式（只输出 文件:描述，退出码 2）
```

> 覆盖口径：仅识别 `R-<域>-<序号>` 形式的**单段**需求 ID；`requirements.md` §7.2–§7.8.4 的双段子域 ID（如 `R-LLM-GM-01`）
> 不在本脚本与追溯表范围内。

> **何时跑**：`git commit` 时由 pre-commit 钩子按暂存域自动执行（**勿手动重复**）；发布门禁（P2）与 CI `guards` job 恒跑全量兜底。

**任务编号与自动化 hook**

**`check-task-numbering.py` — 任务编号全局一致性检查**

**设计逻辑**（为什么存在 / 判什么 / 怎么判 / 边界与取舍）

校验 `plan-` / `rf-` 两类任务编号与各管理文档头部的「编号源」标记（`plan-next` / `rf-next`）是否一致，防止新增编号与历史归档冲突。

新增任务时，编号取管理文档头部 `plan-next` / `rf-next` 当前值，用后将其递增更新；若标记遗漏递增或初值写小，本脚本会扫描当前文档 + 全部历史归档并报错提示修正值。

**使用逻辑**（怎么跑 / 退出码 / finding 处置 / 何时跑）

```bash
.venv/bin/python scripts/check-task-numbering.py            # 检查全部（plan + rf）
.venv/bin/python scripts/check-task-numbering.py --kind rf  # 仅检查 rf
.venv/bin/python scripts/check-task-numbering.py --ci       # CI 模式（只输出错误）
```

自动保障机制（四层，跨机器同步策略见「任务编号规范与自动保障」章节）：P0 门禁、dev-verify preflight、Claude Code hook、git pre-commit。

> **何时跑**：`git commit` 时由 pre-commit 钩子按暂存域自动执行（**勿手动重复**）；发布门禁（P2）与 CI `guards` job 恒跑全量兜底。

**`check-task-numbering-hook.py` — Claude Code PostToolUse hook**

Claude Code 编辑 `plan.md` / `review-findings.md` 后自动运行编号校验，失败返回非零退出码中断编辑。读取 `__INJECTED_OBJECT__`（环境变量或命令行参数）识别目标文件；无 hook 上下文或非编号文档时放行。由 `.claude/settings.json` 的 PostToolUse 钩子调用（不随仓库同步，需 `install-claude-hook.py` 接线）。

**`install-claude-hook.py` — Claude Code hook 安装/卸载**

`.claude/settings.json` 被 `.gitignore` 排除、不随仓库同步。本脚本将 `check-task-numbering-hook.py` 的 PostToolUse 钩子写入该文件，跨机器 clone 后运行一次即完成接线。

```bash
.venv/bin/python scripts/install-claude-hook.py             # 安装（幂等，保留已有配置）
.venv/bin/python scripts/install-claude-hook.py --uninstall # 卸载
```

**`install-hooks.sh` — git pre-commit hook 激活脚本（`.githooks/`）**

`.githooks/` 的 git pre-commit hook（10 个守护脚本全量校验 + 统计快照自动同步）默认**休眠**——`core.hooksPath` 是本机 git 配置、不随仓库同步。clone 后运行一次激活：

```bash
sh .githooks/install-hooks.sh          # 启用（写入本机 core.hooksPath）
sh .githooks/install-hooks.sh --off   # 停用
```

与 `install-claude-hook.py`（Claude Code hook）配套；两条 hook 均调用 `check-task-numbering-hook.py` 校验编号文档。

## 文档类

面向读者文档的痕迹、链接、与实现的一致性，以及语义命名索引的正反向校验。

**`check-doc-traces.py` — 文档历史痕迹 + 结构性冗余检查**

**设计逻辑**（为什么存在 / 判什么 / 怎么判 / 边界与取舍）

扫描项目根 `README.md` 与 `docs/managements/`、`docs/manuals/` 下所有 `.md` 文件，按三个域分流：

| 域 | 文档 | 检查内容 |
|:---|:-----|:---------|
| 常规域 | README + managements（除 changelog/plan/review-findings）+ manuals | 历史痕迹（HIGH）+ 章节/轮次编号 + 归档引用 + 约束代号 + 目录树纪律（folders.md 树行：任务编号 CODE、进度状态词 STATUS，仅 archive 引用豁免）+ 受检域 .md 文件名任务编号 + 重复标题（DUPLICATE 冗余检查） |
| 任务记录域 | `plan.md` / `review-findings.md` / `docs/plan/*.md` | 章节编号 + 复盘痕迹（NARRATIVE：任务内容只反映最新状态）+ 约束代号 + 结构性冗余（DUPLICATE：重复标题 + 同小节内重复长行/区块）；不走表格豁免（任务表/断言表行内叙事必检） |
| 变更日志 | `changelog.md` | 仅章节编号（记录变化是其职责，历史痕迹与复盘叙事均合法）+ 结构性冗余（DUPLICATE：重复标题 + 同小节内重复长行/区块） |
| 归档域 | 各版本归档目录 | 复盘痕迹（NARRATIVE：设计/迭代文档只表述最新状态）+ 结构性冗余（DUPLICATE：重复标题全域、长行/区块归档域）；changelog 归档仅 DUPLICATE（记录变化是其职责）；CIPHER/版本痕迹/章节/轮次属历史文档性质不入检 |


恒不入检：运行时临时目录（脚本跳过范围）。此类文档只应描述“当前是什么/做什么”，不应记录“从哪里来、怎么变的”。

七条核心规则：
1. **正文不得带历史痕迹**：文档正文不得包含历史变更信息（来源叙述、原/旧实现、迁移/重命名、任务编号、版本号、Iter 迭代标记等），只反映“当前是什么/做什么”。例外：`changelog.md`（变更日志的职责即记录变化）
2. **正文不得引用归档文件**：除 changelog 外，常规域文档正文不得引用 `docs/archive/` 下目录或 `archived_*.md`。例外：`folders.md` 的目录树（`│ ├ └` 行）与统计表行——目录树记录项目结构，archive/ 条目是结构的一部分
3. **章节编号引用**：任何受检文档不得用数字章节号（“N 章”）指代报告章节，用语义章节名；计数表述（共 N 章等）豁免。三域均检
4. **迭代轮次引用**：常规文档不得用数字轮次（“第 N 轮”）指代开发迭代；任务记录域与 changelog 豁免（“轮 N”是正式记录载体）
5. **架构约束代号（C 系列，以 technical.md 约束表为准）**：除约束定义处（technical.md / llm-technical.md）外，所有受检文档一律禁（约束代号属暗号，处处禁）
6. **复盘痕迹（NARRATIVE）**：plan/review-findings/docs/plan 的任务内容与归档设计/迭代文档只反映最新状态，禁时间对比叙事、以“不再”领起的对既有行为的否定句、历史归因类表述；任务状态标记、根因定位引用、迭代轮次、设计文档旧格式兼容、行内代码令牌是内容合法。任务记录域与归档域检出（手册操作指引与 changelog 记录变化均不适用）
7. **结构性冗余（DUPLICATE）**：重复标题路径感知判重（同级+同文本+同父标题才算重复，各版本块/任务节下同名小节跨父级合法，同父复现自第 2 次起报出）；≥40 字符重复内容行与连续 5 行重复区块（台账三文件 plan/review-findings/changelog 与归档域）**同小节限定**——跨小节共享行/表属结构，同小节内第 2 次出现起报出，拦截「同一区块/条目粘贴两遍」类残留；比对前空白归一（仅对齐/全角空白差异视为同一内容），同一重复块只报首个窗口（不按滑窗数重复计数）。豁免：围栏代码块、未围栏缩进代码/命令样本与顶格命令（python/pytest/git 等）、顶格 `#` 注释、命令续行（上一行以 `\` 结尾）、键值任务卡（- **键**: 值）、验证清单项（- [ ] 复跑）、分隔/装饰行与短模板行；围栏内容不入窗，整段粘贴由区块判重兜底

目录树与文件名纪律（folders.md 等树行）：
- **树行豁免仅 archive 引用类**：目录树行不走通用行豁免，任务编号（CODE）与进度状态词（STATUS：已实施/完成态/随任务完成移入/验收·判定记录指引/§N 指引/已归档/稿态词/树行“不再”等）在树行照检；描述只讲文件内容，不写进度/流转/任务号。目录树整块位于围栏内，围栏内树行同样照检（围栏跳过仅针对非树行内容）；folders.md 树行按路径分域：docs/archive/ 子树=归档记录域（仅复盘叙事检出）、docs/plan/ 子树=任务记录域（章节编号+约束代号照检）；树行专属来源叙述补强（无后缀模块名的「从 XX 拆出」）
- **文件名任务编号/系列代号**：受检域 .md 文件名含 `rf-N`/`plan-N`、`task\d`、系列字母+数字（`B1-`/`A5-`/`r198_`/`D17-` 类）与 `P3-04` 全形即报（语义命名；phase 词形如 `p1-optimization` 与带版本号区间形式的归档文件名不误伤）

细节规则：
- **Markdown 围栏代码块**（``` 包裹）内为命令/配置示例，非文档叙述，自动跳过（避免 `git tag`、`APP_VERSION` 等示例误报）
- **版本头豁免仅行首锚定**：只豁免 `> 文档版本：vX.Y.Z` 这类版本头行；行中叙述（如"该功能于版本 `vX.Y.Z` 中引入"）仍会命中版本号痕迹
- **当前能力描述豁免**：暂不支持 / 不再支持 / 不正式支持 / 发布版本前 / 门禁流程等合法当前状态描述不报（常规域）
- **运行时产物归档描述豁免**：报告按日期归档属当前功能描述（"归档版报告" / "历史归档至 `YYYYMMDD/` 日期子目录" / "报告已归档到 `reports/`" 等），不视为仓库归档引用
- **任务记录域不走行级豁免**：表格/链接行豁免不适用任务域（任务表、断言表行内的复盘叙事必须检出）；代码块仍跳过
- **LOW 级别**：命中需人工判断的变更/过渡类描述时提示复核，不阻塞提交

**使用逻辑**（怎么跑 / 退出码 / finding 处置 / 何时跑）

```bash
# 检查全部
.venv/bin/python scripts/check-doc-traces.py

# 详细输出（含豁免行信息）
.venv/bin/python scripts/check-doc-traces.py -v

# CI 模式（仅输出 文件名:行号，非零退出码）
.venv/bin/python scripts/check-doc-traces.py --ci
```

**退出码含义**：

| 退出码 | 含义 | 行动 |
|:------:|:-----|:-----|
| 0 | 全部通过 | 无需处理 |
| 1 | HIGH/ARCHIVE/CODE/CIPHER/CHAPTER/ROUND/STATUS/NARRATIVE/DUPLICATE 痕迹 | 应从文档中移除 |
| 2 | 仅 LOW 级别痕迹（需人工判断的变更/过渡类描述） | 建议人工复核 |

> **何时跑**：`git commit` 时由 pre-commit 钩子按暂存域自动执行（**勿手动重复**）；发布门禁（P2）与 CI `guards` job 恒跑全量兜底。

**`check-doc-drift.py` — 文档与实现一致性检查**

> 实现拆在 `_doc_drift/`（章节/开关/目录树/归档索引/分区纪律等各检查族一模块，入口只留 CLI 与编排）。

**设计逻辑**（为什么存在 / 判什么 / 怎么判 / 边界与取舍）

把文档里的「事实断言」（计数、清单、默认值、面板编号、目录树、统计表）与权威源逐条对账，
使漂移在提交前暴露。与 `check-doc-traces.py` 互补：那边管「不该写的内容」（历史痕迹），这边管
「写了但与实现不符的内容」。

二十一项检查（权威源 → 受检文档）：

1. 报告章节表（`reports-instruction.md`）↔ 章节注册表 `_REPORT_SECTION_DEFAULT`（行数/序号/名称）；
   含「可见性规则总览」表 `type` 行双向对账（文档 type 集合 ↔ 注册表 type 集合；历史漂移：注册表把财报两章合为
   `fundamental_snapshot` 并新增 `schedule_replay` 后，表里仍写两个不存在的 type 名称且漏一行——行数恰好相等，计数断言全绿）
2. 章节数量断言（`页签编号 1~N` / `默认顺序（N 项` / `返回 result（N 项` / `N 个报告章节`）↔ 注册表章节数
3. 功能开关表（`how-to-config.md` 四组区段）↔ `feature_switch_registry`（成员/默认值/无表外键）
4. 开关分组计数断言（`呈现与体验 A / 分析增强 B / 独立章节与回放 C / 机制与诊断 D` 连写、`<组名>（N 项`、`共 N 项开关`、旧三组名残留检测）↔ 分组计数
5. 开关默认值断言（`` `flag` `` 后紧随「默认开/关」）↔ 注册表默认值
6. 配置标量默认值表（`how-to-config.md`）↔ `_DEFAULT_CONFIG`
7. LLM 默认参数表（`llm-technical.md`）↔ `_DEFAULT_LLM_SETTINGS` + 缓存 TTL 注册表
8. TUI `[S]` 面板编号连续性与分组边界（`how-to-use-tui-menu.md`）↔ `handlers_config.py` 的派生编号规则
9. 目录树（`folders.md`）↔ 文件系统实测（`src/`、`scripts/`、`docs/{managements,manuals,plan}`）；同父目录 `vN.N.x/` 版本目录块按版本号升序
10. 项目统计表（`folders.md`）↔ 实测文件数/行数（加 `--with-test-count` 再核「测试用例」行）
11. 测试覆盖计数表（`test-coverage.md`）↔ `scripts/collect-test-coverage.py` 快照（仅 `--with-test-count`）
12. 归档索引完整性：changelog / plan / review-findings 三份管理文档的「归档」索引 ↔ 归档目录下
    `archived_*` 文件**双向**比对（漏列 → 「缺少」；幽灵引用 → 「不存在」）
13. 管理文档分区纪律：review-findings 未完成/已解决分区互斥且已解决项须在 changelog 有修复记录；
    「开发期已修复」节只允许出现在已解决区、P 档标题只允许出现在未完成区（节归属，标题错位时
    rf 标识比对完全静默）；plan 未完成区不得含 ✅/已归档项；现行 changelog 只允许一个 `-dev` 段头
14. Extended Thinking 支持矩阵：手册对比表须覆盖代码支持的全部厂商族、「仅」式预算枚举句须列全、
    默认开思考族须有提示（权威源为 `llm/api_base.py` 的前缀名单）
15. Provider Chain 降级表：`fetcher/chain_config.py::_DEFAULT_CHAINS` 的 15 条链 ↔
    `datasource-reliability.md` §4.2 表逐链**双向**比对（漏链 → 「缺少链路」；幽灵行 → 「无此链」）
16. 守护清单同源：developer-guide 的 P0/P2 门禁代码块、`ci.yml` guards steps、CLAUDE.md P0/P2 条款、
    testplan P0/P2 清单行与 `.githooks/pre-commit` 执行体，五处的 `scripts/check-*.py --ci` 引用集合两两一致（新增守护脚本漏改任一处即报）
17. 章节-区块矩阵（`technical.md` §4.22）：文档行 ↔ 区块注册表逐列 / 键集双向 / 两端实现提取集合三向对账
18. 手册菜单块一致性：双手册主菜单 code block（键集合/标签头）↔ `tui/tui_menu.py` MENU_ITEMS；
   正文「菜单 `X`」引用须为主菜单键（历史漂移：缓存管理由 `[4]` 改为 `[3]`、持仓目录/文件名/输出目录收进 `[D]` 二级面板后，
   十余处正文仍写旧主菜单键，读者按提示找不到入口——code block 校验护不住正文）；`[D]` 二级键（`CONFIG_DIR_INFO_KEYS`）须写作「菜单 `D` → `C`」；
    全文档「返回主菜单」行键=0 不变量（返回键全局统一）
19. 需求菜单表（`requirements.md` §3.2）：键集合/分组标题/组内顺序 ↔ MENU_ITEMS + MENU_GROUPS
20. 迁档占位↔归档节：review-findings「已随 vX.Y.Z 发布迁入」占位 ↔ 对应版本归档正文含该版本二级标题归档节
21. 树描述计数禁令：folders.md 目录树描述禁写「阿拉伯数字+量词」易漂移计数（docs/archive 记录域豁免；中文数词设计常量不入检）

**使用逻辑**（怎么跑 / 退出码 / finding 处置 / 何时跑）

```bash
.venv/bin/python scripts/check-doc-drift.py                   # 二十一项全查
.venv/bin/python scripts/check-doc-drift.py -v                # 详细输出（打印解析结果与实测统计）
.venv/bin/python scripts/check-doc-drift.py --ci              # CI 模式（只输出 文件:描述，退出码 2）
.venv/bin/python scripts/check-doc-drift.py --with-test-count # 附带 pytest 收集，核对「测试用例」与 test-coverage.md 计数表
.venv/bin/python scripts/check-doc-drift.py --sync             # 统计快照自动同步（实测数字回写 folders.md 并 git add，幂等）
```

> **统计快照漂移的自动化治理**：第 10 项「项目统计表」的数字（文件数/行数/用例数）是随日常
> 提交高频变化的派生量（changelog 每补一行、用例每增删即变），人工同步必漏，曾是 CI 最高频红源。
> `--sync` 把实测值自动回写 `folders.md` 对应单元格（只改数字、保留千分位/粗体风格与说明文字，
> 不触碰版本演进对照表），并把回写结果 `git add` 加入暂存区；git pre-commit 钩子在提交涉及
> `docs/managements/` 或 `src/test/` 时自动调用（见「install-hooks.sh」条）。其余类目
> （清单/默认值/目录树/归档索引）的漂移仍需人工按提示修正。

> 按设计豁免的文档：`changelog.md` / `review-findings.md`（如实引用旧数字作为变更记录）与
> 版本快照类文档（历次发布的归档快照）不参与计数与默认值断言扫描。修正提示：报告里的数字就是
> 实测值，直接按提示改文档即可；目录树缺条目时按所属子包位置补一行（含简短职责说明）。

> **何时跑**：`git commit` 时由 pre-commit 钩子按暂存域自动执行（**勿手动重复**）；发布门禁（P2）与 CI `guards` job 恒跑全量兜底。

**文档核对方法（一次完整核查的分层与手段）**

机检只能护住「已绑定权威源的断言」。一份文档集要核到底，按四层分工做，各层手段不同：

| 层 | 核什么 | 手段 | 能否机检 |
|:--|:--|:--|:--|
| 机械层 | 文件路径、需求 ID、任务编号、json 键、CLI 选项是否存在 | 跑六件套（doc-drift / doc-links / version-consistency / requirement-trace / task-numbering / doc-traces）+ 路径与 ID 存在性扫描 | 已全覆盖 |
| 结构层 | 目录与章节顺序、TOC 层级、列表编号连续性、分区归属 | `check-doc-links` 编号/层级序列 + 人工对标题树 | 大部分 |
| 断言层 | 计数、默认值、阈值、清单、菜单键、日期、单位 | 先按权威源统一对账（即上面二十一项），再对未绑定的断言做抽取对码（本节下文） | 需按类扩规则 |
| 散文层 | 机制叙述、因果解释、操作步骤 | 标识符对码 + 人工通读 | 仅部分（见下文） |

**断言层：未绑定断言的抽取对码。** 机检覆盖不到的数值散在散文里，用「抽取 → 对码」代替逐句读：

```python
# 抽出全部可证伪断言，再逐类去代码里找权威源
pat = re.compile(r'(默认[^，。；]{0,10}\d|\d+\s*(项|天|秒|分钟|次|页签)|阈值|最多|至少|保留|重试)')
hits = [(i, l) for i, l in enumerate(text.splitlines(), 1) if pat.search(l)]
```

对码表（高频四类，均已踩过）：定价/默认参数表 ↔ `MODEL_PRICING` / `_DEFAULT_LLM_SETTINGS`；
保留期与上限 ↔ `core/constants.py`；阈值 ↔ `_DEFAULT_CONFIG` 对应小节；清单类 ↔ 注册表（功能开关 / 缓存分组 /
章节 / 数据模块）。清单类**双向**比：文档多写一项和漏写一项都要报。

**散文层：反引号标识符 ↔ 代码符号索引。** 散文里点名的函数/模块/常量若已不存在，读者找不到对应实现，
但路径扫描与断言扫描都不管。做法是先从 `src/` + `scripts/` 建符号集（`def` / `class` /
全大写常量 / 字典字面量键），再把文档反引号里的标识符逐个查存在性，**名不对与不存在都算**：

```python
sym |= set(re.findall(r'^\s*(?:def|class)\s+([A-Za-z_]\w*)', src, re.M))
sym |= set(re.findall(r'^([A-Z_][A-Z0-9_]{2,})\s*[:=]', src, re.M))
sym |= set(re.findall(r'^\s{0,8}["\']([a-z][a-z0-9_]{2,})["\']\s*:', src, re.M))
```

**豁免域**（否则误报会淹没真实信号）：环境变量名（`DATASINK_API_KEY` / `NO_COLOR` / `TEST_RUNNER_JOBS`）、
模板占位（`X.Y.Z` / `XXXXXX` / `NAME` / `VALUE` / `YYYYMMDD`）、外部借鉴对象的文件名（引用的是别的
仓库）、文件名后缀模式（`_edge.py` / `test_xxx_part1.py`）、协议字面量（错误码 / 事件名 / HTTP 头）。
命中后必须**逐条人工判读**再定性，不能直接当缺陷改。

**漂移类别出现第二次就落成机检。** 同一类漂移只要人工发现两次（或一次就是十余处），就该写成
`check-doc-drift` 的子规则而非靠记性——**挂在现有项下扩展子分支，不新增项数与清单五处同源维护**。
两个现成例子：第 1 项的「可见性表 `type` 行双向对账」（只人工维护的表格，行数凑巧相等时
任何计数断言都不报）、第 18 项的「正文菜单键引用」（code block 校验护不住散文里的 `菜单 X` 引用）。

**输出纪律：台账唯一，底稿即删。** 核查发现先登记 `review-findings.md`（带根因与处理），
修复后同步 `changelog.md`；过程中的抽取清单/中间结果放 `docs/tmp/`（git 忽略域），
**闭环后立即删除**——同一批发现不允许在两处各存一份，否则台账与底稿会互相漂移。

**已知边界（不要宣称「已全核」）**：既无可证伪断言、也不点名代码符号的纯叙述段（设计理由、
动机解释、抽象的步骤描述）只能人工通读；机检与两种对码都覆盖不到。报告核查结论时按层说明
覆盖范围，不要笼统说「全部核过」。

**`check-doc-links.py` — 文档链接与结构一致性检查**

**设计逻辑**（为什么存在 / 判什么 / 怎么判 / 边界与取舍）

校验当前文档集（`README.md` / `CLAUDE.md` / 管理 / 手册 / 计划；归档快照按设计豁免）六类问题：死文件链接、死锚点（GitHub slug 规则 + `<a id>` 显式锚点，行内代码等长遮罩、代码围栏跳过）、重复标题（锚点歧义）、标题层级跳变、编号序列跳变（数字按层级+父前缀分组，中文数字按层级分组）、`xxx.md §N` 跨文档章节引用失配（归属取同一行 § 前最近的 `.md` 记号；无文件名且文档使用编号章节时自归属）。

**使用逻辑**（怎么跑 / 退出码 / finding 处置 / 何时跑）

```bash
.venv/bin/python scripts/check-doc-links.py                          # 全量校验
.venv/bin/python scripts/check-doc-links.py -v                       # 详细输出（打印扫描文档清单）
.venv/bin/python scripts/check-doc-links.py --ci                     # CI 模式（只输出 文件:行:描述，退出码 2）
```

> **何时跑**：`git commit` 时由 pre-commit 钩子按暂存域自动执行（**勿手动重复**）；发布门禁（P2）与 CI `guards` job 恒跑全量兜底。

**`check-semantic-index.py` — 语义命名索引正反向一致性检查**

**设计逻辑**（为什么存在 / 判什么 / 怎么判 / 边界与取舍）

校验技术设计文档（`technical.md`）「功能语义命名表」章节（`<!-- semantic-index:start/end -->` 标记区间）与代码的**正面一致性**，与 `check-code-traces.py` 的负面禁止互补：

1. **正向**：功能开关注册表（`feature_switch_registry`）的**每个键**（作用域四组全量，不限分组）必须已登记在「功能语义命名表」中（防新增开关绕过登记）
2. **反向**：表中每个语义 slug 在 `src/python/` 下至少一处非注释代码引用（防僵尸条目——功能删除后表行残留）
3. **合并章**：表下「合并章代码标识符」注声明的 sheet key 必须存在于 `core/registry.py` 的 `_REPORT_SECTION_DEFAULT` 注册表

**使用逻辑**（怎么跑 / 退出码 / finding 处置 / 何时跑）

```bash
.venv/bin/python scripts/check-semantic-index.py       # 检查全部
.venv/bin/python scripts/check-semantic-index.py -v    # 详细输出（打印每项解析结果）
.venv/bin/python scripts/check-semantic-index.py --ci  # CI 模式（只输出错误，退出码 2）
```

> **何时跑**：`git commit` 时由 pre-commit 钩子按暂存域自动执行（**勿手动重复**）；发布门禁（P2）与 CI `guards` job 恒跑全量兜底。

## 代码与文件质量类

代码注释痕迹（含三条 AST 守卫）、文件行数红线，以及两条观察期契约检查。

**`check-code-traces.py` — 代码注释历史痕迹检查**

**设计逻辑**（为什么存在 / 判什么 / 怎么判 / 边界与取舍）

扫描 `src/python/`、`src/test/`、`src/static/`、`scripts/` 下所有 `.py` / `.js` / `.mjs` / `.html` / `.sh` / `.ps1` / `.bat` / `.cmd` 文件的注释和文档字符串，检查是否含有代码历史迭代信息（来源拆分、版本号、任务编号、历史迭代叙述等）。代码注释只应描述"当前是什么"，不应记录"从哪里来、怎么变的"。

除注释痕迹外，另有三条 **AST 级架构守卫**（直接看语法树，与注释格式无关）：

| 守卫 | 检出内容 | 实现 |
|:-----|:---------|:-----|
| core 分层 | core 层反向 `import` 上层包（`fetcher`/`analysis`/`report`/`llm`/`providers`/`web`/`tui`/`cli`） | `_traces_code/layers.py`（豁免文件在 technical.md 声明） |
| 日志统一 | 非交互呈现层调用 `print()`（诊断输出应走 `logging` 落盘） | `_traces_code/logging_discipline.py`（豁免域：`tui/`、`cli/` 整目录 + 进度/一次性检查报告/向导六个模块） |
| 语义命名 | 标识符/注释夹带任务编号、系列代号、字母数字暗号 | `_traces_code/extract.py` + `patterns.py` |

**使用逻辑**（怎么跑 / 退出码 / finding 处置 / 何时跑）

```bash
# 检查全部
.venv/bin/python scripts/check-code-traces.py

# 详细输出（含排除行信息）
.venv/bin/python scripts/check-code-traces.py -v

# CI 模式（仅输出 文件名:行号，非零退出码）
.venv/bin/python scripts/check-code-traces.py --ci
```

除注释痕迹外，另有三条 **AST 级架构守卫**（直接看语法树，与注释格式无关）：

| 守卫 | 检出内容 | 实现 |
|:-----|:---------|:-----|
| core 分层 | core 层反向 `import` 上层包（`fetcher`/`analysis`/`report`/`llm`/`providers`/`web`/`tui`/`cli`） | `_traces_code/layers.py`（豁免文件在 technical.md 声明） |
| 日志统一 | 非交互呈现层调用 `print()`（诊断输出应走 `logging` 落盘） | `_traces_code/logging_discipline.py`（豁免域：`tui/`、`cli/` 整目录 + 进度/一次性检查报告/向导六个模块） |
| 语义命名 | 标识符/注释夹带任务编号、系列代号、字母数字暗号 | `_traces_code/extract.py` + `patterns.py` |

**退出码含义**：

| 退出码 | 含义 | 行动 |
|:------:|:-----|:-----|
| 0 | 全部通过 | 无需处理 |
| 1 | HIGH/ORIGIN/VERSION 痕迹 | 必须修复后再提交 |
| 2 | CODE/IDENT/CHAPTER/ROUND/LOG（任务编号/标识符/章节编号引用/日志统一违规） | 应改用语义描述，`print()` 改用 `logging` |
| 3 | 仅 TODO/CHANGE/DEPR 级别 | 建议人工复核 |

> **何时跑**：`git commit` 时由 pre-commit 钩子按暂存域自动执行（**勿手动重复**）；发布门禁（P2）与 CI `guards` job 恒跑全量兜底。

**`check-file-length.py` — 单文件行数红线守护**

**设计逻辑**（为什么存在 / 判什么 / 怎么判 / 边界与取舍）

**类型阈值**：主程序（`src/python/**.py`）与脚本（`scripts/**.py`，含包内子模块）> 1000 行为 finding；测试（`src/test/**.py`）> 1200 行为 finding。主程序 500 / 脚本 400 / 测试 800 起为**可选优化区间**，不判 finding，仅 `-v` 列出，供 review-findings「文件过长」登记表派生（人肉快照退役，脚本输出即真值）。

**豁免与挂账**：既有破线项须在 `EXEMPTIONS` 登记，**同时**在 review-findings 未完成分区挂账限期处理（约定而非机检，两处须一起改）；豁免文件回落到阈值内时 `-v` 提示「可移除豁免」，防豁免永久化。

**取舍**：按文件类型分档而非统一值——测试文件要用例装配、天然更长；包内子模块与顶层脚本同档，避免「拆包即免检」。

**使用逻辑**（怎么跑 / 退出码 / finding 处置 / 何时跑）

```bash
.venv/bin/python scripts/check-file-length.py        # 检查全部
.venv/bin/python scripts/check-file-length.py -v     # 含可选优化区间清单与豁免状态
.venv/bin/python scripts/check-file-length.py --ci   # CI 模式（只输出 文件:描述）
```

退出码：0 全部通过；2 存在非豁免破线文件。

处置：先按「大文件拆分」策略拆模块或把实现迁入子包；确需保留则登记豁免 + 挂账，两处同时改。

> **何时跑**：`git commit` 时钩子自动执行；发布门禁（P2）与 CI `guards` 全量兜底；新增文件或拆分后务必本地跑一次。

**`check-script-contract.py` — scripts 顶层脚本契约机检（观察期）**

**设计逻辑**（为什么存在 / 判什么 / 怎么判 / 边界与取舍）

四条规则，把「靠人肉逐案发现」的契约偏离变成机检：

1. **退出码声明**：`check-*` 与 `_checklib.report` 消费方的 docstring「退出码」节，声明码集须 ⊆ {0, 2}（`report()` 的返回值域）；分级退出码、环境缺失、事实源不可读等特例在 `_EXIT_CODE_WHITELIST` 显式登记并注理由。
2. **CLI 面**：`check-*` 顶层脚本须调用 `_checklib.add_common_args`（统一 `-v/--verbose` + `--ci`），且**确实消费** `args.verbose`（防空开关）；钩子入口在 `_CLI_SURFACE_EXEMPT` 豁免。
3. **显式编码**：`open()`（非二进制）、`Path.read_text/write_text`、`subprocess` 文本模式均须显式 `encoding=`——cp936 Windows 上隐式编码会静默写错或报错。
4. **测试覆盖**：每个顶层脚本须被 `src/test/` 下至少一个测试按文件名引用；一次性工具在 `_UNTESTED_EXEMPT` 豁免。

**观察期**：与样式护栏同模式——未入钩子与 CI，改动 `scripts/` 后本地跑，避免"新增脚本无人引用/无编码声明"沉淀。

**使用逻辑**（怎么跑 / 退出码 / finding 处置 / 何时跑）

```bash
.venv/bin/python scripts/check-script-contract.py      # 检查全部
.venv/bin/python scripts/check-script-contract.py -v   # 逐脚本打印通过项
.venv/bin/python scripts/check-script-contract.py --ci # CI 模式（只输出 文件:描述）
```

退出码：0 全部通过；2 发现契约偏离。

处置：按规则号补声明 / 补 `add_common_args` / 补 `encoding=` / 补测试引用或登记豁免；确属特例才加白名单，并在注释写清理由。

> **何时跑**：观察期——未入钩子与 CI；新增或改动 `scripts/` 顶层脚本后手动跑。

**`check-style-guardrails.py` — 设计护栏机检（DESIGN.md 样式面）**

**设计逻辑**（为什么存在 / 判什么 / 怎么判 / 边界与取舍）

规则与 `DESIGN.md` 护栏条目逐条同源（各函数 docstring 标注映射编号），**E 级拦截、W 级只观察**：

| 级别 | 规则 | 判什么 |
|:--|:--|:--|
| E1 | 强调色越权（护栏 3） | 品牌蓝系 hex 字面量出现在 token 定义行与 JS 字符串之外；rgb/rgba 透明变体归 W1 观察 |
| E2 | 明暗同步（护栏 5） | `[data-theme="dark"]` 覆盖的变量在 `:root` 缺定义 |
| E3 | 双面 token 对表 | 正向：Colors 表两面具名 token 须在双面 `:root` 定义；反向：实现里「值为颜色」的两面同名变量须在 Colors 表登记 |
| W1 | 裸色值存量（护栏 1） | 非定义行的 hex/rgb 字面量（**统计不判 finding**） |
| W2 | 圆角档位（护栏 2） | `border-radius` 档外字面值（**统计不判 finding**） |

**运行域定档**：W 级不阻塞、不入钩子与 CI；E 级进发布门禁（`release.py gate`：E 级拦截、W 级统计留档）。开发期快反馈由 unit 测试承担（真实仓库冒烟 + 观察数基线断言）。纳入 pre-commit / CI 阻塞域须另行独立决策，**不随脚本改动顺带发生**。

**流程管控**：白名单只减不增（新增须带理由并复审，未命中任何现行行的条目会被告警点名，应及时删除）；收敛优先于豁免——能等值收敛到 token 的一律收敛，白名单只兜契约钦定值与恒定/派生域。

**使用逻辑**（怎么跑 / 退出码 / finding 处置 / 何时跑）

```bash
.venv/bin/python scripts/check-style-guardrails.py       # 检查全部（E + W）
.venv/bin/python scripts/check-style-guardrails.py -v    # 含 W 级观察清单与白名单腐化告警
.venv/bin/python scripts/check-style-guardrails.py --ci  # CI 模式（只输出 finding）
```

退出码：0 通过（W 级只统计）；2 存在 E 级 finding。

处置：E 级改回 token 引用；W 级按批次收敛，不逐个就地豁免。

> **何时跑**：发布门禁 `release.py gate` 内置（E 级拦、W 级留档）；开发期由 unit 测试快反馈，不入 pre-commit 与 CI。

## 发布类

**`check-version-consistency.py` — 版本号一致性检查**

**设计逻辑**（为什么存在 / 判什么 / 怎么判 / 边界与取舍）

发布版本前必须运行。检查 `APP_VERSION`（`src/python/core/constants.py`）与以下文件的版本号是否一致：

- `pyproject.toml`（`version` 字段，`--fix` 可自动同步）
- `README.md`
- 版本受检管理文档 10 份：`plan.md`、`technical.md`、`requirements.md`、`testplan.md`、`review-findings.md`、`llm-technical.md`、`folders.md`、`test-coverage.md`、`changelog.md`、`developer-guide.md`
- `folders.md` 另含一条 `evolution_head` 断言：版本演进对照表「当前开发版（」列头版本号与 `APP_VERSION` 同步（与文档版本头双点校验，发版漏改即报错，`--fix` 可自动同步）；断言只锚列头文本，表内统计数据行的刷新义务在「版本发布流程 ② 发布数据文档刷新」

**使用逻辑**（怎么跑 / 退出码 / finding 处置 / 何时跑）

```bash
# 无参数运行，逐项检查并报 [OK]/[ERR]
.venv/bin/python scripts/check-version-consistency.py
```

全部 `[OK]` 方可提交。如有 `[ERR]`，按提示逐个同步（或在发布准备阶段让 `--fix` 代劳），然后重跑直到全部通过。版本切换工作流见下文「版本发布流程」章节。

> **何时跑**：`git commit` 时钩子的版本一致性守护；发布门禁（P2）与 CI `guards` 兜底；`release.py prepare` 会带 `--fix` 把受检清单一次同步。

**`release.py` — 发布流程分步编排**

**设计逻辑**（为什么分步 / 归档为什么进脚本 / 质量与流程怎么把控）

**① 分步不连锁**：把「版本发布流程」固化为可执行子命令，每步独立可审阅、失败即停——避免一次跑完才发现中途出错；数据刷新按变更面条件跳过（纯文档变更不跑 bench/collect），发布会话墙钟与分步耗时进台账可对拍。

**② 归档按「机械 / 判定」切分**：**搬什么、搬去哪、批次标题怎么写、头部怎么派生、引用怎么改、目录树怎么摆**都是机械动作，固化进脚本（纯变换在 `_ledger_archive.py`，命令编排与落盘顺序在 `_archive_flow.py`，入口 `release.py` 只留 CLI 壳与路径常量）；**条目是否真属于本版、完成标记是否打对、设计文件是否真完成、摘要要不要精简**仍需人判断，脚本不改语义。由此过去每次发布最耗时的四项人工迁移降为「自动 + 复核」。

**③ 归档质量的三层把控**（缺一层都不算把住）：

| 层次 | 载体 | 挡住的失效 |
|:-----|:-----|:-----------|
| 纯函数单测 | `test_release_archive.py::TestLedgerArchive` | 表块搬运丢行/幂等破坏/占位与头部派生错/完成节误判/目录树连接符错位 |
| **真实归档格式契约** | `test_release_archive.py::TestRealArchiveContract`（只读读仓库真实归档） | 脚本格式与磁盘既有归档漂移（自创批次标题、占位句变体、索引行不可识别、完成标记判定漏「✅ 主体交付」这类后缀形态）——尺子先量真实数据，格式常量一漂就红 |
| 门禁断言 | `gate` 前置 + `check` 前置 | 漏迁档（表未搬空/缺批次节）、仍是开发版、新小版本 train 缺归档文件或目录树块 |

三层之外，**人工只复核语义**：迁入条目是否确属本版、`docs/plan` 候选是否真完成、要不要另写摘要。

**④ 流程把控（三个时点各有一道闸）**：
- **入口（`check`）**：除分支/工作树/版本形态/tag 外，提前校验「该发布版的归档前置」——三份归档文件与 folders.md 的 `vX.Y.x/` 归档子树块；新小版本首份归档缺件在此报出（另可直接跑 `archive-init` 一次补齐），而不是等 `prepare` 改完版本全链后中途撞上（那时需回滚）。
- **中途（`prepare` 内置 archive）**：**先算后写 + 整体回滚**——纯函数先在内存算出全部结果；设计文件迁档三连为「**引用改写 → 目录树 → `git mv`**」，三处落盘前对全部目标文件（changelog / plan / rf / folders / CLAUDE.md / README / 同级设计文档）拍文本快照，任一步失败即**整体回滚**，不会留下「引用已改指新路径、文件却没搬」或「树已改、文件没动」的错位状态；台账最后落盘，此时仍原样。收尾自动 `doc-drift --sync` + `check-doc-traces --ci` + `check-doc-links --ci`，把文档面 finding 留在本地。
- **历史归档不改写（快照原则）**：`docs/archive/**` 内的旧路径引用**不随迁档改写**——那是历史记录，改写即篡改当时事实。脚本改为在 `archive` 输出里列 `[!] 历史归档仍按快照保留旧路径引用，涉及：…`，由人判断是否处理（通常不需要）。
- **出口（`gate`）**：断言该版本 rf 已解决表已搬空 + 归档存在对应批次节，不满足即在 regression 前中止（省掉一次 20s 白跑，也不靠人记）。

**使用逻辑**（分步命令 / 自动人工边界 / 格式契约 / 何时跑）

```bash
.venv/bin/python scripts/release.py check     # 预检：分支/工作树/版本形态/tag/版本一致性 + 归档前置
.venv/bin/python scripts/release.py archive-init  # 新小版本首发：三份归档 + folders 目录树块 + 三处索引行一次建齐（幂等，--dry 只报告）
.venv/bin/python scripts/release.py prepare   # 版本全链 + changelog 发布段归档 + 一致性 --fix + 台账/设计文件归档迁移 + 收尾 doc-drift --sync
.venv/bin/python scripts/release.py archive   # 单独重跑归档迁移（--dry-run 只报告、--skip-design-docs 只做台账）；prepare 已内置，通常无需单独执行
.venv/bin/python scripts/release.py refresh   # bench --update-docs（发布子集四档，--full-bench 全量）+ collect + doc-drift --sync
.venv/bin/python scripts/release.py evolution --release   # 演进对照快照（默认只滚当前开发版列）+ 收尾 doc-drift --sync
.venv/bin/python scripts/release.py gate      # P2：regression + 十守护 --ci + 设计护栏（gate 内置）
.venv/bin/python scripts/release.py publish --title "<发布主题>"   # release 提交 + P1 verify + --no-ff 合并 + tag
.venv/bin/python scripts/release.py devbump    # 切下一开发版并提交
```

`publish` / `devbump` 默认不推送（只打印推送命令），`--push` 才执行。

**`prepare` 不跨版本发布**：发布版恒等于开发链推导值（`0.14.1-dev` → `0.14.1`）。带 `--version` 且与推导值不一致时**立即中止（exit 2）**并打印四步指引（改 `APP_VERSION` → `check-version-consistency --fix` → 同步 changelog 开发段头与 rf 台账节头 → 提交后重跑），不再「按推导执行」跑到中途才报错。

**归档迁移的自动 / 人工边界（`prepare` 内置，可 `--no-archive` 跳过）**：

| 步骤 | 自动完成的部分 | 仍需人工判定 |
|:-----|:---------------|:-------------|
| rf 已解决表 | 表格块**整块原样搬入**归档新增批次节（含原分隔行；表外散文留主台账）、主台账留迁档占位（**只保留本版占位节——更早批次占位随本次迁档收敛，节内若还有人工备注则保节保散文只摘占位行**）、归档头部「涵盖版本」区间尾延展与「归档时间」追加本批、主文件归档索引区间延展 | 条目是否确属本版、是否需要另写摘要 |
| plan 完成任务 | 标题含完成标记（`✅`/`已完成`，可带后缀如「✅ 主体交付」）的节整节搬入计划归档——台账里的任务节嵌在 `### P1~P4` 分组下（`####`），归档侧一律降为扁平 `## plan-N … ✅`（归档按版本批次堆叠，不分优先级层） | 标记是否打对（在办项被打标会被搬走） |
| `docs/plan` 设计文件 | 引用编号**全部已归档**者判定为候选（强信号）、`git mv` 到该版本归档子目录 `<stem>/`、改写 changelog/plan/rf/folders/README/CLAUDE 与同级设计文档引用、folders 目录树条目搬迁 | 候选是否真完成；未引用任何任务编号的设计文件只列提示、不自动迁档 |
| changelog 发布段 + 主文件指针 | 发布段正文整段迁入该版本 changelog 归档、归档头部两行由段列表派生、主文件「最近发布」指针的**版本号 / 日期 / 归档文件名三者同步改写**（跨小版本时文件名会变，如 `0.13.x → 0.14.x`） | 发布段正文是否确实属于本版（摘要与措辞） |

**格式随既有归档走（不另立一套）**：批次标题 `## 开发期已修复（X.Y.Z-dev）`、说明行 `> 完整复盘见 changelog.md X.Y.Z-dev 段；此处为台账原表搬运（无损），本批发布日 DATE。`、plan 归档扁平 `## plan-N … ✅`、归档头部 `涵盖版本` 只延展区间尾（`vA → vB`）、`归档时间` **只追加**本批戳记（既有逐批叙述只读）。头部缺行（无 `> 涵盖版本：` / `> 归档时间：`）时脚本报 `[!]` 提示补，不静默放行。

**何时跑 / 失败怎么办**：

| 场景 | 动作 |
|:-----|:-----|
| 正常发布 | `check → prepare`（归档已内置）` → refresh → evolution --release → gate → publish → devbump`，无需单独跑 `archive` |
| 想先看动作再落盘 | `archive --dry-run`（只报告将搬迁的条目/文件与目标位置，不写任何文件） |
| 只想搬台账、暂不动设计文件 | `archive --skip-design-docs` |
| 台账想分开提交 / 人工迁档 | `prepare --no-archive`；`gate` 会拦截未迁档 |
| 新小版本（`vX.Y.0`）首份发布 | 先跑 `archive-init`（幂等）——一次建齐该小版本的三份版本归档文件（changelog / plan / review-findings，头部按既有格式写全）、folders.md 目录树的 `vX.Y.x/` 子树块、以及 plan / rf / changelog 三处「归档档案」索引行（区间口径），收尾自动 `doc-drift --sync`；完成后 `check` 即可通过。`archive-init --dry` 只报告将做什么 |
| 归档步失败 | `[ERR]` 已给出具体原因与「台账未改写」状态：补好前置（目录树块/归档文件/头部行）后**重跑同一条命令**即可（变换幂等，重复执行不会二次搬运） |
| 首次实战 / 大改后复验 | 在 `git clone --no-hardlinks` 的副本里跑 `prepare --date <日>` 全链演练（副本自带 `.venv` 或复用主仓解释器），按上表逐项核对产出后再在真仓执行——不污染工作树、不产生 tag |

**bench 范围（refresh）**：默认只测发布口径关心的四档 `unit` / `dev-verify` / `regression` / `integration`——全量十四档串行约 5.5 min（2 路采集 3.2 min），占单次发布机器时间约 75%，其余模式与这四档高度重叠；未测模式的耗时与计数按 `--update-docs` 口径「保留上次实测值」不写脏，需要全量复测时加 `--full-bench`（或直接 `test-runner.py --mode bench --update-docs`）。

**耗时与 token 台账（`logs/release.jsonl`）**：每个子命令结束追加一行 JSON——`command` / `ok` / `elapsed_s` / `version` / `steps[]` / `agent{}`（执行环境身份：`provider`/`model`/`thinking`/`session_id`，取自 `PI_PROVIDER`/`PI_MODEL`/`PI_REASONING_LEVEL`/`PI_SESSION_ID`；非 agent 环境省略）/ `session_usage{}`（agent 会话**累计** token 快照：`input`/`output`/`cache_read`/`cache_write`/`total`/`cost`，取自 `PI_SESSION_FILE` 会话 JSONL 的 assistant 消息 + 非消息用量（cache_warm 等）+ compaction 三类条目，与 pi 自身 token 统计同口径；非 agent 环境省略该字段，旧台账行形状不变）（gate 的 `P2 场景回归`·`P2 十守护`·`P2 设计护栏`、refresh 的 bench·collect·sync、publish 的 `P1 verify`、evolution 的快照统计·统计同步、prepare 的 `台账归档迁移`）；终端尾行同步打印摘要。`logs/` 属 git 忽略域，台账不入仓库、不参与门禁，写入失败只打 `[!]` 且不改退出码（观测面不阻断发布）。跨版本对拍：`tail -n 20 logs/release.jsonl`（发布墙钟的变化归因到此，不再靠现场重测）。**token 统计口径**：窗口 = 上一次 `devbump` 之后的行，用量 = 末行累计 − 边界行累计（跨会话按正增量分段累加，不会出现负数）；每条命令尾行自动打印「执行环境：provider/model（thinking=…）」与「本次发布累计 token：N tok（in/out/cache r/w，≈¥C）」，便于把发布成本按版本对拍。

## 诊断类

**`perf-test-report.py` — 端到端性能基准**

生成 20+ 品种 + 3 年模拟持仓，运行 basic/both 报告生成管线，测量各阶段耗时。

```bash
.venv/bin/python scripts/perf-test-report.py

# 门禁模式：未达标退出码 2（供 CI 拦截性能回归）
.venv/bin/python scripts/perf-test-report.py --gate
```

**输出**：`docs/tmp/better-investment-performance-test-report.md`

**目标**：basic 模式总耗时 < 60s

**门禁归属**：本脚本是**性能测试**（主动压测，同条件可比），故承担 CI 性能门禁（`perf-gate` job）；运行历史查看（`perf-view.py`，样本不可控、不可复现）不用于门禁。

**可靠性保障**：**传输层离线**（`_install_offline_network()`：socket 出口瞬时 `OSError` 走既有降级 + `time.sleep` 置零消掉重试退避）对一切外部抓取兜底，行情/K线历史/交易日历三处咽喉另打桩让热点路径仍走真实计算——门禁测的是代码性能而非网络状况（冷缓存断网全流程 2.8s）；`_isolate_state_writes()` 把 perf 历史/健康快照/熔断状态重定向到临时目录，基准运行不污染 `perf-view` 统计样本与真实运行的供应商熔断状态。

**`perf-view.py` — 性能历史趋势查看**

读取 `data/state/perf_history.jsonl`（由 `PerfCollector` 在每次报告生成时自动追加），按版本和报告类型分组统计（分组节按各组**首次运行时间**排序，最新版本在最末；组内明细行按时间戳升序），输出版本间性能趋势对比；输出跨版本「总体分位概览」（样本数 / 平均 / 中位 / **P95** / **P99** / 最长 / 中位秒每品种，n<20 附小样本提示）、**版本演进总表**（每版中位/P95/较上一版 delta+⚠，按首现时间排序）、离群与尾部归因、**异常运行专区**（中断/失败，无则省略）与**同版本漂移检测**（时间对半、噪声带判显著）。头部含**数据新鲜度**行（最新记录时间戳与距今时长）与可选**版本筛选**行；组详情阶段表按**中位降序**（最慢在前）并含**占比**列；阶段细分/LLM 上下文在范围内应有数据而缺时**明示提示行**（区分「无数据」与「不适用」）而非静默省略。`--by day|week|hour` 时段聚合在耗时列外附**费用合计/费用环比**（与 LLM 段「累计费用」同源的 `llm.total_cost`，范围内无费用样本自动省列，首档环比为 —、末档附提示行）；`--json` 汇总带 `llm_cost` 费用块（`--by` 时另附 `by_period` 时段费用序列），CSV 列不变。

```bash
# 输出全部历史趋势到 stdout（--json/--csv 机读模式同样只向 stdout，落盘需自行重定向）
.venv/bin/python scripts/perf-view.py

# 按日聚合：耗时与费用合计/费用环比同表（LLM 费用趋势视图）
.venv/bin/python scripts/perf-view.py --by day

# 仅看 full 类型报告的性能趋势
.venv/bin/python scripts/perf-view.py --report-type full

# 仅看某版本系列（前缀匹配，0.13.4 可命中 0.13.4-dev）
.venv/bin/python scripts/perf-view.py --version 0.13.4

# 仅看最近 30 条记录
.venv/bin/python scripts/perf-view.py --last 30

# 同时写入 docs/tmp/perf_trend.md
.venv/bin/python scripts/perf-view.py --save
```

**输出列说明**：

| 列 | 含义 |
|:---|:------|
| 阶段 | 报告生成管线阶段名称（行情获取/快照对比/历史走势/HTML 生成/Excel 生成 等） |
| 平均耗时 | 该阶段历史平均耗时 |
| 最短/最长 | 该阶段历史最小/最大耗时 |
| 次数 | 该阶段出现次数（条件阶段如历史走势仅在启用时出现）；行序按**中位降序**（最慢阶段在前，同分按名） |
| 占比 | 阶段均值 ÷ 组平均总耗时；并行执行的阶段之和可超 100% |
| 阶段细分 | 父阶段下的子项自身耗时（如 `LLM+新闻` → 四个 LLM 模块与新闻获取）；子项可并行，**之和不等于父阶段耗时**，仅用于定位瓶颈（子项按平均耗时降序） |

**分位口径**：`总体分位概览`与各分组的 P95/P99 均为**最近秩**（nearest-rank）分位——取 `ceil(pct% × n)` 位样本值，统一表述为「95% 的报告在 Xs 内完成，99% 的报告在 Ys 内完成」（概览口径行同句式：P95 即 95% 的报告在该耗时内完成，P99 即 99% 的报告在该耗时内完成；两段均带全主语，不分省略变体）。概览口径与分组一致（受 `--report-type` / `--last` 影响）；仅单一报告类型时只渲染合计行（不重复出类型行）。

**稳健统计与归因**（`--exclude-outlier` / `--by`）：

| 能力 | 口径 |
|:-----|:-----|
| 离群运行段 | 总耗时 > 中位 + 3.5 × 1.4826 × MAD 判为离群（MAD 为 0 时不判，避免把正常抖动误标）；显式列出而非静默剔除 |
| 稳健均值 | 剔除离群点后的均值（无离群时等于普通均值），与普通均值并列展示 |
| `--exclude-outlier` | 按上述口径剔除离群运行后重算全部统计（服务端超时重试等外部故障不再抬高均值） |
| 阶段级分位 | 阶段表含中位与 P95（不只均值/极值） |
| 尾部归因 | 最慢一次运行逐阶段 z 分数与「相对历史中位倍数」，直给哪一步超常 |
| `--by day\|week\|hour` | 按时段聚合（样本数/中位/P95/最长），看工作日-周末与 LLM 服务端高峰差异 |
| LLM 运行上下文段 | 重试次数与退避等待、端点节流等待、provider 降级、缓存命中/未命中、累计费用与 provider/模型分布——回答「时间花在白等还是真推理」 |
| `--compare 旧 新` | 版本间阶段级对比（中位 delta / 倍数 / 变异系数判显著）；显著性口径：变化幅度需超过两版本各自变异系数之和 × 较大中位值（噪声带），避免把抖动当回归 |
| `--json` / `--csv` | 机读输出，**只向 stdout 打印**（需自行重定向落盘；`--save` 在机读模式不适用，会打警告）——`--json` 为信封 `{record_count, records, summary}`（summary 与 Markdown 各段同源：分位/按类型/离群/异常/演进/漂移）；`--csv` 每运行一行，含 `per_holding_seconds`/`outlier`/`slowest_phase`/`interrupted_stage`/`errors_count` 列 |
| `--version 前缀` | 仅查看版本前缀匹配的记录（`X.Y.Z` 命中带后缀的同系列版本；头部明示「版本筛选」行），与 `--report-type`/`--last`/机读输出同口径生效 |
| `--summary` | 仅输出概览段（总体分位/离群/尾部归因/LLM 上下文/时段聚合/对比），略去逐版本分组详情 |
| `--outlier-k 系数` | 自定义离群判定系数（中位 + k × 1.4826 × MAD，默认 3.5）；系数越小越敏感 |

**定位边界（重要）**：本脚本是**运行历史查看**（被动统计既有记录）——样本取决于最近跑过什么、不可复现，故**不用于 CI 门禁**。性能门禁由主动压测的 `perf-test-report.py --gate` 承担（自造模拟持仓、mock 外部数据源，同条件可比，退化即回归）。

**数据来源**：每次 `generate_report()` 调用时自动记录到 `data/state/perf_history.jsonl`（自动保留最近 5000 条，超出丢弃最旧），无需手动触发；中断运行以 `status=interrupted` 记录（含 `interrupted_stage`），与成功完成（`completed`）区分，页头状态行据显「已中断」。

**记录字段分层**（观测面口径）：

| 字段 | 含义 | 是否参与总耗时 |
|:-----|:-----|:---------------|
| `phases` | 粗粒度阶段墙钟（数据准备/快照对比/历史走势/行业资金流向/LLM+新闻/HTML 生成/Excel 生成） | **是**（`total_seconds` 唯一来源，保证跨版本可比与 ETA 口径稳定） |
| `breakdown` | 父阶段下的子项自身耗时（LLM 四模块、新闻获取） | 否（子项可并行） |
| `counters` | 运行期诊断计数（`warnings`/`errors` 等） | 否 |
| `llm` | LLM 运行上下文（provider/model/thinking、重试与节流等待秒数、provider 降级次数、缓存命中、逐模块 tokens/费用） | 否 |
| `errors` / `warnings_count` | 错误消息（封顶保留）与告警数 | 否 |

`counters` 的 `warnings`/`errors` 由 `PerfCollector` 在首个阶段计时时挂上的只计数日志 handler 自动采集（`invest` logger 的 WARNING/ERROR），`save()` 时摘除——告警来源分散在 `reporter.add_error` 与各模块 `logger.warning`，集中采集避免逐点改造与新增链路漏登记。

`llm` 上下文由 `llm/observation.py` 的运行观测汇聚器（`bind_llm_observation` / `current_llm_observation`）在调用链上归集：重试退避（`core/retry.py` 的 `on_retry` 回调）、端点节流等待（`llm/pacing.py` 的 `PacingGate`）、provider 命中与降级（`llm/api.py` 的 provider 链）、模块级缓存命中（`generators_orchestrator` 预检）、逐模块 model/tokens/费用（`llm/session.py` 单源）。未绑定汇聚器时（如单测直调 LLM 层）所有记录调用为空操作，行为零变化。

**`probe.py` — 探测统一入口（target 分发 registry）**

所有连通性/可用性探测统一走 `scripts/probe.py <target> [options…]`：target 实现在 `scripts/probes/<语义名>.py`（声明 `PROBE_TARGET` / `build_parser()` / `run(args)` 契约面并在 `probes/__init__.py` 登记），**全部纯只读**（不写缓存/熔断/降级记录，无副作用）；新探针只需新增子模块并登记，入口无需改动。现有 target：

- `csi` — CSI 风格指数可用性探测（因子暴露分析已实施，现为**周期性复核**工具：新机器/新窗口验证指数链路与停更预警，条数+新鲜度双维度判定）
- `push2` — 东方财富 push2 连通性诊断（见下）

旧入口 `probe-csi-factor-indices.py` / `probe-push2.py` 保留为**薄委托垫片**（用法不变，内部直接调用对应 target），新用法统一走 `probe.py <target>`。

旧入口 `probe-csi-factor-indices.py` / `probe-push2.py` 保留为薄委托垫片，命令用法不变。

**`csi` target — CSI 风格指数可用性**：判定全量 5 因子 / MVP 3 因子 / 不可行；建议数据回归前置运行一次。

```bash
.venv/bin/python scripts/probe.py csi --days 365
```

**`probe-push2.py` — 东方财富 push2 连通性诊断**

东方财富 push2 连通性探测，用于区分「程序缺陷」与「网络环境拦截」。部分电脑运行报告时 push2 频繁出现 `Server disconnected without sending a response`（服务器接受 TCP 连接但未返回响应即断开），触发熔断退避（60s→300s→900s→3600s）后降级到备用链路——用此脚本可快速定位根因，决定是否需要调整代码或加速降级。

```bash
.venv/bin/python scripts/probe.py push2     # 默认探测 3 次（旧命令 probe-push2.py 等效）
```

判读：
- **三次全部成功** → 网络正常，之前失败为临时抖动/时段性，无需改动
- **三次全失败、且 curl 对照也失败** → 网络/防火墙/代理拦截 push2，属环境问题（curl_cffi 指纹大概率无效，可考虑加速降级）
- **脚本失败、curl 对照成功** → httpx/TLS 指纹被 WAF 拦截，curl_cffi 浏览器指纹方案才有价值

curl 对照命令：`curl -s "https://push2.eastmoney.com/api/qt/stock/get?secid=1.000001&fields=f58"`。纯只读探测，不写缓存/熔断/降级记录，无副作用。

**`check-svg.py` — README SVG 架构图检查（三合一）**

README 首屏架构图（`src/static/architecture.svg` / `llm-chain.svg` / `capabilities.svg`）的渲染质量检查，改图后用于验证文本不越界/重叠。三个渲染质量检查（几何/像素越界/文字色越界）合并为一个带子命令的统一入口（注意：**均带 `--ci` 与退出码语义**，0=通过 / 1=缺 Pillow / 2=发现越界）。

```bash
# 几何审查：文本越界 / 贴边 / 文本重叠（估算字体宽度；矩形底部不齐仅作提示，不计入退出码）
.venv/bin/python scripts/check-svg.py geom <svg路径…>

# 像素审查：副标题行区域亮色像素是否越出卡片右缘（需 Pillow）
.venv/bin/python scripts/check-svg.py pixel <png> <scale> <card_r> <row_y0> <row_y1> <margin>

# 像素审查：精确匹配文字色像素越界（需 Pillow）
.venv/bin/python scripts/check-svg.py text-overflow <png> <scale> <card_r> <y0> <y1> <margin>
```

参数含义：`scale` = px per svg unit；`card_r` = 卡片右缘 x（svg 单位）；`row_y*/y*` = 检测区 y 范围（svg 单位）；`margin` = 检测范围到卡片右缘的右扩量（svg 单位）。几何审查纯标准库；两个像素子命令需 Pillow（`pip install -e '.[svg]'`，缺失时给出可读指引并以退出码 1 结束）。

> **当前状态**：三张 SVG 均通过 `geom`——卡片内文本按估宽模型的右余量 ≥10px（`capabilities.svg` ≥19px）。贴边阈值由 `_PADDING_WARN`（6px）定义，矩形底部不齐仅作提示项（流程图同列卡片高度本就允许不同）。**改图后请重跑本脚本**；本脚本不在提交前/发布前门禁清单内，按需运行。

**`factor_zoo_eval.py` — 因子动物园目录评测（非生产代码）**

「先评测后立项」的评测器：五个来源族各抽 5 个代表因子（共 25），判三项指标——**A** 字段可得率
（≥20/25 因子可完整计算）、**B** 与既有信号族的增量（|ρ|<0.5 的因子占比 ≥30%、分母 ≥10）、
**C** 全量计算耗时占比（÷ 基线报告耗时 ≤20%）。**A/B/C 全过 → 转正立项**（另起实现计划）；
任一不过 → 归档「已评估未采纳」。

```bash
.venv/bin/python scripts/factor_zoo_eval.py catalog   # 25 因子清单冻结（字段需求/口径入 JSON）
.venv/bin/python scripts/factor_zoo_eval.py fields    # 穿透股票池冻结 + 逐因子字段可得性 → 指标 A
.venv/bin/python scripts/factor_zoo_eval.py signals   # 可计算因子近 1 年横截面信号 vs 既有信号族 → 指标 B
.venv/bin/python scripts/factor_zoo_eval.py timing    # 取数/计算耗时与缓存命中 + 报告耗时基线 → 指标 C
.venv/bin/python scripts/factor_zoo_eval.py verdict   # 三项指标汇总判定（阈值预注册于判定书）
.venv/bin/python scripts/factor_zoo_eval.py all       # 依序执行全部阶段
```

**纪律**：取数只经既有 Provider Chain / 网关（禁裸调 provider）；**不 import `report/` 与 `llm/`**、
不向生产模块注入代码（生产侧零改动）；穿透股票池只读复用（不重算穿透）；相关性复用
`analysis.correlation` 的共享 Pearson 原语（防评测口径漂移）；评测产物**只落 `docs/tmp/factor-zoo/`**
（git 忽略）。实现拆在 `_factor_zoo/`（因子清单 / 指标计算 / 报告渲染）。

## 启动脚本

**`launch.sh` — Linux/macOS 启动**

```bash
./scripts/launch.sh
```

**`launch.ps1` — Windows PowerShell 启动**

```powershell
.\scripts\launch.ps1
```

两者均负责：激活虚拟环境（如存在）、设置 `PYTHONPATH`、启动主程序 TUI。

**`launch.sh web` / `launch.ps1 web` — Web 浏览器模式**

```bash
./scripts/launch.sh web                       # Linux/macOS，默认监听 http://127.0.0.1:8000
./scripts/launch.sh web --port 8080           # 换端口
./scripts/launch.sh web --host 0.0.0.0        # 局域网访问（绑定非回环地址需自行评估暴露风险）
```

```powershell
.\scripts\launch.ps1 web                      # Windows，默认监听 http://127.0.0.1:8000
.\scripts\launch.ps1 web --port 8080
```

`web` 子命令启动轻量 Web 服务（`src/python/web/server.py`），浏览器打开提示地址即可上传持仓、选择报告格式（基础/标准/完整）、实时查看生成进度并预览/下载产物；亦支持 `--config <path>` 指定备用配置文件（详见 [快速开始](../manuals/how-to-start.md) 方式四）。同一时间仅执行一个报告生成任务（单 worker 串行队列），新任务自动排队。

**`cli.sh` / `cli.ps1` — CLI 命令行包装**

CLI 模式的便捷入口，跳过 TUI 界面，直接以命令行模式运行。**无参数调用时默认生成报告**（`report --type both`，Excel+HTML 双格式，不含 LLM——全部页签有数据）；传入参数时原样透传给 CLI。

```bash
# Linux/macOS
./scripts/cli.sh                        # 无参数 -> 默认生成报告（both，Excel+HTML）
./scripts/cli.sh report --type full     # 生成全量报告（含 LLM）
./scripts/cli.sh cache --stats          # 查看缓存状态
./scripts/cli.sh --help                 # 查看 CLI 帮助
```

```powershell
# Windows PowerShell
.\scripts\cli.ps1                        # 无参数 -> 默认生成报告（both，Excel+HTML）
.\scripts\cli.ps1 report --type full     # 生成全量报告（含 LLM）
.\scripts\cli.ps1 cache --stats          # 查看缓存状态
.\scripts\cli.ps1 --help                 # 查看 CLI 帮助
```

与直接调用 Python 模块**完全等效**（二选一即可）：

```bash
.venv/bin/python -m src.python.cli report --type both      # Linux/macOS 直调
.venv\Scripts\python.exe -m src.python.cli report --type both   # Windows 直调
```

> 注意：包装脚本的「无参数默认 both」与 CLI 本身的 `--type` 默认值（basic，仅 Excel）不同——直接直调 `.venv/bin/python -m src.python.cli report`（不带 `--type`）仍走 basic 轻量模式（只生成核心页签，新闻/历史/LLM 等页签为降级占位）。包装脚本无参数时自动补 `report --type both`，确保拿到完整非 LLM 报告。

包装脚本相比直调的好处：自动切换到项目根目录、自动定位虚拟环境解释器（避免误用系统 python 缺失 pandas 等依赖）、无参数时自动补 `report` 子命令。CLI 完整参数说明见 [快速开始](../manuals/how-to-start.md) 的「CLI 命令行模式」一节。

**`llm.sh` / `llm.ps1` — 完整报告快捷入口**

只做一件事：生成含 LLM 分析章节的完整报告，等价于 TUI 菜单的「生成完整报告（Excel+HTML，含 LLM）」。
子命令与报告类型写死在脚本里，免去每次敲 `report --type full`。

```bash
./scripts/llm.sh                  # 生成完整报告（含 LLM）
./scripts/llm.sh --force-llm      # 强制重新调用 LLM，跳过缓存
./scripts/llm.sh --history off    # 本次不获取组合历史走势
```

```powershell
.\scripts\llm.ps1 --force-llm
```

追加的参数即 `report` 的报告级参数（`--type` / `--history` / `--force-llm`）；组合历史走势不写死，
由配置 `history.fetch_mode` 决定（与 TUI 菜单一致）。需要全局参数（`--config` / `--output` /
`--experiment` / `--feature`）时仍走 `cli.sh` / `cli.ps1`——它们必须写在 `report` 子命令之前。

## CLI 子命令

**`check-sources` — 数据源健康检查**

跳过 TUI 交互界面，直接测试各数据源联通性并报告延迟。

```bash
# 运行数据源健康检查
.venv/bin/python -m src.python.cli check-sources
```

**输出示例**：

```
数据源健康检查结果 (YYYY-MM-DD)
──────────────────────────────────────────────────────────
  ✅  腾讯财经      行情           45ms  正常
  ✅  新浪财经      行情           82ms  正常
  ⚠️  天天基金      持仓/排名     2.3s  响应慢
  ❌  财联社        新闻           timeout  连接超时
```

**检查覆盖范围**：腾讯财经行情、新浪财经行情、东方财富净值、天天基金持仓/排名、东方财富行业分类、新浪财经新闻、东方财富新闻、华尔街见闻、财联社、腾讯 K 线——共 **10 个端点**。

**退出码**：0=全部正常，1=有告警（部分源慢），2=有失败。

**`cassettes` — 数据源记录-回放维护**

维护已录制的真实数据源响应（见上文「数据源真实响应录制与回放（cassette）」）。与 `doctor` 同例：**无需配置、不受任何实验开关约束、不发起网络请求**。

```bash
# 列出已录制响应（来源/录制时间/交互数/大小）
.venv/bin/python -m src.python.cli cassettes

# 逐条离线回放并交给当前解析器解析（不联网）
.venv/bin/python -m src.python.cli cassettes --verify
```

**`--verify` 输出标记**：`[OK]` 解析正常；`[!]` 该 cassette 未登记解析器（只校验文件可读，不伪造成 OK）；`[ERR]` 解析器吃不下已录制的真实响应体——**上游格式可能已变，需重新录制**。

**退出码**：0=正常（含列表模式与全部 `[OK]`/`[!]`），2=有录制的解析路径失败。

**`doctor` — 系统自检**

一次性盘点「跑不起来」的常见根因，分环境/配置/目录/功能开关/数据源适配/数据源凭据/数据源七组，失败项附可执行修复建议。与 `check-sources` 的分工：后者只测数据源联通性，前者还覆盖解释器/虚拟环境、配置可解析与关键字段、目录可读写。

```bash
# 完整自检（含数据源网络检查）
.venv/bin/python -m src.python.cli doctor

# 仅查本地环境/配置/目录，跳过网络（瞬时返回）
.venv/bin/python -m src.python.cli doctor --offline

# 收紧网络检查的整体耗时预算（秒，默认 8）
.venv/bin/python -m src.python.cli doctor --timeout 5
```

**无需配置**：与 `view-logs` / `cassettes` 同例，在 `init_config()` **之前**分派——配置损坏正是自检要定位的场景，若被配置初始化拦住即成死锁。

**不受开关约束**：TUI 菜单 `[T]` 与 Web 自检卡片由 `doctor_check` 门控（该开关默认开启），但 CLI 子命令始终可用（同理，被开关拦住就失去了诊断手段）。

**退出码**：0=全部通过，1=有失败项（`_EXIT_PARTIAL`）。自检有失败项不算命令本身失败——命令跑完了并给出了结论，故用 PARTIAL 而非 SEVERE。

**`view-logs` — 查看结构化运行日志**

按级别/时间过滤读取日志尾部，**无需配置**（配置损坏时仍可查看日志诊断）。

```bash
# 查看最近日志（默认读末尾 5000 物理行）
.venv/bin/python -m src.python.cli view-logs

# 只看 ERROR + CRITICAL
.venv/bin/python -m src.python.cli view-logs --level ERROR

# 只看指定日期之后 / 只读末尾 200 行
.venv/bin/python -m src.python.cli view-logs --since 2026-08-16
.venv/bin/python -m src.python.cli view-logs --lines 200
```

级别/时间过滤与尾部读取逻辑全部委托 `core/log_reader.read_log()`（与 TUI 菜单 `[V]` 同一实现）。

## LLM 幻觉率采样测试

对 **10 组标准化持仓数据** 调用当前 prompt，经事实校验器验证后统计幻觉率（`scenario_llm` 幻觉率采样测试）。

**数据集简介**：

| # | 名称 | 品种数 | 测试重点 |
|---|------|:------:|----------|
| 1 | 基本 A 股组合 | 3 | 标准正收益场景 |
| 2 | 混合基金组合 | 5 | 股+基混合，部分亏损 |
| 3 | 含较大亏损组合 | 4 | 亏损品种描述准确性 |
| 4 | 权重集中组合 | 3 | 集中度风险描述 |
| 5 | 分散组合 | 8 | 多品种小额分散 |
| 6 | 多账户组合 | 6 | 三账户场内外混合 |
| 7 | 偏防守组合 | 4 | 高股息防守型 |
| 8 | 全基金组合 | 3 | 穿透逻辑幻觉 |
| 9 | 零成本特殊场景 | 3 | 继承/赠予零成本 |
| 10 | 极简组合 | 2 | 最小规模边界 |

**幻觉率标准**：目标 **< 5%**。每次 prompt 重大修改后应重新采样。

**脚本用法**：

```bash
# 完整采样（调用 LLM API 对 10 组数据生成分析）
.venv/bin/python scripts/llm-hallucination-sampler.py

# 仅测试特定模块（默认 expert_review）
.venv/bin/python scripts/llm-hallucination-sampler.py --module health_check

# 仅测试特定数据集（1-indexed）
.venv/bin/python scripts/llm-hallucination-sampler.py --dataset 1,3,5

# 跳过 API 调用，只构建 prompt 验证结构
.venv/bin/python scripts/llm-hallucination-sampler.py --dry-run

# 跳过缓存强制重新生成
.venv/bin/python scripts/llm-hallucination-sampler.py --force
```

**输出**：
- 报告文件：`docs/tmp/hallucination-report.md`
- Dry-run prompt 转储：`docs/tmp/hallucination-prompts-{module}.md`

**注意**：事实校验器对仓位占比百分比和情景假设百分比设跳过策略（`_POSITION_WEIGHT_KEYWORDS` / `_HYPOTHETICAL_KEYWORDS`），避免将百分比陈述误报为幻觉。最终幻觉率以 `docs/tmp/hallucination-report.md` 为准。

